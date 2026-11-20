"""Three basic checks for this first version."""

import json
from pathlib import Path

from syllabus_calendar import find_dates, read_file, save_dates


def test_common_dates(tmp_path: Path) -> None:
    source = tmp_path / "syllabus.txt"
    source.write_text(
        "Homework: November 19, 2026\nReport: 2026-12-10\n"
        "Quiz: 11/20\nFinal: Dec 15, 3:00 pm", encoding="utf-8",
    )
    dates = find_dates(read_file(source), year=2026)
    assert [item["date"] for item in dates] == [
        "2026-11-19", "2026-12-10", "2026-11-20", "2026-12-15",
    ]
    assert all(item["page"] == 1 for item in dates)
    assert "Homework" in dates[0]["context"]


def test_uncertain_dates() -> None:
    pages = [{"text": "03/04/2026\nFebruary 30, 2026\n11/19/26\nNovember 19", "ocr": False}]
    dates = find_dates(pages)
    assert len(dates) == 4
    assert all(item["date"] is None and item["needs_review"] for item in dates)


def test_save_results(tmp_path: Path) -> None:
    pages = [{"text": "Exam: 2026-11-19\nhttps://example.edu  1/1", "ocr": True}]
    dates = find_dates(pages)
    assert len(dates) == 1  # The page counter is not a date.
    assert dates[0]["needs_review"]  # OCR text should be checked.
    output = tmp_path / "dates.json"
    save_dates(dates, output)
    save_dates(dates, output)
    assert json.loads(output.read_text(encoding="utf-8")) == dates
