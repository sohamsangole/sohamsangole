import os
import sys
import re
import json
import math
import random
import urllib.request
from datetime import datetime, timedelta, timezone

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "sohamsangole")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "assets/constellation.svg")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def fetch_contributions() -> list[dict]:
    if TOKEN:
        try:
            query = """
            query($login: String!) {
              user(login: $login) {
                contributionsCollection {
                  contributionCalendar {
                    weeks {
                      contributionDays {
                        date
                        contributionCount
                      }
                    }
                  }
                }
              }
            }
            """
            payload = json.dumps({"query": query, "variables": {"login": GITHUB_USERNAME}}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                data=payload,
                headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "Constellation", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as res:
                data = json.loads(res.read().decode("utf-8"))
                days = []
                for w in data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
                    for d in w["contributionDays"]:
                        days.append({"date": d["date"], "count": d["contributionCount"]})
                return days
        except Exception:
            pass

    try:
        url = f"https://github.com/users/{GITHUB_USERNAME}/contributions"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as res:
            html = res.read().decode("utf-8")
            days = []
            dates = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"', html)
            for date_str in set(dates):
                snippet = html[html.find(date_str):html.find(date_str) + 300]
                cnt = re.search(r'(\d+)\s+contribution', snippet)
                count = int(cnt.group(1)) if cnt else 0
                days.append({"date": date_str, "count": count})
            days.sort(key=lambda x: x["date"])
            if days:
                return days
    except Exception:
        pass

    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            matches = re.findall(r'<title>([A-Za-z]{3}\s+\d{1,2},\s+\d{4})\s+-\s+(\d+)\s+contribution', content)
            if matches:
                today = datetime.now(timezone.utc).date()
                counts = {}
                for d_lbl, c_str in matches:
                    dt = datetime.strptime(d_lbl, "%b %d, %Y").date()
                    counts[dt.strftime("%Y-%m-%d")] = int(c_str)
                days = []
                curr = today - timedelta(days=364)
                while curr <= today:
                    ds = curr.strftime("%Y-%m-%d")
                    days.append({"date": ds, "count": counts.get(ds, 0)})
                    curr += timedelta(days=1)
                return days
        except Exception:
            pass

    return None


def get_constellation_shape(n: int) -> tuple[list[tuple[float, float]], list[tuple[int, int]]]:
    if n == 2:
        pts = [(0.0, 0.0), (22.0, 10.0)]
        edges = [(0, 1)]
    elif n == 3:
        pts = [(0.0, 0.0), (20.0, -18.0), (32.0, 8.0)]
        edges = [(0, 1), (1, 2), (2, 0)]
    elif n == 4:
        pts = [(0.0, 0.0), (16.0, -18.0), (34.0, 0.0), (18.0, 16.0)]
        edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
    elif n == 5:
        pts = [(0.0, 14.0), (16.0, 32.0), (30.0, 8.0), (46.0, 26.0), (62.0, 0.0)]
        edges = [(0, 1), (1, 2), (2, 3), (3, 4)]
    elif n == 6:
        pts = [(0.0, 20.0), (12.0, 6.0), (28.0, 0.0), (44.0, 4.0), (58.0, 14.0), (68.0, 28.0)]
        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    else:
        pts = [
            (0.0, 0.0), (24.0, 16.0), (48.0, 34.0),
            (70.0, 48.0), (64.0, 78.0), (104.0, 84.0), (114.0, 54.0)
        ]
        edges = [
            (0, 1), (1, 2), (2, 3),
            (3, 4), (4, 5), (5, 6), (6, 3)
        ]
        for i in range(7, n):
            last_x, last_y = pts[-1]
            pts.append((last_x + 20.0, last_y - 12.0))
            edges.append((i - 1, i))

    return pts, edges


def render_svg(days: list[dict]) -> str:
    width = 880
    height = 200

    active = []
    for d in days:
        if d["count"] > 0:
            item = dict(d)
            item["dt"] = datetime.strptime(d["date"], "%Y-%m-%d").date()
            active.append(item)

    active.sort(key=lambda x: x["dt"])
    if not active:
        return ""

    first_dt = active[0]["dt"]
    last_dt = active[-1]["dt"]
    span = max(1, (last_dt - first_dt).days)

    streaks = []
    curr_streak = []
    for p in active:
        if not curr_streak:
            curr_streak.append(p)
        else:
            if (p["dt"] - curr_streak[-1]["dt"]).days == 1:
                curr_streak.append(p)
            else:
                streaks.append(curr_streak)
                curr_streak = [p]
    if curr_streak:
        streaks.append(curr_streak)

    longest_streak = max(streaks, key=len) if streaks else []
    longest_dates = set(p["date"] for p in longest_streak)

    all_edges = []
    s_rng = random.Random()

    for streak in streaks:
        mid_t = sum((p["dt"] - first_dt).days for p in streak) / (len(streak) * span)
        base_x = 60 + mid_t * 750
        base_y = s_rng.uniform(45, height - 60)

        n = len(streak)
        if n > 1:
            shape_pts, shape_edges = get_constellation_shape(n)
            
            theta = s_rng.uniform(-0.35, 0.35)
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            scale = s_rng.uniform(0.9, 1.15) if streak != longest_streak else 1.05
            flip = -1.0 if s_rng.random() < 0.4 else 1.0

            xs = [p[0] for p in shape_pts]
            ys = [p[1] for p in shape_pts]
            center_orig_x = sum(xs) / n
            center_orig_y = sum(ys) / n

            transformed_pts = []
            for ox, oy in shape_pts:
                dx = (ox - center_orig_x) * scale
                dy = (oy - center_orig_y) * scale * flip
                rx = dx * cos_t - dy * sin_t + s_rng.uniform(-2.5, 2.5)
                ry = dx * sin_t + dy * cos_t + s_rng.uniform(-2.5, 2.5)
                transformed_pts.append((rx, ry))

            min_tx = min(p[0] for p in transformed_pts)
            max_tx = max(p[0] for p in transformed_pts)
            min_ty = min(p[1] for p in transformed_pts)
            max_ty = max(p[1] for p in transformed_pts)

            place_x = max(35 - min_tx, min(width - 35 - max_tx, base_x))
            place_y = max(30 - min_ty, min(height - 30 - max_ty, base_y))

            for i, p in enumerate(streak):
                p["x"] = round(place_x + transformed_pts[i][0], 2)
                p["y"] = round(place_y + transformed_pts[i][1], 2)

            is_major = (streak == longest_streak)
            for u, v in shape_edges:
                all_edges.append((streak[u], streak[v], is_major))
        else:
            p = streak[0]
            p["x"] = round(max(30, min(width - 30, base_x + s_rng.uniform(-14, 14))), 2)
            p["y"] = round(s_rng.uniform(30, height - 30), 2)

    bg_rng = random.Random()
    dust = []
    for _ in range(280):
        dust.append({
            "x": round(bg_rng.uniform(5, width - 5), 2),
            "y": round(bg_rng.uniform(5, height - 5), 2),
            "r": round(bg_rng.uniform(0.25, 0.75), 2),
            "op": round(bg_rng.uniform(0.04, 0.22), 3),
        })

    max_count = max(p["count"] for p in active)

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background: transparent;">')
    parts.append("""  <defs>
    <radialGradient id="majorGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="1" />
      <stop offset="30%" stop-color="#bae6fd" stop-opacity="0.85" />
      <stop offset="70%" stop-color="#38bdf8" stop-opacity="0.35" />
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0" />
    </radialGradient>
    <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#bfdbfe" stop-opacity="0.75" />
      <stop offset="100%" stop-color="#3b82f6" stop-opacity="0" />
    </radialGradient>
    <style>
      .major-line { stroke: #bae6fd; stroke-width: 0.95; stroke-opacity: 0.65; stroke-dasharray: 2.5 3; }
      .minor-line { stroke: #7dd3fc; stroke-width: 0.6; stroke-opacity: 0.25; stroke-dasharray: 2 3; }
      .flare { stroke: #ffffff; stroke-width: 0.65; stroke-opacity: 0.85; }
      .star { cursor: pointer; }
      .star:hover circle.core { fill: #ffffff !important; stroke: #38bdf8; stroke-width: 1.2px; }
    </style>
  </defs>""")

    parts.append('  <g class="dust">')
    for d in dust:
        parts.append(f'    <circle cx="{d["x"]}" cy="{d["y"]}" r="{d["r"]}" fill="#94a3b8" opacity="{d["op"]}" />')
    parts.append('  </g>')

    parts.append('  <g class="lines">')
    for p1, p2, is_major in all_edges:
        cls = "major-line" if is_major else "minor-line"
        parts.append(f'    <line class="{cls}" x1="{p1["x"]}" y1="{p1["y"]}" x2="{p2["x"]}" y2="{p2["y"]}" />')
    parts.append('  </g>')

    parts.append('  <g class="stars">')
    for p in active:
        is_major = (p["date"] in longest_dates)
        norm = min(1.0, math.log(1 + p["count"]) / math.log(1 + max(max_count, 12)))

        date_lbl = p["dt"].strftime("%b %d, %Y")
        contrib_lbl = "1 contribution" if p["count"] == 1 else f"{p['count']} contributions"
        title = f"{date_lbl} - {contrib_lbl}"

        parts.append(f'    <g class="star">')
        parts.append(f'      <title>{title}</title>')

        if is_major:
            parts.append(f'      <circle cx="{p["x"]}" cy="{p["y"]}" r="6.5" fill="url(#majorGlow)" opacity="0.7" />')
            parts.append(f'      <line class="flare" x1="{p["x"]-6.5}" y1="{p["y"]}" x2="{p["x"]+6.5}" y2="{p["y"]}" />')
            parts.append(f'      <line class="flare" x1="{p["x"]}" y1="{p["y"]-6.5}" x2="{p["x"]}" y2="{p["y"]+6.5}" />')
            parts.append(f'      <circle class="core" cx="{p["x"]}" cy="{p["y"]}" r="1.8" fill="#ffffff" />')
        else:
            if norm > 0.4:
                parts.append(f'      <circle cx="{p["x"]}" cy="{p["y"]}" r="4.5" fill="url(#starGlow)" opacity="{round(0.25*norm, 2)}" />')
            fill = "#ffffff" if norm > 0.6 else "#dbeafe"
            op = round(0.55 + 0.45 * norm, 2)
            parts.append(f'      <circle class="core" cx="{p["x"]}" cy="{p["y"]}" r="1.8" fill="{fill}" opacity="{op}" />')

        parts.append('    </g>')

    parts.append('  </g>')
    parts.append('</svg>')
    return "\n".join(parts)


def main():
    days = fetch_contributions()
    if not days:
        sys.exit(1)
    svg = render_svg(days)
    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)


if __name__ == "__main__":
    main()
