//! Which path-scoped rules would never fire.
//!
//! Path-scoped rules fail silently when their globs miss: a repository whose
//! data access lives somewhere unexpected gets no data-access rules and no
//! error. So `check` says when a rule can never load here.
//!
//! The warning is per *rule*, not per pattern. A concern lists alternatives
//! deliberately — data access might live under `store/`, `db/` or
//! `repository/` — and the rule fires if any one of them matches. Reporting
//! each pattern that missed would put eleven warnings on a perfectly healthy
//! repository, and a warning that always appears is one nobody reads.
//!
//! It stays a warning rather than a failure. A repository may legitimately
//! declare a concern before the code that triggers it exists, and failing there
//! would punish exactly the repositories doing it right. Claude Code also fires
//! these rules on *read* rather than on write, so a brand-new `domain/` gets no
//! rules until something matching is read — which makes the warning worth
//! having and still not worth failing on.

use globset::Glob;

use crate::{Meta, Repo, Scope, Selection, error::RepoError};

/// Directories never worth walking, and never the subject of a rule.
const SKIPPED: [&str; 3] = ["target", "node_modules", "vendor"];

/// A selected rule that no file in the repository would ever trigger.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnusedRule {
    /// The fragment that declared it.
    pub fragment: String,
    /// Its title, as the composed output names it.
    pub title: String,
    /// Every pattern that was tried, none of which matched.
    pub globs: Vec<String>,
}

/// Every selected path-scoped rule that matches nothing in `repo`.
///
/// # Errors
///
/// [`RepoError::Io`] if the repository cannot be walked.
pub fn unused_rules(repo: &Repo, selection: &Selection) -> Result<Vec<UnusedRule>, RepoError> {
    let paths = walk(repo)?;
    let mut unused = Vec::new();

    for fragment in selection.fragments() {
        let Meta::Rules(meta) = fragment.meta() else {
            continue;
        };
        if meta.scope != Scope::Paths {
            continue;
        }

        // A pattern that does not compile cannot match, which is the same
        // outcome. `tests/embedded_tree.rs` is where a malformed one is caught,
        // because that is an authoring error rather than a property of a repo.
        let fires = meta.paths.iter().any(|pattern| {
            Glob::new(pattern).is_ok_and(|glob| {
                let matcher = glob.compile_matcher();
                paths.iter().any(|path| matcher.is_match(path))
            })
        });

        if !fires {
            unused.push(UnusedRule {
                fragment: fragment.path().to_owned(),
                title: meta.title.clone(),
                globs: meta.paths.clone(),
            });
        }
    }

    Ok(unused)
}

/// Every file in the repository, as a `/`-separated path relative to its root.
fn walk(repo: &Repo) -> Result<Vec<String>, RepoError> {
    fn descend(
        root: &std::path::Path,
        dir: &std::path::Path,
        out: &mut Vec<String>,
    ) -> Result<(), RepoError> {
        let io = |source| RepoError::Io {
            path: dir.display().to_string(),
            source,
        };

        for entry in std::fs::read_dir(dir).map_err(io)? {
            let entry = entry.map_err(io)?;
            let name = entry.file_name().to_string_lossy().into_owned();
            let path = entry.path();

            if entry.file_type().map_err(io)?.is_dir() {
                // Build output and version control hold no rules, and walking
                // `target/` alone can cost more than the rest of the check.
                if name.starts_with('.') || SKIPPED.contains(&name.as_str()) {
                    continue;
                }
                descend(root, &path, out)?;
            } else {
                out.push(
                    path.strip_prefix(root)
                        .unwrap_or(&path)
                        .display()
                        .to_string()
                        .replace('\\', "/"),
                );
            }
        }

        Ok(())
    }

    let mut paths = Vec::new();
    descend(repo.root(), repo.root(), &mut paths)?;
    Ok(paths)
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .agents/rust-code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;
    use crate::{FragmentSet, Profile};

    /// A repository selecting both hazard concerns, plus whatever `files` says.
    fn sandbox(files: &[&str]) -> (tempfile::TempDir, Repo, Selection) {
        // Keeps the TempDir alive for the caller; dropping it deletes the tree.
        let dir = tempfile::tempdir().unwrap();
        for file in files {
            let path = dir.path().join(file);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, "").unwrap();
        }

        let tree = FragmentSet::embedded().unwrap();
        let profile = Profile::parse(
            "config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\nconcerns: [data-access, sync]\nemit: [agents-md]\n",
            &tree,
        )
        .unwrap();
        let selection = Selection::resolve(&profile, &tree).unwrap();

        let repo = Repo::at(dir.path());
        (dir, repo, selection)
    }

    fn titles(repo: &Repo, selection: &Selection) -> Vec<String> {
        unused_rules(repo, selection)
            .unwrap()
            .into_iter()
            .map(|rule| rule.title)
            .collect()
    }

    #[test]
    fn a_repository_with_none_of_the_code_is_told_both_rules_are_idle() {
        let (_dir, repo, selection) = sandbox(&["src/main.rs"]);

        assert_eq!(
            titles(&repo, &selection),
            ["Data access", "Synchronisation"]
        );
    }

    #[test]
    fn one_matching_file_is_enough_to_retire_the_warning() {
        // The alternatives are deliberate: data access might live under any of
        // them, and the rule fires if one matches.
        let (_dir, repo, selection) = sandbox(&["internal/store/user.go"]);

        assert_eq!(titles(&repo, &selection), ["Synchronisation"]);
    }

    #[test]
    fn every_pattern_a_rule_declares_is_reported_together() {
        let (_dir, repo, selection) = sandbox(&["src/main.rs"]);
        let rules = unused_rules(&repo, &selection).unwrap();

        let data_access = &rules[0];
        assert_eq!(data_access.fragment, "concerns/data-access/rules.md");
        assert!(data_access.globs.contains(&"**/*.sql".to_owned()));
        assert!(
            data_access.globs.len() > 1,
            "one warning, every alternative"
        );
    }

    #[test]
    fn a_rule_that_fires_is_not_reported_at_all() {
        let (_dir, repo, selection) = sandbox(&["db/schema.sql", "worker/queue.rs"]);

        assert!(titles(&repo, &selection).is_empty());
    }

    #[test]
    fn build_output_and_version_control_are_not_searched() {
        // Otherwise a compiled artifact under `target/` could retire a warning
        // the source tree has not earned — and walking it costs more than the
        // rest of the check.
        let (_dir, repo, selection) = sandbox(&["target/debug/build/db/out.sql", ".git/store/x"]);

        assert_eq!(
            titles(&repo, &selection),
            ["Data access", "Synchronisation"]
        );
    }
}
