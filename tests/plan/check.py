"""python3 tests/plan/check.py, from the repository root.

Runs the project-page renderer the plan concern ships against its example, in
both modes, against full/, which uses every section kind the example leaves
out, and against broken copies of the example. Each broken copy must fail with
its own message and write nothing; everything else must render.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path("fragments/concerns/plan/tasks/project-page")
HERE = Path(__file__).resolve().parent
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


def manifest(page):
    return re.search(r'<script type="application/json" id="anchors">(.*?)</script>', page).group(1)


def check_example(tmp):
    out = tmp / "example"
    run = render(KIT / "example", out)
    expect(run.returncode == 0, f"the example renders: {run.stderr}")
    if run.returncode:
        return
    page = (out / "index.html").read_text()
    files = sorted(p.name for p in (out / "phases").iterdir())
    expect(files == ["analysis.html", "later.html", "plan.html", "research.html"], f"the phases loaded on demand: {files}")
    expect("<title>example-service-health-checks</title>" in page, "the title is <repo>-<objective>")
    expect('data-open="build"' in page, "the page opens on the phase in progress")
    waiting = page[page.index('class="waiting"'):page.index("</section>", page.index('class="waiting"'))]
    expect("EX-2" in waiting and "Q1" in waiting and "EX-1" not in waiting, "Waiting on you lists the open items, and only those")
    expect('"ex-1":"plan"' in manifest(page), "a link to EX-1 opens the plan")
    plan = (out / "phases" / "plan.html").read_text()
    expect("st-open" not in plan, "the plan shows its PRs as approved, without the build's statuses")
    analysis = (out / "phases" / "analysis.html").read_text()
    expect('st-done">Taken<' in analysis, "a decision that is done reads Taken")
    expect('st-done">Merged<' in page and 'st-open">To merge<' in page, "a PR reads Merged, or To merge while open")
    expect('st-blocked">Open<' in page and "closes with" in page, "an open risk names the step that closes it")
    expect('<a class="ref" href="#ex-1"><b>EX-1</b> Liveness probe</a>' in plan, "[[EX-1]] links with its short title")
    for chip in re.findall(r'<a class="chip.*?</a>', page):
        expect("<a " not in chip[2:], f"a chip holds no link of its own: {chip[:80]}")

    inline = tmp / "inline"
    run = render(KIT / "example", inline, "--inline")
    expect(run.returncode == 0, f"the example renders inline: {run.stderr}")
    if run.returncode == 0:
        expect(not (inline / "phases").exists(), "--inline writes no phase files")
        expect('id="ex-1"' in (inline / "index.html").read_text(), "--inline holds every phase")


def check_full(tmp):
    out = tmp / "full"
    run = render(HERE / "full", out)
    expect(run.returncode == 0, f"full/ renders: {run.stderr}")
    if run.returncode:
        return
    page = (out / "index.html").read_text()
    expect('data-open="retrospective"' in page, "full/ opens on its retrospective")
    expect('id="old-status"' in page and 'href="#old-status"' in page, "an imported page's ids and links move under its prefix")
    expect('aria-labelledby="old-status-title"' in page and 'for="old-pick"' in page, "so do the attributes that name ids")
    expect('class="figures"' in page and 'class="defs"' in page, "figures and definitions render")
    expect(".imported-marker" in page, "a project's own stylesheet is appended")
    build = (out / "phases" / "build.html").read_text()
    expect(build.index("MX-2") < build.index("<b>MX-1</b>", build.index('class="results"')), "results follow `ids`")
    expect("st-dropped" in build and "The first one covers it." in build, "a dropped item says why")


# Each broken copy: the file, the text replaced, its replacement, and the message.
BROKEN = [
    ("analysis.toml", 'id = "D2"', 'id = "D1"', "this id is used twice"),
    ("research.toml", '"[[D1]]"', '"<a href=\\"#d9\\">D9</a>"', 'a link to "#d9"'),
    ("research.toml", '"[[D1]]"', '"[[D9]]"', "[[D9]] names no item"),
    ("research.toml", 'type = "piece"', 'type = "pieces"', "`type` is one of"),
    ("build.toml", 'status = "open"\nresult', 'status = "waiting"\nresult', "status `waiting` is not one of"),
    ("build.toml", 'waits = "[[EX-2]]"\n', "", "a blocked item says what it waits on"),
    ("project.toml", 'why = "Two routes', 'what = "Two routes', "a phase that is not needed says why"),
    ("plan.toml", 'kind = "minor"\nfields = [\n  ["Branch", "<code>feat/liveness', 'kind = "minor"\nstatus = "done"\nfields = [\n  ["Branch", "<code>feat/liveness', "status is set twice"),
    ("research.toml", "<code>/api</code>", "<code>/api", "is never closed"),
    ("project.toml", 'objective = "health-checks"', 'objective = "Health Checks"', "kebab-case"),
    ("build.toml", '["EX-2", "RK1"]', '["EX-9", "RK1"]', "the board names EX-9"),
    ("later.toml", 'id = "deferred"', 'id = "deferred', "not valid TOML"),
    ("build.toml", 'changed = ["results", "q1"]', 'changed = ["results", "q9"]', "`changed` names q9"),
]


def check_broken(tmp):
    for index, (name, old, new, message) in enumerate(BROKEN):
        data = tmp / f"broken-{index}"
        shutil.copytree(KIT / "example", data)
        path = data / name
        text = path.read_text()
        if old not in text:
            failed.append(f"broken case {index}: {old!r} is not in {name}")
            continue
        path.write_text(text.replace(old, new, 1))
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
        check_broken(tmp)
    for what in failed:
        print(f"FAIL: {what}", file=sys.stderr)
    print(f"{'FAILED' if failed else 'passed'}: the example, full/ and {len(BROKEN)} broken copies")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
