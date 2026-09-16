//! What can go wrong reading a fragment.
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
            | Self::UnknownEmitter { path, .. } => path,
        }
    }
}
