# Syllabus to Calendar

One Python script that reads a PDF/text file, finds dates, and saves them as JSON.
The PDF reader uses local OCR when the file has no text layer, as with the
provided EC602 PDF.

## Run

With Python 3.14 and `uv` installed, run from this folder:

```powershell
uv sync
uv run python syllabus_calendar.py ec602_syl.pdf --year 2026
```

Results go into `dates.json`. Use `--output other.json` to change the filename.
Each entry has the matched text, date, page, context, and a review note. Running
again replaces the file. Ambiguous/invalid dates stay unresolved; OCR results
are marked for review. These are date mentions, including class meetings and
holidays. Filtering deadlines and exporting a calendar will come later.

## Basic checks

```powershell
uv run pytest -q
uv run ty check syllabus_calendar.py test_syllabus_calendar.py
```

There are three tests: common date formats, uncertain dates, and saving results.
`SPEC.md` holds the short contract; `pyproject.toml` makes the script installable.

AI use: Codex helped draft and simplify the script. Date extraction and saving
are checked with the tests and the provided PDF. An initial assumption that
the PDF had selectable text was wrong; inspecting empty extraction results
showed that local OCR was needed. The application itself does not use an LLM.
