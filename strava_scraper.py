"""
Strava Leaderboard Scraper (Manual Login Version)
Opens Chrome, lets you log in manually, then scrapes the leaderboard.

Requirements:
    pip install selenium

HOW IT WORKS:
1. Opens Chrome to the Strava login page
2. You log in manually in the browser window
3. Press Enter in the terminal when ready
4. Script scrapes the leaderboard automatically
"""

from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import time
import os
import shutil
import random

# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
SEGMENT_IDS = [
    40771040,   # Nickerson Grand Prix
    40763904,   # Philip Keyes Memorial Sprint
    40748016,   # Badland Grand Prix
    40727198,   # Mashpee River Grand Prix
    40728144,   # Greenough Grand Prix
    40727487,   # WBCA Grand Prix
    40721288,   # Sandy Neck Grand Prix
    #40674615,   # Truro Sprint
    #40668331,   # Higgins Crowell Grand Prix
    40701714,   # Four Ponds Grand Prix
    40679327,   # Otis Grand Prix
    #40665540,   # Shawme-Crowell Grand Prix
    #40632958,   # Coonamessett Grand Prix
    40631617,   # Long Pond Grand Prix
    40620316,   # WBCA Sprint
    #40620055,   # Wellfleet Grand Prix
    40617999,   # Maple Swamp Grand Prix
    40616232,   # CCCC / OJL Grand Prix
    40612877,   # Round Hill Sprint
]
GENDERS = ["M", "F"]   # Fetch both Men and Women leaderboards
TOP_N = 10
POINTS_GRAND_PRIX = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
POINTS_SPRINT     = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}

CHROMEDRIVER_PATH = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
TEMP_PROFILE      = r"C:\Users\dlafr\AppData\Local\Temp\strava_fresh_profile"


# -------------------------------------------------------
# Setup Chrome with a fresh temp profile
# -------------------------------------------------------
def create_driver():
    if os.path.exists(TEMP_PROFILE):
        shutil.rmtree(TEMP_PROFILE, ignore_errors=True)
    os.makedirs(TEMP_PROFILE, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={TEMP_PROFILE}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    
    # Add realistic User-Agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Additional stealth options
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-gpu-sandbox")
    
    print("🔧 Launching Chrome...")
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    
    # Inject anti-webdriver detection scripts
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
    driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
    driver.execute_script("""
        window.chrome = {
            runtime: {}
        };
    """)
    driver.execute_script("""
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({ state: Notification.permission })
            })
        });
    """)
    
    return driver


# -------------------------------------------------------
# Scrape Leaderboard
# -------------------------------------------------------
def get_sidebar_data(driver):
    """Extract KOM/QOM/segment name from the React sidebar JSON."""
    import json
    soup = BeautifulSoup(driver.page_source, "html.parser")
    sidebar = soup.find(attrs={"data-react-class": "SegmentDetailsSideBar"})
    if not sidebar:
        return {}
    props = json.loads(sidebar["data-react-props"])
    return props.get("sideBarProps", {})


def parse_row(cols, headers):
    """Parse a table row into a dict using detected column headers."""
    import re
    entry = {}
    for i, col in enumerate(cols):
        if i >= len(headers):
            break
        h = headers[i]
        val = col.text.strip()
        if "rank" in h:
            pass
        elif "name" in h or "athlete" in h:
            entry["name"] = val
        elif "date" in h:
            entry["date"] = val
        elif "speed" in h or "pace" in h:
            entry["speed"] = val if val not in ["-", ""] else "--"
        elif "power" in h:
            power_match = re.search("([0-9,]+ *W)", val)
            entry["power"] = power_match.group(1).strip() if power_match else ("--" if val in ["-", ""] else val)
        elif "hr" in h or "heart" in h or "bpm" in h:
            entry["hr"] = val if val not in ["-", ""] else "--"
        elif "time" in h or "elap" in h:
            entry["time"] = val
    return entry


def scrape_leaderboard(driver, segment_id, gender="M", top_n=10):
    url = f"https://www.strava.com/segments/{segment_id}?gender={gender}"
    print(f"\n📊 Loading {'Men' if gender == 'M' else 'Women'} leaderboard for segment {segment_id}...")
    driver.get(url)
    time.sleep(4)  # Increased from 3 to 4 seconds
    
    # Add random-like delay to avoid detection
    time.sleep(random.uniform(1, 2))

    # ---- Step 1: Check sidebar to see if anyone of this gender has completed the segment ----
    sidebar = get_sidebar_data(driver)
    fastest = sidebar.get("fastestTimes", {})
    gender_key = "men" if gender == "M" else "women"
    label = "KOM" if gender == "M" else "QOM"
    kom = fastest.get(gender_key, {})

    if not kom:
        print(f"   ⚠️  No {label} found — no completions for this gender, skipping.")
        return []

    kom_name = kom.get("name", "Unknown")
    kom_time = kom.get("stats", [{}])[0].get("value", "?")
    kom_date = kom.get("date", "--")
    segment_name = driver.title.split(" | ")[0]
    print(f"   Segment: {segment_name}")
    print(f"   ✅ {label}: {kom_name} ({kom_time})")

    # ---- Step 2: Scroll to trigger full render ----
    for scroll_pos in [0.5, 1.0, 0]:
        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_pos});")
        time.sleep(1)

    # ---- Step 3: Wait for table rows to stabilise ----
    prev_count = 0
    for _ in range(10):
        rows = driver.find_elements(By.CSS_SELECTOR, "table.table-leaderboard tr") or                driver.find_elements(By.CSS_SELECTOR, "table tr")
        if len(rows) == prev_count and len(rows) > 0:
            break
        prev_count = len(rows)
        time.sleep(1)

    all_rows = driver.find_elements(By.CSS_SELECTOR, "table.table-leaderboard tr") or                driver.find_elements(By.CSS_SELECTOR, "table tr")

    # ---- Step 4: Detect column headers ----
    headers = []
    for row in all_rows:
        header_cells = row.find_elements(By.CSS_SELECTOR, "th")
        if header_cells:
            headers = [h.text.strip().lower() for h in header_cells]
            break

    # ---- Step 5: Parse table rows ----
    entries = []
    next_rank = 1
    for row in all_rows:
        cols = row.find_elements(By.CSS_SELECTOR, "td")
        if len(cols) < 3:
            continue
        rank_text = cols[0].text.strip()
        if rank_text.isdigit():
            rank = int(rank_text)
            next_rank = rank + 1
        else:
            rank = next_rank
            next_rank += 1

        entry = {"rank": rank}
        if headers:
            entry.update(parse_row(cols, headers))
        else:
            col_texts = [c.text.strip() for c in cols]
            entry.update({
                "name":  col_texts[1] if len(col_texts) > 1 else "",
                "date":  col_texts[2] if len(col_texts) > 2 else "--",
                "speed": col_texts[3] if len(col_texts) > 3 else "--",
                "power": col_texts[4] if len(col_texts) > 4 else "--",
                "hr":    col_texts[5] if len(col_texts) > 5 else "--",
                "time":  col_texts[-1] if col_texts else "--",
            })

        entries.append(entry)
        if len(entries) >= top_n:
            break

    # ---- Step 6: Ensure KOM/QOM is at rank 1 with full sidebar data ----
    # The table uses auto-assigned ranks starting from 1, but rank numbers may be
    # off by 1 because Strava shows the KOM with an empty rank cell (icon instead of number).
    # Strategy: find the KOM in the table, fix their rank to 1, then renumber
    # everyone else sequentially based on their sorted position.

    existing = next((e for e in entries if e.get("name") == kom_name), None)
    if existing:
        # KOM is in the table — merge sidebar data and correct rank
        existing["rank"] = 1
        existing["date"] = kom_date
        existing["time"] = kom_time
        # Sort by current rank order, then reassign 1,2,3... cleanly
        entries.sort(key=lambda x: (x is not existing, x.get("rank", 99)))
        for i, e in enumerate(entries):
            e["rank"] = i + 1
    else:
        # KOM not in table — add from sidebar only, renumber rest from 2
        for i, e in enumerate(entries):
            e["rank"] = i + 2
        kom_entry = {"rank": 1, "name": kom_name, "date": kom_date, "time": kom_time}
        entries.insert(0, kom_entry)

    entries.sort(key=lambda x: x["rank"])
    # Store segment name in each entry for completionist logic
    for e in entries:
        e["segment_name"] = segment_name
    # Assign points based on rank — Sprint segments use a different points table
    is_sprint = "sprint" in segment_name.lower()
    points_table = POINTS_SPRINT if is_sprint else POINTS_GRAND_PRIX
    for e in entries:
        e["points"] = points_table.get(e["rank"], 0)
    return entries[:top_n]


# -------------------------------------------------------
# Display Leaderboard
# -------------------------------------------------------
def display_leaderboard(entries, gender="M"):
    gender_label = "Men" if gender == "M" else "Women"

    if not entries:
        print("\n⚠️  No leaderboard entries found.")
        print("Open debug.html in your browser to inspect.")
        return

    print(f"\n🏆 Top {len(entries)} {gender_label} - Segment Leaderboard")
    print(f"{'Rank':<6} {'Name':<25} {'Date':<14} {'Speed':<10} {'Power':<8} {'HR':<6} {'Time':<10} {'Pts'}")
    print("-" * 95)
    for e in entries:
        print(
            f"{e.get('rank',''):<6} "
            f"{e.get('name',''):<25} "
            f"{e.get('date','--'):<14} "
            f"{e.get('speed','--'):<10} "
            f"{e.get('power','--'):<8} "
            f"{e.get('hr','--'):<6} "
            f"{e.get('time','--'):<10} "
            f"{e.get('points','')}"
        )


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
if __name__ == "__main__":
    print("=" * 55)
    print("   Strava Leaderboard Scraper (Manual Login)")
    print("=" * 55)

    driver = create_driver()

    # Navigate to Strava login
    print("\n🌐 Opening Strava login page...")
    driver.get("https://www.strava.com/login")

    print("\n" + "=" * 55)
    print("  👉 Please log into Strava in the Chrome window")
    print("  👉 Once you are fully logged in and can see")
    print("     your dashboard, come back here and press Enter")
    print("=" * 55)
    input("\nPress Enter once you are logged in...")

    # Accumulate points across all segments
    men_totals = {}
    women_totals = {}
    men_completionist = {}
    women_completionist = {}
    men_totals_detail = {}
    women_totals_detail = {}
    men_comp_detail = {}
    women_comp_detail = {}

    try:
        for segment_id in SEGMENT_IDS:
            segment_label = str(segment_id)  # Will be updated after first scrape
            for gender in GENDERS:
                entries = scrape_leaderboard(driver, segment_id, gender=gender, top_n=TOP_N)
                if entries and gender == GENDERS[0]:
                    # Now we have the segment name — print the header
                    seg_name = entries[0].get("segment_name", str(segment_id))
                    print(f"\n{'='*65}")
                    print(f"  Segment {segment_id}: {seg_name}")
                    print(f"{'='*65}")
                if entries:
                    display_leaderboard(entries, gender=gender)
                    print()

                    totals = men_totals if gender == "M" else women_totals
                    comp_totals = men_completionist if gender == "M" else women_completionist
                    totals_detail = men_totals_detail if gender == "M" else women_totals_detail
                    comp_detail = men_comp_detail if gender == "M" else women_comp_detail

                    # Determine completionist points for this segment
                    segment_name = entries[0].get("segment_name", "")
                    is_sprint = "sprint" in segment_name.lower()
                    comp_pts = 8 if is_sprint else 25

                    for e in entries:
                        name = e.get("name", "Unknown")
                        seg_name = e.get("segment_name", str(segment_id))

                        # Race points (rank-based)
                        pts = e.get("points", 0)
                        rank = e.get("rank", "")
                        if pts > 0:
                            totals[name] = totals.get(name, 0) + pts
                            # Track per-segment breakdown including rank
                            if name not in totals_detail:
                                totals_detail[name] = []
                            totals_detail[name].append((seg_name, rank, pts))

                        # Completionist points (flat award for completing segment)
                        comp_totals[name] = comp_totals.get(name, 0) + comp_pts
                        if name not in comp_detail:
                            comp_detail[name] = []
                        comp_detail[name].append((seg_name, None, comp_pts))
            
            # Add delay between segments to avoid rate limiting
            time.sleep(random.uniform(3, 5))

        # Ask if user wants detailed breakdown
        print()
        detailed = input("Would you like detailed segment breakdowns in the final standings? (yes/no): ").strip().lower() in ["yes", "y"]

        # Set up output file in same directory as script
        import sys
        from datetime import datetime
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(script_dir, f"formula_u_standings_{timestamp}.txt")

        def output(text=""):
            print(text)
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(text + "\n")

        print(f"\n📄 Saving standings to: {output_file}")

        def print_standings(icon, title, totals, detail, show_rank=False):
            output("\n" + "="*65)
            output(f"  {icon} {title}")
            output("="*65)
            output(f"{'Rank':<6} {'Name':<30} {'Points'}")
            output("-" * 50)
            for i, (name, pts) in enumerate(sorted(totals.items(), key=lambda x: x[1], reverse=True), 1):
                output(f"{i:<6} {name:<30} {pts}")
                if detailed and name in detail:
                    for seg_name, seg_rank, seg_pts in sorted(detail[name], key=lambda x: x[2], reverse=True):
                        if show_rank and seg_rank:
                            output(f"{'':6}   {seg_name:<48} P{seg_rank:<4} {seg_pts}")
                        else:
                            output(f"{'':6}   {seg_name:<50} {seg_pts}")

        print_standings("🏆", "OVERALL MEN'S RIDERS' CHAMPIONSHIP STANDINGS",   men_totals,          men_totals_detail,   show_rank=True)
        print_standings("🏆", "OVERALL WOMEN'S RIDERS' CHAMPIONSHIP STANDINGS", women_totals,        women_totals_detail, show_rank=True)
        print_standings("🎯", "MEN'S COMPLETORS' CHAMPIONSHIP STANDINGS",        men_completionist,   men_comp_detail,     show_rank=False)
        print_standings("🎯", "WOMEN'S COMPLETORS' CHAMPIONSHIP STANDINGS",      women_completionist, women_comp_detail,   show_rank=False)

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("Keeping browser open for 20 seconds...")
        time.sleep(20)
    finally:
        driver.quit()
        shutil.rmtree(TEMP_PROFILE, ignore_errors=True)
        print("\n✅ Done!")