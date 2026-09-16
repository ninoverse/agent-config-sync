//! Composes per-repo agent configuration from single-axis fragments.
//!
//! A **fragment** is one markdown file of agent instructions belonging to
//! exactly one axis value, or to `core/`. An **axis** is a dimension a
//! repository varies on — language, framework, architecture, deployment,
//! concerns, sensitivity — and a **value** is one option on it. A repository
//! picks values in its profile; the tool collects the fragments inside them,
//! substitutes the vocabulary those values declare, and hands the result to one
//! emitter per agent.
//!
//! This crate reads the fragment tree compiled into the binary and the profile
//! that picks between its values, composes the two into the files each agent
//! reads, and works out what writing them would change in a repository. The
//! commands that drive it follow.
//!
//! ```
//! use agentcfg::{FragmentSet, Meta, Profile, Scope};
//!
//! let tree = FragmentSet::embedded()?;
//!
//! // Fragments loaded in every session — the set the always-on budget governs.
//! let always_on = tree.fragments().iter().filter(|fragment| {
//!     matches!(fragment.meta(), Meta::Rules(meta) if meta.scope == Scope::Always)
//! });
//! assert!(always_on.count() > 0);
//!
//! // A profile names one value per axis, validated against that same listing —
//! // never against a hand-written enum.
//! let profile = Profile::parse(
//!     "\
//! config_version: v1.0.0
//! language: rust
//! deployment: tag-only
//! concerns: [template]
//! emit: [agents-md, claude]
//! ",
//!     &tree,
//! )?;
//! assert!(tree.values("language").contains(&profile.language));
//! # Ok::<(), Box<dyn std::error::Error>>(())
//! ```

/// The fragment tree, compiled in by `build.rs`.
///
/// Defines `FILES` — every file under `fragments/`, keyed by relative path —
/// and `AXES`, the axis and value directories inside it.
mod embedded {
    include!(concat!(env!("OUT_DIR"), "/embedded.rs"));
}

mod emit;
mod error;
mod fragment;
mod marker;
mod profile;
mod repo;
mod selection;
mod set;
mod substitute;

pub use emit::{
    AgentsMd, Claude, EmitInput, Emitter, EmitterName, OutputFile, Ownership, UnknownEmitter,
};
pub use error::{EmitError, FragmentError, ProfileError, RepoError, SelectionError};
pub use fragment::{Fragment, Invocation, Meta, RulesMeta, Scope, TaskMeta};
pub use profile::Profile;
pub use repo::{Change, ChangeKind, Plan, Repo};
pub use selection::Selection;
pub use set::FragmentSet;
