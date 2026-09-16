//! The two ends of a repository's life under the tool, and the lookup between.
//!
//! `init` is the one moment a person meets this system on purpose; `eject` is
//! the exit that makes adopting it a small decision; `why` is what makes a
//! centralised rule traceable from the repository that obeys it.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::fs;

use agentcfg::{Composition, FragmentSet, Repo};

const VERSION: &str = "v1.0.0";

fn synced(axes: &str) -> tempfile::TempDir {
    let dir = tempfile::tempdir().unwrap();
    fs::write(
        dir.path().join(".agentprofile.yml"),
        format!("config_version: {VERSION}\nemit: [agents-md, claude]\n{axes}"),
    )
    .unwrap();

    let repo = Repo::at(dir.path());
    let composed = Composition::of(&repo, &FragmentSet::embedded().unwrap(), VERSION).unwrap();
    repo.apply(&composed.plan).unwrap();
    dir
}

const RUST: &str = "language: rust\ndeployment: tag-only\nconcerns: [template]\n";

#[test]
fn the_why_skill_is_written_for_every_claude_repository() {
    let dir = synced(RUST);
    let skill = fs::read_to_string(dir.path().join(".claude/skills/why/SKILL.md")).unwrap();

    // It belongs to no fragment, so no profile can drop it: the agent obeying
    // these rules is the one most likely to need to trace one.
    assert!(skill.contains("name: \"why\""));
    assert!(skill.contains("agentcfg why"));
    assert!(!skill.contains("disable-model-invocation"));
}

#[test]
fn a_built_in_skill_costs_the_budget_like_any_other() {
    let dir = synced(RUST);
    let repo = Repo::at(dir.path());
    let composed = Composition::of(&repo, &FragmentSet::embedded().unwrap(), VERSION).unwrap();

    let budget = agentcfg::Budget::measure(&composed.files);
    assert!(
        budget
            .entries()
            .iter()
            .any(|entry| entry.source == "agentcfg:why"),
        "the /why description loads every session: {:?}",
        budget.entries()
    );
}

#[test]
fn ejecting_keeps_every_file_and_stops_managing_them() {
    let dir = synced(RUST);
    let repo = Repo::at(dir.path());

    // Something genuinely local, in the escape hatch it exists for.
    let rule = dir.path().join(".agents/rust-testing.md");
    let local = "\nThe MSRV is 1.86 because of the icu chain.\n";
    fs::write(&rule, fs::read_to_string(&rule).unwrap() + local).unwrap();

    let before: Vec<String> = fs::read_to_string(dir.path().join(".agentcfg-manifest.json"))
        .map(|text| {
            serde_json::from_str::<serde_json::Value>(&text).unwrap()["files"]
                .as_array()
                .unwrap()
                .iter()
                .map(|value| value.as_str().unwrap().to_owned())
                .collect()
        })
        .unwrap();

    let freed = repo.eject().unwrap();
    assert_eq!(freed.len(), before.len());

    for path in &before {
        let kept = dir.path().join(path);
        assert!(kept.exists(), "{path} was taken away");
        let content = fs::read_to_string(&kept).unwrap();
        assert!(!content.contains("agentcfg:start"), "{path}");
        assert!(!content.contains("agentcfg:end"), "{path}");
    }

    // The composed rules survive as ordinary content, and so does the local
    // note that was sitting beside one.
    assert!(
        fs::read_to_string(dir.path().join("AGENTS.md"))
            .unwrap()
            .contains("# Behavioral guidelines")
    );
    assert!(fs::read_to_string(&rule).unwrap().contains("icu chain"));

    // Nothing is managed any more.
    assert!(!dir.path().join(".agentprofile.yml").exists());
    assert!(!dir.path().join(".agentcfg-manifest.json").exists());
}

#[test]
fn ejecting_a_repository_that_was_never_managed_does_nothing() {
    let dir = tempfile::tempdir().unwrap();

    assert!(Repo::at(dir.path()).eject().unwrap().is_empty());
}

#[test]
fn a_second_sync_after_ejecting_starts_the_file_over_rather_than_doubling_it() {
    // Ejecting leaves unmarked content; re-adopting must not stack a second
    // copy of the rules on top of the first.
    let dir = synced(RUST);
    let repo = Repo::at(dir.path());
    let profile = fs::read_to_string(dir.path().join(".agentprofile.yml")).unwrap();

    repo.eject().unwrap();
    fs::write(dir.path().join(".agentprofile.yml"), &profile).unwrap();

    let composed = Composition::of(&repo, &FragmentSet::embedded().unwrap(), VERSION).unwrap();
    repo.apply(&composed.plan).unwrap();

    let agents_md = fs::read_to_string(dir.path().join("AGENTS.md")).unwrap();
    assert_eq!(
        agents_md.matches("# Behavioral guidelines").count(),
        2,
        "the ejected copy is ordinary content now, so it is kept above the region"
    );
    assert_eq!(agents_md.matches("agentcfg:start").count(), 1);
}
