# Data findings: StreamVault licensing review

## Summary

The candidate list's 127 lines hold 112 films that TMDb could supply. The other 15 lines are 7 repeats of films already listed, 5 ids that do not exist, and 3 lines that are not ids at all. Every line is accounted for in `outputs/ledger.csv`, and the presentation page `outputs/id_breakdown.html` shows the whole breakdown.

**What the gap costs Kwame.** The 7 repeats and 3 non-ids cost nothing: no film behind them is lost, and the repeats would have distorted the figures had they been counted twice (F-05). The real cost is the 5 ids that match no film. Whatever titles they were meant to be, up to 5 of the 127 intended candidates (about 4%) were never assessed and cannot appear on the shortlist. That is recoverable: checking those 5 entries against the three original sources would identify them, and the next run would pick them up (F-04).

The film figures themselves are clean: no budget or revenue is zero or implausibly small, and nothing is missing. The problems that matter are in what the list contains, not in its values. The list holds each franchise's best-known films rather than whole bundles, and its standalone films are a small group of celebrated classics. Correcting the first problem cut the franchise lead from 46% to 14%. It did not change the recommendation, but it changed how strongly it can be made.

Evidence references: "notebook" is `explore/profile_candidates.ipynb`, which profiles the raw list and TMDb's raw answers independently of the analysis. Its last section confirms the two routes agree on every count.

## Reconciliation

| Stage | Rows | Delta | Reason |
|---|---|---|---|
| Lines in `id_list.csv` | 127 | | As received: one column, Windows line endings |
| Lines that can be an id | 124 | -3 | Blank (line 69), `-1` (line 30), `N/A` (line 111). Not sent to TMDb |
| Distinct ids | 117 | -7 | 6 repeated ids (lines 43, 60, 90, 91, 94, 102), plus the IMDb id on line 95, which resolved to 155, already on line 2 |
| Ids sent to TMDb | 117 | 0 | 2 requests each (details and credits) = 234, plus 1 IMDb lookup; 18 November 2026, 12:19 to 12:21 UTC |
| Films TMDb returned | 112 | -5 | Not found: lines 18, 35, 73, 93, 99 |
| Films analysed, with usable budget and revenue | 112 | 0 | None unreleased, short, zero or implausible |
| of which franchise / standalone | 96 / 16 | 0 | Franchise means listed in a TMDb collection; 32 collections |
| Films in the 2000-on window | 71 | -41 | 41 released before 2000 (33 franchise, 8 standalone). Window filter only; they stay in the all-years view |
| Credits TMDb returned | 7,827 cast, 24,931 crew | | Complete, kept in the per-film cache files (notebook section 6). Every film has a cast and at least one director |
| Credits the analysis reads | top 10 cast and directors per film | | Trimmed to what the analysis uses, to hold the time budget (ADR-005). Film count unchanged after every join (quality gate, every run) |
| Bundle check: films in the 32 franchises | 142 | +46 | The 96 franchise films on the list, plus 46 not on it: 39 released (3 with no figures), the rest upcoming or cancelled |

## Findings, ranked by risk

Ranked by how much each could move Kwame's recommendation, not by how odd it looked.

### F-01: The list holds each franchise's best-known films, not whole bundles. Severity: High

- **What it is:** Studios sell a franchise as a whole bundle, but only 13 of the 32 franchises on the list are complete. The missing films are mostly later sequels.
- **How I detected it:** 9 franchises had only 1 film on the list (`kpi_collections.csv`; notebook section 5), which raised the question. The bundle completeness check then fetched every franchise's full film list and the figures for the films missing from it (`improvement/`).
- **Scale:** 39 released films missing across 19 franchises. Jaws: 1 of 4 films on the list. Jurassic Park: 3 of 8. Star Wars: 6 of 9.
- **Effect on the client's number:** The typical bundle's return falls from 5.56x to 4.36x (all years) and from 5.12x to 4.49x (2000 on). The franchise lead over standalones falls from 46% to 14%, and from 32% to 17%. Single bundles fall further: Jaws from 67.2x to 11.3x, Hannibal Lecter from 14.4x to 4.5x, Ghostbusters from 9.9x to 3.8x.
- **What I did about it:** Reported the headline on complete bundles, ranked the franchise shortlist on whole-bundle return and weakest film (ADR-002, ADR-004), and named the missing films for negotiators.
- **Residual risk:** 3 released films have no budget or revenue, so their bundles' figures cover fewer films than they seem. A database franchise may not match the bundle a studio actually offers.

### F-02: The standalone group is small and hand-picked. Severity: High

- **What it is:** Only 16 of the 112 films are standalones, and only 8 from 2000 on. All 16 are celebrated films rated 8.0 or higher.
- **How I detected it:** Group sizes in `kpi_segments.csv`; all 16 read by title in notebook section 5.
- **Scale:** 16 films against 96 franchise films; 8 against 63 from 2000 on.
- **Effect on the client's number:** The standalone figure (3.84x) rests on 8 films in the window Finance trusts. Removing its single best film (Spirited Away, 14.47x) moves it to 3.24x. The spread is wide: the middle half runs from 2.45x to 12.85x across all years.
- **What I did about it:** Put the group size beside every figure, tested each group without its best film (franchises still lead), and said in the memo that the comparison is against celebrated standalones, not standalones in general.
- **Residual risk:** Unlike the franchise side (F-01), this cannot be corrected: there is no "complete set" of standalone films. A broader standalone list could narrow the 15% franchise lead further.

### F-03: Older films' revenue includes decades of re-releases. Severity: Medium

- **What it is:** TMDb's revenue for an old film is usually its lifetime total, including cinema re-releases, which a recent film has not had time to collect.
- **How I detected it:** The "revenue over 50 times budget" flag raised Star Wars (1977, about 70x) and Jaws (1975, 67x). The five largest returns on the list are all pre-2000 films (notebook section 5).
- **Scale:** 41 of 112 films were released before 2000.
- **Effect on the client's number:** The franchise lead is 46% across all years against 32% from 2000 on (per film). Part of that difference is likely re-release revenue, on both sides: the five largest returns are three franchise films and two standalones.
- **What I did about it:** Reported both windows everywhere. Used return ratios, in which inflation cancels (ADR-003). The recommendation is the same in both windows.
- **Residual risk:** The data cannot separate first-release from re-release revenue, so the all-years margins are probably overstated.

### F-04: Five ids do not exist on TMDb. Severity: Medium

- **What it is:** Lines 18, 35, 73, 93 and 99 hold ids (7,733,901 to 9,412,888) that TMDb answers "not found" for.
- **How I detected it:** The id audit flagged them as far larger than every other id on the list (notebook section 2). TMDb's not-found answers confirmed it, and each is cached (notebook section 3).
- **Scale:** 5 of 127 lines.
- **Effect on the client's number:** None on any computed figure, but whatever films they were meant to be are missing from the shortlist.
- **What I did about it:** Recorded each with its line number and reason, and did not guess what was meant (ADR-001).
- **Residual risk:** If one was a serious candidate, it was never assessed. Adjoa should check these 5 entries against the original tracker, the inherited spreadsheet and the studio's batch.

### F-05: Seven lines repeat a film already on the list. Severity: Medium (resolved)

- **What it is:** Ids 155, 278, 550, 603, 680 and 1891 each appear twice, and the IMDb id on line 95 is a third route to 155 (The Dark Knight).
- **How I detected it:** The id audit (notebook section 2), which pairs every repeat with the line it repeats.
- **Scale:** 7 lines, 6 films: three franchise entries and three standalones (The Shawshank Redemption, Fight Club, Pulp Fiction).
- **Effect on the client's number:** Had they been counted twice, the standalone figure would have fallen from 3.84x to 3.24x, because three of 16 standalones would have carried double weight, inflating the franchise lead from 46% to about 73%.
- **What I did about it:** Kept the first line of each, and labelled the later lines with the line they repeat (ADR-001).
- **Residual risk:** None. Three sources overlapping explains the repeats; the same check will catch them next year.

### F-06: One id is in IMDb format, not TMDb format. Severity: Low

- **What it is:** Line 95 holds `tt0468569`, an IMDb identifier.
- **How I detected it:** The id audit's IMDb pattern check (notebook section 2).
- **Scale:** 1 line.
- **Effect on the client's number:** None in the end: TMDb's lookup resolved it to 155, already on the list.
- **What I did about it:** Resolved it rather than discarding it, and accepted the translation only because there was exactly one match (ADR-001).
- **Residual risk:** Low. Next year an IMDb id may stand for a film that appears nowhere else, and the same lookup will handle it.

### F-07: Three lines are not ids at all. Severity: Low

- **What it is:** A blank line (69), `-1` (30) and `N/A` (111).
- **How I detected it:** Reading every value as text with no missing-value guessing (notebook sections 1 and 2). A default reading would have turned `N/A` into an empty cell and could have skipped the blank line, hiding both.
- **Scale:** 3 lines.
- **Effect on the client's number:** None, beyond the 127 not reconciling if they had been hidden.
- **What I did about it:** Labelled and kept them in the ledger, and never sent them to TMDb (ADR-001).
- **Residual risk:** None.

### F-08: Some franchises have films still to come. Severity: Low

- **What it is:** Several franchise lists include films not yet released, such as Avengers: Doomsday (in post-production), Avengers: Secret Wars (planned) and Incredibles 3 (in production), and one cancelled film (Mad Max: The Wasteland).
- **How I detected it:** The bundle completeness check (`bundle_members.csv`).
- **Scale:** A handful of films across the 32 franchises.
- **Effect on the client's number:** None: unreleased films are excluded from every return.
- **What I did about it:** Counted upcoming and cancelled films separately, so neither is treated as a flop nor listed as coming when it is not.
- **Residual risk:** A deal-term risk rather than a data risk: if a bundle's terms include future films, their value is unknown. The Avengers is on the shortlist.

## Looked wrong, is not wrong

| Apparent problem | Why it looks wrong | Why it is actually fine |
|---|---|---|
| Star Wars (1977) returned about 70 times its budget, Jaws (1975) 67 times | Returns over 50x look like unit errors | Two of the most profitable films ever made. The values match live TMDb exactly (spot-check). The headline uses the median, which a few extreme films cannot drag |
| Alien (1979) and Alien³ (1992) flagged as the same title | My title-matching strips special characters, so "Alien³" became "alien" | Different films in the same franchise: a sequel, not a duplicate or a remake. Both kept |
| No budget or revenue is zero, and none is under $1,000 | An uncleaned, three-source list would be expected to have gaps | Checked on every film (notebook section 4): the 112 films are major releases with complete figures. "Plausible" is not "correct", which is why the spot-check exists |
| No two different ids share a title and year, or an IMDb id | The brief warns that a duplicate can be two different releases | Checked: none on this list. All 7 duplicates are the same id repeated, which is always the same film |
| The Windows line endings in `id_list.csv` | Hidden characters at the end of every line (all 128 lines, notebook section 1) | Read correctly; no value carries a stray character or surrounding space (notebook section 2) |
| `WALL┬╖E` in some saved console output | Looks like a corrupted title | A display encoding issue when the console writes to a text file. The title is stored correctly in every output |
| 9 films have two or more directors (up to three) | One director per film is the usual expectation | Co-directing is real (for example, the Wachowskis on The Matrix sequels). Every credited director is kept, and each is counted once per film in the talent analysis (notebook section 6) |
| All 16 standalones are rated 8.0 or higher | Looks like a filter or a bias in the data | It is the list itself: someone chose celebrated films. Recorded as a finding about the list (F-02), not a fault in the data |

## Could not verify

- **Whether TMDb's figures are true.** A spot-check of 16 deliberately chosen films across 7 fields (112 comparisons) matched live TMDb exactly, 4 and 12.5 hours after the fetch, and a deliberately corrupted value was caught. That proves the analysis did not change the source; it cannot prove the source is right. TMDb is community-edited and not audited against studio figures.
- **How much of older films' revenue is re-releases** (F-03).
- **What the 5 missing ids were meant to be** (F-04).
- **Figures for 3 released franchise films** with no budget or revenue recorded (F-01).
- **Whether TMDb's franchises match the bundles studios actually offer.**
- **Licence prices and streaming performance.** Every return is cinema earnings against production budget. It ranks titles and prices them relative to each other; it does not say what to pay in dollars.
