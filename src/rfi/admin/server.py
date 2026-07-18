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

from rfi.admin.field_definitions import field_definitions
from rfi.concepts import ConceptError, ConceptRepository, ConceptService
from rfi.firms import FirmError, FirmRepository, FirmService
from rfi.pull import PullError, PullRequest, PullWorkflow, create_pull_workflow
from rfi.source_profiles import (
    SourceProfileError,
    SourceProfileRepository,
    SourceProfileService,
    load_canonical_template,
)

MAX_BODY_BYTES = 1_000_000


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, default=str) + "\n").encode()


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
    CONSOLE_HTML = _CONSOLE_ASSET.read_text(encoding="utf-8")
_FIRMS_ASSET = Path(__file__).with_name("firms.html")
FIRMS_HTML = _FIRMS_ASSET.read_text(encoding="utf-8")
_SOURCE_PROFILES_ASSET = Path(__file__).with_name("source_profiles.html")
SOURCE_PROFILES_HTML = _SOURCE_PROFILES_ASSET.read_text(encoding="utf-8")
_PULL_SOURCES_ASSET = Path(__file__).with_name("pull_sources.html")
PULL_SOURCES_HTML = _PULL_SOURCES_ASSET.read_text(encoding="utf-8")


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
    ) -> None:
        self.service = service
        self.firm_service = firm_service
        self.source_profile_service = source_profile_service
        self.pull_workflow = pull_workflow
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
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            self._error(HTTPStatus.BAD_REQUEST, str(error))
        except Exception as error:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"request failed: {error}")

    def _api(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        parts = [item for item in path.split("/") if item]
        service = self.server.service
        firm_service = self.server.firm_service
        source_profile_service = self.server.source_profile_service
        pull_workflow = self.server.pull_workflow
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

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(
            status,
            {
                "error": message,
                "error_code": self._error_code(message, status),
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
    source_profile_repository = (
        SourceProfileRepository.open(source_profile_state, template)
        if source_profile_state.exists()
        else SourceProfileRepository.initialize(source_profile_state, template)
    )
    return AdminConsole(
        (host, port),
        ConceptService(repository),
        FirmService(firm_repository),
        SourceProfileService(source_profile_repository, firm_repository, template),
        create_pull_workflow(state),
    )
