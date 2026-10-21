from datetime import date

from analysis.scoring import calculate_fit_score, explain_fit_score


def _score(title="", description="", **kw):
    job = {"title": title, "description": description, "location": "", "work_type": ""}
    return calculate_fit_score(job, kw.pop("pos", []), kw.pop("neg", []), **kw)


def test_neutral_base_is_50():
    assert _score("Electrician", "Great team") == 50


def test_citizenship_requirement_zeroes_score():
    assert _score("Developer", "Must be an Australian citizen", pos=["Developer"]) == 0


def test_positive_signal_weighs_double_in_title():
    assert _score("C# Developer", pos=["C#"]) == 66
    assert _score("Developer", "We use C# daily", pos=["C#"]) == 58


def test_negated_positive_signal_does_not_count():
    assert _score("Role", "no sponsorship available", pos=["sponsorship"]) == 50


def test_negative_sponsorship_blocks_sponsor_boost():
    assert _score("Role", "Visa sponsorship is not available") == 50
    assert _score("Role", "Visa sponsorship available") == 70


def test_no_sponsor_penalty_keeps_ranking():
    # O antigo teto de 72 empatava estas duas; a penalidade preserva a ordem
    kw = dict(visa_required=True, no_sponsor_penalty=10)
    strong = _score("React Node.js TypeScript Developer", pos=["React", "Node.js", "TypeScript"], **kw)
    weak   = _score("React Developer", pos=["React", "Node.js", "TypeScript"], **kw)
    assert strong > weak
    assert _score("React Developer", "482 visa available", pos=["React"], **kw) == 86
    assert _score("Role", "Visa sponsorship is not available", **kw) == 35


def test_disqualify_signal_caps_score():
    assert _score("Apprentice", "will train, cert III required",
                  pos=["Apprentice"], disqualify_signals=["cert III"],
                  entry_level_boost=True) == 78      # aprendiz: cert III é o curso
    assert _score("Electrician", "cert III required",
                  pos=["Electrician"], disqualify_signals=["cert III"]) == 35


def test_senior_title_is_excluded():
    kw = dict(pos=[".NET", "Azure"], exclude_senior=True)
    for title in ("Senior Full Stack Developer (.Net/Azure)", "ETL Test Lead",
                  "Integration Architect", "Associate Director, Automation",
                  "Senior Stylist / Visa Sponsorship Available"):
        assert _score(title, **kw) == 0, title
    assert _score("Junior .NET Developer", **kw) > 50
    assert _score("Leading Hand", exclude_senior=True) == 50   # "lead" isolado, não "leading"


def test_qualified_title_capped_unless_entry_role():
    kw = dict(qualified_titles=["driller", "welder", "mechanic"], visa_required=False)
    assert _score("RC Driller and Relief Driller", "FIFO roster", **kw) == 35
    assert _score("First Class Welders", **kw) == 35                     # plural
    assert _score("Heavy Vehicle / Bus Mechanic", "482 visa", **kw) == 35
    assert _score("Drillers Offsider - Entry Level", **kw) == 50
    assert _score("Apprentice Mechanic", **kw) == 50


def test_age_penalty():
    today = date(2026, 10, 20)
    job = lambda d: {"title": "Labourer", "description": "", "listed_at": f"{d}T00:00:00Z"}
    assert calculate_fit_score(job("2026-10-18"), [], [], today=today) == 50
    assert calculate_fit_score(job("2026-10-01"), [], [], today=today) == 45
    assert calculate_fit_score(job("2026-06-01"), [], [], today=today) == 20


def test_only_exclusions_reach_zero():
    assert _score("Role", "salon hairdresser stylist barber",
                  neg=["salon", "hairdresser", "stylist", "barber"]) == 1


def test_ai_fields_feed_the_score():
    base = {"title": "Developer", "description": "", "ai_enriched": 1}
    assert calculate_fit_score({**base, "ai_visa_stance": "citizen_required"}, [], []) == 0
    assert calculate_fit_score({**base, "ai_visa_stance": "positive"}, [], [], visa_required=True) == 70
    assert calculate_fit_score({**base, "ai_seniority": "senior"}, [], [], exclude_senior=True) == 0


def test_explain_items_add_up():
    exp = explain_fit_score({"title": "C# Developer", "description": "hybrid"}, ["C#"], [])
    assert exp["final"] == exp["base"] + sum(i["pts"] for i in exp["items"]) == 71


def test_penalties_apply_after_the_100_cap():
    today = date(2026, 10, 20)
    job = {"title": "Junior C# .NET Azure React Developer", "description": "",
           "listed_at": "2026-05-01"}
    pos = ["junior", "C#", ".NET", "Azure", "React"]                 # 50 + 5×16 = 130
    assert calculate_fit_score(job, pos, [], today=today) == 70     # 100 − 30
    assert calculate_fit_score(job, pos, [], today=today, visa_required=True) == 60


def test_multi_role_title_with_entry_marker_is_kept():
    assert _score("Graduate/ Junior Project Manager", exclude_senior=True) > 0
    assert _score("Electrical Supervisors | Oil & Gas", exclude_senior=True) == 0
