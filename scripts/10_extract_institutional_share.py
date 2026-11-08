"""Extract the national share of institutional births (of total registered
births) and institutional deaths (of total registered deaths) for each CRS
report year, from the narrative Executive Summary / Chapter III sentences.

These are a candidate explanatory series for the 'what changed' question: if
national registration completeness rose while institutional contact (the
mechanism known to be strong but birth-specific in household survey
district-level study) stayed flat or fell, that is evidence the improvement
is not primarily facility-driven.

The sentence wraps across output lines in most years (the percentage sits on
the line after "...total registered births is"), so matching is done on
whitespace-collapsed text rather than single lines.
"""
import csv
import re
from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = STUDY_ROOT / "data_extracted" / "raw_text"
OUT_PATH = STUDY_ROOT / "data_extracted" / "institutional_share_national.csv"

PAT_BIRTHS = re.compile(
    r"share of [Ii]nstitutional births (?:to|in) total\s+registered births\s+(?:has increased to\s+)?"
    r"(?:is\s+)?([\d.]+)\s*%",
    re.IGNORECASE,
)
PAT_DEATHS = re.compile(
    r"share of [Ii]nstitutional deaths in total\s+registered deaths\s+(?:has increased to\s+)?"
    r"(?:is\s+)?(?:only\s+)?([\d.]+)\s*%",
    re.IGNORECASE,
)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def main() -> None:
    rows = []
    for path in sorted(RAW_DIR.glob("crs_*.txt")):
        year = int(path.stem.split("_")[1])
        text = collapse_whitespace(path.read_text(encoding="utf-8", errors="ignore"))

        m_b = PAT_BIRTHS.search(text)
        m_d = PAT_DEATHS.search(text)
        if m_b:
            rows.append({"year": year, "indicator": "institutional_birth_share_pct", "value_pct": m_b.group(1)})
        if m_d:
            rows.append({"year": year, "indicator": "institutional_death_share_pct", "value_pct": m_d.group(1)})

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "indicator", "value_pct"])
        writer.writeheader()
        writer.writerows(rows)

    for indicator in ("institutional_birth_share_pct", "institutional_death_share_pct"):
        series = sorted((r["year"], r["value_pct"]) for r in rows if r["indicator"] == indicator)
        print(f"{indicator}: {series}")
    print(f"\nWrote {len(rows)} observations to {OUT_PATH}")


if __name__ == "__main__":
    main()
