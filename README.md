# StreamVault Licensing Analysis

Should StreamVault spend its $14M licensing budget on franchise bundles or standalone hits? This project answers that from live public film data. It takes the candidate list (`data/id_list.csv`, 127 lines of TMDb movie ids), fetches each film's details and credits from the TMDb API, accounts for every line of the list, and compares franchise against standalone films across all years and from 2000 on.

It is built to be rerun every quarter by someone other than its author, on a list of about 500 titles, without changes to the code.

```text
 data/id_list.csv
        │
        ▼
   AUDIT ────► FETCH ────► FLATTEN ────► VALIDATE ────► FLAG ────► ANALYSE ────► QUALITY GATE ────► WRITE
   ids.py      fetch.py    flatten.py    validate.py    quality.py analysis.py   checks.py          outputs/
   label every once,       JSON to       data contract; flag,      both windows, 10 named checks;
   line        cached,     tables        quarantine     never      7 measures    stops if any fails
               throttled                 bad records    delete
   └─────────────────────────── run in order, timed stage by stage, by run.py ───────────────────────────┘

   then, optionally:  improvement/bundle_check.py   every film in every franchise
                      spot_check.py                 output against live TMDb
                      present_ids.py                presentation page for the 127 lines
```

## What you need

- Python 3.11 or newer.
- Exact versions are pinned in `requirements-lock.txt`: the environment the documented outputs were produced in (Python 3.15.2, pandas 3.1.1). Install from it to reproduce them exactly.
- `requirements.txt` gives the minimum versions instead, for a machine that already has a different pandas. The code was also tested on pandas 2.2.3 and 3.0.5 and gave identical outputs; every run records the versions it used in `outputs/run_info.csv`.
- A free TMDb API key, needed only when something has not been fetched yet. Register at themoviedb.org, then Settings, API. The v3 "API Key" and the v4 "API Read Access Token" both work.

## Setup (once, about 5 minutes)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell)
source .venv/bin/activate       # macOS / Linux
pip install -r requirements-lock.txt   # exact versions (recommended)
# or: pip install -r requirements.txt   # minimum versions, if you must keep an existing pandas
```

Then put your key in a file called `.env` in this folder, next to `run.py`:

```bash
copy .env.example .env          # Windows
cp .env.example .env            # macOS / Linux
```

Open `.env` and replace `paste-your-key-here` with your key. This is the only manual step. `.env` is ignored by Git and must never be committed.

If PowerShell refuses to activate the environment ("running scripts is disabled"), run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

## Run

In this order, from this folder:

| Command | What it does | Needs the key? | Time |
|---|---|---|---|
| `python tests/test_pipeline.py` | Self-test on invented data: proves the setup works before any request is made | No | Seconds |
| `python run.py` | The analysis. Audits the list, fetches anything not cached (about 235 requests the first time), analyses, runs the quality gate, writes `outputs/` | First run only | About 90 s first time, then about 1 s |
| `python improvement/bundle_check.py` | Fetches every film in every franchise and compares the list's picture of each bundle with the whole bundle | First run only | Under a minute first time |
| `python spot_check.py` | Re-fetches 16 deliberately chosen films live and compares them with the output, field by field | Yes, every time | About 15 s |
| `python present_ids.py` | Builds `outputs/id_breakdown.html`, a page showing where every line of the list went | No | Instant |
| `python tests/scale_test.py` | Benchmark: times the analysis at 112, 500, 1,000 and 2,000 titles, 10 runs each | No | About 2 minutes |

**In a meeting, or without internet:** `python run.py --offline` and `python improvement/bundle_check.py --offline` use the cache only and make no requests.

**Expected result** (data fetched from TMDb on 18 November 2026, 12:19 to 12:21 UTC, the actual fetch date, stamped on every cached response and in `outputs/run_info.csv`; the brief's 31 October board review is the scenario date, and a refetch on 20 November gave identical figures, see `evidence/clean_clone_test.txt`): 127 lines, 117 distinct ids, 112 films analysed; franchise 5.62x against standalone 3.84x per film (all years) and 5.05x against 3.84x (2000 on); 10 of 10 quality checks passed; the analysis inside the 5-second budget.

## Rerunning next quarter

1. Replace `data/id_list.csv` with the new list: one column headed `tmdb_id`. Blank lines, placeholders, IMDb ids (`tt...`) and repeats are handled and reported, not fatal.
2. Run `python run.py`, then `python improvement/bundle_check.py`. Only new ids are fetched.
3. Open `outputs/id_breakdown.html` to see where every line went, and `outputs/checks.csv` to confirm the quality gate passed.

**To refresh figures that TMDb may have edited**, delete the `data/raw/` folder and run again. Do this before each quarterly review, so every figure carries a current as-of date.

## If something goes wrong

| Message | Cause | Fix |
|---|---|---|
| `No TMDb credentials found` | `.env` is missing, or not next to `run.py` | Create it as in Setup |
| `TMDb refused the key (HTTP 401)` | The key is wrong, or the line is not named `TMDB_API_KEY` | Check `.env`. The run stops at once instead of making failed requests |
| `No cached films found` | `--offline` used before anything was fetched | Run once without `--offline` |
| `The film table is missing columns` | TMDb changed the format of its responses | Nothing is written. Compare a cached file in `data/raw/movie/` with [`data_contract.md`](data_contract.md) and update `flatten.py` |
| `... films failed validation, more than the 5% allowed` | Many films broke the data contract at once, so the source is broken, not a few records | Nothing is written. The message lists every film and the rule it broke |
| `Quality checks failed, no outputs written` | The analysis lost, doubled or misplaced a film | The message names the failed checks. Nothing is written, so no half-wrong file reaches a meeting |
| `Analysis stage: ... (OVER the 5s budget)` | The laptop is much slower, or the list is far larger | See [`measurement_report.md`](measurement_report.md) and [`decisions/ADR-005-fetch-once-and-hold-a-5-second-budget.md`](decisions/ADR-005-fetch-once-and-hold-a-5-second-budget.md) for the documented fix |
| Requests time out | Network or TMDb trouble | Run again. Only the missing ids are fetched; failed requests are never cached |
| One run takes several seconds after updating the code | The trimmed cache copy is being rebuilt from the per-film files, once | Nothing to fix; the next run is back to about 1 s |

## Layout

| Path | What it holds | Why it is separate |
|---|---|---|
| `run.py` | The one command that runs the analysis | Everything else is called from here |
| `src/streamvault/` | The building blocks, one file per stage, plus `config.py` | Production code: what runs every quarter |
| `src/streamvault/config.py` | Paths, the 2000 cut-off, the 5-second budget, the minimum group size, which credits the analysis reads | Every setting in one place; nothing hidden in the code |
| `improvement/` | The bundle completeness check and its write-up | The improvement beyond the brief, kept apart from the brief's core work |
| `spot_check.py` | Live reconciliation of the output against TMDb | Checks the analysis from outside it |
| `present_ids.py` | The presentation page for the 127 lines | For the room, not for the analysis |
| `explore/` | `profile_candidates.ipynb`: profiles the raw list and TMDb's raw answers | Investigation, independent of the analysis. Committed with no saved outputs, so no data is in version control; `tests/test_pipeline.py` fails if any cell has outputs |
| `tests/` | Self-test (on a frozen copy of this year's list) and the benchmark | Prove the code works before it touches real data |
| `decisions/` | Architecture decision records, ADR-001 to ADR-005 | The reasons behind the code, versioned with it |
| `data_contract.md` | What every pulled record must satisfy, and what happens when one does not | The rules `validate.py` enforces, in plain language |
| `data_diagnosis.md` | Every problem in the data, ranked by risk, and where every line went | Deliverable: data diagnosis |
| `client_memo.md` | One-page memo to Kwame | Deliverable: client memo |
| `measurement_report.md` | Timing against the 5-second budget | Deliverable: measured time budget |
| `evidence/` | Saved console output from key runs, indexed in [`evidence/README.md`](evidence/README.md) | Records of what happened when, which a rerun cannot reproduce |
| `data/id_list.csv` | The candidate list exactly as received | Never edited; its faults are handled in code |
| `data/raw/` | Every TMDb response, cached with its fetch time and status | Generated, never committed |
| `outputs/` | Everything the analysis writes | Generated, never committed |

## Outputs

| File | One row per | Answers |
|---|---|---|
| `ledger.csv` | line of `id_list.csv` | Where every line went, and why |
| `id_reconciliation.csv` | outcome | The counts, adding up to the number of lines |
| `id_breakdown.html` | | The ledger as a presentation page |
| `fetch_record.csv` | requested id | What TMDb answered for each, and when |
| `fetch_log.csv` | request, per online run | Whether each run went to the network or the cache |
| `films.csv` | film | Every field, derived value and quality flag |
| `cast.csv`, `crew.csv` | film and person | Top 10 cast and the directors of each film, for lookups. Complete credits are in `data/raw/credits/` |
| `talent.csv` | film, director or top-3 actor | What the talent analysis uses |
| `validation.csv` | contract rule | How many films, cast and crew rows each rule checked, and how many failed |
| `quarantine.csv` | record and broken rule | Every record removed by validation, with the rule it broke. Empty on a clean run |
| `quality.csv`, `flag_examples.csv` | check / flagged film | Data-quality evidence |
| `checks.csv` | quality-gate check | The 10 checks that must pass before anything is written |
| `kpi_segments.csv` | segment and window | Franchise against standalone, with group sizes |
| `kpi_positions.csv` | entry position and window | First, middle and last films in a franchise |
| `kpi_collections.csv` | franchise and window | Bundle returns on the list's films |
| `standalone_ranking.csv` | standalone and window | Standalones by score |
| `talent_kpis.csv` | person, role and window | Directors and lead actors |
| `method_sensitivity.csv` | measure and window | Does any other way of measuring flip the answer? |
| `sensitivity.csv` | cleaning rule and window | Does any cleaning choice flip the answer? |
| `bundle_completeness.csv` | franchise | The list's picture of each bundle against the whole bundle |
| `bundle_members.csv` | film in a franchise | Every franchise film, on or off the list |
| `bundle_headline.csv` | window | Franchise against standalone with complete bundles |
| `spot_check.csv` | film and field | Output against live TMDb, each difference classified |
| `run_info.csv` | run | When the analysis ran, the fetch window of the data it used, and the software versions, so two runs can be compared |
| `timing.csv`, `timing_history.csv` | stage, per run | Measured time of the last run, and of every run |
| `benchmark.csv` | list size | Median, p95 and worst time at 112 to 2,000 titles |

## How the work is checked

- **Every line accounted for:** the outcome counts must add up to the number of lines in the list, or the run stops.
- **Every record checked on arrival:** `validate.py` checks each film and credit against the data contract before analysis; a broken record is quarantined, named in `quarantine.csv` and still counted in the ledger as `excluded_failed_validation`.
- **No film lost or doubled:** every merge is validated as many-to-one, and the quality gate re-checks the film count before writing.
- **Independent of itself:** the profiling notebook reaches the same counts from the raw data by a separate route.
- **Against the source:** the spot-check compares 16 films with live TMDb and classifies any difference as an analysis error or a change at TMDb.
- **Across versions:** every output was compared file by file on pandas 2.2 and 3.0.

Author: Ekua Micah Abakah-Paintsil
