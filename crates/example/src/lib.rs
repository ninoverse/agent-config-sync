//! Placeholder crate that keeps the workspace buildable.
//!
//! A Cargo workspace whose `members` glob matches nothing is a hard error, so
//! `cargo check`, `cargo clippy`, `cargo fmt` and `cargo test` all fail on a
//! workspace with no crates. This crate exists so the merge gates in
//! `.claude/testing-requirements.md` pass on a fresh clone.
//!
//! It also demonstrates the conventions every crate here follows: crate-level
//! `//!` docs, a `///` doc comment with a runnable example on each public item,
//! and inline unit tests.
//!
//! **Add your first real crate before deleting this one** — removing it while
//! it is the only member puts the workspace back in the broken state.

/// Builds a greeting for `name`.
///
/// # Examples
///
/// ```
/// assert_eq!(example::greet("world"), "Hello, world!");
/// ```
#[must_use]
pub fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    #[test]
    fn greets_by_name() {
        assert_eq!(greet("rust"), "Hello, rust!");
    }

    #[test]
    fn handles_empty_name() {
        assert_eq!(greet(""), "Hello, !");
    }
}
