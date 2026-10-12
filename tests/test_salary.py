import pytest

from analysis.salary import parse_salary


@pytest.mark.parametrize("text, period, annual_min, annual_max", [
    ("$50 - $65 per hour",       "hour", 104_000, 135_200),
    ("$100,000 – $120,000 pa",   "year", 100_000, 120_000),
    ("$165k - $175k + Super",    "year", 165_000, 175_000),
    ("$950 per day + super",     "day",  247_000, 247_000),
])
def test_parse_salary_annualizes(text, period, annual_min, annual_max):
    sal = parse_salary(text)
    assert sal["salary_period"] == period
    assert sal["salary_annual_min"] == annual_min
    assert sal["salary_annual_max"] == annual_max


@pytest.mark.parametrize("text", [None, "", "—", "Excellent salary", "$5 per hour"])
def test_parse_salary_rejects_missing_or_implausible(text):
    assert parse_salary(text)["salary_annual_min"] is None
