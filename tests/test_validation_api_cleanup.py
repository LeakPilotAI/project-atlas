from app.api.validation import _clean_policy_guard_errors


def test_policy_guard_entries_are_not_reported_as_diagnostic_failures():
    body = {
        "ok": True,
        "section_errors": [
            "redacted phrase guard: go live",
            "marks: timeout",
        ],
    }
    out = _clean_policy_guard_errors(body)
    assert out["section_errors"] == ["marks: timeout"]
    assert out["policy_guard_activations"] == 1
    assert out["diagnostics_healthy"] is False


def test_healthy_report_stays_healthy_after_guard_cleanup():
    body = {
        "ok": True,
        "section_errors": ["redacted phrase guard: go live"],
    }
    out = _clean_policy_guard_errors(body)
    assert out["section_errors"] == []
    assert out["policy_guard_activations"] == 1
    assert out["diagnostics_healthy"] is True
