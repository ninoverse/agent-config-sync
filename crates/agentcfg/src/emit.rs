//! Emission: which emitters exist, what they produce, and the contract they
//! implement.

mod agents_md;
mod claude;

use std::{collections::BTreeSet, fmt, str::FromStr};

use crate::{Fragment, FragmentSet, Meta, Profile, Selection, error::EmitError};

pub use agents_md::AgentsMd;
pub use claude::Claude;

/// One of the emitters `agentcfg` renders fragments for.
///
/// Fixed in code rather than discovered from the fragment tree, because an
/// emitter is a translation into one agent's file layout — a new agent is a new
/// emitter, never a new directory. Cursor is deliberately absent: it reads
/// AGENTS.md natively.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum EmitterName {
    /// `AGENTS.md` and the agent-neutral rule files beside it.
    AgentsMd,
    /// `CLAUDE.md`, `.claude/rules/`, `.claude/skills/` and `.claude/settings.json`.
    Claude,
}

impl EmitterName {
    /// Every emitter this version knows about.
    pub const ALL: [Self; 2] = [Self::AgentsMd, Self::Claude];

    /// The name written in an `emit:` list.
    ///
    /// ```
    /// use agentcfg::EmitterName;
    ///
    /// assert_eq!(EmitterName::AgentsMd.as_str(), "agents-md");
    /// ```
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::AgentsMd => "agents-md",
            Self::Claude => "claude",
        }
    }

    /// Every name, comma-separated — for listing the legal set in an error.
    fn all_names() -> String {
        Self::ALL
            .iter()
            .map(|emitter| emitter.as_str())
            .collect::<Vec<_>>()
            .join(", ")
    }
}

impl fmt::Display for EmitterName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// A name in an `emit:` list that is not an emitter this version knows.
///
/// A hard error rather than an empty selection: `emit: [agent-md]` must fail
/// loudly, never quietly render nothing.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error(
    "unknown emitter `{name}` — expected one of: {}",
    EmitterName::all_names()
)]
pub struct UnknownEmitter {
    /// The name that did not match.
    pub name: String,
}

impl FromStr for EmitterName {
    type Err = UnknownEmitter;

    /// ```
    /// use agentcfg::EmitterName;
    ///
    /// assert_eq!("claude".parse(), Ok(EmitterName::Claude));
    /// assert!("agent-md".parse::<EmitterName>().is_err());
    /// ```
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Self::ALL
            .into_iter()
            .find(|emitter| emitter.as_str() == s)
            .ok_or_else(|| UnknownEmitter { name: s.to_owned() })
    }
}

/// How a generated file relates to what is already at its path.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Ownership {
    /// The content sits inside a marker region, and anything outside it
    /// survives regeneration. The escape hatch for genuinely local content.
    Region,
    /// The file is owned outright and verified byte-for-byte. Two kinds take
    /// this route: JSON, which has no comment syntax to carry a marker and
    /// where a merging emitter could never tell a key it wrote last month from
    /// one a person added; and markdown that leads with generated frontmatter,
    /// which a marker comment cannot sit above without breaking it.
    Whole,
}

/// One file an emitter produces, before it reaches a repository.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OutputFile {
    /// Where it goes, relative to the repository root.
    pub path: String,
    /// What the emitter generated. For [`Ownership::Region`] this is the
    /// content of the marker region, not the whole file: the markers belong to
    /// whatever splices it in.
    pub content: String,
    /// Whether the file is spliced or replaced.
    pub ownership: Ownership,
}

/// Everything emission reads.
#[derive(Debug, Clone, Copy)]
pub struct EmitInput<'a> {
    /// The fragments to write, substituted and ordered.
    pub selection: &'a Selection,
    /// The profile that produced them — for `settings_extra:`.
    pub profile: &'a Profile,
    /// The whole tree — for the files beside the fragments, such as a language
    /// value's `settings.partial.json`.
    pub tree: &'a FragmentSet,
    /// The `config_version` stamped into every provenance comment. The binary's
    /// own version, since a release pins content and code together.
    pub version: &'a str,
}

/// Translates a selection into one agent's file layout.
///
/// Same bodies, different frontmatter and paths — a new agent is a new
/// emitter, never a content migration.
pub trait Emitter {
    /// Which emitter this is, for the `emit:` filter.
    fn name(&self) -> EmitterName;

    /// The files this emitter would write.
    ///
    /// Implement this; call [`Emitter::emit`], which checks the result.
    ///
    /// # Errors
    ///
    /// [`EmitError`] if the emitter cannot render the selection.
    fn files(&self, input: EmitInput<'_>) -> Result<Vec<OutputFile>, EmitError>;

    /// The files this emitter writes, with no two sharing a path.
    ///
    /// # Errors
    ///
    /// [`EmitError::DuplicatePath`] if two fragments would land on one file.
    /// A naming scheme is a weak guarantee; this is the one that holds.
    fn emit(&self, input: EmitInput<'_>) -> Result<Vec<OutputFile>, EmitError> {
        let files = self.files(input)?;
        let mut seen: BTreeSet<&str> = BTreeSet::new();
        for file in &files {
            if !seen.insert(&file.path) {
                return Err(EmitError::DuplicatePath {
                    emitter: self.name(),
                    path: file.path.clone(),
                });
            }
        }
        Ok(files)
    }
}

/// Whether this emitter receives `fragment`.
///
/// A fragment with no `emit:` reaches every emitter the profile selected.
pub(crate) fn receives(emitter: EmitterName, fragment: &Fragment) -> bool {
    let filter = match fragment.meta() {
        Meta::Rules(meta) => meta.emit.as_deref(),
        Meta::Task(meta) => meta.emit.as_deref(),
    };
    filter.is_none_or(|emitters| emitters.contains(&emitter))
}

/// The filename a fragment's body gets, without extension.
///
/// Keyed on the source path rather than the file stem, because three fragments
/// are named `rules.md` and `concerns` is the axis a repo may pick several of:
/// `data-access/rules.md` and `sync/rules.md` would otherwise collide on one
/// file. A task uses its skill name instead, so the pointer an agent follows
/// and the skill Claude runs carry the same word.
pub(crate) fn file_stem(fragment: &Fragment) -> String {
    if let Meta::Task(meta) = fragment.meta() {
        return meta.name.clone();
    }

    let path = fragment.path();
    let without_extension = path.strip_suffix(".md").unwrap_or(path);
    let segments: Vec<&str> = without_extension.split('/').collect();

    match segments.as_slice() {
        ["core", stem] => (*stem).to_owned(),
        [_axis, value, rest @ ..] if !rest.is_empty() => {
            format!("{value}-{}", rest.join("-"))
        }
        _ => segments.join("-"),
    }
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    #[test]
    fn every_emitter_round_trips_through_its_name() {
        for emitter in EmitterName::ALL {
            assert_eq!(emitter.as_str().parse(), Ok(emitter));
        }
    }

    #[test]
    fn unknown_name_error_lists_the_legal_set() {
        let error = "agent-md".parse::<EmitterName>().unwrap_err();
        let rendered = error.to_string();
        for emitter in EmitterName::ALL {
            assert!(rendered.contains(emitter.as_str()), "{rendered}");
        }
    }

    use crate::{FragmentSet, Profile, Selection, error::EmitError};

    fn fragment(path: &str, frontmatter: &str) -> Fragment {
        Fragment::parse(path, &format!("---\n{frontmatter}\n---\n\nBody.\n")).unwrap()
    }

    fn rules(path: &str) -> Fragment {
        fragment(path, "title: X\nscope: always")
    }

    #[test]
    fn a_core_fragment_keeps_its_bare_stem() {
        assert_eq!(file_stem(&rules("core/git-flow.md")), "git-flow");
    }

    #[test]
    fn a_fragment_inside_a_value_is_named_for_that_value() {
        // Three fragments in the tree are called `rules.md`, and `concerns` is
        // the axis a repo may pick several values of.
        assert_eq!(
            file_stem(&rules("concerns/data-access/rules.md")),
            "data-access-rules"
        );
        assert_eq!(file_stem(&rules("concerns/sync/rules.md")), "sync-rules");
        assert_eq!(
            file_stem(&rules("architecture/ddd/domain-model.md")),
            "ddd-domain-model"
        );
    }

    #[test]
    fn a_task_is_named_for_its_skill() {
        let task = fragment(
            "language/rust/tasks/new-unit.md",
            "name: new-crate\ntitle: Adding a crate\nwhen: Adding a crate\ndescription: Adds one",
        );

        // Not `rust-tasks-new-unit`: the pointer an agent follows and the skill
        // Claude runs should carry the same word.
        assert_eq!(file_stem(&task), "new-crate");
    }

    #[test]
    fn a_fragment_without_an_emit_filter_reaches_every_emitter() {
        let open = rules("core/behavior.md");

        for emitter in EmitterName::ALL {
            assert!(receives(emitter, &open));
        }
    }

    #[test]
    fn an_emit_filter_admits_only_the_emitters_it_names() {
        let claude_only = fragment(
            "language/rust/automation.md",
            "title: X\nscope: always\nemit: [claude]",
        );

        assert!(receives(EmitterName::Claude, &claude_only));
        assert!(!receives(EmitterName::AgentsMd, &claude_only));
    }

    /// An emitter that renders two fragments onto one path.
    struct Colliding;

    impl Emitter for Colliding {
        fn name(&self) -> EmitterName {
            EmitterName::AgentsMd
        }

        fn files(&self, _input: EmitInput<'_>) -> Result<Vec<OutputFile>, EmitError> {
            Ok(vec![
                OutputFile {
                    path: ".agents/rules.md".to_owned(),
                    content: "one".to_owned(),
                    ownership: Ownership::Region,
                },
                OutputFile {
                    path: ".agents/rules.md".to_owned(),
                    content: "two".to_owned(),
                    ownership: Ownership::Region,
                },
            ])
        }
    }

    #[test]
    fn two_fragments_landing_on_one_file_is_an_error_not_an_overwrite() {
        // The naming rule makes this unreachable for the two rule directories.
        // This is the guarantee that does not depend on the rule being clever.
        let tree = FragmentSet::embedded().unwrap();
        let profile = Profile::parse(
            "config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\nemit: [agents-md]\n",
            &tree,
        )
        .unwrap();
        let selection = Selection::resolve(&profile, &tree).unwrap();

        let error = Colliding
            .emit(EmitInput {
                selection: &selection,
                profile: &profile,
                tree: &tree,
                version: "v1.0.0",
            })
            .unwrap_err();

        assert!(matches!(error, EmitError::DuplicatePath { .. }));
        assert!(error.to_string().contains(".agents/rules.md"), "{error}");
    }
}
