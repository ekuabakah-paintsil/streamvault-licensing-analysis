# ADR-002: Judge franchise against standalone on the median return per film, and confirm it on complete bundles

- **Status:** Accepted
- **Date:** 2026-11-19
- **Decision owner:** Ekua Micah Abakah-Paintsil

## Context

Kwame's question is whether franchise bundles or standalone hits are the better buy. The brief does not say how to tell a franchise from a standalone, or how to measure "better".

- TMDb records each film's franchise in a field called `belongs_to_collection`. The lab's guidance is that an empty value means a standalone film.
- On that rule the 112 films split into 96 franchise films (in 32 franchises) and 16 standalones. From 2000 on, it is 63 against 8.
- Returns are very uneven. Star Wars (1977) earned about 70 times its budget and The Good, the Bad and the Ugly about 32 times, while most films sit between 2 and 8 times.
- The list mostly holds each franchise's best-known films, but studios sell a franchise as a whole bundle.

## Decision

A film with no TMDb collection is a standalone; any other film is a franchise entry. The headline measure is the median of revenue divided by budget, per film, reported with the number of films behind it. The result is then retested six other ways and, finally, on complete bundles that include every released film in each franchise.

| Measure | All years: franchise vs standalone | 2000 on: franchise vs standalone |
|---|---|---|
| Median per film (headline) | 5.62x vs 3.84x (96 vs 16 films) | 5.05x vs 3.84x (63 vs 8) |
| Average per film | 8.54x vs 8.28x | 5.41x vs 4.90x |
| Total revenue over total budget | 5.58x vs 4.85x | 5.08x vs 4.24x |
| Franchises with 2 or more films on the list | 5.53x vs 3.84x | 5.19x vs 3.84x |
| Without each group's single best film | 5.53x vs 3.24x | 5.03x vs 3.24x |
| Per bundle, list's films only | 5.56x vs 3.84x (32 bundles) | 4.55x vs 3.84x (24 bundles) |
| **Per bundle, complete** | **4.36x vs 3.84x (32 bundles)** | **4.49x vs 3.84x (15 bundles)** |

Franchises come out ahead in all 14 comparisons. Counting the missing films shrinks the lead from 46% to 14% across all years, and from 32% to 17% from 2000 on.

The complete-bundle row compares a whole bundle with a single standalone film. That mixes levels on purpose: it is the choice Kwame faces, because a bundle can only be bought whole and a standalone only on its own. As a like-for-like check, every released film in every franchise was also compared film by film with the standalones: 5.06x against 3.84x across all years (132 franchise films) and 5.21x against 3.84x from 2000 on (54 films). Both levels point the same way, so the recommendation does not depend on which is compared. The memo quotes the bundle-level figures because they are the more cautious of the two.

## Alternatives considered

### Alternative A: Average return per film

- **How it would work:** Compare the mean of revenue divided by budget in each group.
- **Why it is attractive:** Simple, familiar, and uses every film's full value.
- **Why rejected:** A handful of extreme films decide it. Across all years the averages are almost equal (8.54x against 8.28x) because a few standalone classics earned 15 to 32 times their budget. The average describes the jackpots, not the typical film Kwame would actually license. It stays in the report as a tested alternative, and it still favours franchises.

### Alternative B: Total revenue over total budget

- **How it would work:** Add up all revenue and all budget in each group and divide.
- **Why it is attractive:** It answers "for every dollar spent, how many came back".
- **Why rejected:** Each film counts in proportion to its budget, so a few $200M productions dominate the franchise side. Kwame licenses titles, not production budgets. It also favours franchises (5.58x against 4.85x), so the choice does not change the answer.

### Alternative C: Judge bundles only on the films on the list

- **How it would work:** Treat a franchise as the films that happen to be on the candidate list.
- **Why it is attractive:** It needs no data beyond what the brief supplied.
- **Why rejected:** The list is not the bundle. Jaws appears as one film returning 67x, but the studio would sell all four Jaws films, which together returned 11.3x. Only 13 of the 32 franchises are complete on the list. This is the measure I used until the bundle check, and it overstated the franchise lead roughly threefold.

### Alternative D: Reclassify films by my own judgement of what is a series

- **How it would work:** Move any standalone I recognise as part of a series into the franchise group.
- **Why it is attractive:** It could correct gaps in TMDb's records.
- **Why rejected:** It replaces a written, repeatable rule with my opinion, and Adjoa could not reproduce it. I read all 16 standalones by title and found none that is obviously part of a series.

## Consequences

- **What this buys:** A recommendation that does not depend on the choice of measure. Every alternative still points to franchises, and the complete-bundle test closes the biggest hole in the candidate list. Group sizes sit beside every figure, so nobody mistakes 8 films for a large sample.
- **What this costs:** The honest headline is less dramatic. The lead is about 15%, not 46%, and the memo has to say so.
- **What it costs the client if I am wrong:** If standalones were in fact the better buy, part of the $14M goes to bundles that return less than single titles would have. The lead is modest, so the memo recommends franchises selectively (complete bundles with a strong weakest film), not franchises in general. The standalone side cannot be corrected the same way: its 16 films are celebrated classics, and no complete set of standalone films exists to check them against.
- **What would make me revisit this:** Any of the tested measures favouring standalones on a rerun, or the complete-bundle lead falling below about 5%, which would be too small to choose on. A cleaning-rule check also reruns every time, but on this list it could not move anything, because no film had a zero or implausible budget or revenue.

## What this survives

Adjoa rerunning this on about 500 titles. The rule for franchise versus standalone is one line of code, the median is not thrown by a few extreme films, and all seven measures are recomputed on every run with a flag that turns true if any of them flips the answer. With 500 titles the standalone group should be larger, which makes its median more trustworthy than today's 16 films. The complete-bundle check is cached and only fetches franchises it has not seen before.
