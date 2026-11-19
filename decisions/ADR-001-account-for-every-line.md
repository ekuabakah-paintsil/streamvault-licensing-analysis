# ADR-001: Account for every line of the candidate list, and remove only what cannot be a film before fetching

- **Status:** Accepted
- **Date:** 2026-11-19
- **Decision owner:** Ekua Micah Abakah-Paintsil

## Context

The candidate list, `id_list.csv`, has 127 lines. It was assembled over four years from three sources and never cleaned. The brief requires every one of the 127 identifiers to be accounted for, and requires the list to be pulled "without abusing a shared API".

Profiling the file as text, with no missing-value guessing, showed:

- 1 blank line (line 69).
- 1 value that cannot be a TMDb id: `-1` (line 30).
- 1 placeholder: `N/A` (line 111).
- 1 IMDb-format id, `tt0468569` (line 95), which TMDb's ids endpoint cannot use directly.
- 6 lines that repeat an id already listed (lines 43, 60, 90, 91, 94, 102).
- 5 ids far larger than any other on the list (lines 18, 35, 73, 93, 99).

Some faults can be seen in the file itself. Others can only be found by asking TMDb: whether a large id exists, and which film the IMDb id refers to.

## Decision

Every line is labelled with an outcome and a reason, and no line is ever deleted from the file. Lines the file itself proves are not a fetchable id are set aside before any request; everything that needs TMDb to judge is fetched once and judged on the answer.

1. Blank lines, non-positive numbers and placeholder text are labelled and never sent to TMDb.
2. The IMDb-format id is translated through TMDb's lookup and treated like any other id. It resolved to 155 (The Dark Knight), already on line 2, so it became a duplicate.
3. A repeated id keeps its first line; later lines are labelled "same TMDb id as line N".
4. Ids TMDb answers "not found" for are labelled and excluded, and the "not found" answer is cached so it is never asked for twice.
5. The pipeline stops if the outcome counts do not add back to the number of lines in the file.

Result: 127 lines, 117 distinct ids fetched, 112 films analysed, 5 not found, 7 duplicates, 3 non-ids.

## Alternatives considered

### Alternative A: Clean the file by hand, then analyse the cleaned copy

- **How it would work:** Open the list in a spreadsheet, delete the blank line, `-1`, `N/A` and the repeats, and save a clean version.
- **Why it is attractive:** Quick, and the analysis code stays simpler.
- **Why rejected:** It destroys the evidence. Nobody could later see what was removed or why, the 127 could no longer be reconciled, and Adjoa would have to repeat the hand edit every quarter, on a list four times the size.

### Alternative B: Send every line to TMDb as given

- **How it would work:** Request all 127 values and let TMDb's errors sort out the bad ones.
- **Why it is attractive:** One rule for every line; no judgement needed before fetching.
- **Why rejected:** It wastes requests on values that can never be films (`N/A`, `-1`, a blank) and fetches the same film twice for every repeat. That breaks the brief's rule about not abusing a shared API, and double-counts 6 films.

### Alternative C: Discard the IMDb-format id

- **How it would work:** Treat `tt0468569` as invalid, like `N/A`.
- **Why it is attractive:** No extra lookup call and no extra code.
- **Why rejected:** It is a real film written in another system's format. Discarding it would lose a title. Here it happened to be a duplicate, but next year's list may hold IMDb ids for films that appear nowhere else.

### Alternative D: Silently drop ids TMDb does not recognise

- **How it would work:** Skip "not found" answers and analyse whatever came back.
- **Why it is attractive:** The output looks clean.
- **Why rejected:** Five candidates would vanish without trace. If any was a mistyped id for a film Kwame wanted, he would never know it had been left out.

## Consequences

- **What this buys:** A ledger that traces every line of the original file to its outcome, with a reason and its line number. The counts reconcile by construction, and a presentation page (`id_breakdown.html`) shows the whole picture in one view. Acquisition made 235 requests in 87 seconds (about 2.7 per second); a rerun makes none.
- **What this costs:** More code than deleting lines by hand, and one extra lookup call for each IMDb-format id.
- **What it costs the client if I am wrong:** The 5 "not found" ids most likely stood for real films someone mistyped or copied from another system. If any was a serious candidate, it is absent from the shortlist. The memo asks Adjoa to check those 5 entries against the original tracker and spreadsheet.
- **What would make me revisit this:** Next year's list arriving in a format this does not recognise (for example titles instead of ids), or more than about 5% of ids coming back "not found", which would point at a broken source rather than a few typos.

## What this survives

Adjoa rerunning this next year on about 500 titles, without me. The rules are written as whole-column checks that do not depend on the list's length or on which faults it contains, and they handle any number of blanks, placeholders, IMDb ids and repeats. The reconciliation check compares outcomes with the number of lines actually in the file, so it holds for any size. The self-test runs on a frozen copy of this year's list, so replacing the live list never breaks it. Already-fetched ids are never requested again, so a quarterly rerun only pays for new titles.
