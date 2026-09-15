---
title: Releases and deploys
scope: on-demand
when: Any change that ends in a PR
---

A merged PR is a deploy. `bump-version.yml` tags every push to `main` whose
subject is a conventional commit — `docs:` and `chore:` included — and
`release.yml` deploys every `v*.*.*` tag to Cloud Run. A hand-pushed commit on
`main` is an unreviewed deploy.

## How a tag becomes a deploy

- `release.yml` calls the organization's `release-cloudrun.yml`, which runs
  `gcloud run deploy --source .`: Cloud Build builds the repository-root
  `Dockerfile` and deploys the image.
- The tag must be pushed with the release GitHub App's token. A tag pushed with
  `GITHUB_TOKEN` does not trigger other workflows, so nothing would deploy.
- The deploy reads `vars.GCP_PROJECT`, `vars.GCP_REGION` and
  `secrets.GCP_SERVICE_ACCOUNT` from the repository.

## What the service must do

- Listen on the `PORT` environment variable, which Cloud Run injects. Default to
  `8080` so the server still runs locally.
- Keep the `service:` name in `release.yml` matching the binary the `Dockerfile`
  builds. Rename both together.
- The service is public: the deploy passes `--allow-unauthenticated` unless
  `release.yml` sets `allow-unauthenticated: false`. An internal service sets it.
