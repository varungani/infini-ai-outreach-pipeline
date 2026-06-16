#!/usr/bin/env python3
"""
InfiniAI T1 Email Sender
============================================================
Reads Google Sheet, finds T1 Status = "Approved", sends via Gmail.

Usage:
  python send.py              # send to real contacts (Approved rows)
  python send.py --dry-run    # preview without sending
  python send.py --limit 5    # send max 5
  python send.py --test       # send to TEST_EMAILS instead of real contacts (safe demo mode)
"""

import os, sys, time, argparse, smtplib
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

SHEET_ID    = os.getenv("GOOGLE_SHEET_ID")
CREDS_FILE  = os.getenv("GOOGLE_CREDS_FILE", "service_account.json")
GMAIL_USER  = os.getenv("GMAIL_USER")
GMAIL_PASS  = os.getenv("GMAIL_APP_PASSWORD")
SENDER_NAME = os.getenv("SENDER_NAME", "Varun Gani | InfiniAI.tech")

# Test mode: send to these addresses instead of real contacts
TEST_EMAILS = [
    "varungani07@gmail.com",
    "varungani24@gmail.com",
    "02fe22bci056@gmail.com",
    "vimaygav@gmail.com",
]

COL = {
    "company": 0, "name": 1, "first_name": 2, "title": 3, "persona": 4, "track": 5,
    "email": 6, "linkedin_url": 7, "domain": 8, "news_signal": 9,
    "t1_subject": 10, "t1_body": 11, "t1_status": 12, "t1_sent_date": 13,
    "t2_status": 14, "t2_sent_date": 15, "t3_status": 16, "t3_sent_date": 17,
    "t4_status": 18, "t4_sent_date": 19, "reply": 20, "reply_date": 21, "notes": 22,
}

def get_cell(row, col_name, fallback=""):
    idx = COL[col_name]
    return row[idx].strip() if len(row) > idx else fallback

def get_worksheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet("Contacts")

def send_email(to_email, to_name, subject, body, dry_run=False):
    if dry_run:
        print(f"\n    [DRY RUN] → {to_name} <{to_email}>")
        print(f"    Subject : {subject}")
        print(f"    Preview : {body[:200]}...")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"{SENDER_NAME} <{GMAIL_USER}>"
        msg["To"]      = f"{to_name} <{to_email}>"
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
        print("  ✗ Gmail auth failed — check GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        print("    Get App Password: Google Account → Security → 2-Step Verification → App Passwords")
        return False
    except Exception as e:
        print(f"  ✗ Send error: {e}")
        return False

def run_sender(dry_run=False, limit=0, test_mode=False):
    mode_label = "DRY RUN" if dry_run else ("TEST MODE → your inboxes" if test_mode else "LIVE → real contacts")
    print(f"\n{'='*60}")
    print(f"  InfiniAI T1 Sender  |  {mode_label}  |  {date.today()}")
    if test_mode:
        print(f"  Test inboxes: {', '.join(TEST_EMAILS)}")
    print(f"{'='*60}\n")

    if not dry_run:
        missing = [k for k, v in {"GMAIL_USER": GMAIL_USER, "GMAIL_APP_PASSWORD": GMAIL_PASS}.items() if not v]
        if missing:
            print(f"✗ Missing in .env: {', '.join(missing)}")
            sys.exit(1)

    ws       = get_worksheet()
    all_rows = ws.get_all_values()
    if len(all_rows) < 2:
        print("  Sheet empty — run enrich.py first.")
        return

    approved = [
        (i + 2, row) for i, row in enumerate(all_rows[1:])
        if get_cell(row, "t1_status") in ("Approved", "Ready")  # test mode accepts Ready too
    ] if test_mode else [
        (i + 2, row) for i, row in enumerate(all_rows[1:])
        if get_cell(row, "t1_status") == "Approved"
    ]

    if not approved:
        print("  No eligible rows found.")
        if not test_mode:
            print("  → Change T1 Status from 'Ready' to 'Approved' for contacts to send to.")
        return

    print(f"  ✓ {len(approved)} contacts found")
    if limit:
        approved = approved[:limit]
        print(f"  ✓ Capped at {limit}")
    print()

    sent = failed = 0
    test_idx = 0  # cycle through test emails

    for row_num, row in approved:
        name    = get_cell(row, "name")
        company = get_cell(row, "company")
        email   = get_cell(row, "email")
        subject = get_cell(row, "t1_subject")
        body    = get_cell(row, "t1_body")
        persona = get_cell(row, "persona")

        if not subject or not body:
            print(f"  ⚠ {name} — empty subject/body, skipped")
            continue

        # In test mode: send to your own inboxes, cycling through them
        if test_mode:
            target_email = TEST_EMAILS[test_idx % len(TEST_EMAILS)]
            target_name  = f"[TEST for {name}]"
            test_subject = f"[TEST] {subject}"
            test_body    = f"--- TEST EMAIL (real target: {name}, {company}) ---\n\n{body}"
            test_idx += 1
        else:
            if not email:
                ws.update_cell(row_num, COL["t1_status"] + 1, "No Email")
                print(f"  ⚠ {name} — no email, skipped")
                continue
            target_email = email
            target_name  = name
            test_subject = subject
            test_body    = body

        print(f"  → {name} | {company} | {persona}")
        print(f"     Sending to: {target_email}")

        ok = send_email(target_email, target_name, test_subject, test_body, dry_run)
        if ok:
            if not dry_run and not test_mode:
                ws.update_cell(row_num, COL["t1_status"]    + 1, "Sent")
                ws.update_cell(row_num, COL["t1_sent_date"] + 1, str(date.today()))
            elif not dry_run and test_mode:
                ws.update_cell(row_num, COL["t1_status"] + 1, "Test Sent")
            print(f"     {'✓ Would send' if dry_run else '✓ Sent'}")
            sent += 1
        else:
            failed += 1
        time.sleep(2)

    print(f"\n{'='*60}")
    print(f"  Done!  Sent: {sent}  Failed: {failed}")
    if test_mode and sent:
        print(f"  Check your inboxes: {', '.join(TEST_EMAILS)}")
        print(f"  When ready to go live: python send.py (after marking rows 'Approved')")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--limit",   type=int, default=0,  help="Max emails to send")
    parser.add_argument("--test",    action="store_true",  help="Send to test inboxes instead of real contacts")
    args = parser.parse_args()
    run_sender(args.dry_run, args.limit, args.test)
