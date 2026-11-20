# Data contract

What every record pulled from TMDb must satisfy before it reaches the analysis. The rules are enforced by `src/streamvault/validate.py`, which runs straight after flattening (see the pipeline diagram in the README).

## Why a contract

TMDb is a source we do not control. Its format can change, and a single record can arrive broken. Without a check at the door, a negative budget or a rating of 14 would flow into the medians quietly and nobody would know. The contract states what "well-formed" means, so a bad record is caught by name instead of distorting a number.

## Validation is not the quality flags

| Question | Answered by | Example | What happens |
|---|---|---|---|
| Is the record possible? | `validate.py` (this contract) | Budget of -1, rating of 14, no title | Quarantined: removed from the analysis, listed in `outputs/quarantine.csv` |
| Is a valid record plausible? | `quality.py` (flags) | Budget of $5, a 70x return, unreleased film | Kept and flagged; the cleaning rules decide whether it counts |

## Level 1: structure

The tables must have these columns. If any is missing, TMDb's response format has changed and the run stops before anything is written.

| Table | Required columns |
|---|---|
| Film | tmdb_id, returned_id, title, release_date, release_status, budget, revenue, runtime, vote_average, vote_count, collection_id, fetched_at |
| Cast | tmdb_id, person_id, name, order |
| Crew | tmdb_id, person_id, name, job |

## Level 2: each record

A film that breaks any rule is quarantined, together with its cast and crew. A cast or crew row that breaks a rule is dropped on its own; the film stays.

| Level | Rule | Why it matters |
|---|---|---|
| Film | Returned an id | Without it the film cannot be joined to the list |
| Film | Has a title | A film with no title cannot be reported |
| Film | Release status is a known value (Rumored, Planned, In Production, Post Production, Released, Canceled) | The "not released" flag depends on it |
| Film | Released films have a release date | The time windows depend on it |
| Film | Budget present and not negative | TMDb records an unknown budget as 0, never as a negative |
| Film | Revenue present and not negative | Same as budget |
| Film | Runtime not negative (may be missing) | The short-film flag depends on it |
| Film | Rating between 0 and 10 | TMDb's scale is 0 to 10 |
| Film | Vote count not negative | A count cannot be negative |
| Film | Franchise id positive if present (empty means standalone) | The franchise split depends on it |
| Film | Fetch time recorded | Flags are judged as of each film's fetch date |
| Cast | Person id positive, billing order not negative, name present | The talent analysis depends on them |
| Crew | Person id positive, job present, name present | Same as cast |

## Level 3: threshold

If more than 5% of films (`QUARANTINE_MAX_SHARE` in `config.py`) break the contract in one run, the problem is the source, not a few records. The run stops and writes nothing, rather than analysing whatever is left.

## Where a quarantined film goes

- `outputs/quarantine.csv`: one row per record per broken rule.
- `outputs/validation.csv`: one row per rule, with how many records it checked and how many failed.
- `outputs/ledger.csv`: the film's line is marked `excluded_failed_validation`, with the rules it broke as the note, so every line of the list is still accounted for.
- The quality gate checks that every film TMDb returned is either analysed or quarantined.
- Nothing is deleted from the cache in `data/raw/`; a fixed record at TMDb is picked up on the next fetch.

On the data fetched on 18 November 2026, all 112 films, 1,119 cast rows and 122 crew rows passed every rule; nothing was quarantined (`outputs/validation.csv`).

Author: Ekua Micah Abakah-Paintsil
