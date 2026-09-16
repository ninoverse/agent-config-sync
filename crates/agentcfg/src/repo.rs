//! A repository under management: what is on disk, and what would change.
//!
//! [`Repo::plan`] computes the difference between a set of generated files and
//! what the repository currently holds, reading only. `sync`, `check` and
//! `plan` all run that one computation and differ in what they do with the
//! answer, which is why drift detection costs nothing extra — it is the same
//! code path.
//!
//! The manifest is what makes removal work. Without a record of what was
//! generated last time, dropping a concern from a profile leaves an orphaned
//! rule file that nothing ever deletes.

use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};

use crate::{
    OutputFile, Ownership,
    error::{MANIFEST, RepoError},
    marker,
};

/// The profile filename, which `sync` only ever reads.
const PROFILE: &str = ".agentprofile.yml";

/// What syncing would do to one path.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChangeKind {
    /// The file does not exist yet.
    Created,
    /// The file exists and its generated content differs.
    Updated,
    /// The file is already what it should be.
    Unchanged,
    /// This profile no longer generates the file, so it goes.
    Deleted,
}

/// One path, and what would happen to it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Change {
    /// The path, relative to the repository root.
    pub path: String,
    /// What would happen.
    pub kind: ChangeKind,
    /// The file's full content afterwards; `None` for a deletion.
    pub content: Option<String>,
}

/// Everything syncing would do, computed without writing anything.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Plan {
    changes: Vec<Change>,
}

impl Plan {
    /// Every path, in order, including the ones already correct.
    #[must_use]
    pub fn changes(&self) -> &[Change] {
        &self.changes
    }

    /// The paths that would actually change.
    pub fn pending(&self) -> impl Iterator<Item = &Change> {
        self.changes
            .iter()
            .filter(|change| change.kind != ChangeKind::Unchanged)
    }

    /// Whether the repository already matches what this profile composes.
    ///
    /// This is what `check` reports: a hand-edited generated file, a stale
    /// manifest and a dropped concern all show up here.
    #[must_use]
    pub fn is_clean(&self) -> bool {
        self.pending().next().is_none()
    }
}

/// A repository `agentcfg` reads from and writes to.
///
/// ```
/// use agentcfg::{OutputFile, Ownership, Repo};
///
/// let sandbox = tempfile::tempdir()?;
/// let repo = Repo::at(sandbox.path());
/// let files = [OutputFile {
///     path: "AGENTS.md".to_owned(),
///     content: "# Behavioral guidelines".to_owned(),
///     ownership: Ownership::Region,
/// }];
///
/// // Reading only: this is what `check` and `plan` run.
/// let plan = repo.plan(&files)?;
/// assert!(!plan.is_clean());
///
/// // Writing: this is the only part `sync` adds.
/// repo.apply(&plan)?;
/// assert!(repo.plan(&files)?.is_clean());
///
/// let written = std::fs::read_to_string(sandbox.path().join("AGENTS.md"))?;
/// assert!(written.starts_with("<!-- agentcfg:start -->"));
/// # Ok::<(), Box<dyn std::error::Error>>(())
/// ```
#[derive(Debug, Clone)]
pub struct Repo {
    root: PathBuf,
}

impl Repo {
    /// The repository rooted at `root`.
    #[must_use]
    pub fn at(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    /// The repository root.
    #[must_use]
    pub fn root(&self) -> &Path {
        &self.root
    }

    /// The profile's text, for parsing.
    ///
    /// # Errors
    ///
    /// [`RepoError::Io`] if it cannot be read — most often because the
    /// repository has never been initialised.
    pub fn profile(&self) -> Result<String, RepoError> {
        self.read(PROFILE)?.ok_or_else(|| RepoError::Io {
            path: PROFILE.to_owned(),
            source: std::io::Error::new(
                std::io::ErrorKind::NotFound,
                "no profile here — run `agentcfg init` to write one",
            ),
        })
    }

    /// What `files` would do to this repository.
    ///
    /// # Errors
    ///
    /// [`RepoError`] if a file cannot be read, a marker region is damaged, the
    /// manifest is unreadable, or an orphaned file carries local content.
    pub fn plan(&self, files: &[OutputFile]) -> Result<Plan, RepoError> {
        let mut changes = Vec::with_capacity(files.len() + 1);

        for file in files {
            let existing = self.read(&file.path)?;
            let content = match file.ownership {
                Ownership::Whole => file.content.clone(),
                Ownership::Region => {
                    marker::splice(&file.path, existing.as_deref(), &file.content)?
                }
            };

            changes.push(Change {
                kind: kind_of(existing.as_deref(), &content),
                path: file.path.clone(),
                content: Some(content),
            });
        }

        let generated: BTreeSet<&str> = files.iter().map(|file| file.path.as_str()).collect();
        for orphan in self.orphans(&generated)? {
            changes.push(Change {
                path: orphan,
                kind: ChangeKind::Deleted,
                content: None,
            });
        }

        let manifest = Manifest::of(&generated).render()?;
        changes.push(Change {
            kind: kind_of(self.read(MANIFEST)?.as_deref(), &manifest),
            path: MANIFEST.to_owned(),
            content: Some(manifest),
        });

        Ok(Plan { changes })
    }

    /// Carries out `plan`.
    ///
    /// # Errors
    ///
    /// [`RepoError::Io`] if a file cannot be written or removed.
    pub fn apply(&self, plan: &Plan) -> Result<(), RepoError> {
        for change in plan.pending() {
            let path = self.root.join(&change.path);

            match (&change.content, change.kind) {
                (_, ChangeKind::Deleted) => {
                    fs::remove_file(&path).map_err(|source| RepoError::Io {
                        path: change.path.clone(),
                        source,
                    })?;
                }
                (Some(content), _) => {
                    if let Some(parent) = path.parent() {
                        fs::create_dir_all(parent).map_err(|source| RepoError::Io {
                            path: change.path.clone(),
                            source,
                        })?;
                    }
                    fs::write(&path, content).map_err(|source| RepoError::Io {
                        path: change.path.clone(),
                        source,
                    })?;
                }
                (None, _) => {}
            }
        }

        Ok(())
    }

    /// Paths the last sync wrote that this one does not.
    fn orphans(&self, generated: &BTreeSet<&str>) -> Result<Vec<String>, RepoError> {
        let Some(text) = self.read(MANIFEST)? else {
            return Ok(Vec::new());
        };
        let manifest: Manifest =
            serde_json::from_str(&text).map_err(|source| RepoError::Manifest { source })?;

        let mut orphans = Vec::new();
        for path in manifest.files {
            if generated.contains(path.as_str()) {
                continue;
            }
            let Some(existing) = self.read(&path)? else {
                continue; // already gone
            };
            // Not a let-chain: those are Rust 1.88, and this workspace is
            // pinned to an older MSRV.
            if let Some((before, after)) = marker::outside(&path, &existing)? {
                if !(before.trim().is_empty() && after.trim().is_empty()) {
                    return Err(RepoError::OrphanHasLocalContent { path });
                }
            }
            orphans.push(path);
        }

        Ok(orphans)
    }

    /// One file's contents, or `None` if it is not there.
    fn read(&self, path: &str) -> Result<Option<String>, RepoError> {
        match fs::read_to_string(self.root.join(path)) {
            Ok(text) => Ok(Some(text)),
            Err(source) if source.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(source) => Err(RepoError::Io {
                path: path.to_owned(),
                source,
            }),
        }
    }
}

/// Every path the tool generated in this repository.
#[derive(Debug, Serialize, Deserialize)]
struct Manifest {
    files: Vec<String>,
}

impl Manifest {
    fn of(generated: &BTreeSet<&str>) -> Self {
        Self {
            files: generated.iter().map(|path| (*path).to_owned()).collect(),
        }
    }

    fn render(&self) -> Result<String, RepoError> {
        let json =
            serde_json::to_string_pretty(self).map_err(|source| RepoError::Manifest { source })?;
        Ok(format!("{json}\n"))
    }
}

fn kind_of(existing: Option<&str>, content: &str) -> ChangeKind {
    match existing {
        None => ChangeKind::Created,
        Some(existing) if existing == content => ChangeKind::Unchanged,
        Some(_) => ChangeKind::Updated,
    }
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    fn sandbox() -> (tempfile::TempDir, Repo) {
        let dir = tempfile::tempdir().unwrap();
        let repo = Repo::at(dir.path());
        (dir, repo)
    }

    fn region(path: &str, content: &str) -> OutputFile {
        OutputFile {
            path: path.to_owned(),
            content: content.to_owned(),
            ownership: Ownership::Region,
        }
    }

    fn whole(path: &str, content: &str) -> OutputFile {
        OutputFile {
            path: path.to_owned(),
            content: content.to_owned(),
            ownership: Ownership::Whole,
        }
    }

    fn write(repo: &Repo, path: &str, content: &str) {
        let full = repo.root().join(path);
        fs::create_dir_all(full.parent().unwrap()).unwrap();
        fs::write(full, content).unwrap();
    }

    fn read(repo: &Repo, path: &str) -> String {
        fs::read_to_string(repo.root().join(path)).unwrap()
    }

    fn sync(repo: &Repo, files: &[OutputFile]) -> Plan {
        let plan = repo.plan(files).unwrap();
        repo.apply(&plan).unwrap();
        plan
    }

    #[test]
    fn a_first_sync_creates_everything_and_a_second_changes_nothing() {
        let (_dir, repo) = sandbox();
        let files = [
            region("AGENTS.md", "rules"),
            whole(
                ".claude/skills/gates/SKILL.md",
                "---\nname: \"gates\"\n---\n",
            ),
        ];

        let first = sync(&repo, &files);
        assert!(
            first
                .changes()
                .iter()
                .all(|change| change.kind == ChangeKind::Created)
        );

        // Nested directories are created on the way.
        assert!(read(&repo, ".claude/skills/gates/SKILL.md").starts_with("---\n"));
        assert!(read(&repo, "AGENTS.md").contains("<!-- agentcfg:start -->"));

        assert!(repo.plan(&files).unwrap().is_clean());
    }

    #[test]
    fn a_hand_edited_generated_file_shows_as_drift() {
        let (_dir, repo) = sandbox();
        let files = [region("AGENTS.md", "rules")];
        sync(&repo, &files);

        write(
            &repo,
            "AGENTS.md",
            "<!-- agentcfg:start -->\ntampered\n<!-- agentcfg:end -->\n",
        );

        let plan = repo.plan(&files).unwrap();
        assert!(!plan.is_clean());
        assert_eq!(plan.pending().count(), 1);
        assert_eq!(plan.pending().next().unwrap().kind, ChangeKind::Updated);
    }

    #[test]
    fn content_outside_the_markers_survives_regeneration() {
        let (_dir, repo) = sandbox();
        sync(&repo, &[region("AGENTS.md", "first")]);

        let with_local = format!(
            "{}\nThe MSRV is 1.86 because of the icu chain.\n",
            read(&repo, "AGENTS.md")
        );
        write(&repo, "AGENTS.md", &with_local);

        sync(&repo, &[region("AGENTS.md", "second")]);
        let after = read(&repo, "AGENTS.md");

        assert!(after.contains("second"));
        assert!(!after.contains("first"));
        assert!(after.contains("The MSRV is 1.86 because of the icu chain."));
    }

    #[test]
    fn dropping_a_fragment_deletes_the_file_it_used_to_generate() {
        let (_dir, repo) = sandbox();
        sync(
            &repo,
            &[
                region("AGENTS.md", "rules"),
                region(".agents/sync-rules.md", "sync"),
            ],
        );
        assert!(repo.root().join(".agents/sync-rules.md").exists());

        // The profile dropped the concern, so the emitter stops producing it.
        let plan = sync(&repo, &[region("AGENTS.md", "rules")]);

        assert!(!repo.root().join(".agents/sync-rules.md").exists());
        assert!(plan.changes().iter().any(|change| {
            change.path == ".agents/sync-rules.md" && change.kind == ChangeKind::Deleted
        }));
        assert!(!read(&repo, MANIFEST).contains("sync-rules"));
    }

    #[test]
    fn an_orphan_someone_has_written_in_stops_the_sync() {
        let (_dir, repo) = sandbox();
        sync(
            &repo,
            &[
                region("AGENTS.md", "rules"),
                region(".agents/sync-rules.md", "sync"),
            ],
        );

        let kept = format!(
            "{}\nOur queue is at-most-once, deliberately.\n",
            read(&repo, ".agents/sync-rules.md")
        );
        write(&repo, ".agents/sync-rules.md", &kept);

        let error = repo.plan(&[region("AGENTS.md", "rules")]).unwrap_err();

        assert!(matches!(error, RepoError::OrphanHasLocalContent { .. }));
        // Nothing was written, and the file still holds what was added to it.
        assert!(read(&repo, ".agents/sync-rules.md").contains("at-most-once"));
    }

    #[test]
    fn a_damaged_region_stops_the_whole_sync_not_just_that_file() {
        let (_dir, repo) = sandbox();
        write(
            &repo,
            "AGENTS.md",
            "<!-- agentcfg:start -->\nno end marker\n",
        );

        let files = [
            region("AGENTS.md", "rules"),
            region(".agents/git-flow.md", "flow"),
        ];
        let error = repo.plan(&files).unwrap_err();

        assert!(matches!(error, RepoError::DamagedRegion { .. }));
        assert!(error.to_string().contains("AGENTS.md"), "{error}");
        // `sync` refuses rather than guessing: the untouched file is not
        // written either, so the repository never lands half-updated.
        assert!(!repo.root().join(".agents/git-flow.md").exists());
        assert_eq!(
            read(&repo, "AGENTS.md"),
            "<!-- agentcfg:start -->\nno end marker\n"
        );
    }

    #[test]
    fn a_whole_file_is_replaced_rather_than_spliced() {
        let (_dir, repo) = sandbox();
        sync(
            &repo,
            &[whole(".claude/settings.json", "{\n  \"a\": 1\n}\n")],
        );
        sync(
            &repo,
            &[whole(".claude/settings.json", "{\n  \"b\": 2\n}\n")],
        );

        let after = read(&repo, ".claude/settings.json");
        assert_eq!(after, "{\n  \"b\": 2\n}\n");
        assert!(!after.contains("agentcfg:start"));
    }

    #[test]
    fn a_stale_manifest_is_drift_in_its_own_right() {
        let (_dir, repo) = sandbox();
        let files = [region("AGENTS.md", "rules")];
        sync(&repo, &files);

        write(&repo, MANIFEST, "{\n  \"files\": []\n}\n");

        let plan = repo.plan(&files).unwrap();
        assert!(!plan.is_clean());
        assert_eq!(plan.pending().next().unwrap().path, MANIFEST);
    }

    #[test]
    fn an_unreadable_manifest_says_how_to_recover() {
        let (_dir, repo) = sandbox();
        write(&repo, MANIFEST, "not json");

        let error = repo.plan(&[region("AGENTS.md", "rules")]).unwrap_err();

        assert!(matches!(error, RepoError::Manifest { .. }));
        assert!(error.to_string().contains("agentcfg sync"), "{error}");
    }

    #[test]
    fn a_missing_profile_says_what_to_run() {
        let (_dir, repo) = sandbox();
        let error = repo.profile().unwrap_err();

        assert!(error.to_string().contains(".agentprofile.yml"), "{error}");
        assert!(error.to_string().contains("agentcfg init"), "{error}");
    }

    #[test]
    fn syncing_never_writes_the_profile() {
        let (_dir, repo) = sandbox();
        write(&repo, PROFILE, "language: rust\n");
        sync(&repo, &[region("AGENTS.md", "rules")]);

        // Renovate's custom manager owns that file during a bump; a task that
        // rewrote it would have the manager's version silently discarded.
        assert_eq!(read(&repo, PROFILE), "language: rust\n");
        assert!(!read(&repo, MANIFEST).contains(PROFILE));
    }
}
