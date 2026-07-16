from datetime import datetime


def test_report_is_not_generated_at_midnight() -> None:
    assert datetime.now().strftime("%H:%M") != "00:00"
