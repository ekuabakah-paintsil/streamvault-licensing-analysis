# ADR-005: Fetch once, cache in two trimmed files, and hold a 5-second budget on any recent setup

- **Status:** Accepted
- **Date:** 2026-11-19
- **Decision owner:** Ekua Micah Abakah-Paintsil

## Context

Adjoa will rerun this every quarter on her own laptop, sometimes live in a meeting, on a list expected to reach about 500 titles. The brief requires the analysis to run "inside the client's time budget, measured", but never states the budget as a number.

- A full fetch for this year's list is 235 requests to a free, shared public service.
- The first version cached one file per film per request: 234 files. Runs straight after another took 0.67 to 0.84 seconds, but the first run after the laptop had been idle took 6.94 to 7.98 seconds. Timing each stage separately showed one cause: reading the cache took 6.76 to 7.49 seconds when idle against 0.17 seconds warm.
- After packing the cache into two files, 500 titles ran within budget when warm (worst 2.56 seconds over 10 runs), but the first run after idle took 6.01 seconds: over budget, in exactly the case Adjoa meets in a meeting.
- Each film's credits hold about 290 people (70 cast, 223 crew), but the analysis uses only the directors and the top 3 billed cast.
- The course setup uses pandas 2.2. The pipeline was built on pandas 3.

## Decision

Each TMDb response is fetched once and kept in full, the analysis reads a trimmed two-file copy holding only what it uses, and every run must finish in 5 seconds or less on Adjoa's laptop, measured.

1. Each response is cached with the time it was fetched and TMDb's status code, and a rerun makes no requests. Requests are throttled to about 10 per second, retried on temporary errors, and stopped at once on a rejected key.
2. The per-film files stay complete as the source of truth. Two bundle files (film details, and credits trimmed to directors and the top 10 cast) are what the analysis reads. The keep-rules are set in one place in the configuration.
3. The 5-second budget is my own target, set because the run must answer in a meeting without anyone waiting.
4. The pipeline supports pandas 2.2 and later. Testing on both versions found one difference, caused by pandas 2.2 ranking blanked values as if they were the lowest; it is fixed, and all 16 output files are identical on both.

| Measured | Before | After |
|---|---|---|
| Reading the cache, first run after idle (112 titles) | 6.76 to 7.49 s (234 files) | 0.42 s (2 files) |
| Whole analysis, first run after idle (112 titles) | 7 to 8 s, over budget | 2.46 s |
| 500 titles, first run after idle | 6.01 s, over budget (full credits) | About 2 s, estimated (trimmed) |
| 500 titles, worst of 10 warm runs | 2.56 s (full credits) | 0.76 s (trimmed) |
| 2,000 titles, worst of 10 warm runs | 8.84 s, over budget | 1.65 s |
| Credits file read on every run | 9.5 MB | 0.4 MB |

## Alternatives considered

### Alternative A: No cache, fetch on every run

- **How it would work:** Request every film from TMDb each time the analysis runs.
- **Why it is attractive:** The data is always current, and there is nothing on disk to manage.
- **Why rejected:** 235 requests and about 90 seconds per run, rising to roughly 1,000 requests at 500 titles; it fails without internet in a meeting; and the figures would shift between runs with no record of when. It also breaks the brief's rule about a shared API.

### Alternative B: Keep only the one-file-per-film cache

- **How it would work:** Read the 234 individual files on every run.
- **Why it is attractive:** Simpler, and it was already working.
- **Why rejected:** Measured 7 to 8 seconds on the first run after idle, over budget, at today's size. The cost grows with the number of files, so at 500 titles (about 1,000 files) it would get worse.

### Alternative C: Keep the full credits in the bundle

- **How it would work:** Pack every cast and crew entry into the bundle, as the first two-file version did.
- **Why it is attractive:** One fewer rule to explain, and every credit is available to the analysis without opening the per-film files.
- **Why rejected:** Measured, not assumed. I first left the credits whole because 500 titles fit the budget when warm (worst 2.56 seconds). Measuring the first run after idle at 500 titles then gave 6.01 seconds, over budget. The analysis uses about 5% of the credits it was loading, so trimming changed no result (franchise and standalone figures, quality gate and live spot-check all identical) while cutting the worst warm run at 500 titles from 2.56 to 0.76 seconds.

### Alternative D: Require pandas 3 only

- **How it would work:** Keep the original requirement of pandas 3.0 or later.
- **Why it is attractive:** One version to support and test.
- **Why rejected:** It would fail to install on a laptop set up the way the course recommends, which would fail the clean-clone test before a single line ran.

## Consequences

- **What this buys:** A rerun costs TMDb nothing and works offline, so it is safe in a meeting. Every figure carries an as-of date (fetched 18 November 2026, 12:19 to 12:21 UTC). At 500 titles the worst warm run is 0.76 seconds and the estimated cold run about 2 seconds, and even 2,000 titles fit the budget.
- **What this costs:** Data is kept twice on disk (complete per film, trimmed in the bundle), about 10 MB in all. A question that needs other credits, such as writers or composers, means widening the keep-rules in the configuration, after which the first run rebuilds the bundle once (measured at 6.36 seconds). Figures do not refresh by themselves: to pick up TMDb's edits, Adjoa must delete the cache and fetch again, and should do so before each quarterly review.
- **What it costs the client if I am wrong:** The cold run at 500 titles after trimming is estimated, not measured. If Adjoa's laptop is much slower than mine, or the estimate is optimistic, the first run in a meeting could take a few seconds longer than expected, though still well inside the budget on the figures here.
- **What would make me revisit this:** Any run reporting over budget (the pipeline prints the measured time against the budget on every run), the list growing well past 2,000 titles, a question that needs more of the credits, or a client-stated time target replacing my own.

## What this survives

Adjoa rerunning this at about 500 titles on her own laptop, without me. Measured at that size on real data over 10 runs, the worst warm run is 0.76 seconds, and the pipeline would still fit the budget at four times that size. The cache only fetches new titles each quarter, the keep-rules are one setting rather than code, the setup works on any pandas from 2.2 on, and the pipeline reports its own timing every run and keeps a history, so a slowdown is visible the day it happens rather than discovered in a meeting.
