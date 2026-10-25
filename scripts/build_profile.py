#!/usr/bin/env python3
"""Build the dynamic parts of the GitHub profile README.

Fetches live data from the GitHub GraphQL API, renders animated SVG cards
(dark + light variants) into dist/, and rewrites the generated sections of
README.md between <!-- NAME:START --> / <!-- NAME:END --> markers.

Standard library only, so the workflow needs no pip install.
"""

import json
import os
import re
import subprocess
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
CONFIG = json.loads((ROOT / "profile.json").read_text())
USER = CONFIG["username"]
RAW = f"https://raw.githubusercontent.com/{USER}/{USER}/output/"

THEMES = {
    "dark": {
        "bg": "#0d1117", "border": "#30363d", "text": "#e6edf3", "muted": "#8b949e",
        "a1": "#22d3ee", "a2": "#a78bfa", "pill": "#161b22", "grid": "#21262d",
        "track": "#21262d", "ok": "#3fb950",
        "palette": ["#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#60a5fa", "#6e7681"],
    },
    "light": {
        "bg": "#ffffff", "border": "#d0d7de", "text": "#1f2328", "muted": "#59636e",
        "a1": "#0891b2", "a2": "#7c3aed", "pill": "#f6f8fa", "grid": "#eaeef2",
        "track": "#eaeef2", "ok": "#1a7f37",
        "palette": ["#0891b2", "#7c3aed", "#db2777", "#d97706", "#059669", "#2563eb", "#8c959f"],
    },
}

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

ICON_REPO = "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.25.25 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"
ICON_STAR = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
ICON_FORK = "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"
ICON_LOCK = "M4 4a4 4 0 0 1 8 0v2h.25c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 12.25 15h-8.5A1.75 1.75 0 0 1 2 13.25v-5.5C2 6.784 2.784 6 3.75 6H4Zm8.25 3.5h-8.5a.25.25 0 0 0-.25.25v5.5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-5.5a.25.25 0 0 0-.25-.25ZM10.5 6V4a2.5 2.5 0 1 0-5 0v2Z"

BASE_CSS = """
.fade{animation:fade .9s ease-out both}
.grow-y{transform-box:fill-box;transform-origin:bottom;animation:growy .9s cubic-bezier(.2,.8,.2,1) both}
.grow-x{transform-box:fill-box;transform-origin:left;animation:growx 1.2s cubic-bezier(.2,.8,.2,1) both}
.pulse{animation:pulse 1.8s ease-in-out infinite}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes growy{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes growx{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


# ---------------------------------------------------------------- data


def token():
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    contributionsCollection {
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        name description url isFork isArchived stargazerCount forkCount pushedAt
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def streaks(days):
    counts = [d["contributionCount"] for d in days if d["date"] <= date.today().isoformat()]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # Today not having a contribution yet doesn't break the streak.
    current = 0
    tail = counts[:-1] if counts and counts[-1] == 0 else counts
    for c in reversed(tail):
        if not c:
            break
        current += 1
    return current, longest


def language_mix(repos):
    """Each repo gets equal weight, split by its byte share per language.

    Weighting by raw bytes would let notebook outputs drown out everything else.
    """
    aliases, ignore = CONFIG["language_aliases"], set(CONFIG["language_ignore"])
    totals = {}
    for r in repos:
        edges = [e for e in r["languages"]["edges"] if aliases.get(e["node"]["name"], e["node"]["name"]) not in ignore]
        size = sum(e["size"] for e in edges)
        for e in edges:
            name = aliases.get(e["node"]["name"], e["node"]["name"])
            totals[name] = totals.get(name, 0) + e["size"] / size
    grand = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    return [(n, v / grand * 100) for n, v in ranked]


# ---------------------------------------------------------------- svg helpers


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def wrap(text, width, lines):
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}" if cur else w
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: width - 1].rstrip(" ,.;:") + "…"
    return out


def svg(w, h, body, t, extra_css="", title=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{t["a1"]}"/><stop offset="1" stop-color="{t["a2"]}"/></linearGradient></defs>'
        f"<style>{BASE_CSS}{extra_css}</style>"
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="{t["bg"]}" stroke="{t["border"]}"/>'
        f"{body}</svg>"
    )


def card_title(text, t, x=28, y=40):
    return (
        f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="16" font-weight="700" fill="{t["text"]}">{esc(text)}</text>'
        f'<rect class="grow-x" x="{x}" y="{y + 9}" width="44" height="3" rx="1.5" fill="url(#g)"/>'
    )


def icon(path, x, y, color, scale=1.0):
    return f'<path transform="translate({x} {y}) scale({scale})" d="{path}" fill="{color}"/>'


def pill(text, x, y, t):
    w = len(text) * 6.4 + 18
    return w, (
        f'<rect x="{x}" y="{y}" width="{w:.0f}" height="22" rx="11" fill="{t["pill"]}" stroke="{t["border"]}"/>'
        f'<text x="{x + w / 2:.0f}" y="{y + 15}" text-anchor="middle" font-family="{SANS}" font-size="11" '
        f'font-weight="600" fill="{t["a1"]}">{esc(text)}</text>'
    )


# ---------------------------------------------------------------- cards


def banner(t):
    w, h = 900, 250
    lines = CONFIG["typing"]
    char_w, x0, y0 = 9.7, 72, 205
    slot, type_s, hold_s, erase_s = 4.2, 1.6, 1.8, 0.5
    total = slot * len(lines)

    def keyframes(widths):
        pts = [(0.0, 0.0)]
        for i, wd in enumerate(widths):
            s = i * slot
            pts += [(s, 0.0), (s + type_s, wd), (s + type_s + hold_s, wd), (s + type_s + hold_s + erase_s, 0.0)]
        pts.append((total, 0.0))
        clean = []
        for tm, v in pts:
            if clean and abs(clean[-1][0] - tm) < 1e-9:
                clean[-1] = (tm, v)
            else:
                clean.append((tm, v))
        return ";".join(f"{tm / total:.4f}" for tm, _ in clean), clean

    widths = [len(s) * char_w + 2 for s in lines]
    typing = ""
    for i, (line, wd) in enumerate(zip(lines, widths)):
        only = [0.0] * len(lines)
        only[i] = wd
        kt, pts = keyframes(only)
        vals = ";".join(f"{v:.1f}" for _, v in pts)
        typing += (
            f'<clipPath id="c{i}"><rect x="{x0}" y="{y0 - 18}" height="26" width="0">'
            f'<animate attributeName="width" values="{vals}" keyTimes="{kt}" dur="{total}s" repeatCount="indefinite"/>'
            f"</rect></clipPath>"
            f'<text clip-path="url(#c{i})" x="{x0}" y="{y0}" font-family="{MONO}" font-size="16" fill="{t["text"]}">{esc(line)}</text>'
        )
    kt, pts = keyframes(widths)
    cursor_x = ";".join(f"{x0 + v:.1f}" for _, v in pts)
    typing += (
        f'<rect y="{y0 - 15}" x="{x0}" width="9" height="19" fill="{t["a1"]}">'
        f'<animate attributeName="x" values="{cursor_x}" keyTimes="{kt}" dur="{total}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/></rect>'
    )

    # Agent graph on the right: nodes pulse, edges carry flowing dashes.
    nodes = [(700, 70), (800, 60), (850, 140), (760, 190), (660, 160), (750, 125)]
    edges = [(5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]
    graph = ""
    for k, (a, b) in enumerate(edges):
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        graph += (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="url(#g)" stroke-width="1.4" '
            f'stroke-dasharray="4 6" opacity=".55"><animate attributeName="stroke-dashoffset" '
            f'from="0" to="{-20 if k % 2 else 20}" dur="{1.6 + k % 3 * 0.4}s" repeatCount="indefinite"/></line>'
        )
    for k, (x, y) in enumerate(nodes):
        r = 11 if k == 5 else 6
        color = "url(#g)" if k == 5 else (t["a1"] if k % 2 else t["a2"])
        graph += (
            f'<circle cx="{x}" cy="{y}" r="{r + 6}" fill="none" stroke="{t["a1"] if k % 2 else t["a2"]}" opacity="0">'
            f'<animate attributeName="r" values="{r};{r + 12}" dur="2.4s" begin="{k * 0.4}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values=".6;0" dur="2.4s" begin="{k * 0.4}s" repeatCount="indefinite"/></circle>'
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'
        )

    body = (
        f'<defs><pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
        f'<circle cx="1.5" cy="1.5" r="1.2" fill="{t["grid"]}"/></pattern>'
        f'<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="50"/></filter>'
        f'<clipPath id="frame"><rect width="{w}" height="{h}" rx="14"/></clipPath></defs>'
        f'<g clip-path="url(#frame)"><rect width="{w}" height="{h}" fill="url(#dots)"/>'
        f'<circle cx="760" cy="40" r="110" fill="{t["a2"]}" opacity=".16" filter="url(#blur)">'
        f'<animate attributeName="cx" values="760;690;760" dur="12s" repeatCount="indefinite"/></circle>'
        f'<circle cx="120" cy="230" r="120" fill="{t["a1"]}" opacity=".12" filter="url(#blur)">'
        f'<animate attributeName="cx" values="120;220;120" dur="14s" repeatCount="indefinite"/></circle></g>'
        f'<g class="fade">'
        f'<text x="48" y="66" font-family="{MONO}" font-size="14" fill="{t["a1"]}">~/hello-world</text>'
        f'<text x="48" y="116" font-family="{SANS}" font-size="44" font-weight="800" fill="url(#g)">{esc(CONFIG["name"])}</text>'
        f'<text x="48" y="150" font-family="{SANS}" font-size="19" font-weight="600" fill="{t["text"]}">{esc(CONFIG["title"])}</text>'
        f'<text x="48" y="174" font-family="{SANS}" font-size="14" fill="{t["muted"]}">{esc(CONFIG["subtitle"])}</text>'
        f'<text x="48" y="{y0}" font-family="{MONO}" font-size="16" font-weight="700" fill="{t["a2"]}">❯</text>'
        f"</g>{typing}{graph}"
    )
    return svg(w, h, body, t, title=f'{CONFIG["name"]}: {CONFIG["title"]}')


def overview(t, user, cur, longest):
    w, h = 440, 240
    cal = user["contributionsCollection"]
    stats = [
        ("Contributions (1y)", f'{cal["contributionCalendar"]["totalContributions"]:,}'),
        ("Current streak", f"{cur} day{'s' * (cur != 1)}"),
        ("Longest streak", f"{longest} day{'s' * (longest != 1)}"),
        ("Pull requests (1y)", f'{cal["totalPullRequestContributions"]:,}'),
        ("Public repositories", f'{user["repositories"]["totalCount"]:,}'),
        ("Years on GitHub", f'{(date.today() - date.fromisoformat(user["createdAt"][:10])).days / 365.25:.1f}'),
    ]
    body = card_title("GitHub Overview", t)
    for i, (label, value) in enumerate(stats):
        col, row = i % 2, i // 2
        x, y = 28 + col * 206, 92 + row * 56
        body += (
            f'<g class="fade" style="animation-delay:{0.15 * i:.2f}s">'
            f'<rect x="{x}" y="{y - 20}" width="3" height="42" rx="1.5" fill="url(#g)"/>'
            f'<text x="{x + 14}" y="{y - 5}" font-family="{SANS}" font-size="12" fill="{t["muted"]}">{esc(label)}</text>'
            f'<text x="{x + 14}" y="{y + 18}" font-family="{SANS}" font-size="20" font-weight="700" fill="{t["text"]}">{esc(value)}</text></g>'
        )
    return svg(w, h, body, t, title="GitHub overview")


def languages(t, mix):
    w, h = 440, 240
    top = mix[:6]
    other = sum(p for _, p in mix[6:])
    if other >= 0.5:
        top.append(("Other", other))
    top = [(n, p, t["palette"][i]) for i, (n, p) in enumerate(top)]
    body = card_title("Language Focus", t)
    bx, by, bw = 28, 72, 384
    body += f'<clipPath id="bar"><rect x="{bx}" y="{by}" width="{bw}" height="10" rx="5"/></clipPath>'
    body += f'<rect x="{bx}" y="{by}" width="{bw}" height="10" rx="5" fill="{t["track"]}"/><g clip-path="url(#bar)"><g class="grow-x">'
    x = bx
    for _, pct, color in top:
        seg = bw * pct / 100
        body += f'<rect x="{x:.1f}" y="{by}" width="{seg + 0.6:.1f}" height="10" fill="{color}"/>'
        x += seg
    body += "</g></g>"
    for i, (name, pct, color) in enumerate(top):
        col, row = i // 4, i % 4
        x, y = 28 + col * 206, 116 + row * 26
        body += (
            f'<g class="fade" style="animation-delay:{0.3 + 0.1 * i:.2f}s">'
            f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{color}"/>'
            f'<text x="{x + 18}" y="{y}" font-family="{SANS}" font-size="13" fill="{t["text"]}">{esc(name)}</text>'
            f'<text x="{x + 180}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{pct:.1f}%</text></g>'
        )
    body += (
        f'<text x="28" y="{h - 20}" font-family="{SANS}" font-size="11" fill="{t["muted"]}">'
        f"Share of public repositories, each repo weighted equally</text>"
    )
    return svg(w, h, body, t, title="Language focus")


def activity(t, user):
    w, h = 900, 230
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    totals = [sum(d["contributionCount"] for d in wk["contributionDays"]) for wk in weeks]
    peak = max(totals) or 1
    cx, cy, cw, ch = 28, 70, 844, 112
    step = cw / len(weeks)
    bw = max(step - 4, 2)
    updated = datetime.now(timezone.utc).strftime("%b %d, %Y")
    body = card_title("Contribution Activity", t)
    body += (
        f'<text x="{w - 28}" y="40" text-anchor="end" font-family="{SANS}" font-size="13" fill="{t["muted"]}">'
        f'<tspan fill="{t["text"]}" font-weight="700">{cal["totalContributions"]:,}</tspan> contributions in the last year'
        f"  ·  updated {updated}</text>"
    )
    for k in range(4):
        gy = cy + ch * k / 3
        body += f'<line x1="{cx}" x2="{cx + cw}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="{t["grid"]}" stroke-dasharray="2 4"/>'
    prev_month, last_label_x = None, -100
    for i, (wk, total) in enumerate(zip(weeks, totals)):
        x = cx + i * step + (step - bw) / 2
        bh = max(ch * total / peak, 2 if total else 1)
        opacity = 1 if total else 0.35
        body += (
            f'<rect class="grow-y" style="animation-delay:{i * 0.015:.3f}s" x="{x:.1f}" y="{cy + ch - bh:.1f}" '
            f'width="{bw:.1f}" height="{bh:.1f}" rx="{min(bw / 2, 3):.1f}" fill="url(#g)" opacity="{opacity}">'
            f'<title>Week of {wk["contributionDays"][0]["date"]}: {total} contributions</title></rect>'
        )
        month = wk["contributionDays"][0]["date"][:7]
        if month != prev_month and i < len(weeks) - 2 and x - last_label_x > 34:
            label = date.fromisoformat(month + "-01").strftime("%b")
            body += f'<text x="{x:.1f}" y="{cy + ch + 20}" font-family="{SANS}" font-size="11" fill="{t["muted"]}">{label}</text>'
            prev_month, last_label_x = month, x
        elif month != prev_month:
            prev_month = month
    body += (
        f'<text x="{w - 28}" y="{h - 14}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{t["muted"]}">'
        f"weekly totals · peak {peak}/week</text>"
    )
    return svg(w, h, body, t, title="Contribution activity over the last year")


def project_card(t, title, description, tags, footer, badge, url_hint):
    w, h = 440, 210
    body = (
        f'<rect x="1" y="1" width="{w - 2}" height="4" rx="2" fill="url(#g)" class="grow-x"/>'
        f'{icon(ICON_REPO, 28, 26, t["muted"])}'
        f'<text x="52" y="40" font-family="{SANS}" font-size="17" font-weight="700" fill="{t["text"]}">{esc(title)}</text>'
        f"{badge}"
    )
    for i, line in enumerate(wrap(description, 58, 3)):
        body += f'<text class="fade" x="28" y="{72 + i * 19}" font-family="{SANS}" font-size="13" fill="{t["muted"]}">{esc(line)}</text>'
    x = 28
    for tag in tags[:3]:
        pw, p = pill(tag, x, 136, t)
        body += p
        x += pw + 8
    body += f'<line x1="28" x2="{w - 28}" y1="172" y2="172" stroke="{t["grid"]}"/>{footer}'
    return svg(w, h, body, t, title=f"{title}: {url_hint}")


def repo_card(t, repo, spec):
    lang = repo["primaryLanguage"] or {"name": "Mixed", "color": "#8b949e"}
    lang_name = CONFIG["language_aliases"].get(lang["name"], lang["name"])
    lang_color = "#3572A5" if lang_name == "Python" else lang["color"]
    pushed = datetime.fromisoformat(repo["pushedAt"].replace("Z", "+00:00")).strftime("%b %Y")
    stars = repo["stargazerCount"]
    badge = (
        f'{icon(ICON_STAR, 382, 27, t["muted"], 0.85)}'
        f'<text x="412" y="39" text-anchor="end" font-family="{SANS}" font-size="13" font-weight="600" fill="{t["muted"]}">{stars}</text>'
    )
    footer = (
        f'<circle cx="34" cy="191" r="5" fill="{lang_color}"/>'
        f'<text x="46" y="195" font-family="{SANS}" font-size="12" fill="{t["text"]}">{esc(lang_name)}</text>'
        f'{icon(ICON_FORK, 150, 182, t["muted"], 0.8)}'
        f'<text x="166" y="195" font-family="{SANS}" font-size="12" fill="{t["muted"]}">{repo["forkCount"]}</text>'
        f'<text x="412" y="195" text-anchor="end" font-family="{SANS}" font-size="12" fill="{t["muted"]}">updated {pushed}</text>'
    )
    description = spec.get("description") or repo["description"] or "No description yet."
    return project_card(t, repo["name"], description, spec.get("tags", []), footer, badge, repo["url"])


def building_card(t, item):
    live = "live" in item["status"].lower()
    color = t["ok"] if live else t["a1"]
    label = item["status"].upper()
    lw = len(label) * 6.5
    footer = (
        f'{icon(ICON_LOCK, 28, 183, t["muted"], 0.8)}'
        f'<text x="44" y="195" font-family="{SANS}" font-size="12" fill="{t["muted"]}">Private repository</text>'
        f'<circle class="pulse" cx="{412 - lw - 10:.0f}" cy="191" r="4" fill="{color}"/>'
        f'<text x="412" y="195" text-anchor="end" font-family="{SANS}" font-size="10.5" font-weight="700" '
        f'fill="{color}" letter-spacing=".4">{esc(label)}</text>'
    )
    return project_card(t, item["title"], item["description"], item["tags"], footer, "", item["status"])


# ---------------------------------------------------------------- readme


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def picture(name, alt, width):
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" srcset="{RAW}{name}-dark.svg" />'
        f'<source media="(prefers-color-scheme: light)" srcset="{RAW}{name}-light.svg" />'
        f'<img src="{RAW}{name}-dark.svg" alt="{esc(alt)}" width="{width}" /></picture>'
    )


def card_grid(entries):
    rows = []
    for i in range(0, len(entries), 2):
        cells = [f'<a href="{href}">{picture(name, alt, "49%")}</a>' for name, alt, href in entries[i:i + 2]]
        rows.append("<p align=\"center\">\n" + "\n".join(cells) + "\n</p>")
    return "\n".join(rows)


def recent_list(repos):
    lines = []
    for r in repos[: CONFIG["recent_count"]]:
        lang = (r["primaryLanguage"] or {}).get("name", "—")
        pushed = datetime.fromisoformat(r["pushedAt"].replace("Z", "+00:00")).strftime("%b %d, %Y")
        desc = f" — {wrap(r['description'].strip(), 90, 1)[0]}" if r["description"] else ""
        lines.append(f"| [**{r['name']}**]({r['url']}){esc(desc)} | `{lang}` | {pushed} |")
    return "| Repository | Language | Last push |\n|:--|:--:|:--:|\n" + "\n".join(lines)


def replace_section(text, name, content):
    pattern = re.compile(rf"(<!-- {name}:START -->)(.*?)(<!-- {name}:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README is missing the {name} markers")
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", text)


# ---------------------------------------------------------------- main


def main():
    user = fetch()
    excluded = set(CONFIG["exclude_repos"])
    repos = [r for r in user["repositories"]["nodes"] if r["name"] not in excluded]
    own = [r for r in repos if not r["isFork"]]
    by_name = {r["name"]: r for r in repos}
    days = [d for wk in user["contributionsCollection"]["contributionCalendar"]["weeks"] for d in wk["contributionDays"]]
    cur, longest = streaks(days)
    mix = language_mix(own)

    DIST.mkdir(exist_ok=True)
    featured = [(spec, by_name[spec["repo"]]) for spec in CONFIG["featured"] if spec["repo"] in by_name]
    for name, t in THEMES.items():
        files = {
            "banner": banner(t),
            "overview": overview(t, user, cur, longest),
            "languages": languages(t, mix),
            "activity": activity(t, user),
        }
        for item in CONFIG["building"]:
            files[f"building-{slug(item['title'])}"] = building_card(t, item)
        for spec, repo in featured:
            files[f"project-{slug(repo['name'])}"] = repo_card(t, repo, spec)
        for key, content in files.items():
            (DIST / f"{key}-{name}.svg").write_text(content)

    readme_path = ROOT / "README.md"
    readme = readme_path.read_text()
    readme = replace_section(readme, "BUILDING", card_grid(
        [(f"building-{slug(i['title'])}", i["title"], "#currently-building") for i in CONFIG["building"]]))
    readme = replace_section(readme, "FEATURED", card_grid(
        [(f"project-{slug(r['name'])}", r["name"], r["url"]) for _, r in featured]))
    readme = replace_section(readme, "RECENT", recent_list(own))
    readme_path.write_text(readme)
    print(f"Rendered {len(list(DIST.glob('*.svg')))} SVGs; streak {cur}/{longest}; languages {[n for n, _ in mix[:5]]}")


if __name__ == "__main__":
    main()
