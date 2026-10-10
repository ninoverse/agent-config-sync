"""python3 tests/plan/check.py, from the repository root.

Runs the project-page renderer the plan concern ships against its example, in
both modes, against full/, which uses every section kind the example leaves
out, against stale copies of the example, and against broken copies. A stale
copy must still render, with its own warning; a broken copy must fail with its
own message and write nothing; everything else must render without a warning.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path("fragments/concerns/plan/tasks/project-page")
EXAMPLE = KIT / "example"
FULL = Path(__file__).resolve().parent / "full"
failed = []


def render(data, out, *flags):
    return subprocess.run(
        [sys.executable, str(KIT / "render.py"), str(data), str(out), *flags],
        capture_output=True,
        text=True,
    )


def expect(condition, what):
    if not condition:
        failed.append(what)


def between(text, start, end):
    """The text from `start` to the next `end`, or nothing when `start` is missing."""
    if start not in text:
        return ""
    begin = text.index(start)
    return text[begin:text.find(end, begin)]


def manifest(page):
    return re.search(r'<script type="application/json" id="anchors">(.*?)</script>', page).group(1)


def board_cells(text):
    """Each cell of a board's one row: the row's name, then the ids in each wave."""
    cells = re.findall(r"<td>(.*?)</td>", between(text, '<table class="board"', "</table>"))
    return cells[:1] + [re.findall(r"<b>(.*?)</b>", cell) for cell in cells[1:]]


def check_example(tmp):
    out = tmp / "example"
    run = render(EXAMPLE, out)
    expect(run.returncode == 0, f"the example renders: {run.stderr}")
    if run.returncode:
        return
    expect("warning:" not in run.stderr, f"the example renders without a warning: {run.stderr}")
    page = (out / "index.html").read_text()
    phase = {p.stem: p.read_text() for p in (out / "phases").iterdir()}
    expect(sorted(phase) == ["analysis", "brief", "later", "plan", "research", "verify"], f"the phases loaded on demand: {sorted(phase)}")
    expect("<title>example-service-health-checks</title>" in page, "the title is <repo>-<objective>")
    expect('data-open="build"' in page, "the page opens on the phase in progress")
    expect('<span class="span">since 5 Oct</span>' in page, "a phase in progress says since when")
    expect('<span class="span">1 Oct – 2 Oct</span>' in phase["research"], "a finished phase says when it ran")

    expect(board_cells(page) == ["example-service", ["EX-1", "EX-3"], ["EX-2", "S1"]], f"the board's waves come from `needs`: {board_cells(page)}")
    expect('st-done">Merged<' in page and 'st-open">To merge<' in page, "a PR reads Merged, or To merge while open")
    expect('st-blocked">Open<' in page and "closes with" in page, "an open risk names the step that closes it")
    for chip in re.findall(r'<a class="chip.*?</a>', page):
        expect("<a " not in chip[2:], f"a chip holds no link of its own: {chip[:80]}")

    expect('class="st ' not in phase["plan"], "the plan shows its items as approved, without the build's statuses")
    expect('<a class="ref" href="#ex-1"><b>EX-1</b> Liveness probe</a>' in phase["plan"], "[[EX-1]] links with its short title")
    expect("Approved on 3 Oct. Amended since:" in phase["plan"] and 'pill amended">Amended 7 Oct<' in phase["plan"], "an item added after the approval says so")
    needed = between(between(phase["plan"], 'id="ex-1"', "</article>"), "Needed by", "</p>")
    expect(all(f'href="#{i}"' in needed for i in ("ex-2", "s1", "c1")), f"a card lists what needs it: {needed}")
    named = between(between(phase["analysis"], 'id="d1"', "</article>"), "Named by", "</p>")
    expect(all(f'href="#{i}"' in named for i in ("r1", "ex-1", "ex-2")), f"a card lists what names it: {named}")
    expect('st-done">Taken<' in phase["analysis"], "a decision that is done reads Taken")

    expect('class="st ' not in between(phase["brief"], 'id="sc1"', "</article>"), "the brief shows its criteria as agreed, without Verify's statuses")
    expect('id="g1"' in phase["brief"], "the brief holds the ground rules")
    expect('st-done">Met<' in phase["verify"] and 'st-blocked">Not met yet<' in phase["verify"], "a criterion reads Met, or Not met yet")
    expect('st-done">Passed<' in phase["verify"] and 'st-blocked">Waiting<' in phase["verify"], "a check reads Passed, or Waiting")

    ball = between(page, 'id="ball"', "</section>")
    you, me = between(ball, "Waiting on you", "</ul>"), between(ball, "Next for me", "</ul>")
    expect("EX-2" in you and "EX-1" not in you and "Q1" not in you, f"Waiting on you lists the open items, and only those: {you}")
    expect("EX-3" in me and "EX-2" not in me, f"Next for me lists the ready items: {me}")
    expect("<span>1 waiting on you</span> <span>1 next for me</span> <span>Next date: Mon 12 Oct, Renovate's weekly run</span>" in page, "the header counts who holds the ball, and names the next date")
    expect("feat/readiness-probe" in between(page, 'id="next-session"', "</section>"), "the calendar holds the notes for the next session")
    calendar = between(page, 'id="calendar"', "</main>")
    expect("October 2026" in calendar and 'class="d today has"><span class="dn">7</span>' in calendar, "the month shows the day the state was read")
    first = re.search(r'<ol class="agenda"><li class="(\w+)"><time>(.*?)</time>', calendar)
    expect(first is not None and first.groups() == ("ahead", "Wed 14 Oct"), "the agenda runs newest first, from the last date ahead")
    anchors = manifest(page)
    expect('"ex-1":"plan"' in anchors and '"ball":"calendar"' in anchors, "a link to EX-1 opens the plan, and one to the ball the calendar")

    inline = tmp / "inline"
    run = render(EXAMPLE, inline, "--inline")
    expect(run.returncode == 0, f"the example renders inline: {run.stderr}")
    if run.returncode == 0:
        expect(not (inline / "phases").exists(), "--inline writes no phase files")
        whole = (inline / "index.html").read_text()
        expect('id="ex-1"' in whole and 'id="g1"' in whole and 'id="c1"' in whole, "--inline holds every phase")


def check_full(tmp):
    out = tmp / "full"
    run = render(FULL, out)
    expect(run.returncode == 0, f"full/ renders: {run.stderr}")
    if run.returncode:
        return
    expect("warning:" not in run.stderr, f"full/ renders without a warning: {run.stderr}")
    page = (out / "index.html").read_text()
    expect('data-open="retrospective"' in page, "full/ opens on its retrospective")
    expect('ph-not-needed">Not needed<' in page and "Nothing here is worth copying." in page, "a phase that is not needed says why")
    expect('id="old-status"' in page and 'href="#old-status"' in page, "an imported page's ids and links move under its prefix")
    expect('aria-labelledby="old-status-title"' in page and 'for="old-pick"' in page, "so do the attributes that name ids")
    expect('class="figures"' in page and 'class="defs"' in page, "figures and definitions render")
    expect(".imported-marker" in page, "a project's own stylesheet is appended")
    expect(all(f'st-{s}">{label}<' in page for s, label in (("open", "To review"), ("done", "Adopted"), ("dropped", "Not adopted"))), "a lesson reads To review, Adopted or Not adopted")
    build = (out / "phases" / "build.html").read_text()
    expect(board_cells(build) == ["example-service", ["MX-1"], ["MX-2"]], f"a board can name its columns and rows: {board_cells(build)}")
    expect(build.index("MX-2") < build.index("<b>MX-1</b>", build.index('class="results"')), "results follow `ids`")
    expect("st-dropped" in build and "The first one covers it." in build, "a dropped item says why")
    later = (out / "phases" / "later.html").read_text()
    expect('st-blocked">Waiting<' in later and 'href="#l2"' in later, "a rule change waits in For later, on its lesson")
    expect("[[" not in page + build + later, "a title that names an item links it, and leaves no brackets in a short name")


# Each stale copy of the example: the file, the text replaced, its replacement,
# and the warning it must print. The page is still written.
STALE = [
    ("project.toml", '[phases.build]\nstatus = "now"', '[phases.build]\nstatus = "done"', "Build is done, but EX-2 is still `open`"),
    ("plan.toml", '["Carries out", "[[D1]] and [[D2]]"]', '["Carries out", "[[D1]]"]', "D2 is a decision taken, but no PR names it or needs it"),
    ("build.toml", 'on = 2026-10-06\nresult = "Released 1.4.0.', 'on = 2026-10-06\nnote = "Released 1.4.0.', "EX-1 is a merged PR without a `result`"),
    ("build.toml", '[status.EX-2]\nstatus = "open"', '[status.EX-2]\nstatus = "done"', "C2 is `blocked`, but everything it needs is done"),
    ("later.toml", 'waits = "the metrics stack"', 'waits = "[[EX-1]]"', "T1 waits on EX-1, which is done"),
    ("build.toml", 'production"\nstatus = "done"', 'production"\nstatus = "open"', "EX-3 is `ready`, but needs Q1, which isn't done"),
    ("plan.toml", "due = 2026-10-14", "due = 2026-10-05", "EX-2 was due on 5 Oct"),
    ("plan.toml", "amended = { on = 2026-10-07", "amended = { on = 2026-10-02", "EX-3 is amended on 2 Oct, before its phase was approved"),
    ("project.toml", "read_at = 2026-10-07T18:00:00", "read_at = 2026-10-06T18:00:00", "`read_at` is older than the newest changelog entry"),
    ("project.toml", "updated = 2026-10-07", "updated = 2026-10-06", "the notes for the next session date from 6 Oct, before the last change"),
]

# Each broken copy: the project it copies, the file, the text replaced, its
# replacement, and the message.
BROKEN = [
    (EXAMPLE, "analysis.toml", 'id = "D2"', 'id = "D1"', "this id is used twice"),
    (EXAMPLE, "research.toml", '"[[D1]]"', '"<a href=\\"#d9\\">D9</a>"', 'a link to "#d9"'),
    (EXAMPLE, "research.toml", '"[[D1]]"', '"[[D9]]"', "[[D9]] names no item"),
    (EXAMPLE, "research.toml", 'type = "piece"', 'type = "pieces"', "`type` is one of"),
    (EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"', '[status.EX-2]\nstatus = "waiting"', "status `waiting` is not one of"),
    (EXAMPLE, "later.toml", 'waits = "the metrics stack"\n', "", "a blocked item says what it waits on"),
    (EXAMPLE, "project.toml", 'why = "Two routes', 'what = "Two routes', "a phase that is not needed says why"),
    (EXAMPLE, "plan.toml", 'kind = "minor"\nfields = [\n  ["Branch", "<code>feat/liveness', 'kind = "minor"\nstatus = "done"\nfields = [\n  ["Branch", "<code>feat/liveness', "status is set twice"),
    (EXAMPLE, "research.toml", "<code>/api</code>", "<code>/api", "is never closed"),
    (EXAMPLE, "project.toml", 'objective = "health-checks"', 'objective = "Health Checks"', "kebab-case"),
    (EXAMPLE, "later.toml", 'id = "deferred"', 'id = "deferred', "not valid TOML"),
    (EXAMPLE, "build.toml", 'changed = ["results", "q1"]', 'changed = ["results", "q9"]', "`changed` names q9"),
    (EXAMPLE, "build.toml", "[status.EX-3]", "[status.EX-9]", "no item has this id"),
    (EXAMPLE, "project.toml", "[phases.reuse]", "[phases.templating]", "[phases.templating] is not a phase"),
    (EXAMPLE, "project.toml", "read_at = 2026-10-07T18:00:00", 'read_at = "7 October"', "`read_at` is when the state was read"),
    (EXAMPLE, "project.toml", "date = 2026-10-12\n", "", "an event has a `date`"),
    (EXAMPLE, "plan.toml", "due = 2026-10-14", 'due = "14 October"', "`due` is a date"),
    (EXAMPLE, "plan.toml", 'needs = ["EX-1"]\ndue', 'needs = ["EX-9"]\ndue', "`needs` names EX-9, which no item has"),
    (EXAMPLE, "plan.toml", 'short = "Liveness probe"\n', 'short = "Liveness probe"\nneeds = ["EX-2"]\n', "`needs` loops: EX-1 → EX-2 → EX-1"),
    (EXAMPLE, "plan.toml", ', why = "the answer to [[Q1]]" }', " }", "`amended` is"),
    (FULL, "build.toml", 'cells = [["MX-1"], ["MX-2"]]', 'cells = [["MX-1"], ["MX-9"]]', "the board names MX-9"),
]


def copy_with(tmp, name, base, file, old, new):
    """A copy of `base` with one replacement in `file`, or None when `old` isn't there."""
    data = tmp / name
    shutil.copytree(base, data)
    path = data / file
    text = path.read_text()
    if old not in text:
        failed.append(f"{name}: {old!r} is not in {file}")
        return None
    path.write_text(text.replace(old, new, 1))
    return data


def check_stale(tmp):
    for index, (file, old, new, message) in enumerate(STALE):
        data = copy_with(tmp, f"stale-{index}", EXAMPLE, file, old, new)
        if data is None:
            continue
        out = tmp / f"stale-{index}-out"
        run = render(data, out)
        expect(run.returncode == 0, f"stale case {index} ({message}) exits 0, not {run.returncode}")
        warned = [line for line in run.stderr.splitlines() if line.startswith("warning: ")]
        expect(any(message in line for line in warned), f"stale case {index} warns {message!r}; it said: {run.stderr.strip()}")
        expect((out / "index.html").exists(), f"stale case {index} still writes the page")


def check_broken(tmp):
    for index, (base, file, old, new, message) in enumerate(BROKEN):
        data = copy_with(tmp, f"broken-{index}", base, file, old, new)
        if data is None:
            continue
        out = tmp / f"broken-{index}-out"
        run = render(data, out)
        expect(run.returncode == 1, f"broken case {index} ({message}) exits 1, not {run.returncode}")
        expect(message in run.stderr, f"broken case {index} says {message!r}; it said: {run.stderr.strip()}")
        expect(not (out / "index.html").exists(), f"broken case {index} writes nothing")


def main():
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        check_example(tmp)
        check_full(tmp)
        check_stale(tmp)
        check_broken(tmp)
    for what in failed:
        print(f"FAIL: {what}", file=sys.stderr)
    print(f"{'FAILED' if failed else 'passed'}: the example, full/, {len(STALE)} stale copies and {len(BROKEN)} broken copies")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
