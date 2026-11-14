"""Refresh the star counts shown on the project tiles in assets/.

Run from the repo root: python3 scripts/update_stars.py
Uses GITHUB_TOKEN if set (higher API rate limit). `--test` runs the self-check.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

OWNER = "3000IQPlay"
TILES = {
    "obfuscator-list": "assets/project-obfuscator-list.svg",
    "client-library": "assets/project-client-library.svg",
    "AntiRAT-21": "assets/project-antirat-21.svg",
    "IQ-Docs": "assets/project-iq-docs.svg",
}


def stars(repo):
    req = urllib.request.Request(f"https://api.github.com/repos/{OWNER}/{repo}",
                                 headers={"Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=20) as r:
        count = json.load(r)["stargazers_count"]
    if not isinstance(count, int):
        raise ValueError(f"{repo}: bad stargazers_count {count!r}")
    return count


def apply(svg, n):
    label = f"{n} star" + ("" if n == 1 else "s")
    svg, a = re.subn(r'(<text[^>]*class="stars"[^>]*>)\d+ stars?(</text>)', rf"\g<1>{label}\g<2>", svg)
    svg, b = re.subn(r'(<text[^>]*class="stars"[^>]*>)\d+(</text>)', rf"\g<1>{n}\g<2>", svg)
    svg, c = re.subn(r"\d+ stars?(</title>)", rf"{label}\g<1>", svg)
    if a + b != 1 or c != 1:
        raise ValueError("tile layout changed: expected one star count and one title")
    return svg


def test():
    narrow = '<title id="t">x. 347 stars</title><text x="1" class="stars" fill="#e">347 stars</text>'
    wide = '<title id="t">x. 320 stars</title><text x="1" class="stars" fill="u">320</text>'
    assert apply(narrow, 1) == '<title id="t">x. 1 star</title><text x="1" class="stars" fill="#e">1 star</text>'
    assert apply(wide, 1234) == '<title id="t">x. 1234 stars</title><text x="1" class="stars" fill="u">1234</text>'
    try:
        apply("<title>no count</title>", 5)
        raise AssertionError("should reject unknown layout")
    except ValueError:
        pass
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        test()
        sys.exit()
    counts = {repo: stars(repo) for repo in TILES}  # fetch all first so a failure writes nothing
    for repo, path in TILES.items():
        p = Path(path)
        p.write_text(apply(p.read_text(encoding="utf-8"), counts[repo]), encoding="utf-8")
        print(f"{repo}: {counts[repo]}")
