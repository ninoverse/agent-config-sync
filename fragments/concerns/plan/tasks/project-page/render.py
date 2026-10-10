#!/usr/bin/env python3
"""Builds a project page from its TOML data, and checks it.

Usage: python3 render.py <data-dir> <out-dir> [--inline]

<data-dir> holds project.toml and a <phase>.toml for each phase with content.
<out-dir> gets index.html, the page to publish, and phases/<phase>.html for
every other phase with content, which the page loads when that phase is
picked. --inline puts every phase in index.html instead, for a preview or a
small project.

Exits 0 once the page is written, after printing a warning for each state that
looks stale; 1 when the data or the page has a problem, writing nothing and
printing one line per problem on stderr; 2 on a usage error. Needs Python 3.11
or later, and nothing outside its standard library.
"""

import calendar
import datetime
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit("render.py needs Python 3.11 or later, for tomllib.")

import tomllib  # noqa: E402  (after the version check, which names the cause)

HERE = Path(__file__).resolve().parent

PHASES = [
    ("brief", "Brief"),
    ("research", "Research"),
    ("analysis", "Analysis"),
    ("plan", "Plan"),
    ("build", "Build"),
    ("verify", "Verify"),
    ("reuse", "Reuse"),
    ("retrospective", "Retrospective"),
    ("later", "For later"),
]
PHASE_NAME = dict(PHASES)
PHASE_STATUS = {"done": "Done", "now": "Now", "to-come": "To come", "not-needed": "Not needed"}
ITEM_STATUS = {"done": "Done", "open": "Open", "ready": "Ready", "blocked": "Blocked", "dropped": "Dropped"}
UNFINISHED = {"open", "ready", "blocked"}
KINDS = {"major": "Major", "minor": "Minor", "patch": "Patch", "you": "You", "together": "Together"}
# What a status reads as for each type of item, and what the user does while one is open.
TYPES = {
    "piece": {"labels": {}, "ask": "Read"},
    "rule": {"labels": {"dropped": "Retired"}, "ask": "Confirm"},
    "criterion": {"labels": {"open": "To agree", "blocked": "Not met yet", "done": "Met"}, "ask": "Agree"},
    "decision": {"labels": {"open": "To decide", "done": "Taken", "dropped": "Withdrawn"}, "ask": "Decide"},
    "question": {"labels": {"open": "To answer", "done": "Answered", "dropped": "Withdrawn"}, "ask": "Answer"},
    "pr": {"labels": {"open": "To merge", "done": "Merged", "dropped": "Closed"}, "ask": "Merge"},
    "setting": {"labels": {"open": "To set", "done": "Set", "dropped": "Not needed"}, "ask": "Set"},
    "risk": {"labels": {"open": "To accept", "blocked": "Open", "done": "Closed", "dropped": "Accepted"}, "ask": "Accept", "waits": "closes with"},
    "check": {"labels": {"open": "To check", "blocked": "Waiting", "done": "Passed", "dropped": "Skipped"}, "ask": "Check"},
    "lesson": {"labels": {"open": "To review", "done": "Adopted", "dropped": "Not adopted"}, "ask": "Review"},
    "later": {"labels": {"blocked": "Waiting", "done": "Picked up"}, "ask": "Start"},
}
SECTION_KINDS = ("prose", "table", "items", "board", "results", "log", "figures", "defs")
SOURCES = {"coined": "Coined for this project", "borrowed": "Borrowed from elsewhere"}

KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ITEM_ID = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*")
# [[D1]] in any text: a link to the item, with its id and its short title.
REF = re.compile(r"\[\[([^\]]*)\]\]")
# Only an anchor made of these reaches location.hash from an artifact's link.
ANCHOR = re.compile(r"[A-Za-z0-9._~-]+")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Oxanium:wght@500;600;700'
    '&amp;family=Quicksand:wght@400;500;600;700&amp;display=swap" rel="stylesheet">'
)

problems, warnings = [], []
ITEMS = {}  # every item of every phase, by id, in phase order
TODAY = None  # the day the state was read


def problem(where, text):
    problems.append(f"{where}: {text}")


def warn(where, text):
    warnings.append(f"{where}: {text}")


def esc(text):
    return html.escape(str(text), quote=True)


def text_of(fragment):
    """An HTML fragment as plain text, for the places that show a short label."""
    return " ".join(re.sub(r"<[^>]+>", "", fragment).split())


def anchor_of(item_id):
    return item_id.lower()


def load(path):
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        problem(path.name, f"not valid TOML: {error}")
        return None


def required(data, key, where):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        problem(where, f"`{key}` is required")


def as_date(value, where, field):
    """A TOML date, or a string such as 2026-10-07; None when there is none."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            pass
    problem(where, f"`{field}` is a date, such as 2026-10-07")
    return None


def quiet_date(value):
    """As as_date, without reporting: for a second reading of a date already checked."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def day(date):
    """A date as the page shows it: 7 Oct, with its year when that isn't the read's."""
    text = f"{date.day} {date:%b}"
    return text if TODAY and date.year == TODAY.year else f"{text} {date.year}"


def weekday(date):
    return f"{date:%a} {day(date)}"


# ------------------------------------------------------------------ the data


def read_project(data_dir):
    global TODAY
    path = data_dir / "project.toml"
    if not path.is_file():
        print(f"{path}: no such file. A project's data starts with project.toml.", file=sys.stderr)
        sys.exit(1)
    project = load(path)
    if project is None:
        print(problems[0], file=sys.stderr)
        sys.exit(1)
    for key in ("repo", "objective", "summary"):
        required(project, key, "project.toml")
    read_at = project.get("read_at")
    if isinstance(read_at, str):
        try:
            read_at = datetime.datetime.strptime(read_at.replace("T", " "), "%Y-%m-%d %H:%M")
        except ValueError:
            read_at = None
    if not isinstance(read_at, datetime.datetime):
        problem("project.toml", "`read_at` is when the state was read, in UTC, such as 2026-10-07 18:00")
        read_at = datetime.datetime(1970, 1, 1)
    project["read_at"] = read_at
    TODAY = read_at.date()
    objective = project.get("objective", "")
    if isinstance(objective, str) and objective and not KEBAB.fullmatch(objective):
        problem("project.toml", f"`objective` is `{objective}`; it is kebab-case, such as agentcfg-adoption, since the title is <repo>-<objective>")
    phases = project.get("phases", {})
    for key in phases:
        if key not in PHASE_NAME:
            problem("project.toml", f"[phases.{key}] is not a phase; the phases are {', '.join(PHASE_NAME)}")
    project["status"] = {}
    for key, _ in PHASES:
        entry = phases.get(key, {})
        where = f"project.toml [phases.{key}]"
        status = entry.get("status", "to-come")
        if status not in PHASE_STATUS:
            problem(where, f"status `{status}` is not one of {', '.join(PHASE_STATUS)}")
            status = "to-come"
        if status == "not-needed" and not entry.get("why"):
            problem(where, "a phase that is not needed says why, in `why`")
        project["status"][key] = {
            "status": status,
            "why": entry.get("why", ""),
            "start": as_date(entry.get("start"), where, "start"),
            "end": as_date(entry.get("end"), where, "end"),
        }
    for index, entry in enumerate(project.get("glossary", [])):
        where = f"project.toml [[glossary]] {index + 1}"
        required(entry, "term", where)
        required(entry, "text", where)
        if entry.get("source", "coined") not in SOURCES:
            problem(where, f"`source` is one of {', '.join(SOURCES)}")
    for index, event in enumerate(project.get("event", [])):
        where = f"project.toml [[event]] {index + 1}"
        required(event, "title", where)
        event["date"] = as_date(event.get("date"), where, "date")
        if event["date"] is None:
            problem(where, "an event has a `date`")
    handoff = project.get("handoff")
    if handoff is not None:
        handoff["updated"] = as_date(handoff.get("updated"), "project.toml [handoff]", "updated")
        if not all(isinstance(note, str) for note in handoff.get("notes", [])):
            problem("project.toml [handoff]", "`notes` is a list of texts")
    return project


def read_phases(data_dir):
    data = {}
    for key, _ in PHASES:
        path = data_dir / f"{key}.toml"
        if path.is_file():
            loaded = load(path)
            if loaded is not None:
                data[key] = loaded
                loaded["approved"] = as_date(loaded.get("approved"), f"{key}.toml", "approved")
                for index, entry in enumerate(loaded.get("changelog", [])):
                    entry["date"] = as_date(entry.get("date"), f"{key}.toml [[changelog]] {index + 1}", "date")
    return data


def is_pair(value):
    return isinstance(value, list) and len(value) == 2 and all(isinstance(part, str) for part in value)


def check_status(entry, where):
    status = entry.get("status")
    if status is None:
        return
    if status not in ITEM_STATUS:
        problem(where, f"status `{status}` is not one of {', '.join(ITEM_STATUS)}")
    elif status == "blocked" and not entry.get("waits") and not entry.get("needs"):
        problem(where, "a blocked item says what it waits on, in `waits` or `needs`")
    elif status == "dropped" and not entry.get("why"):
        problem(where, "a dropped item says why, in `why`")


def collect_items(phases):
    """Every item, by id, in phase order, with the status it ends up with."""
    anchors = set()
    for key, data in phases.items():
        for section in data.get("section", []):
            if section.get("kind") != "items":
                continue
            for item in section.get("item", []):
                item_id = item.get("id", "")
                where = f"{key}.toml item {item_id or '(no id)'}"
                if not isinstance(item_id, str) or not ITEM_ID.fullmatch(item_id):
                    problem(where, "`id` is required: letters, digits and single dashes or dots, such as AC-1 or D61")
                    continue
                if anchor_of(item_id) in anchors:
                    problem(where, "this id is used twice")
                    continue
                anchors.add(anchor_of(item_id))
                required(item, "title", where)
                check_status(item, where)
                item_type = item.get("type", section.get("type"))
                if item_type is not None and item_type not in TYPES:
                    problem(where, f"`type` is one of {', '.join(TYPES)}")
                    item_type = None
                if item.get("kind") and item["kind"] not in KINDS:
                    problem(where, f"`kind` is one of {', '.join(KINDS)}")
                if not all(is_pair(field) for field in item.get("fields", [])):
                    problem(where, "each of `fields` is a [label, text] pair")
                needs = item.get("needs", [])
                if not (isinstance(needs, list) and all(isinstance(n, str) for n in needs)):
                    problem(where, "`needs` is a list of item ids")
                    needs = []
                amended = item.get("amended")
                if amended is not None:
                    if not isinstance(amended, dict) or not amended.get("why"):
                        problem(where, '`amended` is { on = <date>, why = "..." }')
                        amended = None
                    else:
                        amended = {"on": as_date(amended.get("on"), where, "amended.on"), "why": amended["why"]}
                ITEMS[item_id] = dict(
                    item,
                    phase=key,
                    where=where,
                    type=item_type,
                    needs=needs,
                    amended=amended,
                    due=as_date(item.get("due"), where, "due"),
                    on=as_date(item.get("on"), where, "on"),
                    status_from=key if "status" in item else None,
                )
    for key, data in phases.items():
        for item_id, entry in data.get("status", {}).items():
            where = f"{key}.toml [status.{item_id}]"
            if item_id not in ITEMS:
                problem(where, "no item has this id")
                continue
            item = ITEMS[item_id]
            if item["status_from"]:
                problem(where, f"{item_id}'s status is set twice, here and in {item['status_from']}.toml")
                continue
            check_status(dict(entry, needs=item["needs"]), where)
            for field in ("status", "waits", "why", "result"):
                if field in entry:
                    item[field] = entry[field]
            if "on" in entry:
                item["on"] = as_date(entry["on"], where, "on")
            item["status_from"] = key


def link_items():
    """`needs` checked for unknown ids and loops; backlinks from needs and references."""
    for item_id, item in ITEMS.items():
        item["needed_by"], item["named_by"] = [], []
        for need in item["needs"]:
            if need not in ITEMS:
                problem(item["where"], f"`needs` names {need}, which no item has")
    state = {}

    def visit(item_id, path):
        state[item_id] = "open"
        for need in ITEMS[item_id]["needs"]:
            if need not in ITEMS:
                continue
            if state.get(need) == "open":
                loop = path[path.index(need):] + [need] if need in path else [item_id, need]
                problem(ITEMS[item_id]["where"], f"`needs` loops: {' → '.join(loop)}")
            elif need not in state:
                visit(need, path + [need])
        state[item_id] = "done"

    for item_id in ITEMS:
        if item_id not in state:
            visit(item_id, [item_id])
    for item_id, item in ITEMS.items():
        for need in item["needs"]:
            if need in ITEMS:
                ITEMS[need]["needed_by"].append(item_id)
        texts = [item.get("title", ""), item.get("waits", ""), item.get("why", ""), item.get("result", "")]
        texts += [value for _, value in (f for f in item.get("fields", []) if is_pair(f))]
        if item["amended"]:
            texts.append(item["amended"]["why"])
        for ref in REF.findall(" ".join(str(text) for text in texts)):
            if ref in ITEMS and ref != item_id and ref not in item["needs"] and item_id not in ITEMS[ref]["named_by"]:
                ITEMS[ref]["named_by"].append(item_id)


def check_states(project, phases):
    """Warnings for what looks stale: the mistakes a page makes when it isn't re-read.
    They name statuses as the data writes them, since the data is what to fix."""
    statuses = project["status"]
    has_prs = any(item["type"] == "pr" for item in ITEMS.values())
    for item_id, item in ITEMS.items():
        where, status = item["where"], item.get("status")
        if status in UNFINISHED and item["status_from"] and statuses[item["status_from"]]["status"] == "done":
            warn(where, f"{PHASE_NAME[item['status_from']]} is done, but {item_id} is still `{status}`")
        if item["type"] == "decision" and status == "done" and has_prs:
            if not any(ITEMS[other]["type"] == "pr" for other in item["needed_by"] + item["named_by"]):
                warn(where, f"{item_id} is a decision taken, but no PR names it or needs it")
        if item["type"] == "pr" and status == "done" and not item.get("result"):
            warn(where, f"{item_id} is a merged PR without a `result`")
        needs = [need for need in item["needs"] if need in ITEMS]
        if status == "blocked" and needs and all(ITEMS[need].get("status") == "done" for need in needs):
            if not item.get("waits"):
                warn(where, f"{item_id} is `blocked`, but everything it needs is done: is it `ready`?")
        if status == "blocked" and item.get("waits"):
            named = [ref for ref in REF.findall(item["waits"]) if ref in ITEMS]
            if named and all(ITEMS[ref].get("status") == "done" for ref in named):
                warn(where, f"{item_id} waits on {', '.join(named)}, which {'is' if len(named) == 1 else 'are'} done: is it `ready`?")
        if status == "ready":
            pending = [need for need in needs if ITEMS[need].get("status") != "done"]
            if pending:
                warn(where, f"{item_id} is `ready`, but needs {', '.join(pending)}, which {'isn' if len(pending) == 1 else 'aren'}'t done")
        if item["due"] and item["due"] < TODAY and status != "done":
            warn(where, f"{item_id} was due on {day(item['due'])}")
        if item["amended"] and item["amended"]["on"]:
            approved = phases.get(item["phase"], {}).get("approved")
            if approved and item["amended"]["on"] < approved:
                warn(where, f"{item_id} is amended on {day(item['amended']['on'])}, before its phase was approved")
    changed = [entry["date"] for data in phases.values() for entry in data.get("changelog", []) if entry.get("date")]
    if changed and max(changed) > TODAY:
        warn("project.toml", f"`read_at` is older than the newest changelog entry, of {day(max(changed))}: read the state again")
    handoff = project.get("handoff")
    if handoff and handoff.get("updated") and changed and handoff["updated"] < max(changed):
        warn("project.toml [handoff]", f"the notes for the next session date from {day(handoff['updated'])}, before the last change")


# ------------------------------------------------------------------ rendering


def label_of(item):
    """The status in the words of the item's type: a decision is Taken, a PR Merged."""
    status = item["status"]
    return TYPES.get(item.get("type"), {}).get("labels", {}).get(status, ITEM_STATUS[status])


def ask_of(item):
    return item.get("ask") or TYPES.get(item.get("type"), {}).get("ask", "Open")


def short_of(item):
    """The name an item goes by in links: its `short`, or its title as plain text,
    with the ids it names left bare so that a link never holds another."""
    return item.get("short") or REF.sub(lambda m: m.group(1), text_of(item.get("title", "")))


def ref_html(item_id):
    return f'<a class="ref" href="#{anchor_of(item_id)}"><b>{esc(item_id)}</b> {short_of(ITEMS[item_id])}</a>'


def expand_refs(text, where):
    """[[D1]] as a link to D1, with its short title. An id nothing has is a problem."""

    def replace(match):
        item_id = match.group(1)
        if item_id not in ITEMS:
            problem(where, f"[[{item_id}]] names no item")
            return match.group(0)
        return ref_html(item_id)

    return REF.sub(replace, text)


def refs_as_text(text):
    return REF.sub(lambda m: f"{m.group(1)} {short_of(ITEMS[m.group(1)])}" if m.group(1) in ITEMS else m.group(0), text)


def refs_list(ids, plain=False):
    return ", ".join(f"{i} {short_of(ITEMS[i])}" if plain else f"[[{i}]]" for i in ids if i in ITEMS)


def state_line(item, plain=False):
    """The status badge, with when it was reached, what a Blocked item waits on, or
    why one was Dropped. `plain` writes references as text, for a line inside a link."""
    status = item.get("status")
    if not status or status not in ITEM_STATUS:
        return ""
    line = f'<span class="st st-{status}">{label_of(item)}</span>'
    if item.get("on"):
        line += f' <span class="on">{day(item["on"])}</span>'
    note = ""
    if status == "blocked":
        note = item.get("waits") or refs_list(item["needs"])
        prefix = TYPES.get(item.get("type"), {}).get("waits", "waits on")
        note = f"{prefix} {note}" if note else ""
    elif status == "dropped":
        note = item.get("why", "")
    if note:
        line += f' <span class="waits">{refs_as_text(note) if plain else note}</span>'
    return line


def card(item):
    head = [f'<span class="n">{esc(item["id"])}</span>', f'<h4>{item.get("title", "")}</h4>']
    if item.get("kind") in KINDS:
        head.append(f'<span class="pill k-{item["kind"]}">{KINDS[item["kind"]]}</span>')
    if item["amended"]:
        when = f' {day(item["amended"]["on"])}' if item["amended"]["on"] else ""
        head.append(f'<span class="pill amended">Amended{when}</span>')
    # A status set from another phase shows there: the card keeps the record as written.
    if item.get("status_from") == item["phase"]:
        head.append(state_line(item))
    rows = [(field[0], field[1]) for field in item.get("fields", []) if is_pair(field)]
    if item["needs"]:
        rows.append(("Needs", refs_list(item["needs"])))
    if item["due"]:
        rows.append(("Due", weekday(item["due"])))
    if item["amended"]:
        when = f'On {day(item["amended"]["on"])}, because' if item["amended"]["on"] else "Because"
        rows.append(("Amended", f'{when} {item["amended"]["why"]}'))
    dl = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows)
    links = []
    if item["needed_by"]:
        links.append(f'<span>Needed by</span> {refs_list(item["needed_by"])}')
    if item["named_by"]:
        links.append(f'<span>Named by</span> {refs_list(item["named_by"])}')
    back = f'\n    <p class="backlinks">{" · ".join(links)}</p>' if links else ""
    body = f"\n    <dl>{dl}</dl>" if dl else ""
    return f'  <article class="item" id="{anchor_of(item["id"])}">\n    <div class="item-head">{"".join(head)}</div>{body}{back}\n  </article>'


def chip(item):
    classes = ["chip"]
    if item.get("kind") in KINDS:
        classes.append(f'k-{item["kind"]}')
    if item.get("status") in ITEM_STATUS:
        classes.append(f's-{item["status"]}')
    line = state_line(item, plain=True)
    tail = f'<span class="w">{line}</span>' if line else ""
    return f'<a class="{" ".join(classes)}" href="#{anchor_of(item["id"])}"><b>{esc(item["id"])}</b><span>{short_of(item)}</span>{tail}</a>'


def table_html(head, rows, min_width=None, cls=None):
    attrs = f' class="{cls}"' if cls else ""
    if min_width:
        attrs += f' style="min-width: {min_width}px"'
    thead = "".join(f"<th>{cell}</th>" for cell in head)
    tbody = "\n".join("      <tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'  <div class="scroll">\n    <table{attrs}>\n      <thead><tr>{thead}</tr></thead>\n      <tbody>\n{tbody}\n      </tbody>\n    </table>\n  </div>'


def prefixed(text, prefix):
    """Imported HTML, with its ids and the links to them moved under `prefix`."""
    text = re.sub(r'(?<=\s)id="([^"]+)"', lambda m: f'id="{prefix}-{m.group(1)}"', text)
    text = re.sub(r'(?<=\s)href="#([^"]+)"', lambda m: f'href="#{prefix}-{m.group(1)}"', text)
    return re.sub(
        r'(?<=\s)(aria-labelledby|aria-describedby|aria-controls|for)="([^"]+)"',
        lambda m: f'{m.group(1)}="' + " ".join(f"{prefix}-{token}" for token in m.group(2).split()) + '"',
        text,
    )


def board_rows(section, where):
    """The board's columns and rows: as written, or, with `auto`, from `needs`."""
    if not section.get("auto"):
        columns = section.get("columns", [])
        if not all(is_pair(col) for col in columns):
            problem(where, "each of `columns` is a [title, subtitle] pair")
            return None
        rows = []
        for row in section.get("row", []):
            cells = row.get("cells", [])
            if len(cells) != len(columns):
                problem(where, f"row {row.get('name', '?')} has {len(cells)} cells for {len(columns)} columns")
            for cell in cells:
                for item_id in cell:
                    if item_id not in ITEMS:
                        problem(where, f"the board names {item_id}, which no item has")
            rows.append((row.get("name", ""), [[i for i in cell if i in ITEMS] for cell in cells]))
        return columns, rows
    types = section.get("types", ["pr"])
    chosen = [item_id for item_id, item in ITEMS.items() if item["type"] in types]
    wave = {}

    def depth(item_id, seen=()):
        if item_id not in wave:
            inner = [depth(n, seen + (item_id,)) for n in ITEMS[item_id]["needs"] if n in chosen and n not in seen]
            wave[item_id] = 1 + max(inner, default=0)
        return wave[item_id]

    for item_id in chosen:
        depth(item_id)
    count = max(wave.values(), default=0)
    subtitles = section.get("waves", [])
    columns = [[f"Wave {n}", subtitles[n - 1] if n <= len(subtitles) else ""] for n in range(1, count + 1)]
    names = []
    for item_id in chosen:
        name = ITEMS[item_id].get("repo", section.get("rows_default", ""))
        if name not in names:
            names.append(name)
    rows = [(name, [[i for i in chosen if ITEMS[i].get("repo", section.get("rows_default", "")) == name and wave[i] == n] for n in range(1, count + 1)]) for name in names]
    return columns, rows


def render_section(section, key, data, data_dir):
    where = f"{key}.toml section {section.get('id', '(no id)')}"
    section_id = section.get("id", "")
    kind = section.get("kind")
    if not isinstance(section_id, str) or not KEBAB.fullmatch(section_id):
        problem(where, "`id` is required, in kebab-case")
        return ""
    if kind not in SECTION_KINDS:
        problem(where, f"`kind` is one of {', '.join(SECTION_KINDS)}")
        return ""
    if kind != "prose":
        required(section, "title", where)
    if not isinstance(section.get("min_width", 0), int):
        problem(where, "`min_width` is a number of pixels")
        return ""
    parts = []
    if section.get("intro"):
        parts.append(f'  <p class="intro">{section["intro"]}</p>')
    if kind == "prose":
        body = section.get("body")
        if section.get("file"):
            path = data_dir / section["file"]
            if not path.is_file():
                problem(where, f"`file` {section['file']} does not exist beside project.toml")
                return ""
            body = path.read_text(encoding="utf-8")
        if body is None:
            problem(where, "a prose section has a `body` or a `file`")
            return ""
        if section.get("prefix"):
            body = prefixed(body, section["prefix"])
        parts.append(body if section.get("wide") else f'  <div class="prose">{body}</div>')
    elif kind == "table":
        head, rows = section.get("head", []), section.get("rows", [])
        if not rows or any(len(row) != len(head) for row in rows):
            problem(where, "a table has rows, each with as many cells as `head`")
        parts.append(table_html(head, rows, section.get("min_width")))
    elif kind == "items":
        parts.extend(card(ITEMS[item["id"]]) for item in section.get("item", []) if item.get("id") in ITEMS)
    elif kind == "board":
        board = board_rows(section, where)
        if board is None:
            return ""
        columns, rows = board
        head = [section.get("rows_title", "")] + [f"{esc(title)}<span>{esc(sub)}</span>" for title, sub in columns]
        cells = []
        for name, row in rows:
            rendered = [esc(name)]
            for cell in row:
                chips = "".join(chip(ITEMS[item_id]) for item_id in cell)
                rendered.append(f'<div class="chips">{chips}</div>' if chips else "")
            cells.append(rendered)
        parts.append(table_html(head, cells, section.get("min_width", 160 * len(columns) + 140), "board"))
    elif kind == "results":
        ids = section.get("ids") or list(data.get("status", {}))
        rows = []
        for item_id in ids:
            if item_id not in ITEMS:
                problem(where, f"`ids` names {item_id}, which no item has")
                continue
            item = ITEMS[item_id]
            rows.append([ref_html(item_id), state_line(item), item.get("result", "")])
        parts.append(table_html(["Item", "Status", "Result"], rows, section.get("min_width", 760), "results"))
    elif kind == "log":
        entries = []
        for index, entry in enumerate(section.get("entry", [])):
            date = as_date(entry.get("date"), f"{where} entry {index + 1}", "date")
            entries.append(f'<li><span class="who">{day(date) if date else ""}</span><span>{entry.get("text", "")}</span></li>')
        parts.append(f'  <ul class="plain log">{"".join(entries)}</ul>')
    elif kind == "figures":
        figures = "".join(
            f'<li><span class="v">{esc(fig.get("value", ""))}</span><span class="k">{fig.get("label", "")}</span></li>'
            for fig in section.get("figure", [])
        )
        parts.append(f'  <ul class="figures">{figures}</ul>')
        if section.get("note"):
            parts.append(f'  <p class="note">{section["note"]}</p>')
    elif kind == "defs":
        rows = "".join(f'<dt>{entry.get("term", "")}</dt><dd>{entry.get("text", "")}</dd>' for entry in section.get("def", []))
        parts.append(f'  <dl class="defs">{rows}</dl>')
    title = f'  <h3>{section["title"]}</h3>\n' if section.get("title") else ""
    return f'<section class="block" id="{section_id}">\n{title}' + "\n".join(parts) + "\n</section>"


def amendments(key, data):
    """The items amended into a phase after its approval, listed above its sections."""
    amended = [item for item in ITEMS.values() if item["phase"] == key and item["amended"]]
    if not data.get("approved") and not amended:
        return ""
    lead = f'Approved on {day(data["approved"])}.' if data.get("approved") else ""
    if not amended:
        return f'<p class="approved">{lead} Nothing has been amended since.</p>'
    rows = "".join(
        f'<li>[[{item["id"]}]]{", " + day(item["amended"]["on"]) if item["amended"]["on"] else ""}, because {item["amended"]["why"]}</li>'
        for item in amended
    )
    return f'<div class="approved"><p>{lead} Amended since:</p><ul>{rows}</ul></div>'


def changelog(key, entries, targets):
    if not entries:
        return ""
    rows = []
    for index, entry in enumerate(entries):
        where = f"{key}.toml [[changelog]] {index + 1}"
        required(entry, "text", where)
        if entry.get("date") is None:
            problem(where, "a changelog entry has a `date`")
        links = []
        for target in entry.get("changed", []):
            if target not in targets:
                problem(where, f"`changed` names {target}, which is no section or item in this phase")
                continue
            links.append(f'<a href="#{target}">{targets[target]}</a>')
        changed = f' <span class="changed">Changed: {"; ".join(links)}</span>' if links else ""
        date = day(entry["date"]) if entry.get("date") else ""
        rows.append(f'<li><time>{date}</time><div>{entry.get("text", "")}{changed}</div></li>')
    return f'<footer class="changelog" id="{key}-changelog">\n  <h3>Changelog</h3>\n  <ol>{"".join(rows)}</ol>\n</footer>'


def render_phase(key, state, data, data_dir):
    status = state["status"]
    span = ""
    if state["start"]:
        when = f'{day(state["start"])} – {day(state["end"])}' if state["end"] else f'since {day(state["start"])}'
        span = f'<span class="span">{when}</span>'
    head = f'<div class="phase-head"><h2>{PHASE_NAME[key]}</h2><span class="ph ph-{status}">{PHASE_STATUS[status]}</span>{span}</div>'
    parts = [head]
    if status == "not-needed":
        parts.append(f'<p class="why">{state["why"]}</p>')
    elif data is None:
        parts.append('<p class="why">Nothing here yet.</p>' if status == "to-come" else "")
    if data:
        if data.get("intro"):
            parts.append(f'<p class="lede">{data["intro"]}</p>')
        parts.append(amendments(key, data))
        targets = {}
        for section in data.get("section", []):
            parts.append(render_section(section, key, data, data_dir))
            if section.get("id"):
                targets[section["id"]] = section.get("title") or section["id"]
            for item in section.get("item", []) if section.get("kind") == "items" else []:
                if item.get("id") in ITEMS:
                    targets[anchor_of(item["id"])] = f'<b>{esc(item["id"])}</b> {short_of(ITEMS[item["id"]])}'
        parts.append(changelog(key, data.get("changelog", []), targets))
    return expand_refs("\n".join(part for part in parts if part), f"{key}.toml")


# ------------------------------------------------------------------ the calendar


def dated(project, phases):
    """Everything with a date: (date, class, html), in no order yet."""
    found = []
    for event in project.get("event", []):
        if event.get("date"):
            found.append((event["date"], "event", event.get("title", ""), event.get("short") or text_of(event.get("title", ""))))
    for item_id, item in ITEMS.items():
        if item.get("on") and item.get("status") in ITEM_STATUS:
            found.append((item["on"], f"s-{item['status']}", f"[[{item_id}]] {label_of(item)}", item_id))
        if item["due"] and item.get("status") != "done":
            found.append((item["due"], "due", f"[[{item_id}]] due", f"{item_id} due"))
        if item["amended"] and item["amended"]["on"]:
            found.append((item["amended"]["on"], "amended", f"[[{item_id}]] amended into the {PHASE_NAME[item['phase']]}", f"{item_id} amended"))
    for key, state in project["status"].items():
        if state["start"]:
            found.append((state["start"], "phase", f"{PHASE_NAME[key]} starts", PHASE_NAME[key]))
        if state["end"]:
            found.append((state["end"], "phase", f"{PHASE_NAME[key]} ends", f"{PHASE_NAME[key]} ends"))
    for key, data in phases.items():
        if data.get("approved"):
            found.append((data["approved"], "phase", f"{PHASE_NAME[key]} approved", f"{PHASE_NAME[key]} approved"))
        for section in data.get("section", []):
            if section.get("kind") != "log":
                continue
            for entry in section.get("entry", []):
                date = quiet_date(entry.get("date"))
                if date:
                    found.append((date, "log", entry.get("text", ""), None))
    return found


def month_grid(year, month, by_day):
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    head = "".join(f"<th>{name}</th>" for name in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
    rows = []
    for week in weeks:
        cells = []
        for date in week:
            if date.month != month:
                cells.append('<td class="out"></td>')
                continue
            classes = ["d"] + (["today"] if date == TODAY else []) + (["has"] if date in by_day else [])
            marks = "".join(
                f'<li class="m-{cls}">{esc(label)}</li>' if label else f'<li class="m-{cls} dot" title="{esc(text_of(refs_as_text(text)))}"></li>'
                for cls, text, label in by_day.get(date, [])
            )
            cells.append(f'<td class="{" ".join(classes)}"><span class="dn">{date.day}</span>{f"<ul>{marks}</ul>" if marks else ""}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="month"><h4>{calendar.month_name[month]} {year}</h4><table class="cal"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def calendar_view(project, phases):
    found = dated(project, phases)
    by_day = {}
    for date, cls, text, label in found:
        by_day.setdefault(date, []).append((cls, text, label))
    # What is still to come: later dates, and today's events and deadlines.
    ahead = sorted((e for e in found if e[0] > TODAY or (e[0] == TODAY and e[1] in ("event", "due"))), key=lambda e: e[0])
    you = [i for i, item in ITEMS.items() if item.get("status") == "open"]
    me = [i for i, item in ITEMS.items() if item.get("status") == "ready"]

    def column(title, rows, empty):
        body = "".join(rows) if rows else f'<li class="none">{empty}</li>'
        return f'<div class="col"><h3>{title}</h3><ul>{body}</ul></div>'

    you_rows = [f'<li><span class="pill ask">{esc(ask_of(ITEMS[i]))}</span> [[{i}]]</li>' for i in you]
    me_rows = [f"<li>[[{i}]]</li>" for i in me]
    date_rows = [f'<li><time>{weekday(date)}</time> {text}</li>' for date, cls, text, label in ahead[:6]]
    ball = column("Waiting on you", you_rows, "Nothing.") + column("Next for me", me_rows, "Nothing ready.") + column("Waiting on a date", date_rows, "No date ahead.")
    handoff = project.get("handoff")
    notes = ""
    if handoff and handoff.get("notes"):
        updated = f' <span class="on">{day(handoff["updated"])}</span>' if handoff.get("updated") else ""
        notes = f'<section class="block handoff" id="next-session"><h3>Notes for the next session{updated}</h3><ul>{"".join(f"<li>{n}</li>" for n in handoff["notes"])}</ul></section>'
    grid = ""
    if found:
        first, last = min(e[0] for e in found), max(e[0] for e in found)
        months, cursor = [], datetime.date(first.year, first.month, 1)
        while cursor <= last:
            months.append((cursor.year, cursor.month))
            cursor = datetime.date(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1)
        grid = "".join(month_grid(year, month, by_day) for year, month in months[-6:])
    agenda = []
    for date in sorted(by_day, reverse=True):
        when = "ahead" if date > TODAY else "today" if date == TODAY else "past"
        rows = "".join(f'<li class="m-{cls}">{text}</li>' for cls, text, label in by_day[date])
        agenda.append(f'<li class="{when}"><time>{weekday(date)}</time><ul>{rows}</ul></li>')
    agenda_html = f'<ol class="agenda">{"".join(agenda)}</ol>' if agenda else '<p class="why">Nothing has a date yet.</p>'
    body = f"""<div class="phase-head"><h2>Calendar</h2><span class="span">read on {weekday(TODAY)}</span></div>
<section class="block" id="ball"><h3>Who holds the ball</h3><div class="ball">{ball}</div></section>
{notes}
<section class="block" id="months"><h3>The calendar</h3><div class="months">{grid}</div></section>
<section class="block" id="agenda"><h3>Every date, newest first</h3>{agenda_html}</section>"""
    return expand_refs(body, "the calendar"), len(you), len(me), (ahead[0] if ahead else None)


def glossary(entries):
    if not entries:
        return ""
    groups = []
    for source, title in SOURCES.items():
        rows = "".join(
            f'<dt>{entry.get("term", "")}</dt><dd>{entry.get("text", "")}</dd>'
            for entry in entries
            if entry.get("source", "coined") == source
        )
        if rows:
            groups.append(f'<h3>{title}</h3><dl class="defs">{rows}</dl>')
    return f'<details class="glossary" id="glossary">\n  <summary>Glossary</summary>\n  {"".join(groups)}\n</details>'


def opening_phase(statuses):
    for wanted in ("now", "to-come"):
        for key, _ in PHASES:
            if statuses[key]["status"] == wanted:
                return key
    return PHASES[0][0]


# ------------------------------------------------------------------ checking


class Check(HTMLParser):
    """Tag nesting, and the ids and in-page links an HTML fragment holds."""

    def __init__(self, where):
        super().__init__(convert_charrefs=True)
        self.where, self.stack, self.ids, self.links = where, [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        href = attrs.get("href") or ""
        if href.startswith("#") and len(href) > 1:
            self.links.append(href[1:])
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            opened = f"<{self.stack[-1][0]}> from line {self.stack[-1][1]}" if self.stack else "nothing"
            problem(self.where, f"line {self.getpos()[0]}: </{tag}> closes {opened}")
            return
        self.stack.pop()

    def finish(self):
        self.close()
        for tag, line in self.stack:
            problem(self.where, f"<{tag}> from line {line} is never closed")
        return self


def check(fragments):
    """fragments: (where, html) pairs that end up in one document."""
    seen, links = {}, []
    for where, fragment in fragments:
        result = Check(where)
        result.feed(fragment)
        result.finish()
        for found in result.ids:
            if found in seen:
                problem(where, f'id "{found}" is used twice, here and in {seen[found]}')
            seen.setdefault(found, where)
            if not ANCHOR.fullmatch(found):
                problem(where, f'id "{found}" has characters a link to it would lose; use letters, digits, ".", "_", "~" and "-"')
        links.extend((where, link) for link in result.links)
    for where, link in links:
        if link not in seen:
            problem(where, f'a link to "#{link}", which nothing on the page has')


# ------------------------------------------------------------------ the page


def page(project, sections, opening, inline, data_dir, calendar_html, glance):
    css = (HERE / "page.css").read_text(encoding="utf-8")
    for extra in project.get("css", []):
        path = data_dir / extra
        if path.is_file():
            css += "\n" + path.read_text(encoding="utf-8")
        else:
            problem("project.toml", f"`css` names {extra}, which does not exist beside project.toml")
    title = f'{project.get("repo", "")}-{project.get("objective", "")}'
    tabs = []
    for number, (key, name) in enumerate(PHASES, start=1):
        status = project["status"][key]["status"]
        current = ' aria-current="true"' if key == opening else ""
        tabs.append(
            f'<li><a href="#{key}" data-phase="{key}" class="t-{status}"{current}><span class="n">{number}</span>'
            f'<span class="name">{name}</span><span class="state">{PHASE_STATUS[status]}</span></a></li>'
        )
    shells, files = [], {}
    for key, _ in PHASES:
        hidden = "" if key == opening else " hidden"
        if inline or key == opening or not sections[key][1]:
            shells.append(f'<section class="phase" id="{key}" data-phase="{key}"{hidden}>\n{sections[key][0]}\n</section>')
        else:
            files[key] = sections[key][0] + "\n"
            shells.append(f'<section class="phase" id="{key}" data-phase="{key}" data-src="phases/{key}.html" hidden></section>')
    shells.append(f'<section class="phase view" id="calendar" data-phase="calendar" hidden>\n{calendar_html}\n</section>')
    read_at = project["read_at"]
    return title, files, f"""<meta charset="utf-8">
<title>{esc(title)}</title>
{FONTS}
<style>
{css}
</style>
<div class="wrap">
<header class="top">
  <p class="eyebrow">{esc(project.get("repo", ""))} · project page</p>
  <h1>{esc(title)}</h1>
  <p class="lede">{project.get("summary", "")}</p>
  <nav class="phases" aria-label="Phases"><ol>{"".join(tabs)}</ol></nav>
  <p class="glance"><a class="to-cal" href="#calendar" data-phase="calendar">Calendar</a>{glance}</p>
  <p class="readat">State read on {read_at.day} {read_at:%B %Y} at {read_at:%H:%M} UTC.</p>
</header>
<main id="phases" data-open="{opening}">
{chr(10).join(shells)}
</main>
{glossary(project.get("glossary", []))}
<footer class="site"><p>Built with <code>/project-page</code> from the TOML files published beside this page.</p></footer>
</div>
"""


def main(argv):
    args = [arg for arg in argv if arg != "--inline"]
    if len(args) != 2 or any(arg.startswith("-") for arg in args):
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    data_dir, out_dir = Path(args[0]), Path(args[1])
    inline = "--inline" in argv
    project = read_project(data_dir)
    phases = read_phases(data_dir)
    collect_items(phases)
    link_items()
    if not problems:
        check_states(project, phases)
    sections = {}
    for key, _ in PHASES:
        sections[key] = (render_phase(key, project["status"][key], phases.get(key), data_dir), key in phases)
    calendar_html, waiting_count, next_count, next_date = calendar_view(project, phases)
    glance = f' <span>{waiting_count} waiting on you</span> <span>{next_count} next for me</span>'
    if next_date:
        glance += f' <span>Next date: {weekday(next_date[0])}, {expand_refs(next_date[2], "the calendar")}</span>'
    opening = opening_phase(project["status"])
    title, files, shell = page(project, sections, opening, inline, data_dir, calendar_html, glance)
    shell = expand_refs(shell, "project.toml")
    fragments = [("the page", shell)] + [(f"phases/{key}.html", text) for key, text in files.items()]
    check(fragments)
    if problems:
        for line in problems:
            print(line, file=sys.stderr)
        print(f"{len(problems)} problem{'s' if len(problems) != 1 else ''}; nothing written.", file=sys.stderr)
        return 1
    for line in warnings:
        print(f"warning: {line}", file=sys.stderr)
    # Which view holds each id, so a link into a phase not loaded yet opens it.
    phase_of = {}
    for key, (text, _) in list(sections.items()) + [("calendar", (calendar_html, True))]:
        holder = Check(key)
        holder.feed(text)
        holder.close()
        phase_of.update((found, key) for found in holder.ids)
    script = (HERE / "page.js").read_text(encoding="utf-8")
    manifest = json.dumps(phase_of, separators=(",", ":")).replace("</", "<\\/")
    out = shell + f'<script type="application/json" id="anchors">{manifest}</script>\n<script>\n{script}</script>\n'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(out, encoding="utf-8")
    if files:
        (out_dir / "phases").mkdir(exist_ok=True)
        for key, text in files.items():
            (out_dir / "phases" / f"{key}.html").write_text(text, encoding="utf-8")
    loaded = ", ".join(f"phases/{key}.html" for key in files) or "none"
    notes = f"; {len(warnings)} warning{'s' if len(warnings) != 1 else ''}" if warnings else ""
    print(f"{title}: index.html, {len(out.encode()) // 1024} KB, opening on {PHASE_NAME[opening]}; loaded when picked: {loaded}{notes}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
