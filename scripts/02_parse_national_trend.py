"""Parse national-level CRS birth/death registration completeness ("Level of
Registration") for each year, from the narrative sentences in every CRS annual
report's Executive Summary / Chapter III analysis.

Two sentence patterns cover almost all reports:
  1) "The level of registration of <births|deaths> has increased/decreased
     from X% in YYYY to Y% in YYYY" -> yields two (year, value) points.
  2) "the level of registration of <births|deaths> ... stood at X%" /
     "... is X%" for the report's own year.

Each candidate point is tagged with the report it came from. Where the same
year is reported by more than one report, all observations are kept in the
long output so contradictions are visible rather than silently resolved --
reconciliation (e.g. preferring the self-reporting year) happens in the
analysis script, not here.

Years/indicators with NO matching sentence in ANY report are real data gaps
(confirmed for national deaths/births headline figures in the 2020-2022
reports) and are left absent from the output rather than imputed.
"""
import csv
import re
from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = STUDY_ROOT / "data_extracted" / "raw_text"
OUT_PATH = STUDY_ROOT / "data_extracted" / "national_level_of_registration_candidates.csv"

INDICATORS = {"births": "birth_registration", "deaths": "death_registration"}


def normalize_indicator(word: str) -> str:
    word = word.lower()
    if not word.endswith("s"):
        word += "s"
    return INDICATORS[word]

# Pattern 1: "...from X% in YYYY to Y% in YYYY"
PAT_FROM_TO = re.compile(
    r"level of registration of (births?|deaths?)[^.]{0,60}?"
    r"from\s+([\d.]+)\s*(?:%|per\s*cent)\s*in\s+(\d{4})\s+to\s+"
    r"([\d.]+)\s*(?:%|per\s*cent)\s*in\s+(\d{4})",
    re.IGNORECASE,
)

# Pattern 2: "for the year YYYY stood at X%" / "... is X%" / "... was X%"
PAT_STOOD_AT = re.compile(
    r"level of registration of (births?|deaths?)[a-z\s]{0,20}?"
    r"(?:for the year\s+(\d{4})\s+)?(?:stood at|is|was)\s+([\d.]+)\s*%",
    re.IGNORECASE,
)

# Pattern 3: "India level of X%" (used in the states-above/below-India sentences)
PAT_INDIA_LEVEL = re.compile(
    r"level of Registration of (Births?|Deaths?)\s+(?:is\s+)?(?:above|below)\s+the\s+India\s+level\s+of\s+([\d.]+)\s*%",
    re.IGNORECASE,
)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


# Anchored at end-of-line right after the year: this is true of the actual page
# heading ("...States/UTs 2018") but NOT the Table-of-Contents entry for the same
# statement, which has a trailing page number after a wide gap
# ("...States 2018                    15"). Matching the ToC line instead would
# point the India-row search at the wrong part of the document.
HEADING_STATEMENT2 = re.compile(
    r"Estimated [Ee]vents and Level of Registration by India,?\s*States(?:/UTs)?\s+\d{4}\s*:?\s*$",
    re.IGNORECASE,
)
INDIA_ROW = re.compile(r"^\s{0,8}India\s+[\d,.]")
NUMBER_TOKEN = re.compile(r"[\d,]+\.\d+|[\d,]{2,}")


def parse_statement2_india_row(path: Path, report_year: int, rows: list) -> None:
    """Statement 2 ('Estimated events/Estimated Events and Level of Registration
    by India, States[/UTs] YYYY') always ends its national ('India') row with the
    two headline percentages: level of registration of births, then deaths.
    Column composition upstream of those two numbers (population, SRS CBR/CDR,
    estimated births/deaths) varies by year, so only the final two tokens are
    trusted here.
    """
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    heading_idx = None
    for i, line in enumerate(lines):
        if HEADING_STATEMENT2.search(line):
            heading_idx = i
            break
    if heading_idx is None:
        return

    for line in lines[heading_idx : heading_idx + 40]:
        if INDIA_ROW.match(line):
            tokens = NUMBER_TOKEN.findall(line)
            # drop thousands-separated integers (population/estimated counts) --
            # keep decimal tokens which are the CBR/CDR/percentage fields; the
            # last two decimal tokens are level_births, level_deaths.
            decimals = [t for t in tokens if "." in t]
            if len(decimals) >= 2:
                level_births, level_deaths = decimals[-2], decimals[-1]
                rows.append({
                    "year": report_year, "indicator": "birth_registration",
                    "value_pct": level_births, "source_report": report_year,
                    "pattern": "statement2_india_row", "sentence": line.strip()[:200],
                })
                rows.append({
                    "year": report_year, "indicator": "death_registration",
                    "value_pct": level_deaths, "source_report": report_year,
                    "pattern": "statement2_india_row", "sentence": line.strip()[:200],
                })
            return


def report_year_from_filename(path: Path) -> int:
    return int(path.stem.split("_")[1])


def parse_file(path: Path, rows: list) -> None:
    report_year = report_year_from_filename(path)
    text = collapse_whitespace(path.read_text(encoding="utf-8", errors="ignore"))

    for m in PAT_FROM_TO.finditer(text):
        indicator = normalize_indicator(m.group(1))
        val1, year1, val2, year2 = m.group(2), int(m.group(3)), m.group(4), int(m.group(5))
        rows.append({
            "year": year1, "indicator": indicator, "value_pct": val1,
            "source_report": report_year, "pattern": "from_to_earlier",
            "sentence": m.group(0)[:200],
        })
        rows.append({
            "year": year2, "indicator": indicator, "value_pct": val2,
            "source_report": report_year, "pattern": "from_to_later",
            "sentence": m.group(0)[:200],
        })

    for m in PAT_STOOD_AT.finditer(text):
        indicator = normalize_indicator(m.group(1))
        year = int(m.group(2)) if m.group(2) else report_year
        rows.append({
            "year": year, "indicator": indicator, "value_pct": m.group(3),
            "source_report": report_year, "pattern": "stood_at",
            "sentence": m.group(0)[:200],
        })

    for m in PAT_INDIA_LEVEL.finditer(text):
        indicator = normalize_indicator(m.group(1))
        rows.append({
            "year": report_year, "indicator": indicator, "value_pct": m.group(2),
            "source_report": report_year, "pattern": "india_level_ref",
            "sentence": m.group(0)[:200],
        })


def main() -> None:
    rows: list = []
    for path in sorted(RAW_DIR.glob("crs_*.txt")):
        report_year = report_year_from_filename(path)
        parse_file(path, rows)
        parse_statement2_india_row(path, report_year, rows)

    rows.sort(key=lambda r: (r["indicator"], r["year"], r["source_report"]))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "indicator", "value_pct", "source_report", "pattern", "sentence"])
        writer.writeheader()
        writer.writerows(rows)

    years_covered = sorted({r["year"] for r in rows})
    print(f"Wrote {len(rows)} candidate observations to {OUT_PATH}")
    print(f"Years with at least one observation: {years_covered}")
    for indicator in INDICATORS.values():
        yrs = sorted({r["year"] for r in rows if r["indicator"] == indicator})
        missing = sorted(set(range(2009, 2025)) - set(yrs))
        print(f"  {indicator}: years covered={yrs}")
        print(f"  {indicator}: years MISSING (2009-2024)={missing}")


if __name__ == "__main__":
    main()
