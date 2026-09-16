//! What a profile selects, in the order an emitter writes it.
//!
//! Selection is emitter-agnostic: it collects the fragments the profile's
//! values contain and substitutes the vocabulary those same values declare.
//! The `emit:` filter is applied later, by each emitter, because it is the one
//! thing that differs between them.

use crate::{
    Fragment, FragmentSet, Meta, Profile,
    error::SelectionError,
    substitute::{self, Variables},
};

/// The fragments a profile composes, substituted and ordered.
#[derive(Debug, Clone)]
pub struct Selection {
    fragments: Vec<Fragment>,
    values: Vec<String>,
}

impl Selection {
    /// Collects the fragments `profile` selects from `tree` and substitutes
    /// every `{{ name }}` against the vocabulary its values declare.
    ///
    /// # Errors
    ///
    /// [`SelectionError`] when a `values.yml` does not parse, when two selected
    /// values declare the same name, or when a fragment references a name none
    /// of them declares.
    ///
    /// ```
    /// use agentcfg::{FragmentSet, Profile, Selection};
    ///
    /// let tree = FragmentSet::embedded()?;
    /// let profile = Profile::parse(
    ///     "\
    /// config_version: v1.0.0
    /// language: rust
    /// deployment: tag-only
    /// concerns: [template]
    /// emit: [agents-md]
    /// ",
    ///     &tree,
    /// )?;
    ///
    /// let selection = Selection::resolve(&profile, &tree)?;
    /// let git_flow = selection
    ///     .fragments()
    ///     .iter()
    ///     .find(|fragment| fragment.path() == "core/git-flow.md")
    ///     .expect("core is always selected");
    ///
    /// // `{{ gate_command }}` in the source; what Rust actually runs, here.
    /// assert!(git_flow.body().contains("just ci"));
    /// assert!(!git_flow.body().contains("{{"));
    /// # Ok::<(), Box<dyn std::error::Error>>(())
    /// ```
    pub fn resolve(profile: &Profile, tree: &FragmentSet) -> Result<Self, SelectionError> {
        let values = selected_values(profile);
        let variables = variables(&values, tree)?;

        // Built in axis order, then sorted by `order:` with a stable sort, so
        // ties fall back to axis and then to path without a second comparison.
        let mut fragments: Vec<Fragment> = Vec::new();
        for directory in std::iter::once("core").chain(values.iter().map(String::as_str)) {
            let prefix = format!("{directory}/");
            fragments.extend(
                tree.fragments()
                    .iter()
                    .filter(|fragment| fragment.path().starts_with(&prefix))
                    .cloned(),
            );
        }

        for fragment in &mut fragments {
            let path = fragment.path().to_owned();
            fragment.map_strings(|text| {
                *text = substitute::render(&path, text, &variables)?;
                Ok(())
            })?;
        }

        fragments.sort_by_key(order_of);

        Ok(Self { fragments, values })
    }

    /// The selected fragments, substituted and in composition order.
    #[must_use]
    pub fn fragments(&self) -> &[Fragment] {
        &self.fragments
    }

    /// The `<axis>/<value>` directories this selection drew from, in axis
    /// order. `core/` is not among them — it is not an axis.
    ///
    /// An emitter uses this to reach the files beside the fragments, such as a
    /// language value's `settings.partial.json`.
    #[must_use]
    pub fn values(&self) -> &[String] {
        &self.values
    }
}

/// Every `<axis>/<value>` the profile names, in the order they compose.
///
/// `core/` is not here: it is always included and leads, because it says how
/// to behave before an agent knows what it is doing. The axes then follow the
/// plan's table, so a repo's own concerns come last and read as additions to
/// everything above them. The order is this function's statement order, so
/// there is no separate list to fall out of step with.
fn selected_values(profile: &Profile) -> Vec<String> {
    let mut values = vec![format!("language/{}", profile.language)];
    if let Some(framework) = &profile.framework {
        values.push(format!("framework/{framework}"));
    }
    if let Some(architecture) = &profile.architecture {
        values.push(format!("architecture/{architecture}"));
    }
    values.push(format!("deployment/{}", profile.deployment));
    values.extend(
        profile
            .concerns
            .iter()
            .map(|concern| format!("concerns/{concern}")),
    );
    values.push(format!("sensitivity/{}", profile.sensitivity));
    values
}

/// The merged vocabulary of every selected value.
fn variables(values: &[String], tree: &FragmentSet) -> Result<Variables, SelectionError> {
    let mut variables = Variables::new();
    let mut declared_by: Vec<(String, String)> = Vec::new();

    for value in values {
        let path = format!("{value}/values.yml");
        let Some(contents) = tree.file(&path) else {
            continue;
        };

        let declared: Variables =
            serde_yaml_ng::from_str(contents).map_err(|source| SelectionError::Values {
                path: path.clone(),
                source,
            })?;

        for (name, text) in declared {
            if let Some((_, first)) = declared_by.iter().find(|(seen, _)| *seen == name) {
                return Err(SelectionError::DuplicateVariable {
                    name,
                    first: first.clone(),
                    second: path,
                });
            }
            declared_by.push((name.clone(), path.clone()));
            variables.insert(name, text);
        }
    }

    Ok(variables)
}

/// A fragment's `order:`. Tasks carry none and sort with the default.
fn order_of(fragment: &Fragment) -> i32 {
    match fragment.meta() {
        Meta::Rules(meta) => meta.order,
        Meta::Task(_) => 0,
    }
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;
    use crate::{EmitterName, Scope};

    fn tree() -> FragmentSet {
        FragmentSet::embedded().expect("every embedded fragment parses")
    }

    fn profile(body: &str) -> Profile {
        Profile::parse(
            &format!("config_version: v1.0.0\nemit: [agents-md, claude]\n{body}"),
            &tree(),
        )
        .expect("the test profile is valid")
    }

    fn resolve(body: &str) -> Selection {
        Selection::resolve(&profile(body), &tree()).expect("the test profile composes")
    }

    /// What `claude-mit-rust-template` declares today.
    const RUST_TEMPLATE: &str = "language: rust\ndeployment: tag-only\nconcerns: [template]\n";

    #[test]
    fn a_profile_selects_core_plus_the_fragments_inside_its_values() {
        let selection = resolve(RUST_TEMPLATE);
        let paths: Vec<&str> = selection.fragments().iter().map(Fragment::path).collect();

        // 7 core + 7 rust + 1 deployment + 1 concern. The plan counts 17
        // because it also counts `settings.partial.json`, which carries no
        // frontmatter and so is not a parsed fragment — the claude emitter
        // reads it straight from the tree.
        assert_eq!(paths.len(), 16, "{paths:#?}");
        assert!(paths.contains(&"core/behavior.md"));
        assert!(paths.contains(&"language/rust/tooling.md"));
        assert!(paths.contains(&"deployment/tag-only/release.md"));
        assert!(paths.contains(&"concerns/template/rules.md"));

        // Nothing from a value this profile did not pick.
        assert!(!paths.iter().any(|path| path.starts_with("language/go/")));
        assert!(!paths.iter().any(|path| path.starts_with("architecture/")));
    }

    #[test]
    fn declaring_an_architecture_adds_its_fragments_and_nothing_else() {
        let without = resolve(RUST_TEMPLATE).fragments().len();
        let with = resolve(&format!("{RUST_TEMPLATE}architecture: ddd\n"))
            .fragments()
            .len();

        assert_eq!(with - without, 4);
    }

    #[test]
    fn every_reference_resolves_for_both_languages() {
        for language in ["rust", "go"] {
            let selection = resolve(&format!(
                "language: {language}\ndeployment: service\narchitecture: ddd\nconcerns: [data-access, sync, template]\n"
            ));

            for fragment in selection.fragments() {
                assert!(
                    !fragment.body().contains("{{"),
                    "{} left a reference unsubstituted",
                    fragment.path()
                );
            }
        }
    }

    #[test]
    fn the_language_value_supplies_the_vocabulary_core_reads() {
        let gate_line = |language: &str| {
            resolve(&format!("language: {language}\ndeployment: tag-only\n"))
                .fragments()
                .iter()
                .find(|fragment| fragment.path() == "core/git-flow.md")
                .expect("core is always selected")
                .body()
                .to_owned()
        };

        assert!(gate_line("rust").contains("just ci"));
        assert!(!gate_line("rust").contains("make ci"));
        assert!(gate_line("go").contains("make ci"));
        assert!(!gate_line("go").contains("just ci"));
    }

    #[test]
    fn substitution_reaches_frontmatter_as_well_as_the_body() {
        // No fragment in the real tree references a variable from its
        // frontmatter yet, so this proves the documented `name: "new-{{ unit }}"`
        // form against a tree written for the purpose.
        let tree = FragmentSet::build(
            &[
                (
                    "language/rust/values.yml",
                    "unit: \"crate\"\nunits: \"crates\"\n",
                ),
                (
                    "language/rust/tasks/new-unit.md",
                    concat!(
                        "---\n",
                        "name: \"new-{{ unit }}\"\n",
                        "title: \"Adding a {{ unit }}\"\n",
                        "when: \"Adding or modifying a {{ unit }}\"\n",
                        "description: \"Add a {{ unit }} to the workspace\"\n",
                        "argument-hint: \"<{{ unit }}-name>\"\n",
                        "arguments: [\"{{ unit }}-name\"]\n",
                        "---\n\n",
                        "Scaffold the {{ unit }}.\n",
                    ),
                ),
                (
                    "language/rust/file-naming.md",
                    concat!(
                        "---\n",
                        "title: \"Layout of {{ units }}\"\n",
                        "scope: paths\n",
                        "paths: [\"**/{{ unit }}/**\"]\n",
                        "---\n\n",
                        "Body.\n",
                    ),
                ),
            ],
            &[
                ("deployment", &["tag-only"]),
                ("language", &["rust"]),
                ("sensitivity", &["none"]),
            ],
        )
        .unwrap();

        let profile = Profile::parse(
            "config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\nemit: [claude]\n",
            &tree,
        )
        .unwrap();
        let selection = Selection::resolve(&profile, &tree).unwrap();

        let task = selection
            .fragments()
            .iter()
            .find(|fragment| fragment.path().contains("tasks/"))
            .unwrap();
        match task.meta() {
            Meta::Task(meta) => {
                assert_eq!(meta.name, "new-crate");
                assert_eq!(meta.title, "Adding a crate");
                assert_eq!(meta.when, "Adding or modifying a crate");
                assert_eq!(meta.description, "Add a crate to the workspace");
                assert_eq!(meta.argument_hint.as_deref(), Some("<crate-name>"));
                assert_eq!(meta.arguments, ["crate-name"]);
            }
            Meta::Rules(_) => unreachable!("parsed from a tasks/ path"),
        }
        assert_eq!(task.body(), "Scaffold the crate.");

        let rules = selection
            .fragments()
            .iter()
            .find(|fragment| fragment.path().ends_with("file-naming.md"))
            .unwrap();
        assert!(matches!(
            rules.meta(),
            Meta::Rules(meta)
                if meta.title == "Layout of crates" && meta.paths == ["**/crate/**"]
        ));
    }

    #[test]
    fn order_decides_position_and_ties_fall_back_to_axis_then_path() {
        let selection = resolve(RUST_TEMPLATE);
        let paths: Vec<&str> = selection.fragments().iter().map(Fragment::path).collect();

        // The two fragments carrying `order: -1` lead, core before language.
        assert_eq!(
            &paths[..2],
            ["core/git-flow.md", "language/rust/tooling.md"]
        );

        // Everything else keeps axis order, and path order inside an axis.
        let rest = &paths[2..];
        let core: Vec<_> = rest.iter().filter(|p| p.starts_with("core/")).collect();
        let mut sorted = core.clone();
        sorted.sort_unstable();
        assert_eq!(core, sorted);

        const AXES: [&str; 6] = [
            "language",
            "framework",
            "architecture",
            "deployment",
            "concerns",
            "sensitivity",
        ];
        let axis_of = |path: &str| AXES.iter().position(|axis| path.starts_with(axis));
        let ranks: Vec<_> = rest.iter().filter_map(|path| axis_of(path)).collect();
        let mut ascending = ranks.clone();
        ascending.sort_unstable();
        assert_eq!(ranks, ascending, "{rest:#?}");
    }

    #[test]
    fn selection_is_emitter_agnostic() {
        // `language/rust/automation.md` declares `emit: [claude]`. Selection
        // still carries it; applying the filter is each emitter's job.
        let selection = Selection::resolve(
            &Profile::parse(
                &format!("config_version: v1.0.0\nemit: [agents-md]\n{RUST_TEMPLATE}"),
                &tree(),
            )
            .unwrap(),
            &tree(),
        )
        .unwrap();

        let automation = selection
            .fragments()
            .iter()
            .find(|fragment| fragment.path() == "language/rust/automation.md")
            .expect("selected regardless of the emitters the profile wants");

        assert!(matches!(
            automation.meta(),
            Meta::Rules(meta) if meta.emit == Some(vec![EmitterName::Claude])
                && meta.scope == Scope::Always
        ));
    }

    #[test]
    fn the_selected_values_are_listed_in_axis_order() {
        let selection = resolve(&format!("{RUST_TEMPLATE}architecture: ddd\n"));

        assert_eq!(
            selection.values(),
            [
                "language/rust",
                "architecture/ddd",
                "deployment/tag-only",
                "concerns/template",
                "sensitivity/none",
            ]
        );
    }

    /// A tree with two values on different axes declaring the same name.
    fn colliding_tree() -> FragmentSet {
        FragmentSet::build(
            &[
                ("language/rust/values.yml", "unit: \"crate\"\n"),
                ("deployment/service/values.yml", "unit: \"service\"\n"),
            ],
            &[("deployment", &["service"]), ("language", &["rust"])],
        )
        .unwrap()
    }

    #[test]
    fn two_values_declaring_one_name_is_ambiguous_rather_than_silently_resolved() {
        let tree = colliding_tree();
        let error = variables(
            &["language/rust".to_owned(), "deployment/service".to_owned()],
            &tree,
        )
        .unwrap_err();

        assert!(matches!(
            error,
            SelectionError::DuplicateVariable { ref name, .. } if name == "unit"
        ));
        let rendered = error.to_string();
        assert!(rendered.contains("language/rust/values.yml"), "{rendered}");
        assert!(
            rendered.contains("deployment/service/values.yml"),
            "{rendered}"
        );
    }

    #[test]
    fn a_values_file_that_is_not_a_flat_map_is_rejected() {
        let tree = FragmentSet::build(
            &[("language/rust/values.yml", "unit:\n  nested: crate\n")],
            &[("language", &["rust"])],
        )
        .unwrap();

        let error = variables(&["language/rust".to_owned()], &tree).unwrap_err();

        assert!(matches!(error, SelectionError::Values { .. }));
        assert!(
            error.to_string().starts_with("language/rust/values.yml: "),
            "{error}"
        );
    }

    #[test]
    fn a_value_without_a_values_file_simply_declares_nothing() {
        let tree = FragmentSet::build(&[], &[("concerns", &["sync"])]).unwrap();

        assert!(
            variables(&["concerns/sync".to_owned()], &tree)
                .unwrap()
                .is_empty()
        );
    }
}
