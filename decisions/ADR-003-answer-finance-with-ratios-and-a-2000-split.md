# ADR-003: Answer Finance's concern about older films with return ratios and a 2000 split, not inflation adjustment

- **Status:** Accepted
- **Date:** 2026-11-19
- **Decision owner:** Ekua Micah Abakah-Paintsil

## Context

Yaw in Finance distrusts figures for films released before 2000, citing inflation, currency reporting and the way box office used to be reported, and he will say so in the room. The brief requires the franchise against standalone comparison twice, across all years and from 2000 on, and requires any change between the two to be stated loudly.

- 41 of the 112 films were released before 2000: 33 franchise entries and 8 of the 16 standalones.
- StreamVault's business is licensing older films, so dropping them is not an option for Kwame.
- TMDb's revenue for an old film is usually its lifetime total, including re-releases. The five largest returns on the list are all old films, on both sides: three franchise entries (Star Wars, 1977, about 70x; Jaws, 1975, 67x; The Empire Strikes Back, 1980, 30x) and two standalones (The Good, the Bad and the Ugly, 1966, 32x; Pulp Fiction, 1994, 27x).

## Decision

I compare films on revenue divided by budget, which uses the same year's money on both sides of the division, so inflation cancels out without any adjustment. I split the windows at release year 2000 and report every result in both.

1. No inflation or currency adjustment is applied, because the measure does not need one.
2. The cut-off is release year 2000 or later, matching Yaw's own line, and is set in one place in the configuration.
3. Re-release revenue in older figures is stated as a limit, not corrected, because the data does not separate it.

Result: franchises lead in both windows, by 46% across all years and 32% from 2000 on (per film), or 14% and 17% (complete bundles). The recommendation does not change between windows.

## Alternatives considered

### Alternative A: Adjust old figures for inflation

- **How it would work:** Convert every budget and revenue to today's dollars using a price index.
- **Why it is attractive:** It is the standard answer to "old money is worth more", and it is what Yaw will expect to hear.
- **Why rejected:** It changes nothing in a ratio. Revenue and budget would both be multiplied by the same factor, so revenue divided by budget is unchanged. It would also bring in an outside dataset to maintain every quarter, for no effect on the answer. Adjustment would matter only for comparing dollar amounts across years, which this analysis never does.

### Alternative B: Drop every film released before 2000

- **How it would work:** Analyse only the 71 films from 2000 on.
- **Why it is attractive:** It removes Yaw's objection entirely.
- **Why rejected:** StreamVault licenses older films, so the older titles are the catalogue Kwame is buying. It would also halve the standalone group to 8 films. The 2000-on view is still reported in full; it just is not the only view.

### Alternative C: Choose a different cut-off year

- **How it would work:** Split at 1995 or 2005 instead.
- **Why it is attractive:** A later year might remove more of the re-release effect.
- **Why rejected:** 2000 is Yaw's own line, so it is the split that answers him directly. Any other year invites "why that year?" in the room, with no data to defend it.

## Consequences

- **What this buys:** A direct answer to Yaw: "the measure cancels inflation, and the recommendation is the same in the window you trust." The two windows sit side by side in every output, so a disagreement between them could not be hidden.
- **What this costs:** Re-release revenue is not corrected. A film from the 1970s has had decades and several cinema re-releases to accumulate revenue that a 2015 film has not, and the data cannot tell them apart.
- **What it costs the client if I am wrong:** If pre-2000 revenue is inflated by re-releases, the all-years figures flatter older films. That affects both sides (the five largest returns include three franchise films and two standalones), and the recommendation holds in the 2000-on window, where re-releases matter least. The cost is mainly that the all-years margins look larger than they really are.
- **What would make me revisit this:** The two windows ever pointing to different answers, which the pipeline would show on its printed summary; or Finance supplying figures that separate first-release from re-release revenue.

## What this survives

Adjoa rerunning this quarterly on about 500 titles. Both windows are computed on every run from a single cut-off value, so moving the line to another year is a one-line change with no rewrite. The ratio needs no external price data, so there is nothing extra to update each quarter. If a future list skews further toward older films, the all-years and 2000-on views will diverge visibly rather than silently.
