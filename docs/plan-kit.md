# Working on the plan concern's kit

How to change and check the plan concern: the method, its skills, and the kit
that builds a project's page. [Fragment authoring](fragment-authoring.md) covers
what every fragment follows; this covers what the kit adds.

## Files

`fragments/concerns/plan/` holds `phases.md`, the method; a task per skill under
`tasks/`; and the kit beside `tasks/create-project.md`, in
`tasks/create-project/`: `render.py`, `page.css`, `page.js`, `guide.html` and
`starter/*.toml`, which a new project copies. A repository that selects the
concern gets the kit in `.agents/create-project/`, where every skill of the
concern reaches it.

The kit's smoke test is `tests/plan/check.py`, with `tests/plan/example/`, a
project in its Build phase, and `tests/plan/full/`, a project that uses every
section kind the example leaves out. Neither ships. CI runs it on Python 3.11,
the kit's floor, through `project-page-smoke.yml`.

## Checks

```bash
just ci                       # the four gates
python3 -B tests/plan/check.py
```

Run Python with `-B`, or set `sys.dont_write_bytecode`, in any script that
imports `render.py`: Python otherwise leaves a `__pycache__` beside it, inside
`fragments/`, which `build.rs` embeds. The build skips it, and `.gitignore`
ignores it, but it has no place in the tree.

A change to the renderer comes with a case in `check.py` that fails without it:
a stale copy, which must still render with its warning, a broken copy, which
must stop the render with its message, or an expectation on the example or
`full/`. Run the test once without the change, and see the case fail.

When a task, or a file beside one, is added, removed or renamed, the golden
fixture lists it, so bless it:

```bash
AGENTCFG_BLESS=1 cargo test -q -p agentcfg --test golden
```

## The always-on budget

A PR that changes what the concern composes states its cost. Compose a copy of
the repository with the concern selected, and check it:

```bash
git ls-files -z --cached --others --exclude-standard \
  | tar --null -T - -cf - | tar -xf - -C <dir>
# in <dir>/.agentprofile.yml: concerns: [fragment-authoring, plan]
cargo run -q -p agentcfg -- sync --repo <dir> --fragments ./fragments
cargo run -q -p agentcfg -- check --repo <dir> --fragments ./fragments
```

`check` prints the always-on set's lines, of the 200 the budget allows.

## Looking at the page

```bash
K=fragments/concerns/plan/tasks/create-project
python3 -B $K/render.py tests/plan/example <out> --inline
python3 -B $K/render.py tests/plan/full <out> --retrospective
```

`--inline` holds every phase in `index.html`, so it opens from disk; without
it, serve the output, with `python3 -m http.server <port> --bind 127.0.0.1
--directory <out>`.

Capture it with the scripts the browser-ui concern ships, from
`tests/browser-ui`, after `npm ci` there: they resolve Playwright from the
working directory. A script of your own that clicks through the page does the
same, with `createRequire(process.cwd() + '/package.json')('playwright')`.
Look at it light, dark and at a phone's width, and check nothing scrolls
sideways. After a change to the header, the sheets or the links, go through
them again: the opening phase, a phase fetched when picked, a link into another
phase, the Agenda, the Guides and the Warnings, each closed with its button and
with Escape, and a busy day in the calendar.
