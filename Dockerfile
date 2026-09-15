# syntax=docker/dockerfile:1

# Multi-stage build using cargo-chef. The point of chef is the `cook` step: it
# compiles ONLY the dependency tree into its own layer, keyed on a recipe
# derived from the manifests. Editing your own source invalidates the layers
# after it but not that one, so a source-only rebuild does not recompile the
# whole dependency tree. Without chef, every edit to a .rs file would.

ARG RUST_VERSION=1.98
ARG DEBIAN_RELEASE=bookworm

# ---------- chef: toolchain + cargo-chef, cached once ----------
FROM rust:${RUST_VERSION}-slim-${DEBIAN_RELEASE} AS chef
WORKDIR /app
RUN cargo install --locked cargo-chef
# rust-toolchain.toml asks for `stable`, which is not the name the base image
# registers its toolchain under, so the first cargo call would trigger a rustup
# download. Do it here, once, in a layer that is cached for every later stage.
COPY rust-toolchain.toml ./
RUN rustup show

# ---------- planner: derive the dependency recipe ----------
FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

# ---------- builder ----------
FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
# Dependencies only. Cached until the dependency set itself changes.
RUN cargo chef cook --release --recipe-path recipe.json
COPY . .
# Which binary to ship. Override for your own crate:
#   docker build --build-arg BIN=my-service .
ARG BIN=example
RUN cargo build --release --locked --bin "${BIN}" \
    && cp "target/release/${BIN}" /app/service

# ---------- dev: full toolchain for compose and the devcontainer ----------
# Kept separate from `builder` so the shipped image never carries the test and
# lint tooling. The cargo install is slow, which is exactly why it is its own
# cached layer and not something contributors run by hand.
FROM chef AS dev
# Deliberately unpinned: pinning apt versions in a template breaks the build at
# every Debian point release, and none of these reach the shipped image.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends git pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN cargo install --locked just cargo-nextest cargo-watch cargo-deny cargo-audit
# Kept as a separate layer on purpose: the cargo install above takes minutes and
# this takes seconds, so adding a component later must not rebuild the slow one.
# hadolint ignore=DL3059
RUN rustup component add rustfmt clippy rust-src rust-analyzer
WORKDIR /app
CMD ["bash"]

# ---------- runtime ----------
FROM debian:${DEBIAN_RELEASE}-slim AS runtime
# ca-certificates is deliberately unpinned — see the note in the dev stage.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app
COPY --from=builder /app/service /usr/local/bin/service

# Provenance, passed in rather than discovered. BuildKit's own VCS capture
# depends on a working client-side git and quietly records nothing when it does
# not have one — notably under `sudo`, where git refuses a repo owned by another
# user, and in CI checkouts with no .git. That failure is where the
# "failed to read current commit information" warning comes from; it is a
# property of the build environment, not of this file, and cannot be fixed here.
# A label is also inspectable with `docker inspect`, unlike an attestation.
# `just docker-build` fills these in; a bare `docker build` leaves them
# "unknown", which is honest rather than wrong.
ARG GIT_SHA=unknown
ARG SOURCE_URL=https://github.com/ninoverse/claude-mit-rust-template
LABEL org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.licenses="MIT"

# Numeric, not `app`: orchestrators that enforce runAsNonRoot cannot resolve a
# username and will refuse to schedule the pod.
USER 10001
WORKDIR /home/app
ENTRYPOINT ["/usr/local/bin/service"]
