# Run time report

## Target

**Every run of the analysis finishes within 5 seconds on the analyst's laptop, at this year's list size and at next year's expected 500 titles.**

The brief asks for the analysis to run "inside the client's time budget, measured" but never states the budget as a number, so this target is mine (ADR-005). I chose 5 seconds because Adjoa will sometimes rerun the analysis live in a meeting, where anything longer means people waiting on a screen. The target applies to the worst run, not the typical one, because the run that matters is the one made in the room.

The budget covers the analysis from the cache: reading the cached data, flattening, quality flags, every figure in both time windows, the robustness checks, the quality gate and writing the outputs. It excludes fetching from TMDb, which happens once per new title, takes as long as the network does (87 seconds for this year's 235 requests), and is never repeated in a meeting.

## Method

- **Hardware:** Windows 11 laptop (build 26300), Intel Core processor (Intel64 Family 6 Model 142), 8 logical CPUs, Python 3.15.2, pandas 3.1.1. Normal power settings, with other applications open as in everyday use.
- **What was timed:**
  - *Full analysis:* from the start of reading the cache to the last output file written, as reported on the `Analysis stage:` line of `python run.py --offline`, broken down by stage in `outputs/timing.csv`.
  - *Benchmark:* from the start of reading the two cache files to the end of the analysis (`tests/scale_test.py`). It excludes the quality gate and writing files, which together take about 0.1 to 0.2 seconds.
- **Data:** this year's 112 real films. For 500, 1,000 and 2,000 titles, the real films are copied under new ids, each copy with its own franchise id, so franchises stay realistic in size. Measured twice: with full credits (on average 70 cast and 223 crew per film), then with the credits trimmed to what the analysis uses (directors and the top 10 cast).
- **Runs, warm or cold, and which figure is reported:**
  - Benchmark: 10 runs per size in one session, first run included.
  - First run after idle: the laptop left unused for 10 minutes or more, then `python tests/scale_test.py --sizes 500 --repeats 3`; the first of the three runs is the cold one.
  - **The worst run decides whether the target is met.** The median shows the typical run and p95 the near-worst.
- **How to reproduce:**
  1. `python run.py` once, so the cache exists.
  2. `python tests/scale_test.py`, which writes `outputs/benchmark.csv`.
  3. For the cold case, leave the laptop unused for 10 minutes, then `python tests/scale_test.py --sizes 500 --repeats 3`. Every run of the analysis is also appended to `outputs/timing_history.csv`.

## Results

| Scenario | Runs | Median | p95 | Worst | Target met? |
|---|---|---|---|---|---|
| 112 titles, warm, full credits | 10 | 0.83 s | 1.10 s | 1.20 s | Yes |
| 112 titles, warm, trimmed credits | 10 | 0.54 s | 0.61 s | 0.62 s | Yes |
| 500 titles, warm, full credits | 10 | 2.39 s | 2.55 s | 2.56 s | Yes |
| **500 titles, first run after idle, full credits** | **3** | **4.48 s** | **5.85 s** | **6.01 s** | **No** |
| **500 titles, warm, trimmed credits** | **10** | **0.69 s** | **0.76 s** | **0.76 s** | **Yes** |
| 1,000 titles, warm, full credits | 10 | 3.87 s | 4.64 s | 4.75 s | Yes, by 0.25 s |
| 1,000 titles, warm, trimmed credits | 10 | 0.88 s | 0.95 s | 0.96 s | Yes |
| 2,000 titles, warm, full credits | 10 | 8.42 s | 8.84 s | 8.84 s | No |
| 2,000 titles, warm, trimmed credits | 10 | 1.35 s | 1.58 s | 1.65 s | Yes |
| 112 titles, full analysis, first run after idle, before the cache fix | 2 | 7.46 s | 7.93 s | 7.98 s | No |
| 112 titles, full analysis, first run after idle, after the cache fix | 1 | 2.46 s | 2.46 s | 2.46 s | Yes |

**Not measured: the first run after idle at 500 titles with trimmed credits.** Estimated instead from the measurements above: with full credits the cold run was 2.5 times the warm median (6.01 s against 2.39 s). Applied to the trimmed warm figures (median 0.69 s, worst 0.76 s), that gives about 2 seconds, roughly 3 seconds inside the budget. This is an estimate, not a measurement; it can be confirmed with the command in step 3 above.

With trimmed credits, time grows far more slowly than the list: from 112 to 2,000 titles (about 18 times the data) the median grew about 2.5 times, so no step compares every film with every other.

## Before / after

| Query / stage | Before | After | Change |
|---|---|---|---|
| Reading the cache, warm | 0.17 to 0.18 s (234 files) | 0.13 s (2 files) | About 25% faster |
| Reading the cache, first run after idle | 6.76 to 7.49 s (234 files) | 0.42 s (2 files) | About 16 times faster |
| Whole analysis, first run after idle, 112 titles | 6.94 to 7.98 s, over budget | 2.46 s | Within budget |
| Credits held per film | About 290 people (70 cast, 223 crew) | 11 (10 cast, 1 director) | Only what the analysis uses; the full credits stay in the per-film files |
| Credits file read on every run | 9.5 MB | 0.4 MB | About 24 times smaller |
| Flattening stage, 112 titles | 0.27 to 0.51 s | 0.045 s | About 6 to 10 times faster |
| 500 titles, worst warm run | 2.56 s | 0.76 s | About 3.4 times faster |
| 2,000 titles, worst warm run | 8.84 s, over budget | 1.65 s | Within budget |
| Robustness checks (sensitivity stage), after adding six measures | 0.16 s | 0.20 s | +0.04 s for six extra tests of the recommendation |
| Quality gate (10 checks before writing) | None | 0.005 s | Added at almost no cost; the run stops before writing if any check fails |

**How the two problems were found.** First, two early runs took 7 to 8 seconds while others took under 1. Rather than guess, I added per-stage timing to every run and waited for a slow one: the whole cost was in reading the cache, so the fix changed only that stage, packing 234 cached files into 2. Second, the benchmark showed 500 titles inside budget when warm, but I had not measured the case Adjoa meets at the start of a meeting. Measured, the first run after idle took 6.01 seconds and missed the target. The fix, decided in advance in ADR-005, trims the credits the analysis reads to the directors and top 10 cast it actually uses. No result changed: the franchise and standalone figures, the quality gate (10 of 10) and the live spot-check (112 of 112 matches) are identical after the change.

## Caveats

- **One laptop.** All figures come from one machine. A slower laptop would scale every figure up; the margin at 500 titles (under 1 second warm against 5) is the protection.
- **The cold case after the fix is estimated, not measured** (about 2 seconds; see Results).
- **The laptop's own power saving.** After idle, every stage ran slower, including stages that do not touch the disk, which points to the processor waking up rather than to the code. It is reported, not fixed, because no code change can remove it.
- **A one-off rebuild after the keep-rules change.** The first run after trimming took 6.36 seconds, because it read all 234 per-film files once to build the trimmed copy. It happens only when the rules for what to keep change; after a normal fetch the rebuild happens during fetching, which is not timed against the budget.
- **The copies measure speed, not findings.** The 500, 1,000 and 2,000-title lists repeat this year's films. Real lists will vary more, but their shape (credits per film, franchise sizes) is what drives the time, and that shape is realistic.
- **Sessions vary.** Earlier 500-title runs with full credits had medians of 1.74 and 2.01 seconds against this benchmark's 2.39, so the same laptop varies by a fifth or more from session to session.
- **Fetching is excluded.** The first fetch of a new list takes as long as the network does (87 seconds for 235 requests at about 2.7 a second). It happens once per new title, before the meeting, never during it.
- **The target is self-set.** If Kwame or Adjoa set a different figure, every measurement here can be checked against it as it stands.
