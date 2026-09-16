//! What the `claude` emitter writes, for the profiles that actually exist.
//!
//! The division of labour it encodes: anything Claude reads the same way every
//! other agent does arrives through the `@AGENTS.md` import and is not written
//! twice. What is written here is what only Claude has — rules that load from a
//! glob, skills invocable by name, and the settings file governing what Claude
//! may run unprompted.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::collections::BTreeSet;

use agentcfg::{
    AgentsMd, Claude, EmitInput, Emitter, FragmentSet, Meta, OutputFile, Ownership, Profile, Scope,
    Selection,
};

const VERSION: &str = "v9.9.9";

/// `claude-mit-rust-agent-template`'s shape, with the axes that reach every
/// branch of the emitter.
const FULL: &str =
    "language: rust\ndeployment: service\narchitecture: ddd\nconcerns: [template, data-access]\n";

struct Rendered {
    selection: Selection,
    files: Vec<OutputFile>,
    agents_md_files: Vec<OutputFile>,
}

impl Rendered {
    fn of(axes: &str) -> Self {
        Self::with(axes, "")
    }

    fn with(axes: &str, extra: &str) -> Self {
        let tree = FragmentSet::embedded().unwrap();
        let profile = Profile::parse(
            &format!("config_version: v1.0.0\nemit: [agents-md, claude]\n{axes}{extra}"),
            &tree,
        )
        .unwrap();
        let selection = Selection::resolve(&profile, &tree).unwrap();
        let input = EmitInput {
            selection: &selection,
            profile: &profile,
            tree: &tree,
            version: VERSION,
        };

        Self {
            files: Claude.emit(input).unwrap(),
            agents_md_files: AgentsMd.emit(input).unwrap(),
            selection,
        }
    }

    fn get(&self, path: &str) -> &OutputFile {
        self.files
            .iter()
            .find(|file| file.path == path)
            .unwrap_or_else(|| panic!("{path} was not written; got {:?}", self.paths()))
    }

    fn paths(&self) -> BTreeSet<&str> {
        self.files.iter().map(|file| file.path.as_str()).collect()
    }
}

#[test]
fn claude_md_is_an_import_plus_only_what_agents_md_never_received() {
    let rendered = Rendered::of(FULL);
    let claude_md = &rendered.get("CLAUDE.md").content;

    assert!(claude_md.contains("@AGENTS.md"));

    for fragment in rendered.selection.fragments() {
        let Meta::Rules(meta) = fragment.meta() else {
            continue;
        };
        if meta.scope != Scope::Always {
            continue;
        }

        let opening = fragment.body().lines().next().unwrap();
        let claude_only = fragment.path().ends_with("automation.md");

        assert_eq!(
            claude_md.contains(opening),
            claude_only,
            "{} is {}in CLAUDE.md",
            fragment.path(),
            if claude_only { "not " } else { "" }
        );
    }
}

#[test]
fn a_rule_claude_can_scope_natively_is_not_left_as_a_pointer() {
    let rendered = Rendered::of(FULL);
    let rule = rendered.get(".claude/rules/ddd-repositories.md");

    // Claude Code loads this when it reads a matching file. Every other agent
    // has to be told to go and read it.
    assert!(
        rule.content.starts_with(
            "---\npaths:\n  - \"**/repository/**\"\n  - \"**/infrastructure/**\"\n---\n"
        )
    );
    assert!(rule.content.contains(&format!(
        "<!-- architecture/ddd/repositories.md · {VERSION} -->"
    )));
}

#[test]
fn only_path_scoped_rules_become_rules_files() {
    let rendered = Rendered::of(FULL);

    let written: BTreeSet<String> = rendered
        .paths()
        .iter()
        .filter(|path| path.starts_with(".claude/rules/"))
        .map(|path| (*path).to_owned())
        .collect();

    let expected: BTreeSet<String> = rendered
        .selection
        .fragments()
        .iter()
        .filter(
            |fragment| matches!(fragment.meta(), Meta::Rules(meta) if meta.scope == Scope::Paths),
        )
        .map(|fragment| {
            let stem = fragment.path().split('/').nth(1).unwrap();
            let name = fragment
                .path()
                .rsplit('/')
                .next()
                .unwrap()
                .trim_end_matches(".md");
            format!(".claude/rules/{stem}-{name}.md")
        })
        .collect();

    assert_eq!(written, expected);
    assert!(!written.is_empty());
}

#[test]
fn a_path_scoped_body_is_written_for_both_agents_deliberately() {
    // One fragment, two renderings: Claude gets native frontmatter, everyone
    // else gets a pointer at a file with none. They cannot drift — both are
    // generated from the same fragment and both are checked.
    let rendered = Rendered::of(FULL);

    let claude = &rendered.get(".claude/rules/data-access-rules.md").content;
    let neutral = &rendered
        .agents_md_files
        .iter()
        .find(|file| file.path == ".agents/data-access-rules.md")
        .unwrap()
        .content;

    assert!(claude.starts_with("---\npaths:\n"));
    assert!(!neutral.starts_with("---"));
    assert!(claude.contains("# Data access"));
    assert!(neutral.contains("# Data access"));
}

#[test]
fn every_task_becomes_a_skill_and_never_a_command() {
    let rendered = Rendered::of(FULL);

    // Commands have been merged into skills, and a skill shadows a command of
    // the same name, so writing both has no correct rendering.
    assert!(
        !rendered
            .paths()
            .iter()
            .any(|path| path.starts_with(".claude/commands/"))
    );

    let skill = rendered.get(".claude/skills/new-crate/SKILL.md");
    assert!(skill.content.starts_with("---\nname: \"new-crate\"\n"));
    assert!(skill.content.contains("description: "));
    assert!(!skill.content.contains("disable-model-invocation"));
    assert!(skill.content.contains("# Adding a crate"));

    for fragment in rendered.selection.fragments() {
        if let Meta::Task(meta) = fragment.meta() {
            rendered.get(&format!(".claude/skills/{}/SKILL.md", meta.name));
        }
    }
}

#[test]
fn settings_are_composed_whole_from_the_partial_and_the_profile() {
    let rendered = Rendered::with(FULL, "settings_extra:\n  env:\n    RUST_LOG: debug\n");
    let settings = rendered.get(".claude/settings.json");

    assert_eq!(settings.ownership, Ownership::Whole);

    let parsed: serde_json::Value = serde_json::from_str(&settings.content).unwrap();
    assert_eq!(parsed["env"]["RUST_LOG"], "debug");
    // The language partial survives alongside it rather than being replaced.
    assert!(
        parsed["permissions"]["allow"]
            .as_array()
            .unwrap()
            .iter()
            .any(|entry| entry.as_str() == Some("Bash(just:*)"))
    );
    assert!(parsed["hooks"]["PostToolUse"].is_array());
    assert!(settings.content.ends_with("}\n"));
}

#[test]
fn the_language_decides_which_settings_partial_is_composed() {
    let go = Rendered::of("language: go\ndeployment: service\n");
    let parsed: serde_json::Value =
        serde_json::from_str(&go.get(".claude/settings.json").content).unwrap();

    let allow: Vec<&str> = parsed["permissions"]["allow"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(serde_json::Value::as_str)
        .collect();

    assert!(
        allow.iter().any(|entry| entry.starts_with("Bash(go ")),
        "{allow:?}"
    );
    assert!(
        !allow.iter().any(|entry| entry.contains("cargo")),
        "{allow:?}"
    );
}

#[test]
fn a_file_leading_with_generated_frontmatter_is_owned_outright() {
    // A marker comment cannot sit above frontmatter without breaking it, and
    // these files have no local content to protect. CLAUDE.md does.
    for file in &Rendered::of(FULL).files {
        let expected = if file.path == "CLAUDE.md" {
            Ownership::Region
        } else {
            Ownership::Whole
        };

        assert_eq!(file.ownership, expected, "{}", file.path);
        if expected == Ownership::Whole && file.path.ends_with(".md") {
            assert!(file.content.starts_with("---\n"), "{}", file.path);
        }
    }
}
