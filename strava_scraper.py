"""
Formula U - Strava Leaderboard Scraper + PDF Generator

Requirements:
    pip install selenium beautifulsoup4 reportlab

HOW IT WORKS:
1. Opens Chrome to the Strava login page
2. You log in manually in the browser window
3. Press Enter in the terminal when ready
4. Script scrapes all segment leaderboards
5. Generates standings text file and PDF in the same folder as this script

SETUP:
- Place chromedriver.exe in the same folder as this script
- Place Formula_You_with_Emoji.png in the same folder as this script
"""

import os, sys, shutil, time, json, re
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

# -------------------------------------------------------
# PATHS  (all relative to this script's folder)
# -------------------------------------------------------
SCRIPT_DIR        = os.path.dirname(os.path.abspath(sys.argv[0]))
CHROMEDRIVER_PATH = os.path.join(SCRIPT_DIR, "chromedriver.exe")
LOGO_PATH         = os.path.join(SCRIPT_DIR, "Formula_You_with_Emoji.png")
TEMP_PROFILE      = os.path.join(os.environ.get("TEMP", SCRIPT_DIR), "strava_fresh_profile")

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
    40620055,
]
GENDERS           = ["M", "F"]
TOP_N             = 10
POINTS_GRAND_PRIX = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
POINTS_SPRINT     = {1: 8,  2: 7,  3: 6,  4: 5,  5: 4,  6: 3, 7: 2, 8: 1}

# -------------------------------------------------------
# CHROME DRIVER
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
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-extensions")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    print("🔧 Launching Chrome...")
    service = Service(CHROMEDRIVER_PATH)
    driver  = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# -------------------------------------------------------
# SCRAPING HELPERS
# -------------------------------------------------------
def get_sidebar_data(driver):
    soup    = BeautifulSoup(driver.page_source, "html.parser")
    sidebar = soup.find(attrs={"data-react-class": "SegmentDetailsSideBar"})
    if not sidebar:
        return {}
    props = json.loads(sidebar["data-react-props"])
    return props.get("sideBarProps", {})


def parse_row(cols, headers):
    entry = {}
    for i, col in enumerate(cols):
        if i >= len(headers):
            break
        h   = headers[i]
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
            m = re.search("([0-9,]+ *W)", val)
            entry["power"] = m.group(1).strip() if m else ("--" if val in ["-", ""] else val)
        elif "hr" in h or "heart" in h or "bpm" in h:
            entry["hr"] = val if val not in ["-", ""] else "--"
        elif "time" in h or "elap" in h:
            entry["time"] = val
    return entry


def scrape_leaderboard(driver, segment_id, gender="M", top_n=10):
    url = f"https://www.strava.com/segments/{segment_id}?gender={gender}"
    print(f"\n📊 Loading {'Men' if gender == 'M' else 'Women'} leaderboard for segment {segment_id}...")
    driver.get(url)
    time.sleep(3)

    sidebar      = get_sidebar_data(driver)
    fastest      = sidebar.get("fastestTimes", {})
    gender_key   = "men" if gender == "M" else "women"
    label        = "KOM" if gender == "M" else "QOM"
    kom          = fastest.get(gender_key, {})

    if not kom:
        print(f"   ⚠️  No {label} found — no completions for this gender, skipping.")
        return []

    kom_name     = kom.get("name", "Unknown")
    kom_time     = kom.get("stats", [{}])[0].get("value", "?")
    kom_date     = kom.get("date", "--")
    segment_name = driver.title.split(" | ")[0]
    print(f"   Segment: {segment_name}")
    print(f"   ✅ {label}: {kom_name} ({kom_time})")

    for scroll_pos in [0.5, 1.0, 0]:
        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_pos});")
        time.sleep(1)

    prev_count = 0
    for _ in range(10):
        rows = (driver.find_elements(By.CSS_SELECTOR, "table.table-leaderboard tr") or
                driver.find_elements(By.CSS_SELECTOR, "table tr"))
        if len(rows) == prev_count and len(rows) > 0:
            break
        prev_count = len(rows)
        time.sleep(1)

    all_rows = (driver.find_elements(By.CSS_SELECTOR, "table.table-leaderboard tr") or
                driver.find_elements(By.CSS_SELECTOR, "table tr"))

    headers = []
    for row in all_rows:
        header_cells = row.find_elements(By.CSS_SELECTOR, "th")
        if header_cells:
            headers = [h.text.strip().lower() for h in header_cells]
            break

    entries   = []
    next_rank = 1
    for row in all_rows:
        cols = row.find_elements(By.CSS_SELECTOR, "td")
        if len(cols) < 3:
            continue
        rank_text = cols[0].text.strip()
        if rank_text.isdigit():
            rank      = int(rank_text)
            next_rank = rank + 1
        else:
            rank      = next_rank
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

    existing = next((e for e in entries if e.get("name") == kom_name), None)
    if existing:
        existing["rank"] = 1
        existing["date"] = kom_date
        existing["time"] = kom_time
        entries.sort(key=lambda x: (x is not existing, x.get("rank", 99)))
        for i, e in enumerate(entries):
            e["rank"] = i + 1
    else:
        for i, e in enumerate(entries):
            e["rank"] = i + 2
        entries.insert(0, {"rank": 1, "name": kom_name, "date": kom_date, "time": kom_time})

    entries.sort(key=lambda x: x["rank"])
    is_sprint    = "sprint" in segment_name.lower()
    points_table = POINTS_SPRINT if is_sprint else POINTS_GRAND_PRIX
    for e in entries:
        e["segment_name"] = segment_name
        e["points"]       = points_table.get(e["rank"], 0)
    return entries[:top_n]


def display_leaderboard(entries, gender="M"):
    gender_label = "Men" if gender == "M" else "Women"
    if not entries:
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
# PDF GENERATION
# -------------------------------------------------------
def generate_pdf(men_totals, women_totals, men_completionist, women_completionist,
                 men_totals_detail, women_totals_detail, men_comp_detail, women_comp_detail,
                 detailed, timestamp):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, PageBreak)
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.utils import ImageReader
    except ImportError:
        print("⚠️  reportlab not installed — skipping PDF generation. Run: pip install reportlab")
        return

    # ---- Fonts: Segoe UI (Windows built-in) ----
    FONT_BOLD    = "Helvetica-Bold"
    FONT_REGULAR = "Helvetica"
    WIN_FONTS    = {
        "SegoeUI-Bold":    r"C:\Windows\Fonts\segoeuib.ttf",
        "SegoeUI-Regular": r"C:\Windows\Fonts\segoeui.ttf",
    }
    for name, path in WIN_FONTS.items():
        try:
            pdfmetrics.registerFont(TTFont(name, path))
            FONT_BOLD    = "SegoeUI-Bold"
            FONT_REGULAR = "SegoeUI-Regular"
        except Exception:
            pass

    # ---- Colors ----
    RED       = colors.HexColor("#E10600")
    DARK_GRAY = colors.HexColor("#2C2C2C")
    MID_GRAY  = colors.HexColor("#555555")
    WHITE     = colors.white
    GOLD      = colors.HexColor("#F6C95F")
    SILVER    = colors.HexColor("#C0C0C0")
    BRONZE    = colors.HexColor("#CD7F32")
    STRIPE    = colors.HexColor("#FBF0EB")

    def medal_color(rank):
        r = int(rank)
        if r == 1: return GOLD
        if r == 2: return SILVER
        if r == 3: return BRONZE
        return None

    # ---- Styles ----
    section_style = ParagraphStyle("sec", fontName=FONT_BOLD, fontSize=19,
        textColor=RED, spaceBefore=0, spaceAfter=6, alignment=TA_CENTER)

    # ---- Banner ----
    def banner(canvas, doc):
        canvas.saveState()
        w, h = letter
        canvas.setFillColor(RED)
        canvas.rect(0, h - 1.3*inch, w, 1.3*inch, fill=1, stroke=0)
        try:
            logo = ImageReader(LOGO_PATH)
            canvas.drawImage(logo, 0.3*inch, h - 1.2*inch,
                             width=1.8*inch, height=0.9*inch,
                             mask="auto", preserveAspectRatio=True)
        except Exception:
            pass
        canvas.setFillColor(WHITE)
        canvas.setFont(FONT_BOLD, 20)
        canvas.drawString(2.3*inch, h - 0.58*inch, "FORMULA U STANDINGS")
        canvas.setFont(FONT_REGULAR, 10)
        canvas.drawString(2.3*inch, h - 0.82*inch,
                          f"{datetime.now().strftime('%B %d, %Y')}  \u2022  Cape Cod NEMBA")
        canvas.setFillColor(MID_GRAY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawCentredString(w/2, 0.35*inch, f"Page {doc.page}")
        canvas.restoreState()

    # ---- Riders detail table ----
    def build_riders_detail(data):
        col_widths  = [0.55*inch, 2.0*inch, 0.55*inch, 0.55*inch]
        hdr_style   = ParagraphStyle("hdr", fontName=FONT_BOLD, fontSize=9,
                                     textColor=WHITE, alignment=TA_CENTER)
        table_data  = [["Rank", "Name / Segment", "Pos", "Pts"]]
        for rank, name, pts, segments in data:
            table_data.append([rank, name, "", pts])
            for seg, pos, spts in segments:
                short = seg.replace("Formula U - ", "").replace(" Grand Prix", " GP")
                table_data.append(["", f"  {short}", pos, spts])

        t          = Table(table_data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND",    (0,0), (-1,0), DARK_GRAY),
            ("TEXTCOLOR",     (0,0), (-1,0), WHITE),
            ("FONTNAME",      (0,0), (-1,0), FONT_BOLD),
            ("FONTSIZE",      (0,0), (-1,0), 9),
            ("ALIGN",         (0,0), (-1,0), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING",    (0,0), (-1,0), 6),
            ("GRID",          (0,0), (-1,-1), 0.25, colors.HexColor("#DDDDDD")),
        ]
        row_idx = 1
        for rank, name, pts, segments in data:
            mc = medal_color(rank)
            if mc:
                style_cmds += [
                    ("BACKGROUND", (0,row_idx), (-1,row_idx), mc),
                    ("FONTNAME",   (0,row_idx), (-1,row_idx), FONT_BOLD),
                    ("TEXTCOLOR",  (0,row_idx), (-1,row_idx), DARK_GRAY),
                ]
            else:
                bg = WHITE if row_idx % 2 == 0 else STRIPE
                style_cmds += [
                    ("BACKGROUND", (0,row_idx), (-1,row_idx), bg),
                    ("FONTNAME",   (0,row_idx), (-1,row_idx), FONT_BOLD),
                    ("TEXTCOLOR",  (0,row_idx), (-1,row_idx), DARK_GRAY),
                ]
            style_cmds += [
                ("FONTSIZE",      (0,row_idx), (-1,row_idx), 9),
                ("ALIGN",         (0,row_idx), (0,row_idx), "CENTER"),
                ("ALIGN",         (2,row_idx), (-1,row_idx), "CENTER"),
                ("TOPPADDING",    (0,row_idx), (-1,row_idx), 5),
                ("BOTTOMPADDING", (0,row_idx), (-1,row_idx), 3),
            ]
            row_idx += 1
            for _ in segments:
                style_cmds += [
                    ("FONTSIZE",      (0,row_idx), (-1,row_idx), 7.5),
                    ("TEXTCOLOR",     (1,row_idx), (1,row_idx), MID_GRAY),
                    ("FONTNAME",      (0,row_idx), (-1,row_idx), "Helvetica-Oblique"),
                    ("FONTNAME",      (0,row_idx), (0,row_idx), "Helvetica-Bold"),
                    ("ALIGN",         (2,row_idx), (-1,row_idx), "CENTER"),
                    ("BACKGROUND",    (0,row_idx), (-1,row_idx), colors.HexColor("#FAF7F5")),
                    ("TOPPADDING",    (0,row_idx), (-1,row_idx), 2),
                    ("BOTTOMPADDING", (0,row_idx), (-1,row_idx), 2),
                    ("LEFTPADDING",   (1,row_idx), (1,row_idx), 16),
                ]
                row_idx += 1
        t.setStyle(TableStyle(style_cmds))
        return t

    # ---- Completors table ----
    def build_comp_table(data):
        from reportlab.platypus import Paragraph as Para
        col_widths  = [0.6*inch, 2.0*inch, 0.7*inch, 2.75*inch]
        seg_style   = ParagraphStyle("seg", fontName="Helvetica", fontSize=7,
                                     textColor=MID_GRAY, leading=10)
        bold_s      = ParagraphStyle("bs",  fontName=FONT_BOLD, fontSize=9)
        bold_cs     = ParagraphStyle("bcs", fontName=FONT_BOLD, fontSize=9, alignment=TA_CENTER)
        rank_s      = ParagraphStyle("rs",  fontName=FONT_BOLD, fontSize=9, alignment=TA_CENTER)
        hdr_s       = ParagraphStyle("hs",  fontName=FONT_BOLD, fontSize=9,
                                     textColor=WHITE, alignment=TA_CENTER)
        table_data  = [[Para("Rank", hdr_s), Para("Name", hdr_s),
                        Para("Points", hdr_s), Para("Segments Completed", hdr_s)]]
        for rank, name, pts, segs in data:
            table_data.append([
                Para(f"<b>{rank}</b>", rank_s),
                Para(f"<b>{name}</b>", bold_s),
                Para(f"<b>{pts}</b>",  bold_cs),
                Para(",  ".join(segs), seg_style),
            ])
        t          = Table(table_data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND",    (0,0), (-1,0), DARK_GRAY),
            ("TEXTCOLOR",     (0,0), (-1,0), WHITE),
            ("FONTNAME",      (0,0), (-1,0), FONT_BOLD),
            ("FONTSIZE",      (0,0), (-1,0), 9),
            ("ALIGN",         (0,0), (-1,0), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING",    (0,0), (-1,0), 6),
            ("FONTSIZE",      (0,1), (-1,-1), 9),
            ("ALIGN",         (0,1), (0,-1), "CENTER"),
            ("ALIGN",         (2,1), (2,-1), "CENTER"),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, STRIPE]),
            ("GRID",          (0,0), (-1,-1), 0.25, colors.HexColor("#DDDDDD")),
            ("TOPPADDING",    (0,1), (-1,-1), 5),
            ("BOTTOMPADDING", (0,1), (-1,-1), 5),
            ("LEFTPADDING",   (1,1), (1,-1), 8),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]
        for i, (rank, *_) in enumerate(data, 1):
            mc = medal_color(rank)
            if mc:
                style_cmds += [
                    ("BACKGROUND", (0,i), (-1,i), mc),
                    ("TEXTCOLOR",  (0,i), (2,i),  DARK_GRAY),
                    ("FONTNAME",   (0,i), (2,i),  FONT_BOLD),
                ]
        t.setStyle(TableStyle(style_cmds))
        return t

    # ---- Build data from totals dicts ----
    def build_riders_data(totals, detail):
        result = []
        for i, (name, pts) in enumerate(sorted(totals.items(), key=lambda x: x[1], reverse=True), 1):
            segs = []
            if name in detail:
                for seg_name, seg_rank, seg_pts in sorted(detail[name], key=lambda x: x[1]):
                    short = seg_name.replace("Formula U - ", "").replace(" Grand Prix", " GP")
                    segs.append((short, f"P{seg_rank}", str(seg_pts)))
            result.append((str(i), name, str(pts), segs))
        return result

    def build_comp_data(totals, detail):
        result = []
        for i, (name, pts) in enumerate(sorted(totals.items(), key=lambda x: x[1], reverse=True), 1):
            segs = []
            if name in detail:
                for seg_name, _, _ in detail[name]:
                    short = seg_name.replace("Formula U - ", "").replace(" Grand Prix", " GP")
                    segs.append(short)
            result.append((str(i), name, str(pts), segs))
        return result

    # ---- Assemble PDF ----
    pdf_path = os.path.join(SCRIPT_DIR, f"formula_u_standings_{timestamp}.pdf")
    doc      = SimpleDocTemplate(pdf_path, pagesize=letter,
                                 topMargin=1.45*inch, bottomMargin=0.6*inch,
                                 leftMargin=0.6*inch, rightMargin=0.6*inch)
    story         = []
    first_section = [True]

    def section_header(text):
        if first_section[0]:
            first_section[0] = False
        else:
            story.append(PageBreak())
        story.append(Paragraph(text, section_style))
        story.append(Spacer(1, 6))

    section_header("🏆  MEN'S RIDERS' CHAMPIONSHIP STANDINGS")
    story.append(build_riders_detail(build_riders_data(men_totals, men_totals_detail)))

    section_header("🏆  WOMEN'S RIDERS' CHAMPIONSHIP STANDINGS")
    story.append(build_riders_detail(build_riders_data(women_totals, women_totals_detail)))

    section_header("🎯  MEN'S COMPLETORS' CHAMPIONSHIP STANDINGS")
    story.append(build_comp_table(build_comp_data(men_completionist, men_comp_detail)))

    section_header("🎯  WOMEN'S COMPLETORS' CHAMPIONSHIP STANDINGS")
    story.append(build_comp_table(build_comp_data(women_completionist, women_comp_detail)))

    doc.build(story, onFirstPage=banner, onLaterPages=banner)
    print(f"\n📄 PDF saved to: {pdf_path}")

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
if __name__ == "__main__":
    print("=" * 55)
    print("   Formula U - Strava Leaderboard Scraper")
    print("=" * 55)

    driver = create_driver()

    print("\n🌐 Opening Strava login page...")
    driver.get("https://www.strava.com/login")

    print("\n" + "=" * 55)
    print("  👉 Please log into Strava in the Chrome window")
    print("  👉 Once fully logged in, come back here and")
    print("     press Enter")
    print("=" * 55)
    input("\nPress Enter once you are logged in...")

    men_totals        = {}
    women_totals      = {}
    men_completionist = {}
    women_completionist = {}
    men_totals_detail   = {}
    women_totals_detail = {}
    men_comp_detail     = {}
    women_comp_detail   = {}

    try:
        for segment_id in SEGMENT_IDS:
            for gender in GENDERS:
                entries = scrape_leaderboard(driver, segment_id, gender=gender, top_n=TOP_N)
                if entries and gender == GENDERS[0]:
                    seg_name = entries[0].get("segment_name", str(segment_id))
                    print(f"\n{'='*65}")
                    print(f"  Segment {segment_id}: {seg_name}")
                    print(f"{'='*65}")
                if entries:
                    display_leaderboard(entries, gender=gender)
                    print()

                    totals       = men_totals        if gender == "M" else women_totals
                    comp_totals  = men_completionist if gender == "M" else women_completionist
                    totals_detail = men_totals_detail if gender == "M" else women_totals_detail
                    comp_detail  = men_comp_detail   if gender == "M" else women_comp_detail

                    segment_name = entries[0].get("segment_name", "")
                    is_sprint    = "sprint" in segment_name.lower()
                    comp_pts     = 8 if is_sprint else 25

                    for e in entries:
                        name     = e.get("name", "Unknown")
                        seg_name = e.get("segment_name", str(segment_id))
                        pts      = e.get("points", 0)
                        rank     = e.get("rank", "")
                        if pts > 0:
                            totals[name] = totals.get(name, 0) + pts
                            if name not in totals_detail:
                                totals_detail[name] = []
                            totals_detail[name].append((seg_name, rank, pts))
                        comp_totals[name] = comp_totals.get(name, 0) + comp_pts
                        if name not in comp_detail:
                            comp_detail[name] = []
                        comp_detail[name].append((seg_name, None, comp_pts))

        # ---- Text output ----
        print()
        detailed  = input("Would you like detailed segment breakdowns in the final standings? (yes/no): ").strip().lower() in ["yes", "y"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_path  = os.path.join(SCRIPT_DIR, f"formula_u_standings_{timestamp}.txt")

        def output(text=""):
            print(text)
            with open(txt_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")

        print(f"\n📄 Saving text standings to: {txt_path}")

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

        print_standings("🏆", "MEN'S RIDERS' CHAMPIONSHIP STANDINGS",   men_totals,         men_totals_detail,   show_rank=True)
        print_standings("🏆", "WOMEN'S RIDERS' CHAMPIONSHIP STANDINGS", women_totals,       women_totals_detail, show_rank=True)
        print_standings("🎯", "MEN'S COMPLETORS' CHAMPIONSHIP STANDINGS",   men_completionist, men_comp_detail, show_rank=False)
        print_standings("🎯", "WOMEN'S COMPLETORS' CHAMPIONSHIP STANDINGS", women_completionist, women_comp_detail, show_rank=False)

        # ---- PDF output ----
        generate_pdf(men_totals, women_totals, men_completionist, women_completionist,
                     men_totals_detail, women_totals_detail, men_comp_detail, women_comp_detail,
                     detailed, timestamp)

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        import traceback; traceback.print_exc()
        print("Keeping browser open for 20 seconds...")
        time.sleep(20)
    finally:
        driver.quit()
        shutil.rmtree(TEMP_PROFILE, ignore_errors=True)
        print("\n✅ Done!")