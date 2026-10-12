"""python3 tests/plan/check.py, from the repository root.

Runs the project-page renderer the plan concern ships against its example, in
both modes, against full/, which uses every section kind the example leaves
out, against an edited copy compared with the example as if published, against
stale copies of the example, and against broken copies. A stale copy must still
render, with its own warning; a broken copy must fail with its own message and
write nothing; everything else must render without a warning.
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
    expect(sorted(phase) == ["analysis", "brief", "guides", "later", "plan", "research", "verify"], f"the phases loaded on demand: {sorted(phase)}")
    expect("<title>example-service-health-checks</title>" in page, "the title is <repo>-<objective>")
    views = between(page, '<nav class="views"', "</nav>")
    expect('href="#agenda" data-phase="agenda"' in views and 'href="#guides" data-phase="guides"' in views, "the agenda and the guides open from the top right")
    tabs = re.findall(r'data-phase="(\w+)"', between(page, '<nav class="phases"', "</nav>"))
    expect(tabs == ["brief", "research", "analysis", "plan", "build", "verify", "reuse", "retrospective", "later"], f"the indicator holds the nine phases, and only those: {tabs}")
    expect(page.count('<dialog class="sheet"') == 2 and 'aria-label="Close the agenda"' in page and 'aria-label="Close the guides"' in page, "the agenda and the guides are sheets over the page, each with its close button")
    expect('<footer class="site"' not in page, "the page has no footer: the guides answer what it would")
    guides = phase["guides"]
    parts = ("header", "phases", "sections", "cards", "statuses", "kinds", "board", "agenda", "links", "changes", "answering")
    expect(all(f'id="guide-{part}"' in guides and f'href="#guide-{part}"' in guides for part in parts), "the guides hold every part of the guide, each in the contents")
    words = ('st-done">Taken<', 'st-blocked">Not met yet<', 'st-dropped">Not adopted<', 'st-done">Picked up<', 'st-open">To merge<')
    expect(all(word in between(guides, '<table class="statuses"', "</table>") for word in words), "the guide's statuses come from the page's own words")
    expect('<span class="chip s-open">' in guides and '<a class="chip' not in guides, "its sample chips are drawn as the board draws them, but aren't links")
    expect("Readiness probe" in between(guides, 'id="glossary"', "</section>") and 'id="glossary"' not in page, "the glossary is in the guides, and only there")
    expect('data-open="build"' in page, "the page opens on the phase in progress")
    counts = dict(re.findall(r'data-phase="(\w+)"[^>]*>(?:(?!</a>).)*?<span class="count"[^>]*>([\d/]+)</span>', page))
    expect(counts == {"build": "3/6", "verify": "2/4", "later": "0/1"}, f"each phase in progress counts its items done, and only those: {counts}")
    expect('<span class="span">since 5 Oct</span>' in page, "a phase in progress says since when")
    expect('<span class="span">1 Oct – 2 Oct</span>' in phase["research"], "a finished phase says when it ran")

    expect(board_cells(page) == ["example-service", ["EX-1", "EX-3"], ["EX-2", "S1"]], f"the board's waves come from `needs`: {board_cells(page)}")
    expect('st-done">Merged<' in page and 'st-open">To merge<' in page, "a PR reads Merged, or To merge while open")
    expect('st-blocked">Open<' in page and "closes with" in page, "an open risk names the step that closes it")
    for chip in re.findall(r'<a class="chip.*?</a>', page):
        expect("<a " not in chip[2:], f"a chip holds no link of its own: {chip[:80]}")

    expect('class="st ' not in phase["plan"], "the plan shows its items as approved, without the build's statuses")
    expect('<a class="ref" href="#ex-1"><b>EX-1</b> Liveness probe</a>' in phase["plan"], "[[EX-1]] links with its short title")
    expect('Approved on 3 Oct. Amended since:</p><ul class="list">' in phase["plan"] and 'pill amended">Amended 7 Oct<' in phase["plan"], "an item added after the approval says so, and the plan lists it")
    link = '<a class="pill link" href="https://github.com/example/example-service/pull/12" target="_blank" rel="noopener">example/example-service#12</a>'
    expect(link in phase["plan"], "a PR's url is a chip linking to it, named as GitHub names it")
    ex2 = between(phase["plan"], 'id="ex-2"', "</article>")
    layers = [ex2.find(mark) for mark in ('<h4>Readiness probe</h4>', 'class="item-tags"', "<dl>")]
    expect(-1 not in layers and layers == sorted(layers), f"a card reads number and summary, then chips, then fields: {layers}")
    expect("<dt>Title</dt><dd><code>feat: add the readiness probe</code></dd>" in ex2, "a title longer than the summary is a field")
    expect('<dt>Carries out</dt><dd><ul class="list"><li><a class="ref" href="#d1">' in ex2, "a field that holds several things is a list")
    needed = between(between(phase["plan"], 'id="ex-1"', "</article>"), "Needed by", "</dd>")
    expect('<ul class="list">' in needed and all(f'href="#{i}"' in needed for i in ("ex-2", "s1", "c1")), f"a card lists what needs it: {needed}")
    named = between(between(phase["analysis"], 'id="d1"', "</article>"), "Named by", "</dd>")
    expect('<ul class="list">' in named and all(f'href="#{i}"' in named for i in ("r1", "ex-1", "ex-2")), f"a card lists what names it: {named}")
    expect('pill st-done">Taken · 2 Oct<' in phase["analysis"], "a decision that is done reads Taken, with its day, as a chip")
    d1 = between(phase["analysis"], 'id="d1"', "</article>")
    expect('<li class="chosen"><span class="key">a</span>' in d1 and '<span class="vh"> (chosen)</span>' in d1, "options are a list, the chosen one marked, in a word for screen readers too")
    expect('class="recommended"' not in d1 and "pill" not in between(d1, '<ol class="options">', "</ol>"), "once one is chosen, only it is marked, and options carry no chips")
    unchosen = copy_with(tmp, "unchosen", EXAMPLE, "analysis.toml", 'recommended = "a"\nchosen = "a"', 'recommended = "a"')
    if unchosen is not None:
        render(unchosen, tmp / "unchosen-out")
        analysis = tmp / "unchosen-out" / "phases" / "analysis.html"
        d1 = between(analysis.read_text(), 'id="d1"', "</article>") if analysis.exists() else ""
        expect('<li class="recommended"><span class="key">a</span>' in d1 and 'class="chosen"' not in d1, "until one is chosen, the recommended option is marked")
    expect('<div class="changed">Changed:<ul class="list"><li><a href="#results">' in page, "a changelog entry lists what it changed")

    expect('class="st ' not in between(phase["brief"], 'id="sc1"', "</article>"), "the brief shows its criteria as agreed, without Verify's statuses")
    expect('id="g1"' in phase["brief"], "the brief holds the ground rules")
    expect('st-done">Met<' in phase["verify"] and 'st-blocked">Not met yet<' in phase["verify"], "a criterion reads Met, or Not met yet")
    expect('pill st-done">Passed · 6 Oct<' in phase["verify"] and 'pill st-blocked">Waiting<' in phase["verify"], "a check reads Passed, or Waiting")

    ball = between(page, 'id="ball"', "</section>")
    owner, agent = between(ball, "<h3>The owner</h3>", "</ul>"), between(ball, "<h3>The agent</h3>", "</ul>")
    expect("EX-2" in owner and "EX-1" not in owner and "Q1" not in owner, f"the owner's column lists the open items, and only those: {owner}")
    expect("EX-3" in agent and "EX-2" not in agent, f"the agent's column lists the ready items: {agent}")
    order = [page.find(mark) for mark in ('class="months"', 'class="glance"', 'id="ball"', '<nav class="phases"')]
    expect(-1 not in order and order == sorted(order), f"the calendar, the card under it, who holds the ball, then the phases: {order}")
    expect('<p class="glance">PR statuses as of 7 Oct 2026, 18:00 UTC.</p>' in page, "the card says when the PRs' statuses were read")
    soon = re.findall(r'<li class="dated"><a class="when" href="#(on-[\d-]+)"><time>(.*?)</time></a> <span>(.*?)</span></li>', between(ball, "<h3>A date</h3>", "</ul>"))
    renovate = ("on-2026-10-12", "Mon 12 Oct", 'Renovate\'s weekly run <span class="ci">CI</span>')
    expect(soon == [renovate, ("on-2026-10-14", "Wed 14 Oct", "Production deploys freeze until the 21st")], f"a date coming up holds the ball too, soonest first, each linked to its day, and an automated run marked CI: {soon}")
    expect('Renovate\'s weekly run <span class="ci">CI</span>' in between(page, 'id="coming-up"', "</section>"), "the agenda marks the automated run too")
    expect("<th>Waits on the owner</th>" in phase["guides"] and "<th>The owner's part</th>" in phase["guides"], "the guide's statuses table names the owner, not you")
    expect('<span class="pill k-owner">Owner</span>' in phase["plan"], "an item only the owner can do reads Owner")
    expect('class="more"' not in ball, "with three dates or fewer ahead, nothing points to more")
    expect('id="ball"' not in between(page, 'aria-labelledby="agenda-title"', "</dialog>"), "the agenda leaves who holds the ball to the header")
    expect("feat/readiness-probe" in between(page, 'id="next-session"', "</section>"), "the agenda holds the notes for the next session")
    events = "".join(f'[[event]]\ndate = 2026-10-{day}\ntitle = "Release train {day}"\n\n' for day in (20, 27))
    busy = copy_with(tmp, "busy", EXAMPLE, "project.toml", "[[event]]\ndate = 2026-10-12", events + "[[event]]\ndate = 2026-10-12")
    if busy is not None:
        render(busy, tmp / "busy-out")
        index = tmp / "busy-out" / "index.html"
        held = between(index.read_text(), 'id="ball"', "</section>") if index.exists() else ""
        dates = re.findall(r'class="when" href="#on-([\d-]+)"', held)
        expect(dates == ["2026-10-12", "2026-10-14", "2026-10-20"] and '<a href="#coming-up">1 more in the agenda</a>' in held, f"the header shows the next three dates, and links to the rest: {dates}")
    calendar = between(page, 'class="months"', 'class="glance"')
    expect("October 2026" in calendar and 'class="d today has"><a class="dn" href="#on-2026-10-07">7</a>' in calendar, "the month shows the day the state was read, and a day links into the agenda")
    first = re.search(r'<ol class="agenda"><li class="(\w+)" id="on-[\d-]+"><time>(.*?)</time>', between(page, 'id="coming-up"', "</section>"))
    expect(first is not None and first.groups() == ("ahead", "Mon 12 Oct"), "what is coming up runs soonest first")
    first = re.search(r'<ol class="agenda"><li class="(\w+)" id="on-[\d-]+"><time>(.*?)</time>', between(page, 'id="history"', "</section>"))
    expect(first is not None and first.groups() == ("today", "Wed 7 Oct"), "what happened runs newest first, from the day the state was read")
    anchors = manifest(page)
    expect('"ex-1":"plan"' in anchors and '"coming-up":"agenda"' in anchors and '"on-2026-10-12":"agenda"' in anchors, "a link to EX-1 opens the plan, and one to what is coming up, or to a day, the agenda")
    expect('"ball":' not in anchors, "who holds the ball is in the header, on every view, so no view opens for it")
    expect('"glossary":"guides"' in anchors and '"guide-board":"guides"' in anchors, "a link to the glossary, or into the guide, opens the guides")

    inline = tmp / "inline"
    run = render(EXAMPLE, inline, "--inline")
    expect(run.returncode == 0, f"the example renders inline: {run.stderr}")
    if run.returncode == 0:
        expect(not (inline / "phases").exists(), "--inline writes no phase files")
        whole = (inline / "index.html").read_text()
        expect('id="ex-1"' in whole and 'id="g1"' in whole and 'id="c1"' in whole and 'id="guide-board"' in whole, "--inline holds every phase, and the guides")

    run = render(EXAMPLE, tmp / "no-retrospective", "--retrospective")
    expect(run.returncode == 1 and "the Retrospective has no data yet" in run.stderr, f"--retrospective needs a Retrospective: {run.stderr}")
    run = render(EXAMPLE, tmp / "both", "--inline", "--retrospective")
    expect(run.returncode == 2, f"--inline and --retrospective don't go together: exit {run.returncode}")


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
    expect(all(f'st-{s}">{label}<' in page for s, label in (("open", "To review"), ("done", "Adopted · 8 Oct"), ("dropped", "Not adopted"))), "a lesson reads To review, Adopted or Not adopted")
    analysis = (out / "phases" / "analysis.html").read_text()
    unmarked = '<li><span class="key">a</span><span><code>/metrics</code>, which every scraper asks for first.</span></li>'
    expect(unmarked in analysis and '<li class="chosen"><span class="key">b</span>' in analysis, "the chosen option can differ from the recommended one, which is then no longer marked")
    figures = re.findall(r'<li><span class="v">(.*?)</span><span class="k">(.*?)</span></li>', page)
    counted = [("1", "PR merged"), ("1", "release"), ("1", "decision taken"), ("1", "lesson adopted"), ("38", "days, start to finish"), ("15 s", "between scrapes")]
    expect(figures == counted, f"the figures the data can count come first, then those written out: {figures}")
    expect("The first 5 counted from the project's data on 8 October 2026." in page, "the note says which figures were counted, and when")
    build = (out / "phases" / "build.html").read_text()
    expect(board_cells(build) == ["example-service", ["MX-1"], ["MX-2"]], f"a board can name its columns and rows: {board_cells(build)}")
    expect(build.index("MX-2") < build.index("<b>MX-1</b>", build.index('class="results"')), "results follow `ids`")
    expect("st-dropped" in build and "The first one covers it." in build, "a dropped item says why")
    later = (out / "phases" / "later.html").read_text()
    expect('st-blocked">Waiting<' in later and 'href="#l2"' in later, "a rule change waits in For later, on its lesson")
    expect("[[" not in page + build + later, "a title that names an item links it, and leaves no brackets in a short name")
    september = between(page, '<div class="month" hidden>', "</table>")
    expect("<h2>September 2026</h2>" in september and 'disabled aria-label="No earlier month"' in september, "an earlier month waits behind the arrow, and the first has none before it")
    expect('data-step="-1" aria-label="September 2026">' in between(page, '<div class="month">', "</table>"), "the month shown is the one the state was read in, with an arrow back")

    alone = tmp / "alone"
    run = render(FULL, alone, "--retrospective")
    expect(run.returncode == 0 and "warning:" not in run.stderr, f"full/'s Retrospective renders alone: {run.stderr}")
    if run.returncode == 0:
        expect(sorted(p.name for p in alone.iterdir()) == ["retrospective.html"], "--retrospective writes the one page")
        retro = (alone / "retrospective.html").read_text()
        expect("<title>example-service-metrics-retrospective</title>" in retro, "the page alone is titled <repo>-<objective>-retrospective")
        expect(all(absent not in retro for absent in ('<nav class="phases"', 'class="months"', 'id="agenda"', "<script")), "it has no tabs, no calendar, no agenda and no script")
        expect('<span class="ref"><b>MX-1</b>' in retro and 'href="#mx-1"' not in retro, "it names as text an item it doesn't hold")
        expect('id="l1"' in retro and 'id="glossary"' in retro and "lesson adopted" in retro, "it holds the lessons, the figures and the glossary")
        expect('id="guides"' not in retro and 'id="guide-board"' not in retro, "but not the guides, which are about the project page")
    linked = copy_with(tmp, "full-linked", FULL, "retrospective.toml", "[[MX-1]] shows", '<a href=\\"#mx-1\\">MX-1</a> shows')
    if linked is not None:
        expect(render(linked, tmp / "linked-page").returncode == 0, "on the project page, a link by hand to MX-1 has its target")
        run = render(linked, tmp / "linked-alone", "--retrospective")
        expect(run.returncode == 1 and 'a link to "#mx-1"' in run.stderr, f"alone, it has none, and the render says so: {run.stderr}")


# Each stale copy of the example: the file, the text replaced, its replacement,
# and the warning it must print. The page is still written.
STALE = [
    ("project.toml", '[phases.build]\nstatus = "now"', '[phases.build]\nstatus = "done"', "Build is done, but EX-2 is still `open`"),
    ("plan.toml", '["Carries out", ["[[D1]]", "[[D2]]"]]', '["Carries out", ["[[D1]]"]]', "D2 is a decision taken, but no PR names it or needs it"),
    ("build.toml", 'on = 2026-10-06\nresult = "Released 1.4.0.', 'on = 2026-10-06\nnote = "Released 1.4.0.', "EX-1 is a merged PR without a `result`"),
    ("build.toml", '[status.EX-2]\nstatus = "open"', '[status.EX-2]\nstatus = "done"', "C2 is `blocked`, but everything it needs is done"),
    ("later.toml", 'waits = "the metrics stack"', 'waits = "[[EX-1]]"', "T1 waits on EX-1, which is done"),
    ("build.toml", 'production"\nstatus = "done"', 'production"\nstatus = "open"', "EX-3 is `ready`, but needs Q1, which isn't done"),
    ("analysis.toml", 'recommended = "a"\nchosen = "a"', 'recommended = "a"', "D1 is `done`, but none of its options is `chosen`"),
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
    (EXAMPLE, "plan.toml", 'pull/12"\nfields = [', 'pull/12"\nstatus = "done"\nfields = [', "status is set twice"),
    (EXAMPLE, "research.toml", "<code>/api</code>", "<code>/api", "is never closed"),
    (EXAMPLE, "project.toml", 'objective = "health-checks"', 'objective = "Health Checks"', "kebab-case"),
    (EXAMPLE, "later.toml", 'id = "deferred"', 'id = "deferred', "not valid TOML"),
    (EXAMPLE, "build.toml", 'changed = ["results", "q1"]', 'changed = ["results", "q9"]', "`changed` names q9"),
    (EXAMPLE, "build.toml", "[status.EX-3]", "[status.EX-9]", "no item has this id"),
    (EXAMPLE, "project.toml", "[phases.reuse]", "[phases.templating]", "[phases.templating] is not a phase"),
    (EXAMPLE, "project.toml", "read_at = 2026-10-07T18:00:00", 'read_at = "7 October"', "`read_at` is when the state was read"),
    (EXAMPLE, "project.toml", "date = 2026-10-12\n", "", "an event has a `date`"),
    (EXAMPLE, "project.toml", 'short = "Renovate"\nci = true', 'short = "Renovate"\nci = "yes"', "`ci` is true or false"),
    (EXAMPLE, "plan.toml", 'pull/14"\nneeds = ["EX-1"]', 'pull/14"\nneeds = ["EX-9"]', "`needs` names EX-9, which no item has"),
    (EXAMPLE, "analysis.toml", 'chosen = "a"', 'chosen = "c"', "`chosen` is c, which no option has"),
    (EXAMPLE, "analysis.toml", '["b", "A second port', '["A second port', "`options` is a list of [key, text] pairs"),
    (EXAMPLE, "plan.toml", '["Carries out", ["[[D1]]", "[[D2]]"]]', '["Carries out", ["[[D1]]", 2]]', "each of `fields` is a [label, text] pair, its text one string or a list of them"),
    (EXAMPLE, "plan.toml", 'short = "Liveness probe"\n', 'short = "Liveness probe"\nneeds = ["EX-2"]\n', "`needs` loops: EX-1 → EX-2 → EX-1"),
    (EXAMPLE, "plan.toml", ', why = "the answer to [[Q1]]" }', " }", "`amended` is"),
    (EXAMPLE, "plan.toml", 'url = "https://github.com/example/example-service/pull/12"', 'url = "github.com/example/example-service/pull/12"', "`url` is an https:// address"),
    (FULL, "build.toml", 'cells = [["MX-1"], ["MX-2"]]', 'cells = [["MX-1"], ["MX-9"]]', "the board names MX-9"),
]


def replace_in(data, file, old, new):
    """One replacement in a copy's file; False, and a failure, when `old` isn't there."""
    path = data / file
    text = path.read_text()
    if old not in text:
        failed.append(f"{data.name}: {old!r} is not in {file}")
        return False
    path.write_text(text.replace(old, new, 1))
    return True


def copy_with(tmp, name, base, file, old, new):
    """A copy of `base` with one replacement in `file`, or None when `old` isn't there."""
    data = tmp / name
    shutil.copytree(base, data)
    return data if replace_in(data, file, old, new) else None


def check_since(tmp):
    """--since lists what changed in each phase since the data as published."""
    run = render(EXAMPLE, tmp / "since-same", "--since", str(EXAMPLE))
    expect(run.returncode == 0 and run.stdout.endswith("Since the published data: nothing has changed.\n"), f"unchanged data reports nothing: {run.stdout}")
    expect(render(EXAMPLE, tmp / "since-none", "--since", str(tmp / "nowhere")).returncode == 2, "--since names a directory that exists")

    merged = '[status.EX-2]\nstatus = "done"\non = 2026-10-09\nresult = "Released 1.5.0."'
    data = copy_with(tmp, "since", EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"\non = 2026-10-07\nresult = "Open and green, waiting for your merge."', merged)
    if data is None:
        return
    added = '[[section.item]]\nid = "EX-4"\ntitle = "<code>docs: the probes in the README</code>"\nkind = "patch"\nneeds = ["EX-2"]\n\n[[section]]\nid = "settings"'
    entry = '[[section.entry]]\ndate = 2026-10-09\ntext = "[[EX-2]] merged."\n\n[[section.entry]]\ndate = 2026-10-07'
    edited = [
        replace_in(data, "plan.toml", "stops answering is restarted.", "stops answering is restarted within a minute."),
        replace_in(data, "plan.toml", '["Carries out", ["[[D1]]", "[[D2]]"]]', '["Carries out", ["[[D2]]", "[[D1]]"]]'),
        replace_in(data, "plan.toml", '[[section]]\nid = "settings"', added),
        replace_in(data, "build.toml", "[[section.entry]]\ndate = 2026-10-07", entry),
        replace_in(data, "project.toml", "updated = 2026-10-07", "updated = 2026-10-09"),
    ]
    if not all(edited):
        return
    run = render(data, tmp / "since-out", "--since", str(EXAMPLE))
    expect(run.returncode == 0, f"a changed copy renders: {run.stderr}")
    expect('  Plan: EX-1: Done when edited; EX-2: Carries out edited; EX-4 added.\n    changed = ["ex-1", "ex-2", "ex-4"]\n' in run.stdout, f"edited fields, a list among them, and a new item, with their ids: {run.stdout}")
    expect('  Build: EX-2 To merge → Merged; Log: 1 entry added.\n    changed = ["results", "log"]\n' in run.stdout, f"a status in its type's words, shown in the results: {run.stdout}")
    expect("  project.toml: `handoff` edited.\n" in run.stdout and "read_at" not in run.stdout, f"project.toml's changes, read_at aside: {run.stdout}")
    for key in ("plan", "build"):
        expect(f"warning: {key}.toml: it has changed since the published data, and its changelog has no new entry" in run.stderr, f"{key}.toml changed without a changelog entry: {run.stderr}")
    replace_in(data, "build.toml", "[[changelog]]\ndate = 2026-10-07", '[[changelog]]\ndate = 2026-10-09\ntext = "[[EX-2]] merged."\nchanged = ["results", "log"]\n\n[[changelog]]\ndate = 2026-10-07')
    run = render(data, tmp / "since-out", "--since", str(EXAMPLE))
    expect("build.toml: it has changed" not in run.stderr and "plan.toml: it has changed" in run.stderr, f"a new entry answers the warning, phase by phase: {run.stderr}")


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
        check_since(tmp)
        check_stale(tmp)
        check_broken(tmp)
    for what in failed:
        print(f"FAIL: {what}", file=sys.stderr)
    print(f"{'FAILED' if failed else 'passed'}: the example, full/, changes since a publish, {len(STALE)} stale copies and {len(BROKEN)} broken copies")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
