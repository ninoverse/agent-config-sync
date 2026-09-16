//! The emitters a fragment can be rendered for.

use std::{fmt, str::FromStr};

/// One of the emitters `agentcfg` renders fragments for.
///
/// Fixed in code rather than discovered from the fragment tree, because an
/// emitter is a translation into one agent's file layout — a new agent is a new
/// emitter, never a new directory. Cursor is deliberately absent: it reads
/// AGENTS.md natively.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum EmitterName {
    /// `AGENTS.md` and the agent-neutral rule files beside it.
    AgentsMd,
    /// `CLAUDE.md`, `.claude/rules/`, `.claude/skills/` and `.claude/settings.json`.
    Claude,
}

impl EmitterName {
    /// Every emitter this version knows about.
    pub const ALL: [Self; 2] = [Self::AgentsMd, Self::Claude];

    /// The name written in an `emit:` list.
    ///
    /// ```
    /// use agentcfg::EmitterName;
    ///
    /// assert_eq!(EmitterName::AgentsMd.as_str(), "agents-md");
    /// ```
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::AgentsMd => "agents-md",
            Self::Claude => "claude",
        }
    }

    /// Every name, comma-separated — for listing the legal set in an error.
    fn all_names() -> String {
        Self::ALL
            .iter()
            .map(|emitter| emitter.as_str())
            .collect::<Vec<_>>()
            .join(", ")
    }
}

impl fmt::Display for EmitterName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// A name in an `emit:` list that is not an emitter this version knows.
///
/// A hard error rather than an empty selection: `emit: [agent-md]` must fail
/// loudly, never quietly render nothing.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error(
    "unknown emitter `{name}` — expected one of: {}",
    EmitterName::all_names()
)]
pub struct UnknownEmitter {
    /// The name that did not match.
    pub name: String,
}

impl FromStr for EmitterName {
    type Err = UnknownEmitter;

    /// ```
    /// use agentcfg::EmitterName;
    ///
    /// assert_eq!("claude".parse(), Ok(EmitterName::Claude));
    /// assert!("agent-md".parse::<EmitterName>().is_err());
    /// ```
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Self::ALL
            .into_iter()
            .find(|emitter| emitter.as_str() == s)
            .ok_or_else(|| UnknownEmitter { name: s.to_owned() })
    }
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    #[test]
    fn every_emitter_round_trips_through_its_name() {
        for emitter in EmitterName::ALL {
            assert_eq!(emitter.as_str().parse(), Ok(emitter));
        }
    }

    #[test]
    fn unknown_name_error_lists_the_legal_set() {
        let error = "agent-md".parse::<EmitterName>().unwrap_err();
        let rendered = error.to_string();
        for emitter in EmitterName::ALL {
            assert!(rendered.contains(emitter.as_str()), "{rendered}");
        }
    }
}
