//! The per-repo profile — `.agentprofile.yml`.
//!
//! The entire footprint of this system in a consumer repository: the repo's
//! coordinate on each axis, the emitters it wants, and the release it is
//! pinned to. Every other file in the repo is generated.
//!
//! Cardinality is carried by the field types rather than checked by hand —
//! `language` is a `String` so exactly one is required, `architecture` is an
//! `Option` so none or one is allowed, `concerns` is a `Vec` so any number is.
//! Which values are legal is not in this file at all: it is the directory
//! listing the release shipped, so a value becomes available when its
//! directory does.

use serde::Deserialize;

use crate::{EmitterName, FragmentSet, error::ProfileError};

/// A repository's coordinate on each axis, plus the release it is pinned to.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Profile {
    /// The release tag whose fragments compose this repo, e.g. `v1.0.0`.
    ///
    /// Renovate's custom manager owns this line during a bump, which is why
    /// `sync` only ever reads the profile.
    pub config_version: String,
    /// Exactly one language.
    pub language: String,
    /// None or one framework.
    pub framework: Option<String>,
    /// None or one architecture. One, because two architectures can prescribe
    /// contradictory things in a way two concerns never do.
    pub architecture: Option<String>,
    /// Exactly one deployment.
    pub deployment: String,
    /// Any number of concerns, including none. Sorted, since concerns stack
    /// additively and the order they are written in should not change output.
    pub concerns: Vec<String>,
    /// Exactly one sensitivity, defaulting to `none`.
    pub sensitivity: String,
    /// The emitters this repo wants. Empty is meaningful: the manifest then
    /// deletes everything previously generated, which is the soft off-switch.
    pub emit: Vec<EmitterName>,
    /// Repo-local additions merged last into the generated
    /// `.claude/settings.json`.
    pub settings_extra: Option<serde_json::Map<String, serde_json::Value>>,
}

impl Profile {
    /// Parses a profile and validates every value against what `tree` ships.
    ///
    /// # Errors
    ///
    /// [`ProfileError`] when the YAML does not match the schema, when
    /// `config_version` is not a release tag, when an axis names a value this
    /// release does not ship, or when `emit:` names an unknown emitter.
    ///
    /// ```
    /// use agentcfg::{EmitterName, FragmentSet, Profile};
    ///
    /// let tree = FragmentSet::embedded()?;
    /// let profile = Profile::parse(
    ///     "\
    /// config_version: v1.0.0
    /// language: rust
    /// framework: ~
    /// deployment: tag-only
    /// concerns: [template]
    /// emit: [agents-md, claude]
    /// ",
    ///     &tree,
    /// )?;
    ///
    /// assert_eq!(profile.language, "rust");
    /// assert_eq!(profile.framework, None);
    /// assert_eq!(profile.sensitivity, "none");
    /// assert_eq!(profile.emit, [EmitterName::AgentsMd, EmitterName::Claude]);
    /// # Ok::<(), Box<dyn std::error::Error>>(())
    /// ```
    pub fn parse(text: &str, tree: &FragmentSet) -> Result<Self, ProfileError> {
        let raw: Raw =
            serde_yaml_ng::from_str(text).map_err(|source| ProfileError::Syntax { source })?;

        if !is_release_tag(&raw.config_version) {
            return Err(ProfileError::ConfigVersion {
                value: raw.config_version,
            });
        }

        let mut concerns = raw.concerns;
        concerns.sort();
        if let Some(pair) = concerns.windows(2).find(|pair| pair[0] == pair[1]) {
            return Err(ProfileError::DuplicateConcern {
                value: pair[0].clone(),
            });
        }
        for concern in &concerns {
            shipped(tree, "concern", concern.clone())?;
        }

        Ok(Self {
            config_version: raw.config_version,
            language: shipped(tree, "language", raw.language)?,
            framework: raw
                .framework
                .map(|value| shipped(tree, "framework", value))
                .transpose()?,
            architecture: raw
                .architecture
                .map(|value| shipped(tree, "architecture", value))
                .transpose()?,
            deployment: shipped(tree, "deployment", raw.deployment)?,
            concerns,
            sensitivity: shipped(tree, "sensitivity", raw.sensitivity)?,
            emit: emitters(raw.emit)?,
            settings_extra: raw.settings_extra,
        })
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Raw {
    config_version: String,
    language: String,
    #[serde(default)]
    framework: Option<String>,
    #[serde(default)]
    architecture: Option<String>,
    deployment: String,
    #[serde(default)]
    concerns: Vec<String>,
    #[serde(default = "default_sensitivity")]
    sensitivity: String,
    // No `default`: the plan's *emit has no implicit default*. Omitting the key
    // is a mistake; writing `emit: []` is a decision.
    emit: Vec<String>,
    #[serde(default)]
    settings_extra: Option<serde_json::Map<String, serde_json::Value>>,
}

fn default_sensitivity() -> String {
    "none".to_owned()
}

/// Whether `value` looks like a tag `bump-version.yml` would push.
fn is_release_tag(value: &str) -> bool {
    value.strip_prefix('v').is_some_and(|rest| {
        let mut parts = rest.split('.');
        let digits = |part: Option<&str>| {
            part.is_some_and(|part| !part.is_empty() && part.bytes().all(|b| b.is_ascii_digit()))
        };
        digits(parts.next())
            && digits(parts.next())
            && digits(parts.next())
            && parts.next().is_none()
    })
}

/// Checks one value against the listing, or reports what the axis does ship.
///
/// `axis` is the noun the message reads with — `concern`, not `concerns` — so
/// the directory is looked up by its plural.
fn shipped(tree: &FragmentSet, axis: &'static str, value: String) -> Result<String, ProfileError> {
    let directory = if axis == "concern" { "concerns" } else { axis };
    let available = tree.values(directory);

    if available.contains(&value) {
        Ok(value)
    } else {
        Err(ProfileError::UnknownValue {
            axis,
            value,
            available: available.to_vec(),
        })
    }
}

fn emitters(names: Vec<String>) -> Result<Vec<EmitterName>, ProfileError> {
    let emitters: Vec<EmitterName> = names
        .iter()
        .map(|name| {
            name.parse()
                .map_err(|source| ProfileError::UnknownEmitter { source })
        })
        .collect::<Result<_, _>>()?;

    if emitters.contains(&EmitterName::Claude) && !emitters.contains(&EmitterName::AgentsMd) {
        return Err(ProfileError::ClaudeNeedsAgentsMd);
    }

    Ok(emitters)
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .agents/rust-code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    /// The smallest profile that validates: every axis with a cardinality of
    /// one, plus the emitters, which have no default.
    const MINIMAL: &str = "\
config_version: v1.0.0
language: rust
deployment: tag-only
emit: [agents-md]
";

    fn tree() -> FragmentSet {
        FragmentSet::embedded().expect("every embedded fragment parses")
    }

    fn parse(text: &str) -> Result<Profile, ProfileError> {
        Profile::parse(text, &tree())
    }

    fn with(extra: &str) -> Result<Profile, ProfileError> {
        parse(&format!("{MINIMAL}{extra}"))
    }

    #[test]
    fn a_minimal_profile_defaults_the_optional_axes() {
        let profile = parse(MINIMAL).unwrap();

        assert_eq!(profile.config_version, "v1.0.0");
        assert_eq!(profile.language, "rust");
        assert_eq!(profile.deployment, "tag-only");
        assert_eq!(profile.framework, None);
        assert_eq!(profile.architecture, None);
        assert!(profile.concerns.is_empty());
        assert_eq!(profile.sensitivity, "none");
        assert_eq!(profile.emit, [EmitterName::AgentsMd]);
        assert_eq!(profile.settings_extra, None);
    }

    #[test]
    fn a_full_profile_carries_every_axis() {
        let profile =
            with("framework: ~\narchitecture: ddd\nconcerns: [template, sync]\n").unwrap();

        assert_eq!(profile.framework, None);
        assert_eq!(profile.architecture, Some("ddd".to_owned()));
        assert_eq!(profile.concerns, ["sync", "template"]);
    }

    #[test]
    fn concerns_are_sorted_so_the_order_written_cannot_change_output() {
        let one = with("concerns: [template, data-access, sync]\n").unwrap();
        let other = with("concerns: [sync, template, data-access]\n").unwrap();

        assert_eq!(one.concerns, other.concerns);
        assert_eq!(one.concerns, ["data-access", "sync", "template"]);
    }

    #[test]
    fn a_concern_listed_twice_is_rejected() {
        let error = with("concerns: [sync, sync]\n").unwrap_err();

        assert!(matches!(error, ProfileError::DuplicateConcern { .. }));
        assert!(error.to_string().contains("sync"), "{error}");
    }

    #[test]
    fn emit_has_no_implicit_default() {
        let error =
            parse("config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\n").unwrap_err();

        assert!(matches!(error, ProfileError::Syntax { .. }));
        assert!(
            error.to_string().contains("missing field `emit`"),
            "{error}"
        );
    }

    #[test]
    fn an_empty_emit_list_is_the_soft_off_switch_not_an_error() {
        let profile =
            parse("config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\nemit: []\n")
                .unwrap();

        assert!(profile.emit.is_empty());
    }

    #[test]
    fn claude_cannot_be_emitted_without_the_file_it_imports() {
        // CLAUDE.md is an `@AGENTS.md` import, and the AGENTS.md index is what
        // points Claude at the rules it reads on demand. Alone, it would import
        // a file nobody wrote.
        let error =
            parse("config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\nemit: [claude]\n")
                .unwrap_err();

        assert!(matches!(error, ProfileError::ClaudeNeedsAgentsMd));
        assert!(error.to_string().contains("agents-md"), "{error}");

        // Together they are fine, and so is agents-md alone.
        assert!(with("").is_ok());
        assert!(
            parse("config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\nemit: [agents-md, claude]\n")
                .is_ok()
        );
    }

    #[test]
    fn an_unknown_emitter_is_rejected_rather_than_wiping_the_output() {
        let error = parse(
            "config_version: v1.0.0\nlanguage: rust\ndeployment: tag-only\nemit: [agent-md]\n",
        )
        .unwrap_err();

        assert!(matches!(error, ProfileError::UnknownEmitter { .. }));
        assert!(error.to_string().contains("agents-md"), "{error}");
    }

    #[test]
    fn an_axis_with_a_cardinality_of_one_is_required() {
        for omitted in ["language", "deployment"] {
            let text: String = MINIMAL
                .lines()
                .filter(|line| !line.starts_with(omitted))
                .map(|line| format!("{line}\n"))
                .collect();

            let error = parse(&text).unwrap_err();
            assert!(error.to_string().contains(omitted), "{error}");
        }
    }

    #[test]
    fn an_unknown_key_is_rejected_rather_than_ignored() {
        let error = with("langauge: go\n").unwrap_err();

        assert!(matches!(error, ProfileError::Syntax { .. }));
        assert!(
            error.to_string().contains("unknown field `langauge`"),
            "{error}"
        );
    }

    #[test]
    fn a_value_this_release_does_not_ship_is_rejected_with_the_legal_set() {
        let error = parse(&MINIMAL.replace("language: rust", "language: fsharp")).unwrap_err();

        assert!(matches!(
            error,
            ProfileError::UnknownValue {
                axis: "language",
                ..
            }
        ));
        let rendered = error.to_string();
        assert!(rendered.contains("fsharp"), "{rendered}");
        assert!(rendered.contains("go, rust"), "{rendered}");
    }

    #[test]
    fn an_axis_shipping_no_values_yet_says_so() {
        let error = with("framework: axum\n").unwrap_err();

        assert!(matches!(
            error,
            ProfileError::UnknownValue {
                axis: "framework",
                ..
            }
        ));
        assert!(
            error.to_string().contains("no values for that axis yet"),
            "{error}"
        );
    }

    #[test]
    fn an_unknown_concern_names_the_axis_in_the_singular() {
        let error = with("concerns: [caching]\n").unwrap_err();

        assert!(matches!(
            error,
            ProfileError::UnknownValue {
                axis: "concern",
                ..
            }
        ));
        assert!(error.to_string().contains("unknown concern"), "{error}");
    }

    #[test]
    fn sensitivity_defaults_but_still_has_to_be_a_value_that_ships() {
        assert_eq!(with("sensitivity: none\n").unwrap().sensitivity, "none");

        let error = with("sensitivity: pii\n").unwrap_err();
        assert!(matches!(
            error,
            ProfileError::UnknownValue {
                axis: "sensitivity",
                ..
            }
        ));
    }

    #[test]
    fn config_version_has_to_be_a_release_tag() {
        for good in ["v0.0.0", "v1.0.0", "v0.5.0", "v10.20.30"] {
            let text = MINIMAL.replace("v1.0.0", good);
            assert!(parse(&text).is_ok(), "{good} should parse");
        }

        for bad in [
            "1.0.0", "v1.0", "v1.0.0.0", "latest", "v1.0.x", "v", "v1..0",
        ] {
            let text = MINIMAL.replace("v1.0.0", bad);
            let error = parse(&text).unwrap_err();
            assert!(
                matches!(error, ProfileError::ConfigVersion { .. }),
                "{bad} should be rejected, got: {error}"
            );
        }
    }

    #[test]
    fn settings_extra_is_a_mapping_merged_into_the_generated_settings() {
        let profile = with("settings_extra:\n  env:\n    RUST_LOG: debug\n").unwrap();
        let extra = profile.settings_extra.unwrap();

        assert_eq!(extra["env"]["RUST_LOG"], "debug");
    }

    #[test]
    fn settings_extra_that_is_not_a_mapping_is_rejected() {
        let error = with("settings_extra: [one, two]\n").unwrap_err();

        assert!(matches!(error, ProfileError::Syntax { .. }));
        assert!(error.to_string().contains("invalid type"), "{error}");
    }

    #[test]
    fn every_error_names_the_file_a_human_would_open() {
        let error = with("concerns: [caching]\n").unwrap_err();

        assert!(error.to_string().starts_with(".agentprofile.yml: "));
    }
}
