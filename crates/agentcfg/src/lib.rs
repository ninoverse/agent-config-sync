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
//! This crate models the inputs so far: the fragment tree compiled into the
//! binary, and the frontmatter each fragment carries. Selection, substitution
//! and emission follow.
//!
//! ```
//! use agentcfg::{FragmentSet, Meta, Scope};
//!
//! let set = FragmentSet::embedded()?;
//!
//! // Fragments loaded in every session — the set the always-on budget governs.
//! let always_on = set.fragments().iter().filter(|fragment| {
//!     matches!(fragment.meta(), Meta::Rules(meta) if meta.scope == Scope::Always)
//! });
//! assert!(always_on.count() > 0);
//!
//! // Values come from the directory listing, never a hand-written enum.
//! assert_eq!(set.values("language"), ["go", "rust"]);
//! # Ok::<(), agentcfg::FragmentError>(())
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
mod set;

pub use emit::{EmitterName, UnknownEmitter};
pub use error::FragmentError;
pub use fragment::{Fragment, Invocation, Meta, RulesMeta, Scope, TaskMeta};
pub use set::FragmentSet;
