# Evidence

Console output saved from key runs on the analyst's laptop (Windows 11). These are records of what happened at a point in time, which a rerun cannot reproduce exactly (live TMDb answers, an idle laptop). All files are plain UTF-8 text.

| File | What it records | Supports |
|---|---|---|
| `clean_clone_test.txt` | A fresh clone set up from the README alone, run end to end on 20 November 2026 | README, Expected result |
| `step8b.txt` | The headline tables: franchise against standalone, and first, middle and last films, in both windows | `data_diagnosis.md`, client memo |
| `step8c.txt` | Six other ways of measuring return; none flips the answer | ADR-002 |
| `step8d.txt` | Franchises and standalones ranked for the shortlist (2000 on) | ADR-004, client memo |
| `step9.txt` | Spot check: 16 films x 7 fields compared with live TMDb on 18 November 2026; all 112 match | README, How the work is checked |
| `step9_broken.txt` | The same spot check after one value in `outputs/films.csv` was deliberately altered (The Dark Knight's budget, a zero removed). It is caught and classified as `our_bug`, showing the check works | README, How the work is checked |
| `step10.txt` | Scale test at 112 to 2,000 titles, warm runs, before the credits were trimmed | `measurement_report.md` |
| `step10_idle.txt` | The same scale test after the laptop had been idle | `measurement_report.md` |
| `benchmark.txt` | Benchmark with full credits, 10 runs per size: 2,000 titles misses the 5 s budget | `measurement_report.md`, ADR-005 |
| `benchmark_cold500.txt` | First run after idle at 500 titles with full credits: 6.0 s, over the budget. The reason for trimming the credits | `measurement_report.md`, ADR-005 |
| `benchmark_after.txt` | Benchmark after trimming the credits: every size, up to 2,000 titles, inside 5 s | `measurement_report.md`, ADR-005 |
| `bundle_check.txt` | The improvement: each franchise on the list compared with the whole franchise at TMDb | `improvement/improvement.md` |
| `bundle_gaps.txt` | Franchise films missing from the list that have no usable figures, or are not yet released | `improvement/improvement.md` |

Author: Ekua Micah Abakah-Paintsil
