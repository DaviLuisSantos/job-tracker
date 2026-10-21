from analysis import rescore
from analysis.dedupe import collapse_duplicates


def _job(id_, title, company="Acme", location="Perth WA", score=50):
    return {"id": id_, "source": "seek", "profile": "tech", "title": title,
            "company": company, "location": location, "description": "",
            "work_type": "", "url": "", "listed_at": None, "fit_score": score,
            "salary": None}


def test_rescore_runs_only_when_rules_change(tmp_db, monkeypatch):
    tmp_db.batch_insert_jobs([_job("seek_1", "Senior .NET Developer", score=72)])

    rescore.rescore_if_rules_changed()
    assert tmp_db.fetch_all_jobs()[0]["fit_score"] == 0          # sênior eliminado

    tmp_db.update_job_score("seek_1", 99)
    rescore.rescore_if_rules_changed()                            # mesmas regras: não mexe
    assert tmp_db.fetch_all_jobs()[0]["fit_score"] == 99

    monkeypatch.setattr(rescore, "rules_fingerprint", lambda: "outras-regras")
    rescore.rescore_if_rules_changed()
    assert tmp_db.fetch_all_jobs()[0]["fit_score"] == 0


def test_collapse_duplicates_keeps_first_and_counts():
    jobs = [_job("1", "Labourer", location="Perth WA", score=80),
            _job("2", "Labourer", location="Darwin NT", score=70),
            _job("3", "labourer ", location="Brisbane QLD", score=60),
            _job("4", "Labourer", company=None, score=60),
            _job("5", "Labourer", company=None, score=50)]
    out = collapse_duplicates(jobs)
    assert [j["id"] for j in out] == ["1", "4", "5"]
    assert out[0]["dup_count"] == 3
    assert out[0]["location_label"] == "Perth WA (+2 locais)"


def test_collapse_duplicates_accepts_pandas_nan():
    nan = float("nan")
    out = collapse_duplicates([_job("1", "Labourer", company=nan, location=nan)])
    assert out[0]["location_label"] == "—"
