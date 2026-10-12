#!/usr/bin/env python3
"""Builds a project page from its TOML data, and checks it.

Usage: python3 render.py <data-dir> <out-dir> [--inline | --retrospective] [--since <published-dir>]

<data-dir> holds project.toml and a <phase>.toml for each phase with content.
<out-dir> gets index.html, the page to publish, and phases/<phase>.html for
every other phase with content, which the page loads when that phase is
picked. --inline puts every phase in index.html instead, for a preview or a
small project. --retrospective writes retrospective.html instead: the
Retrospective alone, as a page to share. --since, given the data as it was
last published, also prints what has changed in each phase since, for its
changelog entry.

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
KINDS = {"major": "Major", "minor": "Minor", "patch": "Patch", "owner": "Owner", "together": "Together"}
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
# How the guide names each type of item, with what its numbers start with.
TYPE_NAMES = {
    "piece": ("Research piece", "R1"),
    "rule": ("Ground rule", "G1"),
    "criterion": ("Success criterion", "SC1"),
    "decision": ("Decision", "D1"),
    "question": ("Question", "Q1"),
    "pr": ("PR", "AC-1"),
    "setting": ("Setting", "S1"),
    "risk": ("Risk", "RK1"),
    "check": ("Check", "C1"),
    "lesson": ("Lesson", "L1"),
    "later": ("Later work", "T1"),
}
KIND_MEANING = {
    "major": "Merging it releases a major version: what used the last one may need changing.",
    "minor": "Merging it releases a minor version: something new, and nothing that worked breaks.",
    "patch": "Merging it releases a patch: a fix, with nothing new.",
    "owner": "Only the owner can do it, such as a setting in a service they own.",
    "together": "The owner and the agent do it together, in a session.",
}
SECTION_KINDS = ("prose", "table", "items", "board", "results", "log", "figures", "defs")
SOURCES = {"coined": "Coined for this project", "borrowed": "Borrowed from elsewhere"}

KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ITEM_ID = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*")
# [[D1]] in any text: a link to the item, with its id and its short title.
REF = re.compile(r"\[\[([^\]]*)\]\]")
# Only an anchor made of these reaches location.hash from an artifact's link.
ANCHOR = re.compile(r"[A-Za-z0-9._~-]+")
# A pull request or an issue on GitHub, which a link names as GitHub does: owner/repo#12.
GITHUB = re.compile(r"https://github\.com/([^/]+/[^/]+)/(?:pull|issues)/(\d+)")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&amp;display=swap" rel="stylesheet">'
)

problems, warnings = [], []
ITEMS = {}  # every item of every phase, by id, in phase order
TODAY = None  # the day the state was read
LINKABLE = None  # the ids a reference links to, on a page that holds only some; None for all
COUNTED = []  # the headline figures counted from the data, for a `figures` section with `auto`


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
        if not isinstance(event.get("ci", False), bool):
            problem(where, "`ci` is true or false: true when the event is an automated run")
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


def is_field(value):
    """A [label, text] pair, its text one string or a list of them."""
    if not (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)):
        return False
    text = value[1]
    return isinstance(text, str) or (isinstance(text, list) and all(isinstance(part, str) for part in text))


def texts_of(text):
    return text if isinstance(text, list) else [text]


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
                if not all(is_field(field) for field in item.get("fields", [])):
                    problem(where, "each of `fields` is a [label, text] pair, its text one string or a list of them")
                url = item.get("url")
                if url is not None and not (isinstance(url, str) and url.startswith("https://")):
                    problem(where, "`url` is an https:// address, such as the PR's on GitHub")
                needs = item.get("needs", [])
                if not (isinstance(needs, list) and all(isinstance(n, str) for n in needs)):
                    problem(where, "`needs` is a list of item ids")
                    needs = []
                options = item.get("options")
                if options is not None:
                    keys = [option[0] for option in options] if isinstance(options, list) and all(is_pair(o) for o in options) else None
                    if keys is None or len(set(keys)) != len(keys):
                        problem(where, '`options` is a list of [key, text] pairs, each key once, such as ["a", "One port for everything."]')
                    else:
                        for mark in ("recommended", "chosen"):
                            if mark in item and item[mark] not in keys:
                                problem(where, f"`{mark}` is {item[mark]}, which no option has; the options are {', '.join(keys)}")
                elif "recommended" in item or "chosen" in item:
                    problem(where, "`recommended` and `chosen` name one of the item's `options`")
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
        texts += [part for _, value in (f for f in item.get("fields", []) if is_field(f)) for part in texts_of(value)]
        texts += [text for _, text in (o for o in item.get("options") or [] if is_pair(o))]
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
        if item.get("options") and status == "done" and "chosen" not in item:
            warn(where, f"{item_id} is `done`, but none of its options is `chosen`")
        if "chosen" in item and status in UNFINISHED:
            warn(where, f"{item_id} has a `chosen` option, but is still `{status}`")
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
    """D1 with its short title: a link to it, or text on a page that doesn't hold it."""
    name = f"<b>{esc(item_id)}</b> {short_of(ITEMS[item_id])}"
    if LINKABLE is not None and item_id not in LINKABLE:
        return f'<span class="ref">{name}</span>'
    return f'<a class="ref" href="#{anchor_of(item_id)}">{name}</a>'


def link_html(url):
    """An address outside the page as a chip, named as GitHub names it where it is one."""
    match = GITHUB.fullmatch(url)
    label = f"{match.group(1)}#{match.group(2)}" if match else url
    return f'<a class="pill link" href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


def options_html(item):
    """An item's options as a list: the recommended one marked until one is chosen,
    and after that only the choice. The mark is a background, and a hidden word."""
    chosen = item.get("chosen")
    marked, mark = (chosen, "chosen") if chosen else (item.get("recommended"), "recommended")
    rows = []
    for key, text in item["options"]:
        tag, note = (f' class="{mark}"', f'<span class="vh"> ({mark})</span>') if key == marked else ("", "")
        rows.append(f'<li{tag}><span class="key">{esc(key)}</span><span>{text}{note}</span></li>')
    return f'<ol class="options">{"".join(rows)}</ol>'


def list_html(entries):
    """A simple list: how the page shows anything that holds several things."""
    return f'<ul class="list">{"".join(f"<li>{entry}</li>" for entry in entries)}</ul>'


def refs_ul(ids):
    return list_html([f"[[{i}]]" for i in ids if i in ITEMS])


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
    """An item's card: its number and summary; then chips, for what a word or two says;
    then its fields; then the items that need it or name it."""
    short = item.get("short")
    head = f'<div class="item-head"><span class="n">{esc(item["id"])}</span><h4>{short or item.get("title", "")}</h4></div>'
    tags = []
    if item.get("kind") in KINDS:
        tags.append(f'<span class="pill k-{item["kind"]}">{KINDS[item["kind"]]}</span>')
    # A status set from another phase shows there: the card keeps the record as written.
    own = item.get("status_from") == item["phase"] and item.get("status") in ITEM_STATUS
    if own:
        when = f' · {day(item["on"])}' if item.get("on") else ""
        tags.append(f'<span class="pill st-{item["status"]}">{label_of(item)}{when}</span>')
    if item["amended"]:
        when = f' {day(item["amended"]["on"])}' if item["amended"]["on"] else ""
        tags.append(f'<span class="pill amended">Amended{when}</span>')
    if isinstance(item.get("url"), str):
        tags.append(link_html(item["url"]))
    rows = []
    if short and short != text_of(item.get("title", "")):
        rows.append(("Title", item.get("title", "")))
    options = item.get("options")
    if isinstance(options, list) and options and all(is_pair(option) for option in options):
        rows.append(("Options", options_html(item)))
    rows += [(field[0], list_html(field[1]) if isinstance(field[1], list) else field[1]) for field in item.get("fields", []) if is_field(field)]
    if own and item["status"] == "blocked" and item.get("waits"):
        rows.append((TYPES.get(item["type"], {}).get("waits", "waits on").capitalize(), item["waits"]))
    if own and item["status"] == "dropped":
        rows.append(("Why", item.get("why", "")))
    if item["needs"]:
        rows.append(("Needs", refs_ul(item["needs"])))
    if item["amended"]:
        rows.append(("Why amended", item["amended"]["why"]))
    if item["needed_by"]:
        rows.append(("Needed by", refs_ul(item["needed_by"])))
    if item["named_by"]:
        rows.append(("Named by", refs_ul(item["named_by"])))
    dl = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows)
    chips = f'\n    <div class="item-tags">{"".join(tags)}</div>' if tags else ""
    body = f"\n    <dl>{dl}</dl>" if dl else ""
    return f'  <article class="item" id="{anchor_of(item["id"])}">\n    {head}{chips}{body}\n  </article>'


def chip(item):
    """An item on the board: its stripe and tint say its status, and its kind is a word."""
    classes = ["chip"]
    if item.get("status") in ITEM_STATUS:
        classes.append(f's-{item["status"]}')
    line = state_line(item, plain=True)
    if item.get("kind") in KINDS:
        line += f' <span class="kind">{KINDS[item["kind"]]}</span>'
    tail = f'<span class="w">{line.strip()}</span>' if line else ""
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
        # With `auto`, the figures the data can count come first, then those written out.
        auto = COUNTED if section.get("auto") else []
        shown = auto + [(fig.get("value", ""), fig.get("label", "")) for fig in section.get("figure", [])]
        figures = "".join(f'<li><span class="v">{esc(value)}</span><span class="k">{label}</span></li>' for value, label in shown)
        parts.append(f'  <ul class="figures">{figures}</ul>')
        note = section.get("note", "")
        if auto and not note:
            which = "Counted" if len(auto) == len(shown) else f"The first {len(auto)} counted"
            note = f"{which} from the project's data on {TODAY.day} {TODAY:%B %Y}."
        if note:
            parts.append(f'  <p class="note">{note}</p>')
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
    rows = [
        f'[[{item["id"]}]]{", " + day(item["amended"]["on"]) if item["amended"]["on"] else ""}, because {item["amended"]["why"]}'
        for item in amended
    ]
    return f'<div class="approved"><p>{lead} Amended since:</p>{list_html(rows)}</div>'


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
        changed = f'<div class="changed">Changed:{list_html(links)}</div>' if links else ""
        date = day(entry["date"]) if entry.get("date") else ""
        rows.append(f'<li><time>{date}</time><div>{entry.get("text", "")}{changed}</div></li>')
    return f'<footer class="changelog" id="{key}-changelog">\n  <h3>Changelog</h3>\n  <ol>{"".join(rows)}</ol>\n</footer>'


def render_phase(key, state, data, data_dir, head=True):
    """A phase's view: its head, unless it stands alone, then its sections and changelog."""
    status = state["status"]
    span = ""
    if state["start"]:
        when = f'{day(state["start"])} – {day(state["end"])}' if state["end"] else f'since {day(state["start"])}'
        span = f'<span class="span">{when}</span>'
    parts = []
    if head:
        parts.append(f'<div class="phase-head"><h2>{PHASE_NAME[key]}</h2><span class="ph ph-{status}">{PHASE_STATUS[status]}</span>{span}</div>')
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
            # An automated run, such as a scheduled workflow, is marked CI wherever it is listed.
            mark = ' <span class="ci">CI</span>' if event.get("ci") is True else ""
            found.append((event["date"], "event", event.get("title", "") + mark, event.get("short") or text_of(event.get("title", ""))))
    for item_id, item in ITEMS.items():
        if item.get("on") and item.get("status") in ITEM_STATUS:
            found.append((item["on"], f"s-{item['status']}", f"[[{item_id}]] {label_of(item)}", item_id))
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


def month_grid(year, month, by_day, before, after, shown):
    """One month of the header's calendar, with arrows to the months beside it. A day
    with something on it links to that day in the agenda."""
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
            number = f'<a class="dn" href="#on-{date.isoformat()}">{date.day}</a>' if date in by_day else f'<span class="dn">{date.day}</span>'
            cells.append(f'<td class="{" ".join(classes)}">{number}{f"<ul>{marks}</ul>" if marks else ""}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")

    def arrow(target, step, mark):
        if target is None:
            return f'<button type="button" class="step" disabled aria-label="No {"earlier" if step < 0 else "later"} month">{mark}</button>'
        return f'<button type="button" class="step" data-step="{step}" aria-label="{calendar.month_name[target[1]]} {target[0]}">{mark}</button>'

    hidden = "" if shown else " hidden"
    return (
        f'<div class="month"{hidden}><div class="month-head">{arrow(before, -1, "‹")}<h2>{calendar.month_name[month]} {year}</h2>{arrow(after, 1, "›")}</div>'
        f'<table class="cal"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def calendar_view(project, phases):
    """The header's calendar, every month the project spans with today's shown; who
    holds the ball, which the header shows under it: the user, the agent, or a date
    coming up; and the agenda: every date coming up, the notes for the next session,
    and what happened."""
    found = dated(project, phases)
    by_day = {}
    for date, cls, text, label in found:
        by_day.setdefault(date, []).append((cls, text, label))
    dates = [e[0] for e in found] + [TODAY]
    first, last = min(dates), max(dates)
    months, cursor = [], datetime.date(first.year, first.month, 1)
    while cursor <= last:
        months.append((cursor.year, cursor.month))
        cursor = datetime.date(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1)
    grid = "".join(
        month_grid(year, month, by_day, months[i - 1] if i else None, months[i + 1] if i + 1 < len(months) else None, (year, month) == (TODAY.year, TODAY.month))
        for i, (year, month) in enumerate(months)
    )
    # What is still to come: later dates, and today's events.
    ahead = sorted((e for e in found if e[0] > TODAY or (e[0] == TODAY and e[1] == "event")), key=lambda e: e[0])
    owner = [i for i, item in ITEMS.items() if item.get("status") == "open"]
    agent = [i for i, item in ITEMS.items() if item.get("status") == "ready"]

    def column(title, rows, empty, more=""):
        body = "".join(rows) if rows else f'<li class="none">{empty}</li>'
        return f'<div class="col"><h3>{title}</h3><ul>{body}</ul>{more}</div>'

    owner_rows = [f'<li><span class="pill ask">{esc(ask_of(ITEMS[i]))}</span> [[{i}]]</li>' for i in owner]
    agent_rows = [f"<li>[[{i}]]</li>" for i in agent]
    # The next three dates, each a link to its day in the agenda, which has them all.
    date_rows = [f'<li class="dated"><a class="when" href="#on-{date.isoformat()}"><time>{weekday(date)}</time></a> <span>{text}</span></li>' for date, cls, text, label in ahead[:3]]
    more = f'<p class="more"><a href="#coming-up">{len(ahead) - 3} more in the agenda</a></p>' if len(ahead) > 3 else ""
    ball = (
        '<section class="hold" id="ball" aria-labelledby="ball-title"><h2 id="ball-title">Who holds the ball</h2><div class="ball">'
        + column("The owner", owner_rows, "Nothing to do.")
        + column("The agent", agent_rows, "Nothing ready.")
        + column("A date", date_rows, "No date ahead.", more)
        + "</div></section>"
    )
    handoff = project.get("handoff")
    notes = ""
    if handoff and handoff.get("notes"):
        updated = f' <span class="on">{day(handoff["updated"])}</span>' if handoff.get("updated") else ""
        notes = f'<section class="block handoff" id="next-session"><h3>Notes for the next session{updated}</h3>{list_html(handoff["notes"])}</section>'
    coming, happened = {}, {}
    for date, cls, text, label in found:
        upcoming = date > TODAY or (date == TODAY and cls == "event")
        (coming if upcoming else happened).setdefault(date, []).append((cls, text))
    anchors = set()

    def days(groups, order):
        rows = []
        for date in order:
            when = "ahead" if date > TODAY else "today" if date == TODAY else "past"
            # Today can be in both lists; the calendar's link goes to the first.
            anchor = f"on-{date.isoformat()}"
            attr = "" if anchor in anchors else f' id="{anchor}"'
            anchors.add(anchor)
            entries = "".join(f'<li class="m-{cls}">{text}</li>' for cls, text in groups[date])
            rows.append(f'<li class="{when}"{attr}><time>{weekday(date)}</time><ul>{entries}</ul></li>')
        return f'<ol class="agenda">{"".join(rows)}</ol>'

    coming_html = days(coming, sorted(coming)) if coming else '<p class="why">No date ahead.</p>'
    happened_html = days(happened, sorted(happened, reverse=True)) if happened else '<p class="why">Nothing yet.</p>'
    body = f"""<section class="block" id="coming-up"><h3>Coming up, soonest first</h3>{coming_html}</section>
{notes}
<section class="block" id="history"><h3>What happened, newest first</h3>{happened_html}</section>"""
    return expand_refs(body, "the agenda"), grid, ball


def glossary_groups(entries, level):
    """The terms coined for the project, then those borrowed, under headings of `level`."""
    groups = []
    for source, title in SOURCES.items():
        rows = "".join(
            f'<dt>{entry.get("term", "")}</dt><dd>{entry.get("text", "")}</dd>'
            for entry in entries
            if entry.get("source", "coined") == source
        )
        if rows:
            groups.append(f'<h{level}>{title}</h{level}><dl class="defs">{rows}</dl>')
    return "".join(groups)


def glossary(entries):
    """The glossary folded into a panel, for the Retrospective alone."""
    if not entries:
        return ""
    return f'<details class="aid glossary" id="glossary">\n  <summary>Glossary</summary>\n  {glossary_groups(entries, 3)}\n</details>'


def site_footer(aids, line):
    """The footer: the panels that help read the page, then where it came from."""
    panels = f'\n<div class="aids">\n{aids}\n</div>' if aids.strip() else ""
    return f'<footer class="site">{panels}\n<p>{line}</p>\n</footer>'


def opening_phase(statuses):
    for wanted in ("now", "to-come"):
        for key, _ in PHASES:
            if statuses[key]["status"] == wanted:
                return key
    return PHASES[0][0]


# ------------------------------------------------------------------ the guides


def statuses_table():
    """Each type of item in the words its statuses take, and what the user does while one waits."""
    order = ("open", "ready", "blocked", "done", "dropped")
    rows = []
    for key, entry in TYPES.items():
        name, example = TYPE_NAMES[key]
        words = [f'<span class="st st-{status}">{entry["labels"].get(status, ITEM_STATUS[status])}</span>' for status in order]
        rows.append([f'{name} <span class="letters">{example}</span>'] + words + [entry["ask"]])
    return table_html(["Type", "Waits on the owner", "Ready", "Blocked", "Done", "Dropped", "The owner's part"], rows, 820, "statuses")


def kinds_list():
    rows = "".join(f'<dt><span class="pill k-{key}">{name}</span></dt><dd>{KIND_MEANING[key]}</dd>' for key, name in KINDS.items())
    return f'<dl class="defs kinds">{rows}</dl>'


def sample_chips():
    """A chip in each status, drawn as the board draws them, but not links: they are examples."""
    samples = [
        dict(id="EX-1", short="Liveness probe", status="done", on=TODAY, kind="minor"),
        dict(id="EX-2", short="Readiness probe", status="open", on=TODAY, kind="minor"),
        dict(id="EX-3", short="Ten seconds in production", status="ready", kind="patch"),
        dict(id="EX-4", short="The probes in the README", status="blocked", waits="the freeze to end", kind="patch"),
        dict(id="EX-5", short="A second exporter", status="dropped", why="EX-2 covers it", kind="minor"),
    ]
    chips = [chip(dict(sample, type="pr", needs=[])) for sample in samples]
    chips = [re.sub(r'^<a class="([^"]*)" href="#[^"]*">(.*)</a>$', r'<span class="\1">\2</span>', html, flags=re.S) for html in chips]
    return f'<div class="chips samples">{"".join(chips)}</div>'


def guides_view(project):
    """The guides: how to use the page, the same on every project, then the project's
    glossary. Its title is on the sheet that holds it."""
    guide = (HERE / "guide.html").read_text(encoding="utf-8")
    for mark, generated in (("<!--statuses-->", statuses_table()), ("<!--kinds-->", kinds_list()), ("<!--chips-->", sample_chips())):
        guide = guide.replace(mark, generated)
    parts = re.findall(r'<section class="block" id="([^"]+)">\s*<h3>(.*?)</h3>', guide)
    entries = project.get("glossary", [])
    terms = ""
    if entries:
        terms = f'<section class="block" id="glossary">\n  <h3>Glossary</h3>\n  {glossary_groups(entries, 4)}\n</section>'
        parts.append(("glossary", "Glossary"))
    contents = "".join(f'<li><a href="#{anchor}">{title}</a></li>' for anchor, title in parts)
    return "\n".join([
        "<p class=\"lede\">How to use this page, then the project's glossary. The guide is the same on every project page; the glossary is this project's own.</p>",
        f'<nav class="contents" aria-label="In this view"><ol>{contents}</ol></nav>',
        guide.strip(),
        terms,
    ])


# ------------------------------------------------------------------ since the last publish

STATE = ("status", "waits", "why", "result", "on")


def raw(data_dir, whose):
    """project.toml and each <phase>.toml in a directory, as written."""
    found = {}
    for key in ["project"] + [key for key, _ in PHASES]:
        path = data_dir / f"{key}.toml"
        if path.is_file():
            try:
                found[key] = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as error:
                problem(f"{whose} {path.name}", f"not valid TOML: {error}")
    return found


def snapshot(files):
    """Each item as written, with its type, its state and the phase that keeps
    that state; and each section, by phase and id."""
    items, sections = {}, {}
    for key, _ in PHASES:
        for section in files.get(key, {}).get("section", []):
            sections[(key, section.get("id"))] = section
            for item in section.get("item", []) if section.get("kind") == "items" else []:
                state = {field: item[field] for field in STATE if field in item}
                items[item.get("id")] = {
                    "phase": key,
                    "section": section.get("id"),
                    "type": item.get("type", section.get("type")),
                    "written": {field: value for field, value in item.items() if field not in STATE},
                    "state": state,
                    "kept": key if state else None,
                }
    for key, _ in PHASES:
        for item_id, entry in files.get(key, {}).get("status", {}).items():
            if item_id in items:
                items[item_id].update(state=dict(entry), kept=key)
    return items, sections


def edits(before, after):
    """What changed between two versions of a table: its fields by label, then its keys."""
    fields = [dict(f for f in version.get("fields", []) if is_field(f)) for version in (before, after)]
    words = [label for label in dict.fromkeys(list(fields[1]) + list(fields[0])) if fields[0].get(label) != fields[1].get(label)]
    words += [f"`{key}`" for key in dict.fromkeys(list(after) + list(before)) if key != "fields" and before.get(key) != after.get(key)]
    return words


def said(snap, state):
    """A state's status in the words of the item's type."""
    status = state.get("status")
    if status not in ITEM_STATUS:
        return "no status"
    return TYPES.get(snap["type"], {}).get("labels", {}).get(status, ITEM_STATUS[status])


def changes_since(data_dir, published):
    """What changed since the data was last published: for each phase, the changes
    in words and the ids its changelog entry names in `changed`; then project.toml's.
    A phase that changed without a new changelog entry is warned about."""
    old, new = raw(published, "the published"), raw(data_dir, "the new")
    (old_items, old_sections), (new_items, new_sections) = snapshot(old), snapshot(new)
    found = {key: ([], []) for key, _ in PHASES}

    def note(key, text, *targets):
        lines, known = found[key]
        lines.append(text)
        known.extend(target for target in targets if target and target not in known)

    def shown_at(key, item_id, item):
        """Where a phase shows a state it keeps: the item's card, or its results."""
        if item["phase"] == key:
            return [anchor_of(item_id)]
        data = new.get(key, {})
        return [s.get("id") for s in data.get("section", []) if s.get("kind") == "results" and item_id in (s.get("ids") or list(data.get("status", {})))]

    for item_id in dict.fromkeys(list(new_items) + list(old_items)):
        before, after = old_items.get(item_id), new_items.get(item_id)
        if after is None:
            section = before["section"] if (before["phase"], before["section"]) in new_sections else None
            note(before["phase"], f"{item_id} removed", section)
            continue
        if before is None:
            note(after["phase"], f"{item_id} added", anchor_of(item_id))
        elif before["written"] != after["written"]:
            note(after["phase"], f"{item_id}: {', '.join(edits(before['written'], after['written']))} edited", anchor_of(item_id))
        was = before["state"] if before else {}
        if was == after["state"]:
            continue
        # A state that is gone was kept where it was; one that is new or changed, where it is.
        key = after["kept"] or before["kept"]
        if was.get("status") != after["state"].get("status"):
            note(key, f"{item_id} {said(after, was)} → {said(after, after['state'])}", *shown_at(key, item_id, after))
        else:
            note(key, f"{item_id}: {', '.join(edits(was, after['state']))} edited", *shown_at(key, item_id, after))

    for (key, section_id), after in new_sections.items():
        before = old_sections.get((key, section_id))
        name = text_of(after.get("title") or section_id)
        if before is None:
            note(key, f"{name} added", section_id)
        elif after.get("kind") == "log" and before.get("kind") == "log":
            added = [e for e in after.get("entry", []) if e not in before.get("entry", [])]
            gone = [e for e in before.get("entry", []) if e not in after.get("entry", [])]
            if gone or {k: v for k, v in before.items() if k != "entry"} != {k: v for k, v in after.items() if k != "entry"}:
                note(key, f"{name} edited", section_id)
            elif added:
                note(key, f"{name}: {len(added)} {'entry' if len(added) == 1 else 'entries'} added", section_id)
        elif {k: v for k, v in before.items() if k != "item"} != {k: v for k, v in after.items() if k != "item"}:
            note(key, f"{name} edited", section_id)
    for (key, section_id), before in old_sections.items():
        if (key, section_id) not in new_sections:
            note(key, f"{text_of(before.get('title') or section_id)} removed")

    for key, _ in PHASES:
        before, after = old.get(key, {}), new.get(key, {})
        for field in dict.fromkeys(list(after) + list(before)):
            if field not in ("section", "status", "changelog") and before.get(field) != after.get(field):
                note(key, f"`{field}` edited")
        fresh = [entry for entry in after.get("changelog", []) if entry not in before.get("changelog", [])]
        if found[key][0] and not fresh:
            warn(f"{key}.toml", "it has changed since the published data, and its changelog has no new entry")

    project = []
    before, after = old.get("project", {}), new.get("project", {})
    for field in dict.fromkeys(list(after) + list(before)):
        if field == "read_at" or before.get(field) == after.get(field):
            continue
        if field != "phases":
            project.append(f"`{field}` edited")
            continue
        for key, name in PHASES:
            was, now = before.get("phases", {}).get(key, {}), after.get("phases", {}).get(key, {})
            if was.get("status", "to-come") != now.get("status", "to-come"):
                project.append(f"{name} {PHASE_STATUS.get(was.get('status', 'to-come'), '?')} → {PHASE_STATUS.get(now.get('status', 'to-come'), '?')}")
            elif was != now:
                project.append(f"{name}: {', '.join(edits(was, now))} edited")
    return found, project


def print_changes(changes):
    found, project = changes
    if not project and not any(lines for lines, _ in found.values()):
        print("Since the published data: nothing has changed.")
        return
    print("Since the published data:")
    for key, name in PHASES:
        lines, targets = found[key]
        if lines:
            print(f"  {name}: {'; '.join(lines)}.")
            if targets:
                print(f"    changed = {json.dumps(targets)}")
    if project:
        print(f"  project.toml: {'; '.join(project)}.")


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


def stylesheet(project, data_dir):
    """The kit's styles, then the project's own, from `css`."""
    css = (HERE / "page.css").read_text(encoding="utf-8")
    for extra in project.get("css", []):
        path = data_dir / extra
        if path.is_file():
            css += "\n" + path.read_text(encoding="utf-8")
        else:
            problem("project.toml", f"`css` names {extra}, which does not exist beside project.toml")
    return css


def progress():
    """For each phase, how many of the statuses it keeps are done, of those not Dropped."""
    counts = {}
    for item in ITEMS.values():
        key, status = item.get("status_from"), item.get("status")
        if key and status in ITEM_STATUS and status != "dropped":
            done, total = counts.get(key, (0, 0))
            counts[key] = (done + (status == "done"), total + 1)
    return counts


ICONS = {
    "agenda": '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3" width="12" height="11" rx="2.5"/><path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3"/></svg>',
    "guides": '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="M6.2 6.3a1.85 1.85 0 1 1 2.7 1.6c-.6.33-.9.75-.9 1.35v.25"/><path d="M8 11.4v.1"/></svg>',
    "close": '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>',
}


def sheet(key, name, note, inner, src=""):
    """A view that isn't a phase: a sheet over the whole page, its title and its close
    button on a bar that stays in sight."""
    span = f'<span class="span">{note}</span>' if note else ""
    return (
        f'<dialog class="sheet" aria-labelledby="{key}-title">\n'
        f'  <div class="sheet-bar"><div class="sheet-in"><h2 id="{key}-title">{name}</h2>{span}'
        f'<button type="button" class="close" aria-label="Close the {name.lower()}">{ICONS["close"]}</button></div></div>\n'
        f'  <div class="sheet-in"><section class="phase" id="{key}" data-phase="{key}"{src}>{inner}</section></div>\n'
        "</dialog>"
    )


def page(project, sections, opening, inline, data_dir, agenda_html, months_html, ball_html, guides_html):
    css = stylesheet(project, data_dir)
    title = f'{project.get("repo", "")}-{project.get("objective", "")}'
    counts = progress()
    # The views that aren't phases: the agenda, and the guides to using the page.
    views = "".join(f'<a href="#{key}" data-phase="{key}">{ICONS[key]}<span>{name}</span></a>' for key, name in (("agenda", "Agenda"), ("guides", "Guides")))
    tabs = []
    for number, (key, name) in enumerate(PHASES, start=1):
        status = project["status"][key]["status"]
        current = ' aria-current="true"' if key == opening else ""
        state = PHASE_STATUS[status]
        # A phase in progress says how far it is.
        if status == "now" and key in counts:
            done, total = counts[key]
            state += f' <span class="count" title="{done} of {total} done, dropped items aside">{done}/{total}</span>'
        tabs.append(
            f'<li><a href="#{key}" data-phase="{key}" class="t-{status}"{current}><span class="n">{number}</span>'
            f'<span class="name">{name}</span><span class="state">{state}</span></a></li>'
        )
    shells, files = [], {}
    for key, _ in PHASES:
        hidden = "" if key == opening else " hidden"
        if inline or key == opening or not sections[key][1]:
            shells.append(f'<section class="phase" id="{key}" data-phase="{key}"{hidden}>\n{sections[key][0]}\n</section>')
        else:
            files[key] = sections[key][0] + "\n"
            shells.append(f'<section class="phase" id="{key}" data-phase="{key}" data-src="phases/{key}.html" hidden></section>')
    sheets = [sheet("agenda", "Agenda", f"as of {weekday(TODAY)}", f"\n{agenda_html}\n")]
    if inline:
        sheets.append(sheet("guides", "Guides", "", f"\n{guides_html}\n"))
    else:
        files["guides"] = guides_html + "\n"
        sheets.append(sheet("guides", "Guides", "", "", ' data-src="phases/guides.html"'))
    read_at = project["read_at"]
    # What the agent reads again before each publish is the PRs, from GitHub.
    read = "PR statuses" if any(item["type"] == "pr" for item in ITEMS.values()) else "Statuses"
    return title, files, f"""<meta charset="utf-8">
<title>{esc(title)}</title>
{FONTS}
<style>
{css}
</style>
<div class="wrap">
<header class="top">
  <div class="bar">
    <p class="eyebrow">{esc(project.get("repo", ""))} · project page</p>
    <nav class="views" aria-label="Views">{views}</nav>
  </div>
  <h1>{esc(title)}</h1>
  <p class="lede">{project.get("summary", "")}</p>
  <div class="now">
    <div class="months" role="group" aria-label="Calendar">{months_html}</div>
    <p class="glance">{read} as of {read_at.day} {read_at:%b %Y}, {read_at:%H:%M} UTC.</p>
  </div>
  {ball_html}
  <nav class="phases" aria-label="Phases"><ol>{"".join(tabs)}</ol></nav>
</header>
<main id="phases" data-open="{opening}">
{chr(10).join(shells)}
</main>
{chr(10).join(sheets)}
</div>
"""


# ------------------------------------------------------------------ the retrospective, alone


def counted(project, phases):
    """The headline figures the data can count, as (value, label) pairs, leaving out a zero."""

    def done(kind, kinds=None):
        return sum(1 for item in ITEMS.values() if item["type"] == kind and item.get("status") == "done" and (kinds is None or item.get("kind") in kinds))

    figures = [
        (done("pr"), "PR merged", "PRs merged"),
        (done("pr", ("major", "minor", "patch")), "release", "releases"),
        (done("decision"), "decision taken", "decisions taken"),
        (done("setting"), "setting changed by hand", "settings changed by hand"),
        (done("lesson"), "lesson adopted", "lessons adopted"),
    ]
    # The project's span: what happened, not what is announced.
    dates = [date for date, cls, *_ in dated(project, phases) if cls != "event"]
    if dates:
        figures.append(((max(dates) - min(dates)).days + 1, "day, start to finish", "days, start to finish"))
    return [(str(value), one if value == 1 else many) for value, one, many in figures if value]


def retrospective_page(project, phases, data_dir):
    """The Retrospective alone, as a page to share: no tabs, no calendar and no
    script, and the items it doesn't hold named as text rather than linked."""
    global LINKABLE
    title = f'{project.get("repo", "")}-{project.get("objective", "")}-retrospective'
    data = phases.get("retrospective")
    if not data:
        problem("retrospective.toml", "the Retrospective has no data yet")
        return title, ""
    LINKABLE = {item_id for item_id, item in ITEMS.items() if item["phase"] == "retrospective"}
    body = render_phase("retrospective", project["status"]["retrospective"], data, data_dir, head=False)
    read_at = project["read_at"]
    text = f"""<meta charset="utf-8">
<title>{esc(title)}</title>
{FONTS}
<style>
{stylesheet(project, data_dir)}
</style>
<div class="wrap">
<header class="top">
  <p class="eyebrow">{esc(project.get("repo", ""))} · retrospective</p>
  <h1>{esc(title)}</h1>
  <p class="lede">{project.get("summary", "")}</p>
  <p class="readat">Written from the project's data, read on {read_at.day} {read_at:%B %Y}.</p>
</header>
<main>
<section class="phase" id="retrospective">
{body}
</section>
</main>
{site_footer(glossary(project.get("glossary", [])), "Built with <code>/project-page</code> from the data behind the project's page.")}
</div>
"""
    return title, expand_refs(text, "project.toml")


def failed():
    """Prints the problems, or else the warnings, and says whether there were problems."""
    if not problems:
        for line in warnings:
            print(f"warning: {line}", file=sys.stderr)
        return False
    for line in problems:
        print(line, file=sys.stderr)
    print(f"{len(problems)} problem{'s' if len(problems) != 1 else ''}; nothing written.", file=sys.stderr)
    return True


def main(argv):
    args, flags, since = [], [], None
    rest = iter(argv)
    for arg in rest:
        if arg == "--since":
            since = next(rest, "")
        elif arg.startswith("-"):
            flags.append(arg)
        else:
            args.append(arg)
    if len(args) != 2 or len(flags) > 1 or any(flag not in ("--inline", "--retrospective") for flag in flags) or since == "":
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    if since is not None and not Path(since).is_dir():
        print(f"--since {since}: no such directory; it holds the data as last published", file=sys.stderr)
        return 2
    data_dir, out_dir = Path(args[0]), Path(args[1])
    project = read_project(data_dir)
    phases = read_phases(data_dir)
    collect_items(phases)
    link_items()
    if not problems:
        check_states(project, phases)
    changes = changes_since(data_dir, Path(since)) if since is not None else None
    COUNTED.extend(counted(project, phases))
    warned = f"; {len(warnings)} warning{'s' if len(warnings) != 1 else ''}" if warnings else ""
    if "--retrospective" in flags:
        title, text = retrospective_page(project, phases, data_dir)
        check([("retrospective.html", text)])
        if failed():
            return 1
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "retrospective.html").write_text(text, encoding="utf-8")
        print(f"{title}: retrospective.html, {len(text.encode()) // 1024} KB{warned}")
        if changes:
            print_changes(changes)
        return 0
    inline = "--inline" in flags
    sections = {}
    for key, _ in PHASES:
        sections[key] = (render_phase(key, project["status"][key], phases.get(key), data_dir), key in phases)
    agenda_html, months_html, ball_html = calendar_view(project, phases)
    opening = opening_phase(project["status"])
    guides_html = expand_refs(guides_view(project), "project.toml [[glossary]]")
    title, files, shell = page(project, sections, opening, inline, data_dir, agenda_html, months_html, ball_html, guides_html)
    shell = expand_refs(shell, "project.toml")
    fragments = [("the page", shell)] + [(f"phases/{key}.html", text) for key, text in files.items()]
    check(fragments)
    if failed():
        return 1
    # Which view holds each id, so a link into a phase not loaded yet opens it.
    phase_of = {}
    for key, (text, _) in list(sections.items()) + [("agenda", (agenda_html, True)), ("guides", (guides_html, True))]:
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
    print(f"{title}: index.html, {len(out.encode()) // 1024} KB, opening on {PHASE_NAME[opening]}; loaded when picked: {loaded}{warned}")
    if changes:
        print_changes(changes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
