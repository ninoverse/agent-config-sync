#!/bin/sh
# sh check.sh, from this directory, after `npm ci` and a Chromium install.
#
# Runs the take-screenshot dispatcher, and each entry on its own, in every mode
# against fixture.html, and checks what each wrote: the PNG's size, or the exit
# code and message of a failure. The entries resolve playwright from the working
# directory, as they resolve a repository's own from its root, so this runs here,
# where npm installed it.
#
# The expected sizes are 2× the CSS boxes. Every line in the fixture has a fixed
# line height, so no size depends on which font face loaded.
set -u

here=$(pwd)
scripts="$here/../../fragments/concerns/browser-ui/tasks/take-screenshot"
url="file://$here/fixture.html"
out=$(mktemp -d)
failed=0

# The two ways in, called by name as "$way" below, which ShellCheck reports as
# SC2329, or as SC2317 before 0.11.
# shellcheck disable=SC2317,SC2329
dispatcher() { sh "$scripts/screenshot.sh" "$@"; }
# shellcheck disable=SC2317,SC2329
playwright() { node "$scripts/playwright.mjs" "$@"; }

fail() {
    echo "FAIL: $*" >&2
    failed=1
}

# A PNG's width and height, from its IHDR chunk.
size() {
    node -e '
        const png = require("node:fs").readFileSync(process.argv[1]);
        console.log(png.readUInt32BE(16) + "x" + png.readUInt32BE(20));
    ' "$1"
}

# captures <name> <expected WxH> <way> <heading> [flag]
captures() {
    name=$1 expected=$2 way=$3 heading=$4
    shift 4
    if ! "$way" "$url" "$heading" "$out/$name.png" "$@" > "$out/$name.log" 2>&1; then
        fail "$name exited non-zero: $(cat "$out/$name.log")"
        return
    fi
    actual=$(size "$out/$name.png")
    if [ "$actual" = "$expected" ]; then
        echo "ok: $name, $actual"
    else
        fail "$name is $actual, expected $expected"
    fi
}

for way in dispatcher playwright; do
    # A boxed section: 952 × 116 CSS px.
    captures "$way-boxed" 1904x232 "$way" "Boxed"
    # A `display: contents` section: its children, clipped to the page's width.
    captures "$way-contents" 2000x192 "$way" "Contents"
    # --clip-children on a boxed section: its children, 8 px either side.
    captures "$way-clip" 1864x192 "$way" "Boxed" --clip-children
    # No heading: the whole page, which fits one 1000 × 900 viewport.
    captures "$way-page" 2000x1800 "$way" ""

    # A heading the page doesn't have: the entry's own error, exit 1.
    "$way" "$url" "Nope" "$out/$way-nope.png" > "$out/$way-nope.log" 2>&1
    code=$?
    if [ "$code" -eq 1 ] && grep -q 'no section found' "$out/$way-nope.log"; then
        echo "ok: $way-nope, exit 1"
    else
        fail "$way-nope exited $code: $(cat "$out/$way-nope.log")"
    fi
done

# From a directory playwright doesn't resolve from, no entry fits: exit 2, with
# each entry's needs listed.
(cd "$out" && dispatcher "$url" "Boxed" "$out/none.png") > "$out/none.log" 2>&1
code=$?
if [ "$code" -eq 2 ] && grep -q '^  playwright: ' "$out/none.log"; then
    echo "ok: no entry fits, exit 2"
else
    fail "no-entry case exited $code: $(cat "$out/none.log")"
fi

rm -rf "$out"
exit "$failed"
