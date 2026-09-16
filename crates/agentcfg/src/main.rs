//! `agentcfg` — composes per-repo agent configuration from single-axis
//! fragments.
//!
//! Almost nobody types any of this. A repository meets `init` once, then
//! experiences the system as a Monday pull request and, on a bad day, a red
//! `check`. The command line is for authoring fragments and for the two moments
//! something goes wrong — which is why the error messages carry the polish
//! budget a wizard would otherwise have absorbed.

use std::{io::IsTerminal, io::Write, path::PathBuf, process::ExitCode};

use agentcfg::{
    Budget, Change, ChangeKind, Composition, EmitterName, FragmentSet, Meta, Plan, Repo, UnusedRule,
};
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
    /// Report drift and the always-on budget; exit non-zero if either is wrong.
    Check(Common),
    /// Print what sync would change, without changing it.
    Plan {
        #[command(flatten)]
        common: Common,
        /// How to render the result.
        #[arg(long, value_enum, default_value_t = Format::Text)]
        format: Format,
    },
    /// Name the fragment a rule comes from.
    Why {
        #[command(flatten)]
        common: Common,
        /// A phrase from the rule, as it appears in the composed files.
        #[arg(value_name = "PHRASE")]
        phrase: String,
    },
    /// Write a profile for a repository that does not have one.
    Init(Init),
    /// Stop managing this repository, keeping every composed file.
    ///
    /// The composed files stay where they are, as ordinary content with their
    /// markers stripped; the profile and the manifest are removed. Nothing is
    /// deleted.
    ///
    /// To remove the composed files instead, set `emit: []` in the profile and
    /// run `agentcfg sync`. That leaves the repository managed but generating
    /// nothing, so naming the emitters again brings every file back.
    Eject {
        /// The repository to release.
        #[arg(long, default_value = ".", value_name = "PATH")]
        repo: PathBuf,
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

#[derive(Args)]
struct Init {
    /// Where to write the profile.
    #[arg(long, default_value = ".", value_name = "PATH")]
    repo: PathBuf,
    /// Detected from `Cargo.toml` or `go.mod` when not given.
    #[arg(long, value_name = "NAME")]
    language: Option<String>,
    #[arg(long, value_name = "NAME")]
    framework: Option<String>,
    #[arg(long, value_name = "NAME")]
    architecture: Option<String>,
    /// What a merge to `main` does. There is nothing to detect this from.
    #[arg(long, value_name = "NAME")]
    deployment: Option<String>,
    /// Repeatable.
    #[arg(long = "concern", value_name = "NAME")]
    concerns: Vec<String>,
    #[arg(long, value_name = "NAME")]
    sensitivity: Option<String>,
    /// Repeatable. Defaults to every emitter.
    #[arg(long = "emit", value_name = "NAME")]
    emit: Vec<String>,
    /// Fail on a missing value rather than asking for it.
    #[arg(long)]
    non_interactive: bool,
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

    /// A repository that already has a profile.
    #[error("{0} already has a profile — edit it rather than starting over")]
    AlreadyInitialised(String),

    /// `init` needs a value it was not given and cannot ask for.
    #[error(
        "no {axis} given, and nothing to ask — pass `--{axis} <name>`. This release ships: {available}"
    )]
    Missing {
        /// The axis with no value.
        axis: &'static str,
        /// What could be chosen.
        available: String,
    },

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
        Ok(code) => code,
        Err(failure) => {
            eprintln!("error: {failure}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<ExitCode, Failure> {
    match Cli::parse().command {
        Command::Sync(common) => {
            let (repo, composed) = compose(&common)?;
            repo.apply(&composed.plan).map_err(agentcfg::Error::from)?;
            println!("{}", summary(&composed.plan, "Wrote", "Nothing to write."));
            Ok(ExitCode::SUCCESS)
        }
        Command::Plan { common, format } => {
            let (_, composed) = compose(&common)?;
            print!("{}", render(&composed.plan, format));
            Ok(ExitCode::SUCCESS)
        }
        Command::Check(common) => {
            let (repo, composed) = compose(&common)?;
            let budget = Budget::measure(&composed.files);

            for warning in
                agentcfg::unused_rules(&repo, &composed.selection).map_err(agentcfg::Error::from)?
            {
                eprintln!("warning: {}", describe(&warning));
            }

            print!("{}", check_report(&composed.plan, &budget));

            Ok(if composed.plan.is_clean() && !budget.is_over() {
                ExitCode::SUCCESS
            } else {
                ExitCode::FAILURE
            })
        }
        Command::Why { common, phrase } => {
            let (_, composed) = compose(&common)?;
            let found = why(&composed, &phrase);

            print!("{found}");

            // Nothing found is not an error, but it is worth a status, the way
            // a failed search is in any other tool.
            Ok(if found.is_empty() {
                println!("Nothing in this repository's rules says that.");
                ExitCode::FAILURE
            } else {
                ExitCode::SUCCESS
            })
        }
        Command::Init(options) => {
            init(&options)?;
            Ok(ExitCode::SUCCESS)
        }
        Command::Eject { repo } => {
            let repo = Repo::at(repo);
            let freed = repo.eject().map_err(agentcfg::Error::from)?;

            println!("{}", released(freed.len()));
            Ok(ExitCode::SUCCESS)
        }
    }
}

/// What `eject` leaves behind, and the door it is not.
///
/// The two exits are easy to mistake for each other, and only one of them is
/// reversible by editing a line. Saying so here costs nothing and is the only
/// place the command line mentions the other.
fn released(count: usize) -> String {
    format!(
        "Released {count} file{}; they are ordinary content now, and the profile and manifest are gone.\n\
         Nothing was deleted. To remove the composed files instead, restore this and sync with `emit: []`.",
        plural(count)
    )
}

/// Which fragment says a thing, and where that lands.
///
/// The question centralising creates: a rule you disagree with is no longer a
/// file in your repository you can edit, it is one of twenty fragments composed
/// from six axes. This is the lookup that makes it traceable.
fn why(composed: &Composition, phrase: &str) -> String {
    let needle = phrase.to_lowercase();
    let mut out = String::new();

    for fragment in composed.selection.fragments() {
        let matches: Vec<&str> = fragment
            .body()
            .lines()
            .filter(|line| line.to_lowercase().contains(&needle))
            .collect();
        if matches.is_empty() {
            continue;
        }

        let title = match fragment.meta() {
            Meta::Rules(meta) => &meta.title,
            Meta::Task(meta) => &meta.title,
        };
        out.push_str(&format!("{} — {title}\n", fragment.path()));

        for file in &composed.files {
            if file
                .content
                .contains(&format!("<!-- {} · ", fragment.path()))
            {
                out.push_str(&format!("  in {}\n", file.path));
            }
        }
        if let Meta::Rules(meta) = fragment.meta() {
            if let Some(when) = &meta.when {
                out.push_str(&format!("  read when: {when}\n"));
            }
        }

        out.push('\n');
        for line in matches.iter().take(5) {
            out.push_str(&format!("  {}\n", line.trim()));
        }
        if matches.len() > 5 {
            out.push_str(&format!("  … and {} more lines\n", matches.len() - 5));
        }
        out.push('\n');
    }

    out
}

/// Writes a profile for a repository that does not have one.
///
/// Detects what it can and asks only for what is genuinely a choice — and only
/// when there is someone to ask. Flags always win, so an agent scaffolding a
/// repository from a template never sees a question.
fn init(options: &Init) -> Result<(), Failure> {
    let profile_path = options.repo.join(".agentprofile.yml");
    if profile_path.exists() {
        return Err(Failure::AlreadyInitialised(
            profile_path.display().to_string(),
        ));
    }

    let tree = FragmentSet::embedded().map_err(agentcfg::Error::from)?;

    let language = match &options.language {
        Some(given) => given.clone(),
        None => match detect(&options.repo) {
            Some(detected) => detected,
            None => ask("language", &tree, options.non_interactive)?,
        },
    };
    let deployment = match &options.deployment {
        Some(given) => given.clone(),
        None => ask("deployment", &tree, options.non_interactive)?,
    };

    let emit = if options.emit.is_empty() {
        EmitterName::ALL
            .iter()
            .map(|emitter| emitter.as_str().to_owned())
            .collect()
    } else {
        options.emit.clone()
    };

    let mut yaml = format!("config_version: {VERSION}\nlanguage: {language}\n");
    if let Some(framework) = &options.framework {
        yaml.push_str(&format!("framework: {framework}\n"));
    }
    if let Some(architecture) = &options.architecture {
        yaml.push_str(&format!("architecture: {architecture}\n"));
    }
    yaml.push_str(&format!("deployment: {deployment}\n"));
    if !options.concerns.is_empty() {
        yaml.push_str(&format!("concerns: [{}]\n", options.concerns.join(", ")));
    }
    if let Some(sensitivity) = &options.sensitivity {
        yaml.push_str(&format!("sensitivity: {sensitivity}\n"));
    }
    yaml.push_str(&format!("emit: [{}]\n", emit.join(", ")));

    // Validated by the same parser every other command uses, so `init` cannot
    // write a profile that `sync` would then reject.
    agentcfg::Profile::parse(&yaml, &tree).map_err(agentcfg::Error::from)?;

    std::fs::write(&profile_path, &yaml).map_err(|source| {
        agentcfg::Error::from(agentcfg::RepoError::Io {
            path: profile_path.display().to_string(),
            source,
        })
    })?;

    println!("Wrote {}:\n\n{yaml}", profile_path.display());
    println!("Run `agentcfg sync` to compose it.");
    Ok(())
}

/// The language a repository is obviously written in, if it is obvious.
fn detect(repo: &std::path::Path) -> Option<String> {
    for (marker, language) in [("Cargo.toml", "rust"), ("go.mod", "go")] {
        if repo.join(marker).exists() {
            return Some(language.to_owned());
        }
    }
    None
}

/// Asks for a value, but only when there is a terminal to ask at.
///
/// A tool that prompts cannot run in a workflow, and the workflow is the
/// primary caller — so this is the single exception, and `--non-interactive`
/// removes even that.
fn ask(axis: &'static str, tree: &FragmentSet, non_interactive: bool) -> Result<String, Failure> {
    let available = tree.values(axis).join(", ");

    if non_interactive || !std::io::stdin().is_terminal() {
        return Err(Failure::Missing { axis, available });
    }

    loop {
        print!("{axis} ({available}): ");
        let _ = std::io::stdout().flush();

        let mut answer = String::new();
        if std::io::stdin().read_line(&mut answer).is_err() {
            return Err(Failure::Missing { axis, available });
        }

        let answer = answer.trim().to_owned();
        if tree.values(axis).contains(&answer) {
            return Ok(answer);
        }
        if answer.is_empty() {
            return Err(Failure::Missing { axis, available });
        }
        eprintln!("`{answer}` is not one of: {available}");
    }
}

/// A rule nothing in this repository would ever trigger./// A rule nothing in this repository would ever trigger.
fn describe(warning: &UnusedRule) -> String {
    format!(
        "{} will never load here — nothing matches {}. Either the rule does not apply to this repository, or its code lives somewhere unexpected.",
        warning.title,
        warning
            .globs
            .iter()
            .map(|glob| format!("`{glob}`"))
            .collect::<Vec<_>>()
            .join(" or ")
    )
}

/// What `check` found, and what to do about it.
///
/// A drift failure names the files and the one command that fixes them; a
/// budget failure lists the always-on set largest first, so the thing to move
/// behind `scope: paths` is the first line read.
fn check_report(plan: &Plan, budget: &Budget) -> String {
    let mut out = String::new();

    if !plan.is_clean() {
        let count = plan.pending().count();
        out.push_str(&format!(
            "{count} generated file{} out of date:\n\n",
            if count == 1 { " is" } else { "s are" }
        ));
        for change in plan.pending() {
            out.push_str(&format!("  {:<7} {}\n", verb(change), change.path));
        }
        out.push_str("\nRun `agentcfg sync` to bring them back in line.\n");
    }

    if budget.is_over() {
        if !out.is_empty() {
            out.push('\n');
        }
        out.push_str(&format!(
            "The always-on set is {} lines, over the {}-line budget:\n\n",
            budget.total(),
            budget.limit()
        ));
        for entry in budget.entries() {
            out.push_str(&format!("  {:>4}  {}\n", entry.lines, entry.source));
        }
        out.push_str("\nMove the largest behind `scope: paths`. Deleting a rule is not the fix.\n");
    } else if out.is_empty() {
        out.push_str(&format!(
            "Up to date. Always-on set: {} of {} lines.\n",
            budget.total(),
            budget.limit()
        ));
    } else {
        out.push_str(&format!(
            "\nAlways-on set: {} of {} lines.\n",
            budget.total(),
            budget.limit()
        ));
    }

    out
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

    use agentcfg::Budget;

    use super::{Format, check_report, render, summary};

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
    fn ejecting_says_what_it_did_not_do() {
        // `eject` and `emit: []` are easy to mistake for each other, and the
        // command line mentions the second nowhere else.
        let message = super::released(18);

        assert!(message.contains("Released 18 files"), "{message}");
        assert!(message.contains("Nothing was deleted"), "{message}");
        assert!(message.contains("`emit: []`"), "{message}");
    }

    #[test]
    fn why_names_the_fragment_and_where_it_lands() {
        let (_dir, repo) = sandbox();
        let composed = compose(&repo);

        let found = super::why(&composed, "no stacked PRs");

        assert!(found.contains("core/git-flow.md — Git flow"), "{found}");
        assert!(found.contains("in .agents/git-flow.md"), "{found}");
        assert!(
            found.contains("read when: Any change that ends in a PR"),
            "{found}"
        );
    }

    #[test]
    fn why_is_case_insensitive_and_finds_every_fragment_that_says_it() {
        let (_dir, repo) = sandbox();
        let composed = compose(&repo);

        let found = super::why(&composed, "NO STACKED prs");

        // Git flow states it; execution order repeats it as a consequence.
        assert!(found.contains("core/git-flow.md"), "{found}");
        assert!(found.contains("core/execution-order.md"), "{found}");
    }

    #[test]
    fn why_says_nothing_when_nothing_says_it() {
        let (_dir, repo) = sandbox();

        assert!(super::why(&compose(&repo), "kubernetes operator").is_empty());
    }

    #[test]
    fn the_language_is_detected_from_the_file_that_makes_it_obvious() {
        let dir = tempfile::tempdir().unwrap();
        assert_eq!(super::detect(dir.path()), None);

        std::fs::write(dir.path().join("go.mod"), "module x\n").unwrap();
        assert_eq!(super::detect(dir.path()).as_deref(), Some("go"));

        // Cargo.toml wins where both exist, which only happens in a repository
        // that would have to say which it is anyway.
        std::fs::write(dir.path().join("Cargo.toml"), "[package]\n").unwrap();
        assert_eq!(super::detect(dir.path()).as_deref(), Some("rust"));
    }

    #[test]
    fn a_clean_repository_still_reports_what_it_spends() {
        // `check` reports the always-on size whether or not it is over: a number
        // nobody sees until it fails is a number nobody has a feel for.
        let (_dir, repo) = sandbox();
        let composed = compose(&repo);
        repo.apply(&composed.plan).unwrap();

        let composed = compose(&repo);
        let budget = Budget::measure(&composed.files);
        let report = check_report(&composed.plan, &budget);

        assert!(
            report.starts_with("Up to date. Always-on set: "),
            "{report}"
        );
        assert!(
            report.contains(&format!("of {} lines.", budget.limit())),
            "{report}"
        );
    }

    #[test]
    fn drift_names_the_files_and_the_one_command_that_fixes_them() {
        let (_dir, repo) = sandbox();
        let composed = compose(&repo);
        let budget = Budget::measure(&composed.files);
        let report = check_report(&composed.plan, &budget);

        assert!(
            report.contains("generated files are out of date:"),
            "{report}"
        );
        assert!(report.contains("  create  AGENTS.md\n"), "{report}");
        assert!(report.contains("Run `agentcfg sync`"), "{report}");
        // Still says what it spends, even while failing for another reason.
        assert!(report.contains("Always-on set:"), "{report}");
    }

    #[test]
    fn one_file_out_of_date_reads_as_one_file() {
        let (_dir, repo) = sandbox();
        let composed = compose(&repo);
        repo.apply(&composed.plan).unwrap();
        std::fs::write(repo.root().join("AGENTS.md"), "tampered\n").unwrap();

        let composed = compose(&repo);
        let budget = Budget::measure(&composed.files);
        let report = check_report(&composed.plan, &budget);

        assert!(
            report.starts_with("1 generated file is out of date:"),
            "{report}"
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
