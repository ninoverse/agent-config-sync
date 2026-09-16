//! What the `agents-md` emitter writes, for the profiles that actually exist.
//!
//! Structural rather than golden: the byte-for-byte fixtures arrive with the
//! `sync` command, which is what compares them. These cover the properties a
//! golden file would not make obvious — that every pointer resolves, that no
//! frontmatter leaks, and that the `emit:` filter is applied.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::collections::BTreeSet;

use agentcfg::{
    AgentsMd, EmitInput, Emitter, Fragment, FragmentSet, Meta, OutputFile, Ownership, Profile,
    Scope, Selection,
};

const VERSION: &str = "v9.9.9";

struct Rendered {
    tree: FragmentSet,
    selection: Selection,
    files: Vec<OutputFile>,
}

impl Rendered {
    fn of(axes: &str) -> Self {
        let tree = FragmentSet::embedded().unwrap();
        let profile = Profile::parse(
            &format!("config_version: v1.0.0\nemit: [agents-md, claude]\n{axes}"),
            &tree,
        )
        .unwrap();
        let selection = Selection::resolve(&profile, &tree).unwrap();
        let files = AgentsMd
            .emit(EmitInput {
                selection: &selection,
                profile: &profile,
                tree: &tree,
                version: VERSION,
            })
            .unwrap();

        Self {
            tree,
            selection,
            files,
        }
    }

    fn agents_md(&self) -> &str {
        let file = &self.files[0];
        assert_eq!(file.path, "AGENTS.md");
        &file.content
    }

    fn paths(&self) -> BTreeSet<&str> {
        self.files.iter().map(|file| file.path.as_str()).collect()
    }
}

/// `claude-mit-rust-template`, plus the axes that exercise every scope.
const FULL: &str = "language: rust\ndeployment: tag-only\narchitecture: ddd\nconcerns: [template, data-access, sync]\n";

/// Every `](...)` target in `content`.
fn links_in(content: &str) -> BTreeSet<String> {
    let mut found = BTreeSet::new();
    let mut rest = content;
    while let Some(open) = rest.find("](") {
        let after = &rest[open + 2..];
        let Some(close) = after.find(')') else { break };
        found.insert(after[..close].to_owned());
        rest = &after[close + 1..];
    }
    found
}

fn scope_of(fragment: &Fragment) -> Option<Scope> {
    match fragment.meta() {
        Meta::Rules(meta) => Some(meta.scope),
        Meta::Task(_) => None,
    }
}

#[test]
fn always_on_rules_are_inline_and_everything_else_is_a_pointer() {
    let rendered = Rendered::of(FULL);
    let agents_md = rendered.agents_md();

    for fragment in rendered.selection.fragments() {
        if fragment.path().starts_with("language/rust/automation") {
            continue; // claude-only; covered separately
        }

        let opening = fragment.body().lines().next().unwrap();
        if scope_of(fragment) == Some(Scope::Always) {
            assert!(
                agents_md.contains(opening),
                "{} should be inline",
                fragment.path()
            );
        } else {
            assert!(
                !agents_md.contains(opening),
                "{} should be a pointer, not a body",
                fragment.path()
            );
        }
    }
}

#[test]
fn every_pointer_resolves_and_every_file_is_pointed_at() {
    let rendered = Rendered::of(FULL);

    let linked = links_in(rendered.agents_md());
    let written: BTreeSet<String> = rendered
        .paths()
        .iter()
        .filter(|path| **path != "AGENTS.md")
        .map(|path| (*path).to_owned())
        .collect();

    assert_eq!(linked, written, "a pointer and its file must agree");
    assert!(!linked.is_empty());
}

#[test]
fn the_naming_rule_keeps_two_concerns_from_colliding() {
    let rendered = Rendered::of(FULL);
    let paths = rendered.paths();

    // Both source files are named `rules.md`; keying on the file stem alone
    // would land them on one file and lose one of them silently.
    assert!(paths.contains(".agents/data-access-rules.md"), "{paths:?}");
    assert!(paths.contains(".agents/sync-rules.md"), "{paths:?}");
    assert!(paths.contains(".agents/ddd-domain-model.md"), "{paths:?}");
    // core keeps its bare stem, and a task uses its skill name.
    assert!(paths.contains(".agents/git-flow.md"), "{paths:?}");
    assert!(paths.contains(".agents/new-crate.md"), "{paths:?}");
}

#[test]
fn every_block_carries_the_fragment_and_version_it_came_from() {
    let rendered = Rendered::of(FULL);

    for file in &rendered.files {
        let opening = file.content.lines().next().unwrap();
        assert!(opening.starts_with("<!-- "), "{}: {opening}", file.path);
        assert!(opening.ends_with(&format!(" · {VERSION} -->")), "{opening}");
    }

    assert!(
        rendered
            .agents_md()
            .contains("<!-- core/behavior.md · v9.9.9 -->")
    );
}

#[test]
fn no_frontmatter_reaches_the_output() {
    // A YAML block in AGENTS.md is not ignored; it is read as prose.
    let rendered = Rendered::of(FULL);

    for file in &rendered.files {
        assert!(!file.content.starts_with("---"), "{}", file.path);
        for line in file.content.lines() {
            assert!(
                !matches!(line, "scope: always" | "scope: on-demand" | "scope: paths"),
                "{}: {line}",
                file.path
            );
            assert!(!line.starts_with("invocation:"), "{}: {line}", file.path);
            assert!(!line.starts_with("argument-hint:"), "{}: {line}", file.path);
        }
    }
}

#[test]
fn a_claude_only_fragment_is_filtered_out() {
    let rendered = Rendered::of(FULL);

    let automation = rendered
        .selection
        .fragments()
        .iter()
        .find(|fragment| fragment.path() == "language/rust/automation.md")
        .expect("selection is emitter-agnostic");

    // It says formatting runs on edit because a Claude hook does it — true for
    // Claude Code, wrong for every agent reading AGENTS.md.
    let opening = automation.body().lines().next().unwrap();
    assert!(!rendered.agents_md().contains(opening));
    assert!(!rendered.paths().contains(".agents/rust-automation.md"));
}

#[test]
fn fragments_sharing_an_activity_share_one_index_line() {
    let rendered = Rendered::of(FULL);
    let agents_md = rendered.agents_md();

    let line = agents_md
        .lines()
        .find(|line| line.starts_with("- **Any change that ends in a PR:**"))
        .expect("git flow and the deployment rules share this trigger");

    assert!(line.contains("(.agents/git-flow.md)"), "{line}");
    assert!(line.contains("(.agents/tag-only-release.md)"), "{line}");
    assert_eq!(
        agents_md
            .matches("- **Any change that ends in a PR:**")
            .count(),
        1
    );
}

#[test]
fn a_path_scoped_rule_names_every_glob_that_fires_it() {
    let rendered = Rendered::of(FULL);

    let line = rendered
        .agents_md()
        .lines()
        .find(|line| line.contains("(.agents/ddd-repositories.md)"))
        .expect("the ddd repositories rule is path-scoped");

    assert!(line.contains("before touching"), "{line}");
    assert!(
        line.contains("`**/repository/**` or `**/infrastructure/**`"),
        "{line}"
    );
}

#[test]
fn every_markdown_file_is_spliced_rather_than_owned() {
    // The escape hatch: local content outside the markers survives. It is what
    // keeps the agent template's measured MSRV rationale alive next to the rule
    // it qualifies.
    for file in &Rendered::of(FULL).files {
        assert_eq!(file.ownership, Ownership::Region, "{}", file.path);
    }
}

#[test]
fn a_profile_without_optional_axes_still_composes() {
    let rendered = Rendered::of("language: go\ndeployment: service\n");

    assert!(rendered.agents_md().contains("make ci"));
    assert!(!rendered.agents_md().contains("**By file:**"));
    assert!(rendered.agents_md().contains("**By activity:**"));
    assert!(rendered.tree.values("language").contains(&"go".to_owned()));
}
