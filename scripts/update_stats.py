"""Refresh the rounded stats on the README tiles in assets/.

Project cards get rounded star counts (347 -> "340+"); assets/stats.svg shows rounded
total contributions, rounded total stars and the longest streak. Rounded numbers only
change every few stars/contributions, so this rarely produces a commit.

Run from the repo root: python3 scripts/update_stats.py   (GITHUB_TOKEN needed for contributions)
`--test` runs the self-check (no network).
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from xml.dom import minidom

LOGIN = "3000IQPlay"
TILES = {
    "obfuscator-list": "assets/project-obfuscator-list.svg",
    "client-library": "assets/project-client-library.svg",
    "AntiRAT-21": "assets/project-antirat-21.svg",
    "IQ-Docs": "assets/project-iq-docs.svg",
}
NUM = r"[\d.k+]+"
SANS = "'Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif"
Q_CREATED = "query($l:String!){user(login:$l){createdAt}}"
Q_YEAR = ("query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t)"
          "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}")


def rounded(n):
    """Round down to a 'nice' number so the label stays true as counts grow."""
    if n < 10:
        return str(n)
    if n < 50:
        return f"{n // 5 * 5}+"
    if n < 1000:
        return f"{n // 10 * 10}+"
    return f"{n // 100 / 10:g}k+"


def api(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def repo_stars():
    """Stars of every repo the user owns (forks excluded)."""
    stars, page = {}, 1
    while batch := api(f"https://api.github.com/users/{LOGIN}/repos?type=owner&per_page=100&page={page}"):
        stars.update({r["name"]: r["stargazers_count"] for r in batch if not r["fork"]})
        page += 1
    return stars


def gql(query, **variables):
    body = api("https://api.github.com/graphql", {"query": query, "variables": variables})
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def contribution_days():
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


def apply_stars(svg, n):
    label, unit = rounded(n), "star" if n == 1 else "stars"
    svg, a = re.subn(rf'(<text[^>]*class="stars"[^>]*>){NUM} stars?(</text>)', rf"\g<1>{label} {unit}\g<2>", svg)
    svg, b = re.subn(rf'(<text[^>]*class="stars"[^>]*>){NUM}(</text>)', rf"\g<1>{label}\g<2>", svg)
    svg, c = re.subn(rf"{NUM} stars?(</title>)", rf"{label} {unit}\g<1>", svg)
    if a + b != 1 or c != 1:
        raise ValueError("tile layout changed: expected one star count and one title")
    return svg


def render_strip(contributions, stars, streak):
    unit = "day" if streak == 1 else "days"
    cols = [("CONTRIBUTIONS", rounded(contributions), "url(#num)"),
            ("STARS EARNED", rounded(stars), "url(#num)"),
            ("LONGEST STREAK", f"{streak} {unit}", "#f5f2f8")]
    body = "".join(f'\n    <text class="lbl" x="{40 + i * 396}" y="62">{lbl}</text>'
                   f'\n    <text x="{38 + i * 396}" y="128" font-size="56" font-weight="700" letter-spacing="-1.5" fill="{fill}">{val}</text>'
                   for i, (lbl, val, fill) in enumerate(cols))
    title = f"{rounded(contributions)} contributions, {rounded(stars)} stars earned, longest streak {streak} {unit}"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1188" height="170" viewBox="0 0 1188 170" role="img" aria-labelledby="title">
  <title id="title">{title}</title>
  <style>
    .sans{{font-family:{SANS}}}
    .lbl{{font-size:13px;font-weight:600;letter-spacing:3px;fill:#7d768a}}
    .sheen{{animation:sheen 10s ease-in-out 2s infinite}}
    @keyframes sheen{{0%{{transform:translateX(-400px)}}14%,100%{{transform:translateX(1600px)}}}}
    @media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
  </style>
  <defs>
    <radialGradient id="glow" cx=".5" cy="1.2" r=".9"><stop offset="0" stop-color="#904e95" stop-opacity=".22"/><stop offset="1" stop-color="#904e95" stop-opacity="0"/></radialGradient>
    <linearGradient id="num" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff9a76"/><stop offset=".55" stop-color="#e96443"/><stop offset="1" stop-color="#a24f8c"/></linearGradient>
    <linearGradient id="sheenG" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".06"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <clipPath id="frame"><rect width="1188" height="170" rx="22"/></clipPath>
  </defs>
  <g clip-path="url(#frame)">
    <rect width="1188" height="170" fill="#111015"/>
    <rect width="1188" height="170" fill="url(#glow)"/>
    <g transform="rotate(20 594 85)"><rect class="sheen" x="0" y="-300" width="170" height="770" fill="url(#sheenG)"/></g>
  </g>
  <g stroke="#fff" stroke-opacity=".08"><line x1="396.5" y1="36" x2="396.5" y2="134"/><line x1="792.5" y1="36" x2="792.5" y2="134"/></g>
  <g class="sans">{body}
  </g>
  <rect x=".5" y=".5" width="1187" height="169" rx="21.5" fill="none" stroke="#fff" stroke-opacity=".08"/>
</svg>
"""


def write(stars, days):
    for repo, path in TILES.items():
        p = Path(path)
        p.write_text(apply_stars(p.read_text(encoding="utf-8"), stars[repo]), encoding="utf-8")
    total, streak = sum(days.values()), longest_streak(days)
    Path("assets/stats.svg").write_text(render_strip(total, sum(stars.values()), streak), encoding="utf-8")
    print({r: rounded(stars[r]) for r in TILES}, "contributions", total, "stars", sum(stars.values()), "streak", streak)


def test():
    assert [rounded(n) for n in (1, 9, 10, 29, 33, 50, 347, 999, 1000, 1234, 2000)] == \
        ["1", "9", "10+", "25+", "30+", "50+", "340+", "990+", "1k+", "1.2k+", "2k+"]
    narrow = '<title id="t">x. 347 stars</title><text x="1" class="stars" fill="#e">347 stars</text>'
    wide = '<title id="t">x. 320+ stars</title><text x="1" class="stars" fill="u">320+</text>'
    assert apply_stars(narrow, 351) == '<title id="t">x. 350+ stars</title><text x="1" class="stars" fill="#e">350+ stars</text>'
    assert apply_stars(wide, 1) == '<title id="t">x. 1 star</title><text x="1" class="stars" fill="u">1</text>'
    try:
        apply_stars("<title>no count</title>", 5)
        raise AssertionError("should reject unknown layout")
    except ValueError:
        pass
    d0 = dt.date(2026, 1, 1)
    days = {d0 + dt.timedelta(i): (2 if i in (10, 11, 12, 50) else 0) for i in range(100)}
    assert longest_streak(days) == 3
    assert longest_streak({d0: 1, d0 + dt.timedelta(2): 1}) == 1  # a missing date breaks the run
    minidom.parseString(render_strip(878, 760, 13))
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        test()
        sys.exit()
    write(repo_stars(), contribution_days())
