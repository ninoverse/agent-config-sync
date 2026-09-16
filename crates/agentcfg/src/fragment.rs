//! One fragment: its frontmatter, split from its body.
//!
//! `agentcfg` never parses the markdown — bodies pass through untouched — so
//! everything the tool needs is in the frontmatter. Two shapes exist, told
//! apart by path: a file under a `tasks/` directory becomes a skill and carries
//! task frontmatter; everything else is a rules fragment.

use std::fmt;

use serde::Deserialize;

use crate::{EmitterName, error::FragmentError};

/// When an agent loads a fragment into context.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Scope {
    /// Loaded every session. Every line counts against the always-on budget.
    Always,
    /// Loaded when the agent reaches the activity named in `when:`. Only its
    /// index line counts against the budget.
    OnDemand,
    /// Loaded when the agent reads a file matching `paths:`. Nothing counts.
    Paths,
}

impl Scope {
    /// The value written in `scope:`.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Always => "always",
            Self::OnDemand => "on-demand",
            Self::Paths => "paths",
        }
    }
}

impl fmt::Display for Scope {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Who pulls the trigger on a task fragment's skill.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Invocation {
    /// The model decides, by testing the skill's `description`. That
    /// description loads every session and counts against the budget.
    #[default]
    Model,
    /// Only a typed `/name` fires it, so the description never enters context.
    User,
}

/// The frontmatter of a rules fragment.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RulesMeta {
    /// The heading the emitter writes above the body.
    pub title: String,
    /// How the fragment reaches an agent's context.
    pub scope: Scope,
    /// With [`Scope::OnDemand`], the activity that triggers reading it.
    /// Fragments sharing a `when` share one index line.
    pub when: Option<String>,
    /// With [`Scope::Paths`], the globs that load it, in Claude Code syntax.
    pub paths: Vec<String>,
    /// Lower sorts first. Ties break by axis, then by path.
    pub order: i32,
    /// The emitters that receive this fragment. `None` means every emitter the
    /// profile selects.
    pub emit: Option<Vec<EmitterName>>,
}

/// The frontmatter of a task fragment — one under a `tasks/` directory.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskMeta {
    /// The skill name, typed as `/name`.
    pub name: String,
    /// The heading, and the label on the pointer in the composed index.
    pub title: String,
    /// The activity this task belongs to, as the lead-in of its index line.
    pub when: String,
    /// The condition the model tests to decide whether to load the skill.
    pub description: String,
    /// Who fires the skill.
    pub invocation: Invocation,
    /// Autocomplete hint for the arguments.
    pub argument_hint: Option<String>,
    /// Named arguments, preferred over indexing `$0` / `$1`.
    pub arguments: Vec<String>,
    /// Tools pre-approved for the invoking turn.
    pub allowed_tools: Option<String>,
    /// The emitters that receive this fragment. `None` means every emitter the
    /// profile selects.
    pub emit: Option<Vec<EmitterName>>,
}

/// A fragment's frontmatter, in whichever of the two shapes it carries.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Meta {
    /// A rules fragment: prose an emitter places by `scope`.
    Rules(RulesMeta),
    /// A task fragment: a skill for Claude, a pointer for everyone else.
    Task(TaskMeta),
}

/// One markdown file of agent instructions.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Fragment {
    path: String,
    meta: Meta,
    body: String,
}

impl Fragment {
    /// Splits `text` into frontmatter and body, and validates the frontmatter
    /// against the shape `path` implies.
    ///
    /// Substitution has not run yet, so a value such as `name: "new-{{ unit }}"`
    /// is carried through verbatim.
    ///
    /// # Errors
    ///
    /// [`FragmentError`] when the frontmatter is missing, unclosed, not the
    /// expected YAML, or internally inconsistent — an `on-demand` fragment with
    /// no `when:`, say.
    ///
    /// ```
    /// use agentcfg::{Fragment, Meta, Scope};
    ///
    /// let text = "\
    /// ---
    /// title: Git flow
    /// scope: on-demand
    /// when: Any change that ends in a PR
    /// order: -1
    /// ---
    ///
    /// The branch → commit → PR loop for **every** change.
    /// ";
    ///
    /// let fragment = Fragment::parse("core/git-flow.md", text)?;
    /// assert_eq!(fragment.body(), "The branch → commit → PR loop for **every** change.");
    /// assert!(matches!(
    ///     fragment.meta(),
    ///     Meta::Rules(meta) if meta.scope == Scope::OnDemand && meta.order == -1
    /// ));
    /// # Ok::<(), agentcfg::FragmentError>(())
    /// ```
    pub fn parse(path: &str, text: &str) -> Result<Self, FragmentError> {
        let (frontmatter, body) = split_frontmatter(path, text)?;
        let meta = if is_task(path) {
            Meta::Task(task_meta(path, frontmatter)?)
        } else {
            Meta::Rules(rules_meta(path, frontmatter)?)
        };

        Ok(Self {
            path: path.to_owned(),
            meta,
            body: body.trim().to_owned(),
        })
    }

    /// The fragment's path, relative to `fragments/`.
    #[must_use]
    pub fn path(&self) -> &str {
        &self.path
    }

    /// The parsed frontmatter.
    #[must_use]
    pub fn meta(&self) -> &Meta {
        &self.meta
    }

    /// The markdown below the frontmatter, trimmed of surrounding blank lines
    /// and otherwise untouched.
    #[must_use]
    pub fn body(&self) -> &str {
        &self.body
    }
}

/// Whether `path` sits under a `tasks/` directory.
fn is_task(path: &str) -> bool {
    path.split('/').any(|segment| segment == "tasks")
}

/// Splits the leading `---`-delimited block off `text`.
fn split_frontmatter<'a>(path: &str, text: &'a str) -> Result<(&'a str, &'a str), FragmentError> {
    let rest = text
        .strip_prefix("---\n")
        .or_else(|| text.strip_prefix("---\r\n"))
        .ok_or_else(|| FragmentError::MissingFrontmatter {
            path: path.to_owned(),
        })?;

    let mut offset = 0;
    for line in rest.split_inclusive('\n') {
        if line.trim_end() == "---" {
            return Ok((&rest[..offset], &rest[offset + line.len()..]));
        }
        offset += line.len();
    }

    Err(FragmentError::UnclosedFrontmatter {
        path: path.to_owned(),
    })
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawRules {
    title: String,
    scope: Scope,
    #[serde(default)]
    when: Option<String>,
    #[serde(default)]
    paths: Vec<String>,
    #[serde(default)]
    order: i32,
    #[serde(default)]
    emit: Option<Vec<String>>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
struct RawTask {
    name: String,
    title: String,
    when: String,
    description: String,
    #[serde(default)]
    invocation: Invocation,
    #[serde(default)]
    argument_hint: Option<String>,
    #[serde(default)]
    arguments: Vec<String>,
    #[serde(default)]
    allowed_tools: Option<String>,
    #[serde(default)]
    emit: Option<Vec<String>>,
}

fn rules_meta(path: &str, frontmatter: &str) -> Result<RulesMeta, FragmentError> {
    let raw: RawRules = parse_yaml(path, frontmatter)?;

    if raw.scope == Scope::OnDemand && raw.when.is_none() {
        return Err(FragmentError::MissingWhen {
            path: path.to_owned(),
        });
    }
    if raw.scope == Scope::Paths && raw.paths.is_empty() {
        return Err(FragmentError::MissingPaths {
            path: path.to_owned(),
        });
    }
    if raw.scope != Scope::OnDemand && raw.when.is_some() {
        return Err(FragmentError::FieldNotAllowed {
            path: path.to_owned(),
            field: "when",
            scope: raw.scope,
        });
    }
    if raw.scope != Scope::Paths && !raw.paths.is_empty() {
        return Err(FragmentError::FieldNotAllowed {
            path: path.to_owned(),
            field: "paths",
            scope: raw.scope,
        });
    }

    Ok(RulesMeta {
        title: raw.title,
        scope: raw.scope,
        when: raw.when,
        paths: raw.paths,
        order: raw.order,
        emit: emitters(path, raw.emit)?,
    })
}

fn task_meta(path: &str, frontmatter: &str) -> Result<TaskMeta, FragmentError> {
    let raw: RawTask = parse_yaml(path, frontmatter)?;

    Ok(TaskMeta {
        name: raw.name,
        title: raw.title,
        when: raw.when,
        description: raw.description,
        invocation: raw.invocation,
        argument_hint: raw.argument_hint,
        arguments: raw.arguments,
        allowed_tools: raw.allowed_tools,
        emit: emitters(path, raw.emit)?,
    })
}

fn parse_yaml<T: serde::de::DeserializeOwned>(
    path: &str,
    frontmatter: &str,
) -> Result<T, FragmentError> {
    serde_yaml_ng::from_str(frontmatter).map_err(|source| FragmentError::Frontmatter {
        path: path.to_owned(),
        source,
    })
}

/// Resolves an `emit:` list, rejecting an empty one and any unknown name.
fn emitters(
    path: &str,
    raw: Option<Vec<String>>,
) -> Result<Option<Vec<EmitterName>>, FragmentError> {
    let Some(names) = raw else {
        return Ok(None);
    };
    if names.is_empty() {
        return Err(FragmentError::EmptyEmit {
            path: path.to_owned(),
        });
    }

    names
        .iter()
        .map(|name| {
            name.parse()
                .map_err(|source| FragmentError::UnknownEmitter {
                    path: path.to_owned(),
                    source,
                })
        })
        .collect::<Result<Vec<_>, _>>()
        .map(Some)
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    /// A rules fragment with `frontmatter` and a one-line body.
    fn rules(frontmatter: &str) -> String {
        format!("---\n{frontmatter}\n---\n\nBody.\n")
    }

    fn parse_rules_at(path: &str, frontmatter: &str) -> Result<Fragment, FragmentError> {
        Fragment::parse(path, &rules(frontmatter))
    }

    fn parse(frontmatter: &str) -> Result<Fragment, FragmentError> {
        parse_rules_at("core/example.md", frontmatter)
    }

    fn meta_of(fragment: &Fragment) -> &RulesMeta {
        match fragment.meta() {
            Meta::Rules(meta) => meta,
            Meta::Task(_) => unreachable!("parsed from a non-task path"),
        }
    }

    #[test]
    fn splits_frontmatter_from_body_and_trims_the_gap() {
        let fragment = parse("title: Behavioral guidelines\nscope: always").unwrap();

        assert_eq!(fragment.path(), "core/example.md");
        assert_eq!(fragment.body(), "Body.");
        assert_eq!(meta_of(&fragment).title, "Behavioral guidelines");
        assert_eq!(meta_of(&fragment).scope, Scope::Always);
        assert_eq!(meta_of(&fragment).order, 0);
        assert_eq!(meta_of(&fragment).emit, None);
    }

    #[test]
    fn accepts_crlf_frontmatter() {
        let fragment = Fragment::parse(
            "core/example.md",
            "---\r\ntitle: X\r\nscope: always\r\n---\r\nBody.",
        )
        .unwrap();

        assert_eq!(meta_of(&fragment).title, "X");
    }

    #[test]
    fn a_file_without_frontmatter_is_rejected() {
        let error = Fragment::parse("core/example.md", "# Just markdown\n").unwrap_err();

        assert!(matches!(error, FragmentError::MissingFrontmatter { .. }));
    }

    #[test]
    fn a_frontmatter_block_that_never_closes_is_rejected() {
        let error =
            Fragment::parse("core/example.md", "---\ntitle: X\nscope: always\n").unwrap_err();

        assert!(matches!(error, FragmentError::UnclosedFrontmatter { .. }));
    }

    #[test]
    fn a_misspelled_field_is_rejected_rather_than_ignored() {
        let error = parse("title: X\nscope: always\nordr: 2").unwrap_err();

        assert!(matches!(error, FragmentError::Frontmatter { .. }));
        assert!(error.to_string().contains("ordr"), "{error}");
    }

    #[test]
    fn on_demand_without_a_trigger_is_rejected() {
        let error = parse("title: X\nscope: on-demand").unwrap_err();

        assert!(matches!(error, FragmentError::MissingWhen { .. }));
    }

    #[test]
    fn path_scoped_without_globs_is_rejected() {
        let error = parse("title: X\nscope: paths").unwrap_err();

        assert!(matches!(error, FragmentError::MissingPaths { .. }));

        let empty = parse("title: X\nscope: paths\npaths: []").unwrap_err();

        assert!(matches!(empty, FragmentError::MissingPaths { .. }));
    }

    #[test]
    fn a_trigger_on_a_scope_that_ignores_it_is_rejected() {
        let error = parse("title: X\nscope: always\nwhen: Committing code").unwrap_err();

        assert!(matches!(
            error,
            FragmentError::FieldNotAllowed {
                field: "when",
                scope: Scope::Always,
                ..
            }
        ));
    }

    #[test]
    fn globs_on_a_scope_that_ignores_them_are_rejected() {
        let error =
            parse("title: X\nscope: on-demand\nwhen: Reviewing PRs\npaths: [\"**/domain/**\"]")
                .unwrap_err();

        assert!(matches!(
            error,
            FragmentError::FieldNotAllowed {
                field: "paths",
                scope: Scope::OnDemand,
                ..
            }
        ));
    }

    #[test]
    fn an_emit_filter_names_the_emitters_that_receive_the_fragment() {
        let fragment = parse("title: Automation\nscope: always\nemit: [claude]").unwrap();

        assert_eq!(meta_of(&fragment).emit, Some(vec![EmitterName::Claude]));
    }

    #[test]
    fn an_empty_emit_filter_is_rejected() {
        let error = parse("title: X\nscope: always\nemit: []").unwrap_err();

        assert!(matches!(error, FragmentError::EmptyEmit { .. }));
    }

    #[test]
    fn an_unknown_emitter_is_a_hard_error_not_an_empty_selection() {
        let error = parse("title: X\nscope: always\nemit: [agent-md]").unwrap_err();

        assert!(matches!(error, FragmentError::UnknownEmitter { .. }));
        assert!(error.to_string().contains("agents-md"), "{error}");
    }

    #[test]
    fn a_path_under_tasks_parses_as_a_skill() {
        let text = rules(concat!(
            "name: new-crate\n",
            "title: Adding a crate\n",
            "when: Adding or modifying a crate\n",
            "description: Add a crate following the 9-step workflow\n",
            "arguments: [name]",
        ));
        let fragment = Fragment::parse("language/rust/tasks/new-unit.md", &text).unwrap();

        match fragment.meta() {
            Meta::Task(meta) => {
                assert_eq!(meta.name, "new-crate");
                assert_eq!(meta.arguments, ["name"]);
                assert_eq!(meta.invocation, Invocation::Model);
                assert_eq!(meta.allowed_tools, None);
            }
            Meta::Rules(_) => unreachable!("parsed from a tasks/ path"),
        }
    }

    #[test]
    fn a_user_skill_declares_its_invocation() {
        let text = rules(concat!(
            "name: gates\n",
            "title: Merge gates\n",
            "when: Checking your work\n",
            "description: Run the merge gates\n",
            "invocation: user",
        ));
        let fragment = Fragment::parse("language/go/tasks/gates.md", &text).unwrap();

        assert!(matches!(
            fragment.meta(),
            Meta::Task(meta) if meta.invocation == Invocation::User
        ));
    }

    #[test]
    fn a_task_cannot_carry_a_scope() {
        let text = rules(concat!(
            "name: gates\n",
            "title: Merge gates\n",
            "when: Checking your work\n",
            "description: Run the merge gates\n",
            "scope: always",
        ));
        let error = Fragment::parse("language/go/tasks/gates.md", &text).unwrap_err();

        assert!(matches!(error, FragmentError::Frontmatter { .. }));
    }

    #[test]
    fn substitution_references_survive_parsing_untouched() {
        let text = rules(concat!(
            "name: \"new-{{ unit }}\"\n",
            "title: \"Adding a {{ unit }}\"\n",
            "when: \"Adding or modifying a {{ unit }}\"\n",
            "description: \"Add a {{ unit }} to the {{ unit_container }}\"",
        ));
        let fragment = Fragment::parse("language/rust/tasks/new-unit.md", &text).unwrap();

        assert!(matches!(
            fragment.meta(),
            Meta::Task(meta) if meta.name == "new-{{ unit }}"
        ));
    }

    #[test]
    fn every_error_names_the_fragment_it_came_from() {
        let error = parse_rules_at("concerns/sync/rules.md", "title: X").unwrap_err();

        assert_eq!(error.path(), "concerns/sync/rules.md");
        assert!(error.to_string().starts_with("concerns/sync/rules.md: "));
    }
}
