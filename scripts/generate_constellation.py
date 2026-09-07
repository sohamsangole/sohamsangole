import os
import sys
import re
import json
import math
import urllib.request
from datetime import datetime, timedelta, timezone

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "sohamsangole")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "assets/constellation.svg")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def fetch_github_contributions_graphql(username: str, token: str) -> list[dict]:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                weekday
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Constellation-Generator",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            if "errors" in data:
                return None
            calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            days = []
            for week in calendar["weeks"]:
                for day in week["contributionDays"]:
                    days.append(
                        {
                            "date": day["date"],
                            "count": day["contributionCount"],
                            "weekday": day["weekday"],
                        }
                    )
            return days
    except Exception:
        return None


def fetch_public_contributions(username: str) -> list[dict]:
    url = f"https://github.com/users/{username}/contributions"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8")
            days = []
            pattern = re.compile(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="(\d+)"')
            count_pattern = re.compile(r'id="contribution-day-component-[^"]*"[^>]*>(\d+)\s+contribution')
            
            matches = re.findall(r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*>', html)
            if not matches:
                matches = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"', html)
            
            for date_str in matches:
                snippet = html[html.find(date_str):html.find(date_str) + 300]
                cnt_match = re.search(r'(\d+)\s+contribution', snippet)
                count = int(cnt_match.group(1)) if cnt_match else 0
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                weekday = (d.weekday() + 1) % 7
                days.append({"date": date_str, "count": count, "weekday": weekday})
            return days if days else None
    except Exception:
        return None


def read_existing_svg_contributions(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = re.compile(r'<title>([A-Za-z]{3}\s+\d{1,2},\s+\d{4})\s+-\s+(\d+)\s+contribution')
        matches = pattern.findall(content)
        if not matches:
            return None

        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=364)
        start_date = start_date - timedelta(days=(start_date.weekday() + 1) % 7)

        counts_by_date = {}
        for date_label, count_str in matches:
            dt = datetime.strptime(date_label, "%b %d, %Y").date()
            counts_by_date[dt.strftime("%Y-%m-%d")] = int(count_str)

        days = []
        curr = start_date
        while curr <= today:
            d_str = curr.strftime("%Y-%m-%d")
            weekday = (curr.weekday() + 1) % 7
            days.append({
                "date": d_str,
                "count": counts_by_date.get(d_str, 0),
                "weekday": weekday,
            })
            curr += timedelta(days=1)
        return days
    except Exception:
        return None


def calculate_brightness(count: int, max_count: int) -> dict:
    if count <= 0:
        return None

    norm = min(1.0, math.log(1 + count) / math.log(1 + max(max_count, 12)))
    core_opacity = round(0.55 + 0.45 * norm, 3)

    if norm < 0.35:
        core_fill = "#b8d5fd"
        glow_opacity = 0.0
        has_flare = False
    elif norm < 0.70:
        core_fill = "#e0eeff"
        glow_opacity = round(0.18 + 0.15 * norm, 3)
        has_flare = False
    else:
        core_fill = "#ffffff"
        glow_opacity = round(0.28 + 0.25 * norm, 3)
        has_flare = True

    return {
        "fill": core_fill,
        "opacity": core_opacity,
        "glow_opacity": glow_opacity,
        "glow_radius": 5.2,
        "has_flare": has_flare,
    }


def compute_constellation_edges(streak: list[dict]) -> list[tuple[dict, dict]]:
    if len(streak) < 2:
        return []

    if len(streak) == 2:
        return [(streak[0], streak[1])]

    n = len(streak)
    all_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            dx = streak[i]["x"] - streak[j]["x"]
            dy = streak[i]["y"] - streak[j]["y"]
            dist = math.hypot(dx, dy)
            time_dist = abs((streak[i]["datetime"] - streak[j]["datetime"]).days)
            score = dist * (1.0 + 0.12 * time_dist)
            all_pairs.append((score, i, j))

    all_pairs.sort(key=lambda p: p[0])

    parent = list(range(n))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a, b):
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[ra] = rb
            return True
        return False

    tree_edges = []
    degree = [0] * n
    for score, u, v in all_pairs:
        if union(u, v):
            tree_edges.append((streak[u], streak[v]))
            degree[u] += 1
            degree[v] += 1
            if len(tree_edges) == n - 1:
                break

    for score, u, v in all_pairs:
        if (streak[u], streak[v]) not in tree_edges and (streak[v], streak[u]) not in tree_edges:
            if degree[u] <= 2 and degree[v] <= 2 and score < 42.0:
                tree_edges.append((streak[u], streak[v]))
                degree[u] += 1
                degree[v] += 1
                if len(tree_edges) >= n + 1:
                    break

    return tree_edges


def generate_deep_sky_dust(width: float, height: float, count: int = 55) -> list[dict]:
    import random
    rng = random.Random(1337)
    dust = []
    for _ in range(count):
        x = round(rng.uniform(15, width - 15), 2)
        y = round(rng.uniform(15, height - 15), 2)
        r = round(rng.uniform(0.5, 0.9), 2)
        opacity = round(rng.uniform(0.06, 0.14), 3)
        dust.append({"x": x, "y": y, "r": r, "opacity": opacity})
    return dust


def render_constellation_svg(days: list[dict]) -> str:
    width = 880
    height = 175
    pad_x = 36
    pad_y = 28

    first_date = datetime.strptime(days[0]["date"], "%Y-%m-%d").date()
    
    grid_points = []
    for day in days:
        d = datetime.strptime(day["date"], "%Y-%m-%d").date()
        delta_days = (d - first_date).days
        start_weekday = (first_date.weekday() + 1) % 7
        total_offset = delta_days + start_weekday
        col = total_offset // 7
        row = (d.weekday() + 1) % 7
        grid_points.append({
            "date": day["date"],
            "count": day["count"],
            "col": col,
            "row": row,
            "datetime": d,
        })

    max_col = max(p["col"] for p in grid_points)
    total_cols = max(max_col, 52)
    step_x = (width - 2 * pad_x) / total_cols
    step_y = (height - 2 * pad_y) / 6.0

    for p in grid_points:
        p["x"] = round(pad_x + p["col"] * step_x, 2)
        p["y"] = round(pad_y + p["row"] * step_y, 2)

    counts = [p["count"] for p in grid_points if p["count"] > 0]
    max_count = max(counts) if counts else 10

    streaks = []
    current_streak = []

    for i, p in enumerate(grid_points):
        if p["count"] > 0:
            if not current_streak:
                current_streak.append(p)
            else:
                prev_p = current_streak[-1]
                if (p["datetime"] - prev_p["datetime"]).days == 1:
                    current_streak.append(p)
                else:
                    if len(current_streak) > 1:
                        streaks.append(current_streak)
                    current_streak = [p]
        else:
            if len(current_streak) > 1:
                streaks.append(current_streak)
            current_streak = []

    if len(current_streak) > 1:
        streaks.append(current_streak)

    constellation_edges = []
    for streak in streaks:
        edges = compute_constellation_edges(streak)
        constellation_edges.extend(edges)

    dust_stars = generate_deep_sky_dust(width, height, count=60)

    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background: transparent;">')
    svg_parts.append("""  <defs>
    <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#bfdbfe" stop-opacity="0.9" />
      <stop offset="40%" stop-color="#60a5fa" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#3b82f6" stop-opacity="0" />
    </radialGradient>
    <style>
      .celestial-guide {
        stroke: #93c5fd;
        stroke-opacity: 0.07;
        stroke-width: 0.5;
        stroke-dasharray: 4 12;
      }
      .constellation-line {
        stroke: #7dd3fc;
        stroke-width: 0.7;
        stroke-opacity: 0.32;
        stroke-linecap: round;
      }
      .flare {
        stroke: #ffffff;
        stroke-width: 0.5;
        stroke-opacity: 0.7;
        stroke-linecap: round;
      }
      .star {
        cursor: pointer;
      }
      .star:hover circle.core {
        fill: #ffffff !important;
        opacity: 1 !important;
        stroke: #93c5fd;
        stroke-width: 1px;
      }
      .star:hover circle.halo {
        opacity: 0.7 !important;
      }
    </style>
  </defs>""")

    svg_parts.append('  <g class="celestial-guides">')
    for r_idx in (1, 3, 5):
        gy = round(pad_y + r_idx * step_y, 2)
        svg_parts.append(f'    <line class="celestial-guide" x1="{pad_x - 10}" y1="{gy}" x2="{width - pad_x + 10}" y2="{gy}" />')
    svg_parts.append('  </g>')

    svg_parts.append('  <g class="deep-sky-dust">')
    for d in dust_stars:
        svg_parts.append(f'    <circle cx="{d["x"]}" cy="{d["y"]}" r="{d["r"]}" fill="#93c5fd" opacity="{d["opacity"]}" />')
    svg_parts.append('  </g>')

    svg_parts.append('  <g class="constellations">')
    for p1, p2 in constellation_edges:
        svg_parts.append(f'    <line class="constellation-line" x1="{p1["x"]}" y1="{p1["y"]}" x2="{p2["x"]}" y2="{p2["y"]}" />')
    svg_parts.append('  </g>')

    STAR_RADIUS = 1.8
    FLARE_LEN = 5.0
    svg_parts.append('  <g class="stars">')

    for p in grid_points:
        if p["count"] <= 0:
            continue

        style = calculate_brightness(p["count"], max_count)
        date_str = p["datetime"].strftime("%b %d, %Y")
        contrib_label = "1 contribution" if p["count"] == 1 else f"{p['count']} contributions"
        tooltip = f"{date_str} - {contrib_label}"

        svg_parts.append(f'    <g class="star">')
        svg_parts.append(f'      <title>{tooltip}</title>')

        if style["glow_opacity"] > 0:
            svg_parts.append(
                f'      <circle class="halo" cx="{p["x"]}" cy="{p["y"]}" '
                f'r="{style["glow_radius"]}" fill="url(#starGlow)" opacity="{style["glow_opacity"]}" />'
            )

        if style["has_flare"]:
            fx1, fx2 = round(p["x"] - FLARE_LEN, 2), round(p["x"] + FLARE_LEN, 2)
            fy1, fy2 = round(p["y"] - FLARE_LEN, 2), round(p["y"] + FLARE_LEN, 2)
            svg_parts.append(f'      <line class="flare" x1="{fx1}" y1="{p["y"]}" x2="{fx2}" y2="{p["y"]}" />')
            svg_parts.append(f'      <line class="flare" x1="{p["x"]}" y1="{fy1}" x2="{p["x"]}" y2="{p["x"]}" />')

        svg_parts.append(
            f'      <circle class="core" cx="{p["x"]}" cy="{p["y"]}" '
            f'r="{STAR_RADIUS}" fill="{style["fill"]}" opacity="{style["opacity"]}" />'
        )
        svg_parts.append(f'    </g>')

    svg_parts.append('  </g>')
    svg_parts.append('</svg>')

    return "\n".join(svg_parts)


def main():
    days = None
    if TOKEN:
        days = fetch_github_contributions_graphql(GITHUB_USERNAME, TOKEN)

    if not days:
        days = fetch_public_contributions(GITHUB_USERNAME)

    if not days:
        days = read_existing_svg_contributions(OUTPUT_PATH)

    if not days:
        print("No contribution data available to render.")
        sys.exit(1)

    svg_content = render_constellation_svg(days)

    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg_content)

    print(f"Generated constellation SVG at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
