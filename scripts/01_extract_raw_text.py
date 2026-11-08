"""Dump layout-preserving text from every CRS annual report and SRS bulletin PDF.

Source PDFs are read from source_reports/CRS and source_reports/SRS.
Output goes to ../data_extracted/raw_text/{crs,srs}_<year>.txt for all downstream
parsing scripts. Re-run whenever a new year's report is added.
"""
import subprocess
import sys
from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_ROOT = STUDY_ROOT.parent
CRS_DIR = STUDY_ROOT / "source_reports" / "CRS"
SRS_DIR = STUDY_ROOT / "source_reports" / "SRS"
OUT_DIR = STUDY_ROOT / "data_extracted" / "raw_text"


def dump(pdf_path: Path, out_path: Path) -> None:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), str(out_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  FAILED: {pdf_path.name}: {result.stderr.strip()}", file=sys.stderr)
    else:
        print(f"  OK: {pdf_path.name} -> {out_path.name}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"CRS reports from {CRS_DIR}")
    for pdf in sorted(CRS_DIR.glob("*.pdf")):
        year = pdf.stem
        dump(pdf, OUT_DIR / f"crs_{year}.txt")

    print(f"SRS bulletins from {SRS_DIR}")
    for pdf in sorted(SRS_DIR.glob("SRS_Bulletin_*.pdf")):
        # filenames look like SRS_Bulletin_2009_Vol_45_No_1.pdf
        year = pdf.stem.split("_")[2]
        dump(pdf, OUT_DIR / f"srs_{year}.txt")


if __name__ == "__main__":
    main()
