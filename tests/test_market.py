import analysis.market_report as market_report
from scrapers.seek_market import assess_snapshot

# ── Validação do retrato ──────────────────────────────────────────────────────

PREV = {("HVAC-R", "Perth WA"): 70}


def test_snapshot_ok_when_complete_and_stable():
    counts = [("HVAC-R", "Perth WA", "", 72), ("HVAC-R", "Perth WA", "482", 1)]
    assert assess_snapshot(counts, PREV, []) == ("ok", [])


def test_snapshot_partial_when_a_count_failed():
    counts = [("HVAC-R", "Perth WA", "", 72), ("HVAC-R", "Perth WA", "482", None)]
    status, issues = assess_snapshot(counts, PREV, [])
    assert status == "partial" and "482" in issues[0]


def test_snapshot_partial_when_listing_incomplete():
    status, _ = assess_snapshot([("HVAC-R", "Perth WA", "", 72)], PREV, [("HVAC-R", "Perth WA")])
    assert status == "partial"


def test_snapshot_suspect_when_total_drops_to_zero():
    status, _ = assess_snapshot([("HVAC-R", "Perth WA", "", 0)], PREV, [])
    assert status == "suspect"


def test_snapshot_suspect_on_sudden_swing():
    assert assess_snapshot([("HVAC-R", "Perth WA", "", 20)], PREV, [])[0] == "suspect"
    assert assess_snapshot([("HVAC-R", "Perth WA", "", 150)], PREV, [])[0] == "suspect"


def test_snapshot_small_bases_tolerate_swings():
    prev = {("Dev", "Darwin NT"): 4}
    assert assess_snapshot([("Dev", "Darwin NT", "", 9)], prev, [])[0] == "ok"


def test_first_snapshot_has_no_baseline():
    assert assess_snapshot([("HVAC-R", "Perth WA", "", 72)], {}, [])[0] == "ok"


# ── Relatório mensal ──────────────────────────────────────────────────────────

def _seed(db):
    for day, total, sponsor, status in [
        ("2026-09-15", 50, 1, "ok"),
        ("2026-10-01", 70, 2, "ok"),
        ("2026-10-02", 74, 2, "ok"),
        ("2026-10-03", 0,  0, "suspect"),   # deve ficar fora da média
    ]:
        db.save_market_counts(day, [("HVAC-R", "Perth WA", "", total),
                                    ("HVAC-R", "Perth WA", "sponsorship", sponsor)])
        db.save_market_run(day, status, 2, 2, 0, [] if status == "ok" else ["zerou"])

    base = dict(city="Perth WA", category="HVAC-R", location="Perth", work_type="Full time",
                listed_at="2026-10-01T00:00:00Z")
    db.upsert_market_listings("2026-10-01", [
        {**base, "id": "seek_1", "title": "HVAC Tech", "company": "Acme", "salary": "$100,000 - $120,000"},
        {**base, "id": "seek_2", "title": "HVAC  tech", "company": "ACME", "salary": "$100,000 - $120,000"},
        {**base, "id": "seek_3", "title": "Fridgie", "company": None, "salary": "$60 per hour"},
        {**base, "id": "seek_4", "title": "Apprentice", "company": "Cool Co", "salary": None,
         "listed_at": "2026-09-20T00:00:00Z"},
    ])


def test_monthly_report_aggregates_only_valid_snapshots(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(market_report, "OUTPUT_DIR", tmp_path)
    _seed(tmp_db)

    md = market_report.build_market_report("2026-10").read_text(encoding="utf-8")

    assert "Média de 2 retrato(s)" in md and "1 descartado(s)" in md
    assert "Vagas abertas (média diária):** 72 (+44% vs. mês anterior)" in md
    assert 'citam "sponsorship": 2 (2.8%)' in md
    assert "4 → 3 únicos (1 repetidos)" in md          # seek_1 e seek_2 são o mesmo anúncio
    assert "Publicados no mês: 2" in md                  # seek_4 é de setembro
    # medianas: (100k+120k)/2 = 110k e $60/h × 2080 = 124,8k → mediana 117k
    assert "mediana $117k" in md
    assert "Acme" not in md and "HVAC Tech" not in md    # nunca publica vaga individual


def test_monthly_report_without_valid_snapshots_returns_none(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(market_report, "OUTPUT_DIR", tmp_path)
    assert market_report.build_market_report("2026-10") is None
