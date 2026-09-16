//! The one substitution pass: `{{ name }}`, and nothing else.
//!
//! Deliberately hand-rolled rather than a templating engine, so that nobody
//! switches conditionals back on later. Substitution removes a real defect —
//! without it a core fragment has to say "run the repo's full gate command"
//! where it could say `just ci`, and vague guidance is worse guidance. Control
//! flow is the opposite: it would let a language fragment ask what the
//! deployment is, which is exactly the cross-axis coupling the single-axis
//! refactor bought. Wanting an `{% if %}` is the diagnosis that the content
//! belongs in another fragment.
//!
//! `\{{` writes a literal `{{`, which is what lets a fragment document
//! Renovate's own `\{{{newValue}}}` templates.

use std::collections::BTreeMap;

use crate::error::SelectionError;

/// The vocabulary the selected axis values declare.
pub(crate) type Variables = BTreeMap<String, String>;

/// Replaces every `{{ name }}` in `text` with its value.
///
/// An unresolved name is an error, never an empty string: silently emitting
/// "run" with nothing after it is the worst failure this system could have.
pub(crate) fn render(
    path: &str,
    text: &str,
    variables: &Variables,
) -> Result<String, SelectionError> {
    let mut out = String::with_capacity(text.len());
    let mut rest = text;

    loop {
        let Some(open) = rest.find("{{") else {
            out.push_str(rest);
            return Ok(out);
        };

        // A preceding backslash escapes the braces. The byte before `{{` is a
        // char boundary whenever it is an ASCII backslash, so this cannot split
        // a multi-byte character.
        if open > 0 && rest.as_bytes()[open - 1] == b'\\' {
            out.push_str(&rest[..open - 1]);
            out.push_str("{{");
            rest = &rest[open + 2..];
            continue;
        }

        out.push_str(&rest[..open]);
        let after = &rest[open + 2..];

        let Some(close) = after.find("}}") else {
            return Err(SelectionError::UnclosedSubstitution {
                path: path.to_owned(),
            });
        };

        let name = after[..close].trim();
        let Some(value) = variables.get(name) else {
            return Err(SelectionError::UnresolvedVariable {
                path: path.to_owned(),
                name: name.to_owned(),
                available: variables.keys().cloned().collect(),
            });
        };

        out.push_str(value);
        rest = &after[close + 2..];
    }
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;

    fn variables() -> Variables {
        [
            ("unit".to_owned(), "crate".to_owned()),
            ("gate_command".to_owned(), "just ci".to_owned()),
        ]
        .into_iter()
        .collect()
    }

    fn render_ok(text: &str) -> String {
        render("core/example.md", text, &variables()).unwrap()
    }

    #[test]
    fn replaces_every_reference_in_the_text() {
        assert_eq!(
            render_ok("Run `{{ gate_command }}` before adding a {{ unit }}."),
            "Run `just ci` before adding a crate."
        );
    }

    #[test]
    fn text_without_references_passes_through_untouched() {
        assert_eq!(render_ok("Nothing to do here."), "Nothing to do here.");
        assert_eq!(render_ok(""), "");
    }

    #[test]
    fn a_reference_can_repeat_and_can_sit_at_either_end() {
        assert_eq!(render_ok("{{ unit }}"), "crate");
        assert_eq!(render_ok("{{ unit }}{{ unit }}"), "cratecrate");
        assert_eq!(render_ok("a {{ unit }} b {{ unit }}"), "a crate b crate");
    }

    #[test]
    fn whitespace_inside_the_braces_is_not_part_of_the_name() {
        assert_eq!(render_ok("{{unit}}"), "crate");
        assert_eq!(render_ok("{{   unit   }}"), "crate");
    }

    #[test]
    fn a_backslash_escapes_the_braces_and_is_itself_dropped() {
        assert_eq!(render_ok(r"\{{ unit }}"), "{{ unit }}");
        assert_eq!(render_ok(r"a \{{ unit }} b"), "a {{ unit }} b");
    }

    #[test]
    fn the_escape_carries_renovates_own_template_syntax() {
        // The real case the escape exists for: a fragment documenting
        // Renovate's `{{{newValue}}}`, which must survive verbatim.
        assert_eq!(render_ok(r"\{{{newValue}}}"), "{{{newValue}}}");
    }

    #[test]
    fn an_unresolved_name_is_an_error_not_an_empty_string() {
        let error = render("core/git-flow.md", "{{ unti }}", &variables()).unwrap_err();

        assert!(matches!(
            error,
            SelectionError::UnresolvedVariable { ref name, .. } if name == "unti"
        ));
        let rendered = error.to_string();
        assert!(rendered.contains("core/git-flow.md"), "{rendered}");
        assert!(rendered.contains("gate_command, unit"), "{rendered}");
    }

    #[test]
    fn an_unclosed_reference_is_an_error_rather_than_literal_text() {
        let error = render("core/example.md", "run {{ unit", &variables()).unwrap_err();

        assert!(matches!(error, SelectionError::UnclosedSubstitution { .. }));
    }

    #[test]
    fn substitution_does_not_recurse_into_what_it_produced() {
        let mut vars = variables();
        vars.insert("recursive".to_owned(), "{{ unit }}".to_owned());

        assert_eq!(
            render("core/example.md", "{{ recursive }}", &vars).unwrap(),
            "{{ unit }}"
        );
    }

    #[test]
    fn multi_byte_text_around_a_reference_survives() {
        assert_eq!(render_ok("→ {{ unit }} ←"), "→ crate ←");
        assert_eq!(render_ok(r"→ \{{ unit }} ←"), "→ {{ unit }} ←");
    }
}
