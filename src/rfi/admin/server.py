"""Small-footprint local HTTP console over public concept-catalog contracts."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from rfi.acquisition import AcquisitionRepository
from rfi.admin.field_definitions import field_definitions
from rfi.artifacts import (
    ArtifactOrder,
    ArtifactQuery,
    ArtifactQueryError,
    ArtifactQueryService,
)
from rfi.concepts import ConceptError, ConceptRepository, ConceptService
from rfi.firms import FirmError, FirmRepository, FirmService
from rfi.mailing_lists import MailingListError, MailingListQueryService, MailingListRepository
from rfi.pull import PullError, PullRequest, PullWorkflow, create_pull_workflow
from rfi.source_profiles import (
    SourceProfileError,
    SourceProfileRepository,
    SourceProfileService,
    load_canonical_template,
)
from rfi.streams import StreamError, StreamRepository, StreamService, draft_from_dict

MAX_BODY_BYTES = 1_000_000
ADMIN_PREFERENCES_JS = (Path(__file__).parent / "admin_preferences.js").read_bytes()
OPERATOR_NAVIGATION = (
    ("/concepts", "Concept Catalog"),
    ("/firms", "Target Firms"),
    ("/source-profiles", "Source Profiles"),
    ("/pull-sources", "Pull Sources"),
    ("/streams", "Streams"),
    ("/artifacts", "Artifacts"),
)
_OPERATOR_NAVIGATION_SLOT = "<!-- operator-navigation -->"


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, default=str) + "\n").encode()


def _load_operator_page(filename: str, active_path: str) -> str:
    """Compose one page with the authoritative operator navigation."""
    if active_path not in {path for path, _label in OPERATOR_NAVIGATION}:
        raise ValueError(f"unknown operator navigation path: {active_path}")
    template = (Path(__file__).parent / filename).read_text(encoding="utf-8")
    if template.count(_OPERATOR_NAVIGATION_SLOT) != 1:
        raise ValueError(f"{filename} must contain exactly one operator navigation slot")
    links = "".join(
        f'<a href="{path}"{active}>{label}</a>'
        for path, label in OPERATOR_NAVIGATION
        for active in (' aria-current="page"' if path == active_path else "",)
    )
    navigation = f'<nav aria-label="Operator sections">{links}</nav>'
    return template.replace(_OPERATOR_NAVIGATION_SLOT, navigation)


CONSOLE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>RFI Admin Console</title>
  <style>
    :root { --ink:#18212b; --muted:#667384; --line:#d8dee6; --blue:#2457d6;
      --paper:#fff; --wash:#f4f7fb; --warn:#9b3b18; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:var(--wash);
      font:14px/1.45 ui-sans-serif,system-ui,-apple-system,sans-serif; }
    header { height:62px; padding:0 24px; display:flex; align-items:center; gap:28px;
      color:#fff; background:#172334; box-shadow:0 1px 3px #0004; }
    header strong { font-size:18px; letter-spacing:.02em; }
    nav button { border:0; border-bottom:3px solid #69a2ff; padding:20px 8px 17px;
      color:#fff; background:transparent; font-weight:700; }
    main { max-width:1440px; margin:auto; padding:22px; }
    .toolbar,.panel { background:var(--paper); border:1px solid var(--line);
      border-radius:8px; box-shadow:0 1px 2px #1c2b3a14; }
    .toolbar { display:flex; gap:10px; padding:14px; margin-bottom:16px; }
    input,select,textarea { border:1px solid #b7c1ce; border-radius:5px; padding:9px;
      background:#fff; font:inherit; }
    input[type=search] { min-width:330px; }
    button { cursor:pointer; border:1px solid #b7c1ce; border-radius:5px; padding:9px 13px;
      background:#fff; font-weight:650; }
    button.primary { color:#fff; border-color:var(--blue); background:var(--blue); }
    .layout { display:grid; grid-template-columns:340px 1fr; gap:16px; min-height:680px; }
    .panel { overflow:hidden; }
    .panel h2 { margin:0; padding:16px 18px; border-bottom:1px solid var(--line); }
    #list { max-height:730px; overflow:auto; }
    .concept { display:block; width:100%; text-align:left; border:0; border-bottom:1px solid
      var(--line); border-radius:0; padding:13px 16px; }
    .concept:hover,.concept.selected { background:#edf4ff; }
    .concept small,.muted { color:var(--muted); }
    #detail { padding:20px 24px 30px; }
    .badge { display:inline-block; margin:0 5px 5px 0; padding:3px 8px; border-radius:20px;
      background:#e8eef8; font-size:12px; }
    .status { color:#175c2d; background:#dcf4e3; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px 20px; }
    .method { margin:12px 0; padding:13px; border-left:4px solid #6688b5;
      background:#f6f8fb; }
    pre { white-space:pre-wrap; overflow-wrap:anywhere; }
    dialog { width:min(920px,94vw); max-height:92vh; border:0; border-radius:10px;
      box-shadow:0 12px 45px #0006; }
    dialog::backdrop { background:#101820a8; }
    form { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    label { display:flex; flex-direction:column; gap:5px; font-weight:650; }
    label.wide { grid-column:1/-1; }
    textarea { min-height:78px; font-family:ui-monospace,SFMono-Regular,monospace; }
    #methods { min-height:220px; }
    .actions { grid-column:1/-1; display:flex; justify-content:flex-end; gap:10px; }
    #message { min-height:22px; color:var(--warn); font-weight:650; }
    @media(max-width:800px) { .layout{grid-template-columns:1fr}.toolbar{flex-wrap:wrap} }
  </style>
</head>
<body>
<header><strong>RFI Admin Console</strong><nav><button>Concept Catalog</button></nav></header>
<main>
  <div class="toolbar">
    <input id="search" type="search" placeholder="Search ID, name, alias, hint, or keyword">
    <select id="status"><option value="">All statuses</option><option>active</option>
      <option>draft</option><option>retired</option><option>superseded</option></select>
    <input id="tag" placeholder="Tag">
    <input id="valid" type="date" title="Valid on">
    <button id="refresh">Search</button>
    <button id="new-concept" class="primary">New concept</button>
  </div>
  <div class="layout">
    <section class="panel"><h2>Concepts <span id="count" class="muted"></span></h2>
      <div id="list"></div></section>
    <section class="panel"><div id="detail"><p class="muted">Select a concept.</p></div></section>
  </div>
</main>
<dialog id="editor">
  <h2 id="editor-title">Concept editor</h2><div id="message"></div>
  <form id="form">
    <label>Stable ID<input name="concept_id" required pattern="[a-z][a-z0-9._-]*"></label>
    <label>Display name<input name="display_name" required></label>
    <label class="wide">Definition<textarea name="definition" required></textarea></label>
    <label class="wide">Comments<textarea name="comments"></textarea></label>
    <label>Aliases (comma separated)<input name="aliases"></label>
    <label>Hints (comma separated)<input name="hints"></label>
    <label>Tags (comma separated)<input name="tags"></label>
    <label>Status<select name="status"><option>draft</option><option>active</option>
      <option>retired</option><option>superseded</option></select></label>
    <label>Valid from<input name="valid_from" type="date" required></label>
    <label>Valid through<input name="valid_through" type="date"></label>
    <label>Sample/example date<input name="sample_date" type="date"></label>
    <label>Related IDs (comma separated)<input name="related_concept_ids"></label>
    <label class="wide">Methods and derivations (JSON array)<textarea id="methods"
      name="methods">[]</textarea></label>
    <label class="wide">Samples (JSON array)<textarea name="samples">[]</textarea></label>
    <label class="wide">Warnings (one per line)<textarea name="warnings"></textarea></label>
    <div class="actions"><button type="button" id="validate">Validate</button>
      <button type="button" id="cancel">Cancel</button>
      <button type="submit" class="primary">Save new revision</button></div>
  </form>
</dialog>
<script>
let selected=null;
const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,c=>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const split=s=>s.split(',').map(x=>x.trim()).filter(Boolean);
async function api(path,options={}) {
  const response=await fetch(path,{headers:{'Content-Type':'application/json'},...options});
  const data=await response.json(); if(!response.ok) throw new Error(data.error||'Request failed');
  return data;
}
async function load() {
  const params=new URLSearchParams({
    q:document.getElementById('search').value,
    tag:document.getElementById('tag').value,
    status:document.getElementById('status').value,
    valid_on:document.getElementById('valid').value});
  const data=await api('/api/concepts?'+params);
  document.getElementById('count').textContent='('+data.items.length+')';
  document.getElementById('list').innerHTML=data.items.map(x=>
    `<button class="concept ${selected===x.concept_id?'selected':''}"
    onclick="showConcept('${escapeHtml(x.concept_id)}')"><b>${escapeHtml(x.display_name)}</b><br>
    <small>${escapeHtml(x.concept_id)} · r${x.revision_number} · ${escapeHtml(x.status)}</small>
    </button>`).join('')||'<p class="muted" style="padding:16px">No matching concepts.</p>';
}
async function showConcept(id,revision='') {
  selected=id; const x=await api('/api/concepts/'+encodeURIComponent(id)+
    (revision?'?revision_id='+encodeURIComponent(revision):'')); const history=await api(
    '/api/concepts/'+encodeURIComponent(id)+'/history');
  detail.innerHTML=`<div style="float:right"><button onclick="editConcept()">Edit</button>
    <button onclick="retireConcept()">Retire</button></div><h1>${escapeHtml(x.display_name)}</h1>
    <p><code>${escapeHtml(x.concept_id)}</code>
    <span class="badge status">${escapeHtml(x.status)}</span>
    revision ${x.revision_number}</p><p>${escapeHtml(x.definition)}</p>
    <div class="grid"><div><b>Validity</b><br>${x.valid_from} — ${x.valid_through||'open'}</div>
    <div><b>Sample date</b><br>${x.sample_date||'—'}</div><div><b>Aliases</b><br>
    ${x.aliases.map(a=>`<span class="badge">${escapeHtml(a)}</span>`).join('')||'—'}</div>
    <div><b>Tags</b><br>
    ${x.tags.map(a=>`<span class="badge">${escapeHtml(a)}</span>`).join('')||'—'}</div></div>
    <h3>Comments</h3><p>${escapeHtml(x.comments)||'—'}</p><h3>Hints</h3>
    <p>${x.hints.map(escapeHtml).join(' · ')||'—'}</p>
    <h3>Observation and derivation methods</h3>
    ${x.methods.map(m=>`<div class="method"><b>${escapeHtml(m.name)}</b>
    <span class="badge">${escapeHtml(m.kind)}</span>
    <span class="badge">${escapeHtml(m.result_shape)}</span>
    <br><code>${escapeHtml(m.method_id)}</code>
    <pre>${escapeHtml(JSON.stringify(m.configuration,null,2))}</pre></div>`).join('')
      ||'<p>None defined.</p>'}
    <h3>Samples and warnings</h3><pre>${escapeHtml(JSON.stringify(x.samples,null,2))}</pre>
    <p>${x.warnings.map(escapeHtml).join('<br>')}</p><h3>Revision history</h3>
    ${history.items.map(h=>`<button
      onclick="showConcept('${escapeHtml(id)}','${h.revision_id}')">
      r${h.revision_number} · ${escapeHtml(h.updated_at)}</button>`).join(' ')}`;
  selected=x.concept_id; window.current=x; await load();
}
function values() { const d=Object.fromEntries(new FormData(form));
  if(window.editing) d.concept_id=window.editing.concept_id;
  for(const k of ['aliases','hints','tags','related_concept_ids']) d[k]=split(d[k]);
  d.warnings=d.warnings.split('\\n').map(x=>x.trim()).filter(Boolean);
  d.methods=JSON.parse(d.methods||'[]'); d.samples=JSON.parse(d.samples||'[]');
  d.classifications=window.current?.classifications||{}; return d; }
function openEditor(x=null) { form.reset(); methods.value='[]'; form.samples.value='[]';
  message.textContent=''; window.editing=x; window.current=x||null;
  if(x) for(const [k,v] of Object.entries(x)) { const el=form.elements[k]; if(!el) continue;
    if(['aliases','hints','tags','related_concept_ids'].includes(k)) el.value=v.join(', ');
    else if(k==='warnings') el.value=v.join('\\n');
    else if(k==='methods'||k==='samples')
      el.value=JSON.stringify(v,null,2); else if(v!==null&&typeof v!=='object') el.value=v; }
  form.concept_id.disabled=!!x; editor.showModal(); }
async function validateForm() { try { const data=await api('/api/concepts/validate',
  {method:'POST',body:JSON.stringify(values())});
  message.textContent=data.valid?'Definition is valid.':data.errors.join('; ');
  } catch(e){message.textContent=e.message;} }
async function save(event) { event.preventDefault(); try { const payload=values(); let x;
  if(window.editing) x=await api('/api/concepts/'+encodeURIComponent(window.editing.concept_id),
    {method:'PUT',body:JSON.stringify({
      expected_revision_id:window.editing.revision_id,concept:payload})});
  else x=await api('/api/concepts',{method:'POST',body:JSON.stringify(payload)});
  editor.close(); await showConcept(x.concept_id); } catch(e){message.textContent=e.message;} }
async function retireConcept(){
  if(!window.current||!confirm('Retire by creating a new revision?'))return;
  try{await api('/api/concepts/'+encodeURIComponent(window.current.concept_id)+'/retire',
    {method:'POST',body:JSON.stringify({expected_revision_id:window.current.revision_id})});
    await showConcept(window.current.concept_id);}catch(e){alert(e.message)}}
const editConcept=()=>openEditor(window.current); refresh.onclick=load;
document.getElementById('new-concept').onclick=()=>openEditor();
validate.onclick=validateForm; cancel.onclick=()=>editor.close(); form.onsubmit=save;
search.onkeydown=e=>{if(e.key==='Enter')load()}; load();
</script></body></html>"""

# The substantial schema-aware console is kept as a browser-native asset so its typed editor can
# evolve without coupling operator interaction code to the HTTP adapter. The fallback above keeps
# source archives made before TASK-010 readable, while normal operation always uses this asset.
_CONSOLE_ASSET = Path(__file__).with_name("console.html")
if _CONSOLE_ASSET.exists():
    CONSOLE_HTML = _load_operator_page("console.html", "/concepts")
FIRMS_HTML = _load_operator_page("firms.html", "/firms")
SOURCE_PROFILES_HTML = _load_operator_page("source_profiles.html", "/source-profiles")
PULL_SOURCES_HTML = _load_operator_page("pull_sources.html", "/pull-sources")
ARTIFACT_BROWSER_HTML = _load_operator_page("artifact_browser.html", "/artifacts")
STREAMS_HTML = _load_operator_page("streams.html", "/streams")


class AdminConsole(ThreadingHTTPServer):
    """HTTP composition root; all catalog work is delegated to the public service."""

    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        service: ConceptService,
        firm_service: FirmService,
        source_profile_service: SourceProfileService,
        pull_workflow: PullWorkflow,
        artifact_query_service: ArtifactQueryService,
        mailing_list_query_service: MailingListQueryService,
        stream_service: StreamService,
    ) -> None:
        self.service = service
        self.firm_service = firm_service
        self.source_profile_service = source_profile_service
        self.pull_workflow = pull_workflow
        self.artifact_query_service = artifact_query_service
        self.mailing_list_query_service = mailing_list_query_service
        self.stream_service = stream_service
        super().__init__(address, AdminHandler)


class AdminHandler(BaseHTTPRequestHandler):
    """HTTP adapter for the multi-tab console shell and concept public API."""

    server: AdminConsole

    def do_GET(self) -> None:
        """Serve the console shell, health check, or read API."""
        self._dispatch("GET")

    def do_POST(self) -> None:
        """Serve validated create, validate, and retirement actions."""
        self._dispatch("POST")

    def do_PUT(self) -> None:
        """Serve optimistic revision updates."""
        self._dispatch("PUT")

    def log_message(self, format_text: str, *arguments: Any) -> None:
        """Retain standard visibility without logging request bodies or credentials."""
        super().log_message(format_text, *arguments)

    def _dispatch(self, method: str) -> None:
        try:
            split = urlsplit(self.path)
            path = unquote(split.path)
            if ".." in path.split("/") or "\\" in path or "\x00" in path:
                self._error(HTTPStatus.BAD_REQUEST, "unsafe path rejected")
                return
            if method == "GET" and path in {"/", "/concepts"}:
                self._send(HTTPStatus.OK, CONSOLE_HTML.encode(), "text/html; charset=utf-8")
                return
            if method == "GET" and path == "/firms":
                self._send(HTTPStatus.OK, FIRMS_HTML.encode(), "text/html; charset=utf-8")
                return
            if method == "GET" and path == "/source-profiles":
                self._send(
                    HTTPStatus.OK,
                    SOURCE_PROFILES_HTML.encode(),
                    "text/html; charset=utf-8",
                )
                return
            if method == "GET" and path == "/pull-sources":
                self._send(
                    HTTPStatus.OK,
                    PULL_SOURCES_HTML.encode(),
                    "text/html; charset=utf-8",
                )
                return
            if method == "GET" and path == "/artifacts":
                self._send(
                    HTTPStatus.OK,
                    ARTIFACT_BROWSER_HTML.encode(),
                    "text/html; charset=utf-8",
                )
                return
            if method == "GET" and path == "/streams":
                self._send(
                    HTTPStatus.OK,
                    STREAMS_HTML.encode(),
                    "text/html; charset=utf-8",
                )
                return
            if method == "GET" and path == "/admin/admin_preferences.js":
                self._send(
                    HTTPStatus.OK,
                    ADMIN_PREFERENCES_JS,
                    "text/javascript; charset=utf-8",
                )
                return
            if method == "GET" and path == "/health":
                self._send_json(HTTPStatus.OK, {"status": "ok", "bind": "local-default"})
                return
            if method == "GET" and path == "/api/field-definitions":
                self._send_json(HTTPStatus.OK, {"fields": field_definitions()})
                return
            if not path.startswith("/api/"):
                self._error(HTTPStatus.NOT_FOUND, "unknown browser request")
                return
            self._api(method, path, parse_qs(split.query))
        except (
            ConceptError,
            FirmError,
            SourceProfileError,
            PullError,
            ArtifactQueryError,
            MailingListError,
            StreamError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            if isinstance(error, ArtifactQueryError):
                status = HTTPStatus.NOT_FOUND if error.code in {
                    "unknown_firm", "unknown_document_id", "unknown_observation_id",
                    "missing_stored_content"
                } else HTTPStatus.CONFLICT if error.code in {
                    "stale_cursor", "checksum_mismatch"
                } else HTTPStatus.BAD_REQUEST
                self._error(status, str(error), error.code)
            elif isinstance(error, MailingListError):
                status = (
                    HTTPStatus.NOT_FOUND
                    if error.code.startswith("unknown_")
                    else HTTPStatus.BAD_REQUEST
                )
                self._error(status, str(error), error.code)
            elif isinstance(error, StreamError):
                status = (
                    HTTPStatus.NOT_FOUND
                    if error.code.startswith("unknown_")
                    else HTTPStatus.CONFLICT
                    if error.code in {"revision_conflict", "upstream_not_current"}
                    else HTTPStatus.BAD_REQUEST
                )
                self._error(status, str(error), error.code)
            else:
                self._error(HTTPStatus.BAD_REQUEST, str(error))
        except Exception as error:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"request failed: {error}")

    def _api(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        parts = [item for item in path.split("/") if item]
        service = self.server.service
        firm_service = self.server.firm_service
        source_profile_service = self.server.source_profile_service
        pull_workflow = self.server.pull_workflow
        artifacts = self.server.artifact_query_service
        mailing_lists = self.server.mailing_list_query_service
        streams = self.server.stream_service
        if method == "GET" and parts == ["api", "external-sources"]:
            self._send_json(HTTPStatus.OK, {"items": list(streams.external_sources())})
            return
        if method == "GET" and parts == ["api", "streams"]:
            self._send_json(
                HTTPStatus.OK, {"items": [asdict(item) for item in streams.list_streams()]}
            )
            return
        if method == "GET" and parts == ["api", "streams", "capabilities"]:
            self._send_json(
                HTTPStatus.OK, {"items": [asdict(item) for item in streams.capabilities()]}
            )
            return
        if method == "POST" and parts == ["api", "streams", "validate"]:
            self._send_json(HTTPStatus.OK, asdict(streams.validate(draft_from_dict(self._body()))))
            return
        if method == "POST" and parts == ["api", "streams", "preview"]:
            body = self._body()
            draft = body.get("draft")
            if not isinstance(draft, dict):
                raise StreamError("invalid_draft", "stream draft is required")
            self._send_json(
                HTTPStatus.OK,
                asdict(streams.preview(draft_from_dict(draft), int(body.get("limit", 25)))),
            )
            return
        if method == "POST" and parts == ["api", "streams"]:
            body = self._body()
            draft = body.get("draft")
            expected = body.get("expected_revision_id")
            if not isinstance(draft, dict) or (
                expected is not None and not isinstance(expected, str)
            ):
                raise StreamError("invalid_draft", "stream draft or expected revision is invalid")
            self._send_json(
                HTTPStatus.CREATED,
                asdict(streams.save(draft_from_dict(draft), expected)),
            )
            return
        if method == "POST" and parts == ["api", "streams", "rebuild"]:
            self._send_json(HTTPStatus.OK, streams.rebuild())
            return
        if len(parts) >= 3 and parts[:2] == ["api", "streams"]:
            stream_id = parts[2]
            if method == "GET" and len(parts) == 3:
                revision_id = self._first(query, "revision_id") or None
                self._send_json(HTTPStatus.OK, asdict(streams.detail(stream_id, revision_id)))
                return
            if method == "GET" and parts[3:] == ["history"]:
                self._send_json(
                    HTTPStatus.OK,
                    {"items": [asdict(item) for item in streams.history(stream_id)]},
                )
                return
            if method == "GET" and parts[3:] == ["runs"]:
                self._send_json(
                    HTTPStatus.OK,
                    {"items": [asdict(item) for item in streams.repository.runs(stream_id)]},
                )
                return
            if method == "GET" and parts[3:] == ["memberships"]:
                limit = int(self._first(query, "limit") or "100")
                offset = int(self._first(query, "offset") or "0")
                run_id = self._first(query, "run_id") or None
                self._send_json(
                    HTTPStatus.OK,
                    {"items": [asdict(item) for item in streams.repository.memberships(
                        stream_id, run_id, limit, offset
                    )]},
                )
                return
            if method == "POST" and parts[3:] == ["run"]:
                self._body()
                self._send_json(HTTPStatus.OK, asdict(streams.run(stream_id)))
                return
            if method == "POST" and parts[3:] == ["run-chain"]:
                self._body()
                self._send_json(
                    HTTPStatus.OK,
                    {"items": [asdict(item) for item in streams.run_chain(stream_id)]},
                )
                return
        if len(parts) >= 3 and parts[:2] == ["api", "stream-runs"]:
            if method == "GET" and len(parts) == 3:
                self._send_json(HTTPStatus.OK, asdict(streams.repository.run(parts[2])))
                return
        if len(parts) >= 3 and parts[:2] == ["api", "stream-memberships"]:
            membership_id = parts[2]
            if method == "GET" and parts[3:] == ["content"]:
                self._send_artifact_content(streams.content(membership_id))
                return
            if method == "GET" and len(parts) == 3:
                self._send_json(
                    HTTPStatus.OK, asdict(streams.repository.membership(membership_id))
                )
                return
        if method == "GET" and parts == ["api", "mailing-lists", "sources"]:
            self._send_json(HTTPStatus.OK, {"items": list(mailing_lists.sources())})
            return
        if method == "GET" and parts == ["api", "mailing-lists", "discussions"]:
            source_id = self._first(query, "source_id")
            limit = int(self._first(query, "limit") or "25")
            offset = int(self._first(query, "offset") or "0")
            self._send_json(HTTPStatus.OK, {"items": [asdict(item) for item in
                mailing_lists.discussions(source_id, limit, offset)]})
            return
        if method == "GET" and parts == ["api", "mailing-lists", "incomplete"]:
            source_id = self._first(query, "source_id") or None
            self._send_json(HTTPStatus.OK, {"items": [asdict(item) for item in
                mailing_lists.incomplete(source_id)]})
            return
        if method == "GET" and parts == ["api", "mailing-lists", "search"]:
            self._send_json(HTTPStatus.OK, {"items": [asdict(item) for item in
                mailing_lists.search(self._first(query, "q"),
                                     self._first(query, "source_id") or None)]})
            return
        if len(parts) >= 4 and parts[:3] == ["api", "mailing-lists", "discussions"]:
            discussion_id = parts[3]
            if method == "GET" and len(parts) == 4:
                self._send_json(HTTPStatus.OK, asdict(mailing_lists.discussion(discussion_id)))
                return
            if method == "GET" and parts[4:] == ["projection"]:
                limit = int(self._first(query, "limit") or "100")
                self._send_json(
                    HTTPStatus.OK, asdict(mailing_lists.projection(discussion_id, limit))
                )
                return
        if len(parts) >= 4 and parts[:3] == ["api", "mailing-lists", "messages"]:
            message_key = parts[3]
            if method == "GET" and parts[4:] == ["content"]:
                self._send_artifact_content(mailing_lists.content(message_key))
                return
            if method == "GET" and parts[4:] == ["children"]:
                limit = int(self._first(query, "limit") or "50")
                offset = int(self._first(query, "offset") or "0")
                self._send_json(HTTPStatus.OK, {"items": [asdict(item) for item in
                    mailing_lists.children(message_key, limit, offset)]})
                return
            if method == "GET" and parts[4:] == ["ancestors"]:
                self._send_json(HTTPStatus.OK, {"items": [asdict(item) for item in
                    mailing_lists.ancestors(message_key)]})
                return
            if method == "GET" and len(parts) == 4:
                self._send_json(HTTPStatus.OK, asdict(mailing_lists.message(message_key)))
                return
        if method == "GET" and parts == ["api", "artifacts", "firms"]:
            self._send_json(HTTPStatus.OK, {"items": list(artifacts.firms())})
            return
        if method == "GET" and parts == ["api", "artifacts", "families"]:
            firm_id = self._first(query, "firm_id")
            self._send_json(HTTPStatus.OK, {"items": list(artifacts.families(firm_id))})
            return
        if method == "GET" and parts == ["api", "artifacts", "types"]:
            firm_id = self._first(query, "firm_id")
            family_id = self._first(query, "family_id")
            self._send_json(
                HTTPStatus.OK,
                {"items": list(artifacts.canonical_types(firm_id, family_id))},
            )
            return
        if method == "GET" and parts == ["api", "artifacts"]:
            order_text = self._first(query, "order") or ArtifactOrder.NEWEST.value
            try:
                order = ArtifactOrder(order_text)
            except ValueError as error:
                raise ArtifactQueryError(
                    "invalid_query", "order must be newest or oldest"
                ) from error
            limit_text = self._first(query, "limit") or "50"
            page = artifacts.query(
                ArtifactQuery(
                    firm_ids=self._query_values(query, "firm_id"),
                    family_ids=self._query_values(query, "family_id"),
                    canonical_artifact_ids=self._query_values(query, "canonical_artifact_id"),
                    provider_ids=self._query_values(query, "provider"),
                    source_effective_from=self._first(query, "date_from") or None,
                    source_effective_through=self._first(query, "date_through") or None,
                    order=order,
                    limit=int(limit_text),
                    cursor=self._first(query, "cursor") or None,
                )
            )
            self._send_json(HTTPStatus.OK, asdict(page))
            return
        if len(parts) >= 3 and parts[:2] == ["api", "artifacts"]:
            document_id = parts[2]
            if method == "GET" and parts[3:] == ["content"]:
                self._send_artifact_content(artifacts.content(document_id))
                return
            if method == "GET" and len(parts) == 3:
                selection = self._first(query, "observation") or "last"
                self._send_json(
                    HTTPStatus.OK, asdict(artifacts.detail(document_id, selection))
                )
                return
            if method == "GET" and parts[3:] == ["observations", "next"]:
                self._send_json(
                    HTTPStatus.OK,
                    asdict(artifacts.next(self._first(query, "cursor"))),
                )
                return
            if method == "GET" and parts[3:] == ["observations", "previous"]:
                self._send_json(
                    HTTPStatus.OK,
                    asdict(artifacts.previous(self._first(query, "cursor"))),
                )
                return
        if method == "GET" and parts == ["api", "pulls", "adapters"]:
            self._send_json(
                HTTPStatus.OK,
                {"items": list(pull_workflow.adapter_capabilities())},
            )
            return
        if method == "GET" and parts == ["api", "pulls", "firms"]:
            self._send_json(
                HTTPStatus.OK,
                {"items": [asdict(item) for item in pull_workflow.configured_firms()]},
            )
            return
        if method == "POST" and parts == ["api", "pulls"]:
            body = self._body()
            firm_ids = body.get("firm_ids", [])
            if not isinstance(firm_ids, list) or any(
                not isinstance(item, str) for item in firm_ids
            ):
                raise PullError("firm_ids must be an array of strings")
            all_configured = body.get("all_configured", False)
            if not isinstance(all_configured, bool):
                raise PullError("all_configured must be true or false")
            run_id = pull_workflow.initiate(
                PullRequest(tuple(firm_ids), all_configured)
            )
            threading.Thread(
                target=pull_workflow.execute,
                args=(run_id,),
                name=f"rfi-{run_id}",
                daemon=True,
            ).start()
            self._send_json(
                HTTPStatus.ACCEPTED,
                {
                    "run_id": run_id,
                    "status": "running",
                    "status_url": f"/api/pulls/{run_id}",
                    "results_url": f"/api/pulls/{run_id}/results",
                },
            )
            return
        if len(parts) >= 3 and parts[:2] == ["api", "pulls"]:
            run_id = parts[2]
            if method == "GET" and len(parts) == 3:
                self._send_json(HTTPStatus.OK, pull_workflow.status(run_id))
                return
            if method == "GET" and parts[3:] == ["results"]:
                self._send_json(HTTPStatus.OK, pull_workflow.results(run_id))
                return
        if method == "GET" and parts == ["api", "source-profile-template"]:
            self._send_json(
                HTTPStatus.OK,
                source_profile_service.canonical_template(),
            )
            return
        if method == "GET" and parts == ["api", "firms"]:
            items = firm_service.list_firms(
                self._first(query, "q"),
                self._first(query, "status") or None,
                self._first(query, "sector") or None,
                self._first(query, "industry") or None,
                float(self._first(query, "minimum_relevance"))
                if self._first(query, "minimum_relevance")
                else None,
            )
            self._send_json(HTTPStatus.OK, {"items": [asdict(item) for item in items]})
            return
        if method == "POST" and parts == ["api", "firms"]:
            self._send_json(HTTPStatus.CREATED, asdict(firm_service.create(self._body())))
            return
        if method == "POST" and parts == ["api", "firms", "validate"]:
            body = self._body()
            current = body.pop("current_firm_id", None)
            self._send_json(HTTPStatus.OK, firm_service.validate(body, current))
            return
        if len(parts) >= 3 and parts[:2] == ["api", "firms"]:
            firm_id = parts[2]
            if parts[3:] == ["source-profile"]:
                if method == "GET":
                    revision_id = self._first(query, "revision_id") or None
                    profile = source_profile_service.detail(firm_id, revision_id)
                    self._send_json(HTTPStatus.OK, asdict(profile))
                    return
                body = self._body()
                if method == "PUT":
                    expected = body.get("expected_revision_id")
                    if expected is not None and not isinstance(expected, str):
                        raise SourceProfileError(
                            "expected source-profile revision identifier must be a string or null"
                        )
                    profile = body.get("profile")
                    if not isinstance(profile, dict):
                        raise SourceProfileError("source-profile payload is required")
                    result = source_profile_service.publish(firm_id, profile, expected)
                    self._send_json(HTTPStatus.OK, asdict(result))
                    return
            if method == "GET" and parts[3:] == ["source-profile", "history"]:
                history = source_profile_service.history(firm_id)
                self._send_json(
                    HTTPStatus.OK,
                    {"items": [asdict(item) for item in history]},
                )
                return
            if method == "POST" and parts[3:] == ["source-profile", "validate"]:
                self._send_json(
                    HTTPStatus.OK,
                    source_profile_service.validate(firm_id, self._body()),
                )
                return
            if method == "GET" and len(parts) == 3:
                revision_id = self._first(query, "revision_id") or None
                self._send_json(HTTPStatus.OK, asdict(firm_service.detail(firm_id, revision_id)))
                return
            if method == "GET" and parts[3:] == ["history"]:
                history = firm_service.history(firm_id)
                self._send_json(HTTPStatus.OK, {"items": [asdict(item) for item in history]})
                return
            body = self._body()
            expected = body.get("expected_revision_id")
            if not isinstance(expected, str) or not expected:
                raise FirmError("expected_revision_id is required")
            if method == "PUT" and len(parts) == 3:
                firm = body.get("firm")
                if not isinstance(firm, dict):
                    raise FirmError("firm payload is required")
                result = firm_service.revise(firm_id, firm, expected)
                self._send_json(HTTPStatus.OK, asdict(result))
                return
            if method == "POST" and parts[3:] == ["retire"]:
                self._send_json(HTTPStatus.OK, asdict(firm_service.retire(firm_id, expected)))
                return
        if method == "GET" and parts == ["api", "concepts"]:
            items = service.list_concepts(
                self._first(query, "q"),
                self._first(query, "tag") or None,
                self._first(query, "status") or None,
                self._first(query, "valid_on") or None,
            )
            self._send_json(HTTPStatus.OK, {"items": [asdict(item) for item in items]})
            return
        if method == "POST" and parts == ["api", "concepts"]:
            self._send_json(HTTPStatus.CREATED, asdict(service.create(self._body())))
            return
        if method == "POST" and parts == ["api", "concepts", "validate"]:
            self._send_json(HTTPStatus.OK, service.validate(self._body()))
            return
        if len(parts) >= 3 and parts[:2] == ["api", "concepts"]:
            concept_id = parts[2]
            if method == "GET" and len(parts) == 3:
                revision_id = self._first(query, "revision_id") or None
                self._send_json(HTTPStatus.OK, asdict(service.detail(concept_id, revision_id)))
                return
            if method == "GET" and parts[3:] == ["history"]:
                history = service.history(concept_id)
                self._send_json(
                    HTTPStatus.OK,
                    {"items": [asdict(item) for item in history]},
                )
                return
            body = self._body()
            expected = body.get("expected_revision_id")
            if not isinstance(expected, str) or not expected:
                raise ConceptError("expected_revision_id is required")
            if method == "PUT" and len(parts) == 3:
                concept = body.get("concept")
                if not isinstance(concept, dict):
                    raise ConceptError("concept payload is required")
                result = service.revise(concept_id, concept, expected)
                self._send_json(HTTPStatus.OK, asdict(result))
                return
            if method == "POST" and parts[3:] == ["retire"]:
                self._send_json(HTTPStatus.OK, asdict(service.retire(concept_id, expected)))
                return
        self._error(HTTPStatus.NOT_FOUND, "unknown API request")

    def _body(self) -> dict[str, Any]:
        length_text = self.headers.get("Content-Length")
        if not length_text:
            raise ConceptError("request body is required")
        length = int(length_text)
        if length < 0 or length > MAX_BODY_BYTES:
            raise ConceptError("request body exceeds local console limit")
        if self.headers.get_content_type() != "application/json":
            raise ConceptError("application/json is required")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ConceptError("request JSON must be an object")
        return value

    def _first(self, query: dict[str, list[str]], name: str) -> str:
        return query.get(name, [""])[0]

    @staticmethod
    def _query_values(query: dict[str, list[str]], name: str) -> tuple[str, ...]:
        return tuple(value for value in query.get(name, []) if value)

    def _error(self, status: HTTPStatus, message: str, error_code: str | None = None) -> None:
        self._send_json(
            status,
            {
                "error": message,
                "error_code": error_code or self._error_code(message, status),
                "status": int(status),
            },
        )

    @staticmethod
    def _error_code(message: str, status: HTTPStatus) -> str:
        """Classify failures so the GUI can present focused recovery guidance."""
        text = message.casefold()
        if "current revision has changed" in text:
            return "revision_conflict"
        if "current firm revision has changed" in text:
            return "revision_conflict"
        if "conflicting firm identifier" in text:
            return "identifier_conflict"
        if "conflicting firm domain" in text:
            return "domain_conflict"
        if "duplicate" in text:
            return "duplicate"
        if "validity interval" in text or "iso date" in text:
            return "invalid_date_interval"
        if "deterministic" in text or "required_inputs" in text:
            return "invalid_deterministic_method"
        if "method" in text or "result shape" in text:
            return "invalid_method"
        if "unit" in text:
            return "incompatible_unit"
        if status == HTTPStatus.INTERNAL_SERVER_ERROR:
            return "persistence_failure"
        return "invalid_request"

    def _send_json(self, status: HTTPStatus, value: Any) -> None:
        self._send(status, _json(value), "application/json; charset=utf-8")

    def _send_artifact_content(self, value: Any) -> None:
        """Serve exact bytes with an origin-isolating policy for hostile stored content."""
        media_type = value.media_type.lower()
        allowed = {
            "text/html", "application/xhtml+xml", "application/pdf", "text/plain",
            "text/csv", "application/json", "application/xml", "text/xml",
        }
        if media_type not in allowed and not media_type.startswith("text/"):
            media_type = "application/octet-stream"
        content = value.content
        status = HTTPStatus.OK
        content_range = None
        range_header = self.headers.get("Range")
        if range_header:
            if not range_header.startswith("bytes=") or "," in range_header:
                raise ArtifactQueryError("invalid_query", "unsupported content range")
            try:
                start_text, end_text = range_header[6:].split("-", 1)
                start = int(start_text) if start_text else 0
                end = int(end_text) if end_text else len(content) - 1
            except ValueError as error:
                raise ArtifactQueryError("invalid_query", "invalid content range") from error
            if start < 0 or end < start or end >= len(content):
                raise ArtifactQueryError("invalid_query", "content range is outside stored bytes")
            content = content[start : end + 1]
            status = HTTPStatus.PARTIAL_CONTENT
            content_range = f"bytes {start}-{end}/{len(value.content)}"
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Accept-Ranges", "bytes")
        if content_range:
            self.send_header("Content-Range", content_range)
        self.send_header("Content-Disposition", f'inline; filename="{value.document_id}"')
        self.send_header("Cache-Control", "private, immutable")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data: blob:; "
            "media-src data: blob:; frame-ancestors 'self'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(content)

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)


def create_admin_server(
    state: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> AdminConsole:
    """Create a local-default server backed by repository-controlled catalog state."""
    if not 0 <= port <= 65535:
        raise ConceptError("port must be between 0 and 65535")
    repository = ConceptRepository.open(state)
    firm_repository = FirmRepository.open(state / "firm-catalog")
    template = load_canonical_template()
    source_profile_state = state / "source-profiles"
    source_profile_repository = SourceProfileRepository.open(source_profile_state, template)
    acquisition_repository = AcquisitionRepository(state / "acquisition")
    firm_service = FirmService(firm_repository)
    return AdminConsole(
        (host, port),
        ConceptService(repository),
        firm_service,
        SourceProfileService(source_profile_repository, firm_repository, template),
        create_pull_workflow(state),
        ArtifactQueryService(acquisition_repository, firm_repository, template),
        MailingListQueryService(MailingListRepository(state)),
        StreamService(StreamRepository(state)),
    )
