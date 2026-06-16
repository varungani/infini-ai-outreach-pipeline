#!/usr/bin/env python3
"""
InfiniAI Follow-up Engine
============================================================
Run daily via GitHub Actions (Mon–Fri 9am UTC).
  T2 (day 8)  → LinkedIn note in sheet (manual send)
  T3 (day 14) → Auto email via Gmail
  T4 (day 21) → Final auto email via Gmail
  T5 (day 28) → Mark sequence closed

Usage:
  python followup.py             # live
  python followup.py --dry-run   # preview
"""

import os, sys, json, time, re, smtplib, argparse
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from groq import Groq
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

SHEET_ID    = os.getenv("GOOGLE_SHEET_ID")
CREDS_FILE  = os.getenv("GOOGLE_CREDS_FILE", "service_account.json")
GMAIL_USER  = os.getenv("GMAIL_USER")
GMAIL_PASS  = os.getenv("GMAIL_APP_PASSWORD")
GROQ_KEY    = os.getenv("GROQ_API_KEY")
SENDER_NAME = os.getenv("SENDER_NAME", "Varun Gani | InfiniAI.tech")

client = Groq(api_key=GROQ_KEY)

SCHEDULE = {"T2": 8, "T3": 6, "T4": 7}

COL = {
    "company": 0, "name": 1, "first_name": 2, "title": 3, "persona": 4, "track": 5,
    "email": 6, "linkedin_url": 7, "domain": 8, "news_signal": 9,
    "t1_subject": 10, "t1_body": 11, "t1_status": 12, "t1_sent_date": 13,
    "t2_status": 14, "t2_sent_date": 15, "t3_status": 16, "t3_sent_date": 17,
    "t4_status": 18, "t4_sent_date": 19, "reply": 20, "reply_date": 21, "notes": 22,
}

def get_cell(row, col, fallback=""):
    idx = COL[col]
    return row[idx].strip() if len(row) > idx else fallback

def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None

def days_since(d):
    return (date.today() - d).days

def get_worksheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet("Contacts")

def send_email(to_email, to_name, subject, body, dry_run=False):
    if dry_run:
        print(f"      [DRY RUN] → {to_name} <{to_email}> | {subject}")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{SENDER_NAME} <{GMAIL_USER}>"
        msg["To"]   = f"{to_name} <{to_email}>"
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        html = body.replace("\n\n", "</p><p>").replace("\n", "<br>")
        msg.attach(MIMEText(
            f'<html><body style="font-family:Georgia,serif;font-size:15px;color:#1a1a1a;max-width:580px;line-height:1.6"><p>{html}</p></body></html>',
            "html"
        ))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.sendmail(GMAIL_USER, to_email, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        print("  ✗ Gmail auth failed")
        return False
    except Exception as e:
        print(f"  ✗ Email error: {e}")
        return False

def groq_call(prompt, max_tokens=400):
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return r.choices[0].message.content.strip()

def parse_json(text):
    match = re.search(r'\{[^{}]*"subject"[^{}]*"body"[^{}]*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)

def gen_t2_linkedin(contact, t1_subject):
    first = contact["first_name"] or contact["name"].split()[0]
    try:
        return groq_call(
            f"""Write a LinkedIn connection request note (under 280 chars) for {first}, {contact['title']} at {contact['company']}.
Context: emailed about Infini.OS legacy bank modernization. Subject: "{t1_subject}"
Reference email briefly. Be friendly. Return ONLY the note text.""",
            max_tokens=100
        )[:280]
    except Exception:
        return f"Hi {first}, I emailed about modernizing {contact['company']}'s legacy platform with Infini.OS — 12 weeks, no big-bang rewrite. Would love to connect. — Varun, InfiniAI.tech"

def gen_t3_email(contact, t1_subject, news, persona):
    first = contact["first_name"] or contact["name"].split()[0]
    proof = {
        "CEO / Strategic":    "A Caribbean bank decommissioned their COBOL core in 12 weeks. 44% TCO reduction. Board presented it as regulatory risk removed.",
        "CTO / Technical":    "One CTO said the Knowledge Graph found 3,000 undocumented COBOL dependencies no one knew existed — that's why the Strangler Fig works.",
        "CRO / Compliance":   "Post-CFATF review, one Caribbean CRO replaced their legacy AML system with Infini.OS. Native audit trail. 12 weeks.",
        "COO / Operations":   "One operations team cut $2.1M/year in middleware costs. Module by module, no disruption.",
        "VP/Director Digital":"One digital head: 'Our legacy core was the ceiling on digital. We removed the ceiling.' 12 weeks, one module.",
        "VP/Director IT Ops": "A bank decommissioned their AS/400 RPG payroll module in 11 weeks. Parallel run to 99.97% parity. Zero incidents.",
        "CISO / Security":    "Post-modernization: zero legacy auth vulnerabilities. Data never left their firewall. CIMA audit passed.",
    }.get(persona, "A Caribbean bank reduced TCO by 44% in 12 weeks with zero service disruption.")

    try:
        return parse_json(groq_call(
            f"""Write a T3 follow-up email for {contact['name']}, {contact['title']}, {contact['company']}.
Prior subject: "{t1_subject}" | Persona: {persona}
{'Signal: ' + news[:100] if news else ''}
Proof: {proof}
Rules: under 100 words, reference prior email, include proof naturally, offer 2-page brief, sign: Varun Gani | InfiniAI.tech
Return ONLY JSON: {{"subject": "Re: {t1_subject}", "body": "..."}}"""
        ))
    except Exception:
        return {"subject": f"Re: {t1_subject}", "body": f"Hi {first},\n\nFollowing up. {proof}\n\nHappy to send a 2-page brief for {contact['company']}'s stack.\n\nVarun Gani | InfiniAI.tech"}

def gen_t4_email(contact, t1_subject):
    first = contact["first_name"] or contact["name"].split()[0]
    company = contact["company"]
    try:
        return parse_json(groq_call(
            f"""Write a final follow-up email (under 70 words) for {first} at {company}. Prior subject: "{t1_subject}"
Gracious, no pressure. Say timing might not be right. Leave door open: offer the 2-page brief if useful later.
Sign: Varun Gani | InfiniAI.tech
Return ONLY JSON: {{"subject": "Last note — Infini.OS for {company}", "body": "..."}}"""
        ))
    except Exception:
        return {
            "subject": f"Last note — Infini.OS for {company}",
            "body": f"Hi {first},\n\nTiming might not be right — no worries. If a brief on {company}'s modernization path would be useful later, just reply.\n\nBest,\nVarun Gani | InfiniAI.tech"
        }

def run_followups(dry_run=False):
    print(f"\n{'='*60}")
    print(f"  InfiniAI Follow-up Engine  |  {'DRY RUN' if dry_run else 'LIVE'}  |  {date.today()}")
    print(f"{'='*60}\n")

    ws       = get_worksheet()
    all_rows = ws.get_all_values()
    if len(all_rows) < 2:
        print("  No data — run enrich.py first.")
        return

    actions = {"t2": 0, "t3": 0, "t4": 0, "closed": 0, "skipped": 0}
    today   = date.today()

    for i, row in enumerate(all_rows[1:]):
        row_num = i + 2
        name    = get_cell(row, "name")
        if not name:
            continue
        if get_cell(row, "reply").lower() in ("yes", "y"):
            continue

        email       = get_cell(row, "email")
        first       = get_cell(row, "first_name") or (name.split()[0] if name else "")
        company     = get_cell(row, "company")
        persona     = get_cell(row, "persona")
        news        = get_cell(row, "news_signal")
        t1_subject  = get_cell(row, "t1_subject")
        t1_status   = get_cell(row, "t1_status")
        t1_date     = parse_date(get_cell(row, "t1_sent_date"))
        t2_status   = get_cell(row, "t2_status")
        t2_date     = parse_date(get_cell(row, "t2_sent_date"))
        t3_status   = get_cell(row, "t3_status")
        t3_date     = parse_date(get_cell(row, "t3_sent_date"))
        t4_status   = get_cell(row, "t4_status")
        t4_date     = parse_date(get_cell(row, "t4_sent_date"))

        contact = {"name": name, "first_name": first, "title": get_cell(row, "title"),
                   "company": company, "email": email, "linkedin_url": get_cell(row, "linkedin_url")}

        # T5: close sequence
        if t4_status == "Sent" and t4_date and days_since(t4_date) >= 21:
            print(f"  ✓ {name} — closed")
            if not dry_run:
                ws.update_cell(row_num, COL["notes"] + 1, f"Sequence closed {today}")
            actions["closed"] += 1
            continue

        # T4: final email
        if t3_status == "Sent" and t3_date and days_since(t3_date) >= SCHEDULE["T4"] and not t4_status:
            print(f"  → T4: {name} ({company})")
            if not email:
                actions["skipped"] += 1
                continue
            d = gen_t4_email(contact, t1_subject)
            if send_email(email, name, d["subject"], d["body"], dry_run) and not dry_run:
                ws.update_cell(row_num, COL["t4_status"]    + 1, "Sent")
                ws.update_cell(row_num, COL["t4_sent_date"] + 1, str(today))
            actions["t4"] += 1
            time.sleep(2)
            continue

        # T3: proof email
        if "Done" in t2_status and t2_date and days_since(t2_date) >= SCHEDULE["T3"] and not t3_status:
            print(f"  → T3: {name} ({company})")
            if not email:
                actions["skipped"] += 1
                continue
            d = gen_t3_email(contact, t1_subject, news, persona)
            if send_email(email, name, d["subject"], d["body"], dry_run) and not dry_run:
                ws.update_cell(row_num, COL["t3_status"]    + 1, "Sent")
                ws.update_cell(row_num, COL["t3_sent_date"] + 1, str(today))
            actions["t3"] += 1
            time.sleep(2)
            continue

        # T2: LinkedIn flag
        if t1_status == "Sent" and t1_date and days_since(t1_date) >= SCHEDULE["T2"] and not t2_status:
            print(f"  → T2 LinkedIn due: {name} ({company})")
            note = gen_t2_linkedin(contact, t1_subject)
            if not dry_run:
                ws.update_cell(row_num, COL["t2_status"]    + 1, "LinkedIn Due")
                ws.update_cell(row_num, COL["t2_sent_date"] + 1, str(today))
                ws.update_cell(row_num, COL["notes"]        + 1, f"T2 note: {note}")
            print(f"     Note: {note[:100]}...")
            if get_cell(row, "linkedin_url"):
                print(f"     URL : {get_cell(row, 'linkedin_url')}")
            actions["t2"] += 1
            time.sleep(1)

    print(f"\n{'='*60}")
    print(f"  T2 LinkedIn flagged: {actions['t2']}  |  T3 sent: {actions['t3']}  |  T4 sent: {actions['t4']}  |  Closed: {actions['closed']}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run_followups(args.dry_run)
