---
title: Automation
scope: always
emit: [claude]
---

`.claude/settings.json` allowlists the commands in *Build and test commands* so
they do not prompt, runs `gofmt` on every `.go` file you edit, and warns if the
module stops compiling when a turn ends. Formatting is therefore already handled
— do not run `make fmt` after each edit.
