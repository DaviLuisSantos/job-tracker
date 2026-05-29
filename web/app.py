"""
Interface web do Job Tracker.

Rotas:
  GET  /              → Dashboard com KPIs e gráficos
  GET  /jobs          → Tabela completa com filtros
  POST /api/job/<id>/status  → Atualiza status (AJAX)
  POST /api/job/<id>/notes   → Atualiza anotações (AJAX)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Garante que o root do projeto está no sys.path quando rodado diretamente
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, render_template, request

from config.config import PROFILES
from db.database import (
    fetch_all_jobs,
    fetch_scrape_runs,
    update_job_notes,
    update_job_status,
)

app = Flask(__name__)

_STATUSES = ("new", "reviewed", "applied", "rejected", "interview")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _stats(jobs: list[dict]) -> dict:
    if not jobs:
        return dict(total=0, new=0, high_fit=0, applied=0, avg_score=0, max_score=0)
    scores = [j.get("fit_score") or 0 for j in jobs]
    return dict(
        total     = len(jobs),
        new       = sum(1 for j in jobs if j.get("status") == "new"),
        high_fit  = sum(1 for j in jobs if (j.get("fit_score") or 0) >= 70),
        applied   = sum(1 for j in jobs if j.get("applied")),
        avg_score = round(sum(scores) / len(scores), 1),
        max_score = max(scores),
    )


def _safe_jobs_json(jobs: list[dict]) -> str:
    """Serializa jobs para JSON eliminando NaN/None → string vazia."""
    clean = []
    for j in jobs:
        clean.append({k: (v if v is not None else "") for k, v in j.items()})
    return json.dumps(clean, default=str)


# ── Rotas ─────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    jobs  = fetch_all_jobs()
    runs  = fetch_scrape_runs(limit=6)
    stats = _stats(jobs)

    # Breakdown por perfil
    by_profile = {
        p: _stats([j for j in jobs if j.get("profile") == p])
        for p in PROFILES
        if any(j.get("profile") == p for j in jobs)
    }

    # Top vagas novas com score ≥ 70
    top_jobs = sorted(
        [j for j in jobs if (j.get("fit_score") or 0) >= 70 and j.get("status") == "new"],
        key=lambda j: j.get("fit_score") or 0,
        reverse=True,
    )[:10]

    # Distribuição de scores em 5 faixas
    buckets = [0, 0, 0, 0, 0]
    for j in jobs:
        s = j.get("fit_score") or 0
        if   s < 50: buckets[0] += 1
        elif s < 60: buckets[1] += 1
        elif s < 70: buckets[2] += 1
        elif s < 80: buckets[3] += 1
        else:        buckets[4] += 1

    return render_template("index.html",
        stats=stats, by_profile=by_profile, top_jobs=top_jobs,
        runs=runs, score_buckets=json.dumps(buckets),
    )


@app.route("/jobs")
def jobs_page():
    profile   = request.args.get("profile", "")
    status    = request.args.get("status", "")
    min_score = int(request.args.get("min_score") or 0)

    jobs = fetch_all_jobs(profile or None)
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    if min_score:
        jobs = [j for j in jobs if (j.get("fit_score") or 0) >= min_score]

    return render_template("jobs.html",
        jobs=jobs,
        jobs_json=_safe_jobs_json(jobs),
        profiles=list(PROFILES.keys()),
        statuses=_STATUSES,
        selected_profile=profile,
        selected_status=status,
        min_score=min_score,
    )


# ── API JSON ──────────────────────────────────────────────────────────────────

@app.route("/api/job/<job_id>/status", methods=["POST"])
def api_status(job_id: str):
    data   = request.get_json() or {}
    status = data.get("status", "")
    if status not in _STATUSES:
        return jsonify({"error": "invalid status"}), 400
    update_job_status(job_id, status, applied=(status == "applied"))
    return jsonify({"ok": True})


@app.route("/api/job/<job_id>/notes", methods=["POST"])
def api_notes(job_id: str):
    data = request.get_json() or {}
    update_job_notes(job_id, data.get("notes", ""))
    return jsonify({"ok": True})


# ── Entry point ───────────────────────────────────────────────────────────────

def start(port: int = 5000, open_browser: bool = True):
    if open_browser:
        import threading
        import time
        import webbrowser

        def _open():
            time.sleep(0.9)
            webbrowser.open(f"http://localhost:{port}")

        threading.Thread(target=_open, daemon=True).start()

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
