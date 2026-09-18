//! What each profile composes: which files, from which fragments, in what order.
//!
//! Deliberately *not* a copy of the composed prose. A fragment's text is
//! reviewed in that fragment's own diff; duplicating it here would mean every
//! wording change failed the test suite for a reason that has nothing to do
//! with the crate being broken, and the fix would be to regenerate rather than
//! to think.
//!
//! What is worth pinning is the structure the emitters decide: the set of paths,
//! whether each is spliced or owned outright, and which fragments were composed
//! into it, in composition order. That changes when a fragment is added,
//! removed or moved between axes — which is exactly when someone should look —
//! and stays still when prose is edited.
//!
//! Regenerate with `AGENTCFG_BLESS=1 cargo test`.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
};

use agentcfg::{Composition, FragmentSet, OutputFile, Ownership, Repo};

/// Fixed so that cutting a release does not rewrite every fixture.
const VERSION: &str = "v1.0.0";

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures")
}

fn blessing() -> bool {
    std::env::var_os("AGENTCFG_BLESS").is_some()
}

/// Renders the shape of a composition: each file, how it is owned, and the
/// fragments that went into it.
///
/// Sources are read back out of the provenance comments, so this describes what
/// a reader of the repository would be able to work out for themselves.
fn describe(files: &[OutputFile]) -> String {
    let mut out = String::new();

    for file in files {
        let ownership = match file.ownership {
            Ownership::Region => "region",
            Ownership::Whole => "whole",
        };
        out.push_str(&format!("{} ({ownership})\n", file.path));

        for line in file.content.lines() {
            if let Some(rest) = line.strip_prefix("<!-- ") {
                if let Some(source) = rest.split(" · ").next() {
                    if source.ends_with(".md") {
                        out.push_str(&format!("    {source}\n"));
                    }
                }
            }
        }
    }

    out
}

/// Composes `fixture` into `sandbox` and writes it.
fn compose(fixture: &str, sandbox: &Path) -> Composition {
    let profile = fs::read_to_string(fixtures().join(fixture).join("profile.yml")).unwrap();
    fs::write(sandbox.join(".agentprofile.yml"), profile).unwrap();

    let tree = FragmentSet::embedded().unwrap();
    let repo = Repo::at(sandbox);
    let composed = Composition::of(&repo, &tree, VERSION).unwrap();
    repo.apply(&composed.plan).unwrap();
    composed
}

/// Every file under `root`, by path relative to it.
fn paths_under(root: &Path) -> BTreeSet<String> {
    fn walk(root: &Path, dir: &Path, out: &mut BTreeSet<String>) {
        let Ok(entries) = fs::read_dir(dir) else {
            return;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                walk(root, &path, out);
            } else {
                out.insert(path.strip_prefix(root).unwrap().display().to_string());
            }
        }
    }

    let mut out = BTreeSet::new();
    walk(root, root, &mut out);
    out
}

fn assert_fixture(fixture: &str) {
    let sandbox = tempfile::tempdir().unwrap();
    let composed = compose(fixture, sandbox.path());

    let shape = fixtures().join(fixture).join("expected.txt");
    let actual = describe(&composed.files);

    if blessing() {
        fs::write(&shape, &actual).unwrap();
    } else {
        let expected = fs::read_to_string(&shape).unwrap_or_else(|_| {
            panic!("{fixture} has no expected.txt — run `AGENTCFG_BLESS=1 cargo test`")
        });
        assert_eq!(actual, expected, "{fixture}: composition shape changed");
    }

    // Everything described was written, and nothing else was.
    let mut wanted: BTreeSet<String> = composed
        .files
        .iter()
        .map(|file| file.path.clone())
        .collect();
    wanted.insert(".agentcfg-manifest.json".to_owned());
    wanted.insert(".agentprofile.yml".to_owned());

    assert_eq!(paths_under(sandbox.path()), wanted, "{fixture}: on disk");
}

#[test]
fn rust_template() {
    assert_fixture("rust-template");
}

#[test]
fn go_service() {
    assert_fixture("go-service");
}

#[test]
fn two_concerns() {
    assert_fixture("two-concerns");
}

/// This repository's own profile: the two values Stage 6 added, composed
/// together before anything selects them for real.
#[test]
fn rust_cli() {
    assert_fixture("rust-cli");
}

#[test]
fn dropping_a_concern_removes_the_files_it_generated() {
    // The manifest's whole reason for existing: without it, the dropped
    // concerns' rule files sit in the repository forever, unselected and unread.
    let sandbox = tempfile::tempdir().unwrap();

    let wide = compose("two-concerns", sandbox.path());
    let wide_paths: BTreeSet<&str> = wide.files.iter().map(|f| f.path.as_str()).collect();
    assert!(wide_paths.contains(".agents/data-access-rules.md"));
    assert!(wide_paths.contains(".claude/rules/sync-rules.md"));

    // Same repository, narrower profile.
    compose("rust-template", sandbox.path());

    assert!(!sandbox.path().join(".agents/data-access-rules.md").exists());
    assert!(!sandbox.path().join(".claude/rules/sync-rules.md").exists());
    assert!(
        !sandbox.path().join(".claude/rules").exists()
            || paths_under(&sandbox.path().join(".claude/rules")).is_empty()
    );

    // And it lands on exactly what that profile composes from scratch.
    let fresh = tempfile::tempdir().unwrap();
    compose("rust-template", fresh.path());
    assert_eq!(paths_under(sandbox.path()), paths_under(fresh.path()));
}

#[test]
fn sync_refuses_a_mangled_marker_region_and_writes_nothing() {
    let sandbox = tempfile::tempdir().unwrap();
    compose("rust-template", sandbox.path());
    let before = paths_under(sandbox.path());

    fs::write(
        sandbox.path().join("AGENTS.md"),
        "<!-- agentcfg:start -->\nsomeone deleted the end marker\n",
    )
    .unwrap();
    let untouched = fs::read_to_string(sandbox.path().join(".agents/git-flow.md")).unwrap();

    let repo = Repo::at(sandbox.path());
    let error = Composition::of(&repo, &FragmentSet::embedded().unwrap(), VERSION).unwrap_err();

    assert!(error.to_string().contains("AGENTS.md"), "{error}");
    assert!(
        error.to_string().contains("start marker with no end"),
        "{error}"
    );

    // The refusal is total: no other file moved, so the repository never lands
    // half-updated.
    assert_eq!(paths_under(sandbox.path()), before);
    assert_eq!(
        fs::read_to_string(sandbox.path().join(".agents/git-flow.md")).unwrap(),
        untouched
    );
}
