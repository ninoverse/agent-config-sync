"""python3 tests/plan/check.py, from the repository root.

Runs the project-page renderer the plan concern ships against its example, in
both modes, against full/, which uses every section kind the example leaves
out, against an edited copy compared with the example as if published, against
stale copies of the example, and against broken copies. A stale copy must still
render, with its own warning; a broken copy must fail with its own message and
write nothing; everything else must render without a warning.
"""

import datetime
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


def calendar_of(page):
    return between(page, 'class="months"', 'class="glance"')


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
    expect(sorted(phase) == ["analysis", "brief", "deferred", "guides", "plan", "research", "verify"], f"the phases loaded on demand: {sorted(phase)}")
    expect("<title>example-service-health-checks</title>" in page, "the title is <repo>-<objective>")
    views = between(page, '<nav class="views"', "</nav>")
    expect('href="#agenda" data-phase="agenda"' in views and 'href="#guides" data-phase="guides"' in views, "the agenda and the guides open from the top right")
    indicator = between(page, '<nav class="phases" aria-labelledby="phases-title">', "</nav>")
    leaves = between(page, '<nav class="phases leaves" aria-labelledby="leaves-title">', "</nav>")
    tabs, left = re.findall(r'data-phase="(\w+)"', indicator), re.findall(r'data-phase="(\w+)"', leaves)
    expect(indicator.count("<li>") == 6 and tabs == ["brief", "research", "analysis", "plan", "build", "verify"], f"the indicator holds the six phases, each a link: {tabs}")
    expect(leaves.count("<li>") == 3 and left == ["deferred"] and '<span class="n">' not in leaves, f"then, unnumbered, the three that are what the project leaves, each a link but those with nothing to show: {left}")
    expect('<h2 id="phases-title">Phases</h2><nav class="phases" aria-labelledby="phases-title">' in page and '<h2 id="leaves-title">What it leaves</h2>' in page, "the two groups have a title each, Phases and What it leaves")
    unwritten = '<li><span class="off t-to-come"><span class="name">Retrospective</span><span class="state">To come</span></span></li>'
    expect(unwritten in leaves and 'id="retrospective"' not in page, "a phase with nothing written has a tab that doesn't open, and no view")
    reuse = '<li><span class="off t-not-needed"><span class="name">Reuse</span><span class="state">Not needed</span></span></li>'
    expect(reuse in leaves and 'id="reuse"' not in page and "Two routes are too little" not in page and '"reuse"' not in manifest(page), "a phase not needed has a tab that doesn't open, and no view; its reason stays in the data")
    expect('<span class="name">Deferred</span><span class="state">2 waiting</span>' in leaves, f"Deferred's tab says how many items wait, deferred work that is blocked among them: {leaves}")
    expect(page.count('<dialog class="sheet"') == 2 and 'aria-label="Close the agenda"' in page and 'aria-label="Close the guides"' in page, "the agenda and the guides are sheets over the page, each with its close button")
    expect('<footer class="site"' not in page, "the page has no footer: the guides answer what it would")
    guides = phase["guides"]
    parts = ("header", "phases", "cards", "statuses", "kinds", "board", "agenda", "answering")
    expect(all(f'id="guide-{part}"' in guides and f'href="#guide-{part}"' in guides for part in parts), "the guides hold every part of the guide, each in the contents")
    words = ('st-done">Taken<', 'st-dropped">Not taken<', 'st-blocked">Not met yet<', 'st-dropped">Not adopted<', 'st-done">Picked up<', 'st-open">To merge<')
    expect(all(word in between(guides, '<table class="statuses"', "</table>") for word in words), "the guide's statuses come from the page's own words")
    expect('<span class="chip s-open">' in guides and '<a class="chip' not in guides, "its sample chips are drawn as the board draws them, but aren't links")
    expect('<span class="chip s-deferred">' in guides and '<span class="mine">Your go</span>' in guides, "one of them is set aside, until the owner says")
    expect("Readiness probe" in between(guides, 'id="glossary"', "</section>") and 'id="glossary"' not in page, "the glossary is in the guides, and only there")
    expect('data-open="build"' in page, "the page opens on the phase in progress")
    counts = dict(re.findall(r'data-phase="(\w+)"[^>]*>(?:(?!</a>).)*?<span class="count"[^>]*>([\d/]+)</span>', page))
    expect(counts == {"build": "3/6", "verify": "2/4"}, f"each phase in progress counts its items done, and only those: {counts}")
    views = [page] + list(phase.values())
    expect('<section class="phase" id="build" data-phase="build">\n<h2 class="vh">Build</h2>\n<section class="block" id="board">' in page, "a phase's view starts with its first section, its name only for screen readers")
    shown = [between(page, '<main id="phases"', "</main>")] + [text for key, text in phase.items() if key != "guides"]
    expect(all('class="lede"' not in view and 'class="intro"' not in view for view in shown) and 'class="lede"' not in phase["guides"], "no view has a description of itself, nor a section a line saying what it holds")
    expect(all("phase-head" not in view and "1 Oct – 2 Oct" not in view for view in views), "the tab shows a phase's name and state, and the calendar its dates, so its view doesn't repeat them")

    expect(board_cells(page) == ["example-service", ["EX-1", "EX-3"], ["EX-2", "S1"]], f"the board's waves come from `needs`: {board_cells(page)}")
    expect('st-done">Merged<' in page and 'st-open">To merge<' in page, "a PR reads Merged, or To merge while open")
    expect('pill st-blocked">Open<' in page and "<dt>Closes with</dt>" in page, "an open risk names the step that closes it")
    results = between(page, 'id="results"', "</section>")
    expect("<table" not in results and '<span class="n">EX-1</span><h4><a class="ref" href="#ex-1">Liveness probe</a></h4>' in results and "<dt>Result</dt><dd>Released 1.4.0." in results, "results are cards, each linking to its item's own card")
    shown = re.findall(r'<span class="n">(.*?)</span>', results)
    ex1 = between(results, '<span class="n">EX-1</span>', "</article>")
    expect(shown == ["EX-1", "S1", "RK1"] and "pill" not in ex1 and 'pill st-blocked">Open<' in results, f"what the board shows is in the results only once it has a result, and then the result alone: {shown}")
    rk1, ex3 = between(phase["plan"], 'id="rk1"', "</article>"), between(phase["plan"], 'id="ex-3"', "</article>")
    expect("<dt>Closes with</dt>" in rk1 and "<dt>Closes</dt>" in ex3 and "Needed by" not in ex3, "a risk's needs read Closes with, and the step that closes it says Closes")
    for chip in re.findall(r'<a class="chip.*?</a>', page):
        expect("<a " not in chip[2:], f"a chip holds no link of its own: {chip[:80]}")

    expect('class="st ' not in phase["plan"], "the plan shows its items as approved, without the build's statuses")
    expect('<a class="ref" href="#ex-1"><b>EX-1</b> Liveness probe</a>' in phase["plan"], "[[EX-1]] links with its short title")
    approved = '<span class="n"></span><p class="says">Approved.</p></div>\n    <div class="item-tags"><span class="pill day">3 Oct</span></div>\n    <dl><dt>Amended since</dt><dd><ul class="amendments"><li><span class="pill day">7 Oct</span> the answer to <a class="ref" href="#q1"><b>Q1</b> The probe\'s timeout in production</a>:<ul class="list"><li><a class="ref" href="#ex-3"><b>EX-3</b> Ten seconds in production</a></li></ul></li></ul></dd></dl>'
    expect(approved in phase["plan"] and 'pill amended">Amended 7 Oct<' in phase["plan"], "an item added after the approval says so, with when and why, and the plan's approval lists it under that day and why")
    expect(phase["plan"].index('id="plan-approval"') > phase["plan"].index('id="risks"'), "the approval comes after the plan's sections")
    expect('<a href="#plan" data-phase="plan" class="t-amended"><span class="n">4</span><span class="name">Plan</span><span class="state">Amended</span></a>' in page, "a done phase that has taken amendments reads Amended on its tab")
    amending = copy_with(tmp, "amending", EXAMPLE, "analysis.toml", 'id = "D2"\ntitle = "What readiness waits for"\n', 'id = "D2"\ntitle = "What readiness waits for"\namended = { on = 2026-10-02, why = "the cache, found on the way" }\n')
    if amending is not None:
        run = render(amending, tmp / "amending-out")
        analysis = (tmp / "amending-out" / "phases" / "analysis.html").read_text() if run.returncode == 0 else ""
        closing = between(analysis, '<section class="block" id="analysis-amendments">', "</section>")
        expect('<h3>Amendments</h3>' in closing and '<p class="says">Done.</p>' in closing and '<span class="pill day">2 Oct</span> the cache, found on the way:' in closing and 'href="#d2"' in closing, f"a phase without an approval takes amendments after its end, and lists them there: {run.stderr} {closing[:600]}")
        expect('<span class="name">Analysis</span><span class="state">Amended</span>' in (tmp / "amending-out" / "index.html").read_text(), "and its tab reads Amended")
    link = '<a class="pill link" href="https://github.com/example/example-service/pull/12" target="_blank" rel="noopener">example/example-service#12</a>'
    expect(link in phase["plan"], "a PR's url is a chip linking to it, named as GitHub names it")
    ex2 = between(phase["plan"], 'id="ex-2"', "</article>")
    layers = [ex2.find(mark) for mark in ('<h4>Readiness probe</h4>', 'class="item-tags"', "<dl>")]
    expect(-1 not in layers and layers == sorted(layers), f"a card reads number and summary, then chips, then fields: {layers}")
    expect("<dt>Title</dt><dd><code>feat: add the readiness probe</code></dd>" in ex2, "a title longer than the summary is a field")
    folded = '<details class="fold">\n      <summary class="item-head"><span class="n">EX-2</span><h4>Readiness probe</h4><span class="item-tags">'
    expect(folded in ex2 and "</summary>\n      <dl>" in ex2, "a card folds its fields behind its number, summary and chips")
    unfolded = [m for view in views for m in re.findall(r'<article class="item" id="[^"]+">\n    (?!<details class="fold">)', view)]
    expect(not unfolded, f"every item's card folds: {unfolded[:2]}")
    expect('<details class="fold">' in results and "open-all" in results, "results fold, as cards do, and can be opened all at once")
    prs, risks = between(phase["plan"], 'id="prs"', "</section>"), between(phase["plan"], 'id="risks"', "</section>")
    expect('<p class="fold-all"><button type="button" class="open-all">Open all</button></p>' in prs and "open-all" not in risks, "a section with several folded cards can open them all, and one with a single card has no need")
    expect('<dt>Carries out</dt><dd><ul class="list"><li><a class="ref" href="#d1">' in ex2, "a field that holds several things is a list")
    needed = between(between(phase["plan"], 'id="ex-1"', "</article>"), "Needed by", "</dd>")
    expect('<ul class="list">' in needed and all(f'href="#{i}"' in needed for i in ("ex-2", "s1", "c1")), f"a card lists what needs it: {needed}")
    by_setting = copy_with(tmp, "by-setting", EXAMPLE, "plan.toml", '["Carries out", ["[[D1]]", "[[D2]]"]]', '["Carries out", ["[[D1]]"]]')
    if by_setting is not None and replace_in(by_setting, "plan.toml", 'fields = [["Where", "The service\'s deployment settings."]]', 'fields = [["Where", "The service\'s deployment settings."], ["Carries out", "[[D2]]"]]'):
        run = render(by_setting, tmp / "by-setting-out")
        analysis = tmp / "by-setting-out" / "phases" / "analysis.html"
        d2 = between(analysis.read_text(), 'id="d2"', "</article>") if analysis.exists() else ""
        expect("D2 is a decision taken" not in run.stderr and '<dt>Carried out by</dt><dd><ul class="list"><li><a class="ref" href="#s1">' in d2, f"a setting carries out a decision as a PR does: {run.stderr} {d2[:300]}")
    d1 = between(phase["analysis"], 'id="d1"', "</article>")
    carried, mentioned = between(d1, "<dt>Carried out by</dt>", "</dd>"), between(d1, "<dt>Mentioned in</dt>", "</dd>")
    expect(all(f'href="#{i}"' in carried for i in ("ex-1", "ex-2")) and 'href="#r1"' not in carried, f"a decision lists the PRs that name it as carrying it out: {carried}")
    expect('<ul class="list">' in mentioned and 'href="#r1"' in mentioned and 'href="#ex-1"' not in mentioned, f"and what else mentions it: {mentioned}")
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
    expect(all("changelog" not in view.lower() and "Earlier changes" not in view for view in views), "the page has no changelog: the Agenda says what happened, and the agent tells the user what changed")
    expect(not re.search(r'<div class="item-head"><span class="n">\d', "".join(views)), "no card has a date where an item's number goes")
    project = between(phase["brief"], 'id="the-project"', "</section>")
    expect('<article class="item">\n    <dl class="terms"><dt>Problem</dt>' in project, "the Brief's definitions are a card of their own")
    expect('id="analysis-contents"' not in phase["analysis"], "an Analysis with one section needs no contents")
    plan_contents = between(phase["plan"], 'id="plan-contents"', "</nav>")
    expect('<li><a href="#prs">' in plan_contents and plan_contents.endswith('<li><a href="#plan-approval">Approval</a></li></ol>'), f"the Plan opens with its sections, then its approval: {plan_contents}")
    two = copy_with(tmp, "two-batches", EXAMPLE, "analysis.toml", '[[section]]\nid = "decisions"\ntitle = "Decisions"', '[[section]]\nid = "decisions"\ntitle = "Batch A"')
    if two is not None and replace_in(two, "analysis.toml", '[[section.item]]\nid = "D2"', '[[section]]\nid = "batch-b"\ntitle = "Batch B"\nkind = "items"\ntype = "decision"\n\n[[section.item]]\nid = "D2"'):
        run = render(two, tmp / "two-batches-out")
        analysis = tmp / "two-batches-out" / "phases" / "analysis.html"
        contents = between(analysis.read_text(), 'id="analysis-contents"', "</nav>") if analysis.exists() else ""
        expect('<li><a href="#decisions">Batch A</a></li><li><a href="#batch-b">Batch B</a></li>' in contents, f"the Analysis opens with a list of its sections, built from them: {run.stderr} {contents}")
    raised = copy_with(tmp, "raised-later", EXAMPLE, "analysis.toml", 'waits for"\nstatus = "done"\non = 2026-10-02', 'waits for"\nstatus = "open"\namended = { on = 2026-10-07, why = "the cache, found in Build" }')
    if raised is not None and replace_in(raised, "analysis.toml", 'recommended = "a"\nchosen = "a"\nfields = [["Reasons", "The service answers', 'recommended = "a"\nfields = [["Reasons", "The service answers'):
        run = render(raised, tmp / "raised-later-out")
        expect(run.returncode == 0, f"a decision amended in after the Plan's approval can wait on the owner: {run.stderr}")
    waiting = copy_with(tmp, "nothing-yet", EXAMPLE, "build.toml", 'title = "Results"\nkind = "results"\n', 'title = "Results"\nkind = "results"\nids = ["EX-2"]\n')
    if waiting is not None:
        run = render(waiting, tmp / "nothing-yet-out")
        index = tmp / "nothing-yet-out" / "index.html"
        results = between(index.read_text(), 'id="results"', "</section>") if index.exists() else ""
        expect(run.returncode == 0 and '<p class="note">Nothing yet.</p>' in results, f"results with nothing to show yet say so: {run.stderr} {results}")
    expect("article.item dl.terms { grid-template-columns: minmax(var(--label), max-content)" in page, "a definitions card's terms take the width they need, a chip among them")
    expect("td .pill { white-space: normal" in page and "no-repeat local" in page, "a chip in a table wraps with its column, and a table that scrolls is shaded at the edge with more past it")
    chipped = copy_with(tmp, "chipped", EXAMPLE, "research.toml", '  ["Today", "<code>example-service</code> serves', '  ["Found", "<span class=\\"pill day\\">A gap</span>"],\n  ["Today", "<code>example-service</code> serves')
    if chipped is not None:
        render(chipped, tmp / "chipped-out")
        research = tmp / "chipped-out" / "phases" / "research.html"
        r1 = between(research.read_text(), 'id="r1"', "</article>") if research.exists() else ""
        expect("<h4>The service's routes</h4><span class=\"item-tags\"><span class=\"pill day\">A gap</span></span></summary>" in r1 and "<dt>Found</dt>" not in r1, f"a field that is one chip is a chip, which a folded card shows: {r1[:300]}")
    more = '\n\n[[section]]\nid = "pieces-more"\nkind = "prose"\nbody = "<p>More on the pieces.</p>"\n'
    untitled = copy_with(tmp, "untitled", EXAMPLE, "research.toml", '  ["Raises", "[[D2]]"],\n]\n', '  ["Raises", "[[D2]]"],\n]' + more)
    if untitled is not None:
        run = render(untitled, tmp / "untitled-out", "--since", str(EXAMPLE))
        expect("  Research: What exists added.\n" in run.stdout, f"--since names a section without a title by the one it carries on: {run.stdout}")
    dropped = copy_with(tmp, "dropped", EXAMPLE, "verify.toml", '[status.SC2]\nstatus = "blocked"', '[status.SC2]\nstatus = "dropped"\non = 2026-10-07\nwhy = "The platform drains a process on its own."')
    if dropped is not None:
        render(dropped, tmp / "dropped-out")
        brief = tmp / "dropped-out" / "phases" / "brief.html"
        sc2 = between(brief.read_text(), 'id="sc2"', "</article>") if brief.exists() else ""
        expect('<span class="pill st-dropped">Dropped · 7 Oct</span>' in sc2 and "<dt>Why</dt><dd>The platform drains a process on its own.</dd>" in sc2, f"a dropped criterion says so in the Brief, with why: {sc2[:400]}")
    statuses = copy_with(tmp, "statuses-only", EXAMPLE, "brief.toml", 'needs = ["C1"]\n', "")
    if statuses is not None and replace_in(statuses, "brief.toml", 'needs = ["C2"]\n', ""):
        (statuses / "verify.toml").write_text('[status.SC1]\nstatus = "done"\non = 2026-10-06\n\n[status.SC2]\nstatus = "blocked"\nwaits = "its checks, written in Verify"\n')
        run = render(statuses, tmp / "statuses-only-out")
        index = tmp / "statuses-only-out" / "index.html"
        tab = '<li><span class="off t-now"><span class="n">6</span><span class="name">Verify</span>'
        expect(run.returncode == 0 and tab in index.read_text() and not (tmp / "statuses-only-out" / "phases" / "verify.html").exists(), f"a phase whose file holds only statuses has nothing to show: its tab doesn't open: {run.stderr}")

    expect('<div class="scroll" data-start' not in page, "a board whose first column has work left opens at its start")
    shipped = copy_with(tmp, "shipped", EXAMPLE, "build.toml", '[status.EX-3]\nstatus = "ready"', '[status.EX-3]\nstatus = "done"\non = 2026-10-07\nresult = "Released 1.4.1."')
    if shipped is not None:
        render(shipped, tmp / "shipped-out")
        board = (tmp / "shipped-out" / "index.html").read_text()
        expect('<div class="scroll" data-start="2">' in board, "once its first column is done, a board opens at the next, which has work left")
    parked = copy_with(tmp, "parked-first", EXAMPLE, "build.toml", '[status.EX-3]\nstatus = "ready"', '[status.EX-3]\nstatus = "deferred"\non = 2026-10-07\nwaits = "the freeze to end"')
    if parked is not None:
        render(parked, tmp / "parked-first-out")
        board = (tmp / "parked-first-out" / "index.html").read_text()
        expect('<div class="scroll" data-start="2">' in board, "an item set aside is not work left: a board whose first column holds only it, and what is done, opens at the next")
    reused = copy_with(tmp, "reused", EXAMPLE, "project.toml", '[phases.reuse]\nstatus = "not-needed"\nwhy = "Two routes are too little for another project to take. The service template\'s README links this project instead."', '[phases.reuse]\nstatus = "now"')
    if reused is not None:
        (reused / "reuse.toml").write_text('[[section]]\nid = "takeaways"\ntitle = "What another project can take"\nkind = "defs"\n\n[[section.def]]\nterm = "The probes"\ntext = "[[EX-1]] and [[EX-2]], copied as they are."\n\n[[section.def]]\nterm = "The timeout"\ntext = "[[EX-3]], for a slow database."\n')
        run = render(reused, tmp / "reused-out")
        reuse = (tmp / "reused-out" / "phases" / "reuse.html").read_text() if run.returncode == 0 else ""
        expect(reuse.count('<article class="item">') == 2 and "<h4>The probes</h4>" in reuse and "<h4>The timeout</h4>" in reuse, f"Reuse holds its pieces as definitions, a card each: {run.stderr}")
        (reused / "reuse.toml").write_text('[[section]]\nid = "log"\ntitle = "The log"\nkind = "prose"\nbody = "<p>What happened.</p>"\n')
        run = render(reused, tmp / "reused-log-out")
        expect(run.returncode == 1 and "Reuse holds only defs sections" in run.stderr, f"and nothing else: {run.stderr}")
    parked = copy_with(tmp, "parked", EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"\non = 2026-10-07', '[status.EX-2]\nstatus = "deferred"\non = 2026-10-07\nwaits = "the next release train"')
    if parked is not None:
        run = render(parked, tmp / "parked-out")
        work = between((tmp / "parked-out" / "phases" / "deferred.html").read_text(), 'id="work"', "</section>") if run.returncode == 0 else ""
        expect('<span class="n">EX-2</span>' in work and 'st-deferred">Deferred · 7 Oct</span><span class="waits">waits on the next release train</span>' in work, f"Deferred lists what another phase deferred, with what it waits on: {run.stderr} {work[-600:]}")
        build_tab = between((tmp / "parked-out" / "index.html").read_text(), 'data-phase="build"', "</a>") if run.returncode == 0 else ""
        expect('<span class="count" title="3 of 5 done, not counting dropped or set-aside items">3/5</span>' in build_tab, f"and a deferred item no longer counts in its phase: {build_tab}")
    early = copy_with(tmp, "early", EXAMPLE, "project.toml", '[phases.plan]\nstatus = "done"', '[phases.plan]\nstatus = "now"')
    if early is not None:
        run = render(early, tmp / "early-out")
        expect(run.returncode == 1 and "Build has started, but Plan isn't done: say why it starts early, in `early`" in run.stderr, f"a phase starts once the one it follows is done: {run.stderr}")
        if replace_in(early, "project.toml", '[phases.build]\nstatus = "now"', '[phases.build]\nstatus = "now"\nearly = "the fix the outage needed, before the plan\'s approval"'):
            run = render(early, tmp / "early-out")
            started = between((tmp / "early-out" / "index.html").read_text(), 'id="on-2026-10-05"', "</li>") if run.returncode == 0 else ""
            expect("Build starts early: the fix the outage needed, before the plan's approval" in started, f"or early, saying why, which the agenda shows: {run.stderr} {started}")
    reopened = copy_with(tmp, "reopened", EXAMPLE, "project.toml", '[phases.build]\nstatus = "now"', '[phases.build]\nstatus = "now"\nreopened = [{ ended = 2026-10-06, on = 2026-10-07 }]')
    if reopened is not None:
        run = render(reopened, tmp / "reopened-out")
        agenda = (tmp / "reopened-out" / "index.html").read_text() if run.returncode == 0 else ""
        ended, again = between(agenda, 'id="on-2026-10-06"', "</ul>"), between(agenda, 'id="on-2026-10-07"', "</ul>")
        expect("Build ends" in ended and "Build reopens" in again, f"a phase that reopened keeps the day it ended, and the day it reopened: {run.stderr} {ended[:300]} {again[:300]}")
    moved = copy_with(tmp, "moved", EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"\non = 2026-10-07', '[status.EX-2]\nstatus = "moved"\non = 2026-10-08\nto = "https://example.com/health-v2#ex-1"')
    if moved is not None and replace_in(moved, "plan.toml", 'short = "Liveness probe"\n', 'short = "Liveness probe"\nfrom = "https://example.com/health-v1#hc-1"\n'):
        run = render(moved, tmp / "moved-out")
        moved_build = (tmp / "moved-out" / "index.html").read_text() if run.returncode == 0 else ""
        moved_plan = (tmp / "moved-out" / "phases" / "plan.html").read_text() if run.returncode == 0 else ""
        moved_deferred = (tmp / "moved-out" / "phases" / "deferred.html").read_text() if run.returncode == 0 else ""
        moved_card = between(between(moved_build, 'id="results"', "</section>"), '<span class="n">EX-2</span>', "</article>")
        expect('st-moved">Moved · 8 Oct</span><a class="pill link" href="https://example.com/health-v2#ex-1" target="_blank" rel="noopener">Its new page</a>' in moved_card, f"a moved item, though on the board, shows in the results with a link to its card on the page that took it: {run.stderr} {moved_card[:400]}")
        expect('href="https://example.com/health-v1#hc-1" target="_blank" rel="noopener">Its old page</a>' in moved_plan, "and an item moved in links back to where it came from")
        expect('<span class="n">EX-2</span>' not in moved_deferred, "a moved item is done with here, so Deferred doesn't list it")
    came_true = '[status.RK1]\nstatus = "happened"\non = 2026-10-07\nresult = "It did, under load: [[Q1]] took it over."'
    happened = copy_with(tmp, "happened", EXAMPLE, "build.toml", '[status.RK1]\nstatus = "blocked"', came_true)
    if happened is not None:
        run = render(happened, tmp / "happened-out")
        build = tmp / "happened-out" / "index.html"
        rk1 = between(build.read_text(), '<span class="n">RK1</span>', "</article>") if build.exists() else ""
        expect(run.returncode == 0 and '<span class="pill st-happened">Happened · 7 Oct</span>' in rk1 and "took it over" in rk1, f"a risk that came true is Happened, naming what took it over: {run.stderr} {rk1[:400]}")
        if replace_in(happened, "plan.toml", 'short = "Slow database"\n', 'short = "Slow database"\namended = { on = 2026-10-08, why = "seen in production" }\n'):
            run = render(happened, tmp / "happened-late-out")
            expect(run.returncode == 1 and "RK1 happened on 7 Oct, before it was written on 8 Oct" in run.stderr, f"a risk is written before it happens: {run.stderr}")
    statuses = between(phase["guides"], 'id="guide-statuses"', "</section>")
    expect("<strong>Happened</strong>" in statuses and "<th>Ready</th>" not in statuses and "<th>Happened</th>" not in statuses, "the guide words a risk's sixth state, and its table leaves out what every type says alike")

    expect('class="st ' not in between(phase["brief"], 'id="sc1"', "</article>") and "pill st-" not in between(phase["brief"], 'id="sc1"', "</article>"), "the brief shows its criteria as agreed, without Verify's statuses")
    agreeing = copy_with(tmp, "agreeing", EXAMPLE, "verify.toml", '[status.SC2]\nstatus = "blocked"', '[status.SC2]\nstatus = "open"')
    if agreeing is not None:
        render(agreeing, tmp / "agreeing-out")
        brief = tmp / "agreeing-out" / "phases" / "brief.html"
        sc2 = between(brief.read_text(), 'id="sc2"', "</article>") if brief.exists() else ""
        expect('<span class="pill st-open">To agree</span>' in sc2, f"until the owner agrees a criterion, its card in the Brief says To agree: {sc2[:300]}")
    expect('id="g1"' in phase["brief"], "the brief holds the ground rules")
    t1 = between(phase["deferred"], 'id="t1"', "</article>")
    expect('Waiting</span><span class="waits">waits on the metrics stack</span></span></summary>' in t1 and "<dt>Waits on</dt>" not in t1, f"a blocked card says what it waits on beside its chip, folded, and not again under it: {t1[:400]}")
    t2 = between(phase["deferred"], 'id="t2"', "</article>")
    expect('<span class="pill st-deferred">Deferred</span><span class="pill ask">Your go</span></span></summary>' in t2 and "waits on" not in t2, f"an item deferred until the owner says shows it as theirs, beside its chip: {t2[:400]}")
    yours = copy_with(tmp, "yours", EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"', '[status.EX-2]\nstatus = "deferred"\nwaits = "owner"')
    if yours is not None and replace_in(yours, "build.toml", 'id = "Q1"\ntitle = "The probe\'s timeout in production"\nstatus = "done"', 'id = "Q1"\ntitle = "The probe\'s timeout in production"\nstatus = "deferred"\nwaits = "owner"'):
        run = render(yours, tmp / "yours-out")
        build = (tmp / "yours-out" / "index.html").read_text() if run.returncode == 0 else ""
        chip = between(build, '<a class="chip s-deferred" href="#ex-2">', "</a>")
        expect('<span class="mine">Your go</span>' in chip and "waits on" not in chip, f"a board chip says it too: {run.stderr} {chip}")
        expect('<span class="pill ask">Your call</span>' in between(build, 'id="q1"', "</article>"), "and a question deferred until the owner says waits on their call")
        owner = between(between(build, 'id="ball"', "</section>"), "<h3>The owner</h3>", "</div>")
        expect('<p class="more"><a href="#deferred">Deferred until you say: 3</a></p>' in owner and "EX-2" not in owner, f"the header counts what waits on the owner but not yet, without listing it: {owner}")
    sc2 = between(phase["verify"], '<span class="n">SC2</span>', "</article>")
    expect('<span class="waits">waits on C2 Cut the database in staging</span>' in sc2 and '<dt>Waits on</dt><dd><ul class="list"><li><a class="ref" href="#c2">' in sc2, f"and when it waits on items, they stay links under the fold: {sc2[:500]}")
    sc1, c1 = between(phase["brief"], 'id="sc1"', "</article>"), between(phase["verify"], 'id="c1"', "</article>")
    expect('<dt>Verified by</dt><dd><ul class="list"><li><a class="ref" href="#c1">' in sc1 and "Needs" not in sc1, "a success criterion's needs read Verified by")
    expect('<dt>Verifies</dt><dd><ul class="list"><li><a class="ref" href="#sc1">' in c1 and "Needed by" not in c1 and "<dt>Needs</dt>" in c1, "and a check names the criteria it verifies, apart from what it needs")
    repos = between(phase["brief"], 'id="repositories"', "</section>")
    uses = ('<code>example-service</code> <span class="pill u-change">Change</span>', '<code>platform-docs</code> <span class="pill u-read">Read</span>')
    expect(all(use in repos for use in uses), "each repository has a chip for what the project does with it")
    expect(all(f'<span class="pill u-{use}">' in phase["guides"] for use in ("change", "read", "new")), "the guides explain every use, in the page's own words")
    met = between(phase["verify"], 'id="criteria-met"', "</section>")
    expect('pill st-done">Met · 6 Oct<' in met and 'pill st-blocked">Not met yet<' in met and "<table" not in met, "the success criteria are cards, each Met, or Not met yet")
    expect('pill st-done">Passed · 6 Oct<' in phase["verify"] and 'pill st-blocked">Waiting<' in phase["verify"], "a check reads Passed, or Waiting")

    ball = between(page, 'id="ball"', "</section>")
    owner, agent = between(ball, "<h3>The owner</h3>", "</ul>"), between(ball, "<h3>The agent</h3>", "</ul>")
    expect("EX-2" in owner and "EX-1" not in owner and "Q1" not in owner, f"the owner's column lists the open items, and only those: {owner}")
    expect("EX-3" in agent and "EX-2" not in agent, f"the agent's column lists the ready items: {agent}")
    expect('<p class="more"><a href="#deferred">Deferred until you say: 1</a></p>' in between(ball, "<h3>The owner</h3>", "</div>") and "T2" not in owner, "and counts, under them, what is deferred until the owner says")
    order = [page.find(mark) for mark in ('class="months"', 'class="glance"', 'id="ball"', '<nav class="phases"')]
    expect(-1 not in order and order == sorted(order), f"the calendar, the card under it, who holds the ball, then the phases: {order}")
    expect('<p class="glance">PR statuses as of 7 Oct 2026, 18:00 UTC.</p>' in page, "the card says when the PRs' statuses were read")
    soon = re.findall(r'<li class="dated"><a class="when" href="#(on-[\d-]+)"><time>(.*?)</time></a> <span>(.*?)</span></li>', between(ball, "<h3>A date</h3>", "</ul>"))
    renovate = ("on-2026-10-12", "Mon 12 Oct", 'Renovate\'s weekly run <span class="automated">Automated</span>')
    expect(soon == [renovate, ("on-2026-10-14", "Wed 14 Oct", "Production deploys freeze until the 21st")], f"a date coming up holds the ball too, soonest first, each linked to its day, and an automated run marked Automated: {soon}")
    expect('Renovate\'s weekly run <span class="automated">Automated</span>' in between(page, 'id="coming-up"', "</section>"), "the agenda marks the automated run too")
    expect("<th>Waits on the owner</th>" in phase["guides"] and "<th>The owner's part</th>" in phase["guides"], "the guide's statuses table names the owner, not you")
    expect('<span class="pill k-owner">Owner</span>' in phase["plan"], "an item only the owner can do reads Owner")
    expect('class="more"' not in between(ball, "<h3>A date</h3>", "</div>"), "with three dates or fewer ahead, nothing points to more")
    asked = copy_with(tmp, "asked", EXAMPLE, "build.toml", '[status.EX-3]\nstatus = "ready"', '[status.EX-3]\nstatus = "open"')
    if asked is not None:
        render(asked, tmp / "asked-out")
        index = tmp / "asked-out" / "index.html"
        owner = between(between(index.read_text(), 'id="ball"', "</section>"), "<h3>The owner</h3>", "</ul>") if index.exists() else ""
        lines = re.findall(r'<li><span class="pill ask">Merge</span> <a class="ref" href="#(ex-\d)">', owner)
        expect(lines == ["ex-2", "ex-3"], f"each of the owner's items has a line of its own, with what to do: {owner}")
    approving = copy_with(tmp, "approving", EXAMPLE, "project.toml", '[phases.plan]\nstatus = "done"\nend = 2026-10-03\n\n[phases.build]\nstatus = "now"\nstart = 2026-10-05\n\n[phases.verify]\nstatus = "now"\nstart = 2026-10-06', '[phases.plan]\nstatus = "now"\n\n[phases.build]\nstatus = "to-come"\n\n[phases.verify]\nstatus = "to-come"')
    if approving is not None and replace_in(approving, "plan.toml", "approved = 2026-10-03\n", ""):
        run = render(approving, tmp / "approving-out")
        index = tmp / "approving-out" / "index.html"
        owner = between(between(index.read_text(), 'id="ball"', "</section>"), "<h3>The owner</h3>", "</ul>") if index.exists() else ""
        expect(owner.startswith('<h3>The owner</h3><ul><li><span class="pill ask">Approve</span> <a href="#plan">the Plan</a></li>'), f"a Plan not approved yet waits on the owner, first: {run.stderr} {owner}")
    expect('href="#plan">the Plan' not in ball, "and once approved, no longer")
    expect('id="ball"' not in between(page, 'aria-labelledby="agenda-title"', "</dialog>"), "the agenda leaves who holds the ball to the header")
    expect("feat/readiness-probe" in between(page, 'id="next-session"', "</section>"), "the agenda holds the notes for the next session")
    expect("m-log" not in page and "dot" not in calendar_of(page) and all('id="log"' not in view for view in views), "there is no log: the agenda holds what happened")
    marks = re.findall(r'<li class="(m-[\w-]+)(?: count)?">(.*?)</li>', between(calendar_of(page), 'href="#on-2026-10-06">6</a>', "</td>"))
    counted = [("m-phase", "Verify starts"), ("m-s-done", '<b>1</b><span class="word"> met</span>'), ("m-s-done", '<b>1</b><span class="word"> merged</span>'), ("m-s-done", '<b>1</b><span class="word"> set</span>'), ("m-s-done", '<b>1</b><span class="word"> passed</span>')]
    expect(marks == counted, f"a day names its events and phase dates, then counts its items by what happened to them, the number apart for a phone: {marks}")
    first, third = (between(calendar_of(page), f'href="#on-2026-10-0{n}">{n}</a>', "</td>") for n in (1, 3))
    expect(">Brief, one day<" in first and ">Research starts<" in first and "Brief ends" not in first, f"a phase that starts and ends the same day is one mark, and a start says so: {first}")
    expect(">Plan approved<" in third and "Plan ends" not in third, f"an end on the day of the approval is the approval: {third}")
    expect('<p class="eyebrow">Project page</p>' in page, "the line above the title doesn't repeat the repository, which starts the title")
    expect("table.cal .m-s-blocked {" in page and "table.cal .m-event { background: transparent" in page, "in the calendar, a blocked mark has its own colour, and an event is outlined")
    merged = '[status.EX-2]\nstatus = "done"\non = 2026-10-06\nresult = "Released 1.5.0."'
    crowded = copy_with(tmp, "crowded", EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"\non = 2026-10-07', merged)
    if crowded is not None:
        render(crowded, tmp / "crowded-out")
        index = tmp / "crowded-out" / "index.html"
        text = index.read_text() if index.exists() else ""
        sixth = between(calendar_of(text), 'href="#on-2026-10-06">6</a>', "</td>")
        marks = re.findall(r'<li class="m-s-done count"><b>(\d+)</b><span class="word"> (.*?)</span></li>', sixth)
        expect(marks == [("1", "met"), ("2", "merged"), ("1", "set"), ("1", "passed")], f"two items that merged the same day are counted together: {marks}")
        day = between(text, 'id="on-2026-10-06"', "</ul>")
        day = between(text, 'id="on-2026-10-06"', "</ol>")
        merged = re.search(r'<li class="m-s-done"><span class="what">Merged:</span><ul class="list"><li><a class="ref" href="#ex-1">.*?</a></li><li><a class="ref" href="#ex-2">', day)
        expect(merged is not None, f"the agenda lists a day's items under each thing that happened to them: {day[:300]}")
    events = "".join(f'[[event]]\ndate = 2026-10-{day}\ntitle = "Release train {day}"\n\n' for day in (20, 27))
    busy = copy_with(tmp, "busy", EXAMPLE, "project.toml", "[[event]]\ndate = 2026-10-12", events + "[[event]]\ndate = 2026-10-12")
    if busy is not None:
        render(busy, tmp / "busy-out")
        index = tmp / "busy-out" / "index.html"
        held = between(index.read_text(), 'id="ball"', "</section>") if index.exists() else ""
        dates = re.findall(r'class="when" href="#on-([\d-]+)"', held)
        expect(dates == ["2026-10-12", "2026-10-14", "2026-10-20"] and '<a href="#coming-up">1 more in the agenda</a>' in held, f"the header shows the next three dates, and links to the rest: {dates}")
    calendar = calendar_of(page)
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
    empty = tmp / "empty"
    empty.mkdir()
    shutil.copy(EXAMPLE / "project.toml", empty)
    run = render(empty, tmp / "empty-out")
    expect(run.returncode == 1 and "no phase has anything to show yet" in run.stderr and not (tmp / "empty-out").exists(), f"a project with nothing written in any phase has no page yet: {run.stderr}")


def check_full(tmp):
    out = tmp / "full"
    run = render(FULL, out)
    expect(run.returncode == 0, f"full/ renders: {run.stderr}")
    if run.returncode:
        return
    expect("warning:" not in run.stderr, f"full/ renders without a warning: {run.stderr}")
    page = (out / "index.html").read_text()
    expect('data-open="retrospective"' in page, "full/ opens on its retrospective")
    expect('<span class="off t-not-needed">' in page and "Nothing here is worth copying." not in between(page, '<nav class="phases leaves"', "</nav>"), "a phase that is not needed has a tab that doesn't open")
    built = {sid: between(page, f'id="{sid}"', "</section>") for sid in ("how-it-went", "roads", "risks-closed", "what-it-took", "next", "decision-log")}
    found = between(page, 'id="found"', "</section>")
    expect("<h4>A scrape that timed out</h4>" in found and "<dt>Observed</dt><dd>A slow night took twenty.</dd>" in found, f"a definition with fields is a card of its own, titled by its term: {found[:400]}")
    expect("<td>Build</td><td></td><td>One PR, merged on its second review.</td>" in built["how-it-went"] and "<td>Reuse</td><td>Not needed</td><td>Nothing here is worth copying.</td>" in built["how-it-went"], f"the Retrospective builds how the phases went, each with its line, or why it wasn't needed: {built['how-it-went'][:600]}")
    expect('<span class="n">MX-2</span>' in built["roads"] and '<span class="n">L3</span>' in built["roads"] and "The first one covers it." in built["roads"], "and every road not taken, from every phase, with why")
    expect('<span class="n">RK1</span>' in built["risks-closed"] and 'st-done">Closed · 6 Oct<' in built["risks-closed"] and "They are hashed before export." in built["risks-closed"], "and how each risk ended")
    expect("<dt>Time</dt><dd>38 days, from 1 Sep to 8 Oct</dd>" in built["what-it-took"] and "<dt>PRs</dt><dd>1 merged: 1 MX; 1 closed unmerged</dd>" in built["what-it-took"] and "<dt>Running costs</dt>" in built["what-it-took"], f"and what it took, what the data counts first: {built['what-it-took']}")
    expect("<dt>Waiting on a trigger</dt>" in built["next"] and 'href="#t1"' in built["next"], "and what comes next, by what starts it")
    expect('<span class="key">b</span> <code>/stats</code>' in built["decision-log"] and "<h4>" not in built["decision-log"], "and every decision, with the option chosen, a batch titled only when there are several")
    expect(page.count('<span class="off t-done">') == 3, "nor does a phase done but never written, such as full/'s Brief")
    expect('id="cost"' in page and "<th>Days</th>" in page, "a table renders")
    expect('id="old-status"' in page and 'href="#old-status"' in page, "an imported page's ids and links move under its prefix")
    expect('aria-labelledby="old-status-title"' in page and 'for="old-pick"' in page, "so do the attributes that name ids")
    expect('class="figures"' in page and '<dl class="terms"><dt>Problem</dt><dd>Nobody could see' in page, "figures render, and definitions as a card")
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
    order = re.findall(r'<span class="n">(.*?)</span>', between(build, 'id="results"', "</section>"))
    expect(order == ["RK1", "MX-1"], f"results follow `ids`, leaving out what the board shows without a result: {order}")
    plan = (out / "phases" / "plan.html").read_text()
    expect("st-dropped" in plan and "The first one covers it." in plan, "a dropped item says why")
    deferred = (out / "phases" / "deferred.html").read_text()
    expect('st-blocked">Waiting<' in deferred and 'href="#l2"' in deferred, "a rule change waits in Deferred, on its lesson")
    expect("[[" not in page + plan + build + deferred, "a title that names an item links it, and leaves no brackets in a short name")
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
        expect('<details class="fold">' in retro and 'class="open-all"' not in retro, "its cards fold too, one at a time, since it has no script to open them all")
    linked = copy_with(tmp, "full-linked", FULL, "retrospective.toml", "[[MX-1]] shows", '<a href=\\"#mx-1\\">MX-1</a> shows')
    if linked is not None:
        expect(render(linked, tmp / "linked-page").returncode == 0, "on the project page, a link by hand to MX-1 has its target")
        run = render(linked, tmp / "linked-alone", "--retrospective")
        expect(run.returncode == 1 and 'a link to "#mx-1"' in run.stderr, f"alone, it has none, and the render says so: {run.stderr}")


# Each stale copy of the example: the file, the text replaced, its replacement,
# and the warning it must print. The page is still written.
STALE = [
    ("plan.toml", '["Carries out", ["[[D1]]", "[[D2]]"]]', '["Carries out", ["[[D1]]"]]', "D2 is a decision taken, but no PR or setting names it or needs it"),
    ("build.toml", 'on = 2026-10-06\nresult = "Released 1.4.0.', 'on = 2026-10-06\nnote = "Released 1.4.0.', "EX-1 is a merged PR without a `result`"),
    ("build.toml", '[status.EX-2]\nstatus = "open"', '[status.EX-2]\nstatus = "done"', "C2 is `blocked`, but everything it needs is done"),
    ("deferred.toml", 'waits = "the metrics stack"', 'waits = "[[EX-1]]"', "T1 waits on EX-1, which is done"),
    ("build.toml", 'production"\nstatus = "done"', 'production"\nstatus = "open"', "EX-3 is `ready`, but needs Q1, which isn't done"),
    ("analysis.toml", 'recommended = "a"\nchosen = "a"', 'recommended = "a"', "D1 is `done`, but none of its options is `chosen`"),
    ("plan.toml", "amended = { on = 2026-10-07", "amended = { on = 2026-10-02", "EX-3 is amended on 2 Oct, before its phase was approved"),
    ("analysis.toml", 'id = "D2"\ntitle = "What readiness waits for"\n', 'id = "D2"\ntitle = "What readiness waits for"\namended = { on = 2026-10-01, why = "the cache" }\n', "D2 is amended on 1 Oct, before its phase ended on 2 Oct"),
    ("project.toml", "read_at = 2026-10-07T18:00:00", "read_at = 2026-10-06T18:00:00", "`read_at` is older than the newest status, of 7 Oct"),
    ("project.toml", "updated = 2026-10-07", "updated = 2026-10-06", "the notes for the next session date from 6 Oct, before the last change"),
    ("plan.toml", 'why = "the answer to [[Q1]]" }', 'why = "[[Q1]]\'s answer" }', "plan.toml item EX-3: [[Q1]]'s reads as \"Q1 The probe's timeout in production's\": put the link after its noun"),
    ("build.toml", 'production"\nstatus = "done"\non = 2026-10-07', 'production"\nstatus = "done"\non = 2026-10-04', "Q1 is a question in Build dated 4 Oct, before Build started on 5 Oct"),
]

# Each broken copy: the project it copies, the file, the text replaced, its
# replacement, and the message.
BROKEN = [
    (EXAMPLE, "research.toml", '[[section]]\nid = "pieces"', '[[section]]\nid = "roads"\ntitle = "Roads not taken"\nkind = "roads"\n\n[[section]]\nid = "pieces"', "a `roads` section is built for the Retrospective"),
    (EXAMPLE, "project.toml", '[phases.build]\nstatus = "now"', '[phases.build]\nstatus = "done"', "Build is done, but EX-2 is still `open`: new work reopens it"),
    (EXAMPLE, "project.toml", '[phases.verify]\nstatus = "now"', '[phases.verify]\nstatus = "done"', "Verify is done, but Build isn't: it ends only after it"),
    (EXAMPLE, "project.toml", 'status = "now"\nstart = 2026-10-05', 'status = "now"\nstart = 2026-10-02', "Build starts on 2 Oct, before Plan ends on 3 Oct: say why, in `early`"),
    (EXAMPLE, "project.toml", '[phases.build]\nstatus = "now"', '[phases.build]\nstatus = "now"\nreopened = [{ on = 2026-10-06 }]', "each of `reopened` is { ended = <date>, on = <date> }"),
    (EXAMPLE, "plan.toml", '[[section]]\nid = "settings"', '[[section]]\nid = "queues"\nkind = "prose"\nbody = "<p>One at a time.</p>"\n\n[[section]]\nid = "settings"', "Plan holds only items sections"),
    (EXAMPLE, "analysis.toml", '[[section]]\nid = "decisions"', '[[section]]\nid = "why"\nkind = "prose"\nbody = "<p>Why these.</p>"\n\n[[section]]\nid = "decisions"', "Analysis holds only items sections"),
    (EXAMPLE, "build.toml", '[[section]]\nid = "questions"', '[[section]]\nid = "log"\nkind = "prose"\nbody = "<p>What happened.</p>"\n\n[[section]]\nid = "questions"', "Build holds only board, results and items sections: what happened is in the Agenda"),
    (EXAMPLE, "verify.toml", '[[section]]\nid = "checks"', '[[section]]\nid = "on-the-way"\nkind = "prose"\nbody = "<p>What this run couldn\'t settle.</p>"\n\n[[section]]\nid = "checks"', "Verify holds only items and results sections"),
    (EXAMPLE, "plan.toml", '[[section]]\nid = "settings"', '[[section]]\nid = "more-prs"\ntitle = "More PRs"\nkind = "items"\ntype = "pr"\n\n[[section]]\nid = "settings"', "plan.toml section more-prs: it shows nothing but its title"),
    (EXAMPLE, "research.toml", '[[section]]\nid = "pieces"', '[[section]]\nid = "note"\ntitle = "A note"\nkind = "prose"\nbody = "<p></p>"\n\n[[section]]\nid = "pieces"', "research.toml section note: it shows nothing but its title"),
    (EXAMPLE, "research.toml", 'type = "piece"', 'type = "decision"', "a card of type `decision` belongs in Analysis, not in Research"),
    (EXAMPLE, "analysis.toml", '[[section]]\nid = "decisions"', '[[section]]\nid = "compared"\ntitle = "Compared"\nkind = "table"\nhead = ["Option"]\nrows = [["a"]]\n\n[[section]]\nid = "decisions"', "Analysis holds only items sections"),
    (EXAMPLE, "analysis.toml", 'id = "D2"', 'id = "D1"', "this id is used twice"),
    (EXAMPLE, "research.toml", '"[[D1]]"', '"<a href=\\"#d9\\">D9</a>"', 'a link to "#d9"'),
    (EXAMPLE, "research.toml", '"[[D1]]"', '"[[D9]]"', "[[D9]] names no item"),
    (EXAMPLE, "research.toml", '"[[D1]]"', '"<a href=\\"#d1\\">[[D1]]</a>"', "a link inside a link"),
    (EXAMPLE, "research.toml", 'type = "piece"', 'type = "pieces"', "`type` is one of"),
    (EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"', '[status.EX-2]\nstatus = "waiting"', "status `waiting` is not one of"),
    (EXAMPLE, "deferred.toml", 'waits = "the metrics stack"\n', "", "a blocked item says what it waits on"),
    (EXAMPLE, "deferred.toml", 'waits = "the metrics stack"', 'waits = "owner"', "an item that waits on the owner is `open`"),
    (EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"', '[status.EX-2]\nstatus = "to-move"', "an item to be moved names the project that takes it, in `to`"),
    (EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"', '[status.EX-2]\nstatus = "moved"\nto = "the next project"', "a moved item links its card on the other project's page"),
    (EXAMPLE, "build.toml", '[status.EX-1]\nstatus = "done"', '[status.EX-1]\nstatus = "deferred"', "a deferred item says what it waits on"),
    (FULL, "plan.toml", 'status = "dropped"\nwhy = "The first one covers it."', 'status = "happened"\nresult = "Two were needed."', "only a risk happens"),
    (FULL, "plan.toml", 'status = "done"\non = 2026-10-06\nresult = "They are hashed before export."', 'status = "happened"\non = 2026-10-06', "a risk that happened names, in `result`"),
    (EXAMPLE, "project.toml", 'why = "Two routes', 'what = "Two routes', "a phase that is not needed says why"),
    (EXAMPLE, "project.toml", '[phases.research]\nstatus = "done"', '[phases.research]\nstatus = "not-needed"\nwhy = "Nothing to find."', "research.toml: Research is not needed, so it holds nothing"),
    (EXAMPLE, "brief.toml", 'use = "read"', 'use = "write"', "`use` is what the project does with it: change, read, new"),
    (EXAMPLE, "plan.toml", 'pull/12"\nfields = [', 'pull/12"\nstatus = "done"\nfields = [', "status is set twice"),
    (EXAMPLE, "research.toml", "<code>/api</code>", "<code>/api", "is never closed"),
    (EXAMPLE, "project.toml", 'objective = "health-checks"', 'objective = "Health Checks"', "kebab-case"),
    (EXAMPLE, "deferred.toml", 'id = "work"', 'id = "work', "not valid TOML"),
    (EXAMPLE, "build.toml", "[status.EX-3]", "[status.EX-9]", "no item has this id"),
    (EXAMPLE, "project.toml", "[phases.reuse]", "[phases.templating]", "[phases.templating] is not a phase"),
    (EXAMPLE, "project.toml", "read_at = 2026-10-07T18:00:00", 'read_at = "7 October"', "`read_at` is when the state was read"),
    (EXAMPLE, "project.toml", "date = 2026-10-12\n", "", "an event has a `date`"),
    (EXAMPLE, "project.toml", 'short = "Renovate"\nautomated = true', 'short = "Renovate"\nautomated = "yes"', "`automated` is true or false"),
    (EXAMPLE, "plan.toml", 'pull/14"\nneeds = ["EX-1"]', 'pull/14"\nneeds = ["EX-9"]', "`needs` names EX-9, which no item has"),
    (EXAMPLE, "analysis.toml", 'chosen = "a"', 'chosen = "c"', "`chosen` is c, which no option has"),
    (EXAMPLE, "analysis.toml", '["b", "A second port', '["A second port', "`options` is a list of [key, text] pairs"),
    (EXAMPLE, "plan.toml", '["Carries out", ["[[D1]]", "[[D2]]"]]', '["Carries out", ["[[D1]]", 2]]', "each of `fields` is a [label, text] pair, its text one string or a list of them"),
    (EXAMPLE, "plan.toml", 'short = "Liveness probe"\n', 'short = "Liveness probe"\nneeds = ["EX-2"]\n', "`needs` loops: EX-1 → EX-2 → EX-1"),
    (EXAMPLE, "plan.toml", ', why = "the answer to [[Q1]]" }', " }", "`amended` is"),
    (EXAMPLE, "plan.toml", 'url = "https://github.com/example/example-service/pull/12"', 'url = "github.com/example/example-service/pull/12"', "`url` is an https:// address"),
    (FULL, "build.toml", 'cells = [["MX-1"], ["MX-2"]]', 'cells = [["MX-1"], ["MX-9"]]', "the board names MX-9"),
    (EXAMPLE, "plan.toml", "approved = 2026-10-03\n", "", "plan.toml: the Plan is done, but not approved: give it `approved`"),
    (EXAMPLE, "plan.toml", "approved = 2026-10-03", "approved = 2026-10-06", "Build starts on 5 Oct, before the Plan's approval on 6 Oct: say why, in `early`"),
    (EXAMPLE, "analysis.toml", 'waits for"\nstatus = "done"\non = 2026-10-02', 'waits for"\nstatus = "open"', "D2 isn't taken, but the Plan was approved on 3 Oct"),
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
    expect("warning: project.toml: the state was read at 18:00 UTC on 7 Oct, more than 15 minutes before this render" in run.stderr, f"a render for a publish warns when the state was read long before: {run.stderr}")
    now = datetime.datetime.now(datetime.UTC)
    fresh = copy_with(tmp, "fresh", EXAMPLE, "project.toml", "read_at = 2026-10-07T18:00:00", f"read_at = {now:%Y-%m-%dT%H:%M:00}")
    if fresh is not None:
        run = render(fresh, tmp / "fresh-out", "--since", str(EXAMPLE))
        expect(run.returncode == 0 and "more than 15 minutes" not in run.stderr, f"and not when it was just read: {run.stderr}")
    expect(render(EXAMPLE, tmp / "since-none", "--since", str(tmp / "nowhere")).returncode == 2, "--since names a directory that exists")

    merged = '[status.EX-2]\nstatus = "done"\non = 2026-10-09\nresult = "Released 1.5.0."'
    data = copy_with(tmp, "since", EXAMPLE, "build.toml", '[status.EX-2]\nstatus = "open"\non = 2026-10-07', merged)
    if data is None:
        return
    added = '[[section.item]]\nid = "EX-4"\ntitle = "<code>docs: the probes in the README</code>"\nkind = "patch"\nneeds = ["EX-2"]\n\n[[section]]\nid = "settings"'
    amended = added.replace('needs = ["EX-2"]', 'needs = ["EX-2"]\namended = { on = 2026-10-09, why = "the README, found silent on the probes" }')
    edited = [
        replace_in(data, "plan.toml", "stops answering is restarted.", "stops answering is restarted within a minute."),
        replace_in(data, "plan.toml", '["Carries out", ["[[D1]]", "[[D2]]"]]', '["Carries out", ["[[D2]]", "[[D1]]"]]'),
        replace_in(data, "plan.toml", '[[section]]\nid = "settings"', amended),
        replace_in(data, "project.toml", "updated = 2026-10-07", "updated = 2026-10-09"),
    ]
    if not all(edited):
        return
    run = render(data, tmp / "since-out", "--since", str(EXAMPLE))
    expect(run.returncode == 0, f"a changed copy renders: {run.stderr}")
    expect("  Plan: EX-1: Done when edited; EX-2: Carries out edited; EX-4 added.\n" in run.stdout, f"edited fields, a list among them, and a new item: {run.stdout}")
    expect("  Build: EX-2 To merge → Merged.\n" in run.stdout, f"a status in its type's words: {run.stdout}")
    expect("  project.toml: `handoff` edited.\n" in run.stdout and "read_at" not in run.stdout, f"project.toml's changes, read_at aside: {run.stdout}")
    unmarked = copy_with(tmp, "unmarked", EXAMPLE, "plan.toml", '[[section]]\nid = "settings"', added)
    if unmarked is not None:
        run = render(unmarked, tmp / "unmarked-out", "--since", str(EXAMPLE))
        expect(run.returncode == 1 and "plan.toml: EX-4 is new since the published data, which had the Plan approved: an item added to it is an amendment" in run.stderr, f"an item added to an approved phase without `amended` stops the render: {run.stderr}")
    asked = '[[section.item]]\nid = "Q2"\ntitle = "The probe\'s path behind the proxy"\nstatus = "open"\n'
    live = copy_with(tmp, "live", EXAMPLE, "build.toml", '[[section.item]]\nid = "Q1"', asked + '\n[[section.item]]\nid = "Q1"')
    if live is not None:
        run = render(live, tmp / "live-out", "--since", str(EXAMPLE))
        expect(run.returncode == 0 and "  Build: Q2 added;" in run.stdout, f"Build takes new work without `amended`: {run.stderr}")

    r2 = '\n\n[[section.item]]\nid = "R2"\ntitle = "What the platform does with a probe"\nfields = [\n  ["Today", "It restarts a process whose liveness probe fails three times in a row, and sends it traffic only while its readiness probe passes."],\n  ["Raises", "[[D2]]"],\n]\n'
    deleted = copy_with(tmp, "deleted", EXAMPLE, "research.toml", r2, "\n")
    if deleted is not None:
        run = render(deleted, tmp / "deleted-out", "--since", str(EXAMPLE))
        expect(run.returncode == 1 and "research.toml: R2 is gone since the published data: an item is never deleted, but given the status `dropped`, with `why`" in run.stderr, f"an item that is gone stops the render: {run.stderr}")


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
