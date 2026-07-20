"""Repository-owned operator-help registry and deterministic Markdown rendering."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

HELP_WINDOW_NAME = "rfi-operator-help"
GUIDE_PATH = Path(__file__).resolve().parents[3] / "docs" / "operator-guide.md"


@dataclass(frozen=True)
class HelpTopic:
    """One stable topic identity independent of its display heading."""

    topic_id: str
    title: str


HELP_TOPICS = (
    HelpTopic("getting-started", "Getting started"),
    HelpTopic("repository", "Repository and state model"),
    HelpTopic("concepts", "Concept Catalog"),
    HelpTopic("firms", "Target Firms"),
    HelpTopic("source-profiles", "Firm Source Profiles"),
    HelpTopic("source-readiness", "Source readiness and run eligibility"),
    HelpTopic("external-sources", "External Sources"),
    HelpTopic("acquisition", "Pull Sources and acquisition workflow"),
    HelpTopic("artifacts", "Artifacts and retained evidence"),
    HelpTopic("streams", "Artifact Streams"),
    HelpTopic("stream-upstream-definitions", "Preparing upstream streams"),
    HelpTopic("stream-validation-preview", "Stream validation and preview"),
    HelpTopic("revisions-lineage", "Revisions, immutability, and lineage"),
    HelpTopic("yaml", "Stream YAML import and export"),
    HelpTopic("repository-protection", "Verify, backup, and restore"),
    HelpTopic("troubleshooting", "Troubleshooting and recovery"),
    HelpTopic("cli-reference", "CLI equivalents"),
    HelpTopic("glossary", "Glossary"),
)
TOPICS_BY_ID = {topic.topic_id: topic for topic in HELP_TOPICS}

# This is the completeness contract for all major administration pages.
PAGE_HELP_TOPICS = {
    "/concepts": "concepts",
    "/firms": "firms",
    "/source-profiles": "source-profiles",
    "/external-sources": "external-sources",
    "/pull-sources": "acquisition",
    "/streams": "streams",
    "/artifacts": "artifacts",
}

TOPIC_MARKER = re.compile(r"^<!-- help-topic: ([a-z][a-z0-9-]*) -->$")
LINK = re.compile(r"\[([^]]+)]\(([^)]+)\)")
INLINE_CODE = re.compile(r"`([^`]+)`")


def topic_url(topic_id: str) -> str:
    """Return the stable local deep link for one registered topic."""
    if topic_id not in TOPICS_BY_ID:
        raise ValueError(f"unknown help topic: {topic_id}")
    return f"/help/{topic_id}#{topic_id}"


def guide_source() -> str:
    """Read the canonical repository documentation source."""
    return GUIDE_PATH.read_text(encoding="utf-8")


def guide_topic_ids(source: str | None = None) -> tuple[str, ...]:
    """Return explicit stable topic markers in canonical order."""
    content = guide_source() if source is None else source
    return tuple(
        match.group(1)
        for line in content.splitlines()
        if (match := TOPIC_MARKER.fullmatch(line))
    )


def _inline(value: str) -> str:
    """Render the guide's deliberately small safe inline Markdown subset."""
    escaped = html.escape(value, quote=True)
    escaped = INLINE_CODE.sub(lambda match: f"<code>{match.group(1)}</code>", escaped)

    def replace_link(match: re.Match[str]) -> str:
        label, target = match.groups()
        if target.startswith("#") and target[1:] in TOPICS_BY_ID:
            target = topic_url(target[1:])
        elif not target.startswith(("/", "#")):
            return label
        return f'<a href="{html.escape(target, quote=True)}">{label}</a>'

    return LINK.sub(replace_link, escaped)


def render_guide_markdown(source: str | None = None) -> str:
    """Render deterministic, dependency-free HTML from the canonical guide subset."""
    lines = (guide_source() if source is None else source).splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_kind = ""
    list_item: list[str] = []
    code: list[str] | None = None
    pending_topic = ""

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list_item() -> None:
        if list_item:
            output.append(f"<li>{_inline(' '.join(list_item))}</li>")
            list_item.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            flush_list_item()
            output.append(f"</{list_kind}>")
            list_kind = ""

    for line in lines:
        if code is not None:
            if line.startswith("```"):
                output.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        if line.startswith("```"):
            flush_paragraph()
            close_list()
            code = []
            continue
        marker = TOPIC_MARKER.fullmatch(line)
        if marker:
            flush_paragraph()
            close_list()
            pending_topic = marker.group(1)
            continue
        heading = re.fullmatch(r"(#{1,4}) (.+)", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            identifier = f' id="{pending_topic}" tabindex="-1"' if pending_topic else ""
            output.append(f"<h{level}{identifier}>{_inline(heading.group(2))}</h{level}>")
            pending_topic = ""
            continue
        item = re.fullmatch(r"[-*] (.+)", line)
        numbered = re.fullmatch(r"\d+\. (.+)", line)
        if item or numbered:
            flush_paragraph()
            kind = "ul" if item else "ol"
            if list_kind != kind:
                close_list()
                output.append(f"<{kind}>")
                list_kind = kind
            else:
                flush_list_item()
            value = item.group(1) if item else numbered.group(1)  # type: ignore[union-attr]
            list_item.append(value)
            continue
        if not line.strip():
            flush_paragraph()
            close_list()
            continue
        if list_kind:
            list_item.append(line.strip())
        else:
            paragraph.append(line.strip())
    flush_paragraph()
    close_list()
    if code is not None:
        output.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
    return "\n".join(output)


def render_help_page(requested_topic: str | None = None) -> tuple[bytes, bool]:
    """Render the complete local manual and flag whether the requested topic exists."""
    known = requested_topic is None or requested_topic in TOPICS_BY_ID
    notice = ""
    if not known:
        notice = (
            '<div class="notice" role="alert"><strong>Unknown Help topic.</strong> '
            "The requested topic is not registered. The complete contents are shown safely; "
            "no application state was changed.</div>"
        )
    topics = "".join(
        f'<li><a href="{topic_url(topic.topic_id)}">{html.escape(topic.title)}</a></li>'
        for topic in HELP_TOPICS
    )
    body = render_guide_markdown()
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>RFI-1 Operator Help</title>
  <style>
    :root{{--ink:#17212b;--muted:#607083;--line:#d7dee7;--blue:#2359d1;
      --paper:#fff;--wash:#f4f7fb}}
    *{{box-sizing:border-box}}
    body{{margin:0;color:var(--ink);background:var(--wash);
      font:16px/1.58 ui-sans-serif,system-ui,-apple-system,sans-serif}}
    header{{position:sticky;top:0;z-index:2;display:flex;align-items:center;gap:20px;
      padding:12px 22px;color:#fff;background:#172334;box-shadow:0 1px 4px #0004}}
    header strong{{font-size:18px}}header a{{color:#fff}}
    header span{{color:#cdd8e7;font-size:13px}}
    .layout{{max-width:1280px;margin:auto;display:grid;
      grid-template-columns:280px minmax(0,800px);gap:28px;padding:24px}}
    aside{{position:sticky;top:74px;align-self:start;max-height:calc(100vh - 92px);
      overflow:auto;padding:18px;background:var(--paper);border:1px solid var(--line);
      border-radius:9px}}
    aside h2{{margin-top:0;font-size:17px}}aside ol{{padding-left:22px}}
    aside li{{margin:5px 0}}
    main{{min-width:0;padding:28px 38px;background:var(--paper);border:1px solid var(--line);
      border-radius:9px;box-shadow:0 1px 2px #17212b14}}
    h1{{margin-top:0}}
    h2{{margin-top:2.6rem;padding-top:1rem;border-top:1px solid var(--line);
      scroll-margin-top:105px}}
    h2:target{{outline:3px solid #f3c64f;outline-offset:8px}}h3{{margin-top:1.8rem}}
    a{{color:var(--blue)}}
    pre{{overflow:auto;padding:15px;border-radius:7px;background:#111c2a;color:#edf4ff;
      white-space:pre-wrap}}
    code{{font-family:ui-monospace,SFMono-Regular,monospace}}
    p code,li code{{padding:1px 4px;background:#edf1f6;color:#17212b;border-radius:4px}}
    .notice{{margin-bottom:20px;padding:14px;border-left:5px solid #ad5a20;
      background:#fff1df}}
    .browser-note{{margin-left:auto}}
    @media(max-width:850px){{.layout{{display:block;padding:12px}}
      aside{{position:static;max-height:none;margin-bottom:12px}}main{{padding:22px}}
      header{{flex-wrap:wrap}}.browser-note{{margin-left:0}}}}
    @media print{{header,aside{{display:none}}body{{background:#fff}}
      .layout{{display:block;padding:0}}main{{border:0;box-shadow:none;padding:0;max-width:none}}
      h2{{break-before:page}}}}
  </style>
</head>
<body>
<header><strong>RFI-1 Operator Help</strong><a href="/help">Contents</a>
  <span class="browser-note">Separate named Help view · browser controls tab/window placement</span>
</header>
<div class="layout"><aside aria-label="Help topics"><h2>Topics</h2><ol>{topics}</ol>
  <p>Use browser Find to search the complete guide.</p></aside><main>{notice}{body}</main></div>
</body></html>"""
    return page.encode(), known
