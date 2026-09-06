#!/usr/bin/env python3
"""
Regenerates assets/banner-dark.svg, assets/banner-light.svg and the link row
inside README.md from live GitHub data.

Everything that changes (pinned repos, descriptions, languages, stars, accent
colours) is pulled at run time. Everything that doesn't (bio, stack, socials)
lives in scripts/config.json.

usage:
    GITHUB_TOKEN=... python scripts/generate.py
    python scripts/generate.py --sample     # offline preview, fake data
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "config.json").read_text())

# ----------------------------------------------------------------- palettes

THEMES = {
    "dark": {
        "bg": "none",
        "panel": "#0d1117",
        "border": "#21262d",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "faint": "#6e7681",
        "rule": "#1c2128",
    },
    "light": {
        "bg": "none",
        "panel": "#ffffff",
        "border": "#d1d9e0",
        "text": "#1f2328",
        "muted": "#59636e",
        "faint": "#818b98",
        "rule": "#e4e8ed",
    },
}

FALLBACK_ACCENT = {"dark": "#7d8590", "light": "#6e7781"}

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

# ------------------------------------------------------------ colour helpers


def hex_to_rgb(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def luminance(c):
    r, g, b = [v / 255 for v in hex_to_rgb(c)]
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def mix(a, b, t):
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def readable(color, theme):
    """Nudge a language colour until it reads against the theme background.

    GitHub's language colours are tuned for a 12px dot, not for text. JS yellow
    on white is unreadable; Go's cyan on black is fine. This walks the colour
    toward the opposite end until it clears a 3.2:1 ratio, so the accents stay
    recognisably 'the language colour' but never turn to mush.
    """
    if not color:
        return FALLBACK_ACCENT[theme]
    bg = THEMES[theme]["panel"]
    target = "#000000" if theme == "light" else "#ffffff"
    out = color
    for step in range(11):
        if contrast(out, bg) >= 3.2:
            return out
        out = mix(color, target, 0.06 * (step + 1))
    return out


# ------------------------------------------------------------- text helpers

_WIDE = set("MWmw@%")
_NARROW = set("iljtfrI.,:;'|!()[]{}-")


def text_width(s, size, mono=False):
    if mono:
        return len(s) * size * 0.6
    total = 0.0
    for ch in s:
        if ch in _WIDE:
            total += 0.87
        elif ch in _NARROW:
            total += 0.31
        elif ch == " ":
            total += 0.27
        elif ch.isupper() or ch.isdigit():
            total += 0.6
        else:
            total += 0.52
    return total * size


def clip(s, size, limit, mono=False):
    if text_width(s, size, mono) <= limit:
        return s
    out = s
    while out and text_width(out + "…", size, mono) > limit:
        out = out[:-1]
    return out.rstrip(" ,.;-") + "…"


def esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ------------------------------------------------------------------- fetch

QUERY = """
query($login:String!, $limit:Int!) {
  user(login:$login) {
    login
    pinnedItems(first:$limit, types:REPOSITORY) {
      nodes { ... on Repository {
        name
        description
        url
        stargazerCount
        forkCount
        isArchived
        primaryLanguage { name color }
        languages(first:6, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name color } }
        }
      } }
    }
  }
}
"""


def fetch(login, limit, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login, "limit": limit}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit("github api error: " + json.dumps(payload["errors"]))
    user = payload["data"]["user"]
    if not user:
        raise SystemExit(f"no such user: {login}")
    return [n for n in user["pinnedItems"]["nodes"] if n]


SAMPLE = [
    {"name": "gbh-suite", "description": "container runtime and image builder written from scratch in go", "url": "#", "stargazerCount": 14, "forkCount": 2, "primaryLanguage": {"name": "Go", "color": "#00ADD8"}, "languages": {"edges": [{"size": 48000, "node": {"name": "Go", "color": "#00ADD8"}}, {"size": 9000, "node": {"name": "Shell", "color": "#89e051"}}]}},
    {"name": "vector", "description": "distributed vector store with hnsw indexing and a wire protocol", "url": "#", "stargazerCount": 9, "forkCount": 0, "primaryLanguage": {"name": "Rust", "color": "#dea584"}, "languages": {"edges": [{"size": 61000, "node": {"name": "Rust", "color": "#dea584"}}]}},
    {"name": "nexus", "description": "gitops controller that reconciles cluster state from a single manifest", "url": "#", "stargazerCount": 6, "forkCount": 1, "primaryLanguage": {"name": "Go", "color": "#00ADD8"}, "languages": {"edges": [{"size": 30000, "node": {"name": "Go", "color": "#00ADD8"}}]}},
    {"name": "flux", "description": "real-time stream processor with exactly-once delivery over kafka", "url": "#", "stargazerCount": 4, "forkCount": 0, "primaryLanguage": {"name": "Python", "color": "#3572A5"}, "languages": {"edges": [{"size": 27000, "node": {"name": "Python", "color": "#3572A5"}}]}},
    {"name": "echo", "description": "macos automation daemon driving window and audio state from a config file", "url": "#", "stargazerCount": 3, "forkCount": 0, "primaryLanguage": {"name": "Swift", "color": "#F05138"}, "languages": {"edges": [{"size": 18000, "node": {"name": "Swift", "color": "#F05138"}}]}},
    {"name": "vertex", "description": "transformer training loop and tokenizer built without a framework", "url": "#", "stargazerCount": 7, "forkCount": 1, "primaryLanguage": {"name": "Python", "color": "#3572A5"}, "languages": {"edges": [{"size": 41000, "node": {"name": "Python", "color": "#3572A5"}}]}},
]

# ------------------------------------------------------------------ layout

W = 900
PAD = 34
INNER = W - PAD * 2


def language_spectrum(repos):
    """Aggregate every language byte across the pinned repos into one strip."""
    totals = {}
    colors = {}
    for r in repos:
        for e in (r.get("languages") or {}).get("edges", []) or []:
            node = e["node"]
            totals[node["name"]] = totals.get(node["name"], 0) + e["size"]
            colors[node["name"]] = node.get("color")
    if not totals:
        for r in repos:
            pl = r.get("primaryLanguage")
            if pl:
                totals[pl["name"]] = totals.get(pl["name"], 0) + 1
                colors[pl["name"]] = pl.get("color")
    total = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    top = ranked[:7]
    rest = sum(v for _, v in ranked[7:])
    out = [{"name": n, "share": v / total, "color": colors.get(n)} for n, v in top]
    if rest:
        out.append({"name": "other", "share": rest / total, "color": None})
    return out


def render(repos, theme):
    t = THEMES[theme]
    spec = language_spectrum(repos)
    parts = []
    y = 0

    def add(s):
        parts.append(s)

    # ---- header
    y = 64
    name = CONFIG["display_name"]
    add(f'<text x="{PAD}" y="{y}" font-family="{SANS}" font-size="24" font-weight="640" '
        f'letter-spacing="-0.5" fill="{t["text"]}">{esc(name)}</text>')
    nx = PAD + text_width(name, 24) * 0.86 + 20
    add(f'<text x="{nx:.0f}" y="{y}" font-family="{MONO}" font-size="12" '
        f'fill="{t["faint"]}">@{esc(CONFIG["login"])}</text>')

    y += 30
    for line in CONFIG["bio"]:
        add(f'<text x="{PAD}" y="{y}" font-family="{SANS}" font-size="12.5" '
            f'fill="{t["muted"]}">{esc(clip(line, 12.5, INNER))}</text>')
        y += 19.5

    # ---- language spectrum: the one loud element, and it is entirely data
    y += 18
    bar_h = 10
    x = PAD
    add(f'<clipPath id="strip-{theme}"><rect x="{PAD}" y="{y}" width="{INNER}" '
        f'height="{bar_h}" rx="5"/></clipPath>')
    add(f'<g clip-path="url(#strip-{theme})">')
    for i, seg in enumerate(spec):
        w = INNER * seg["share"]
        col = readable(seg["color"], theme) if seg["color"] else mix(t["border"], t["muted"], 0.4)
        add(f'<rect x="{x:.2f}" y="{y}" width="{max(w, 0.6):.2f}" height="{bar_h}" fill="{col}"/>')
        x += w
    add("</g>")

    y += bar_h + 22
    lx = PAD
    for seg in spec:
        if seg["share"] < 0.02:
            continue
        col = readable(seg["color"], theme) if seg["color"] else t["faint"]
        label = f'{seg["name"]} {seg["share"] * 100:.0f}%'
        add(f'<circle cx="{lx + 4:.0f}" cy="{y - 4}" r="4" fill="{col}"/>')
        add(f'<text x="{lx + 15:.0f}" y="{y}" font-family="{MONO}" font-size="10.5" '
            f'fill="{t["muted"]}">{esc(label)}</text>')
        lx += 15 + text_width(label, 10.5, mono=True) + 18

    # ---- stack
    y += 30
    add(f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{t["rule"]}" stroke-width="1"/>')
    y += 28
    key_w = 92
    for key, items in CONFIG["stack"].items():
        add(f'<text x="{PAD}" y="{y}" font-family="{MONO}" font-size="11" '
            f'fill="{t["faint"]}">{esc(key)}</text>')
        add(f'<text x="{PAD + key_w}" y="{y}" font-family="{SANS}" font-size="12" '
            f'fill="{t["muted"]}" xml:space="preserve">{esc("   ".join(items))}</text>')
        y += 21

    # ---- pinned repos
    y += 8
    add(f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{t["rule"]}" stroke-width="1"/>')
    y += 26

    for r in repos:
        pl = r.get("primaryLanguage") or {}
        accent = readable(pl.get("color"), theme)
        top = y - 14
        add(f'<rect x="{PAD}" y="{top}" width="3" height="40" rx="1.5" fill="{accent}"/>')

        nm = r["name"]
        add(f'<text x="{PAD + 16}" y="{y}" font-family="{MONO}" font-size="13" '
            f'font-weight="600" fill="{t["text"]}">{esc(nm)}</text>')

        meta = []
        if pl.get("name"):
            meta.append(pl["name"].lower())
        if r.get("stargazerCount"):
            meta.append(f'★ {r["stargazerCount"]}')
        if r.get("isArchived"):
            meta.append("archived")
        meta_s = "   ".join(meta)
        if meta_s:
            mw = text_width(meta_s, 11, mono=True)
            add(f'<text x="{W - PAD - mw:.0f}" y="{y}" font-family="{MONO}" font-size="11" '
                f'fill="{t["faint"]}" xml:space="preserve">{esc(meta_s)}</text>')

        desc = r.get("description") or "no description yet"
        avail = INNER - 16 - 20
        add(f'<text x="{PAD + 16}" y="{y + 18}" font-family="{SANS}" font-size="11.5" '
            f'fill="{t["muted"]}">{esc(clip(desc.lower(), 11.5, avail))}</text>')
        y += 44

    # ---- footer
    y += 4
    add(f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{t["rule"]}" stroke-width="1"/>')
    y += 24
    add(f'<text x="{PAD}" y="{y}" font-family="{SANS}" font-size="11.5" '
        f'fill="{t["faint"]}">{esc(CONFIG["footer"])}</text>')
    y += 22

    H = y
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" fill="none" role="img" '
        f'aria-label="{esc(CONFIG["display_name"])} github profile">'
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" '
        f'fill="{THEMES[theme]["panel"]}" stroke="{THEMES[theme]["border"]}"/>'
    )
    return head + "".join(parts) + "</svg>\n"


# ------------------------------------------------------------------ readme


def link_row(repos):
    socials = " · ".join(f'<a href="{s["url"]}">{s["label"]}</a>' for s in CONFIG["socials"])
    projects = " · ".join(f'<a href="{r["url"]}">{r["name"]}</a>' for r in repos)
    return f"<p align=\"right\"><sub>{socials}&nbsp; | &nbsp;{projects}</sub></p>"


def patch_readme(repos):
    path = ROOT / "README.md"
    text = path.read_text()
    new = re.sub(
        r"(<!-- links:start -->).*?(<!-- links:end -->)",
        lambda m: m.group(1) + "\n" + link_row(repos) + "\n" + m.group(2),
        text,
        flags=re.S,
    )
    path.write_text(new)


def main():
    sample = "--sample" in sys.argv
    if sample:
        repos = SAMPLE
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("set GITHUB_TOKEN, or pass --sample for an offline preview")
        repos = fetch(CONFIG["login"], CONFIG.get("pinned_limit", 6), token)
    if not repos:
        raise SystemExit("no pinned repositories found")

    (ROOT / "assets").mkdir(exist_ok=True)
    for theme in ("dark", "light"):
        (ROOT / "assets" / f"banner-{theme}.svg").write_text(render(repos, theme))
    patch_readme(repos)
    print(f"generated {len(repos)} pinned repos into both banners")


if __name__ == "__main__":
    main()
