<!-- agentcfg:start -->
<!-- agentcfg:import · v1.0.0 -->
@AGENTS.md

<!-- language/rust/automation.md · v1.0.0 -->
# Automation

`.claude/settings.json` allowlists the commands in *Build and test commands* so
they do not prompt, runs `rustfmt` on every `.rs` file you edit, and warns if the
workspace stops compiling when a turn ends. Formatting is therefore already
handled — do not run `cargo fmt` after each edit.
<!-- agentcfg:end -->
