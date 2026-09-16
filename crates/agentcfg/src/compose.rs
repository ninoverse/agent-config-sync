//! The one computation `sync`, `check` and `plan` all run.
//!
//! They differ only in what they do with the answer — write it, compare it, or
//! print it — which is why drift detection costs nothing extra.

use crate::{
    AgentsMd, Claude, EmitInput, Emitter, EmitterName, FragmentSet, OutputFile, Plan, Profile,
    Repo, Selection,
    error::{EmitError, Error},
};

/// A repository's configuration, composed and compared against what is there.
#[derive(Debug)]
pub struct Composition {
    /// What the repository asked for.
    pub profile: Profile,
    /// The fragments that answers, substituted and ordered.
    pub selection: Selection,
    /// What every selected emitter would write.
    pub files: Vec<OutputFile>,
    /// What writing it would change.
    pub plan: Plan,
}

impl Composition {
    /// Composes `repo`'s configuration from `tree`, stamping `version` into
    /// every provenance comment.
    ///
    /// Reads only — [`crate::Repo::apply`] is the part that writes.
    ///
    /// # Errors
    ///
    /// [`Error`] if the profile is missing or invalid, a fragment references
    /// something no selected value declares, two emitters claim one path, or
    /// the repository cannot be read.
    pub fn of(repo: &Repo, tree: &FragmentSet, version: &str) -> Result<Self, Error> {
        let profile = Profile::parse(&repo.profile()?, tree)?;
        let selection = Selection::resolve(&profile, tree)?;

        let input = EmitInput {
            selection: &selection,
            profile: &profile,
            tree,
            version,
        };

        let mut claimed: Vec<(EmitterName, OutputFile)> = Vec::new();
        for emitter in &profile.emit {
            let files = match emitter {
                EmitterName::AgentsMd => AgentsMd.emit(input)?,
                EmitterName::Claude => Claude.emit(input)?,
            };
            claimed.extend(files.into_iter().map(|file| (*emitter, file)));
        }

        // Each emitter already rejects a path it claims twice. This is the
        // other direction: two emitters claiming one path between them. Their
        // prefixes are disjoint today, so this is a guard rather than a fix.
        for (index, (emitter, file)) in claimed.iter().enumerate() {
            if claimed[..index]
                .iter()
                .any(|(_, seen)| seen.path == file.path)
            {
                return Err(EmitError::DuplicatePath {
                    emitter: *emitter,
                    path: file.path.clone(),
                }
                .into());
            }
        }

        let files: Vec<OutputFile> = claimed.into_iter().map(|(_, file)| file).collect();
        let plan = repo.plan(&files)?;

        Ok(Self {
            profile,
            selection,
            files,
            plan,
        })
    }
}
