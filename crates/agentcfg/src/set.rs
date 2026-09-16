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

    /// Builds a set from explicit tables, for tests that need a tree the
    /// real `fragments/` does not contain.
    /// The fragments in `directory`, read at run time rather than compiled in.
    ///
    /// This is `--fragments`, for iterating on fragments without cutting a
    /// release. What it composes is therefore not pinned by any
    /// `config_version`, so provenance says `local` rather than a version.
    ///
    /// # Errors
    ///
    /// [`FragmentError`] if the directory cannot be read or a fragment in it
    /// does not parse.
    pub fn from_dir(directory: &std::path::Path) -> Result<Self, FragmentError> {
        let mut files = Vec::new();
        collect(directory, directory, &mut files)?;
        files.sort();

        // Axes come from the directory tree, not from the files inside it: an
        // axis value may legitimately ship none yet, as `sensitivity/none/`
        // does, and deriving from files would make it vanish.
        let mut axes: BTreeMap<String, Vec<String>> = BTreeMap::new();
        for axis in subdirectories(directory)? {
            let name = directory_name(&axis)?;
            if name == "core" {
                continue;
            }
            let mut values = Vec::new();
            for value in subdirectories(&axis)? {
                values.push(directory_name(&value)?);
            }
            values.sort();
            axes.insert(name, values);
        }

        let mut fragments = Vec::new();
        for (path, contents) in &files {
            if path.ends_with(".md") {
                fragments.push(Fragment::parse(path, contents)?);
            }
        }

        Ok(Self {
            fragments,
            files: files.into_iter().collect(),
            axes,
        })
    }

    pub(crate) fn build(
        files: &[(&str, &str)],
        axes: &[(&str, &[&str])],
    ) -> Result<Self, FragmentError> {
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

/// Every file under `dir`, as `(path relative to `root`, contents)`.
///
/// Dotfiles are skipped, as they are in the build script: a `.gitkeep` holding
/// an empty value directory open is not content.
fn collect(
    root: &std::path::Path,
    dir: &std::path::Path,
    out: &mut Vec<(String, String)>,
) -> Result<(), FragmentError> {
    let entries = std::fs::read_dir(dir).map_err(io_error(dir))?;
    for entry in entries {
        let entry = entry.map_err(io_error(dir))?;
        let path = entry.path();

        if entry.file_type().map_err(io_error(&path))?.is_dir() {
            collect(root, &path, out)?;
        } else if !entry.file_name().to_string_lossy().starts_with('.') {
            let relative = path
                .strip_prefix(root)
                .map_err(|_| FragmentError::Io {
                    path: path.display().to_string(),
                    source: std::io::Error::new(
                        std::io::ErrorKind::InvalidInput,
                        "not inside the fragments directory",
                    ),
                })?
                .display()
                .to_string()
                .replace('\\', "/");
            out.push((
                relative,
                std::fs::read_to_string(&path).map_err(io_error(&path))?,
            ));
        }
    }

    Ok(())
}

/// The immediate subdirectories of `dir`, sorted.
fn subdirectories(dir: &std::path::Path) -> Result<Vec<std::path::PathBuf>, FragmentError> {
    let mut found = Vec::new();
    for entry in std::fs::read_dir(dir).map_err(io_error(dir))? {
        let entry = entry.map_err(io_error(dir))?;
        if entry.file_type().map_err(io_error(&entry.path()))?.is_dir() {
            found.push(entry.path());
        }
    }
    found.sort();
    Ok(found)
}

/// A directory's own name.
fn directory_name(dir: &std::path::Path) -> Result<String, FragmentError> {
    dir.file_name()
        .and_then(|name| name.to_str())
        .map(str::to_owned)
        .ok_or_else(|| FragmentError::Io {
            path: dir.display().to_string(),
            source: std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "directory name is not valid UTF-8",
            ),
        })
}

/// Binds `path` into an IO error constructor.
fn io_error(path: &std::path::Path) -> impl FnOnce(std::io::Error) -> FragmentError {
    let path = path.display().to_string();
    move |source| FragmentError::Io { path, source }
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
        assert_eq!(
            axes,
            [
                "architecture",
                "concerns",
                "deployment",
                "language",
                "sensitivity"
            ]
        );
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
