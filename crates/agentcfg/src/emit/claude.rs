//! The `claude` emitter — `CLAUDE.md`, `.claude/rules/`, `.claude/skills/` and
//! `.claude/settings.json`.
//!
//! Claude Code reads `CLAUDE.md` rather than `AGENTS.md`, so this emitter
//! writes the adapter the Claude Code docs themselves recommend: an
//! `@AGENTS.md` import, with anything genuinely Claude-specific below it. That
//! is why a profile cannot name `claude` without `agents-md` — there would be
//! nothing to import.
//!
//! Two things Claude does natively and nobody else does, so they are written
//! here rather than pointed at: a rule carrying `paths:` frontmatter loads when
//! Claude reads a matching file, and a skill is invocable by name. Both are
//! owned outright, because a marker comment cannot sit above the frontmatter
//! that makes them work.

use serde_json::{Map, Value};

use super::{EmitInput, Emitter, EmitterName, OutputFile, Ownership, file_stem, receives};
use crate::{Fragment, Invocation, Meta, Scope, error::EmitError};

/// Writes the Claude Code layout for a selection.
///
/// ```
/// use agentcfg::{Claude, EmitInput, Emitter, FragmentSet, Profile, Selection};
///
/// let tree = FragmentSet::embedded()?;
/// let profile = Profile::parse(
///     "\
/// config_version: v1.0.0
/// language: rust
/// deployment: tag-only
/// architecture: ddd
/// emit: [agents-md, claude]
/// ",
///     &tree,
/// )?;
/// let selection = Selection::resolve(&profile, &tree)?;
///
/// let files = Claude.emit(EmitInput {
///     selection: &selection,
///     profile: &profile,
///     tree: &tree,
///     version: "v1.0.0",
/// })?;
/// let wrote = |path: &str| files.iter().any(|file| file.path == path);
///
/// // An adapter, not a second copy of the rules.
/// assert!(files[0].path == "CLAUDE.md" && files[0].content.contains("@AGENTS.md"));
///
/// // What only Claude has: globs that load a rule, and skills.
/// assert!(wrote(".claude/rules/ddd-domain-model.md"));
/// assert!(wrote(".claude/skills/new-crate/SKILL.md"));
/// assert!(wrote(".claude/settings.json"));
///
/// // Commands have been merged into skills, so this directory is never written.
/// assert!(!files.iter().any(|file| file.path.starts_with(".claude/commands/")));
/// # Ok::<(), Box<dyn std::error::Error>>(())
/// ```
#[derive(Debug, Clone, Copy, Default)]
pub struct Claude;

impl Emitter for Claude {
    fn name(&self) -> EmitterName {
        EmitterName::Claude
    }

    fn files(&self, input: EmitInput<'_>) -> Result<Vec<OutputFile>, EmitError> {
        let mut claude_md = vec![format!(
            "<!-- agentcfg · {} — the rules live in AGENTS.md; this imports them. -->\n@AGENTS.md\n",
            input.version
        )];
        let mut files = Vec::new();

        for fragment in input.selection.fragments() {
            if !receives(EmitterName::Claude, fragment) {
                continue;
            }

            match fragment.meta() {
                Meta::Task(meta) => files.push(OutputFile {
                    path: format!(".claude/skills/{}/SKILL.md", file_stem(fragment)),
                    content: format!(
                        "{}\n{}",
                        skill_frontmatter(meta),
                        block(fragment, input.version)
                    ),
                    ownership: Ownership::Whole,
                }),
                Meta::Rules(meta) if meta.scope == Scope::Paths => files.push(OutputFile {
                    path: format!(".claude/rules/{}.md", file_stem(fragment)),
                    content: format!(
                        "{}\n{}",
                        paths_frontmatter(&meta.paths),
                        block(fragment, input.version)
                    ),
                    ownership: Ownership::Whole,
                }),
                // Everything else already reaches Claude through the AGENTS.md
                // import — unless AGENTS.md never received it.
                Meta::Rules(_) if receives(EmitterName::AgentsMd, fragment) => {}
                Meta::Rules(_) => claude_md.push(block(fragment, input.version)),
            }
        }

        files.insert(
            0,
            OutputFile {
                path: "CLAUDE.md".to_owned(),
                content: claude_md.join("\n"),
                ownership: Ownership::Region,
            },
        );

        if let Some(settings) = settings(input)? {
            files.push(settings);
        }

        Ok(files)
    }
}

/// One emitted span, below whatever frontmatter the file needs.
fn block(fragment: &Fragment, version: &str) -> String {
    let title = match fragment.meta() {
        Meta::Rules(meta) => &meta.title,
        Meta::Task(meta) => &meta.title,
    };

    // Claude Code strips block-level HTML comments before loading a file, so
    // provenance costs this reader nothing.
    format!(
        "<!-- {} · {} -->\n# {}\n\n{}\n",
        fragment.path(),
        version,
        title,
        fragment.body()
    )
}

/// The globs that load a rule, in Claude Code's own `paths:` syntax.
fn paths_frontmatter(paths: &[String]) -> String {
    let mut out = String::from("---\npaths:\n");
    for glob in paths {
        out.push_str(&format!("  - {}\n", scalar(glob)));
    }
    out.push_str("---\n");
    out
}

/// What makes a task fragment a skill.
fn skill_frontmatter(meta: &crate::TaskMeta) -> String {
    let mut out = format!(
        "---\nname: {}\ndescription: {}\n",
        scalar(&meta.name),
        scalar(&meta.description)
    );

    if let Some(hint) = &meta.argument_hint {
        out.push_str(&format!("argument-hint: {}\n", scalar(hint)));
    }
    if !meta.arguments.is_empty() {
        let named: Vec<String> = meta.arguments.iter().map(|name| scalar(name)).collect();
        out.push_str(&format!("arguments: [{}]\n", named.join(", ")));
    }
    if let Some(tools) = &meta.allowed_tools {
        out.push_str(&format!("allowed-tools: {}\n", scalar(tools)));
    }
    // A `user` skill's description never enters context, which is the whole
    // point of the flag — and why the budget does not count it.
    if meta.invocation == Invocation::User {
        out.push_str("disable-model-invocation: true\n");
    }

    out.push_str("---\n");
    out
}

/// `.claude/settings.json`, composed whole.
///
/// The emitter owns the file outright rather than merging into what is there:
/// JSON has no comment syntax, so it cannot carry a marker region, and a
/// merging emitter could never tell a key it wrote last month from one a person
/// added — which in the one file governing what Claude may run unprompted means
/// a permission dropped centrally could never be removed anywhere.
fn settings(input: EmitInput<'_>) -> Result<Option<OutputFile>, EmitError> {
    let mut settings = Map::new();

    for value in input.selection.values() {
        let path = format!("{value}/settings.partial.json");
        let Some(contents) = input.tree.file(&path) else {
            continue;
        };

        let partial: Map<String, Value> = serde_json::from_str(contents)
            .map_err(|source| EmitError::Settings { path, source })?;
        merge(&mut settings, &partial);
    }

    // Repo-local additions go in the profile, and land last.
    if let Some(extra) = &input.profile.settings_extra {
        merge(&mut settings, extra);
    }

    if settings.is_empty() {
        return Ok(None);
    }

    Ok(Some(OutputFile {
        path: ".claude/settings.json".to_owned(),
        content: format!(
            "{}\n",
            serde_json::to_string_pretty(&settings).map_err(|source| EmitError::Settings {
                path: ".claude/settings.json".to_owned(),
                source
            })?
        ),
        ownership: Ownership::Whole,
    }))
}

/// Deep-merges `extra` over `base`: objects combine, everything else replaces.
fn merge(base: &mut Map<String, Value>, extra: &Map<String, Value>) {
    for (key, value) in extra {
        match (base.get_mut(key), value) {
            (Some(Value::Object(existing)), Value::Object(incoming)) => merge(existing, incoming),
            _ => {
                base.insert(key.clone(), value.clone());
            }
        }
    }
}

/// A YAML scalar, always double-quoted so no value needs a quoting rule.
fn scalar(value: &str) -> String {
    format!("\"{}\"", value.replace('\\', r"\\").replace('"', "\\\""))
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;
    use crate::{Fragment, TaskMeta};

    fn task(frontmatter: &str) -> Fragment {
        Fragment::parse(
            "language/rust/tasks/new-unit.md",
            &format!("---\n{frontmatter}\n---\n\nBody.\n"),
        )
        .unwrap()
    }

    fn meta_of(fragment: &Fragment) -> &TaskMeta {
        match fragment.meta() {
            Meta::Task(meta) => meta,
            Meta::Rules(_) => unreachable!("parsed from a tasks/ path"),
        }
    }

    const MINIMAL_TASK: &str = "name: gates\ntitle: Merge gates\nwhen: Checking your work\ndescription: Run the merge gates";

    #[test]
    fn a_model_invocable_skill_carries_no_opt_out() {
        let fragment = task(MINIMAL_TASK);
        let rendered = skill_frontmatter(meta_of(&fragment));

        assert_eq!(
            rendered,
            "---\nname: \"gates\"\ndescription: \"Run the merge gates\"\n---\n"
        );
    }

    #[test]
    fn a_user_skill_opts_out_of_model_invocation() {
        // Its description then never enters context, which is why the budget
        // does not count it.
        let fragment = task(&format!("{MINIMAL_TASK}\ninvocation: user"));

        assert!(skill_frontmatter(meta_of(&fragment)).contains("disable-model-invocation: true\n"));
    }

    #[test]
    fn the_optional_skill_fields_pass_through() {
        let fragment = task(&format!(
            "{MINIMAL_TASK}\nargument-hint: \"[-p <crate>]\"\narguments: [name, kind]\nallowed-tools: Bash(just:*), Bash(cargo:*)"
        ));
        let rendered = skill_frontmatter(meta_of(&fragment));

        assert!(
            rendered.contains("argument-hint: \"[-p <crate>]\"\n"),
            "{rendered}"
        );
        assert!(
            rendered.contains("arguments: [\"name\", \"kind\"]\n"),
            "{rendered}"
        );
        assert!(
            rendered.contains("allowed-tools: \"Bash(just:*), Bash(cargo:*)\"\n"),
            "{rendered}"
        );
    }

    #[test]
    fn a_value_that_would_break_yaml_is_quoted_and_escaped() {
        assert_eq!(scalar("plain"), "\"plain\"");
        assert_eq!(scalar("has: colon"), "\"has: colon\"");
        assert_eq!(scalar(r#"a "quote""#), r#""a \"quote\"""#);
        assert_eq!(scalar(r"back\slash"), r#""back\\slash""#);
    }

    #[test]
    fn globs_render_as_a_block_sequence() {
        let rendered = paths_frontmatter(&["**/domain/**".to_owned(), "**/*.sql".to_owned()]);

        assert_eq!(
            rendered,
            "---\npaths:\n  - \"**/domain/**\"\n  - \"**/*.sql\"\n---\n"
        );
    }

    fn json(text: &str) -> Map<String, Value> {
        serde_json::from_str(text).unwrap()
    }

    #[test]
    fn merging_combines_objects_and_replaces_everything_else() {
        let mut base = json(r#"{"permissions": {"allow": ["a"], "deny": ["x"]}, "keep": 1}"#);
        merge(
            &mut base,
            &json(r#"{"permissions": {"allow": ["b"]}, "env": {"K": "v"}}"#),
        );

        // A sibling key inside a merged object survives.
        assert_eq!(base["permissions"]["deny"].to_string(), r#"["x"]"#);
        assert_eq!(base["keep"].to_string(), "1");
        // A new key arrives.
        assert_eq!(base["env"]["K"].to_string(), r#""v""#);
        // An array replaces rather than concatenating, so a repo can remove an
        // entry as well as add one.
        assert_eq!(base["permissions"]["allow"].to_string(), r#"["b"]"#);
    }

    #[test]
    fn the_partial_is_composed_before_the_profiles_own_additions() {
        let mut base = json(r#"{"env": {"A": "from-partial", "B": "kept"}}"#);
        merge(&mut base, &json(r#"{"env": {"A": "from-profile"}}"#));

        assert_eq!(base["env"]["A"].to_string(), r#""from-profile""#);
        assert_eq!(base["env"]["B"].to_string(), r#""kept""#);
    }
}
