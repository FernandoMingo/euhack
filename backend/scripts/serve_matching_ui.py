"""Throwaway localhost UI for inspecting the matching engine.

Pure stdlib (`http.server` + `json`). Boots a fresh SQLite database in a
temp directory, seeds the activity catalog, and exposes:

* ``GET  /``            -> single-page HTML form
* ``POST /api/match``   -> JSON in / JSON out, runs the engine for the
                            submitted profile and returns the top N

The whole server tears down with Ctrl+C; the temp DB is removed on exit
so nothing pollutes ``backend/civiccircles.db`` (and ratings / referrals
/ resident profiles created during play are forgotten).

Usage::

    python3 backend/scripts/serve_matching_ui.py
    # then visit http://127.0.0.1:8765/

This script is intentionally not wired into production; it's a quick
inspector for development.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import (  # noqa: E402
    ActivityTemplateRepository,
    MatchingEngine,
    MatchingRepository,
    ResidentRepository,
    configure_logging,
    connect,
    init_db,
)
from app.seed import seed_activity_templates  # noqa: E402

logger = logging.getLogger("matching_ui")

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CivicCircles Matching Inspector</title>
<style>
  :root {
    --bg: #f4f6fb;
    --card: #ffffff;
    --text: #1f2937;
    --muted: #6b7280;
    --accent: #2f6df6;
    --accent-soft: #e7eefe;
    --border: #e5e7eb;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 Ubuntu, sans-serif;
    background: var(--bg);
    color: var(--text);
  }
  header {
    background: white;
    border-bottom: 1px solid var(--border);
    padding: 20px 32px;
  }
  header h1 { margin: 0; font-size: 20px; font-weight: 600; }
  header p { margin: 4px 0 0; color: var(--muted); font-size: 14px; }
  main {
    max-width: 1100px;
    margin: 24px auto;
    padding: 0 24px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }
  @media (max-width: 880px) { main { grid-template-columns: 1fr; } }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }
  .card h2 { margin: 0 0 16px; font-size: 16px; font-weight: 600; }
  label { display: block; font-size: 13px; color: var(--muted); margin: 12px 0 4px; }
  input[type=text], input[type=number], textarea, select {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 14px;
    font-family: inherit;
    background: white;
  }
  textarea { min-height: 56px; resize: vertical; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .availability { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
  .availability label { font-size: 12px; display: flex; align-items: center; gap: 4px; margin: 0; color: var(--text); }
  button {
    margin-top: 20px;
    padding: 10px 16px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    width: 100%;
  }
  button:hover { background: #1f57d5; }
  button:disabled { background: #9aa3b2; cursor: not-allowed; }
  .result {
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 10px;
    background: white;
  }
  .result.top { border-color: var(--accent); background: var(--accent-soft); }
  .result h3 { margin: 0 0 4px; font-size: 15px; }
  .result .meta { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .result .summary { font-size: 13px; line-height: 1.4; }
  .result .features { margin-top: 8px; font-size: 12px; color: var(--muted); }
  .result .features span { display: inline-block; background: #f3f4f6; padding: 2px 6px; border-radius: 4px; margin-right: 4px; margin-bottom: 4px; }
  .empty { color: var(--muted); font-size: 13px; }
  .error { color: #b91c1c; font-size: 13px; margin-top: 8px; }
  .stats { font-size: 12px; color: var(--muted); margin-bottom: 12px; }
  small.help { display: block; font-size: 11px; color: var(--muted); margin-top: 4px; }
</style>
</head>
<body>
<header>
  <h1>CivicCircles matching inspector</h1>
  <p>Throwaway local UI &middot; deterministic engine v1 &middot; cosine + soft signals</p>
</header>
<main>
  <section class="card">
    <h2>Resident profile</h2>
    <form id="match-form">
      <label for="first_name">First name</label>
      <input id="first_name" type="text" value="Sofia" required>

      <label for="interests">Interests (comma separated)</label>
      <textarea id="interests" placeholder="photography, nature, outdoor">photography, nature, outdoor</textarea>
      <small class="help">Maps to feature key <code>interest:&lt;value&gt;</code> (weight 1.0).</small>

      <label for="activity_prefs">Wanted activity types (comma separated, optional)</label>
      <textarea id="activity_prefs" placeholder="photography_walk, slow_park_walk">photography_walk</textarea>
      <small class="help">Maps to <code>activity_pref:&lt;code&gt;</code> &mdash; use a template code for a direct match.</small>

      <label for="avoidances">Avoidances (comma separated, optional)</label>
      <textarea id="avoidances" placeholder="pubs_social, loud_music"></textarea>
      <small class="help">Hard constraint: any activity whose family/code/tag matches gets rejected.</small>

      <label for="accessibility">Accessibility needs (comma separated, optional)</label>
      <textarea id="accessibility" placeholder="step_free"></textarea>

      <div class="row">
        <div>
          <label for="group_min">Group size min</label>
          <input id="group_min" type="number" min="1" max="50" value="3">
        </div>
        <div>
          <label for="group_max">Group size max</label>
          <input id="group_max" type="number" min="1" max="50" value="6">
        </div>
      </div>

      <div class="row">
        <div>
          <label for="social_comfort">Social comfort</label>
          <select id="social_comfort">
            <option value="small_group_low_pressure" selected>small_group_low_pressure</option>
            <option value="moderate_social">moderate_social</option>
            <option value="high_energy">high_energy</option>
          </select>
        </div>
        <div>
          <label for="cost_sensitivity">Cost sensitivity</label>
          <select id="cost_sensitivity">
            <option value="free_only">free_only</option>
            <option value="free_or_low_cost" selected>free_or_low_cost</option>
            <option value="moderate_cost_ok">moderate_cost_ok</option>
            <option value="any_cost">any_cost</option>
          </select>
        </div>
      </div>

      <label>Availability</label>
      <div class="availability" id="availability">
        <!-- populated by JS -->
      </div>

      <label for="top_n">Top N</label>
      <input id="top_n" type="number" min="1" max="20" value="5">

      <button id="submit" type="submit">Run matching</button>
      <div class="error" id="error"></div>
    </form>
  </section>
  <section class="card">
    <h2>Top matches</h2>
    <div class="stats" id="stats"></div>
    <div id="results"><div class="empty">Submit the form to see ranked activity templates.</div></div>
  </section>
</main>
<script>
const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const BUCKETS = ["morning", "afternoon", "evening"];
const availDiv = document.getElementById("availability");
WEEKDAYS.forEach((day) => {
  BUCKETS.forEach((bucket) => {
    const id = `avail_${day}_${bucket}`;
    const wrap = document.createElement("label");
    wrap.innerHTML = `<input type="checkbox" id="${id}" data-day="${day}" data-bucket="${bucket}"> ${day}.${bucket.slice(0,3)}`;
    availDiv.appendChild(wrap);
  });
});
document.getElementById("avail_sat_morning").checked = true;

function splitList(value) {
  return value.split(",").map((s) => s.trim()).filter((s) => s.length > 0);
}

function bucketToWindow(bucket) {
  return {
    morning: ["09:00", "12:00"],
    afternoon: ["13:00", "17:00"],
    evening: ["18:00", "21:00"],
  }[bucket];
}

document.getElementById("match-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = document.getElementById("submit");
  const errorEl = document.getElementById("error");
  const resultsEl = document.getElementById("results");
  const statsEl = document.getElementById("stats");
  submit.disabled = true;
  errorEl.textContent = "";
  resultsEl.innerHTML = '<div class="empty">Running...</div>';
  statsEl.textContent = "";

  const availability = [];
  document.querySelectorAll("#availability input:checked").forEach((cb) => {
    const [start, end] = bucketToWindow(cb.dataset.bucket);
    availability.push({ weekday: cb.dataset.day, start_time_local: start, end_time_local: end });
  });

  const payload = {
    first_name: document.getElementById("first_name").value.trim() || "Resident",
    interests: splitList(document.getElementById("interests").value),
    activity_prefs: splitList(document.getElementById("activity_prefs").value),
    avoidances: splitList(document.getElementById("avoidances").value),
    accessibility_needs: splitList(document.getElementById("accessibility").value),
    group_size_min: parseInt(document.getElementById("group_min").value, 10),
    group_size_max: parseInt(document.getElementById("group_max").value, 10),
    social_comfort: document.getElementById("social_comfort").value,
    cost_sensitivity: document.getElementById("cost_sensitivity").value,
    availability,
    top_n: parseInt(document.getElementById("top_n").value, 10),
  };

  try {
    const response = await fetch("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    statsEl.textContent = `Run ${data.run_id || "(empty)"} \u00b7 ${data.results.length} top candidates \u00b7 ${data.totals.passed} passed / ${data.totals.rejected} rejected of ${data.totals.scored} templates`;
    if (!data.results.length) {
      resultsEl.innerHTML = '<div class="empty">No candidates passed the hard constraints.</div>';
    } else {
      resultsEl.innerHTML = data.results.map((r, i) => `
        <div class="result${i === 0 ? " top" : ""}">
          <h3>#${r.rank} ${escapeHtml(r.title)}</h3>
          <div class="meta">code <code>${escapeHtml(r.code)}</code> &middot; family ${escapeHtml(r.family)} &middot; total ${r.total.toFixed(3)} &middot; cosine ${r.cosine.toFixed(3)} &middot; cost ${r.cost.toFixed(2)} &middot; availability ${r.availability.toFixed(2)}</div>
          <div class="summary">${escapeHtml(r.summary)}</div>
          <div class="features">${r.top_features.map((f) => `<span title="contribution ${f.contribution.toFixed(3)}">${escapeHtml(f.feature_key)}</span>`).join("")}</div>
        </div>
      `).join("");
    }
  } catch (err) {
    errorEl.textContent = err.message || String(err);
    resultsEl.innerHTML = '<div class="empty">No results.</div>';
  } finally {
    submit.disabled = false;
  }
});

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[c]));
}
</script>
</body>
</html>
"""


class MatchingServiceState:
    """One-shot setup: temp DB, seeded catalog, repos ready to use."""

    def __init__(self) -> None:
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="civiccircles_ui_"))
        self.db_path = self._tmp_dir / "ui.db"
        self._lock = threading.Lock()
        self._counter = 0
        init_db(db_path=self.db_path)
        with connect(db_path=self.db_path) as conn:
            seed_activity_templates(conn=conn)
        logger.info("UI state ready db_path=%s", self.db_path)

    def cleanup(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(self._tmp_dir)

    def next_email_suffix(self) -> int:
        with self._lock:
            self._counter += 1
            return self._counter

    def run_match(self, payload: dict[str, Any]) -> dict[str, Any]:
        first_name = str(payload.get("first_name") or "Resident").strip() or "Resident"
        interests = [str(v).strip() for v in (payload.get("interests") or []) if str(v).strip()]
        activity_prefs = [str(v).strip() for v in (payload.get("activity_prefs") or []) if str(v).strip()]
        avoidances = [str(v).strip() for v in (payload.get("avoidances") or []) if str(v).strip()]
        accessibility_needs = [
            str(v).strip() for v in (payload.get("accessibility_needs") or []) if str(v).strip()
        ]
        group_min = int(payload.get("group_size_min") or 2)
        group_max = int(payload.get("group_size_max") or max(group_min, 6))
        group_min = max(1, group_min)
        group_max = max(group_min, group_max)
        social_comfort = str(payload.get("social_comfort") or "small_group_low_pressure").strip()
        cost_sensitivity = str(payload.get("cost_sensitivity") or "free_or_low_cost").strip()
        availability = payload.get("availability") or []
        top_n = max(1, min(20, int(payload.get("top_n") or 5)))

        suffix = self.next_email_suffix()
        with connect(db_path=self.db_path) as conn:
            residents = ResidentRepository(conn)
            templates = ActivityTemplateRepository(conn)
            matching = MatchingRepository(conn)
            engine = MatchingEngine(
                residents=residents, templates=templates, matching=matching
            )

            resident = residents.create_resident(
                first_name=first_name,
                email=f"ui-{suffix}@local",
                preferred_language="English",
                city="Local",
                social_comfort=social_comfort,
                preferred_group_size_min=group_min,
                preferred_group_size_max=group_max,
                cost_sensitivity=cost_sensitivity,
            )
            for value in interests:
                residents.add_preference(
                    resident_id=resident.id, preference_type="interest", value=value
                )
            for value in activity_prefs:
                residents.add_preference(
                    resident_id=resident.id, preference_type="activity", value=value
                )
            for value in accessibility_needs:
                residents.add_preference(
                    resident_id=resident.id,
                    preference_type="accessibility_need",
                    value=value,
                )
            for value in avoidances:
                residents.add_avoidance(resident_id=resident.id, value=value)
            for slot in availability:
                if not isinstance(slot, dict):
                    continue
                weekday = str(slot.get("weekday") or "").strip().lower()
                start = str(slot.get("start_time_local") or "").strip()
                end = str(slot.get("end_time_local") or "").strip()
                if weekday and start and end:
                    residents.add_availability(
                        resident_id=resident.id,
                        weekday=weekday,
                        start_time_local=start,
                        end_time_local=end,
                    )
            conn.commit()

            run_id, results = engine.run_matching(resident_id=resident.id, top_n=top_n)

            passed_total = conn.execute(
                """
                SELECT COUNT(*) FROM match_candidates
                WHERE matching_run_id = ? AND hard_constraints_passed = 1
                """,
                (run_id,),
            ).fetchone()[0]
            rejected_total = conn.execute(
                """
                SELECT COUNT(*) FROM match_candidates
                WHERE matching_run_id = ? AND hard_constraints_passed = 0
                """,
                (run_id,),
            ).fetchone()[0]

        return {
            "run_id": run_id,
            "totals": {
                "scored": passed_total + rejected_total,
                "passed": passed_total,
                "rejected": rejected_total,
            },
            "results": [
                {
                    "rank": r.candidate.rank_position,
                    "code": r.template.code,
                    "title": r.template.title,
                    "family": r.template.family,
                    "total": r.breakdown.total,
                    "cosine": r.breakdown.cosine,
                    "cost": r.breakdown.cost,
                    "availability": r.breakdown.availability,
                    "summary": r.explanation.summary_text,
                    "top_features": r.explanation.payload.get("top_features", []),
                }
                for r in results
            ],
        }


def _build_handler(state: MatchingServiceState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "CivicCirclesUI/1.0"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            logger.info("%s - %s", self.client_address[0], format % args)

        def _write(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _write_json(self, status: int, data: dict[str, Any]) -> None:
            self._write(status, json.dumps(data).encode("utf-8"), "application/json")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._write(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/healthz":
                self._write_json(200, {"status": "ok"})
                return
            self._write_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path != "/api/match":
                self._write_json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self._write_json(400, {"error": f"bad json: {exc}"})
                return
            try:
                result = state.run_match(payload)
            except ValueError as exc:
                self._write_json(400, {"error": str(exc)})
                return
            except Exception as exc:  # pragma: no cover - dev tool
                logger.exception("matching run failed")
                self._write_json(500, {"error": f"engine error: {exc}"})
                return
            self._write_json(200, result)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Throwaway localhost UI for the matching engine.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765).")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    args = parser.parse_args()

    configure_logging(args.log_level)

    state = MatchingServiceState()
    handler = _build_handler(state)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"CivicCircles matching inspector listening on {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        logger.info("shutting down")
    finally:
        server.server_close()
        state.cleanup()


if __name__ == "__main__":
    main()
