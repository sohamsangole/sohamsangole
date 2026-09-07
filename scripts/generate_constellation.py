import os
import sys
import json
import math
import urllib.request
from datetime import datetime, timedelta, timezone

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "sohamsangole")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "assets/constellation.svg")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def fetch_github_contributions(username: str, token: str | None) -> list[dict]:
    if not token:
        print("No GITHUB_TOKEN or GH_TOKEN provided. Checking fallback options...")
        return None

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
                print(f"GraphQL Errors: {data['errors']}")
                return None
            calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            weeks = calendar["weeks"]
            days = []
            for week in weeks:
                for day in week["contributionDays"]:
                    days.append(
                        {
                            "date": day["date"],
                            "count": day["contributionCount"],
                            "weekday": day["weekday"],
                        }
                    )
            print(f"Successfully fetched {len(days)} days from GitHub GraphQL API. Total contributions: {calendar['totalContributions']}")
            return days
    except Exception as e:
        print(f"Failed to fetch from GitHub API: {e}")
        return None


def generate_sample_contributions() -> list[dict]:
    print("Generating sample celestial contribution history...")
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=364)
    start_date = start_date - timedelta(days=(start_date.weekday() + 1) % 7)

    import random
    rng = random.Random(42)

    days = []
    curr = start_date
    in_streak = False
    streak_len = 0
    max_streak = 0

    while curr <= today:
        weekday = (curr.weekday() + 1) % 7
        
        if in_streak:
            if streak_len < max_streak and rng.random() < 0.82:
                count = rng.choice([1, 2, 3, 4, 5, 7, 11])
                streak_len += 1
            else:
                in_streak = False
                count = 0
        else:
            if rng.random() < 0.28:
                in_streak = True
                streak_len = 1
                max_streak = rng.choice([2, 3, 4, 5, 7, 12, 18])
                count = rng.choice([1, 2, 3, 5, 8])
            else:
                count = 0

        days.append({
            "date": curr.strftime("%Y-%m-%d"),
            "count": count,
            "weekday": weekday,
        })
        curr += timedelta(days=1)

    return days


def calculate_brightness(count: int, max_count: int) -> dict:
    if count <= 0:
        return None

    norm = min(1.0, math.log(1 + count) / math.log(1 + max(max_count, 12)))
    core_opacity = round(0.50 + 0.50 * norm, 3)

    if norm < 0.35:
        core_fill = "#b8d5fd"
        glow_opacity = 0.0
    elif norm < 0.70:
        core_fill = "#e0eeff"
        glow_opacity = round(0.12 + 0.15 * norm, 3)
    else:
        core_fill = "#ffffff"
        glow_opacity = round(0.20 + 0.25 * norm, 3)

    return {
        "fill": core_fill,
        "opacity": core_opacity,
        "glow_opacity": glow_opacity,
        "glow_radius": 4.5,
    }


def render_constellation_svg(days: list[dict]) -> str:
    width = 880
    height = 170
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

    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">')
    svg_parts.append("""  <defs>
    <radialGradient id="skyGrad" cx="50%" cy="45%" r="75%" fx="45%" fy="40%">
      <stop offset="0%" stop-color="#0f172a" stop-opacity="0.9" />
      <stop offset="60%" stop-color="#090d16" stop-opacity="1" />
      <stop offset="100%" stop-color="#05070c" stop-opacity="1" />
    </radialGradient>
    <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#bfdbfe" stop-opacity="0.8" />
      <stop offset="50%" stop-color="#60a5fa" stop-opacity="0.3" />
      <stop offset="100%" stop-color="#3b82f6" stop-opacity="0" />
    </radialGradient>
    <style>
      .bg { fill: url(#skyGrad); }
      .constellation-line {
        stroke: #7dd3fc;
        stroke-width: 0.65;
        stroke-opacity: 0.22;
        stroke-linecap: round;
        stroke-linejoin: round;
      }
      .star {
        transition: transform 0.2s ease, opacity 0.2s ease;
        cursor: pointer;
      }
      .star:hover circle.core {
        fill: #ffffff !important;
        opacity: 1 !important;
        stroke: #93c5fd;
        stroke-width: 1px;
      }
      .star:hover circle.halo {
        opacity: 0.6 !important;
      }
    </style>
  </defs>""")

    svg_parts.append(f'  <rect class="bg" width="{width}" height="{height}" rx="12" />')

    svg_parts.append('  <g class="constellations">')
    for streak in streaks:
        points_str = " ".join(f"{p['x']},{p['y']}" for p in streak)
        svg_parts.append(f'    <polyline class="constellation-line" points="{points_str}" />')
    svg_parts.append('  </g>')

    STAR_RADIUS = 1.8
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

        svg_parts.append(
            f'      <circle class="core" cx="{p["x"]}" cy="{p["y"]}" '
            f'r="{STAR_RADIUS}" fill="{style["fill"]}" opacity="{style["opacity"]}" />'
        )
        svg_parts.append(f'    </g>')

    svg_parts.append('  </g>')
    svg_parts.append('</svg>')

    return "\n".join(svg_parts)


def main():
    print(f"Generating constellation for user: {GITHUB_USERNAME}")
    days = fetch_github_contributions(GITHUB_USERNAME, TOKEN)
    
    if not days:
        print("Using sample realistic contribution distribution for fallback.")
        days = generate_sample_contributions()

    svg_content = render_constellation_svg(days)

    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg_content)

    print(f"Successfully generated constellation SVG at: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
