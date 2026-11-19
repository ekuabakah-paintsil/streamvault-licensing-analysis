# Improvement beyond the brief: Bundle completeness check

## The problem it solves

Studios sell a franchise as a bundle: every film in it, or none. Kwame's candidate list was assembled from three sources over four years, and it mostly holds each franchise's best-known films. The franchise figures in the main analysis therefore describe the films someone chose to list, not the bundle StreamVault would actually be buying.

That gap sits exactly on the argument inside Kwame's team. Half of them say StreamVault overpays for weak middle entries, and the list could not test that claim, because the weak entries were mostly never put on it. Jaws is the clearest case. The list holds the 1975 original, which returned 67 times its budget, but the studio would sell all four Jaws films, and the three sequels were not on the list at all.

The brief left this exposed: it asks for a franchise recommendation and a deal note on a bundle, but supplies only part of each bundle.

## What I built

A check that looks up every franchise's complete film list from the same public film database the brief specified, fetches the figures for every film the candidate list left out, and compares what the list says each bundle returns with what the whole bundle actually returned.

- **How to run it:** `python improvement/bundle_check.py` after the main analysis; `--offline` reuses cached data with no requests.
- **Code:** the script in this folder, plus `src/streamvault/bundles.py`, which reuses the main analysis's cached, throttled fetcher and its table-building code. The main analysis is unchanged.
- **Outputs:**
  - `outputs/bundle_completeness.csv`: one row per franchise, with films in the franchise, films on the list, which released films are missing (by name), the return on the list's films against the return on the whole bundle, and the weakest film in each.
  - `outputs/bundle_members.csv`: one row per film per franchise, marked on or off the list.
  - `outputs/bundle_headline.csv`: the franchise against standalone comparison rerun with complete bundles, in both time windows.
- **Films not yet released** are counted separately and never treated as flops: upcoming films (announced or in production) apart from cancelled ones, so a negotiator never sees a cancelled film listed as coming.

What it found on this year's list:

| | Result |
|---|---|
| Franchises checked | 32, holding 142 films |
| Franchises complete on the candidate list | 13 of 32 |
| Released films missing from the list | 39, of which 3 have no budget or revenue recorded |
| Typical bundle, list's films only | 5.56x its budget (all years), 5.12x (2000 on) |
| **Typical bundle, every released film** | **4.36x (all years), 4.49x (2000 on)** |
| Typical standalone film | 3.84x in both windows |
| Recommendation | Unchanged: franchises still lead, by 14% (all years) and 17% (2000 on), down from 46% and 33% |

The franchises the list flattered most, with what the whole bundle returned and its weakest film:

| Franchise | Films on list | List says | Whole bundle | Weakest film |
|---|---|---|---|---|
| Jaws | 1 of 4 | 67.2x | 11.3x | 2.3x |
| The Hannibal Lecter films | 1 of 3 | 14.4x | 4.5x | 2.7x |
| Ghostbusters | 1 of 4 | 9.9x | 3.8x | 2.0x |
| Jurassic Park | 3 of 8 | 8.9x | 5.0x | 1.5x |
| Star Wars | 6 of 9 | 10.8x | 6.2x | 2.2x |

## What it is worth to Kwame

- **It tests his recommendation where it was weakest.** Before this check, "franchises win" rested on the films someone happened to list. It now holds with every film in each bundle counted, so it can be defended against the "weak middle entries" objection with numbers rather than opinion.
- **It sizes the edge honestly.** The franchise lead is about 15%, not the 45% the list suggests. Kwame hears that from his own analysis in October rather than from Finance in November, and the memo can recommend franchises selectively instead of across the board.
- **It strengthens the deal note.** The Lord of the Rings is complete on the list, all 3 films, and its weakest film returned 9.37x, so its figures describe the whole bundle. Its premium can be argued without a hidden-sequel caveat.
- **It arms the negotiators.** For every franchise they get the missing films by name, the weakest film in the whole bundle, and which franchises have films still to come. Two Avengers films are announced (one in post-production, one planned), so the terms need to say whether they are included and at what price. Three franchises have a recent film that barely broke even or lost money: The Matrix (0.82x), Mad Max (1.04x) and Indiana Jones (1.30x).
- **It answers the question Kwame could not.** Last quarter's passed-on five-film bundle can be judged the same way next time: one franchise list, one number for the whole bundle.

And to Adjoa: it runs on the same command pattern as the main analysis, caches everything, and only fetches franchises it has not seen before, so it costs almost nothing to rerun each quarter on a larger list.

## What it cost

- **Requests:** 78 extra requests to the public film database, once (32 franchise lists, then the 46 films not on the candidate list), at the same throttled pace as the main fetch, in under a minute. A rerun makes none.
- **Code:** one module and one script, about 200 lines together. No change to the main analysis or its outputs.
- **Run time:** about a second from cache when the laptop is warm. It reads about 80 cached files individually, so the first run after the laptop has been idle may take a few seconds. It is a separate step, so it does not count against the main analysis's 5-second budget.
- **Limits, stated rather than hidden:**
  - 3 released films in these franchises have no budget or revenue recorded. They are counted and named, but cannot be judged; where they sit in a bundle, its whole-bundle figure covers fewer films than it seems.
  - A franchise as the database defines it may not match the bundle a studio actually offers. A studio may split or combine series differently, and the check cannot know.
  - Like the whole analysis, it measures cinema earnings against production budget, not the licence price or streaming value.
