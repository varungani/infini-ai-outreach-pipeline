#!/usr/bin/env python3
"""
InfiniAI Outreach Engine — Enrichment Pipeline
============================================================
Usage:
  python enrich.py --companies "Republic Bank, CIBC Caribbean" --region "Caribbean Banking"
  python enrich.py --file companies.txt --region "Dominican Republic Banking"

Outputs: Google Sheet populated live, row by row.
"""

import os, sys, json, time, argparse, re
from datetime import date
from dotenv import load_dotenv
import requests
from groq import Groq
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

# ─── API Keys & Config ────────────────────────────────────────────────────────
HUNTER_KEY  = os.getenv("HUNTER_API_KEY")
SERPER_KEY  = os.getenv("SERPER_API_KEY")
GROQ_KEY    = os.getenv("GROQ_API_KEY")
SHEET_ID    = os.getenv("GOOGLE_SHEET_ID")
CREDS_FILE  = os.getenv("GOOGLE_CREDS_FILE", "service_account.json")

client = Groq(api_key=GROQ_KEY)

# Known domains for Caribbean/DR banks (Hunter searches by domain, not company name)
KNOWN_DOMAINS = {
    "republic bank":            "republictt.com",
    "republic financial":       "republictt.com",
    "cibc caribbean":           "cibcfcib.com",
    "cibc firstcaribbean":      "cibcfcib.com",
    "firstcaribbean":           "cibcfcib.com",
    "ncb financial":            "jncb.com",
    "ncb jamaica":              "jncb.com",
    "sagicor":                  "sagicor.com",
    "scotiabank":               "scotiabank.com",
    "jmmb":                     "jmmb.com",
    "cayman national":          "caymanational.com",
    "banco popular":            "bpd.com.do",
    "banreservas":              "banreservas.com",
    "scotiabank trinidad":      "tt.scotiabank.com",
    "first citizens":           "firstcitizenstt.com",
    "rbtt":                     "republictt.com",
}

# ─── Target Titles ────────────────────────────────────────────────────────────
TARGET_TITLES = [
    "CEO", "President", "Chief Executive Officer", "Managing Director",
    "CTO", "Chief Technology Officer", "Chief Information Officer",
    "Chief Digital Officer", "Chief Information Digital Officer",
    "CRO", "Chief Risk Officer", "Chief Compliance Officer",
    "COO", "Chief Operating Officer",
    "CISO", "Chief Information Security Officer",
    "VP Digital Banking", "Head of Digital", "Director Digital Banking",
    "VP Technology", "Head of Technology", "Head of IT",
    "VP Operations", "Head of Operations",
]

# ─── Persona Classification ───────────────────────────────────────────────────
PERSONA_MAP = {
    "CEO / Strategic":    ["ceo", "president", "chief executive", "managing director", "group chief"],
    "CTO / Technical":    ["cto", "cio", "chief technology", "chief information officer", "chief digital",
                           "chief information digital", "head of technology", "director of technology"],
    "CRO / Compliance":   ["cro", "chief risk", "chief compliance", "compliance officer", "risk officer"],
    "COO / Operations":   ["coo", "chief operating", "vp operations", "head of operations"],
    "VP/Director Digital":["vp digital", "head of digital", "director digital", "digital banking", "digital transformation"],
    "VP/Director IT Ops": ["vp technology", "head of technology", "head of it", "director it",
                           "it operations", "vp it", "vp information technology"],
    "CISO / Security":    ["ciso", "information security", "cybersecurity", "head of security", "security officer"],
}

TRACK_MAP = {
    "CEO / Strategic":    "C-Suite Email First",
    "CTO / Technical":    "C-Suite Email First",
    "CRO / Compliance":   "C-Suite Email First",
    "COO / Operations":   "Director LinkedIn First",
    "VP/Director Digital":"Director LinkedIn First",
    "VP/Director IT Ops": "Director LinkedIn First",
    "CISO / Security":    "Director LinkedIn First",
}

PERSONA_ANGLES = {
    "CEO / Strategic":
        "Board-level technology liability. Revenue protection. Correspondent bank de-risking. 38-52% TCO reduction. "
        "Legacy is now a credit rating and M&A risk — not just an IT problem.",
    "CTO / Technical":
        "No failed rewrites. Knowledge Graph maps every COBOL/RPG/T24 dependency first. "
        "Strangler Fig + parallel run = proven 99.97% parity before cutover. Zero big-bang risk.",
    "CRO / Compliance":
        "CFATF 4th Round / Ley 155-17 personal liability. Native immutable audit trail. "
        "Clean AML data lineage. No reconciliation workarounds. Correspondent bank scrutiny ends.",
    "COO / Operations":
        "Eliminate manual reconciliation and middleware costs. 38-52% TCO. "
        "Module-by-module means no operational disruption — pilot one module, prove it, expand.",
    "VP/Director Digital":
        "The legacy back-end is throttling your digital velocity. "
        "Replace it module-by-module — no big-bang risk to the digital layer you've already built.",
    "VP/Director IT Ops":
        "Decommission AS/400 RPG / COBOL / Java EE without downtime. "
        "Knowledge Graph maps everything first. Strangler Fig. Parallel run.",
    "CISO / Security":
        "Replace legacy auth modules natively. Immutable audit trail. "
        "Zero data egress — runs inside your firewall. CBTT/CIMA/CFATF cybersecurity compliance built in.",
}

REGULATORY_CONTEXT = {
    "caribbean":    "CFATF 4th Round review, CBTT cybersecurity guidelines, ECCB supervision, correspondent banking de-risking",
    "trinidad":     "CFATF review, CBTT cybersecurity guidelines, Trinidad Stock Exchange disclosure, correspondent banking",
    "jamaica":      "FATF monitoring, Bank of Jamaica fintech guidelines, correspondent banking de-risking",
    "cayman":       "CIMA 2024 digital asset/AML framework, US FATCA, CFATF, correspondent bank AML scrutiny",
    "barbados":     "Central Bank of Barbados, CFATF, correspondent banking, BICA digital banking",
    "oecs":         "ECCB supervision, CFATF member state obligations, DCash digital infrastructure",
    "dominican":    "Ley 155-17 (AML — CRO personal liability), Junta Monetaria, SB guidelines, FATF grey list risk",
    "dr":           "Ley 155-17 (AML — CRO personal liability), Junta Monetaria, SB guidelines, FATF grey list risk",
}

PRODUCT_BRIEF = """
Infini.OS by InfiniAI.tech — AI-powered legacy banking platform modernization.
• Decodes: COBOL, Java EE, Natural/ADABAS, AS/400 RPG, Oracle stored procedures, T24, Temenos, 30+ legacy systems
• Process: Knowledge Construction (full dependency map) → Strangler Fig (module-by-module replacement) → Parallel Run (99.97% parity proven) → Cutover
• Timeline: 12–16 weeks per module
• TCO reduction: 38–52%
• Zero data egress: runs inside client firewall — data never leaves
• Compliance-first: immutable native audit trail, CFATF/SB/OSFI/correspondent bank ready
• No big-bang rewrite. Parallel run proves parity before any cutover.
"""

# ─── Hunter.io People Search ──────────────────────────────────────────────────
SENIORITY_KEYWORDS = ["ceo", "cto", "cio", "coo", "cro", "ciso", "chief", "president",
                      "managing director", "head of", "vp ", "vice president", "director"]

def find_domain(company_name: str) -> str:
    """Resolve company name to domain. Uses known list first, falls back to Serper."""
    name_lower = company_name.lower().strip()
    for key, domain in KNOWN_DOMAINS.items():
        if key in name_lower or name_lower in key:
            return domain
    # Fallback: search Google for the company website
    try:
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
        r = requests.post(url, headers=headers,
                          json={"q": f"{company_name} bank official website", "num": 3}, timeout=10)
        results = r.json().get("organic", [])
        for result in results:
            link = result.get("link", "")
            # Extract root domain
            import re as _re
            match = _re.search(r'https?://(?:www\.)?([^/]+)', link)
            if match:
                domain = match.group(1)
                # Skip generic sites
                if not any(x in domain for x in ["wikipedia", "linkedin", "bloomberg", "facebook"]):
                    return domain
    except Exception:
        pass
    return ""

def hunter_search(company_name: str) -> list:
    """Find people at a company using Hunter.io domain search."""
    domain = find_domain(company_name)
    if not domain:
        print(f"  ⚠ Could not resolve domain for '{company_name}'")
        return []

    print(f"    🌐 Domain: {domain}")
    url = "https://api.hunter.io/v2/domain-search"
    params = {
        "domain":   domain,
        "api_key":  HUNTER_KEY,
        "limit":    10,
        "type":     "personal",
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        emails = r.json().get("data", {}).get("emails", [])

        # Filter to senior titles
        filtered = [e for e in emails
                    if any(k in (e.get("position") or "").lower() for k in SENIORITY_KEYWORDS)]
        results = filtered or emails[:5]

        return [{
            "name":         f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
            "first_name":   e.get("first_name", ""),
            "title":        e.get("position", ""),
            "email":        e.get("value", ""),
            "linkedin_url": e.get("linkedin", ""),
            "company":      company_name,
            "domain":       domain,
        } for e in results if e.get("first_name")]

    except requests.exceptions.HTTPError as e:
        if r.status_code == 401:
            print("  ✗ Hunter: Invalid API key — check HUNTER_API_KEY in .env")
        elif r.status_code == 429:
            print("  ✗ Hunter: Rate limit hit")
        else:
            print(f"  ✗ Hunter HTTP {r.status_code}: {r.text[:200]}")
        return []
    except Exception as e:
        print(f"  ✗ Hunter error: {e}")
        return []

# ─── Serper News Search ───────────────────────────────────────────────────────
def serper_news(query: str) -> str:
    url = "https://google.serper.dev/news"
    headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json={"q": query, "num": 3, "tbs": "qdr:y"}, timeout=15)
        r.raise_for_status()
        items = r.json().get("news", [])
        return " | ".join(f"{n.get('title','')}: {n.get('snippet','')}" for n in items[:2] if n.get("title"))
    except Exception:
        return ""

# ─── Persona Classification ───────────────────────────────────────────────────
def classify_persona(title: str) -> str:
    t = title.lower()
    for persona, keywords in PERSONA_MAP.items():
        if any(k in t for k in keywords):
            return persona
    return "CEO / Strategic"

# ─── Groq: Generate Personalized Email ───────────────────────────────────────
def generate_email(contact: dict, persona: str, news_signal: str, region: str) -> dict:
    region_lower = region.lower()
    reg_context = next(
        (v for k, v in REGULATORY_CONTEXT.items() if k in region_lower),
        "Caribbean banking regulatory compliance, CFATF obligations, correspondent banking requirements"
    )
    angle = PERSONA_ANGLES.get(persona, PERSONA_ANGLES["CEO / Strategic"])
    news_section = (
        f"NEWS/SIGNAL:\n{news_signal}" if news_signal
        else f"No news found. Use regional context: {reg_context}"
    )

    prompt = f"""You write cold outreach emails for InfiniAI.tech selling Infini.OS to banking executives.

PRODUCT:
{PRODUCT_BRIEF}

TARGET:
Name: {contact['name']}
First name: {contact.get('first_name', contact['name'].split()[0])}
Title: {contact['title']}
Company: {contact['company']}
Region: {region}
Regulatory context: {reg_context}

PERSONA: {persona}
KEY ANGLE: {angle}

{news_section}

TASK: Write a cold T1 email. Rules:
- Subject: specific, under 10 words
- Body: under 140 words TOTAL
- Opening: reference news signal or specific observation — NOT "I hope this finds you well"
- Value prop: 2–3 sentences, specific numbers (12–16 weeks, 38–52% TCO)
- CTA: ask for 20 min call
- Sign-off: Varun Gani | InfiniAI.tech | varun.gani@infiniai.tech
- No buzzwords. Direct.

Return ONLY valid JSON, no markdown:
{{"subject": "...", "body": "..."}}"""

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.choices[0].message.content.strip()
        match = re.search(r'\{[^{}]*"subject"[^{}]*"body"[^{}]*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(text)
    except json.JSONDecodeError:
        sm = re.search(r'"subject":\s*"([^"]+)"', text)
        bm = re.search(r'"body":\s*"(.*?)"(?:\s*\})', text, re.DOTALL)
        return {
            "subject": sm.group(1) if sm else f"Legacy modernization for {contact['company']}",
            "body":    bm.group(1).replace("\\n", "\n") if bm else text[:500]
        }
    except Exception as e:
        print(f"  ✗ Groq error: {e}")
        return {"subject": f"Infini.OS for {contact['company']}", "body": ""}

# ─── Google Sheets ────────────────────────────────────────────────────────────
SHEET_HEADERS = [
    "Company", "Name", "First Name", "Title", "Persona", "Track",
    "Email", "LinkedIn URL", "Domain", "News Signal",
    "T1 Subject", "T1 Body", "T1 Status", "T1 Sent Date",
    "T2 Status", "T2 Sent Date", "T3 Status", "T3 Sent Date",
    "T4 Status", "T4 Sent Date", "Reply?", "Reply Date", "Notes",
]

def get_worksheet(sheet_name="Contacts"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scope)
    sh    = gspread.authorize(creds).open_by_key(SHEET_ID)
    try:
        return sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(title=sheet_name, rows=1000, cols=25)

def setup_headers(ws):
    ws.clear()
    ws.append_row(SHEET_HEADERS, value_input_option="RAW")
    ws.format("A1:W1", {
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "backgroundColor": {"red": 0.1, "green": 0.13, "blue": 0.25},
    })

def append_contact(ws, contact, persona, news, email_data):
    ws.append_row([
        contact["company"], contact["name"], contact.get("first_name",""),
        contact["title"], persona, TRACK_MAP.get(persona, "C-Suite Email First"),
        contact.get("email",""), contact.get("linkedin_url",""), contact.get("domain",""),
        news[:300] if news else "",
        email_data.get("subject",""), email_data.get("body",""),
        "Ready", "",  # T1
        "", "", "", "", "", "",  # T2-T4
        "No", "", "",  # Reply, Notes
    ], value_input_option="RAW")

# ─── Main ─────────────────────────────────────────────────────────────────────
def run_pipeline(companies, region, skip_existing=False):
    print(f"\n{'='*60}")
    print(f"  InfiniAI Enrichment Pipeline")
    print(f"  Companies : {', '.join(companies)}")
    print(f"  Region    : {region}  |  Date: {date.today()}")
    print(f"{'='*60}\n")

    missing = [k for k, v in {
        "HUNTER_API_KEY": HUNTER_KEY, "SERPER_API_KEY": SERPER_KEY,
        "GROQ_API_KEY": GROQ_KEY, "GOOGLE_SHEET_ID": SHEET_ID,
    }.items() if not v]
    if missing:
        print(f"✗ Missing .env keys: {', '.join(missing)}")
        sys.exit(1)

    print("📊 Connecting to Google Sheets...")
    ws = get_worksheet()
    existing = ws.get_all_values()
    if not existing or existing[0] != SHEET_HEADERS:
        setup_headers(ws)
        print("   → Headers created")
    print("   ✓ Connected\n")

    total = 0
    for company in companies:
        company = company.strip()
        if not company:
            continue
        print(f"🔍  {company}")
        people = hunter_search(company)
        if not people:
            print(f"    ⚠ No contacts found\n")
            continue
        print(f"    ✓ {len(people)} contacts")

        for p in people:
            if not p["name"]:
                continue
            print(f"\n    → {p['name']} | {p['title']}")
            news = serper_news(f'"{p["name"]}" OR "{company}" digital banking OR legacy OR compliance {date.today().year}')
            print(f"       📰 {'Signal found' if news else 'No news'}")
            persona = classify_persona(p["title"])
            email_data = generate_email(p, persona, news, region)
            print(f"       👤 {persona} | ✉ {email_data.get('subject','')}")
            append_contact(ws, p, persona, news, email_data)
            print(f"       📝 Written ✓")
            total += 1
            time.sleep(0.8)
        print()
        time.sleep(1.5)

    print(f"\n{'='*60}")
    print(f"  ✅ Done! {total} contacts enriched.")
    print(f"  Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    print(f"  Next: mark T1 Status → 'Approved' → python send.py")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--companies", help='Comma-separated company names')
    group.add_argument("--file",      help=".txt file with one company per line")
    parser.add_argument("--region",   default="Caribbean Banking")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()
    companies = open(args.file).read().splitlines() if args.file else [c.strip() for c in args.companies.split(",")]
    run_pipeline([c for c in companies if c], args.region, args.skip_existing)
