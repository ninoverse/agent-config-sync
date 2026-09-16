//! Embeds `fragments/` into the binary at build time.
//!
//! The plan's *Embedded fragments* decision: one downloaded artifact is the
//! whole contract, so `config_version` pins content and code atomically and a
//! fragment edit requires a release. This script therefore emits two tables
//! into `OUT_DIR`:
//!
//! - `FILES` — every file under `fragments/`, keyed by its path relative to
//!   that directory, with contents pulled in by `include_str!`.
//! - `AXES` — the axis directories and the value directories inside them.
//!   This is the *valid values are the directory listing* rule: `language:
//!   fsharp` becomes legal the moment `language/fsharp/` ships, and is a hard
//!   error before that. Never a hand-written enum, which would make every new
//!   language a code change.
//!
//! `core/` is skipped in `AXES` because it is not an axis — it has no values
//! and is always included.

use std::{
    env,
    error::Error,
    fmt::Write as _,
    fs,
    path::{Path, PathBuf},
};

fn main() -> Result<(), Box<dyn Error>> {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR")?);
    let fragments = manifest_dir
        .ancestors()
        .nth(2)
        .ok_or("CARGO_MANIFEST_DIR is not two levels below the workspace root")?
        .join("fragments");

    println!("cargo::rerun-if-changed={}", display(&fragments)?);

    let mut files = Vec::new();
    collect_files(&fragments, &fragments, &mut files)?;
    files.sort();

    let mut generated = String::new();
    writeln!(generated, "pub(crate) static FILES: &[(&str, &str)] = &[")?;
    for (relative, absolute) in &files {
        let absolute = display(absolute)?;
        println!("cargo::rerun-if-changed={absolute}");
        writeln!(generated, "    ({relative:?}, include_str!({absolute:?})),")?;
    }
    writeln!(generated, "];")?;

    writeln!(
        generated,
        "\npub(crate) static AXES: &[(&str, &[&str])] = &["
    )?;
    for (axis, values) in axes(&fragments)? {
        write!(generated, "    ({axis:?}, &[")?;
        for value in values {
            write!(generated, "{value:?}, ")?;
        }
        writeln!(generated, "]),")?;
    }
    writeln!(generated, "];")?;

    let out = PathBuf::from(env::var("OUT_DIR")?).join("embedded.rs");
    fs::write(out, generated)?;
    Ok(())
}

/// An axis directory and the value directories inside it.
type Axis = (String, Vec<String>);

/// Every file under `dir`, as `(path relative to `root`, absolute path)`.
fn collect_files(
    root: &Path,
    dir: &Path,
    out: &mut Vec<(String, PathBuf)>,
) -> Result<(), Box<dyn Error>> {
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if entry.file_type()?.is_dir() {
            collect_files(root, &path, out)?;
        } else {
            out.push((display(path.strip_prefix(root)?)?, path));
        }
    }
    Ok(())
}

/// The axis directories under `fragments/`, each with its value directories.
fn axes(fragments: &Path) -> Result<Vec<Axis>, Box<dyn Error>> {
    let mut axes = Vec::new();
    for axis in subdirectories(fragments)? {
        let name = display(axis.strip_prefix(fragments)?)?;
        if name == "core" {
            continue;
        }
        let values = subdirectories(&axis)?
            .iter()
            .map(|value| display(value.strip_prefix(&axis)?))
            .collect::<Result<Vec<_>, _>>()?;
        axes.push((name, values));
    }
    axes.sort();
    Ok(axes)
}

/// The immediate subdirectories of `dir`, sorted.
fn subdirectories(dir: &Path) -> Result<Vec<PathBuf>, Box<dyn Error>> {
    let mut found = Vec::new();
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        if entry.file_type()?.is_dir() {
            found.push(entry.path());
        }
    }
    found.sort();
    Ok(found)
}

/// A path as a `/`-separated string, so generated keys match on every platform.
fn display(path: &Path) -> Result<String, Box<dyn Error>> {
    Ok(path
        .to_str()
        .ok_or("a path under fragments/ is not valid UTF-8")?
        .replace('\\', "/"))
}
