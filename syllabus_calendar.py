"""Read a syllabus, find dates, and save them as JSON."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from statistics import median

import pypdfium2 as pdfium
from pypdf import PdfReader
from rapidocr import RapidOCR
from rapidocr.utils.output import RapidOCROutput

MONTHS = "January February March April May June July August September October November December".split()
MONTH_NAMES = "|".join(MONTHS + [month[:3] for month in MONTHS] + ["Sept"])
DAY = r"\d{1,2}(?:st|nd|rd|th)?"
# Avoid reading an exam time such as "11 pm" as a two-digit year.
YEAR = r"(?:,?\s+(?:\d{4}|\d{2})(?![\d:]|\s*[ap]\.?m\b))?"
DATE_PATTERN = re.compile(
    rf"\b(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|"
    rf"(?:{MONTH_NAMES})\.?\s+{DAY}{YEAR}|"
    rf"{DAY}\s+(?:{MONTH_NAMES})\.?{YEAR}|"
    r"\d{1,2}/\d{1,2}(?:/(?:\d{4}|\d{2}))?)(?![\w/])",
    re.IGNORECASE,
)


def read_file(path: Path) -> list[dict]:
    """Return each page's text and whether it needed OCR."""
    if path.suffix.lower() in {".txt", ".md"}:
        return [
            {"text": text, "ocr": False}
            for text in path.read_text(encoding="utf-8-sig").split("\f")
        ]
    if path.suffix.lower() != ".pdf":
        raise ValueError("Choose a PDF or UTF-8 text file.")

    pages: list[dict] = []
    renderer = None
    engine = None
    try:
        for number, page in enumerate(PdfReader(path).pages):
            text = page.extract_text(extraction_mode="layout") or ""
            used_ocr = not text.strip()
            if used_ocr:
                if renderer is None:
                    renderer = pdfium.PdfDocument(str(path))
                    engine = RapidOCR(params={
                        "Global.log_level": "error",
                        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                        "EngineConfig.onnxruntime.inter_op_num_threads": 2,
                    })
                assert engine is not None
                text = read_ocr_page(renderer[number], engine)
            pages.append({"text": text, "ocr": used_ocr})
    finally:
        if renderer is not None:
            renderer.close()
    if not any(page["text"].strip() for page in pages):
        raise ValueError("No readable text was found.")
    return pages


def read_ocr_page(page: pdfium.PdfPage, engine: RapidOCR) -> str:
    """Read a page locally and keep table cells on the same text row."""
    bitmap = page.render(scale=2.5)
    image = bitmap.to_pil()
    try:
        result = engine(image)
    finally:
        image.close()
        bitmap.close()
        page.close()
    if not isinstance(result, RapidOCROutput) or result.txts is None:
        return ""
    if result.boxes is None:
        return "\n".join(result.txts)

    # OCR sees a table's date and topic as separate boxes. Group by height,
    # then read each row from left to right to keep useful context.
    blocks = []
    for box, text in zip(result.boxes, result.txts):
        top = float(min(point[1] for point in box))
        bottom = float(max(point[1] for point in box))
        left = float(min(point[0] for point in box))
        blocks.append(((top + bottom) / 2, left, bottom - top, text))
    if not blocks:
        return ""
    tolerance = median(block[2] for block in blocks) * 0.45
    rows = []
    for block in sorted(blocks):
        if rows and abs(block[0] - rows[-1][0][0]) <= tolerance:
            rows[-1].append(block)
        else:
            rows.append([block])
    return "\n".join(
        "  ".join(block[3] for block in sorted(row, key=lambda block: block[1]))
        for row in rows
    )


def parse_date(text: str, year: int | None) -> tuple[str | None, str]:
    """Return an ISO date, or a short explanation of why it needs review."""
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
        formats = ["%Y-%m-%d"]
    else:
        text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(r"\bSept\b", "Sep", text, flags=re.IGNORECASE)
        text = " ".join(text.replace(",", " ").replace(".", "").split())
        parts = text.split("/") if "/" in text else text.split()
        if len(parts) == 2:
            if year is None:
                return None, "Missing year"
            text += ("/" if "/" in text else " ") + str(year)
        elif len(parts[-1]) != 4:
            return None, "Use a four-digit year"
        formats = ["%m/%d/%Y", "%d/%m/%Y"] if "/" in text else [
            "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y",
        ]
    possible = set()
    for date_format in formats:
        try:
            possible.add(datetime.strptime(text, date_format).date().isoformat())
        except ValueError:
            continue
    if len(possible) == 1:
        return possible.pop(), ""
    if len(possible) > 1:
        return None, "Ambiguous month/day order"
    return None, "Invalid date"


def find_dates(pages: list[dict], year: int | None = None) -> list[dict]:
    """Find explicit date mentions with enough context to review them."""
    if year is not None and not 1 <= year <= 9999:
        raise ValueError("Year must be between 1 and 9999.")
    dates = []
    for page_number, page in enumerate(pages, start=1):
        lines = page["text"].splitlines()
        for line_number, line in enumerate(lines):
            footer = rf"(?:https?://\S+\s+|page\s*){page_number}/{len(pages)}"
            if re.fullmatch(footer, line.strip(), re.IGNORECASE):
                continue
            matches = list(DATE_PATTERN.finditer(line))
            for index, match in enumerate(matches):
                date, note = parse_date(match.group(), year)
                # Keep a range unresolved instead of turning it into a deadline.
                before = line[matches[index - 1].end():match.start()] if index else ""
                after = line[match.end():]
                if re.fullmatch(r"\s*(?:[-–—]|to)\s*", before, re.IGNORECASE) or re.match(
                    r"\s*(?:[-–—]|to)\s*(?:\d|[A-Za-z])", after, re.IGNORECASE
                ):
                    date, note = None, "Date range; review manually"
                context = "\n".join(lines[max(0, line_number - 1):line_number + 2])
                dates.append({
                    "text": match.group(), "date": date, "page": page_number,
                    "context": context.strip(),
                    "needs_review": date is None or page["ocr"],
                    "note": note or ("Check OCR text" if page["ocr"] else ""),
                })
    return dates


def save_dates(dates: list[dict], output: Path) -> None:
    """Write a readable JSON list, replacing the previous import."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Find syllabus dates and save JSON.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--year", type=int, help="Semester year for dates missing a year")
    parser.add_argument("-o", "--output", type=Path, default=Path("dates.json"))
    args = parser.parse_args()
    try:
        if args.file.resolve() == args.output.resolve():
            raise ValueError("The output must not overwrite the input file.")
        dates = find_dates(read_file(args.file), args.year)
        save_dates(dates, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Saved {len(dates)} date candidates to {args.output}")
    print(f"Flagged for review: {sum(date['needs_review'] for date in dates)}")


if __name__ == "__main__":
    main()
