//! The always-on budget: what loads in every session, measured rather than
//! intended.
//!
//! The always-on set staying small is the assumption the whole composition
//! rests on — it is why the glossary went to a file and why concerns are
//! path-scoped. Stated in a plan and enforced by nobody, that decays: four
//! fragments added over a year degrade every session in every repository with
//! no one noticing. So it is a gate, and the fix when it trips is moving
//! content behind `scope: paths`, never deleting a rule.
//!
//! What counts is everything loaded unconditionally — not a formula over
//! fragments, but the lines that actually reach a session. Otherwise the
//! cheapest way to evade the gate would be to move rules onto a surface it does
//! not measure. What does not count is what never reaches context: HTML
//! comments, which Claude Code strips before loading, and the descriptions of
//! `invocation: user` skills, which enter context only when someone types the
//! name.

use crate::{Meta, OutputFile, Selection, emit};

/// The ceiling on always-on content, in lines.
///
/// Declared here and nowhere else: one number, shipped in the same release as
/// the fragments it governs.
pub const ALWAYS_ON_BUDGET: usize = 200;

/// The files whose generated content loads in every session.
const ALWAYS_ON_FILES: [&str; 2] = ["AGENTS.md", "CLAUDE.md"];

/// One contributor to the always-on set.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    /// The fragment it came from, or the name of a generated span that belongs
    /// to no single fragment.
    pub source: String,
    /// How many lines it costs every session.
    pub lines: usize,
}

/// What a profile's composition costs unconditionally.
#[derive(Debug, Clone)]
pub struct Budget {
    entries: Vec<Entry>,
    total: usize,
}

impl Budget {
    /// Measures the always-on cost of `files`.
    ///
    /// ```
    /// use agentcfg::{AgentsMd, Budget, EmitInput, Emitter, FragmentSet, Profile, Selection};
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
    /// let selection = Selection::resolve(&profile, &tree)?;
    /// let files = AgentsMd.emit(EmitInput {
    ///     selection: &selection,
    ///     profile: &profile,
    ///     tree: &tree,
    ///     version: "v1.0.0",
    /// })?;
    ///
    /// let budget = Budget::measure(&files, &selection);
    /// assert!(!budget.is_over());
    ///
    /// // Largest first, so the thing to move is the first line you read.
    /// let worst = &budget.entries()[0];
    /// assert!(worst.lines > 0);
    /// # Ok::<(), Box<dyn std::error::Error>>(())
    /// ```
    #[must_use]
    pub fn measure(files: &[OutputFile], selection: &Selection) -> Self {
        let mut entries: Vec<Entry> = Vec::new();

        let mut add = |source: &str, lines: usize| {
            if lines == 0 {
                return;
            }
            match entries.iter_mut().find(|entry| entry.source == source) {
                Some(entry) => entry.lines += lines,
                None => entries.push(Entry {
                    source: source.to_owned(),
                    lines,
                }),
            }
        };

        for file in files
            .iter()
            .filter(|file| ALWAYS_ON_FILES.contains(&file.path.as_str()))
        {
            let mut source = file.path.clone();
            for line in file.content.lines() {
                if let Some(named) = provenance(line) {
                    source = named.to_owned();
                } else if !line.trim().is_empty() {
                    add(&source, 1);
                }
            }
        }

        // A model-invocable skill's description is tested every session, so it
        // is spend the gate would otherwise not see.
        let writes_skills = files
            .iter()
            .any(|file| file.path.starts_with(".claude/skills/"));
        if writes_skills {
            for fragment in selection.fragments() {
                if let Meta::Task(meta) = fragment.meta() {
                    if meta.invocation == crate::Invocation::Model {
                        add(fragment.path(), 1);
                    }
                }
            }
        }

        entries.sort_by(|a, b| b.lines.cmp(&a.lines).then_with(|| a.source.cmp(&b.source)));
        let total = entries.iter().map(|entry| entry.lines).sum();

        Self { entries, total }
    }

    /// Lines loaded in every session.
    #[must_use]
    pub fn total(&self) -> usize {
        self.total
    }

    /// The ceiling this was measured against.
    #[must_use]
    pub fn limit(&self) -> usize {
        ALWAYS_ON_BUDGET
    }

    /// Whether the always-on set costs more than the ceiling allows.
    #[must_use]
    pub fn is_over(&self) -> bool {
        self.total > ALWAYS_ON_BUDGET
    }

    /// What it is spent on, largest first.
    #[must_use]
    pub fn entries(&self) -> &[Entry] {
        &self.entries
    }
}

/// The source named by a provenance comment, if `line` is one.
///
/// Claude Code strips block-level HTML comments before loading a file, so these
/// lines cost the reader that matters nothing — and counting them would spend
/// the budget on the reader that does not need them.
fn provenance(line: &str) -> Option<&str> {
    let inner = line.trim().strip_prefix("<!-- ")?.strip_suffix(" -->")?;
    let source = inner.split(" · ").next()?;

    match source {
        emit::INDEX => Some("the on-demand index"),
        emit::IMPORT => Some("the CLAUDE.md import"),
        _ => Some(source),
    }
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;
    use crate::{FragmentSet, Ownership, Profile};

    fn selection(axes: &str) -> Selection {
        let tree = FragmentSet::embedded().unwrap();
        let profile = Profile::parse(
            &format!("config_version: v1.0.0\nemit: [agents-md, claude]\n{axes}"),
            &tree,
        )
        .unwrap();
        Selection::resolve(&profile, &tree).unwrap()
    }

    fn agents_md(content: &str) -> OutputFile {
        OutputFile {
            path: "AGENTS.md".to_owned(),
            content: content.to_owned(),
            ownership: Ownership::Region,
        }
    }

    fn measure(content: &str) -> Budget {
        Budget::measure(
            &[agents_md(content)],
            &selection("language: rust\ndeployment: tag-only\n"),
        )
    }

    #[test]
    fn provenance_and_blank_lines_cost_nothing() {
        // Claude Code strips block-level HTML comments before loading, so
        // counting them would spend the budget on the reader that does not
        // need them — and push authors toward the wrong choice to pass a gate.
        let budget =
            measure("<!-- core/behavior.md · v1.0.0 -->\n# Behaviour\n\nOne rule.\n\n\nAnother.\n");

        assert_eq!(budget.total(), 3);
        assert_eq!(
            budget.entries(),
            [Entry {
                source: "core/behavior.md".to_owned(),
                lines: 3
            }]
        );
    }

    #[test]
    fn lines_are_attributed_to_the_fragment_that_produced_them() {
        let budget = measure(concat!(
            "<!-- core/behavior.md · v1 -->\na\nb\nc\n",
            "<!-- language/rust/tooling.md · v1 -->\nd\n",
        ));

        // Largest first, so the thing to move is the first line read.
        assert_eq!(
            budget.entries(),
            [
                Entry {
                    source: "core/behavior.md".to_owned(),
                    lines: 3
                },
                Entry {
                    source: "language/rust/tooling.md".to_owned(),
                    lines: 1
                },
            ]
        );
    }

    #[test]
    fn the_generated_spans_that_belong_to_no_fragment_are_named() {
        let budget = measure(concat!(
            "<!-- core/behavior.md · v1 -->\na\n",
            "<!-- agentcfg:index · v1 -->\n- **Committing code:** read x\n",
        ));

        assert!(
            budget
                .entries()
                .iter()
                .any(|entry| entry.source == "the on-demand index"),
            "{:?}",
            budget.entries()
        );
    }

    #[test]
    fn content_outside_the_always_on_files_is_not_counted() {
        // A path-scoped rule costs only the sessions that reach it.
        let budget = Budget::measure(
            &[
                agents_md("<!-- core/behavior.md · v1 -->\none\n"),
                OutputFile {
                    path: ".agents/data-access-rules.md".to_owned(),
                    content: "<!-- concerns/data-access/rules.md · v1 -->\n".to_owned()
                        + &"line\n".repeat(500),
                    ownership: Ownership::Region,
                },
            ],
            &selection("language: rust\ndeployment: tag-only\n"),
        );

        assert_eq!(budget.total(), 1);
    }

    #[test]
    fn a_model_invocable_skill_description_is_spend_the_gate_can_see() {
        let selection = selection("language: rust\ndeployment: tag-only\n");
        let skills: Vec<OutputFile> = selection
            .fragments()
            .iter()
            .filter(|fragment| matches!(fragment.meta(), Meta::Task(_)))
            .map(|fragment| OutputFile {
                path: format!(".claude/skills/{}/SKILL.md", fragment.path()),
                content: String::new(),
                ownership: Ownership::Whole,
            })
            .collect();

        let without = Budget::measure(&[agents_md("x\n")], &selection).total();

        let mut with = vec![agents_md("x\n")];
        with.extend(skills.clone());
        let with = Budget::measure(&with, &selection).total();

        // Both tasks in the rust value are model-invocable, so each costs the
        // one line of description the model tests every session.
        assert_eq!(with - without, skills.len());
        assert_eq!(skills.len(), 2);
    }

    #[test]
    fn a_profile_that_emits_no_skills_pays_for_no_descriptions() {
        let selection = selection("language: rust\ndeployment: tag-only\n");

        assert_eq!(Budget::measure(&[agents_md("x\n")], &selection).total(), 1);
    }

    #[test]
    fn the_gate_trips_past_the_ceiling_and_says_what_to_move() {
        let big = format!(
            "<!-- core/behavior.md · v1 -->\n{}<!-- language/rust/tooling.md · v1 -->\n{}",
            "rule\n".repeat(ALWAYS_ON_BUDGET),
            "rule\n".repeat(5),
        );
        let budget = measure(&big);

        assert!(budget.is_over());
        assert_eq!(budget.total(), ALWAYS_ON_BUDGET + 5);
        assert_eq!(budget.limit(), ALWAYS_ON_BUDGET);
        assert_eq!(budget.entries()[0].source, "core/behavior.md");
    }

    #[test]
    fn exactly_the_ceiling_is_within_budget() {
        let budget = measure(&format!(
            "<!-- core/behavior.md · v1 -->\n{}",
            "rule\n".repeat(ALWAYS_ON_BUDGET)
        ));

        assert_eq!(budget.total(), ALWAYS_ON_BUDGET);
        assert!(!budget.is_over());
    }

    #[test]
    fn the_real_profiles_sit_well_inside_the_ceiling() {
        // Measured against what those profiles actually compose, not a stand-in.
        // If this ever fails, the fix is moving content behind `scope: paths`,
        // never deleting a rule.
        for axes in [
            "language: rust\ndeployment: tag-only\nconcerns: [template]\n",
            "language: go\ndeployment: service\narchitecture: ddd\nconcerns: [template]\n",
            "language: rust\ndeployment: tag-only\nconcerns: [template, data-access, sync]\n",
        ] {
            let sandbox = tempfile::tempdir().unwrap();
            std::fs::write(
                sandbox.path().join(".agentprofile.yml"),
                format!("config_version: v1.0.0\nemit: [agents-md, claude]\n{axes}"),
            )
            .unwrap();

            let tree = FragmentSet::embedded().unwrap();
            let composed =
                crate::Composition::of(&crate::Repo::at(sandbox.path()), &tree, "v1.0.0").unwrap();

            let budget = Budget::measure(&composed.files, &composed.selection);

            assert!(
                !budget.is_over(),
                "{axes} costs {} of {} lines:\n{:#?}",
                budget.total(),
                budget.limit(),
                budget.entries()
            );
            // Headroom is the point: a profile at 199 would be one fragment
            // away from tripping, which is not a margin worth shipping.
            assert!(
                budget.total() < ALWAYS_ON_BUDGET * 3 / 4,
                "{axes} costs {} of {}",
                budget.total(),
                budget.limit()
            );
        }
    }
}
