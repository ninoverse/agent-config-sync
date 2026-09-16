//! The `agents-md` emitter — `AGENTS.md` and the rules beside it.
//!
//! AGENTS.md is the canonical artifact, not a fallback: if every other emitter
//! broke, 30-odd agents would still read this and nothing would be lost. So it
//! carries the always-on rules in full, and an index pointing at everything
//! else.
//!
//! The index exists because no agent offers glob scoping inside AGENTS.md, and
//! nested files are not a way out — implementations disagree on whether a
//! nested file supplements the parent or replaces it, Claude Code reads no
//! AGENTS.md at all, and a concern's scope is a glob spanning directories
//! rather than one directory a file could sit in. Root-level pointers are the
//! only strategy that works everywhere.

use super::{EmitInput, Emitter, EmitterName, OutputFile, Ownership, file_stem, receives};
use crate::{Fragment, Meta, Scope, error::EmitError};

/// Where the bodies an agent reads on demand live.
const RULES_DIR: &str = ".agents";

/// Names the index in its provenance comment, so the always-on budget can
/// attribute its lines to something other than the fragment above it.
pub(crate) const INDEX: &str = "agentcfg:index";

/// Writes `AGENTS.md` and one file per rule that is not always-on.
///
/// ```
/// use agentcfg::{AgentsMd, EmitInput, Emitter, FragmentSet, Profile, Selection};
///
/// let tree = FragmentSet::embedded()?;
/// let profile = Profile::parse(
///     "\
/// config_version: v1.0.0
/// language: go
/// deployment: service
/// concerns: [template]
/// emit: [agents-md]
/// ",
///     &tree,
/// )?;
/// let selection = Selection::resolve(&profile, &tree)?;
///
/// let files = AgentsMd.emit(EmitInput {
///     selection: &selection,
///     profile: &profile,
///     tree: &tree,
///     version: "v1.0.0",
/// })?;
///
/// // AGENTS.md leads, carrying the always-on rules and the index.
/// assert_eq!(files[0].path, "AGENTS.md");
/// assert!(files[0].content.contains("make ci"));
/// assert!(files[0].content.contains("[Git flow](.agents/git-flow.md)"));
///
/// // Each rule an agent reads on demand gets its own file.
/// assert!(files.iter().any(|file| file.path == ".agents/git-flow.md"));
/// # Ok::<(), Box<dyn std::error::Error>>(())
/// ```
#[derive(Debug, Clone, Copy, Default)]
pub struct AgentsMd;

impl Emitter for AgentsMd {
    fn name(&self) -> EmitterName {
        EmitterName::AgentsMd
    }

    fn files(&self, input: EmitInput<'_>) -> Result<Vec<OutputFile>, EmitError> {
        let selected: Vec<&Fragment> = input
            .selection
            .fragments()
            .iter()
            .filter(|fragment| receives(EmitterName::AgentsMd, fragment))
            .collect();

        let mut blocks = Vec::new();
        let mut activities: Vec<(String, Vec<String>)> = Vec::new();
        let mut by_file = Vec::new();
        let mut files = Vec::new();

        for fragment in selected {
            let block = block(fragment, input.version);

            match fragment.meta() {
                Meta::Rules(meta) if meta.scope == Scope::Always => {
                    blocks.push(block);
                    continue;
                }
                Meta::Rules(meta) if meta.scope == Scope::Paths => {
                    by_file.push(format!(
                        "- {} — before touching {}",
                        link(fragment, &meta.title),
                        // Globs are alternatives: any one of them fires the rule.
                        join(
                            &meta
                                .paths
                                .iter()
                                .map(|glob| format!("`{glob}`"))
                                .collect::<Vec<_>>(),
                            "or",
                        )
                    ));
                }
                Meta::Rules(meta) => index(
                    &mut activities,
                    meta.when.as_deref(),
                    link(fragment, &meta.title),
                ),
                Meta::Task(meta) => index(
                    &mut activities,
                    Some(&meta.when),
                    link(fragment, &meta.title),
                ),
            }

            files.push(OutputFile {
                path: format!("{RULES_DIR}/{}.md", file_stem(fragment)),
                content: block,
                ownership: Ownership::Region,
            });
        }

        blocks.extend(extended_rules(&activities, &by_file, input.version));
        files.insert(
            0,
            OutputFile {
                path: "AGENTS.md".to_owned(),
                content: blocks.join("\n"),
                ownership: Ownership::Region,
            },
        );

        Ok(files)
    }
}

/// One emitted span: where it came from, its heading, and its body.
///
/// The provenance comment is what turns a rule you disagree with back into a
/// file you can edit — without it, a rule is one of twenty-one fragments
/// composed from six axes, with nothing in the repo saying which.
fn block(fragment: &Fragment, version: &str) -> String {
    let title = match fragment.meta() {
        Meta::Rules(meta) => &meta.title,
        Meta::Task(meta) => &meta.title,
    };

    format!(
        "<!-- {} · {} -->\n# {}\n\n{}\n",
        fragment.path(),
        version,
        title,
        fragment.body()
    )
}

/// A markdown link from `AGENTS.md` to a fragment's own file.
fn link(fragment: &Fragment, title: &str) -> String {
    format!("[{title}]({RULES_DIR}/{}.md)", file_stem(fragment))
}

/// Files an agent reads for one activity share that activity's index line.
fn index(activities: &mut Vec<(String, Vec<String>)>, when: Option<&str>, link: String) {
    let when = when.unwrap_or_default().to_owned();

    match activities.iter_mut().find(|(seen, _)| *seen == when) {
        Some((_, links)) => links.push(link),
        None => activities.push((when, vec![link])),
    }
}

/// The index that replaces the hand-written *Extended Rules* list.
fn extended_rules(
    activities: &[(String, Vec<String>)],
    by_file: &[String],
    version: &str,
) -> Option<String> {
    if activities.is_empty() && by_file.is_empty() {
        return None;
    }

    let mut out = format!(
        "<!-- {INDEX} · {version} -->\n# Extended rules\n\nRead these when they apply; they are not loaded by default.\n"
    );

    if !activities.is_empty() {
        out.push_str("\n**By activity:**\n\n");
        for (when, links) in activities {
            out.push_str(&format!("- **{when}:** {}\n", join(links, "and")));
        }
    }

    if !by_file.is_empty() {
        out.push_str("\n**By file:**\n\n");
        out.push_str(&by_file.join("\n"));
        out.push('\n');
    }

    Some(out)
}

/// `a`, `a <last> b`, `a, b <last> c`.
fn join(items: &[String], conjunction: &str) -> String {
    match items {
        [] => String::new(),
        [only] => only.clone(),
        [rest @ .., last] => format!("{} {conjunction} {last}", rest.join(", ")),
    }
}
