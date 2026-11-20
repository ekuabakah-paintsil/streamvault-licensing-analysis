"""Presentation page: where every line of the candidate list went.

    python present_ids.py        # after run.py; writes outputs/id_breakdown.html

Reads outputs/ledger.csv (one row per line of id_list.csv) and builds a single
self-contained HTML page you can open in any browser and present from: the 127 -> 117 -> 112
funnel, the outcome summary, and every line with its reason. No internet needed to view it.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd  # noqa: E402

from streamvault import config  # noqa: E402

LABELS = {  # final_status -> (plain label, colour group, explanation for the room)
    "analysed_full": ("Analysed", "ok", "Fetched, released, has budget and revenue; in the analysis"),
    "analysed_no_usable_financials": ("Analysed, no financials", "warn",
                                      "Fetched and in scope, but budget or revenue missing"),
    "excluded_out_of_scope": ("Out of scope", "warn", "Real film, but unreleased, a short or a video release"),
    "excluded_duplicate": ("Duplicate", "dup", "Same film already listed on an earlier line"),
    "excluded_not_found_on_tmdb": ("Not on TMDb", "bad", "TMDb has no film with this id"),
    "excluded_fetch_failed": ("Fetch failed", "bad", "Request failed after retries; re-run to retry"),
    "excluded_failed_validation": ("Failed validation", "bad",
                                   "Returned by TMDb but broke the data contract; see quarantine.csv"),
    "excluded_imdb_unresolved": ("IMDb id unresolved", "bad", "IMDb-format id with no single TMDb match"),
    "excluded_blank_line": ("Blank line", "bad", "Empty line in the file"),
    "excluded_invalid_number": ("Invalid id", "bad", "A number that cannot be a TMDb id"),
    "excluded_not_an_id": ("Not an id", "bad", "Placeholder text, not an identifier"),
}


def esc(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).map(html.escape)


def main() -> None:
    led = pd.read_csv(config.OUTPUTS / "ledger.csv", dtype={"raw_value": str})
    # Re-read the raw values with NO missing-value guessing, or pandas turns the text "N/A" into NaN
    led["raw_value"] = pd.read_csv(config.OUTPUTS / "ledger.csv", usecols=["raw_value"], dtype=str,
                                   keep_default_na=False)["raw_value"]
    unknown = set(led["final_status"]) - set(LABELS)
    if unknown:
        raise SystemExit(f"Unlabelled outcome(s) in ledger: {unknown}. Add them to LABELS.")

    n_lines = len(led)
    n_distinct = int(led["id_status"].eq("candidate").sum())
    n_analysed = int(led["final_status"].str.startswith("analysed").sum())
    fetched_at = led.get("movie_fetched_at", pd.Series(dtype=str)).dropna()
    as_of = pd.to_datetime(fetched_at).min().strftime("%d %B %Y") if len(fetched_at) else "not recorded"

    lab = led["final_status"].map(lambda k: LABELS[k][0])
    grp = led["final_status"].map(lambda k: LABELS[k][1])

    # Summary: one row per outcome
    summ = (led.assign(label=lab, grp=grp)
               .groupby(["final_status", "label", "grp"], sort=False)
               .agg(n=("file_line", "size"), lines=("file_line", lambda s: ", ".join(s.astype(str))))
               .reset_index().sort_values("n", ascending=False))
    summ["why"] = summ["final_status"].map(lambda k: LABELS[k][2])
    summ["lines"] = summ["lines"].where(summ["n"].le(20), "(" + summ["n"].astype(str) + " lines)")
    summary_rows = "".join(
        "<tr><td><span class='tag " + summ["grp"] + "'>" + esc(summ["label"]) + "</span></td>"
        "<td class='num'>" + summ["n"].astype(str) + "</td><td>" + esc(summ["why"]) +
        "</td><td class='mono'>" + esc(summ["lines"]) + "</td></tr>")

    # Detail: one row per line of the source file (vectorised string building, no row loop)
    raw = led["raw_value"].fillna("")
    raw_cell = raw.where(raw.ne(""), "(empty)")
    title = esc(led.get("title", pd.Series("", index=led.index)))
    year = led.get("release_year", pd.Series(dtype=float)).astype("Int64").astype("string").fillna("")
    seg = esc(led.get("segment", pd.Series("", index=led.index)))
    reason = esc(led["note"])
    detail_rows = "".join(
        "<tr data-grp='" + grp + "'><td class='num'>" + led["file_line"].astype(str) +
        "</td><td class='mono'>" + esc(raw_cell) + "</td><td><span class='tag " + grp + "'>" +
        esc(lab) + "</span></td><td>" + title + "</td><td class='num'>" + year + "</td><td>" + seg +
        "</td><td class='muted'>" + reason + "</td></tr>")

    removed = n_lines - n_distinct
    missing = n_distinct - n_analysed
    page = TEMPLATE.format(
        n_lines=n_lines, n_distinct=n_distinct, n_analysed=n_analysed, removed=removed,
        missing=missing, as_of=as_of, summary_rows=summary_rows, detail_rows=detail_rows,
        total_check="OK" if summ["n"].sum() == n_lines else "DOES NOT RECONCILE")
    out = config.OUTPUTS / "id_breakdown.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out}  ({n_lines} lines -> {n_distinct} distinct ids -> {n_analysed} analysed)")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Candidate List Breakdown</title>
<style>
:root {{ --bg:#fafaf8; --card:#fff; --ink:#1c1c1a; --muted:#6b6b66; --line:#e4e3de;
  --ok:#1f7a4d; --ok-bg:#e3f2ea; --warn:#8a5a00; --warn-bg:#fbf0d9; --dup:#3d5a99; --dup-bg:#e6ecf8;
  --bad:#a33a2c; --bad-bg:#f8e4e0; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#161615; --card:#1f1f1d;
  --ink:#ecebe6; --muted:#a3a29b; --line:#33322f; --ok:#7fd1a5; --ok-bg:#183326; --warn:#e6bd6a;
  --warn-bg:#352a12; --dup:#9db4ec; --dup-bg:#1d2740; --bad:#f0a092; --bad-bg:#3a1f1a; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; letter-spacing:-.01em; }}
h2 {{ font-size:17px; margin:36px 0 12px; }}
.sub {{ color:var(--muted); margin:0 0 24px; }}
.funnel {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; }}
.step {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; }}
.step .big {{ font-size:40px; font-weight:650; line-height:1; font-variant-numeric:tabular-nums; }}
.step .lbl {{ font-weight:600; margin-top:6px; }}
.step .note {{ color:var(--muted); font-size:13px; margin-top:4px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ text-align:left; padding:8px 12px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); font-weight:600;
  position:sticky; top:0; background:var(--card); }}
tr:last-child td {{ border-bottom:none; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.mono {{ font-family:ui-monospace,Consolas,monospace; font-size:13px; }}
.muted {{ color:var(--muted); font-size:13px; }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:600;
  white-space:nowrap; }}
.tag.ok {{ color:var(--ok); background:var(--ok-bg); }} .tag.warn {{ color:var(--warn); background:var(--warn-bg); }}
.tag.dup {{ color:var(--dup); background:var(--dup-bg); }} .tag.bad {{ color:var(--bad); background:var(--bad-bg); }}
tfoot td {{ font-weight:650; }}
.filters {{ display:flex; flex-wrap:wrap; gap:8px; margin:0 0 12px; }}
.filters button {{ font:inherit; font-size:13px; padding:5px 12px; border-radius:999px; cursor:pointer;
  border:1px solid var(--line); background:var(--card); color:var(--ink); }}
.filters button[aria-pressed="true"] {{ background:var(--ink); color:var(--bg); border-color:var(--ink); }}
.foot {{ color:var(--muted); font-size:13px; margin-top:16px; }}
@media print {{ .filters {{ display:none; }} th {{ position:static; }} body {{ background:#fff; }} }}
</style></head>
<body><main>
<h1>Candidate List Breakdown</h1>
<p class="sub">Where every line of the candidate list ended up. Film data from TMDb as of {as_of}.</p>

<div class="funnel">
  <div class="step"><div class="big">{n_lines}</div><div class="lbl">Lines in the list</div>
    <div class="note">Every line accounted for below</div></div>
  <div class="step"><div class="big">{n_distinct}</div><div class="lbl">Distinct film ids</div>
    <div class="note">{removed} lines removed: repeats, blanks and non-ids</div></div>
  <div class="step"><div class="big">{n_analysed}</div><div class="lbl">Films analysed</div>
    <div class="note">{missing} ids not found on TMDb</div></div>
</div>

<h2>Outcome summary</h2>
<div class="card"><table>
<thead><tr><th>Outcome</th><th class="num">Lines</th><th>What it means</th><th>Line numbers in the list</th></tr></thead>
<tbody>{summary_rows}</tbody>
<tfoot><tr><td>Total</td><td class="num">{n_lines}</td><td colspan="2">Reconciliation check: {total_check}</td></tr></tfoot>
</table></div>

<h2>Every line</h2>
<div class="filters" role="group" aria-label="Filter lines">
  <button data-f="all" aria-pressed="true">All</button>
  <button data-f="ok" aria-pressed="false">Analysed</button>
  <button data-f="dup" aria-pressed="false">Duplicates</button>
  <button data-f="bad" aria-pressed="false">Problems</button>
  <button data-f="warn" aria-pressed="false">Other</button>
</div>
<div class="card"><table id="detail">
<thead><tr><th class="num">Line</th><th>Value in list</th><th>Outcome</th><th>Film</th><th class="num">Year</th>
<th>Type</th><th>Reason</th></tr></thead>
<tbody>{detail_rows}</tbody>
</table></div>
<p class="foot">Line numbers match the file, with line 1 as the header row. Generated by present_ids.py from the analysis ledger.</p>
</main>
<script>
document.querySelectorAll('.filters button').forEach(function (b) {{
  b.addEventListener('click', function () {{
    document.querySelectorAll('.filters button').forEach(function (x) {{ x.setAttribute('aria-pressed', x === b); }});
    var f = b.dataset.f;
    document.querySelectorAll('#detail tbody tr').forEach(function (r) {{
      r.style.display = (f === 'all' || r.dataset.grp === f) ? '' : 'none';
    }});
  }});
}});
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
