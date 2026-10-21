from analysis import rescore
from analysis.dedupe import collapse_duplicates


def _job(id_, title, company="Acme", location="Perth WA", score=50):
    return {"id": id_, "source": "seek", "profile": "tech", "title": title,
            "company": company, "location": location, "description": "",
            "work_type": "", "url": "", "listed_at": None, "fit_score": score,
            "salary": None}


def test_rescore_runs_only_when_rules_change(tmp_db, monkeypatch):
    tmp_db.batch_insert_jobs([_job("seek_1", "Lead .NET Developer", score=72)])

    rescore.rescore_if_rules_changed()
    assert tmp_db.fetch_all_jobs()[0]["fit_score"] == 0          # liderança eliminada

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


def test_terms_and_labels_reach_the_job_dict(tmp_db):
    tmp_db.batch_insert_jobs([_job("seek_1", "FIFO Utility")])
    tmp_db.save_job_terms([("seek_1", "working holiday"), ("seek_1", "working holiday")])
    tmp_db.set_job_label("seek_1", "good", "aceita 6 meses")
    job = tmp_db.fetch_all_jobs()[0]
    assert job["fulltext_terms"] == ["working holiday"]
    assert job["label"] == "good"
    tmp_db.set_job_label("seek_1", None)
    assert tmp_db.fetch_all_jobs()[0]["label"] is None


def test_calibration_stats_counts_pairs():
    from analysis.calibrate import calibration_stats
    jobs = [{**_job("1", "A", score=80), "label": "good"},
            {**_job("2", "B", score=40), "label": "bad"},
            {**_job("3", "C", score=90), "status": "rejected"},     # status vira rótulo
            {**_job("4", "D", score=60)}]                            # sem rótulo
    st = calibration_stats(jobs, alert_min=75)["tech"]
    assert (len(st["good"]), len(st["bad"])) == (1, 2)
    assert st["pairs"] == 0.5
    assert st["good_alert"] == 1 and st["bad_visible"] == 1
