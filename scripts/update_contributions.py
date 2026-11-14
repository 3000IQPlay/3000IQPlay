"""Redraw the contribution tiles in assets/ from GitHub's GraphQL API.

Run from the repo root with a token in GITHUB_TOKEN: python3 scripts/update_contributions.py
`--test` runs the self-check (no network).
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path
from xml.dom import minidom

LOGIN = "3000IQPlay"
LEVELS = ["#1e1b25", "#3d2549", "#6d3a7c", "#b44f73", "#f07a58"]
Q_CREATED = "query($l:String!){user(login:$l){createdAt}}"
Q_YEAR = ("query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t)"
          "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}")
SANS = "'Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif"


def gql(query, **variables):
    token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN is required")
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": query, "variables": variables}).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def fetch_days():
    """Every day since the account was created -> contribution count."""
    created = dt.date.fromisoformat(gql(Q_CREATED, l=LOGIN)["createdAt"][:10])
    now = dt.datetime.now(dt.timezone.utc)
    days = {}
    for year in range(created.year, now.year + 1):
        end = now.strftime("%Y-%m-%dT%H:%M:%SZ") if year == now.year else f"{year}-12-31T23:59:59Z"
        cal = gql(Q_YEAR, l=LOGIN, f=f"{year}-01-01T00:00:00Z", t=end)
        for week in cal["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[dt.date.fromisoformat(d["date"])] = d["contributionCount"]
    return days


def longest_streak(days):
    best = run = 0
    prev = None
    for d in sorted(days):
        if prev is not None and (d - prev).days != 1:
            run = 0
        run = run + 1 if days[d] else 0
        best = max(best, run)
        prev = d
    return best


def heatmap(days, today):
    """53 week columns ending today, Sunday on top. Returns (cells, total) with cells = (col, row, level)."""
    start = today - dt.timedelta(days=(today.weekday() + 1) % 7 + 52 * 7)
    counts = [days.get(start + dt.timedelta(i), 0) for i in range((today - start).days + 1)]
    nonzero = sorted(c for c in counts if c)
    cuts = [nonzero[int(len(nonzero) * p)] for p in (.25, .5, .75)] if nonzero else []
    cells = [(i // 7, i % 7, 0 if c == 0 else 1 + sum(c > t for t in cuts)) for i, c in enumerate(counts)]
    return cells, sum(counts)


def frame(w, title, body, glow, delay):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="220" viewBox="0 0 {w} 220" role="img" aria-labelledby="title">
  <title id="title">{title}</title>
  <style>
    .sans{{font-family:{SANS}}}
    .lbl{{font-size:13px;font-weight:600;letter-spacing:3px;fill:#7d768a}}
    .sheen{{animation:sheen 10s ease-in-out {delay}s infinite}}
    @keyframes sheen{{0%{{transform:translateX(-400px)}}14%,100%{{transform:translateX(1200px)}}}}
    @media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
  </style>
  <defs>
    <radialGradient id="glow" cx="{glow}" cy="0" r="1"><stop offset="0" stop-color="#904e95" stop-opacity=".2"/><stop offset=".7" stop-color="#904e95" stop-opacity="0"/></radialGradient>
    <linearGradient id="num" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff9a76"/><stop offset=".55" stop-color="#e96443"/><stop offset="1" stop-color="#a24f8c"/></linearGradient>
    <linearGradient id="sheenG" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".06"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <clipPath id="frame"><rect width="{w}" height="220" rx="22"/></clipPath>
  </defs>
  <g clip-path="url(#frame)">
    <rect width="{w}" height="220" fill="#111015"/>
    <rect width="{w}" height="220" fill="url(#glow)"/>
    <g transform="rotate(20 {w // 2} 110)"><rect class="sheen" x="0" y="-250" width="170" height="720" fill="url(#sheenG)"/></g>
  </g>
{body}
  <rect x=".5" y=".5" width="{w - 1}" height="219" rx="21.5" fill="none" stroke="#fff" stroke-opacity=".08"/>
</svg>
"""


def render_heatmap(days, today):
    cells, total = heatmap(days, today)
    rects = "".join(f'<rect x="{36 + c * 13.5:g}" y="{74 + r * 13.5:g}" width="10.5" height="10.5" rx="2.5" fill="{LEVELS[lv]}"/>'
                    for c, r, lv in cells)
    legend = "".join(f'<rect x="{628 + i * 13.5:g}" y="189" width="10.5" height="10.5" rx="2.5" fill="{col}"/>'
                     for i, col in enumerate(LEVELS))
    body = f"""  <g class="sans">
    <text class="lbl" x="36" y="50">CONTRIBUTIONS</text>
    <text x="756" y="50" text-anchor="end" font-size="14" fill="#7d768a">last 12 months</text>
  </g>
  <g>{rects}</g>
  <g class="sans" font-size="13" fill="#7d768a">
    <text x="36" y="199" font-size="15" fill="#a59fae">{total:,} contributions in the last year</text>
    <text x="620" y="199" text-anchor="end">less</text>
    <text x="700" y="199">more</text>
  </g>
  <g>{legend}</g>"""
    return frame(792, f"Contributions: {total:,} in the last year", body, ".2", 2.0)


def render_stats(days):
    total, streak = sum(days.values()), longest_streak(days)
    unit = "day" if streak == 1 else "days"
    body = f"""  <g class="sans">
    <text class="lbl" x="32" y="50">TOTAL CONTRIBUTIONS</text>
    <text x="30" y="116" font-size="64" font-weight="700" letter-spacing="-2" fill="url(#num)">{total:,}</text>
    <text class="lbl" x="32" y="156">LONGEST STREAK</text>
    <text x="32" y="194" font-size="30" font-weight="700" fill="#f5f2f8">{streak} {unit}</text>
  </g>"""
    return frame(390, f"{total:,} total contributions, longest streak {streak} {unit}", body, "1", 2.25)


def write(days, today):
    Path("assets/contributions.svg").write_text(render_heatmap(days, today), encoding="utf-8")
    Path("assets/contribution-stats.svg").write_text(render_stats(days), encoding="utf-8")
    print(f"total {sum(days.values())}, longest streak {longest_streak(days)}")


def test():
    d0 = dt.date(2026, 1, 1)
    days = {d0 + dt.timedelta(i): 0 for i in range(400)}
    for i in (10, 11, 12, 50):  # 3-day run, then a single day
        days[d0 + dt.timedelta(i)] = 2
    assert longest_streak(days) == 3
    assert longest_streak({d0: 1, d0 + dt.timedelta(2): 1}) == 1  # a missing date breaks the run
    today = d0 + dt.timedelta(399)
    cells, total = heatmap(days, today)
    assert 365 <= len(cells) <= 371 and max(c for c, _, _ in cells) == 52 and cells[0][1] == 0
    assert all(0 <= lv <= 4 for _, _, lv in cells) and total == 2  # only day 50 is inside the last 53 weeks
    minidom.parseString(render_heatmap(days, today))
    minidom.parseString(render_stats(days))
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        test()
        sys.exit()
    write(fetch_days(), dt.datetime.now(dt.timezone.utc).date())
