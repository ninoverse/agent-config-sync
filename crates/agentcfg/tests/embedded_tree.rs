//! Invariants of the fragment tree this binary was built from.
//!
//! The unit tests cover what `Fragment::parse` accepts and rejects in
//! isolation. These cover the shape of the real tree, which parsing alone
//! cannot see: that `core/` stayed language-neutral, that the two language
//! values kept parity, and that no two skills in one value would collide.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::collections::{BTreeMap, BTreeSet};

use agentcfg::{Fragment, FragmentSet, Meta, Scope};

fn tree() -> FragmentSet {
    FragmentSet::embedded().expect("every embedded fragment parses")
}

/// The `<axis>/<value>` a fragment lives in, or `None` for `core/`.
fn value_of(fragment: &Fragment) -> Option<String> {
    let mut segments = fragment.path().split('/');
    let axis = segments.next()?;
    let value = segments.next()?;
    (axis != "core").then(|| format!("{axis}/{value}"))
}

/// A fragment's path within its value, e.g. `tasks/gates.md`.
fn name_within_value(fragment: &Fragment) -> String {
    match value_of(fragment) {
        Some(value) => fragment.path()[value.len() + 1..].to_owned(),
        None => fragment.path().to_owned(),
    }
}

#[test]
fn core_holds_only_language_neutral_rules() {
    for fragment in tree().fragments() {
        if value_of(fragment).is_some() {
            continue;
        }

        match fragment.meta() {
            Meta::Rules(meta) => assert_ne!(
                meta.scope,
                Scope::Paths,
                "{}: core has no layer to scope globs to",
                fragment.path()
            ),
            Meta::Task(_) => panic!(
                "{}: a task belongs to a language value, not to core",
                fragment.path()
            ),
        }
    }
}

#[test]
fn every_on_demand_fragment_declares_a_usable_trigger() {
    for fragment in tree().fragments() {
        let Meta::Rules(meta) = fragment.meta() else {
            continue;
        };
        if meta.scope != Scope::OnDemand {
            continue;
        }

        let when = meta.when.as_deref().unwrap_or_default();
        assert!(
            !when.trim().is_empty(),
            "{}: `when:` is what the composed index line reads",
            fragment.path()
        );
    }
}

#[test]
fn every_task_names_a_skill_and_the_condition_that_loads_it() {
    for fragment in tree().fragments() {
        let Meta::Task(meta) = fragment.meta() else {
            continue;
        };

        assert!(
            fragment.path().contains("/tasks/"),
            "{}: task frontmatter outside a tasks/ directory",
            fragment.path()
        );
        assert!(!meta.name.trim().is_empty(), "{}", fragment.path());
        assert!(!meta.description.trim().is_empty(), "{}", fragment.path());
    }
}

#[test]
fn no_two_skills_in_one_value_would_collide() {
    let tree = tree();
    let mut seen: BTreeSet<(String, &str)> = BTreeSet::new();

    for fragment in tree.fragments() {
        let Meta::Task(meta) = fragment.meta() else {
            continue;
        };
        let value = value_of(fragment).unwrap_or_default();

        assert!(
            seen.insert((value.clone(), &meta.name)),
            "{value} ships two skills named `{}` — one would overwrite the other",
            meta.name
        );
    }
}

#[test]
fn the_language_values_stay_at_parity() {
    let tree = tree();
    let mut by_value: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();

    for fragment in tree.fragments() {
        let Some(value) = value_of(fragment) else {
            continue;
        };
        if value.starts_with("language/") {
            by_value
                .entry(value)
                .or_default()
                .insert(name_within_value(fragment));
        }
    }

    // Core fragments substitute vocabulary from whichever language is picked, so
    // a rule one language ships and the other does not is a hole in composition.
    let mut values = by_value.values();
    let first = values.next().expect("at least one language value");
    for other in values {
        assert_eq!(first, other, "the language values ship different fragments");
    }

    for value in by_value.keys() {
        for required in ["values.yml", "settings.partial.json"] {
            assert!(
                tree.file(&format!("{value}/{required}")).is_some(),
                "{value} is missing {required}"
            );
        }
    }
}
