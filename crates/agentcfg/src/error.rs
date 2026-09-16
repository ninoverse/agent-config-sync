//! What can go wrong reading the inputs.
//!
//! The tool never prompts, so its failures carry the whole user experience.
//! Every variant names the file it came from and, where there is one, the edit
//! that fixes it.

use crate::{Scope, emit::UnknownEmitter};

/// A fragment that could not be read.
#[derive(Debug, thiserror::Error)]
pub enum FragmentError {
    /// The file does not open with a `---` line.
    #[error("{path}: no frontmatter — a fragment opens with a `---` line")]
    MissingFrontmatter {
        /// The fragment's path, relative to `fragments/`.
        path: String,
    },

    /// The opening `---` has no matching close.
    #[error("{path}: frontmatter is never closed — expected a second `---` line")]
    UnclosedFrontmatter {
        /// The fragment's path, relative to `fragments/`.
        path: String,
    },

    /// The frontmatter is not the YAML this kind of fragment expects.
    #[error("{path}: {source}")]
    Frontmatter {
        /// The fragment's path, relative to `fragments/`.
        path: String,
        /// What the YAML parser objected to.
        source: serde_yaml_ng::Error,
    },

    /// `scope: on-demand` carries no `when:`, so nothing would index it.
    #[error("{path}: `scope: on-demand` requires `when:` — the activity that triggers reading it")]
    MissingWhen {
        /// The fragment's path, relative to `fragments/`.
        path: String,
    },

    /// `scope: paths` carries no globs, so it would never load.
    #[error("{path}: `scope: paths` requires a non-empty `paths:` list")]
    MissingPaths {
        /// The fragment's path, relative to `fragments/`.
        path: String,
    },

    /// A field that only means something under a different scope.
    #[error(
        "{path}: `{field}:` means nothing under `scope: {scope}` — remove it or change the scope"
    )]
    FieldNotAllowed {
        /// The fragment's path, relative to `fragments/`.
        path: String,
        /// The field that does not belong.
        field: &'static str,
        /// The scope the fragment actually declares.
        scope: Scope,
    },

    /// `emit: []` — a fragment no emitter would ever receive.
    #[error(
        "{path}: `emit:` is empty, so no emitter would receive this fragment — remove the field to reach every emitter"
    )]
    EmptyEmit {
        /// The fragment's path, relative to `fragments/`.
        path: String,
    },

    /// An `emit:` entry naming an emitter this version does not have.
    #[error("{path}: {source}")]
    UnknownEmitter {
        /// The fragment's path, relative to `fragments/`.
        path: String,
        /// The name that did not match.
        source: UnknownEmitter,
    },

    /// A `--fragments` directory that could not be read.
    #[error("{path}: {source}")]
    Io {
        /// The path that could not be read.
        path: String,
        /// What the filesystem reported.
        source: std::io::Error,
    },
}

impl FragmentError {
    /// The fragment this error came from, relative to `fragments/`.
    ///
    /// ```
    /// use agentcfg::Fragment;
    ///
    /// let error = Fragment::parse("core/behavior.md", "no frontmatter").unwrap_err();
    /// assert_eq!(error.path(), "core/behavior.md");
    /// ```
    #[must_use]
    pub fn path(&self) -> &str {
        match self {
            Self::MissingFrontmatter { path }
            | Self::UnclosedFrontmatter { path }
            | Self::Frontmatter { path, .. }
            | Self::MissingWhen { path }
            | Self::MissingPaths { path }
            | Self::FieldNotAllowed { path, .. }
            | Self::EmptyEmit { path }
            | Self::UnknownEmitter { path, .. }
            | Self::Io { path, .. } => path,
        }
    }
}

/// A profile that could not be read, or that names something this release does
/// not ship.
#[derive(Debug, thiserror::Error)]
pub enum ProfileError {
    /// The file is not the YAML the schema expects — a missing required key, an
    /// unknown one, or a value of the wrong shape.
    #[error("{PROFILE}: {source}")]
    Syntax {
        /// What the YAML parser objected to.
        source: serde_yaml_ng::Error,
    },

    /// `config_version` is not a release tag, so nothing could resolve it.
    #[error(
        "{PROFILE}: `config_version: {value}` is not a release tag — expected `v<major>.<minor>.<patch>`, such as `v1.0.0`"
    )]
    ConfigVersion {
        /// The value that was written.
        value: String,
    },

    /// An axis names a value this release does not ship.
    ///
    /// Central first: a value becomes legal when its directory ships, not when
    /// a repository asks for it.
    #[error("{PROFILE}: unknown {axis} `{value}` — {}", shipped(.available))]
    UnknownValue {
        /// The axis the value was written under.
        axis: &'static str,
        /// The value that was written.
        value: String,
        /// The values this release does ship for that axis.
        available: Vec<String>,
    },

    /// One concern listed twice — a typo rather than an intention, since a
    /// concern selected twice composes exactly as it does once.
    #[error("{PROFILE}: `{value}` is listed twice under `concerns:`")]
    DuplicateConcern {
        /// The repeated value.
        value: String,
    },

    /// `claude` without `agents-md`.
    ///
    /// `CLAUDE.md` is an `@AGENTS.md` import and the AGENTS.md index is what
    /// points Claude at the rules it reads on demand, so the claude output has
    /// nothing to import and nothing to follow on its own.
    #[error(
        "{PROFILE}: `emit:` names claude without agents-md — CLAUDE.md imports AGENTS.md, so claude cannot be emitted alone"
    )]
    ClaudeNeedsAgentsMd,

    /// An `emit:` entry naming an emitter this release does not have.
    #[error("{PROFILE}: {source}")]
    UnknownEmitter {
        /// The name that did not match.
        source: UnknownEmitter,
    },
}

/// The profile's fixed filename — the one file in a consumer repo a human writes.
const PROFILE: &str = ".agentprofile.yml";

/// Renders the values an axis ships, for the tail of an `UnknownValue` message.
fn shipped(available: &[String]) -> String {
    if available.is_empty() {
        "this release ships no values for that axis yet".to_owned()
    } else {
        format!("this release ships: {}", available.join(", "))
    }
}

/// A selection that could not be composed from the profile and the fragments.
#[derive(Debug, thiserror::Error)]
pub enum SelectionError {
    /// A `values.yml` is not the flat map of names to strings it must be.
    #[error("{path}: {source}")]
    Values {
        /// The `values.yml` path, relative to `fragments/`.
        path: String,
        /// What the YAML parser objected to.
        source: serde_yaml_ng::Error,
    },

    /// Two selected values declare the same name, so the reference is
    /// ambiguous. Which value wins would be an invisible rule; failing is not.
    #[error("`{name}` is declared by both {first} and {second} — a name belongs to one value")]
    DuplicateVariable {
        /// The name declared twice.
        name: String,
        /// The first `values.yml` to declare it.
        first: String,
        /// The second.
        second: String,
    },

    /// A fragment references a name the selected values do not declare.
    ///
    /// Always an error, never an empty string: a rule that renders as "run"
    /// with nothing after it is worse than no rule at all. It is also what
    /// catches a new language value that forgot to declare something.
    #[error("{path}: `{{{{ {name} }}}}` is not declared by any selected value — {}", declared(.available))]
    UnresolvedVariable {
        /// The fragment holding the reference.
        path: String,
        /// The name that did not resolve.
        name: String,
        /// Every name the selected values do declare.
        available: Vec<String>,
    },

    /// A `{{` with no closing `}}`, which would otherwise emit as literal text.
    #[error("{path}: a `{{{{` is never closed — write `\\{{{{` for a literal one")]
    UnclosedSubstitution {
        /// The fragment holding the reference.
        path: String,
    },
}

/// Renders the names in scope, for the tail of an `UnresolvedVariable` message.
fn declared(available: &[String]) -> String {
    if available.is_empty() {
        "the selected values declare nothing".to_owned()
    } else {
        format!("in scope: {}", available.join(", "))
    }
}

/// A selection an emitter could not render.
#[derive(Debug, thiserror::Error)]
pub enum EmitError {
    /// Two fragments would render to the same file, so one would silently
    /// overwrite the other.
    #[error("the {emitter} emitter would write `{path}` twice — two fragments render to one file")]
    DuplicatePath {
        /// The emitter that produced the clash.
        emitter: crate::EmitterName,
        /// The path claimed twice.
        path: String,
    },

    /// A `settings.partial.json` in the tree is not valid JSON.
    #[error("{path}: {source}")]
    Settings {
        /// The partial's path, relative to `fragments/`.
        path: String,
        /// What the JSON parser objected to.
        source: serde_json::Error,
    },
}

/// A repository that could not be read or written.
#[derive(Debug, thiserror::Error)]
pub enum RepoError {
    /// The filesystem refused.
    #[error("{path}: {source}")]
    Io {
        /// The path, relative to the repository root.
        path: String,
        /// What the filesystem reported.
        source: std::io::Error,
    },

    /// A generated region the tool cannot safely write over.
    ///
    /// `sync` refuses and leaves the file untouched rather than guessing where
    /// generated content was meant to end.
    #[error(
        "{path}: {reason} — fix the `agentcfg:start` / `agentcfg:end` markers by hand, then run `agentcfg sync`"
    )]
    DamagedRegion {
        /// The file holding the damaged region.
        path: String,
        /// Which way it is damaged.
        reason: &'static str,
    },

    /// The manifest is not the JSON it must be.
    #[error("{MANIFEST}: {source} — delete it and run `agentcfg sync` to rebuild it")]
    Manifest {
        /// What the JSON parser objected to.
        source: serde_json::Error,
    },

    /// A file this profile no longer generates, which someone has written in.
    ///
    /// Deleting it would take their prose with it, and `sync` never prompts
    /// before losing something — it stops.
    #[error(
        "{path} is no longer generated by this profile, but has content outside its markers — move that content elsewhere, then run `agentcfg sync`"
    )]
    OrphanHasLocalContent {
        /// The orphaned file.
        path: String,
    },
}

/// Where the list of generated paths lives.
pub(crate) const MANIFEST: &str = ".agentcfg-manifest.json";

/// Anything that can go wrong composing a repository's configuration.
///
/// Each variant renders as the underlying message and nothing more: the tool
/// never prompts, so its failures carry the whole user experience, and a prefix
/// naming the layer that failed would only get between the reader and the fix.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// A fragment could not be read.
    #[error(transparent)]
    Fragment(#[from] FragmentError),

    /// The profile could not be read, or names something unreleased.
    #[error(transparent)]
    Profile(#[from] ProfileError),

    /// The selection could not be composed.
    #[error(transparent)]
    Selection(#[from] SelectionError),

    /// An emitter could not render the selection.
    #[error(transparent)]
    Emit(#[from] EmitError),

    /// The repository could not be read or written.
    #[error(transparent)]
    Repo(#[from] RepoError),
}
