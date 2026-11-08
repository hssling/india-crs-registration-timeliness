#!/usr/bin/env python3
"""Extract, for report year 2024, each state/UT's estimated births and deaths
(Statement 2), published level of registration (Statement 2), and registered
births and deaths (Statements 10 and 11), plus the India rows for 2023 and 2024.

Why: the level of registration is published capped at 100.0%. Its numerator,
per the report's own notes, is every registration made during the year
whatever the year of occurrence (Delhi and Goa are the stated exceptions). The
uncapped ratio registered/estimated shows where registrations exceed the
estimated events of the year, i.e. where backlog registration is inflating
completeness.

Validation built in: min(100, 100 * registered / estimated) must reproduce the
published level of registration to within 0.15 points for every state/UT;
otherwise the script stops.

Inputs (read-only): the plain-text extraction of the 2023 and 2024 reports in
data_extracted/raw_text/ for Statement 2, and the
2024 report PDF in source_reports/CRS/ for Statements 10 and 11.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT
RAW = ROOT / "data_extracted" / "raw_text"
PDF_2024 = ROOT / "source_reports" / "CRS" / "2024.pdf"
OUT = ROOT / "data_extracted" / "state_events_2024.csv"
OUT_NATIONAL = ROOT / "data_extracted" / "national_estimated_events.csv"

CANON = {
    "d & n haveli & daman & diu": "D & N Haveli and Daman & Diu",
    "d & n haveli and daman & diu": "D & N Haveli and Daman & Diu",
}


def canon(name: str) -> str:
    name = re.sub(r"\s+", " ", name.strip())
    return CANON.get(name.lower(), name)


def block(lines: list[str], start_pattern: str, end_pattern: str) -> list[str]:
    start = next(i for i, l in enumerate(lines) if re.search(start_pattern, l))
    end = next(i for i in range(start + 1, len(lines)) if re.search(end_pattern, lines[i]))
    return lines[start:end]


ROW2 = re.compile(
    r"^\s*(?:\d+\.\s+)?([A-Za-z][A-Za-z&.\s]*?)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s*$"
)


def parse_statement2(lines: list[str]) -> dict:
    rows = {}
    for line in block(lines, r"Statement 2: Estimated Events", r"^Note: Mid-Year"):
        m = ROW2.match(line)
        if not m:
            continue
        name = canon(m.group(1))
        rows[name] = {
            "population_000": int(m.group(2)),
            "estimated_births": int(m.group(3)),
            "estimated_deaths": int(m.group(4)),
            "level_births_pct": float(m.group(5)),
            "level_deaths_pct": float(m.group(6)),
        }
    return rows


def parse_registered(pdf_path: Path, header: str) -> dict:
    """Statements 10/11 read with pdfplumber's table extraction (their text layer
    is column-shifted). The last cell of each row is the report year."""
    import logging
    import pdfplumber
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    rows = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            if header not in (page.extract_text() or ""):
                continue
            for table in page.extract_tables():
                for row in table:
                    cells = [c for c in row if c not in (None, "")]
                    names = [c for c in cells if re.search(r"[A-Za-z]{3}", c)]
                    last = row[-1]
                    if not names or last is None or not re.fullmatch(r"\d+", str(last).strip()):
                        continue
                    name = canon(names[0])
                    if name.lower() in {"states", "union territories"} or "Number of" in name:
                        continue
                    rows[name] = int(str(last).strip())
            break
    if not rows:
        raise SystemExit(f"{header!r} not found in {pdf_path.name}")
    return rows


def main() -> None:
    lines24 = (RAW / "crs_2024.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    lines23 = (RAW / "crs_2023.txt").read_text(encoding="utf-8", errors="replace").splitlines()

    est = parse_statement2(lines24)
    reg_b = parse_registered(PDF_2024, "Statement 10: Number of registered births")
    reg_d = parse_registered(PDF_2024, "Statement 11: Number of registered deaths")

    out = []
    problems = []
    for name, e in est.items():
        if name not in reg_b or name not in reg_d:
            problems.append(f"{name}: registered count not parsed")
            continue
        rb, rd = reg_b[name], reg_d[name]
        ratio_b = 100 * rb / e["estimated_births"]
        ratio_d = 100 * rd / e["estimated_deaths"]
        for label, ratio, published in (("births", ratio_b, e["level_births_pct"]),
                                        ("deaths", ratio_d, e["level_deaths_pct"])):
            if abs(min(100.0, ratio) - published) > 0.15:
                problems.append(f"{name} {label}: computed {ratio:.2f} vs published {published}")
        out.append({
            "state": name, **e,
            "registered_births": rb, "registered_deaths": rd,
            "ratio_births_pct": round(ratio_b, 1), "ratio_deaths_pct": round(ratio_d, 1),
        })
    if problems:
        raise SystemExit("validation failed:\n  " + "\n  ".join(problems))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"wrote {OUT.name}: {len(out)} rows (India + states/UTs); all published levels reproduced")

    # India rows of Statement 2 for 2023 and 2024 (2023's table text is column-
    # shifted below the India row, so only the India row is used from it).
    national = []
    for year, lines in ((2023, lines23), (2024, lines24)):
        for line in block(lines, r"Statement 2: Estimated Events", r"^Note: Mid-Year"):
            m = re.match(r"^\s*India\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)", line)
            if m:
                national.append({"year": year, "estimated_births": int(m.group(2)),
                                 "estimated_deaths": int(m.group(3)),
                                 "level_births_pct": float(m.group(4)),
                                 "level_deaths_pct": float(m.group(5))})
                break
    with OUT_NATIONAL.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(national[0]))
        w.writeheader()
        w.writerows(national)
    print(f"wrote {OUT_NATIONAL.name}: {national}")
    over = [r for r in out if r["state"] != "India" and (r["ratio_births_pct"] > 100 or r["ratio_deaths_pct"] > 100)]
    print(f"{len(over)} states/UTs with registrations exceeding estimated events (births or deaths)")
    for r in sorted(over, key=lambda r: -r["ratio_births_pct"])[:12]:
        print(f"  {r['state']:32s} births {r['ratio_births_pct']:6.1f}  deaths {r['ratio_deaths_pct']:6.1f}")


if __name__ == "__main__":
    main()
