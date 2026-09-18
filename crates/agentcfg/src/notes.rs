//! Release notes — what the fragment tree gained, lost and changed.
//!
//! Renovate embeds a release's notes in the body of every bump pull request it
//! opens, so this text is written once per release and then read in every
//! repository that pins it. What a maintainer wants from it is one question
//! answered: *does this affect me.*
//!
//! The heading says so outright, because the section does not sit alone: the
//! release workflow appends a conventional-commit changelog beneath it. Every
//! release here is one commit, by git-flow, so whenever that commit touches a
//! fragment both sections describe it and a heading of "Fragments" reads as the
//! same line twice. They are different questions — this one is what a consumer's
//! repository will change, the changelog is what happened in this one — and the
//! heading is what makes that legible.
//!
//! So the grouping is by axis value rather than by kind of change — a
//! repository on `language: go` can skip the `language/rust` block whole — and
//! each entry is named by its `title:`, which is the heading that will appear
//! in that repository's own `AGENTS.md` once the bump lands.
//!
//! Every file counts, not only the markdown. A release whose entire content is
//! one line of `settings.partial.json` changes what a repository gets, and
//! notes that said "no fragment changed" would be lying about it.
//!
//! What this cannot see is the tool. The fragments are the source, but the
//! binary composing them is an input too: v0.13.0 changed no fragment and still
//! added `.claude/skills/why/SKILL.md` to every Claude repository. So a release
//! with nothing to list says where a change could still have come from, rather
//! than letting "no fragment changed" be read as "nothing changed".

use std::collections::BTreeMap;

use crate::{FragmentSet, Meta};

/// What happened to one file between the two trees.
///
/// Ordered as the sentence is: added, changed, removed.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum Kind {
    Added,
    Changed,
    Removed,
}

impl Kind {
    /// The word the notes use.
    const fn label(self) -> &'static str {
        match self {
            Self::Added => "added",
            Self::Changed => "changed",
            Self::Removed => "removed",
        }
    }
}

/// The fragment-level difference between two releases, as markdown.
///
/// `previous` is the tree the last release shipped — in the release workflow,
/// a checkout of the previous tag's `fragments/` — and `current` is this one,
/// normally [`FragmentSet::embedded`].
///
/// ```
/// use agentcfg::{FragmentSet, notes};
///
/// let tree = FragmentSet::embedded()?;
///
/// // A release that changed no fragment says so — and says where a change
/// // could still come from, since composing is the tool's job too.
/// assert!(
///     notes(&tree, &tree).contains("No fragment changed in this release.")
/// );
/// # Ok::<(), agentcfg::FragmentError>(())
/// ```
#[must_use]
pub fn notes(previous: &FragmentSet, current: &FragmentSet) -> String {
    let mut groups: BTreeMap<(u8, String), Vec<(Kind, String)>> = BTreeMap::new();

    for (path, contents) in current.files() {
        let kind = match previous.file(path) {
            None => Kind::Added,
            Some(before) if before != contents => Kind::Changed,
            Some(_) => continue,
        };
        groups
            .entry(group(path))
            .or_default()
            .push((kind, name(current, path)));
    }

    for (path, _) in previous.files() {
        if current.file(path).is_none() {
            groups
                .entry(group(path))
                .or_default()
                .push((Kind::Removed, name(previous, path)));
        }
    }

    if groups.is_empty() {
        return "### What this changes in your repository\n\nNo fragment changed in this release. Anything this bump changes in your repository comes from the tool rather than from the rules.\n".to_owned();
    }

    let mut out = String::from("### What this changes in your repository\n");
    for ((_, group), mut entries) in groups {
        entries.sort();
        out.push_str(&format!("\n**{group}**\n"));
        for (kind, name) in entries {
            out.push_str(&format!("- {} — {name}\n", kind.label()));
        }
    }
    out
}

/// The axis value a path belongs to — `core`, or `<axis>/<value>` — and where
/// it sorts.
///
/// This is the unit a profile picks, so it is the unit a reader decides on.
/// `core` leads rather than sorting alphabetically between `concerns` and
/// `deployment`: it is the one group in every repository's composition, so a
/// reader asking *does this affect me* has the answer that always applies in
/// the first block. The rest follow by name.
fn group(path: &str) -> (u8, String) {
    let parts: Vec<&str> = path.split('/').collect();
    match parts.as_slice() {
        ["core", ..] => (0, "core".to_owned()),
        [axis, value, ..] => (1, format!("{axis}/{value}")),
        _ => (1, path.to_owned()),
    }
}

/// What to call a file: a fragment's title, or its bare filename.
///
/// A `values.yml` or `settings.partial.json` carries no frontmatter and so has
/// no title. The filename is what someone would go looking for anyway, and
/// naming it is better than leaving the change unlisted.
fn name(set: &FragmentSet, path: &str) -> String {
    for fragment in set.fragments() {
        if fragment.path() == path {
            return match fragment.meta() {
                Meta::Rules(meta) => meta.title.clone(),
                Meta::Task(meta) => meta.title.clone(),
            };
        }
    }

    path.rsplit('/').next().unwrap_or(path).to_owned()
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    /// A fragment body long enough to be worth diffing.
    const RULES: &str = "\
---
title: Git flow
scope: on-demand
when: Any change that ends in a PR
---

The branch → commit → PR loop.
";

    fn tree(files: &[(&str, &str)]) -> FragmentSet {
        FragmentSet::build(files, &[("language", &["rust"])]).unwrap()
    }

    #[test]
    fn a_release_that_touched_nothing_says_so_rather_than_printing_an_empty_list() {
        let set = tree(&[("core/git-flow.md", RULES)]);

        assert_eq!(
            notes(&set, &set),
            "### What this changes in your repository\n\nNo fragment changed in this release. Anything this bump changes in your repository comes from the tool rather than from the rules.\n"
        );
    }

    #[test]
    fn a_fragment_is_named_by_its_title_not_its_path() {
        let before = tree(&[]);
        let after = tree(&[("core/git-flow.md", RULES)]);

        let rendered = notes(&before, &after);
        assert!(rendered.contains("- added — Git flow\n"), "{rendered}");
        assert!(
            !rendered.contains("git-flow.md"),
            "the path is what the title replaces: {rendered}"
        );
    }

    #[test]
    fn a_file_with_no_frontmatter_is_listed_under_its_filename() {
        let before = tree(&[("language/rust/values.yml", "unit: crate\n")]);
        let after = tree(&[("language/rust/values.yml", "unit: crate\ngate: just ci\n")]);

        // It is not a fragment and has no title, but a repository on
        // `language: rust` still gets different output because of it.
        assert!(
            notes(&before, &after).contains("- changed — values.yml\n"),
            "{}",
            notes(&before, &after)
        );
    }

    #[test]
    fn entries_group_by_the_value_a_profile_picks() {
        let before = tree(&[("core/git-flow.md", RULES)]);
        let after = tree(&[
            (
                "core/git-flow.md",
                &RULES.replace("loop.", "loop, in order."),
            ),
            (
                "language/rust/tooling.md",
                &RULES.replace("Git flow", "Build"),
            ),
        ]);

        let rendered = notes(&before, &after);
        let core = rendered.find("**core**").expect("core block");
        let rust = rendered.find("**language/rust**").expect("rust block");

        assert!(
            core < rust,
            "a fragment lands under its own value: {rendered}"
        );
        assert!(rendered.contains("- changed — Git flow\n"), "{rendered}");
        assert!(rendered.contains("- added — Build\n"), "{rendered}");
    }

    #[test]
    fn core_leads_even_when_a_group_sorts_before_it_alphabetically() {
        let before = tree(&[]);
        let after = tree(&[
            ("concerns/sync/rules.md", RULES),
            ("core/git-flow.md", RULES),
            ("architecture/ddd/layers.md", RULES),
        ]);

        // `core` is in every composition, so the block that always applies is
        // the first one read — not the third, behind two a repository may not
        // have declared.
        let rendered = notes(&before, &after);
        let core = rendered.find("**core**").expect("core block");

        assert!(
            core < rendered.find("**architecture/ddd**").expect("ddd block"),
            "{rendered}"
        );
        assert!(
            core < rendered.find("**concerns/sync**").expect("sync block"),
            "{rendered}"
        );
    }

    #[test]
    fn a_removed_file_is_named_from_the_tree_that_still_has_it() {
        let before = tree(&[("concerns/sync/rules.md", RULES)]);
        let after = tree(&[]);

        // The title only exists in `before`; looking it up in `after` would
        // silently fall back to the filename.
        assert!(
            notes(&before, &after).contains("- removed — Git flow\n"),
            "{}",
            notes(&before, &after)
        );
    }

    #[test]
    fn the_real_tree_against_an_empty_one_lists_every_file_it_ships() {
        let current = FragmentSet::embedded().unwrap();
        let rendered = notes(&tree(&[]), &current);

        assert_eq!(
            rendered.matches("\n- added — ").count(),
            current.files().count(),
            "every file in the tree is accounted for: {rendered}"
        );
        assert!(rendered.contains("**core**"), "{rendered}");
        assert!(rendered.contains("**language/rust**"), "{rendered}");
    }
}
