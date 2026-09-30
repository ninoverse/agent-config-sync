//! A task's companion files, through a whole sync: written once beside the
//! skill, tracked like every other generated file, and gone with their task.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::{fs, path::Path};

use agentcfg::{ChangeKind, Composition, FragmentSet, Repo};

const VERSION: &str = "v1.0.0";
const SCRIPT: &str = "language/rust/tasks/new-unit/scaffold.sh";
const EMITTED: &str = ".agents/new-crate/scaffold.sh";

/// The real tree, written to `dir` with `extra` beside it and read back the
/// way `--fragments` reads one. No task in the real tree ships a companion yet.
fn tree_with(dir: &Path, extra: &[(&str, &str)]) -> FragmentSet {
    let embedded = FragmentSet::embedded().unwrap();
    // A value may hold no files, as `sensitivity/none/` does, so the
    // directories are written from the axes rather than from the files.
    for (axis, values) in embedded.axes() {
        for value in values {
            fs::create_dir_all(dir.join(axis).join(value)).unwrap();
        }
    }
    for (path, contents) in embedded.files().chain(extra.iter().copied()) {
        let file = dir.join(path);
        fs::create_dir_all(file.parent().unwrap()).unwrap();
        fs::write(file, contents).unwrap();
    }

    FragmentSet::from_dir(dir).unwrap()
}

/// A repository with a Rust profile emitting `emit`, synced from `tree`.
fn synced(tree: &FragmentSet, emit: &str) -> tempfile::TempDir {
    let dir = tempfile::tempdir().unwrap();
    fs::write(
        dir.path().join(".agentprofile.yml"),
        format!("config_version: {VERSION}\nlanguage: rust\ndeployment: tag-only\nemit: {emit}\n"),
    )
    .unwrap();

    let repo = Repo::at(dir.path());
    let composed = Composition::of(&repo, tree, VERSION).unwrap();
    repo.apply(&composed.plan).unwrap();
    dir
}

#[test]
fn a_companion_is_written_once_whichever_emitters_the_profile_names() {
    let fragments = tempfile::tempdir().unwrap();
    let tree = tree_with(fragments.path(), &[(SCRIPT, "echo scaffold\n")]);

    for emit in ["[agents-md]", "[agents-md, claude]"] {
        let dir = synced(&tree, emit);

        assert_eq!(
            fs::read_to_string(dir.path().join(EMITTED)).unwrap(),
            "echo scaffold\n",
            "{emit}"
        );
        let manifest = fs::read_to_string(dir.path().join(".agentcfg-manifest.json")).unwrap();
        assert_eq!(manifest.matches("scaffold.sh").count(), 1, "{emit}");
    }
}

#[test]
fn check_fails_when_the_emitted_copy_is_edited() {
    let fragments = tempfile::tempdir().unwrap();
    let tree = tree_with(fragments.path(), &[(SCRIPT, "echo scaffold\n")]);
    let dir = synced(&tree, "[agents-md, claude]");
    let repo = Repo::at(dir.path());

    assert!(
        Composition::of(&repo, &tree, VERSION)
            .unwrap()
            .plan
            .is_clean()
    );

    fs::write(dir.path().join(EMITTED), "echo edited\n").unwrap();
    let composed = Composition::of(&repo, &tree, VERSION).unwrap();
    let pending: Vec<_> = composed.plan.pending().collect();

    assert_eq!(pending.len(), 1, "{pending:?}");
    assert_eq!(pending[0].path, EMITTED);
    assert_eq!(pending[0].kind, ChangeKind::Updated);
}

#[test]
fn a_companion_goes_when_its_task_stops_shipping_it() {
    let fragments = tempfile::tempdir().unwrap();
    let with_script = tree_with(fragments.path(), &[(SCRIPT, "echo scaffold\n")]);
    let dir = synced(&with_script, "[agents-md, claude]");
    let repo = Repo::at(dir.path());

    let composed = Composition::of(&repo, &FragmentSet::embedded().unwrap(), VERSION).unwrap();
    let removed = composed
        .plan
        .pending()
        .find(|change| change.path == EMITTED)
        .unwrap();

    assert_eq!(removed.kind, ChangeKind::Deleted);
    repo.apply(&composed.plan).unwrap();
    assert!(!dir.path().join(EMITTED).exists());
}
