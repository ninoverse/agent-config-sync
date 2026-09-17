# Task runner for this workspace. Install: cargo install --locked just
#
# These recipes are the canonical form of every command in CLAUDE.md, the README
# and the .claude/ rule files. Change a command here, not in five places.

# `just agentcfg why "a phrase"` has to reach the binary as one argument, and a
# variadic parameter joins its arguments with spaces. This passes them through
# as real positional arguments instead, so `"$@"` keeps every boundary.
set positional-arguments

# List available recipes
default:
    @just --list

# Build every crate
build:
    cargo build --workspace

# Type-check every crate (faster than build)
check:
    cargo check --workspace --all-targets

# Format in place
fmt:
    cargo fmt --all

# Gate 1 — formatting is clean
fmt-check:
    cargo fmt --all -- --check

# Gate 2 — clippy with warnings as errors
lint:
    cargo clippy --workspace --all-targets --all-features -- -D warnings

# Gate 3 — tests. nextest does not run doc-tests, so those run separately.
test:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v cargo-nextest >/dev/null 2>&1; then
        cargo nextest run --workspace
    else
        echo "note: cargo-nextest not installed, falling back to cargo test" >&2
        cargo test --workspace --all-targets
    fi
    cargo test --workspace --doc

# Gate 4 — licenses and advisories
deny:
    cargo deny check

# All four merge gates, in the order .claude/testing-requirements.md lists them
ci: fmt-check lint test deny

# Known CVEs in the dependency tree
audit:
    cargo audit

# Re-check on every save
watch:
    cargo watch -x 'check --workspace --all-targets'

# Build and open the workspace docs
doc:
    cargo doc --workspace --no-deps --open

# Optimized build
release:
    cargo build --workspace --release

# Consumer repositories download this file and run it: no toolchain, no glibc
# version to match, and the Go repositories have no Rust at all. `-p agentcfg`
# rather than `--workspace` because the example crate is scaffolding and has no
# business in a release. `rustup target add` is a no-op once the target is
# installed, so this is the same command on a laptop and on a release runner.
#
# One statically linked agentcfg for one target — what a release publishes
dist target:
    rustup target add {{ target }}
    cargo build --release --locked -p agentcfg --target {{ target }}

# `just agentcfg check` is what someone runs after editing their profile, and the
# point is that it needs nothing installed: the published binary is static, and
# the Go repositories have no Rust toolchain to build one with. The version
# comes from `.agentprofile.yml`, so the cache cannot drift from the pin — a
# bump fetches a new file rather than reusing a stale one — and `.agentcfg/` is
# gitignored, so nothing downloaded is ever committed.
#
# Run the pinned agentcfg, fetching it once into a gitignored cache
agentcfg *args:
    #!/usr/bin/env bash
    set -euo pipefail

    if [ ! -f .agentprofile.yml ]; then
        echo "no .agentprofile.yml here — this recipe is for a repository agentcfg manages" >&2
        exit 1
    fi
    version=$(sed -n 's/^config_version:[[:space:]]*//p' .agentprofile.yml)

    # The asset names are the rustc target triples the release publishes, and
    # nothing else builds these URLs, so a rename here is a rename there.
    case "$(uname -s)/$(uname -m)" in
        Linux/x86_64)              target=x86_64-unknown-linux-musl ;;
        Linux/aarch64 | Linux/arm64) target=aarch64-unknown-linux-musl ;;
        Darwin/arm64)              target=aarch64-apple-darwin ;;
        *)
            echo "no agentcfg binary for $(uname -s)/$(uname -m) — published: linux-musl x86_64 and aarch64, darwin aarch64" >&2
            exit 1
            ;;
    esac

    binary=".agentcfg/agentcfg-${version}"
    if [ ! -x "${binary}" ]; then
        mkdir -p .agentcfg
        curl -fsSL -o "${binary}" \
            "https://github.com/ninoverse/agent-config-sync/releases/download/${version}/agentcfg-${target}"
        chmod +x "${binary}"
    fi

    exec "${binary}" "$@"

# Build the runtime image, stamping the current commit as an OCI label.
# Passed explicitly rather than left to BuildKit's own VCS capture, which needs
# a working client-side git and silently yields nothing when it does not have
# one — under `sudo` (git refuses a repo it does not own), or in a CI checkout
# with no .git. A label is also inspectable with `docker inspect`, unlike a
# provenance attestation.
#
# The fallback matters: without it, `sudo just docker-build` runs git as root,
# git refuses the repo, and GIT_SHA becomes an empty string — an empty label
# that looks like a real value. "unknown" is at least honest.
docker-build bin="example":
    docker build \
        --build-arg BIN={{ bin }} \
        --build-arg GIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)" \
        --tag {{ bin }}:latest \
        .

# Scaffold a crate, then follow .claude/crate-workflow.md for the rest
new-crate name:
    cargo new --lib crates/{{ name }}
    @echo "Now: add '[lints]\\nworkspace = true' to crates/{{ name }}/Cargo.toml"
    @echo "and switch its [package] keys to '<key>.workspace = true'."
    @echo "See .claude/crate-workflow.md — 9 steps, do not skip."

# Install the auxiliary tooling the gates need (once per machine)
setup:
    cargo install --locked cargo-nextest cargo-watch cargo-deny cargo-audit
