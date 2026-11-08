"""Extract state/UT-level birth & death registration completeness ('Level of
Registration') for every CRS report year, directly from the PDFs using
pdfplumber's coordinate-based table extraction.

Earlier attempts at parsing pdftotext -layout output line-by-line produced
silent errors on years where a table column wrapped onto an adjacent output
line (verified case: 2015 Andhra Pradesh read as births=100.0/deaths=46.6 from
the text dump, vs. births=98.4/deaths=84.9 from pdfplumber's actual table
cells -- the text-based parser had picked up an SRS crude birth/death rate
value instead of the real percentage in some rows). pdfplumber keeps each
number in its own table cell regardless of how the visual layout wraps, so it
is used here instead for every year.

Candidate pages are located by searching each PDF's page text for the
co-occurrence of 'Level of Registration' and 'Estimated' (broader than the
literal 'Statement 2' heading, since page/statement numbering is not
consistent across years) then keeping tables with at least 15 rows and an
'India' row -- the fingerprint of the state/UT completeness table.
"""
import csv
import re
from pathlib import Path

import pdfplumber

STUDY_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_ROOT = STUDY_ROOT.parent
CRS_DIR = STUDY_ROOT / "source_reports" / "CRS"
OUT_PATH = STUDY_ROOT / "data_extracted" / "state_level_of_registration_raw.csv"

PERCENT_TOKEN = re.compile(r"^\d{1,3}\.\d$")
HAS_LETTER = re.compile(r"[A-Za-z]")
DROP_NAMES = {"india", "states", "union territories", "state", "sl", "no", "total"}


def cell_row_to_values(row) -> list:
    return [c.strip() for c in row if c and str(c).strip()]


def parse_row(row) -> tuple | None:
    values = cell_row_to_values(row)
    if not values:
        return None
    names = [v for v in values if HAS_LETTER.search(v) and not v.rstrip(".").isdigit()]
    percents = [v for v in values if PERCENT_TOKEN.match(v)]
    if len(names) != 1 or len(percents) < 2:
        return None
    name = names[0].strip()
    if name.lower() in DROP_NAMES:
        return None
    return name, percents[-2], percents[-1]


def find_candidate_tables(pdf: "pdfplumber.PDF") -> list:
    tables = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "Level of Registration" not in text or "Estimated" not in text:
            continue
        for table in page.extract_tables():
            if len(table) < 15:
                continue
            flat_first_col_text = " ".join(
                " ".join(cell_row_to_values(r)) for r in table[:6]
            )
            if "India" in flat_first_col_text:
                tables.append(table)
    return tables


def parse_pdf(pdf_path: Path, report_year: int, rows: list) -> int:
    with pdfplumber.open(str(pdf_path)) as pdf:
        tables = find_candidate_tables(pdf)

    seen_names = set()
    n_added = 0
    for table in tables:
        for row in table:
            parsed = parse_row(row)
            if parsed is None:
                continue
            name, level_births, level_deaths = parsed
            dedupe_key = (name.lower(), report_year)
            if dedupe_key in seen_names:
                continue
            seen_names.add(dedupe_key)
            rows.append({
                "report_year": report_year,
                "state_raw": name,
                "level_births_pct": level_births,
                "level_deaths_pct": level_deaths,
            })
            n_added += 1
    return n_added


def main() -> None:
    rows: list = []
    for pdf_path in sorted(CRS_DIR.glob("*.pdf")):
        report_year = int(pdf_path.stem)
        n = parse_pdf(pdf_path, report_year, rows)
        print(f"{report_year}: {n} state/UT rows")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["report_year", "state_raw", "level_births_pct", "level_deaths_pct"]
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    years = sorted({r["report_year"] for r in rows})
    print(f"\nWrote {len(rows)} state/UT row observations to {OUT_PATH}")
    print(f"Years with a parsed state table: {years}")
    missing = sorted(set(range(2009, 2025)) - set(years))
    print(f"Years with NO parseable state table: {missing}")


if __name__ == "__main__":
    main()
