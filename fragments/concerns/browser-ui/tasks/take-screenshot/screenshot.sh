#!/bin/sh
# sh .agents/take-screenshot/screenshot.sh <url> <h2-text|""> <out.png> [--clip-children]
# Run from the repo root. Runs the first entry whose needs hold, with the same arguments.
#
# Every entry is a script beside this file that takes these arguments, writes the PNG,
# prints "wrote <out>" when it succeeds, and warns on stderr when web fonts failed to load.
# To add one, add its script and three functions named after it (<name>_needs, <name>_applies,
# <name>_run), then add the name to ENTRIES, whose order is the preference. Names are shell
# names: letters, digits and underscores.

# The entry functions are only ever called by name, as "${entry}_applies" and so on.
# ShellCheck reports that as SC2329, or as SC2317 before 0.11.
# shellcheck disable=SC2317,SC2329

here=$(cd "$(dirname "$0")" && pwd)

ENTRIES='playwright'

playwright_needs() {
    echo 'the playwright package resolves from the repo root, and Chromium is at /opt/pw-browsers/chromium or wherever Playwright installed it'
}
playwright_applies() {
    command -v node >/dev/null 2>&1 &&
        node -e '
            const fromRoot = require("node:module").createRequire(process.cwd() + "/package.json");
            const { existsSync } = require("node:fs");
            const { chromium } = fromRoot("playwright");
            process.exit(existsSync("/opt/pw-browsers/chromium") || existsSync(chromium.executablePath()) ? 0 : 1);
        ' 2>/dev/null
}
# No executable bit is set on generated files, so every entry names its interpreter.
playwright_run() {
    node "$here/playwright.mjs" "$@"
}

for entry in $ENTRIES; do
    if "${entry}_applies"; then
        echo "take-screenshot: using $entry" >&2
        "${entry}_run" "$@"
        exit $?
    fi
done

echo 'take-screenshot: no entry applies here. What each one needs:' >&2
for entry in $ENTRIES; do
    echo "  $entry: $("${entry}_needs")" >&2
done
exit 2
