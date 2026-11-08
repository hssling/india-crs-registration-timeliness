"""Extract national Crude Birth Rate, Crude Death Rate and Infant Mortality
Rate from every SRS Bulletin (2009-2024), as an independent benchmark against
the CRS 'estimated events' denominator (used in the discussion, not to
replace it -- SRS is itself a sample-based estimate, not a census).

Two extraction patterns are needed because the bulletin's layout changed
partway through the series:
  - Older bulletins (~2009-2019): Table 1's 'India' row parses cleanly as
    twelve numbers (Total/Rural/Urban x4 indicators); the first of each
    Total/Rural/Urban triple is the national Total figure we want.
  - Newer bulletins (~2020-2024): Table 1's layout does not extract cleanly
    (state rows get mis-aligned), so the Abstract's prose sentence
    ("the Birth Rate for the Country has been estimated at X ... Death Rate
    ... estimated at Y ... Infant Mortality Rate for the year YYYY is Z") is
    used instead.
"""
import csv
import re
from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = STUDY_ROOT / "data_extracted" / "raw_text"
OUT_PATH = STUDY_ROOT / "data_extracted" / "srs_national_rates.csv"

INDIA_ROW = re.compile(r"^India\s+([\d.]+.*)$", re.MULTILINE)
NUMBER = re.compile(r"\d+\.\d+|\d+")

# These bulletins lay the Abstract out in two columns, and pdftotext -layout
# interleaves both columns onto the same physical output lines rather than
# preserving true reading order -- so a cross-line regex on collapsed text
# picks up left-column noise between "has been" and "estimated at". Matching
# each figure independently within a single output line sidesteps that.
PROSE_CBR = re.compile(r"estimated at\s+([\d.]+),\s*whereas the\s+[Dd]eath\s+[Rr]ate", re.IGNORECASE)
PROSE_CDR = re.compile(r"estimated at\s+([\d.]+)\.\s*The estimate of Infant", re.IGNORECASE)
PROSE_IMR = re.compile(r"Rate for the year\s+\d{4}\s+is\s+(\d+)\s+infant", re.IGNORECASE)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def try_table_row(text: str) -> dict | None:
    for m in INDIA_ROW.finditer(text):
        tokens = NUMBER.findall(m.group(1))
        if len(tokens) < 10:
            continue
        # Reject false positives such as a column-index header row that also
        # starts with "India" (e.g. "India   2  3  4  5 ... 8") -- India's
        # crude birth rate has stayed in a 15-30 range across 2009-2024, so a
        # first token outside that band means this isn't the real data row.
        try:
            cbr_candidate = float(tokens[0])
        except ValueError:
            continue
        if not (10.0 <= cbr_candidate <= 35.0):
            continue
        return {"cbr": tokens[0], "cdr": tokens[3], "ngr": tokens[6], "imr": tokens[9]}
    return None


def try_prose(text: str) -> dict | None:
    cbr = cdr = imr = None
    for line in text.splitlines():
        if cbr is None:
            m = PROSE_CBR.search(line)
            if m:
                cbr = m.group(1)
        if cdr is None:
            m = PROSE_CDR.search(line)
            if m:
                cdr = m.group(1)
        if imr is None:
            m = PROSE_IMR.search(line)
            if m:
                imr = m.group(1)
    if cbr is None or cdr is None or imr is None:
        return None
    return {"cbr": cbr, "cdr": cdr, "ngr": "", "imr": imr}


def main() -> None:
    rows = []
    for path in sorted(RAW_DIR.glob("srs_*.txt")):
        year = int(path.stem.split("_")[1])
        text = path.read_text(encoding="utf-8", errors="ignore")

        result = try_table_row(text)
        method = "table1_india_row"
        if result is None:
            result = try_prose(text)
            method = "abstract_prose"
        if result is None:
            print(f"{year}: NO MATCH (needs manual check)")
            continue

        rows.append({"year": year, "method": method, **result})
        print(f"{year}: cbr={result['cbr']} cdr={result['cdr']} imr={result['imr']} (via {method})")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "method", "cbr", "cdr", "ngr", "imr"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} SRS national-rate observations to {OUT_PATH}")


if __name__ == "__main__":
    main()
