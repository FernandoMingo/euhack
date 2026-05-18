"""Throwaway localhost UI for inspecting CivicCircles matching.

Pure stdlib (`http.server` + `json`). Boots a fresh SQLite database in a
temporary directory, seeds the activity catalog, and exposes a tiny
single-page UI for:

* resident -> activity-template ranking (`MatchingEngine`)
* resident group/circle proposals around a template (`CircleEngine`)

Usage:

    python3 backend/scripts/serve_matching_ui.py
    # then visit http://127.0.0.1:8765/

This script is intentionally not wired into production. It creates only
temporary data and sends no invitations.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import shutil
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import (  # noqa: E402
    ActivityRepository,
    ActivityTemplateRepository,
    CircleEngine,
    MatchingEngine,
    MatchingRepository,
    ResidentRepository,
    configure_logging,
    connect,
    init_db,
)
from app.seed import seed_activity_templates  # noqa: E402

logger = logging.getLogger("matching_ui")

DEFAULT_CANDIDATES = [
    {
        "first_name": "Sofia",
        "interests": ["photography", "nature", "outdoor"],
        "activity_prefs": ["photography_walk"],
        "availability": [{"weekday": "sat", "start": "09:00", "end": "12:00"}],
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "group_min": 3,
        "group_max": 6,
    },
    {
        "first_name": "Marco",
        "interests": ["photography", "outdoor"],
        "activity_prefs": ["photography_walk"],
        "availability": [{"weekday": "sat", "start": "10:00", "end": "12:30"}],
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "group_min": 3,
        "group_max": 5,
    },
    {
        "first_name": "Aisha",
        "interests": ["nature", "photography"],
        "activity_prefs": ["photography_walk"],
        "availability": [{"weekday": "sat", "start": "09:30", "end": "11:30"}],
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "group_min": 3,
        "group_max": 6,
    },
    {
        "first_name": "Bo",
        "interests": ["nature", "outdoor"],
        "activity_prefs": ["photography_walk"],
        "availability": [{"weekday": "sat", "start": "10:30", "end": "11:30"}],
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "group_min": 3,
        "group_max": 6,
    },
    {
        "first_name": "Diego",
        "interests": ["photography"],
        "activity_prefs": ["photography_walk"],
        "avoidances": ["walks_outdoor"],
        "availability": [{"weekday": "sat", "start": "09:00", "end": "12:00"}],
        "social_comfort": "small_group_low_pressure",
        "cost_sensitivity": "free_or_low_cost",
        "group_min": 3,
        "group_max": 6,
    },
]


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CivicCircles Matching Inspector</title>
<style>
  :root {
    --bg: #f5f7fb;
    --card: #fff;
    --text: #172033;
    --muted: #687186;
    --border: #dfe4ef;
    --accent: #2f6df6;
    --soft: #edf3ff;
    --bad: #b91c1c;
    --good: #047857;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
  }
  header {
    padding: 18px 28px;
    background: white;
    border-bottom: 1px solid var(--border);
  }
  h1 { margin: 0; font-size: 20px; }
  header p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
  main {
    max-width: 1280px;
    margin: 22px auto;
    padding: 0 20px;
    display: grid;
    grid-template-columns: 390px 1fr;
    gap: 18px;
  }
  @media (max-width: 920px) { main { grid-template-columns: 1fr; } }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
    box-shadow: 0 8px 24px rgba(23, 32, 51, 0.04);
  }
  h2 { margin: 0 0 14px; font-size: 16px; }
  h3 { margin: 0 0 8px; font-size: 14px; }
  label {
    display: block;
    margin: 12px 0 5px;
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
  }
  input, select, textarea {
    width: 100%;
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 8px 10px;
    font: inherit;
    font-size: 13px;
    background: white;
  }
  textarea { min-height: 68px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px; }
  .tab {
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 9px;
    background: white;
    color: var(--text);
    font-weight: 700;
    cursor: pointer;
  }
  .tab.active { background: var(--accent); color: white; border-color: var(--accent); }
  .panel { display: none; }
  .panel.active { display: block; }
  button.run {
    margin-top: 14px;
    width: 100%;
    border: 0;
    border-radius: 9px;
    background: var(--accent);
    color: white;
    padding: 10px 12px;
    font-weight: 700;
    cursor: pointer;
  }
  button.run:disabled { opacity: .55; cursor: wait; }
  .hint { color: var(--muted); font-size: 12px; line-height: 1.35; margin-top: 6px; }
  .error { color: var(--bad); font-size: 13px; margin-top: 10px; white-space: pre-wrap; }
  .result {
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 13px;
    margin-bottom: 10px;
    background: white;
  }
  .result.top { border-color: var(--accent); background: var(--soft); }
  .summary { font-size: 13px; line-height: 1.42; margin: 6px 0; }
  .meta { color: var(--muted); font-size: 12px; }
  .pill {
    display: inline-block;
    padding: 2px 7px;
    border-radius: 999px;
    margin: 3px 3px 0 0;
    background: #eef1f7;
    color: #384154;
    font-size: 11px;
  }
  .ok { color: var(--good); font-weight: 700; }
  .bad { color: var(--bad); font-weight: 700; }
  pre {
    white-space: pre-wrap;
    background: #0f172a;
    color: #e2e8f0;
    border-radius: 10px;
    padding: 12px;
    overflow: auto;
    font-size: 12px;
  }
</style>
</head>
<body>
<header>
  <h1>CivicCircles matching inspector</h1>
  <p>Throwaway local UI. Uses a temp SQLite DB, seeds the catalog, sends no invitations.</p>
</header>
<main>
  <section class="card">
    <div class="tabs">
      <button class="tab active" data-tab="ranking">Activity ranking</button>
      <button class="tab" data-tab="circles">Circle matching</button>
    </div>

    <form id="ranking-panel" class="panel active">
      <h2>Resident -> activity templates</h2>
      <label>First name</label>
      <input id="rank-name" value="Sofia">
      <label>Interests, comma separated</label>
      <textarea id="rank-interests">photography, nature, outdoor</textarea>
      <label>Activity preferences, comma separated</label>
      <textarea id="rank-activity-prefs">photography_walk</textarea>
      <label>Avoidances, comma separated</label>
      <textarea id="rank-avoidances" placeholder="pubs_social, loud_music"></textarea>
      <label>Accessibility needs, comma separated</label>
      <textarea id="rank-access" placeholder="step_free"></textarea>
      <div class="row">
        <div>
          <label>Group min</label>
          <input id="rank-group-min" type="number" min="1" value="3">
        </div>
        <div>
          <label>Group max</label>
          <input id="rank-group-max" type="number" min="1" value="6">
        </div>
      </div>
      <label>Availability JSON</label>
      <textarea id="rank-availability">[{"weekday":"sat","start":"09:00","end":"12:00"}]</textarea>
      <div class="row">
        <div>
          <label>Social comfort</label>
          <select id="rank-social">
            <option selected>small_group_low_pressure</option>
            <option>moderate_social</option>
            <option>high_energy</option>
          </select>
        </div>
        <div>
          <label>Cost sensitivity</label>
          <select id="rank-cost">
            <option>free_only</option>
            <option selected>free_or_low_cost</option>
            <option>moderate_cost_ok</option>
            <option>any_cost</option>
          </select>
        </div>
      </div>
      <label>Top N</label>
      <input id="rank-top-n" type="number" min="1" max="20" value="8">
      <button class="run" type="submit">Run activity ranking</button>
      <div id="rank-error" class="error"></div>
    </form>

    <form id="circles-panel" class="panel">
      <h2>Residents -> proposed circles</h2>
      <label>Template code</label>
      <input id="circle-template-code" value="photography_walk">
      <div class="row">
        <div>
          <label>Min group size</label>
          <input id="circle-min" type="number" min="2" value="3">
        </div>
        <div>
          <label>Max group size</label>
          <input id="circle-max" type="number" min="2" value="4">
        </div>
      </div>
      <label>Top groups</label>
      <input id="circle-top-n" type="number" min="1" max="10" value="3">
      <label>Candidate residents JSON</label>
      <textarea id="circle-candidates" style="min-height: 330px"></textarea>
      <div class="hint">Fields: first_name, interests, activity_prefs, avoidances, accessibility, availability, social_comfort, cost_sensitivity, group_min, group_max.</div>
      <button class="run" type="submit">Run circle matching</button>
      <div id="circle-error" class="error"></div>
    </form>
  </section>

  <section class="card">
    <h2>Results</h2>
    <div id="results" class="hint">Run one of the tools to see persisted matching artifacts and explanations.</div>
  </section>
</main>

<script>
const DEFAULT_CANDIDATES = __DEFAULT_CANDIDATES__;
document.getElementById("circle-candidates").value = JSON.stringify(DEFAULT_CANDIDATES, null, 2);

function csv(id) {
  return document.getElementById(id).value.split(",").map(v => v.trim()).filter(Boolean);
}

function jsonField(id) {
  const raw = document.getElementById(id).value.trim();
  return raw ? JSON.parse(raw) : [];
}

function setBusy(form, busy) {
  form.querySelector("button.run").disabled = busy;
}

function renderRaw(data) {
  return `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[ch]));
}

function renderRanking(data) {
  const items = data.results.map((r, index) => {
    const cls = index === 0 ? "result top" : "result";
    const top = (r.top_features || []).map(f => `<span class="pill">${escapeHtml(f.feature_key)} ${f.contribution}</span>`).join("");
    const status = r.hard_constraints_passed ? '<span class="ok">passed</span>' : '<span class="bad">filtered</span>';
    return `<div class="${cls}">
      <h3>#${r.rank_position} ${escapeHtml(r.template_title)}</h3>
      <div class="meta">${escapeHtml(r.template_code)} - total ${r.total_score} - cosine ${r.cosine} - ${status}</div>
      <div class="summary">${escapeHtml(r.summary_text)}</div>
      <div>${top}</div>
    </div>`;
  }).join("");
  return `<div class="meta">run_id: ${escapeHtml(data.run_id)} - persisted candidates: ${data.persisted_candidate_count}</div>${items}${renderRaw(data)}`;
}

function renderCircles(data) {
  const groups = data.groups.map((g, index) => {
    const cls = index === 0 ? "result top" : "result";
    const members = g.members.map(m => `<span class="pill">${escapeHtml(m.first_name)} (${m.template_score})</span>`).join("");
    const avail = g.shared_availability.map(v => `<span class="pill">${escapeHtml(v)}</span>`).join("");
    const interests = g.shared_interests.map(v => `<span class="pill">${escapeHtml(v)}</span>`).join("");
    return `<div class="${cls}">
      <h3>#${g.rank_position} Circle fit ${g.fit_score}</h3>
      <div class="summary">${escapeHtml(g.summary_text)}</div>
      <div class="meta">circle_id: ${escapeHtml(g.circle_id || "")}</div>
      <div>${members}</div>
      <div class="meta">Shared availability</div><div>${avail || '<span class="pill">none</span>'}</div>
      <div class="meta">Shared interests</div><div>${interests || '<span class="pill">none</span>'}</div>
    </div>`;
  }).join("");
  const rejected = data.rejected.map(r => `<div class="result">
    <h3 class="bad">${escapeHtml(r.first_name)} filtered</h3>
    <div class="summary">${escapeHtml(r.summary_text)}</div>
    <div>${r.reasons.map(v => `<span class="pill">${escapeHtml(v)}</span>`).join("")}</div>
  </div>`).join("");
  return `<div class="meta">run_id: ${escapeHtml(data.run_id)} - template: ${escapeHtml(data.template_code)}</div>
    <h3>Groups</h3>${groups || '<div class="hint">No proposed groups.</div>'}
    <h3>Rejected residents</h3>${rejected || '<div class="hint">No hard-constraint rejections.</div>'}
    ${renderRaw(data)}`;
}

document.querySelectorAll(".tab").forEach(button => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(button.dataset.tab + "-panel").classList.add("active");
  });
});

document.getElementById("ranking-panel").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const err = document.getElementById("rank-error");
  err.textContent = "";
  setBusy(form, true);
  try {
    const payload = {
      first_name: document.getElementById("rank-name").value,
      interests: csv("rank-interests"),
      activity_prefs: csv("rank-activity-prefs"),
      avoidances: csv("rank-avoidances"),
      accessibility: csv("rank-access"),
      group_min: Number(document.getElementById("rank-group-min").value),
      group_max: Number(document.getElementById("rank-group-max").value),
      availability: jsonField("rank-availability"),
      social_comfort: document.getElementById("rank-social").value,
      cost_sensitivity: document.getElementById("rank-cost").value,
      top_n: Number(document.getElementById("rank-top-n").value),
    };
    const res = await fetch("/api/activity-ranking", {method: "POST", body: JSON.stringify(payload)});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "request failed");
    document.getElementById("results").innerHTML = renderRanking(data);
  } catch (error) {
    err.textContent = error.message || String(error);
  } finally {
    setBusy(form, false);
  }
});

document.getElementById("circles-panel").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const err = document.getElementById("circle-error");
  err.textContent = "";
  setBusy(form, true);
  try {
    const payload = {
      template_code: document.getElementById("circle-template-code").value,
      min_group_size: Number(document.getElementById("circle-min").value),
      max_group_size: Number(document.getElementById("circle-max").value),
      top_n: Number(document.getElementById("circle-top-n").value),
      candidates: jsonField("circle-candidates"),
    };
    const res = await fetch("/api/circle-matching", {method: "POST", body: JSON.stringify(payload)});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "request failed");
    document.getElementById("results").innerHTML = renderCircles(data);
  } catch (error) {
    err.textContent = error.message || String(error);
  } finally {
    setBusy(form, false);
  }
});
</script>
</body>
</html>
"""


def _split_values(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [item.strip() for item in values.split(",") if item.strip()]
    if isinstance(values, list):
        return [str(item).strip() for item in values if str(item).strip()]
    raise ValueError(f"Expected string or list, got {type(values).__name__}")


def _availability(values: Any) -> list[dict[str, str]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("availability must be a list")
    result: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("availability entries must be objects")
        result.append(
            {
                "weekday": str(item.get("weekday", "sat")),
                "start": str(item.get("start", "09:00")),
                "end": str(item.get("end", "12:00")),
            }
        )
    return result


def _create_resident(repo: ResidentRepository, payload: dict[str, Any]):
    first_name = str(payload.get("first_name") or "Resident")
    resident = repo.create_resident(
        first_name=first_name,
        email=f"{first_name.lower()}.{uuid4().hex[:10]}@matching-ui.local",
        preferred_language=str(payload.get("preferred_language") or "English"),
        city=str(payload.get("city") or "Amsterdam"),
        social_comfort=str(payload.get("social_comfort") or "small_group_low_pressure"),
        preferred_group_size_min=int(payload.get("group_min") or payload.get("preferred_group_size_min") or 3),
        preferred_group_size_max=int(payload.get("group_max") or payload.get("preferred_group_size_max") or 6),
        cost_sensitivity=str(payload.get("cost_sensitivity") or "free_or_low_cost"),
    )
    for value in _split_values(payload.get("interests")):
        repo.add_preference(resident_id=resident.id, preference_type="interest", value=value)
    for value in _split_values(payload.get("activity_prefs")):
        repo.add_preference(resident_id=resident.id, preference_type="activity", value=value)
    for value in _split_values(payload.get("accessibility")):
        repo.add_preference(
            resident_id=resident.id,
            preference_type="accessibility_need",
            value=value,
        )
    for value in _split_values(payload.get("avoidances")):
        repo.add_avoidance(resident_id=resident.id, value=value)
    for item in _availability(payload.get("availability")):
        repo.add_availability(
            resident_id=resident.id,
            weekday=item["weekday"],
            start_time_local=item["start"],
            end_time_local=item["end"],
        )
    return resident


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8")
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON payload must be an object")
    return data


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_html(handler: BaseHTTPRequestHandler, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class MatchingUiServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], db_path: Path) -> None:
        super().__init__(server_address, MatchingUiHandler)
        self.db_path = db_path


class MatchingUiHandler(BaseHTTPRequestHandler):
    server: MatchingUiServer

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = INDEX_HTML.replace(
                "__DEFAULT_CANDIDATES__",
                json.dumps(DEFAULT_CANDIDATES, sort_keys=True),
            )
            _send_html(self, html)
            return
        _send_json(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/activity-ranking":
                _send_json(self, 200, self._activity_ranking(_read_json(self)))
                return
            if parsed.path == "/api/circle-matching":
                _send_json(self, 200, self._circle_matching(_read_json(self)))
                return
            _send_json(self, 404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001 - this is a throwaway inspector.
            logger.exception("request failed")
            _send_json(self, 400, {"error": str(exc)})

    def _activity_ranking(self, payload: dict[str, Any]) -> dict[str, Any]:
        with connect(self.server.db_path) as conn:
            residents = ResidentRepository(conn)
            templates = ActivityTemplateRepository(conn)
            matching = MatchingRepository(conn)
            resident = _create_resident(residents, payload)
            engine = MatchingEngine(
                residents=residents,
                templates=templates,
                matching=matching,
            )
            run_id, results = engine.run_matching(
                resident_id=resident.id,
                top_n=int(payload.get("top_n") or 8),
            )
            persisted_count = conn.execute(
                "SELECT COUNT(*) FROM match_candidates WHERE matching_run_id = ?",
                (run_id,),
            ).fetchone()[0]
            return {
                "run_id": run_id,
                "resident_id": resident.id,
                "persisted_candidate_count": persisted_count,
                "results": [
                    {
                        "rank_position": item.candidate.rank_position,
                        "template_code": item.template.code,
                        "template_title": item.template.title,
                        "total_score": round(item.breakdown.total, 6),
                        "cosine": round(item.breakdown.cosine, 6),
                        "cost": round(item.breakdown.cost, 6),
                        "availability": round(item.breakdown.availability, 6),
                        "hard_constraints_passed": item.constraint.passed,
                        "constraint_reasons": list(item.constraint.reasons),
                        "summary_text": item.explanation.summary_text,
                        "top_features": item.explanation.payload.get("top_features", []),
                    }
                    for item in results
                ],
            }

    def _circle_matching(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidates = payload.get("candidates") or []
        if not isinstance(candidates, list):
            raise ValueError("candidates must be a list")
        with connect(self.server.db_path) as conn:
            residents = ResidentRepository(conn)
            templates = ActivityTemplateRepository(conn)
            matching = MatchingRepository(conn)
            activities = ActivityRepository(conn)
            resident_ids = [
                _create_resident(residents, candidate).id
                for candidate in candidates
                if isinstance(candidate, dict)
            ]
            engine = CircleEngine(
                residents=residents,
                templates=templates,
                matching=matching,
                activities=activities,
            )
            result = engine.run_grouping(
                template_code=str(payload.get("template_code") or "photography_walk"),
                resident_ids=resident_ids,
                top_n=int(payload.get("top_n") or 3),
                min_group_size=int(payload.get("min_group_size") or 3),
                max_group_size=int(payload.get("max_group_size") or 4),
            )
            return {
                "run_id": result.matching_run_id,
                "template_code": result.template.code,
                "template_title": result.template.title,
                "groups": [
                    {
                        "rank_position": index,
                        "circle_id": group.circle.id if group.circle else None,
                        "fit_score": round(group.fit_score, 6),
                        "summary_text": group.summary_text,
                        "components": group.payload.get("components", {}),
                        "members": [
                            {
                                "resident_id": member.id,
                                "first_name": member.first_name,
                                "template_score": group.member_template_scores[i],
                            }
                            for i, member in enumerate(group.members)
                        ],
                        "shared_availability": list(group.shared_availability),
                        "shared_interests": list(group.shared_interests),
                    }
                    for index, group in enumerate(result.groups, start=1)
                ],
                "rejected": [
                    {
                        "resident_id": rejected.resident.id,
                        "first_name": rejected.resident.first_name,
                        "reasons": list(rejected.reasons),
                        "summary_text": rejected.summary_text,
                    }
                    for rejected in result.rejected
                ],
            }


@contextlib.contextmanager
def _temporary_db() -> Any:
    temp_dir = Path(tempfile.mkdtemp(prefix="civiccircles-matching-ui-"))
    db_path = temp_dir / "matching-ui.db"
    try:
        init_db(db_path=db_path)
        with connect(db_path) as conn:
            seed_activity_templates(conn=conn)
        yield db_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve throwaway matching inspector UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    configure_logging(args.log_level.upper())
    with _temporary_db() as db_path:
        server = MatchingUiServer((args.host, args.port), db_path)
        logger.info("Serving matching UI at http://%s:%d/", args.host, args.port)
        logger.info("Using temporary DB at %s", db_path)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
