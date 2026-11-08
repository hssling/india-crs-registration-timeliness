# From Completeness to Timeliness: Birth and Death Registration in India's Civil Registration System, 2009-2024 - data and code

Data, code and derived outputs for the study *From Completeness to Timeliness: Birth and Death Registration in India's Civil Registration System, 2009-2024*.

The study analyses the Registrar General of India's Annual Reports on Vital Statistics of India based on the Civil Registration System (CRS) and the Sample Registration System (SRS) Bulletins for 2009-2024. It separates the completeness of birth and death registration from its timeliness, shows that both published statistics are tabulated by year of registration rather than year of occurrence, and assesses state convergence in completeness with sensitivity analyses for the 100% ceiling, boundary changes and regression to the mean.

## Contents

| Path | Contents |
| --- | --- |
| `data_extracted/` | Values extracted from the published reports: national and state level of registration, time-gap distribution of registrations by state (2020-2024), 2024 state registered and estimated events, institutional shares, SRS national rates |
| `data_extracted/raw_text/` | Plain-text extraction of each CRS report and SRS Bulletin, the input to the parsers |
| `scripts/` | Extraction (01-06, 10-14) and analysis (16-18) code |
| `outputs/tables/` | Derived tables: national timeliness accounting, 2024 state timeliness accounting, convergence and sensitivity analyses, dispersion on a balanced panel, earliest-to-latest state change |
| `outputs/figures/` | Figures (JPEG, 300 dpi) |
| `source_reports/` | Location for the downloaded report PDFs (not redistributed) |

## Reproducing the results

Python 3.10 or later with the packages in `requirements.txt`.

From the extracted data (no PDFs needed):

```
pip install -r requirements.txt
python scripts/17_timeliness_accounting_and_convergence.py
python scripts/18_make_figures.py
```

From the source reports: download the CRS Annual Reports 2009-2024 and SRS Bulletins (https://crsorgi.gov.in/) into `source_reports/CRS/<year>.pdf` and `source_reports/SRS/<year>.pdf`, then run scripts 01-06, 10-14 and 16-18 in numerical order.

Script 16 validates its extraction internally: the uncapped ratio of registered to estimated events, capped at 100%, must reproduce every published level of registration for 2024.

## Key definitions

- **Completeness (level of registration):** registered events as a percentage of events estimated from SRS rates and population projections; the numerator counts all registrations made in the year, whatever the year of occurrence, and values above 100% are published as 100.0%.
- **Registration-year timeliness:** percentage of a year's registrations made within the statutory 21 days.
- **Recent-event timeliness:** within-21-day registrations as a percentage of registrations excluding those made more than one year after the event.
- **Timely coverage:** within-21-day registrations per 100 estimated events.
- **Delayed registration:** percentage of registrations made more than one year after the event.

## Sources

Office of the Registrar General, India. Vital Statistics of India Based on the Civil Registration System, 2009-2024; Sample Registration System Bulletins, 2009-2024. Ministry of Home Affairs, Government of India. https://crsorgi.gov.in/

## Licence

Code: MIT License (`LICENSE`). Extracted data and derived outputs: Creative Commons Attribution 4.0 International (`LICENSE-DATA.md`). The underlying reports are publications of the Government of India and are not redistributed here.

## Citation

See `CITATION.cff`. Author: Siddalingaiah H S (ORCID 0000-0002-4771-8285).
