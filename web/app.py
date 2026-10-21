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
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Garante que o root do projeto está no sys.path quando rodado diretamente
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, render_template, request, send_file

from config.config import PROFILES
from db.database import (
    fetch_all_jobs,
    fetch_for_review,
    fetch_scrape_runs,
    update_job_notes,
    update_job_status,
)
from analysis.dedupe import collapse_duplicates
from analysis.excel_report import export_excel
from analysis.ai_export import export_for_ai

app = Flask(__name__)

_PYTHON       = sys.executable
_PROJECT_ROOT = Path(__file__).parent.parent
_ANSI_RE      = re.compile(r'\x1b\[[0-9;]*[mGKHF]')


# ── Task runner ───────────────────────────────────────────────────────────────

@dataclass
class _Task:
    id:          str
    action:      str
    status:      str        = "running"   # running | done | error
    logs:        list[str]  = field(default_factory=list)
    error:       str | None = None
    started_at:  float      = field(default_factory=time.time)
    finished_at: float | None = None

_tasks: dict[str, _Task] = {}
_tasks_lock = threading.Lock()


def _build_cmd(action: str, profile: str | None,
               full_desc: bool, min_score: int) -> list[str]:
    cmd = [_PYTHON, str(_PROJECT_ROOT / "main.py")]
    if action == "scrape":
        cmd.append("--scrape")
        if full_desc:
            cmd.append("--full-desc")
    elif action == "enrich":
        cmd.append("--enrich")
        if min_score:
            cmd += ["--min-score", str(min_score)]
    elif action == "ai_enrich":
        cmd.append("--ai-enrich")
        if min_score:
            cmd += ["--min-score", str(min_score)]
    elif action == "rescore":
        cmd.append("--rescore")
    if profile:
        cmd += ["--profile", profile]
    return cmd


def _run_background(task: _Task, cmd: list[str]) -> None:
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "NO_COLOR": "1",        # desativa ANSI no Rich
        "PYTHONUNBUFFERED": "1",
    }
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(_PROJECT_ROOT),
            env=env,
        )
        for raw in proc.stdout:
            line = _ANSI_RE.sub("", raw).rstrip()
            if line:
                with _tasks_lock:
                    task.logs.append(line)
        proc.wait()
        with _tasks_lock:
            task.status    = "done" if proc.returncode == 0 else "error"
            task.finished_at = time.time()
            if proc.returncode != 0:
                task.error = f"Processo terminou com código {proc.returncode}"
    except Exception as exc:
        with _tasks_lock:
            task.error       = str(exc)
            task.status      = "error"
            task.finished_at = time.time()

_STATUSES = ("new", "reviewed", "applied", "rejected", "interview")


@app.context_processor
def _inject_globals():
    """Injeta variáveis disponíveis em todos os templates."""
    return {"profile_names": list(PROFILES.keys())}

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
    jobs  = [j for j in fetch_all_jobs() if (j.get("fit_score") or 0) > 0]
    runs  = fetch_scrape_runs(limit=6)
    stats = _stats(jobs)

    # Breakdown por perfil
    by_profile = {
        p: _stats([j for j in jobs if j.get("profile") == p])
        for p in PROFILES
        if any(j.get("profile") == p for j in jobs)
    }

    # Top vagas novas com score ≥ 70
    top_jobs = collapse_duplicates(sorted(
        [j for j in jobs if (j.get("fit_score") or 0) >= 70 and j.get("status") == "new"],
        key=lambda j: (j.get("fit_score") or 0, j.get("listed_at") or ""),
        reverse=True,
    ))[:10]

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
    location  = request.args.get("location", "")
    min_score = int(request.args.get("min_score") or 0)

    all_jobs = [j for j in fetch_all_jobs(profile or None) if (j.get("fit_score") or 0) > 0]

    # Localizações únicas para o dropdown (antes de filtrar)
    locations = sorted({j["location"] for j in all_jobs if j.get("location")})

    jobs = all_jobs
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    if location:
        loc_lower = location.lower()
        jobs = [j for j in jobs if loc_lower in (j.get("location") or "").lower()]
    if min_score:
        jobs = [j for j in jobs if (j.get("fit_score") or 0) >= min_score]
    jobs = collapse_duplicates(jobs)

    return render_template("jobs.html",
        jobs=jobs,
        jobs_json=_safe_jobs_json(jobs),
        profiles=list(PROFILES.keys()),
        statuses=_STATUSES,
        locations=locations,
        selected_profile=profile,
        selected_status=status,
        selected_location=location,
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


# ── Run API ───────────────────────────────────────────────────────────────────

@app.route("/api/run", methods=["POST"])
def api_run_start():
    """Inicia uma tarefa em background e retorna o task_id."""
    data      = request.get_json() or {}
    action    = data.get("action", "scrape")
    profile   = data.get("profile") or None
    full_desc = bool(data.get("full_desc", False))
    min_score = int(data.get("min_score") or 0)

    if action not in ("scrape", "enrich", "ai_enrich", "rescore"):
        return jsonify({"error": "ação inválida"}), 400
    if profile and profile not in PROFILES:
        return jsonify({"error": f"perfil '{profile}' não existe"}), 400

    task = _Task(id=uuid.uuid4().hex, action=action)
    with _tasks_lock:
        _tasks[task.id] = task

    cmd = _build_cmd(action, profile, full_desc, min_score)
    threading.Thread(target=_run_background, args=(task, cmd), daemon=True).start()

    return jsonify({"task_id": task.id})


@app.route("/api/run/<task_id>")
def api_run_status(task_id: str):
    """Retorna status + linhas de log (a partir do índice `from`)."""
    task = _tasks.get(task_id)
    if not task:
        return jsonify({"error": "não encontrado"}), 404

    from_idx = int(request.args.get("from") or 0)
    with _tasks_lock:
        lines  = task.logs[from_idx:]
        status = task.status
        error  = task.error

    return jsonify({
        "status":      status,
        "lines":       lines,
        "total_lines": from_idx + len(lines),
        "error":       error,
    })


# ── Score explain ─────────────────────────────────────────────────────────────

def _explain_score(job: dict) -> dict:
    from analysis.scoring import explain_job
    return {
        **explain_job(job),
        "ai_enriched":    bool(job.get("ai_enriched")),
        "ai_visa_stance": job.get("ai_visa_stance"),
        "ai_seniority":   job.get("ai_seniority"),
    }


@app.route("/api/job/<job_id>/explain")
def api_explain(job_id: str):
    all_jobs = fetch_all_jobs()
    job = next((j for j in all_jobs if j["id"] == job_id), None)
    if not job:
        return jsonify({"error": "não encontrado"}), 404
    return jsonify(_explain_score(job))


# ── Export / Download ─────────────────────────────────────────────────────────

@app.route("/api/export/excel")
def api_export_excel():
    profile = request.args.get("profile") or None
    path = export_excel(profile)
    if not path:
        return jsonify({"error": "Nenhuma vaga elegível para exportar."}), 404
    return send_file(str(path), as_attachment=True, download_name=path.name)


@app.route("/api/export/ai")
def api_export_ai():
    profile   = request.args.get("profile") or None
    min_score = int(request.args.get("min_score") or 0)
    path = export_for_ai(profile, min_score=min_score)
    if not path:
        return jsonify({"error": "Nenhuma vaga para exportar."}), 404
    return send_file(str(path), as_attachment=True, download_name=path.name)


# ── Review page ───────────────────────────────────────────────────────────────

@app.route("/review")
def review_page():
    profile   = request.args.get("profile", "")
    min_score = int(request.args.get("min_score") or 0)
    jobs = fetch_for_review(profile or None, min_score=min_score, limit=200)
    return render_template("review.html",
        jobs=jobs,
        jobs_json=_safe_jobs_json(jobs),
        profiles=list(PROFILES.keys()),
        selected_profile=profile,
        min_score=min_score,
    )


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
