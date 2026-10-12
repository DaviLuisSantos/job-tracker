from analysis.scoring import calculate_fit_score


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


def test_visa_required_caps_unconfirmed_sponsor():
    high = dict(pos=["React", "Node.js", "TypeScript"], visa_required=True, no_sponsor_max=72)
    assert _score("React Node.js TypeScript Developer", **high) == 72
    assert _score("React Node.js TypeScript Developer", "482 visa available", **high) > 72


def test_disqualify_signal_caps_score():
    assert _score("Apprentice", "will train, cert III required",
                  pos=["Apprentice"], disqualify_signals=["cert III"],
                  entry_level_boost=True) == 60
