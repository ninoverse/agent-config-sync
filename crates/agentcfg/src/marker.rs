//! The marker region: what a generated file owns, and what it leaves alone.
//!
//! Generated content sits between `<!-- agentcfg:start -->` and
//! `<!-- agentcfg:end -->`; anything outside survives regeneration untouched.
//! That is the escape hatch for genuinely repo-local content — the agent
//! template's measured MSRV rationale lives in one, beside the rule it
//! qualifies.
//!
//! A damaged region is a hard error rather than a best guess. The tool cannot
//! know where generated content was meant to end, and writing over a person's
//! prose because two markers were out of order is not a recoverable mistake.

use crate::error::RepoError;

/// Opens a generated region.
pub(crate) const START: &str = "<!-- agentcfg:start -->";
/// Closes one.
pub(crate) const END: &str = "<!-- agentcfg:end -->";

/// Replaces the marked region of `existing` with `generated`.
///
/// A file with no region yet keeps everything it has and gains one at the end.
/// A file that does not exist becomes the region alone.
pub(crate) fn splice(
    path: &str,
    existing: Option<&str>,
    generated: &str,
) -> Result<String, RepoError> {
    // No trailing newline: the text after the end marker already carries the
    // one that terminated it, and adding a second grows the file by a blank
    // line on every sync — which would mean `check` never reports clean.
    let region = format!("{START}\n{}\n{END}", generated.trim_end());

    let Some(existing) = existing else {
        return Ok(format!("{region}\n"));
    };

    match locate(path, existing)? {
        Some((before, after)) => Ok(format!("{before}{region}{after}")),
        // Not damaged, just unmanaged: keep what is there and append.
        None if existing.trim().is_empty() => Ok(format!("{region}\n")),
        None => Ok(format!("{}\n\n{region}\n", existing.trim_end())),
    }
}

/// Removes the markers, keeping everything between them.
///
/// `None` when the file carries no region, so there is nothing to strip.
pub(crate) fn strip(path: &str, existing: &str) -> Result<Option<String>, RepoError> {
    let Some((before, after)) = locate(path, existing)? else {
        return Ok(None);
    };

    let region = &existing[before.len() + START.len()..existing.len() - after.len() - END.len()];

    Ok(Some(format!(
        "{before}{}{after}",
        region.trim_matches('\n')
    )))
}

/// Everything outside the region: the text before the start marker and the text
/// after the end marker. `None` when the file carries no region.
pub(crate) fn outside<'a>(
    path: &str,
    existing: &'a str,
) -> Result<Option<(&'a str, &'a str)>, RepoError> {
    locate(path, existing)
}

/// Splits `text` around its region, rejecting anything ambiguous.
fn locate<'a>(path: &str, text: &'a str) -> Result<Option<(&'a str, &'a str)>, RepoError> {
    let starts = text.match_indices(START).count();
    let ends = text.match_indices(END).count();

    let damaged = |reason: &'static str| RepoError::DamagedRegion {
        path: path.to_owned(),
        reason,
    };

    match (starts, ends) {
        (0, 0) => return Ok(None),
        (1, 1) => {}
        (0, _) => return Err(damaged("an end marker with no start")),
        (_, 0) => return Err(damaged("a start marker with no end")),
        _ => {
            return Err(damaged(
                "more than one region, or one nested inside another",
            ));
        }
    }

    let start = text.find(START).ok_or_else(|| damaged("no start marker"))?;
    let end = text.find(END).ok_or_else(|| damaged("no end marker"))?;

    if end < start {
        return Err(damaged("the end marker comes before the start marker"));
    }

    Ok(Some((&text[..start], &text[end + END.len()..])))
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    fn splice_ok(existing: Option<&str>, generated: &str) -> String {
        splice("AGENTS.md", existing, generated).unwrap()
    }

    #[test]
    fn a_new_file_is_the_region_alone() {
        assert_eq!(
            splice_ok(None, "rules"),
            "<!-- agentcfg:start -->\nrules\n<!-- agentcfg:end -->\n"
        );
    }

    #[test]
    fn regenerating_replaces_the_region_and_nothing_else() {
        let existing = "Local preamble.\n\n<!-- agentcfg:start -->\nold\n<!-- agentcfg:end -->\n\nLocal note.\n";

        assert_eq!(
            splice_ok(Some(existing), "new"),
            "Local preamble.\n\n<!-- agentcfg:start -->\nnew\n<!-- agentcfg:end -->\n\nLocal note.\n"
        );
    }

    #[test]
    fn an_unmanaged_file_keeps_what_it_has() {
        // Not damaged — just a file the tool has not written to before.
        assert_eq!(
            splice_ok(Some("Hand-written.\n"), "rules"),
            "Hand-written.\n\n<!-- agentcfg:start -->\nrules\n<!-- agentcfg:end -->\n"
        );
    }

    #[test]
    fn an_empty_file_becomes_the_region() {
        assert_eq!(
            splice_ok(Some("   \n\n"), "rules"),
            splice_ok(None, "rules")
        );
    }

    #[test]
    fn a_damaged_region_is_refused_rather_than_guessed_at() {
        let cases = [
            ("<!-- agentcfg:start -->\nrules\n", "no end"),
            ("rules\n<!-- agentcfg:end -->\n", "no start"),
            (
                "<!-- agentcfg:start -->\na\n<!-- agentcfg:start -->\nb\n<!-- agentcfg:end -->\n",
                "nested",
            ),
            (
                "<!-- agentcfg:end -->\nrules\n<!-- agentcfg:start -->\n",
                "out of order",
            ),
        ];

        for (existing, why) in cases {
            let error = splice("AGENTS.md", Some(existing), "new").unwrap_err();
            assert!(
                matches!(error, RepoError::DamagedRegion { .. }),
                "{why}: {error}"
            );
            assert!(error.to_string().contains("AGENTS.md"), "{error}");
        }
    }

    #[test]
    fn splicing_the_same_content_twice_changes_nothing() {
        // The property `check` rests on: if this were not idempotent, every
        // sync would report drift against the sync before it.
        let once = splice_ok(None, "rules");
        let twice = splice_ok(Some(&once), "rules");

        assert_eq!(once, twice);
        assert_eq!(splice_ok(Some(&twice), "rules"), twice);
    }

    #[test]
    fn stripping_leaves_the_content_and_takes_the_markers() {
        let managed = splice_ok(Some("Local note.\n"), "the rules");

        assert_eq!(
            strip("AGENTS.md", &managed).unwrap(),
            Some("Local note.\n\nthe rules\n".to_owned())
        );
        // A file that was never managed has nothing to strip.
        assert_eq!(strip("AGENTS.md", "plain\n").unwrap(), None);
    }

    #[test]
    fn what_sits_outside_the_region_can_be_read_back() {
        let existing = "before\n<!-- agentcfg:start -->\nx\n<!-- agentcfg:end -->\nafter\n";

        assert_eq!(
            outside("AGENTS.md", existing).unwrap(),
            Some(("before\n", "\nafter\n"))
        );
        assert_eq!(outside("AGENTS.md", "plain\n").unwrap(), None);
    }
}
