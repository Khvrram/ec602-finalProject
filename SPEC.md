# Initial project specification

The first version has three jobs:

1. Read a syllabus PDF or text file. Use local OCR if a PDF page has no text layer.
2. Find dates and keep their surrounding text and page number.
3. Save the results as a JSON list for later review.

Support English month-name dates (`November 19, 2026`), ISO dates
(`2026-11-19`), and slash dates (`11/19/2026`). An optional semester year fills
in missing years. Flag ambiguous dates, invalid dates, and two-digit years
instead of guessing. OCR results also need review. Ignore labeled page counters.

Use one Python script with ordinary functions, lists, and dictionaries. Save
with Python's JSON library; running again replaces the output file. Keep three
basic tests for date detection, uncertain dates, and saving the results.

For now, these are date mentions, including class meetings and holidays.
Deadline filtering, a review screen, and calendar export come later.
