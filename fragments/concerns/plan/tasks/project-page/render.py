#!/usr/bin/env python3
"""Builds a project page from its TOML data, and checks it.

Usage: python3 render.py <data-dir> <out-dir> [--inline | --retrospective] [--since <published-dir>]

<data-dir> holds project.toml and a <phase>.toml for each phase with content.
<out-dir> gets index.html, the page to publish, and phases/<phase>.html for
every other phase with content, which the page loads when that phase is
picked. --inline puts every phase in index.html instead, for a preview or a
small project. --retrospective writes retrospective.html instead: the
Retrospective alone, as a page to share. --since, given the data as it was
last published, also prints what has changed in each phase since, to tell the
user when publishing.

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
    ("deferred", "Deferred"),
]
PHASE_NAME = dict(PHASES)
# What the project leaves, after the six phases and unnumbered, since they don't run in
# their order: what another project can take, the story of this one, and what waits.
LEAVES = ("reuse", "retrospective", "deferred")
# The phases' order. A phase starts once those it follows are done, or not needed, but
# Verify and Reuse, which start once Build has; one that starts early says why. A phase
# that runs beside others ends only after them, and never early.
FOLLOWS = {"research": ("brief",), "analysis": ("research",), "plan": ("analysis",), "build": ("plan",), "retrospective": ("build", "verify")}
STARTS_WITH = {"verify": "build", "reuse": "build"}
ENDS_AFTER = {"verify": ("build",), "reuse": ("build", "verify"), "retrospective": ("brief", "research", "analysis", "plan", "build", "verify", "reuse")}
# The phases that keep the statuses of live work, which reopen when new work comes in.
LIVE = ("build", "verify")
PHASE_STATUS = {"done": "Done", "now": "Now", "to-come": "To come", "not-needed": "Not needed"}
ITEM_STATUS = {"done": "Done", "open": "Open", "ready": "Ready", "blocked": "Blocked", "happened": "Happened", "deferred": "Deferred", "to-move": "To be moved", "moved": "Moved", "dropped": "Dropped"}
UNFINISHED = {"open", "ready", "blocked"}
# Set aside: out of its phase's way until a trigger comes, or until another project takes
# it, and listed in Deferred. A moved item is done with here.
PARKED = ("deferred", "to-move")
# The types of item that can come true: a risk that does is no longer a risk.
HAPPENS = ("risk",)
# The types of item that carry out a decision.
CARRY_OUT = ("pr", "setting")
KINDS = {"major": "Major", "minor": "Minor", "patch": "Patch", "owner": "Owner"}
# What a status reads as for each type of item, and what the user does while one is open;
# for some, what its `needs` read as on its card, and on the cards of what it needs.
TYPES = {
    "piece": {"labels": {}, "ask": "Read"},
    "rule": {"labels": {"dropped": "Retired"}, "ask": "Confirm"},
    "criterion": {"labels": {"open": "To agree", "blocked": "Not met yet", "done": "Met"}, "ask": "Agree", "needs": "Verified by", "needed_by": "Verifies"},
    "decision": {"labels": {"open": "To decide", "done": "Taken", "dropped": "Not taken"}, "ask": "Decide"},
    "question": {"labels": {"open": "To answer", "done": "Answered", "dropped": "Withdrawn"}, "ask": "Answer"},
    "pr": {"labels": {"open": "To merge", "done": "Merged", "dropped": "Closed"}, "ask": "Merge"},
    "setting": {"labels": {"open": "To set", "done": "Set", "dropped": "Not needed"}, "ask": "Set"},
    "risk": {"labels": {"open": "To accept", "blocked": "Open", "done": "Closed", "dropped": "Accepted"}, "ask": "Accept", "waits": "closes with", "needs": "Closes with", "needed_by": "Closes"},
    "check": {"labels": {"open": "To check", "blocked": "Waiting", "done": "Passed", "dropped": "Skipped"}, "ask": "Check"},
    "lesson": {"labels": {"open": "To review", "done": "Adopted", "dropped": "Not adopted"}, "ask": "Review"},
    "deferred": {"labels": {"blocked": "Waiting", "done": "Picked up"}, "ask": "Start"},
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
    "deferred": ("Deferred work", "T1"),
}
# The types of card each phase holds: a card of any other type belongs elsewhere.
PHASE_TYPES = {
    "brief": ("criterion", "rule"),
    "research": ("piece",),
    "analysis": ("decision",),
    "plan": ("pr", "setting", "risk"),
    "build": ("question",),
    "verify": ("check",),
    "reuse": (),
    "retrospective": ("lesson",),
    "deferred": ("deferred", "question"),
}
# The kinds of section a phase is held to, where it is: the Analysis is its decisions,
# the Plan its PRs, settings and risks, Build its board, results and questions,
# Verify its checks and where the success criteria stand, and Reuse its pieces, each
# with how to take it; and where what they leave out goes.
PHASE_KINDS = {"analysis": ("items",), "plan": ("items",), "build": ("board", "results", "items"), "verify": ("items", "results"), "reuse": ("defs",)}
ELSEWHERE = {
    "analysis": "anything else, such as evidence in a table, goes in the Research, and the cards link to it",
    "plan": "anything else, such as evidence in a table, goes in the Research, and the cards link to it",
    "build": "what happened is in the Agenda, and what came of an item is its Result",
    "verify": "what happened is in the Agenda, and what a check showed is in its card",
    "reuse": "what happened is in the Agenda, and how a piece was built is in the items its entry links",
}
# The phases that open with a list of their sections, built from them.
CONTENTS = ("analysis", "plan")
KIND_MEANING = {
    "major": "Merging it releases a major version: what used the last one may need changing.",
    "minor": "Merging it releases a minor version: something new, and nothing that worked breaks.",
    "patch": "Merging it releases a patch: a fix, with nothing new.",
    "owner": "Only the owner can do it, such as a setting in a service they own.",
}
SECTION_KINDS = ("prose", "table", "repos", "items", "board", "results", "figures", "defs", "timeline", "roads", "risks", "cost", "next", "decisions")
# The Retrospective's record, built from the other phases rather than written: how the
# phases went, what was dropped, the risks, what it cost, what waits, and every decision.
BUILT = ("timeline", "roads", "risks", "cost", "next", "decisions")
SOURCES = {"coined": "Coined for this project", "borrowed": "Borrowed from elsewhere"}
# What a project does with each repository it involves, as the chip beside its name says.
USES = {"change": "Change", "read": "Read", "new": "New"}
USE_MEANING = {
    "change": "The project's PRs land in it.",
    "read": "The project reads it, and changes nothing in it.",
    "new": "The project creates it.",
}

KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ITEM_ID = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*")
# [[D1]] in any text: a link to the item, with its id and its short title.
REF = re.compile(r"\[\[([^\]]*)\]\]")
# [[HMI-8]]'s: a possessive on a link, which the page reads as its short title's.
POSSESSIVE = re.compile(r"\[\[([^\]]*)\]\]['\u2019]s\b")
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
STATES = {}  # each phase's state and dates, as project.toml gives them
TODAY = None  # the day the state was read
LINKABLE = None  # the ids a reference links to, on a page that holds only some; None for all
COUNTED = []  # the headline figures counted from the data, for a `figures` section with `auto`
SPAN = []  # the project's first and last day, from every date it holds but its events
SCRIPTED = True  # whether the page runs page.js; the Retrospective alone doesn't


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
        if not isinstance(entry.get("early", ""), str):
            problem(where, "`early` says why the phase starts before those it follows are done")
        reopened = []
        for index, again in enumerate(entry.get("reopened", [])):
            ended = as_date(again.get("ended"), where, f"reopened {index + 1}: ended") if isinstance(again, dict) else None
            on = as_date(again.get("on"), where, f"reopened {index + 1}: on") if isinstance(again, dict) else None
            if ended is None or on is None or on < ended:
                problem(where, "each of `reopened` is { ended = <date>, on = <date> }: the day the phase ended, and the later day it reopened")
                continue
            reopened.append((ended, on))
        project["status"][key] = {
            "status": status,
            "why": entry.get("why", ""),
            "start": as_date(entry.get("start"), where, "start"),
            "end": as_date(entry.get("end"), where, "end"),
            "early": entry.get("early", "") if isinstance(entry.get("early", ""), str) else "",
            "reopened": reopened,
        }
    check_order(project["status"])
    STATES.update(project["status"])
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
        if not isinstance(event.get("automated", False), bool):
            problem(where, "`automated` is true or false: true for a run that starts on its own, such as a scheduled workflow")
    handoff = project.get("handoff")
    if handoff is not None:
        handoff["updated"] = as_date(handoff.get("updated"), "project.toml [handoff]", "updated")
        if not all(isinstance(note, str) for note in handoff.get("notes", [])):
            problem("project.toml [handoff]", "`notes` is a list of texts")
    return project


def names(keys):
    words = [PHASE_NAME[key] for key in keys]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def check_order(statuses):
    """The phases' order, in their states and their dates: a phase starts once those it
    follows are done, or with `early` saying why, and ends only after those it runs beside."""
    finished = {key for key, state in statuses.items() if state["status"] in ("done", "not-needed")}
    started = {key for key, state in statuses.items() if state["status"] in ("now", "done")}
    for key, name in PHASES:
        state, where = statuses[key], f"project.toml [phases.{key}]"
        if key in started and not state["early"]:
            waiting = [other for other in FOLLOWS.get(key, ()) if other not in finished]
            if waiting:
                problem(where, f"{name} has started, but {names(waiting)} {'isn' if len(waiting) == 1 else 'aren'}'t done: say why it starts early, in `early`")
            if key in STARTS_WITH and STARTS_WITH[key] not in started:
                problem(where, f"{name} has started, but {PHASE_NAME[STARTS_WITH[key]]} hasn't: say why it starts early, in `early`")
            for other in FOLLOWS.get(key, ()):
                if state["start"] and statuses[other]["end"] and state["start"] < statuses[other]["end"]:
                    problem(where, f"{name} starts on {day(state['start'])}, before {PHASE_NAME[other]} ends on {day(statuses[other]['end'])}: say why, in `early`")
            other = STARTS_WITH.get(key)
            if other and state["start"] and statuses[other]["start"] and state["start"] < statuses[other]["start"]:
                problem(where, f"{name} starts on {day(state['start'])}, before {PHASE_NAME[other]} starts on {day(statuses[other]['start'])}: say why, in `early`")
        if state["status"] == "done":
            open_ = [other for other in ENDS_AFTER.get(key, ()) if other not in finished]
            if open_:
                problem(where, f"{name} is done, but {names(open_)} {'isn' if len(open_) == 1 else 'aren'}'t: it ends only after {'it' if len(open_) == 1 else 'them'}")
            for other in ENDS_AFTER.get(key, ()):
                if state["end"] and statuses[other]["end"] and state["end"] < statuses[other]["end"]:
                    problem(where, f"{name} ends on {day(state['end'])}, before {PHASE_NAME[other]} ends on {day(statuses[other]['end'])}")


def read_phases(data_dir, statuses):
    data = {}
    for key, name in PHASES:
        path = data_dir / f"{key}.toml"
        if path.is_file() and statuses[key]["status"] == "not-needed":
            # Its tab doesn't open, so nothing in the file would show.
            problem(path.name, f"{name} is not needed, so it holds nothing: remove the file, or give the phase another status")
        elif path.is_file():
            loaded = load(path)
            if loaded is not None:
                data[key] = loaded
                loaded["approved"] = as_date(loaded.get("approved"), f"{key}.toml", "approved")
    return data


def is_pair(value):
    return isinstance(value, list) and len(value) == 2 and all(isinstance(part, str) for part in value)


def is_field(value):
    """A [label, text] pair, its text one string or a list of them."""
    if not (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)):
        return False
    text = value[1]
    return isinstance(text, str) or (isinstance(text, list) and all(isinstance(part, str) for part in text))


def is_chip(text):
    """A field's text that is one pill and nothing else, which a card shows as a chip."""
    return isinstance(text, str) and re.fullmatch(r'<span class="pill[^"]*">[^<]*</span>', text.strip()) is not None


def section_names(sections):
    """Each section's name, by id: its title; or, for one without a title, which carries
    on the section before it, that section's title."""
    names, last = {}, None
    for section in sections:
        last = section.get("title") or last
        if section.get("id"):
            names[section["id"]] = last or section["id"]
    return names


def texts_of(text):
    return text if isinstance(text, list) else [text]


def check_status(entry, item_type, where):
    status = entry.get("status")
    if status is None:
        return
    if status not in ITEM_STATUS:
        problem(where, f"status `{status}` is not one of {', '.join(ITEM_STATUS)}")
    elif status == "blocked" and not entry.get("waits") and not entry.get("needs"):
        problem(where, "a blocked item says what it waits on, in `waits` or `needs`")
    elif status == "dropped" and not entry.get("why"):
        problem(where, "a dropped item says why, in `why`")
    elif status == "happened" and item_type not in HAPPENS:
        problem(where, "only a risk happens: any other item that is finished is `done`")
    elif status == "happened" and not entry.get("result"):
        problem(where, "a risk that happened names, in `result`, the question or the blocker that took it over")
    elif status == "blocked" and entry.get("waits") == "owner":
        problem(where, "an item that waits on the owner is `open`: `waits = \"owner\"` is for one deferred until they say")
    elif status == "deferred" and not entry.get("waits") and not entry.get("needs"):
        problem(where, "a deferred item says what it waits on, in `waits` or `needs`")
    elif status == "to-move" and not entry.get("to"):
        problem(where, "an item to be moved names the project that takes it, in `to`")
    elif status == "moved" and not str(entry.get("to", "")).startswith("https://"):
        problem(where, "a moved item links its card on the other project's page, in `to`, an https:// address")


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
                item_type = item.get("type", section.get("type"))
                if item_type is not None and item_type not in TYPES:
                    problem(where, f"`type` is one of {', '.join(TYPES)}")
                    item_type = None
                check_status(item, item_type, where)
                if item_type is not None and item_type not in PHASE_TYPES[key]:
                    holders = " or ".join(PHASE_NAME[phase] for phase, types in PHASE_TYPES.items() if item_type in types)
                    problem(where, f"a card of type `{item_type}` belongs in {holders}, not in {PHASE_NAME[key]}")
                if item.get("kind") and item["kind"] not in KINDS:
                    problem(where, f"`kind` is one of {', '.join(KINDS)}")
                if not all(is_field(field) for field in item.get("fields", [])):
                    problem(where, "each of `fields` is a [label, text] pair, its text one string or a list of them")
                url = item.get("url")
                if url is not None and not (isinstance(url, str) and url.startswith("https://")):
                    problem(where, "`url` is an https:// address, such as the PR's on GitHub")
                origin = item.get("from")
                if origin is not None and not (isinstance(origin, str) and origin.startswith("https://")):
                    problem(where, "`from` is the https:// address of its card on the page it moved from")
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
                    batch=section.get("title") or section.get("id", ""),
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
            check_status(dict(entry, needs=item["needs"]), item["type"], where)
            for field in ("status", "waits", "why", "result", "to"):
                if field in entry:
                    item[field] = entry[field]
            if "on" in entry:
                item["on"] = as_date(entry["on"], where, "on")
            item["status_from"] = key
    # A risk is written before what it describes: one added after it happened was a question or a blocker.
    for item_id, item in ITEMS.items():
        written = item["amended"] and item["amended"]["on"]
        if item.get("status") == "happened" and written and item["on"] and item["on"] < written:
            problem(item["where"], f"{item_id} happened on {day(item['on'])}, before it was written on {day(written)}: what has already happened is a question or a blocker, not a risk")


def link_items():
    """`needs` checked for unknown ids and loops; backlinks from needs and references."""
    for item_id, item in ITEMS.items():
        item["needed_by"], item["mentioned_in"] = [], []
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
            if ref in ITEMS and ref != item_id and ref not in item["needs"] and item_id not in ITEMS[ref]["mentioned_in"]:
                ITEMS[ref]["mentioned_in"].append(item_id)


def check_states(project, phases):
    """Warnings for what looks stale: the mistakes a page makes when it isn't re-read.
    They name statuses as the data writes them, since the data is what to fix."""
    statuses = project["status"]
    has_prs = any(item["type"] == "pr" for item in ITEMS.values())
    for item_id, item in ITEMS.items():
        where, status = item["where"], item.get("status")
        if status in UNFINISHED and item["status_from"] and statuses[item["status_from"]]["status"] == "done":
            # Live work reopens its phase; anywhere else, a done phase holding it looks stale.
            if item["status_from"] in LIVE:
                problem(where, f"{PHASE_NAME[item['status_from']]} is done, but {item_id} is still `{status}`: new work reopens it, with `reopened`")
            elif not item["amended"]:
                warn(where, f"{PHASE_NAME[item['status_from']]} is done, but {item_id} is still `{status}`")
        if item["type"] == "decision" and status == "done" and has_prs:
            if not any(ITEMS[other]["type"] in CARRY_OUT for other in item["needed_by"] + item["mentioned_in"]):
                warn(where, f"{item_id} is a decision taken, but no PR or setting names it or needs it")
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
            # An amendment comes after its phase's approval, or after its end in a phase without one.
            approved, end = phases.get(item["phase"], {}).get("approved"), statuses[item["phase"]]["end"]
            if approved and item["amended"]["on"] < approved:
                warn(where, f"{item_id} is amended on {day(item['amended']['on'])}, before its phase was approved")
            elif not approved and end and item["amended"]["on"] < end:
                warn(where, f"{item_id} is amended on {day(item['amended']['on'])}, before its phase ended on {day(end)}")
    # The last change the data records: the newest day an item reached its status, or was amended.
    changed = [item["on"] for item in ITEMS.values() if item.get("on")] + [item["amended"]["on"] for item in ITEMS.values() if item["amended"] and item["amended"]["on"]]
    if changed and max(changed) > TODAY:
        warn("project.toml", f"`read_at` is older than the newest status, of {day(max(changed))}: read the state again")
    handoff = project.get("handoff")
    if handoff and handoff.get("updated") and changed and handoff["updated"] < max(changed):
        warn("project.toml [handoff]", f"the notes for the next session date from {day(handoff['updated'])}, before the last change")


def check_wording(project, phases):
    """Warnings for a possessive on a link: [[HMI-8]]'s merge reads as "HMI-8 Bump and
    release callers's merge", since a link carries its short title."""

    def walk(value, where):
        if isinstance(value, str):
            for ref in POSSESSIVE.findall(value):
                if ref in ITEMS:
                    warn(where, f"[[{ref}]]'s reads as \"{ref} {short_of(ITEMS[ref])}'s\": put the link after its noun, as in \"the merge of [[{ref}]]\"")
        elif isinstance(value, dict):
            for inner in value.values():
                walk(inner, where)
        elif isinstance(value, list):
            for inner in value:
                walk(inner, where)

    for key, data in phases.items():
        for section in data.get("section", []):
            for item in section.get("item", []):
                walk(item, f"{key}.toml item {item.get('id', '(no id)')}")
            walk({name: value for name, value in section.items() if name != "item"}, f"{key}.toml section {section.get('id', '(no id)')}")
        for item_id, entry in data.get("status", {}).items():
            walk(entry, f"{key}.toml [status.{item_id}]")
    walk(project, "project.toml")


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


def state_line(item):
    """A board chip's status badge, with when it was reached, what a Blocked or Deferred
    item waits on, where one To be moved goes, or why one was Dropped, its references as
    text, since the chip is a link."""
    status = item.get("status")
    if not status or status not in ITEM_STATUS:
        return ""
    line = f'<span class="st st-{status}">{label_of(item)}</span>'
    if item.get("on"):
        line += f' <span class="on">{day(item["on"])}</span>'
    note = ""
    if status == "deferred" and item.get("waits") == "owner":
        line += f' <span class="mine">{yours(item)}</span>'
    elif status in ("blocked", "deferred"):
        note = item.get("waits") or refs_list(item["needs"])
        prefix = TYPES.get(item.get("type"), {}).get("waits", "waits on")
        note = f"{prefix} {note}" if note else ""
    elif status == "to-move":
        note = f"to {item.get('to', '')}"
    elif status == "dropped":
        note = item.get("why", "")
    if note:
        line += f' <span class="waits">{refs_as_text(note)}</span>'
    return line


def card_html(number, title, tags=(), rows=(), anchor=None, says=False, fold=False):
    """A card: its number and title on its first line, its chips under the title, then
    its fields, each a label and its text. `says` writes the title as a sentence rather
    than a heading, for a card that records something, such as an approval. A
    card with neither number nor title is its fields alone. `fold` shows the first
    two layers and keeps the fields behind them, opened by a click."""
    attr = f' id="{anchor}"' if anchor else ""
    if fold and rows:
        tagline = f'<span class="item-tags">{"".join(tags)}</span>' if tags else ""
        fields = "<dl>" + "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows) + "</dl>"
        summary = f'<summary class="item-head"><span class="n">{number or ""}</span><h4>{title}</h4>{tagline}</summary>'
        return f'  <article class="item"{attr}>\n    <details class="fold">\n      {summary}\n      {fields}\n    </details>\n  </article>'
    parts = []
    if number is not None or title is not None:
        name = f'<p class="says">{title}</p>' if says else f"<h4>{title}</h4>"
        parts.append(f'<div class="item-head"><span class="n">{number or ""}</span>{name}</div>')
    if tags:
        parts.append(f'<div class="item-tags">{"".join(tags)}</div>')
    if rows:
        parts.append("<dl>" + "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows) + "</dl>")
    return f'  <article class="item"{attr}>\n    ' + "\n    ".join(parts) + "\n  </article>"


def status_pill(item):
    """An item's status as a chip, in the words of its type, with the day it got there."""
    when = f' · {day(item["on"])}' if item.get("on") else ""
    return f'<span class="pill st-{item["status"]}">{label_of(item)}{when}</span>'


def day_pill(date):
    """The day a record card is about, as a chip under its sentence."""
    return f'<span class="pill day">{day(date)}</span>'


def yours(item):
    """What the owner gives to start an item deferred until they say: a call on a question
    or a decision, a go on anything else."""
    return "Your call" if item.get("type") in ("question", "decision") else "Your go"


def waits_label(item):
    return TYPES.get(item.get("type"), {}).get("waits", "waits on").capitalize()


def waits_tag(item):
    """What a waiting item waits on, or where it goes, as words beside its chip, as a board
    chip says it: a folded card shows it, and its references are text, since a summary is a
    toggle. One deferred until the owner says, and a moved item, have a chip instead: the
    owner's, and one to its card on the page that took it."""
    status = item.get("status")
    if status == "moved":
        return f'<a class="pill link" href="{esc(item.get("to", ""))}" target="_blank" rel="noopener">Its new page</a>'
    if status == "to-move":
        return f'<span class="waits">to {refs_as_text(item.get("to", ""))}</span>'
    if status not in ("blocked", "deferred"):
        return ""
    if status == "deferred" and item.get("waits") == "owner":
        return f'<span class="pill ask">{yours(item)}</span>'
    note = item.get("waits") or refs_list(item["needs"], plain=True)
    prefix = TYPES.get(item.get("type"), {}).get("waits", "waits on")
    return f'<span class="waits">{prefix} {refs_as_text(note)}</span>' if note else ""


def card(item):
    """An item's card: its number and summary; then chips, for what a word or two says;
    then, folded behind those until the reader opens them, its fields, and the items
    that need it or mention it."""
    short = item.get("short")
    fields = [field for field in item.get("fields", []) if is_field(field)]
    tags = []
    if item.get("kind") in KINDS:
        tags.append(f'<span class="pill k-{item["kind"]}">{KINDS[item["kind"]]}</span>')
    # A field that is one pill and nothing else is a chip, so a folded card shows it.
    tags += [field[1].strip() for field in fields if is_chip(field[1])]
    # A status set from another phase shows there: the card keeps the record as written.
    own = item.get("status_from") == item["phase"] and item.get("status") in ITEM_STATUS
    # A criterion is agreed in the Brief, though Verify keeps its status: its card in the
    # Brief says so until the owner agrees it, and again once it is dropped, with why.
    shown = own or (item["type"] == "criterion" and item.get("status") in ("open", "dropped"))
    if shown:
        tags.append(status_pill(item))
        if waits_tag(item):
            tags.append(waits_tag(item))
    if item["amended"]:
        when = f' {day(item["amended"]["on"])}' if item["amended"]["on"] else ""
        tags.append(f'<span class="pill amended">Amended{when}</span>')
    if isinstance(item.get("url"), str):
        tags.append(link_html(item["url"]))
    if isinstance(item.get("from"), str):
        tags.append(f'<a class="pill link" href="{esc(item["from"])}" target="_blank" rel="noopener">Its old page</a>')
    rows = []
    if short and short != text_of(item.get("title", "")):
        rows.append(("Title", item.get("title", "")))
    options = item.get("options")
    if isinstance(options, list) and options and all(is_pair(option) for option in options):
        rows.append(("Options", options_html(item)))
    rows += [(field[0], list_html(field[1]) if isinstance(field[1], list) else field[1]) for field in fields if not is_chip(field[1])]
    if shown and item["status"] == "dropped":
        rows.append(("Why", item.get("why", "")))
    if item["needs"]:
        rows.append((TYPES.get(item["type"], {}).get("needs", "Needs"), refs_ul(item["needs"])))
    if item["amended"]:
        rows.append(("Why amended", item["amended"]["why"]))
    # What needs this item, in the words of its type: a check Verifies the criteria that need it.
    needed_by = {}
    for other in item["needed_by"]:
        needed_by.setdefault(TYPES.get(ITEMS[other]["type"], {}).get("needed_by", "Needed by"), []).append(other)
    rows += [(label, refs_ul(ids)) for label, ids in needed_by.items()]
    # A decision is carried out by the PRs and settings that name it; anything else mentions it.
    carried = [other for other in item["mentioned_in"] if item["type"] == "decision" and ITEMS[other]["type"] in CARRY_OUT]
    mentioned = [other for other in item["mentioned_in"] if other not in carried]
    if carried:
        rows.append(("Carried out by", refs_ul(carried)))
    if mentioned:
        rows.append(("Mentioned in", refs_ul(mentioned)))
    return card_html(esc(item["id"]), short or item.get("title", ""), tags, rows, anchor_of(item["id"]), fold=True)


def linked_name(item):
    """An item's summary, linked to its own card where the page holds it."""
    name = short_of(item)
    if LINKABLE is None or item["id"] in LINKABLE:
        name = f'<a class="ref" href="#{anchor_of(item["id"])}">{name}</a>'
    return name


def result_card(item, on_board=False):
    """Where an item stands, in the phase that keeps its status: its number, and its
    summary linked to its own card; its status as a chip; then what it waits on, why
    it was dropped, or what came of it, folded as an item's card is. For an item on the
    board, which says the rest, only what came of it."""
    name = linked_name(item)
    status, tags, rows = item.get("status"), [], []
    if not on_board and status in ITEM_STATUS:
        tags.append(status_pill(item))
        if waits_tag(item):
            tags.append(waits_tag(item))
        # The items it waits on stay links, under the fold.
        if status in ("blocked", "deferred") and not item.get("waits") and item["needs"]:
            rows.append((waits_label(item), refs_ul(item["needs"])))
        elif status == "dropped":
            rows.append(("Why", item.get("why", "")))
    if item.get("result"):
        rows.append(("Result", item["result"]))
    return card_html(esc(item["id"]), name, tags, rows, fold=True)


def chip(item):
    """An item on the board: its stripe and tint say its status, and its kind is a word."""
    classes = ["chip"]
    if item.get("status") in ITEM_STATUS:
        classes.append(f's-{item["status"]}')
    line = state_line(item)
    if item.get("kind") in KINDS:
        line += f' <span class="kind">{KINDS[item["kind"]]}</span>'
    tail = f'<span class="w">{line.strip()}</span>' if line else ""
    return f'<a class="{" ".join(classes)}" href="#{anchor_of(item["id"])}"><b>{esc(item["id"])}</b><span>{short_of(item)}</span>{tail}</a>'


def table_html(head, rows, min_width=None, cls=None, start=None):
    """A table in a box that scrolls; `start` is the column the box opens at, its first
    column kept beside it."""
    attrs = f' class="{cls}"' if cls else ""
    if min_width:
        attrs += f' style="min-width: {min_width}px"'
    thead = "".join(f"<th>{cell}</th>" for cell in head)
    tbody = "\n".join("      <tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    box = f' data-start="{start}"' if start else ""
    return f'  <div class="scroll"{box}>\n    <table{attrs}>\n      <thead><tr>{thead}</tr></thead>\n      <tbody>\n{tbody}\n      </tbody>\n    </table>\n  </div>'


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


def on_boards(data):
    """The ids a phase's boards show, which already say each one's status."""
    shown = set()
    for section in data.get("section", []):
        if section.get("kind") != "board":
            continue
        if section.get("auto"):
            shown.update(i for i, item in ITEMS.items() if item["type"] in section.get("types", ["pr"]))
        else:
            shown.update(i for row in section.get("row", []) for cell in row.get("cells", []) for i in cell)
    return shown


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
    if kind not in PHASE_KINDS.get(key, SECTION_KINDS):
        kinds = PHASE_KINDS[key]
        named = kinds[0] if len(kinds) == 1 else f"{', '.join(kinds[:-1])} and {kinds[-1]}"
        problem(where, f"{PHASE_NAME[key]} holds only {named} sections: {ELSEWHERE[key]}")
        return ""
    if kind in BUILT and key != "retrospective":
        problem(where, f"a `{kind}` section is built for the Retrospective, from the other phases")
        return ""
    if kind != "prose":
        required(section, "title", where)
    if not isinstance(section.get("min_width", 0), int):
        problem(where, "`min_width` is a number of pixels")
        return ""
    parts, empty = [], False
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
        empty = not text_of(body).strip()
        if section.get("prefix"):
            body = prefixed(body, section["prefix"])
        parts.append(body if section.get("wide") else f'  <div class="prose">{body}</div>')
    elif kind == "table":
        head, rows = section.get("head", []), section.get("rows", [])
        if not rows or any(len(row) != len(head) for row in rows):
            problem(where, "a table has rows, each with as many cells as `head`")
        parts.append(table_html(head, rows, section.get("min_width")))
    elif kind == "repos":
        rows = []
        for index, repo in enumerate(section.get("repo", [])):
            at = f"{where} repo {index + 1}"
            required(repo, "name", at)
            use = repo.get("use")
            if use not in USES:
                problem(at, f"`use` is what the project does with it: {', '.join(USES)}")
                continue
            rows.append([f'<code>{esc(repo.get("name", ""))}</code> <span class="pill u-{use}">{USES[use]}</span>', repo.get("part", "")])
        empty = not rows
        parts.append(table_html(["Repository", "Its part"], rows, section.get("min_width"), "repos"))
    elif kind == "items":
        cards = [card(ITEMS[item["id"]]) for item in section.get("item", []) if item.get("id") in ITEMS]
        # Deferred's work goes on with what other phases set aside, each linked to its own card.
        work = next((s for s in data.get("section", []) if s.get("kind") == "items" and s.get("type") == "deferred"), None)
        if key == "deferred" and section is work:
            cards += [result_card(item) for item in ITEMS.values() if item["phase"] != key and item.get("status") in PARKED]
        empty = not cards
        # One button opens, or closes, every folded card in the section.
        if SCRIPTED and sum('<details class="fold">' in c for c in cards) > 1:
            parts.append('  <p class="fold-all"><button type="button" class="open-all">Open all</button></p>')
        parts.extend(cards)
    elif kind == "board":
        board = board_rows(section, where)
        if board is None:
            return ""
        columns, rows = board
        empty = not any(cell for _, row in rows for cell in row)
        head = [section.get("rows_title", "")] + [f"{esc(title)}<span>{esc(sub)}</span>" for title, sub in columns]
        cells = []
        for name, row in rows:
            rendered = [esc(name)]
            for cell in row:
                chips = "".join(chip(ITEMS[item_id]) for item_id in cell)
                rendered.append(f'<div class="chips">{chips}</div>' if chips else "")
            cells.append(rendered)
        # The board opens at its first column with work left, the finished ones behind it:
        # an item set aside, deferred or moved, is not work left.
        left = [index for index in range(len(columns)) if any(ITEMS[i].get("status") in UNFINISHED or not ITEMS[i].get("status") for _, row in rows for i in row[index])]
        start = left[0] + 1 if left and left[0] > 0 else None
        parts.append(table_html(head, cells, section.get("min_width", 160 * len(columns) + 140), "board", start))
    elif kind == "results":
        # An item the board shows is here only once it has a result, since the board says the rest,
        # or once it has moved, since a board's chip can't hold the link to its new page.
        shown = on_boards(data)
        for item_id in section.get("ids") or list(data.get("status", {})):
            if item_id not in ITEMS:
                problem(where, f"`ids` names {item_id}, which no item has")
            elif item_id not in shown or ITEMS[item_id].get("result") or ITEMS[item_id].get("status") == "moved":
                parts.append(result_card(ITEMS[item_id], on_board=item_id in shown and ITEMS[item_id].get("status") != "moved"))
        # Early on, nothing has a result yet, which the section says rather than vanishing.
        if not parts:
            parts.append('  <p class="note">Nothing yet.</p>')
        elif SCRIPTED and sum('<details class="fold">' in c for c in parts) > 1:
            parts.insert(0, '  <p class="fold-all"><button type="button" class="open-all">Open all</button></p>')
    elif kind == "figures":
        # With `auto`, the figures the data can count come first, then those written out.
        auto = COUNTED if section.get("auto") else []
        shown = auto + [(fig.get("value", ""), fig.get("label", "")) for fig in section.get("figure", [])]
        empty = not shown
        figures = "".join(f'<li><span class="v">{esc(value)}</span><span class="k">{label}</span></li>' for value, label in shown)
        parts.append(f'  <ul class="figures">{figures}</ul>')
        note = section.get("note", "")
        if auto and not note:
            which = "Counted" if len(auto) == len(shown) else f"The first {len(auto)} counted"
            note = f"{which} from the project's data on {TODAY.day} {TODAY:%B %Y}."
        if note:
            parts.append(f'  <p class="note">{note}</p>')
    elif kind == "defs":
        entries = section.get("def", [])
        empty = not entries
        if any(not all(is_pair(field) for field in entry.get("fields", [])) for entry in entries):
            problem(where, "a definition's `fields` are [label, text] pairs")
        if key == "reuse" or any("fields" in entry for entry in entries):
            # Reuse's pieces stand apart, and so does a definition with fields of its own, such
            # as something only using it revealed: each term a card, titled by it.
            parts += [card_html("", entry.get("term", ""), rows=[tuple(field) for field in entry["fields"]] if "fields" in entry else [("", entry.get("text", ""))]) for entry in entries]
        else:
            # Its terms' column grows to fit the widest, which may be a chip.
            terms = "".join(f'<dt>{entry.get("term", "")}</dt><dd>{entry.get("text", "")}</dd>' for entry in entries)
            parts.append(f'  <article class="item">\n    <dl class="terms">{terms}</dl>\n  </article>')
    elif kind in BUILT:
        parts.append(built_html(kind, section, where))
    if empty:
        problem(where, "it shows nothing but its title: give it content, or remove it")
    title = f'  <h3>{section["title"]}</h3>\n' if section.get("title") else ""
    return f'<section class="block" id="{section_id}">\n{title}' + "\n".join(parts) + "\n</section>"


# ------------------------------------------------------------------ the Retrospective's record
#
# What each built part lists, as data, then the HTML that shows it, so another renderer
# can take the same lists.


def phase_span(state):
    """When a phase ran, in words: its days, or that it runs still."""
    start, end = state["start"], state["end"]
    if start and end:
        return day(start) if start == end else f"{day(start)} – {day(end)}"
    return f"From {day(start)}" if start else (f"Until {day(end)}" if end else "")


def timeline(lines):
    """Each phase that ran, or was skipped, but the Retrospective and Deferred: its name,
    when, whether it started early or reopened, and the line written for it, or why
    it wasn't needed."""
    rows = []
    for key, name in PHASES:
        state = STATES[key]
        if key in ("retrospective", "deferred") or state["status"] == "to-come":
            continue
        marks = (["started early"] if state["early"] else []) + [f"reopened {day(on)}" for _, on in state["reopened"]]
        said = state["why"] if state["status"] == "not-needed" else lines.get(key, "")
        rows.append((name, "Not needed" if state["status"] == "not-needed" else phase_span(state), marks, said))
    return rows


def dropped():
    """Every road not taken: each item dropped, in the order the phases hold them."""
    return [item for item in ITEMS.values() if item.get("status") == "dropped"]


def risks():
    return [item for item in ITEMS.values() if item["type"] == "risk"]


def waiting():
    """What comes next, by who or what starts it: the owner's say, a trigger outside the
    project, or another project. Deferred work not yet picked up counts as much as an
    item another phase set aside."""
    groups = {"Until the owner says": [], "Waiting on a trigger": [], "Ready to start": [], "To another project": []}
    for item in ITEMS.values():
        status = item.get("status")
        if status == "deferred":
            groups["Until the owner says" if item.get("waits") == "owner" else "Waiting on a trigger"].append(item)
        elif status in ("to-move", "moved"):
            groups["To another project"].append(item)
        elif item["type"] == "deferred" and status in UNFINISHED:
            groups[{"open": "Until the owner says", "blocked": "Waiting on a trigger", "ready": "Ready to start"}[status]].append(item)
    return {name: items for name, items in groups.items() if items}


def decisions():
    """Every decision, by the section that holds it: what was chosen, and when."""
    batches = {}
    for item in ITEMS.values():
        if item["type"] == "decision":
            batches.setdefault(item["batch"], []).append(item)
    return batches


def cost():
    """What the data can count of what it took: the days, the PRs by repository, the
    settings changed by hand, and the decisions."""
    rows = []
    if SPAN:
        first, last = SPAN
        rows.append(("Time", f"{(last - first).days + 1} days, from {day(first)} to {day(last)}"))
    prs = [item for item in ITEMS.values() if item["type"] == "pr"]
    merged = [item for item in prs if item.get("status") == "done"]
    if prs:
        by_repo = {}
        for item in merged:
            prefix = item["id"].rsplit("-", 1)[0]
            by_repo[prefix] = by_repo.get(prefix, 0) + 1
        closed = sum(1 for item in prs if item.get("status") == "dropped")
        line = f"{len(merged)} merged" + (": " + ", ".join(f"{count} {prefix}" for prefix, count in by_repo.items()) if by_repo else "")
        rows.append(("PRs", line + (f"; {closed} closed unmerged" if closed else "")))
    settings = sum(1 for item in ITEMS.values() if item["type"] == "setting" and item.get("status") == "done")
    if settings:
        rows.append(("Settings", f"{settings} changed by hand"))
    taken = sum(1 for item in ITEMS.values() if item["type"] == "decision" and item.get("status") == "done")
    if taken:
        rows.append(("Decisions", f"{taken} taken"))
    return rows


def built_html(kind, section, where):
    """A part of the Retrospective's record, from the lists above. One with nothing to
    list says so, as a Results section does."""
    if kind == "timeline":
        rows = timeline(section.get("lines", {}))
        written = any(said for *_, said in rows)
        head = ["Phase", "When"] + (["What came of it"] if written else [])
        cells = []
        for name, span, marks, said in rows:
            when = span + "".join(f' <span class="waits">{mark}</span>' for mark in marks)
            cells.append([name, when] + ([said] if written else []))
        return table_html(head, cells, section.get("min_width"), "timeline") if cells else '  <p class="note">No phase has run yet.</p>'
    if kind == "roads":
        cards = [result_card(item) for item in dropped()]
        return "\n".join(cards) if cards else '  <p class="note">Nothing was dropped.</p>'
    if kind == "risks":
        cards = []
        for item in risks():
            rows = []
            if item["needs"]:
                rows.append((TYPES["risk"]["needs"], refs_ul(item["needs"])))
            if item.get("result"):
                rows.append(("Result", item["result"]))
            if item.get("status") == "dropped":
                rows.append(("Why", item.get("why", "")))
            tags = [status_pill(item)] if item.get("status") in ITEM_STATUS else []
            cards.append(card_html(esc(item["id"]), linked_name(item), tags, rows, fold=True))
        return "\n".join(cards) if cards else '  <p class="note">The register holds no risk.</p>'
    if kind == "next":
        groups = waiting()
        if not groups:
            return '  <p class="note">Nothing waits.</p>'
        terms = "".join(
            f'<dt>{name}</dt><dd><ul class="list">' + "".join(f"<li>[[{item['id']}]] {waits_tag(item)}</li>" for item in items) + "</ul></dd>"
            for name, items in groups.items()
        )
        return f'  <article class="item">\n    <dl class="terms">{terms}</dl>\n  </article>'
    if kind == "decisions":
        parts, batches = [], decisions()
        for batch, items in batches.items():
            # The option chosen has a column only in a batch whose decisions have options;
            # a decision not taken, or not yet, says so beside its name.
            with_options = any(item.get("chosen") for item in items)
            rows = []
            for item in items:
                name = f"[[{item['id']}]]" + (f" {status_pill(dict(item, on=None))}" if item.get("status") in ITEM_STATUS and item["status"] != "done" else "")
                options = dict(option for option in item.get("options", []) if is_pair(option))
                chosen = f'<span class="key">{esc(item["chosen"])}</span> {options[item["chosen"]]}' if item.get("chosen") in options else ""
                rows.append([name] + ([chosen] if with_options else []) + [day(item["on"]) if item.get("on") else ""])
            # A batch is titled only when there are several.
            heading = f"  <h4>{batch}</h4>\n" if len(batches) > 1 else ""
            parts.append(heading + table_html(["Decision"] + (["Chosen"] if with_options else []) + ["Day"], rows, section.get("min_width", 640 if with_options else None), "decisions"))
        return "\n".join(parts) if parts else '  <p class="note">No decision yet.</p>'
    # What it cost: what the data counts, then what it can't, written.
    rows = [[label, text] for label, text in cost()] + [row for row in section.get("rows", []) if is_pair(row)]
    if any(not is_pair(row) for row in section.get("rows", [])):
        problem(where, "each of `rows` is a [label, text] pair")
    terms = "".join(f"<dt>{label}</dt><dd>{text}</dd>" for label, text in rows)
    return f'  <article class="item">\n    <dl class="terms">{terms}</dl>\n  </article>' if rows else '  <p class="note">Nothing to count yet.</p>'


def amendments_html(ids):
    """The items amended into a phase, grouped by the day and the reason they came in,
    oldest first: each group its day as a chip, its reason, then its items."""
    groups = {}
    for item_id in ids:
        amended = ITEMS[item_id]["amended"]
        groups.setdefault((amended["on"], amended["why"]), []).append(item_id)
    # A stable sort keeps the phase's order among the groups of one day; an undated one goes last.
    order = sorted(groups, key=lambda group: group[0] or datetime.date.max)
    rows = "".join(f'<li>{day_pill(on) + " " if on else ""}{why}:{refs_ul(groups[(on, why)])}</li>' for on, why in order)
    return f'<ul class="amendments">{rows}</ul>'


def closing(key, data):
    """What ends a phase, after its sections: its approval, or, for a done phase without
    one that has taken amendments, its end; then the items amended into it since, by day
    and reason. Its title and anchor, for the phase's contents, and its section."""
    amended = [item["id"] for item in ITEMS.values() if item["phase"] == key and item["amended"]]
    state = STATES.get(key, {})
    if data.get("approved"):
        title, says, tags = "Approval", "Approved.", [day_pill(data["approved"])]
    elif amended and state.get("status") == "done":
        title, says, tags = "Amendments", "Done.", [day_pill(state["end"])] if state.get("end") else []
    elif amended:
        title, says, tags = "Approval", "Not approved yet.", []
    else:
        return None
    anchor = f"{key}-{title.lower()}"
    if amended:
        body = card_html("", says, tags, [("Amended since", amendments_html(amended))], says=True)
    else:
        body = card_html("", f"{says} Nothing has been amended since.", tags, says=True)
    return title, anchor, f'<section class="block" id="{anchor}">\n  <h3>{title}</h3>\n{body}\n</section>'


def render_phase(key, data, data_dir, head=True):
    """A phase's view: its name, for screen readers only, since its tab shows the name
    and the state, unless it stands alone; then, for some phases, a list of its
    sections; then its sections, and what closes it: its approval, or its amendments.
    Nothing, for a phase whose file shows neither, such as one holding only statuses."""
    parts = [f'<h2 class="vh">{PHASE_NAME[key]}</h2>'] if head else []
    rendered = [(section, render_section(section, key, data, data_dir)) for section in data.get("section", [])]
    shown = [section for section, html in rendered if html]
    ending = closing(key, data)
    if not shown and not ending:
        return ""
    if key in CONTENTS and len(shown) > 1:
        links = "".join(f'<li><a href="#{section["id"]}">{section.get("title") or section["id"]}</a></li>' for section in shown)
        if ending:
            links += f'<li><a href="#{ending[1]}">{ending[0]}</a></li>'
        # A contents line, as the guides open with.
        parts.append(f'<nav class="contents" id="{key}-contents" aria-label="In this view"><ol>{links}</ol></nav>')
    parts += [html for _, html in rendered]
    if ending:
        parts.append(ending[2])
    return expand_refs("\n".join(part for part in parts if part), f"{key}.toml")


# ------------------------------------------------------------------ the calendar


def dated(project, phases):
    """Everything with a date: (date, class, html, label, word, item id), in no order
    yet. The word is what happened to an item, which the calendar counts and the
    agenda groups by; an event or a phase's date has neither, and shows on its own."""
    found = []
    for event in project.get("event", []):
        if event.get("date"):
            # A run that starts on its own, such as a scheduled workflow, is marked Automated wherever it is listed.
            mark = ' <span class="automated">Automated</span>' if event.get("automated") is True else ""
            found.append((event["date"], "event", event.get("title", "") + mark, event.get("short") or text_of(event.get("title", "")), None, None))
    for item_id, item in ITEMS.items():
        if item.get("on") and item.get("status") in ITEM_STATUS:
            found.append((item["on"], f"s-{item['status']}", f"[[{item_id}]] {label_of(item)}", item_id, label_of(item).lower(), item_id))
        if item["amended"] and item["amended"]["on"]:
            found.append((item["amended"]["on"], "amended", f"[[{item_id}]] amended into the {PHASE_NAME[item['phase']]}", f"{item_id} amended", "amended", item_id))
    # A phase's dates, each said once: one that starts and ends the same day is one
    # mark, and an end on the day of its approval is the approval. An early start says
    # why, and a phase that reopened keeps the day it ended, and the day it reopened.
    for key, state in project["status"].items():
        name, start, end = PHASE_NAME[key], state["start"], state["end"]
        approved = phases.get(key, {}).get("approved")
        early = f" early: {state['early']}" if state["early"] else ""
        for ended, on in state["reopened"]:
            found.append((ended, "phase", f"{name} ends", f"{name} ends", None, None))
            found.append((on, "phase", f"{name} reopens", f"{name} reopens", None, None))
        if start and start == end:
            found.append((start, "phase", f"{name}, one day{',' + early if early else ''}", f"{name}, one day", None, None))
            continue
        if start:
            found.append((start, "phase", f"{name} starts{early}", f"{name} starts", None, None))
        if end and end != approved:
            found.append((end, "phase", f"{name} ends", f"{name} ends", None, None))
    for key, data in phases.items():
        if data.get("approved"):
            found.append((data["approved"], "phase", f"{PHASE_NAME[key]} approved", f"{PHASE_NAME[key]} approved", None, None))
    return found


def day_mark(cls, label, count=None):
    """One mark in a calendar day: an event or a phase's date by name, or a count of
    items with what happened to them, such as 18 merged. On a phone a mark is a box,
    and a count's box shows its number; the word stays for screen readers."""
    if count is None:
        return f'<li class="m-{cls}">{esc(label)}</li>'
    return f'<li class="m-{cls} count"><b>{count}</b><span class="word"> {esc(label)}</span></li>'


def day_marks(entries):
    """A day's marks in the calendar: its events and phase dates, then its items
    counted by what happened to them. The day's link opens the Agenda, which lists
    each item."""
    marks, counts = [], {}
    for cls, text, label, word in entries:
        if word is None:
            marks.append(day_mark(cls, label))
        else:
            counts[(cls, word)] = counts.get((cls, word), 0) + 1
    return "".join(marks + [day_mark(cls, word, count) for (cls, word), count in counts.items()])


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
            marks = day_marks(by_day.get(date, []))
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


def agenda_day(entries):
    """A day in the agenda: its events and phase dates, then each thing that
    happened to its items, such as Merged, over a list of the items."""
    lines, groups = [], {}
    for cls, text, ref in entries:
        if ref is None:
            lines.append(f'<li class="m-{cls}">{text}</li>')
            continue
        item = ITEMS[ref]
        what = f"Amended into the {PHASE_NAME[item['phase']]}" if cls == "amended" else label_of(item)
        groups.setdefault((cls, what), []).append(f"[[{ref}]]")
    lines += [f'<li class="m-{cls}"><span class="what">{what}:</span>{list_html(refs)}</li>' for (cls, what), refs in groups.items()]
    return "".join(lines)


def parked_line(count, linked):
    """Under the owner's column, how many items are deferred until the owner says, linked
    to Deferred, which lists them."""
    if not count:
        return ""
    words = f"Deferred until you say: {count}"
    return f'<p class="more"><a href="#deferred">{words}</a></p>' if linked else f'<p class="more">{words}</p>'


def calendar_view(project, phases):
    """The header's calendar, every month the project spans with today's shown; who
    holds the ball, which the header shows under it: the user, with what they have
    deferred, the agent, or a date coming up; and the agenda: every date coming up,
    the notes for the next session, and what happened."""
    found = dated(project, phases)
    by_day = {}
    for date, cls, text, label, word, ref in found:
        by_day.setdefault(date, []).append((cls, text, label, word))
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
    # What waits on the owner, but not now: counted, not listed, since it isn't to do yet.
    parked = sum(1 for item in ITEMS.values() if item.get("status") == "deferred" and item.get("waits") == "owner")

    def column(title, rows, empty, more=""):
        body = "".join(rows) if rows else f'<li class="none">{empty}</li>'
        return f'<div class="col"><h3>{title}</h3><ul>{body}</ul>{more}</div>'

    owner_rows = [f'<li><span class="pill ask">{esc(ask_of(ITEMS[i]))}</span> [[{i}]]</li>' for i in owner]
    agent_rows = [f"<li>[[{i}]]</li>" for i in agent]
    # The next three dates, each a link to its day in the agenda, which has them all.
    date_rows = [f'<li class="dated"><a class="when" href="#on-{date.isoformat()}"><time>{weekday(date)}</time></a> <span>{text}</span></li>' for date, cls, text, label, word, ref in ahead[:3]]
    more = f'<p class="more"><a href="#coming-up">{len(ahead) - 3} more in the agenda</a></p>' if len(ahead) > 3 else ""
    ball = (
        '<section class="hold" id="ball" aria-labelledby="ball-title"><h2 id="ball-title">Who holds the ball</h2><div class="ball">'
        + column("The owner", owner_rows, "Nothing to do.", parked_line(parked, "deferred" in phases))
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
    for date, cls, text, label, word, ref in found:
        upcoming = date > TODAY or (date == TODAY and cls == "event")
        (coming if upcoming else happened).setdefault(date, []).append((cls, text, ref))
    anchors = set()

    def days(groups, order):
        rows = []
        for date in order:
            when = "ahead" if date > TODAY else "today" if date == TODAY else "past"
            # Today can be in both lists; the calendar's link goes to the first.
            anchor = f"on-{date.isoformat()}"
            attr = "" if anchor in anchors else f' id="{anchor}"'
            anchors.add(anchor)
            entries = agenda_day(groups[date])
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


def opening_phase(statuses, shown):
    """The phase in progress, or else the next to come, or else the first: of those
    with something to show."""
    for wanted in ("now", "to-come"):
        for key in shown:
            if statuses[key]["status"] == wanted:
                return key
    return next(iter(shown))


# ------------------------------------------------------------------ the guides


def statuses_table():
    """Each type of item in the words its statuses take, and what the user does while one waits.
    Ready reads the same for every type, and only a risk happens, so neither has a column."""
    order = ("open", "blocked", "done", "dropped")
    rows = []
    for key, entry in TYPES.items():
        name, example = TYPE_NAMES[key]
        words = [f'<span class="st st-{status}">{entry["labels"].get(status, ITEM_STATUS[status])}</span>' for status in order]
        rows.append([f'{name} <span class="letters">{example}</span>'] + words + [entry["ask"]])
    return table_html(["Type", "Waits on the owner", "Blocked", "Done", "Dropped", "The owner's part"], rows, 700, "statuses")


def kinds_list():
    rows = "".join(f'<dt><span class="pill k-{key}">{name}</span></dt><dd>{KIND_MEANING[key]}</dd>' for key, name in KINDS.items())
    return f'<dl class="defs kinds">{rows}</dl>'


def uses_list():
    rows = "".join(f'<dt><span class="pill u-{key}">{name}</span></dt><dd>{USE_MEANING[key]}</dd>' for key, name in USES.items())
    return f'<dl class="defs kinds">{rows}</dl>'


def sample_chips():
    """A chip in each status, drawn as the board draws them, but not links: they are examples."""
    samples = [
        dict(id="EX-1", short="Liveness probe", status="done", on=TODAY, kind="minor"),
        dict(id="EX-2", short="Readiness probe", status="open", on=TODAY, kind="minor"),
        dict(id="EX-3", short="Ten seconds in production", status="ready", kind="patch"),
        dict(id="EX-4", short="The probes in the README", status="blocked", waits="the freeze to end", kind="patch"),
        dict(id="EX-5", short="A second exporter", status="dropped", why="EX-2 covers it", kind="minor"),
        dict(id="EX-6", short="Probes on the workers", status="deferred", waits="owner", kind="minor"),
    ]
    chips = [chip(dict(sample, type="pr", needs=[])) for sample in samples]
    chips = [re.sub(r'^<a class="([^"]*)" href="#[^"]*">(.*)</a>$', r'<span class="\1">\2</span>', html, flags=re.S) for html in chips]
    return f'<div class="chips samples">{"".join(chips)}</div>'


def guides_view(project):
    """The guides: how to use the page, the same on every project, then the project's
    glossary. Its title is on the sheet that holds it."""
    guide = (HERE / "guide.html").read_text(encoding="utf-8")
    for mark, generated in (("<!--statuses-->", statuses_table()), ("<!--kinds-->", kinds_list()), ("<!--uses-->", uses_list()), ("<!--chips-->", sample_chips())):
        guide = guide.replace(mark, generated)
    parts = re.findall(r'<section class="block" id="([^"]+)">\s*<h3>(.*?)</h3>', guide)
    entries = project.get("glossary", [])
    terms = ""
    if entries:
        terms = f'<section class="block" id="glossary">\n  <h3>Glossary</h3>\n  {glossary_groups(entries, 4)}\n</section>'
        parts.append(("glossary", "Glossary"))
    contents = "".join(f'<li><a href="#{anchor}">{title}</a></li>' for anchor, title in parts)
    return "\n".join([
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
    """What changed since the data was last published, in words, for the user: each
    phase's changes, then project.toml's. An item that is gone is warned about,
    since an item is never deleted, but dropped, with why."""
    old, new = raw(published, "the published"), raw(data_dir, "the new")
    (old_items, old_sections), (new_items, new_sections) = snapshot(old), snapshot(new)
    found = {key: [] for key, _ in PHASES}

    def note(key, text):
        found[key].append(text)

    for item_id in dict.fromkeys(list(new_items) + list(old_items)):
        before, after = old_items.get(item_id), new_items.get(item_id)
        if after is None:
            note(before["phase"], f"{item_id} removed")
            warn(f"{before['phase']}.toml", f"{item_id} is gone since the published data: an item is never deleted, but given the status `dropped`, with `why`")
            continue
        if before is None:
            note(after["phase"], f"{item_id} added")
        elif before["written"] != after["written"]:
            note(after["phase"], f"{item_id}: {', '.join(edits(before['written'], after['written']))} edited")
        was = before["state"] if before else {}
        if was == after["state"]:
            continue
        # A state that is gone was kept where it was; one that is new or changed, where it is.
        key = after["kept"] or before["kept"]
        if was.get("status") != after["state"].get("status"):
            note(key, f"{item_id} {said(after, was)} → {said(after, after['state'])}")
        else:
            note(key, f"{item_id}: {', '.join(edits(was, after['state']))} edited")

    for (key, section_id), after in new_sections.items():
        before = old_sections.get((key, section_id))
        name = text_of(section_names(new.get(key, {}).get("section", [])).get(section_id, section_id))
        if before is None:
            note(key, f"{name} added")
        elif {k: v for k, v in before.items() if k != "item"} != {k: v for k, v in after.items() if k != "item"}:
            note(key, f"{name} edited")
    for (key, section_id), before in old_sections.items():
        if (key, section_id) not in new_sections:
            note(key, f"{text_of(section_names(old.get(key, {}).get('section', [])).get(section_id, section_id))} removed")

    for key, _ in PHASES:
        before, after = old.get(key, {}), new.get(key, {})
        for field in dict.fromkeys(list(after) + list(before)):
            if field not in ("section", "status") and before.get(field) != after.get(field):
                note(key, f"`{field}` edited")

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
    if not project and not any(found.values()):
        print("Since the published data: nothing has changed.")
        return
    print("Since the published data:")
    for key, name in PHASES:
        if found[key]:
            print(f"  {name}: {'; '.join(found[key])}.")
    if project:
        print(f"  project.toml: {'; '.join(project)}.")


# ------------------------------------------------------------------ checking


class Check(HTMLParser):
    """Tag nesting, links inside links, and the ids and in-page links an HTML fragment holds."""

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
        if tag == "a" and any(opened == "a" for opened, _ in self.stack):
            problem(self.where, f"line {self.getpos()[0]}: a link inside a link, which a browser splits in two; a [[ref]] is a link already")
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
    """For each phase, how many of the statuses it keeps are done, of those not Dropped or
    set aside; a risk that happened is done with, since a question or a blocker took it
    over, and so is an item moved to another project."""
    counts = {}
    for item in ITEMS.values():
        key, status = item.get("status_from"), item.get("status")
        if key and status in ITEM_STATUS and status != "dropped" and status not in PARKED:
            done, total = counts.get(key, (0, 0))
            counts[key] = (done + (status in ("done", "happened", "moved")), total + 1)
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
    tabs, leaves = [], []
    waiting = sum(1 for item in ITEMS.values() if item.get("status") in PARKED)
    for number, (key, name) in enumerate(PHASES, start=1):
        status = project["status"][key]["status"]
        state = PHASE_STATUS[status]
        group = leaves if key in LEAVES else tabs
        inner = f'<span class="name">{name}</span>' if key in LEAVES else f'<span class="n">{number}</span><span class="name">{name}</span>'
        # A phase with nothing to show, not needed or not written yet, has a tab that doesn't open.
        if key not in sections:
            group.append(f'<li><span class="off t-{status}">{inner}<span class="state">{state}</span></span></li>')
            continue
        current = ' aria-current="true"' if key == opening else ""
        # Deferred says how many items wait; a phase in progress, how far it is; a done
        # phase that has taken amendments reads Amended.
        if status == "done" and any(item["phase"] == key and item["amended"] for item in ITEMS.values()):
            status, state = "amended", "Amended"
        if key == "deferred":
            state = f"{waiting} waiting" if waiting else "Nothing waiting"
        elif status == "now" and key in counts:
            done, total = counts[key]
            state += f' <span class="count" title="{done} of {total} done, not counting dropped or set-aside items">{done}/{total}</span>'
        group.append(f'<li><a href="#{key}" data-phase="{key}" class="t-{status}"{current}>{inner}<span class="state">{state}</span></a></li>')
    shells, files = [], {}
    for key, text in sections.items():
        hidden = "" if key == opening else " hidden"
        if inline or key == opening:
            shells.append(f'<section class="phase" id="{key}" data-phase="{key}"{hidden}>\n{text}\n</section>')
        else:
            files[key] = text + "\n"
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
    <p class="eyebrow">Project page</p>
    <nav class="views" aria-label="Views">{views}</nav>
  </div>
  <h1>{esc(title)}</h1>
  <p class="lede">{project.get("summary", "")}</p>
  <div class="now">
    <div class="months" role="group" aria-label="Calendar">{months_html}</div>
    <p class="glance">{read} as of {read_at.day} {read_at:%b %Y}, {read_at:%H:%M} UTC.</p>
  </div>
  {ball_html}
  <div class="hold groups"><div class="group"><h2 id="phases-title">Phases</h2><nav class="phases" aria-labelledby="phases-title"><ol>{"".join(tabs)}</ol></nav></div><div class="group"><h2 id="leaves-title">What it leaves</h2><nav class="phases leaves" aria-labelledby="leaves-title"><ol>{"".join(leaves)}</ol></nav></div></div>
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
        SPAN[:] = [min(dates), max(dates)]
        figures.append(((max(dates) - min(dates)).days + 1, "day, start to finish", "days, start to finish"))
    return [(str(value), one if value == 1 else many) for value, one, many in figures if value]


def retrospective_page(project, phases, data_dir):
    """The Retrospective alone, as a page to share: no tabs, no calendar and no
    script, and the items it doesn't hold named as text rather than linked."""
    global LINKABLE, SCRIPTED
    title = f'{project.get("repo", "")}-{project.get("objective", "")}-retrospective'
    data = phases.get("retrospective")
    if not data:
        problem("retrospective.toml", "the Retrospective has no data yet")
        return title, ""
    LINKABLE = {item_id for item_id, item in ITEMS.items() if item["phase"] == "retrospective"}
    # Without the page's script, folded cards still open on a click, one at a time.
    SCRIPTED = False
    body = render_phase("retrospective", data, data_dir, head=False)
    read_at = project["read_at"]
    text = f"""<meta charset="utf-8">
<title>{esc(title)}</title>
{FONTS}
<style>
{stylesheet(project, data_dir)}
</style>
<div class="wrap">
<header class="top">
  <p class="eyebrow">Retrospective</p>
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
    phases = read_phases(data_dir, project["status"])
    collect_items(phases)
    link_items()
    if not problems:
        check_states(project, phases)
        check_wording(project, phases)
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
    # Only a phase with something to show has a view; the others' tabs don't open.
    rendered = ((key, render_phase(key, phases[key], data_dir)) for key, _ in PHASES if key in phases)
    sections = {key: text for key, text in rendered if text}
    if not sections:
        problem("project.toml", "no phase has anything to show yet: a project starts with its Brief, in brief.toml")
        failed()
        return 1
    agenda_html, months_html, ball_html = calendar_view(project, phases)
    opening = opening_phase(project["status"], sections)
    guides_html = expand_refs(guides_view(project), "project.toml [[glossary]]")
    title, files, shell = page(project, sections, opening, inline, data_dir, agenda_html, months_html, ball_html, guides_html)
    shell = expand_refs(shell, "project.toml")
    fragments = [("the page", shell)] + [(f"phases/{key}.html", text) for key, text in files.items()]
    check(fragments)
    if failed():
        return 1
    # Which view holds each id, so a link into a phase not loaded yet opens it.
    phase_of = {}
    for key, text in list(sections.items()) + [("agenda", agenda_html), ("guides", guides_html)]:
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
