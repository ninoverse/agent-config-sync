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
fn every_new_thing_task_follows_the_repositorys_own_steps_before_its_gate() {
    // A composed skill is owned whole, so a repository adds its own steps
    // through a file beside it. The task has to be the one that reads it.
    for fragment in tree().fragments() {
        let Meta::Task(meta) = fragment.meta() else {
            continue;
        };
        if !meta.name.starts_with("new-") {
            continue;
        }

        let body = fragment.body();
        let gate = body
            .find("Verification gate")
            .unwrap_or_else(|| panic!("{}: no verification gate", fragment.path()));
        let step_end = body[gate..]
            .find("\n### ")
            .map_or(body.len(), |offset| gate + offset);
        let local = format!("`.agents/{}.local.md`", meta.name);

        assert!(
            body[gate..step_end].contains(&local),
            "{}: the gate step never follows {local}",
            fragment.path()
        );
    }
}

#[test]
fn every_deployment_value_says_what_a_merge_sets_off() {
    // Git flow closes by sending the reader to this repository's deployment
    // rules for what the merge triggered. A value with nothing on Git flow's own
    // trigger leaves that pointer landing on nothing.
    let tree = tree();
    let git_flow = tree
        .fragments()
        .iter()
        .find(|fragment| fragment.path() == "core/git-flow.md")
        .expect("core ships Git flow");
    let Meta::Rules(git_flow) = git_flow.meta() else {
        panic!("Git flow is a rules fragment");
    };

    for value in tree.values("deployment") {
        let prefix = format!("deployment/{value}/");
        let answers = tree.fragments().iter().any(|fragment| {
            fragment.path().starts_with(&prefix)
                && matches!(fragment.meta(), Meta::Rules(meta) if meta.when == git_flow.when)
        });
        assert!(
            answers,
            "deployment/{value} never says what a merge sets off"
        );
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

#[test]
fn reading_the_tree_from_disk_agrees_with_the_embedded_copy() {
    // `--fragments` and the release must compose identically, or iterating
    // locally proves nothing about what ships. This caught a real divergence:
    // deriving axes from file paths rather than directories made
    // `sensitivity/none/` — which holds no fragments — disappear, so
    // `sensitivity: none` was rejected under `--fragments` and accepted under
    // the embedded tree.
    let embedded = tree();
    let on_disk = FragmentSet::from_dir(std::path::Path::new("../../fragments"))
        .expect("the workspace's own fragments/ directory");

    assert_eq!(embedded.axes(), on_disk.axes());
    assert_eq!(embedded.fragments(), on_disk.fragments());
    assert_eq!(
        embedded.file("language/rust/values.yml"),
        on_disk.file("language/rust/values.yml")
    );
}

#[test]
fn every_path_scoped_glob_in_the_tree_compiles() {
    // A malformed pattern matches nothing, which at run time is indistinguishable
    // from a rule that simply does not apply to a repository. Catching it here
    // keeps that an authoring error rather than a silent one.
    for fragment in tree().fragments() {
        let Meta::Rules(meta) = fragment.meta() else {
            continue;
        };

        for pattern in &meta.paths {
            assert!(
                globset::Glob::new(pattern).is_ok(),
                "{}: `{pattern}` is not a valid glob",
                fragment.path()
            );
        }
    }
}
