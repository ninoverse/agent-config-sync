#!/usr/bin/env python3
"""Builds a project page from its TOML data, and checks it.

Usage: python3 render.py <data-dir> <out-dir> [--inline]

<data-dir> holds project.toml and a <phase>.toml for each phase with content.
<out-dir> gets index.html, the page to publish, and phases/<phase>.html for
every other phase with content, which the page loads when that phase is
picked. --inline puts every phase in index.html instead, for a preview or a
small project.

Exits 0 once the page is written; 1 when the data or the page has a problem,
writing nothing and printing one line per problem on stderr; 2 on a usage
error. Needs Python 3.11 or later, and nothing outside its standard library.
"""

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
    ("research", "Research"),
    ("analysis", "Analysis"),
    ("plan", "Plan"),
    ("build", "Build"),
    ("templating", "Templating"),
    ("retrospective", "Retrospective"),
    ("later", "For later"),
]
PHASE_NAME = dict(PHASES)
PHASE_STATUS = {"done": "Done", "now": "Now", "to-come": "To come", "not-needed": "Not needed"}
ITEM_STATUS = {"done": "Done", "open": "Open", "ready": "Ready", "blocked": "Blocked", "dropped": "Dropped"}
KINDS = {"major": "Major", "minor": "Minor", "patch": "Patch", "you": "You", "together": "Together"}
SECTION_KINDS = ("prose", "table", "items", "board", "results", "log", "figures", "defs")
SOURCES = {"coined": "Coined for this project", "borrowed": "Borrowed from elsewhere"}

KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ITEM_ID = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*")
# Only an anchor made of these reaches location.hash from an artifact's link.
ANCHOR = re.compile(r"[A-Za-z0-9._~-]+")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Oxanium:wght@500;600;700'
    '&amp;family=Quicksand:wght@400;500;600;700&amp;display=swap" rel="stylesheet">'
)

problems = []


def problem(where, text):
    problems.append(f"{where}: {text}")


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


# ------------------------------------------------------------------ the data


def read_project(data_dir):
    path = data_dir / "project.toml"
    if not path.is_file():
        print(f"{path}: no such file. A project's data starts with project.toml.", file=sys.stderr)
        sys.exit(1)
    project = load(path)
    if project is None:
        print(problems[0], file=sys.stderr)
        sys.exit(1)
    for key in ("repo", "objective", "summary", "read_at"):
        required(project, key, "project.toml")
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
        status = entry.get("status", "to-come")
        if status not in PHASE_STATUS:
            problem(f"project.toml [phases.{key}]", f"status `{status}` is not one of {', '.join(PHASE_STATUS)}")
            status = "to-come"
        if status == "not-needed" and not entry.get("why"):
            problem(f"project.toml [phases.{key}]", "a phase that is not needed says why, in `why`")
        project["status"][key] = (status, entry.get("why", ""))
    for index, entry in enumerate(project.get("glossary", [])):
        where = f"project.toml [[glossary]] {index + 1}"
        required(entry, "term", where)
        required(entry, "text", where)
        if entry.get("source", "coined") not in SOURCES:
            problem(where, f"`source` is one of {', '.join(SOURCES)}")
    return project


def read_phases(data_dir):
    data = {}
    for key, _ in PHASES:
        path = data_dir / f"{key}.toml"
        if path.is_file():
            loaded = load(path)
            if loaded is not None:
                data[key] = loaded
    return data


def collect_items(phases):
    """Every item, by id, in phase order, with the status it ends up with."""
    items, anchors = {}, set()
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
                if item.get("kind") and item["kind"] not in KINDS:
                    problem(where, f"`kind` is one of {', '.join(KINDS)}")
                if not all(is_pair(field) for field in item.get("fields", [])):
                    problem(where, "each of `fields` is a [label, text] pair")
                items[item_id] = dict(item, phase=key, status_from=key if "status" in item else None)
    for key, data in phases.items():
        for item_id, entry in data.get("status", {}).items():
            where = f"{key}.toml [status.{item_id}]"
            if item_id not in items:
                problem(where, "no item has this id")
                continue
            if items[item_id]["status_from"]:
                problem(where, f"{item_id}'s status is set twice, here and in {items[item_id]['status_from']}.toml")
                continue
            check_status(entry, where)
            for field in ("status", "waits", "why", "result"):
                if field in entry:
                    items[item_id][field] = entry[field]
            items[item_id]["status_from"] = key
    return items


def is_pair(value):
    return isinstance(value, list) and len(value) == 2 and all(isinstance(part, str) for part in value)


def check_status(entry, where):
    status = entry.get("status")
    if status is None:
        return
    if status not in ITEM_STATUS:
        problem(where, f"status `{status}` is not one of {', '.join(ITEM_STATUS)}")
    elif status == "blocked" and not entry.get("waits"):
        problem(where, "a blocked item says what it waits on, in `waits`")
    elif status == "dropped" and not entry.get("why"):
        problem(where, "a dropped item says why, in `why`")


# ------------------------------------------------------------------ rendering


def badge(status):
    return f'<span class="st st-{status}">{ITEM_STATUS[status]}</span>'


def state_line(item):
    status = item.get("status")
    if not status or status not in ITEM_STATUS:
        return ""
    line = badge(status)
    if status == "blocked":
        line += f' <span class="waits">waits on {item.get("waits", "")}</span>'
    if status == "dropped":
        line += f' <span class="waits">{item.get("why", "")}</span>'
    return line


def short_of(item):
    return item.get("short") or text_of(item.get("title", ""))


def card(item):
    head = [f'<span class="n">{esc(item["id"])}</span>', f'<h4>{item.get("title", "")}</h4>']
    if item.get("kind") in KINDS:
        head.append(f'<span class="pill k-{item["kind"]}">{KINDS[item["kind"]]}</span>')
    # A status set from another phase shows there: the card keeps the record as written.
    if item.get("status_from") == item["phase"]:
        head.append(state_line(item))
    rows = "".join(f"<dt>{field[0]}</dt><dd>{field[1]}</dd>" for field in item.get("fields", []) if is_pair(field))
    body = f"\n    <dl>{rows}</dl>" if rows else ""
    return f'  <article class="item" id="{anchor_of(item["id"])}">\n    <div class="item-head">{"".join(head)}</div>{body}\n  </article>'


def chip(item):
    classes = ["chip"]
    if item.get("kind") in KINDS:
        classes.append(f'k-{item["kind"]}')
    if item.get("status") in ITEM_STATUS:
        classes.append(f's-{item["status"]}')
    line = state_line(item)
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


def render_section(section, key, data, items, data_dir):
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
        parts.extend(card(items[item["id"]]) for item in section.get("item", []) if item.get("id") in items)
    elif kind == "board":
        columns = section.get("columns", [])
        if not all(is_pair(col) for col in columns):
            problem(where, "each of `columns` is a [title, subtitle] pair")
            return ""
        head = [section.get("rows_title", "")] + [f"{esc(title)}<span>{esc(sub)}</span>" for title, sub in columns]
        rows = []
        for row in section.get("row", []):
            cells = row.get("cells", [])
            if len(cells) != len(columns):
                problem(where, f"row {row.get('name', '?')} has {len(cells)} cells for {len(columns)} columns")
            rendered = [esc(row.get("name", ""))]
            for cell in cells:
                for item_id in cell:
                    if item_id not in items:
                        problem(where, f"the board names {item_id}, which no item has")
                chips = "".join(chip(items[item_id]) for item_id in cell if item_id in items)
                rendered.append(f'<div class="chips">{chips}</div>' if chips else "")
            rows.append(rendered)
        parts.append(table_html(head, rows, section.get("min_width", 160 * len(columns) + 140), "board"))
    elif kind == "results":
        ids = section.get("ids") or list(data.get("status", {}))
        rows = []
        for item_id in ids:
            if item_id not in items:
                problem(where, f"`ids` names {item_id}, which no item has")
                continue
            item = items[item_id]
            link = f'<a class="ref" href="#{anchor_of(item_id)}"><b>{esc(item_id)}</b> {short_of(item)}</a>'
            rows.append([link, state_line(item), item.get("result", "")])
        parts.append(table_html(["Item", "Status", "Result"], rows, section.get("min_width", 760), "results"))
    elif kind == "log":
        entries = "".join(
            f'<li><span class="who">{esc(entry.get("date", ""))}</span><span>{entry.get("text", "")}</span></li>'
            for entry in section.get("entry", [])
        )
        parts.append(f'  <ul class="plain log">{entries}</ul>')
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


def changelog(key, entries, targets):
    if not entries:
        return ""
    rows = []
    for index, entry in enumerate(entries):
        where = f"{key}.toml [[changelog]] {index + 1}"
        required(entry, "date", where)
        required(entry, "text", where)
        links = []
        for target in entry.get("changed", []):
            if target not in targets:
                problem(where, f"`changed` names {target}, which is no section or item in this phase")
                continue
            links.append(f'<a href="#{target}">{targets[target]}</a>')
        changed = f' <span class="changed">Changed: {" · ".join(links)}</span>' if links else ""
        rows.append(f'<li><time>{esc(entry.get("date", ""))}</time><div>{entry.get("text", "")}{changed}</div></li>')
    return f'<footer class="changelog" id="{key}-changelog">\n  <h3>Changelog</h3>\n  <ol>{"".join(rows)}</ol>\n</footer>'


def render_phase(key, status, why, data, items, data_dir):
    head = f'<div class="phase-head"><h2>{PHASE_NAME[key]}</h2><span class="ph ph-{status}">{PHASE_STATUS[status]}</span></div>'
    parts = [head]
    if status == "not-needed":
        parts.append(f'<p class="why">{why}</p>')
    elif data is None:
        parts.append('<p class="why">Nothing here yet.</p>' if status == "to-come" else "")
    if data:
        if data.get("intro"):
            parts.append(f'<p class="lede">{data["intro"]}</p>')
        targets = {}
        for section in data.get("section", []):
            parts.append(render_section(section, key, data, items, data_dir))
            if section.get("id"):
                targets[section["id"]] = section.get("title") or section["id"]
            for item in section.get("item", []) if section.get("kind") == "items" else []:
                if item.get("id"):
                    targets[anchor_of(item["id"])] = esc(item["id"])
        parts.append(changelog(key, data.get("changelog", []), targets))
    return "\n".join(part for part in parts if part)


def waiting(items):
    rows = [
        f'<li><span class="pill ask">{esc(item.get("ask", "Open"))}</span><span><b>{esc(item_id)}</b> {short_of(item)}</span><a href="#{anchor_of(item_id)}">{PHASE_NAME[item["phase"]]}</a></li>'
        for item_id, item in items.items()
        if item.get("status") == "open"
    ]
    body = f'<ul class="inbox">{"".join(rows)}</ul>' if rows else '<p class="nothing">Nothing waits on you.</p>'
    return f'<section class="waiting" aria-labelledby="waiting">\n  <h2 id="waiting">Waiting on you</h2>\n  {body}\n</section>'


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
            if statuses[key][0] == wanted:
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


def page(project, sections, opening, inline, data_dir, waiting_html):
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
        status = project["status"][key][0]
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
  <p class="readat">State read on {esc(project.get("read_at", ""))}.</p>
</header>
{waiting_html}
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
    items = collect_items(phases)
    sections = {}
    for key, _ in PHASES:
        status, why = project["status"][key]
        sections[key] = (render_phase(key, status, why, phases.get(key), items, data_dir), key in phases)
    opening = opening_phase(project["status"])
    title, files, shell = page(project, sections, opening, inline, data_dir, waiting(items))
    fragments = [("the page", shell)] + [(f"phases/{key}.html", text) for key, text in files.items()]
    check(fragments)
    if problems:
        for line in problems:
            print(line, file=sys.stderr)
        print(f"{len(problems)} problem{'s' if len(problems) != 1 else ''}; nothing written.", file=sys.stderr)
        return 1
    # Which phase holds each id, so a link into a phase not loaded yet opens it.
    phase_of = {}
    for key, _ in PHASES:
        holder = Check(key)
        holder.feed(sections[key][0])
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
    print(f"{title}: index.html, {len(out.encode()) // 1024} KB, opening on {PHASE_NAME[opening]}; loaded when picked: {loaded}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
