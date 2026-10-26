#!/usr/bin/env python3
"""Regenerate assets/languages-all-repos.svg from ALL repos (public + private).

Needs GH_TOKEN (a PAT with read access to the account's repos; private repos are
excluded silently if the token cannot see them). Linguistic stats come from
GitHub's /languages endpoint, which honors .gitattributes linguist-vendored
rules — so vendored build output (e.g. hotspot-hub's packaging/) is excluded
server-side and needs no local cloning.
"""
import json
import os
import sys
import urllib.request

TOKEN = os.environ.get("GH_TOKEN", "")
OWNER = "Ekonop"            # account whose repos we aggregate
PAGE_SIZE = 100
MIN_SHARE = 0.007           # drop languages below 0.7% of total
REPO_SKIP = {"Ekonop"}      # the profile repo itself

HDRS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HDRS["Authorization"] = f"Bearer {TOKEN}"


def api(path: str):
    req = urllib.request.Request(f"https://api.github.com{path}", headers=HDRS)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            # token missing / invalid / lacks repo scope: treat as no access
            raise TokenError(str(exc.code))
        raise


class TokenError(RuntimeError):
    pass


def api_paginate(path: str, key: str = None):
    out = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        data = api(f"{path}{sep}per_page={PAGE_SIZE}&page={page}")
        if not data:
            break
        out.extend(data)
        if len(data) < PAGE_SIZE:
            break
        page += 1
    return out


def main():
    # every non-fork repo owned by the account (owner affiliation only, so
    # collaborator repos like other people's projects are not counted)
    repos = []
    try:
        repos = [
            r for r in api_paginate("/user/repos?affiliation=owner")
            if not r["fork"] and r["owner"]["login"] == OWNER
            and r["name"] not in REPO_SKIP
        ]
    except TokenError:
        pass  # fall through to the guard below with an empty list
    full_names = [r["full_name"] for r in repos]
    print(f"aggregating languages over {len(full_names)} owned repos", flush=True)

    totals = {}
    for full in full_names:
        try:
            langs = api(f"/repos/{full}/languages")
        except Exception as exc:
            print(f"  ! {full}: {exc}", file=sys.stderr)
            continue
        for lang, n in langs.items():
            totals[lang] = totals.get(lang, 0) + n

    grand = sum(totals.values())
    if grand <= 0 or len(repos) < 5:
        print(
            "aborting: saw %d repos / %d language bytes — "
            "GH_TOKEN secret (EKONOP_GH_TOKEN) is missing or lacks repo access. "
            "The committed SVG was NOT overwritten." % (len(repos), grand),
            file=sys.stderr,
        )
        return 1

    items = [(k, v) for k, v in sorted(totals.items(), key=lambda x: -x[1]) if v / grand >= MIN_SHARE]
    sub = sum(v for _, v in items)

    print("top languages:")
    for lang, v in items:
        print(f"  {lang:14s} {v:12,d}  {100 * v / sub:5.1f}%")

    colors = {
        "JavaScript": "#f1e05a", "Dart": "#00B4AB", "TypeScript": "#3178c6",
        "C++": "#f34b7d", "Go": "#00ADD8", "CMake": "#DA3434", "C": "#555555",
        "CSS": "#663399", "Python": "#3572A5", "Shell": "#89e051",
        "PLpgSQL": "#336790", "HTML": "#e34c26", "QML": "#44a51c",
        "Rust": "#dea584", "Java": "#b07219", "C#": "#178600",
        "PHP": "#4F5D95", "Kotlin": "#A97BFF", "Swift": "#F05138",
        "Svelte": "#FF3E00", "Vue": "#41B883", "Lua": "#000080",
        "Elixir": "#6e4a7e", "Ruby": "#701516", "Scala": "#c22d40",
    }

    W, H = 880, 96
    segs = []
    x = 0
    for lang, v in items:
        w = (v / sub) * W
        segs.append((lang, x, w, colors.get(lang, "#cccccc"), v))
        x += w

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect x="0" y="8" width="{W}" height="18" rx="6" fill="#161b22"/>',
    ]
    for lang, sx, w, c, v in segs:
        svg.append(f'<rect x="{sx:.1f}" y="8" width="{w:.1f}" height="18" fill="{c}"/>')
    lx = 0
    ly = 46
    for lang, sx, w, c, v in segs:
        label = f"{lang} {100 * v / sub:.1f}%"
        svg.append(f'<rect x="{lx}" y="{ly - 10}" width="10" height="10" rx="2" fill="{c}"/>')
        svg.append(f'<text x="{lx + 14}" y="{ly}" font-family="Arial,sans-serif" font-size="11" fill="#adbac7">{label}</text>')
        lx += 14 + len(label) * 6.4
    svg.append("</svg>")

    out_path = "assets/languages-all-repos.svg"
    with open(out_path, "w") as f:
        f.write("\n".join(svg))
    print(f"wrote {out_path} ({len(segs)} languages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())