"""Extract the time-gap distribution of birth and death registrations for every
CRS report year that carries it, using pdfplumber coordinate-based extraction.

The CRS "Time Gap in Registration" statement classifies every registered event
into four delay bands: within the legal 21-day limit; 21-30 days; 30 days to 1
year; and more than 1 year ("delayed registration"). From these we compute, for
each state/UT and year, the timeliness rate (share registered within 21 days)
and the delayed-registration rate (share registered more than a year late).

Why this matters: timeliness = (registered within 21 days) / (total
registered). Both numerator and denominator are counted events, so unlike the
"level of registration" completeness statistic it does not depend on any
modelled population denominator.

Available years (table present and extractable): 2014-2016 and 2018-2024. The
table is absent from the 2009-2013 and 2017 reports.
"""
import csv
import re
from pathlib import Path

import pdfplumber

STUDY_ROOT = Path(__file__).resolve().parents[1]
CRS_DIR = STUDY_ROOT / "source_reports" / "CRS"
OUT_PATH = STUDY_ROOT / "data_extracted" / "timeliness_by_state.csv"

INT_TOKEN = re.compile(r"^\d[\d,]*$")
HAS_LETTER = re.compile(r"[A-Za-z]")
DROP = {"states", "union territories", "india", "state", "sl", "no", "total", "grand total"}


def clean_cells(row):
    return [str(c).strip() for c in row if c and str(c).strip()]


def to_int(tok):
    return int(tok.replace(",", ""))


def parse_row(row):
    """A state/UT row: one name cell, then exactly four integer band counts."""
    cells = clean_cells(row)
    # drop a leading serial number cell like "1." or "12."
    cells = [c for c in cells if not re.fullmatch(r"\d{1,2}\.", c)]
    names = [c for c in cells if HAS_LETTER.search(c)]
    ints = [c for c in cells if INT_TOKEN.match(c)]
    if len(names) != 1 or len(ints) < 4:
        return None
    name = names[0].strip()
    if name.lower() in DROP:
        return None
    within, d21_30, d30_1y, after_1y = (to_int(x) for x in ints[:4])
    total = within + d21_30 + d30_1y + after_1y
    if total == 0:
        return None
    return name, within, d21_30, d30_1y, after_1y, total


def find_timegap_tables(pdf, event_word):
    """Yield candidate tables from pages whose text names the time-gap table for
    the requested event ('Birth' or 'Death')."""
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "Within Time" not in text or "After One Year" not in text:
            continue
        if event_word not in text:
            continue
        for table in page.extract_tables():
            if len(table) >= 10:
                yield table


def extract_event(pdf, report_year, event, rows):
    event_word = "Birth" if event == "births" else "Death"
    seen = set()
    for table in find_timegap_tables(pdf, event_word):
        for row in table:
            parsed = parse_row(row)
            if parsed is None:
                continue
            name, within, d21_30, d30_1y, after_1y, total = parsed
            key = (name.lower(), report_year, event)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "report_year": report_year,
                "event": event,
                "state_raw": name,
                "within_21d": within,
                "d21_30d": d21_30,
                "d30d_1y": d30_1y,
                "after_1y": after_1y,
                "total_registered": total,
                "timely_pct": round(100 * within / total, 1),
                "delayed_over_1y_pct": round(100 * after_1y / total, 1),
            })


def main():
    rows = []
    for pdf_path in sorted(CRS_DIR.glob("*.pdf")):
        year = int(pdf_path.stem)
        with pdfplumber.open(str(pdf_path)) as pdf:
            extract_event(pdf, year, "births", rows)
            extract_event(pdf, year, "deaths", rows)
        n = len([r for r in rows if r["report_year"] == year])
        print(f"{year}: {n} state-event rows")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = ["report_year", "event", "state_raw", "within_21d", "d21_30d", "d30d_1y",
              "after_1y", "total_registered", "timely_pct", "delayed_over_1y_pct"]
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    years = sorted({r["report_year"] for r in rows})
    print(f"\nWrote {len(rows)} rows to {OUT_PATH}")
    print(f"Years with timeliness data: {years}")


if __name__ == "__main__":
    main()
