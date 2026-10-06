---
title: Releases and deploys
scope: on-demand
when: Any change that ends in a PR
---

A merged PR is a deploy. `bump-version.yml` tags every push to `main` whose
subject cuts a release, `docs:` and `chore:` included, and `release.yml`
deploys every `v*.*.*` tag to Firebase. A hand-pushed commit on `main` is an
unreviewed deploy.

## How a tag becomes a deploy

- `release.yml` calls the organization's `firebase-deploy.yml`, which installs
  the dependencies and runs `firebase deploy` for the project and the targets
  `release.yml` names in `only`.
- `firebase.json` says what each target is. `apphosting` uploads the source, and
  Firebase App Hosting builds it and runs it, server rendering included.
  `hosting:<site>` uploads the static files the target's `predeploy` hook builds,
  for Firebase Hosting to serve.
- The tag must be pushed with the release GitHub App's token. A tag pushed with
  `GITHUB_TOKEN` does not trigger other workflows, so nothing would deploy.
- The deploy signs in with `secrets.FIREBASE_DEPLOY_SERVICE_ACCOUNT`, a service
  account key with a role for each target it deploys.

## What the site must do

- Keep secrets out of what the browser downloads. Hosting serves every file a
  static build writes, so no secret enters one.
- On App Hosting, set the environment in `apphosting.yaml`, with each secret as
  a reference to Cloud Secret Manager, never as a value.
- Change a target in `firebase.json` and in `release.yml`'s `only` together:
  `only` is what deploys, and `firebase.json` is what each name means.

## After the merge

- Check the site, not the run: the tag the merge cut, the deploy for that tag,
  and the change live on the site.
- A broken deploy is fixed by the next merge, or rolled back in the Firebase
  console. Never by deleting a tag and pushing it again.
