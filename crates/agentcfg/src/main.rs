//! `agentcfg` — composes per-repo agent configuration from single-axis
//! fragments.
//!
//! Almost nobody types any of this. A repository meets `init` once, then
//! experiences the system as a Monday pull request and, on a bad day, a red
//! `check`. The command line is for authoring fragments and for the two moments
//! something goes wrong — which is why the error messages carry the polish
//! budget a wizard would otherwise have absorbed.

use std::{path::PathBuf, process::ExitCode};

use agentcfg::{Change, ChangeKind, Composition, FragmentSet, Plan, Repo};
use clap::{Args, Parser, Subcommand, ValueEnum};

/// The release this binary is, as a profile would pin it.
const VERSION: &str = concat!("v", env!("CARGO_PKG_VERSION"));

/// What provenance says when the fragments came from a directory instead.
const LOCAL: &str = "local";

#[derive(Parser)]
#[command(name = "agentcfg", version, about, long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Write the composed configuration into a repository.
    Sync(Common),
    /// Print what sync would change, without changing it.
    Plan {
        #[command(flatten)]
        common: Common,
        /// How to render the result.
        #[arg(long, value_enum, default_value_t = Format::Text)]
        format: Format,
    },
}

#[derive(Args)]
struct Common {
    /// The repository to act on.
    #[arg(long, default_value = ".", value_name = "PATH")]
    repo: PathBuf,
    /// Compose from this fragment directory instead of the embedded release.
    #[arg(long, value_name = "PATH")]
    fragments: Option<PathBuf>,
}

#[derive(Clone, Copy, ValueEnum)]
enum Format {
    /// For a terminal.
    Text,
    /// For pasting into a pull request.
    Markdown,
}

/// A run that did not finish.
#[derive(Debug, thiserror::Error)]
enum Failure {
    #[error(transparent)]
    Compose(#[from] agentcfg::Error),

    /// The profile pins a release this binary is not.
    ///
    /// Renovate bumps the pin and runs the matching binary, so the two agree in
    /// the case that matters; a mismatch means the wrong binary is on the path,
    /// and composing anyway would stamp provenance nobody could resolve.
    #[error(
        ".agentprofile.yml pins `config_version: {pinned}`, but this is agentcfg {running} — run the pinned release, or bump the pin and sync with the release that matches"
    )]
    VersionMismatch { pinned: String, running: String },
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(failure) => {
            eprintln!("error: {failure}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), Failure> {
    match Cli::parse().command {
        Command::Sync(common) => {
            let (repo, composed) = compose(&common)?;
            repo.apply(&composed.plan).map_err(agentcfg::Error::from)?;
            println!("{}", summary(&composed.plan, "Wrote", "Nothing to write."));
            Ok(())
        }
        Command::Plan { common, format } => {
            let (_, composed) = compose(&common)?;
            print!("{}", render(&composed.plan, format));
            Ok(())
        }
    }
}

/// Reads the repository and composes it, honouring `--fragments`.
fn compose(common: &Common) -> Result<(Repo, Composition), Failure> {
    let repo = Repo::at(&common.repo);

    let (tree, version) = match &common.fragments {
        Some(directory) => (
            FragmentSet::from_dir(directory).map_err(agentcfg::Error::from)?,
            LOCAL,
        ),
        None => (
            FragmentSet::embedded().map_err(agentcfg::Error::from)?,
            VERSION,
        ),
    };

    let composed = Composition::of(&repo, &tree, version)?;

    // A local fragment directory is not pinned by any release, so the pin
    // cannot be expected to match; say so rather than refusing to iterate.
    if composed.profile.config_version != VERSION {
        if version == LOCAL {
            eprintln!(
                "note: composing from {} — the `config_version: {}` pin is not what produced this",
                common
                    .fragments
                    .as_ref()
                    .map_or_else(String::new, |path| path.display().to_string()),
                composed.profile.config_version
            );
        } else {
            return Err(Failure::VersionMismatch {
                pinned: composed.profile.config_version.clone(),
                running: VERSION.to_owned(),
            });
        }
    }

    Ok((repo, composed))
}

fn render(plan: &Plan, format: Format) -> String {
    match format {
        Format::Text => render_text(plan),
        Format::Markdown => render_markdown(plan),
    }
}

fn render_text(plan: &Plan) -> String {
    let mut out = String::new();
    for change in plan.pending() {
        out.push_str(&format!("  {:<7} {}\n", verb(change), change.path));
    }
    if !out.is_empty() {
        out.push('\n');
    }
    out.push_str(&summary(plan, "Would write", "Already up to date."));
    out.push('\n');
    out
}

fn render_markdown(plan: &Plan) -> String {
    if plan.is_clean() {
        return "Already up to date.\n".to_owned();
    }

    let mut out = String::from("| Change | File |\n| --- | --- |\n");
    for change in plan.pending() {
        out.push_str(&format!("| {} | `{}` |\n", verb(change), change.path));
    }
    out.push_str(&format!("\n{}\n", summary(plan, "Would write", "")));
    out
}

/// One line saying how much moved, and how much did not.
fn summary(plan: &Plan, acted: &str, idle: &str) -> String {
    let (mut written, mut deleted) = (0, 0);
    for change in plan.pending() {
        match change.kind {
            ChangeKind::Deleted => deleted += 1,
            _ => written += 1,
        }
    }

    if written == 0 && deleted == 0 {
        return idle.to_owned();
    }

    let unchanged = plan.changes().len() - written - deleted;
    let mut parts = vec![format!("{acted} {written} file{}", plural(written))];
    if deleted > 0 {
        parts.push(format!("removed {deleted}"));
    }
    if unchanged > 0 {
        parts.push(format!("{unchanged} already current"));
    }

    format!("{}.", parts.join(", "))
}

fn verb(change: &Change) -> &'static str {
    match change.kind {
        ChangeKind::Created => "create",
        ChangeKind::Updated => "update",
        ChangeKind::Deleted => "delete",
        ChangeKind::Unchanged => "keep",
    }
}

fn plural(count: usize) -> &'static str {
    if count == 1 { "" } else { "s" }
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use agentcfg::{Composition, FragmentSet, Repo};

    use super::{Format, render, summary};

    /// A repository with a profile and nothing generated yet.
    fn sandbox() -> (tempfile::TempDir, Repo) {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join(".agentprofile.yml"),
            "config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\nemit: [agents-md]\n",
        )
        .unwrap();
        let repo = Repo::at(dir.path());
        (dir, repo)
    }

    fn compose(repo: &Repo) -> Composition {
        Composition::of(repo, &FragmentSet::embedded().unwrap(), "v1.0.0").unwrap()
    }

    #[test]
    fn a_fresh_repository_reads_as_a_list_of_creations() {
        let (_dir, repo) = sandbox();
        let rendered = render(&compose(&repo).plan, Format::Text);

        assert!(rendered.contains("  create  AGENTS.md\n"), "{rendered}");
        assert!(
            rendered.contains("  create  .agentcfg-manifest.json\n"),
            "{rendered}"
        );
        assert!(!rendered.contains("keep"), "unchanged files are noise here");
        assert!(rendered.trim_end().ends_with("files."), "{rendered}");
    }

    #[test]
    fn a_synced_repository_says_so_in_either_format() {
        let (_dir, repo) = sandbox();
        let composed = compose(&repo);
        repo.apply(&composed.plan).unwrap();

        let plan = compose(&repo).plan;
        assert!(plan.is_clean());
        assert_eq!(render(&plan, Format::Text), "Already up to date.\n");
        assert_eq!(render(&plan, Format::Markdown), "Already up to date.\n");
    }

    #[test]
    fn markdown_is_a_table_a_pull_request_can_hold() {
        let (_dir, repo) = sandbox();
        let rendered = render(&compose(&repo).plan, Format::Markdown);

        assert!(
            rendered.starts_with("| Change | File |\n| --- | --- |\n"),
            "{rendered}"
        );
        assert!(
            rendered.contains("| create | `AGENTS.md` |\n"),
            "{rendered}"
        );
    }

    #[test]
    fn the_summary_counts_what_moved_and_what_did_not() {
        let (_dir, repo) = sandbox();
        let composed = compose(&repo);
        repo.apply(&composed.plan).unwrap();

        // Hand-edit one file, so exactly one of many is pending.
        let agents_md = repo.root().join("AGENTS.md");
        let tampered = format!(
            "{}\n",
            std::fs::read_to_string(&agents_md)
                .unwrap()
                .replace("Git flow", "Git flowx")
        );
        std::fs::write(&agents_md, tampered).unwrap();

        let plan = compose(&repo).plan;
        let line = summary(&plan, "Would write", "Already up to date.");

        assert!(line.starts_with("Would write 1 file,"), "{line}");
        assert!(line.contains("already current"), "{line}");
        assert!(!line.contains("1 files"), "{line}");
    }
}
