//! The whole fragment tree — parsed fragments, raw files, and the value listing.

use std::collections::BTreeMap;

use crate::{Fragment, error::FragmentError};

/// Every fragment `agentcfg` can select from, and the axis values they live in.
///
/// Markdown files are parsed into [`Fragment`]s. Everything else — a
/// `values.yml`, a `settings.partial.json` — is kept as raw text for the
/// consumer that understands it, because neither carries frontmatter.
#[derive(Debug, Clone)]
pub struct FragmentSet {
    fragments: Vec<Fragment>,
    files: BTreeMap<String, String>,
    axes: BTreeMap<String, Vec<String>>,
}

impl FragmentSet {
    /// The fragments compiled into this binary.
    ///
    /// # Errors
    ///
    /// [`FragmentError`] if a fragment in the tree this binary was built from
    /// does not parse. That is a committed-and-released bug rather than a user
    /// mistake, so it is worth failing loudly.
    ///
    /// ```
    /// use agentcfg::FragmentSet;
    ///
    /// let set = FragmentSet::embedded()?;
    /// assert_eq!(set.values("language"), ["go", "rust"]);
    ///
    /// // An axis with no directory yet has no legal values, so naming one is
    /// // an error rather than a silent pick.
    /// assert!(set.values("framework").is_empty());
    /// # Ok::<(), agentcfg::FragmentError>(())
    /// ```
    pub fn embedded() -> Result<Self, FragmentError> {
        Self::build(crate::embedded::FILES, crate::embedded::AXES)
    }

    fn build(files: &[(&str, &str)], axes: &[(&str, &[&str])]) -> Result<Self, FragmentError> {
        let mut fragments = Vec::new();
        for (path, contents) in files {
            if path.ends_with(".md") {
                fragments.push(Fragment::parse(path, contents)?);
            }
        }

        Ok(Self {
            fragments,
            files: files
                .iter()
                .map(|(path, contents)| ((*path).to_owned(), (*contents).to_owned()))
                .collect(),
            axes: axes
                .iter()
                .map(|(axis, values)| {
                    (
                        (*axis).to_owned(),
                        values.iter().map(|value| (*value).to_owned()).collect(),
                    )
                })
                .collect(),
        })
    }

    /// Every parsed fragment, ordered by path.
    #[must_use]
    pub fn fragments(&self) -> &[Fragment] {
        &self.fragments
    }

    /// The axes this release ships, each with its values.
    #[must_use]
    pub fn axes(&self) -> &BTreeMap<String, Vec<String>> {
        &self.axes
    }

    /// The values an axis offers, empty when the axis ships none yet.
    ///
    /// This is the *valid values are the directory listing* rule: a profile
    /// naming a value absent from here is a hard error, so `language: fsharp`
    /// becomes legal exactly when `language/fsharp/` ships in a release.
    #[must_use]
    pub fn values(&self, axis: &str) -> &[String] {
        self.axes.get(axis).map_or(&[], Vec::as_slice)
    }

    /// One file from the tree, by its path relative to `fragments/`.
    #[must_use]
    pub fn file(&self, path: &str) -> Option<&str> {
        self.files.get(path).map(String::as_str)
    }
}

#[cfg(test)]
mod tests {
    // Test code is exempt from the unwrap/expect ban; see .claude/code-review.md.
    #![allow(clippy::unwrap_used, clippy::expect_used)]

    use super::*;
    use crate::embedded;

    fn embedded_set() -> FragmentSet {
        FragmentSet::embedded().expect("every embedded fragment parses")
    }

    #[test]
    fn every_embedded_markdown_file_is_parsed_as_a_fragment() {
        let markdown = embedded::FILES
            .iter()
            .filter(|(path, _)| path.ends_with(".md"))
            .count();

        assert_eq!(embedded_set().fragments().len(), markdown);
        assert!(markdown > 0, "the embed found no fragments at all");
    }

    #[test]
    fn fragment_paths_are_unique() {
        let set = embedded_set();
        let mut paths: Vec<_> = set.fragments().iter().map(Fragment::path).collect();
        paths.sort_unstable();
        let total = paths.len();
        paths.dedup();
        assert_eq!(paths.len(), total);
    }

    #[test]
    fn the_axes_are_the_directory_listing_minus_core() {
        let set = embedded_set();
        let axes: Vec<_> = set.axes().keys().map(String::as_str).collect();

        // Adding an axis is the expensive change the plan guards; it should not
        // pass unnoticed. Adding a *value* is cheap, so values are not pinned
        // here beyond the two languages every core fragment substitutes from.
        assert_eq!(axes, ["architecture", "concerns", "deployment", "language"]);
        assert_eq!(set.values("language"), ["go", "rust"]);
        assert!(
            !set.axes().contains_key("core"),
            "core is not an axis — it has no values and is always included"
        );
    }

    #[test]
    fn non_markdown_files_are_kept_raw_rather_than_parsed() {
        let set = embedded_set();

        assert!(
            set.file("language/rust/values.yml")
                .unwrap()
                .contains("unit:")
        );
        assert!(
            set.file("language/rust/settings.partial.json")
                .unwrap()
                .contains("permissions")
        );
        assert!(
            !set.fragments()
                .iter()
                .any(|fragment| fragment.path().ends_with(".json")),
            "settings.partial.json carries no frontmatter and is not a fragment"
        );
    }

    #[test]
    fn an_unknown_file_is_absent_rather_than_empty() {
        assert!(embedded_set().file("language/fsharp/values.yml").is_none());
    }
}
