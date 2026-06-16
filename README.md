# InfiniAI Outreach Pipeline

Automated B2B outreach for Infini.OS — AI-powered legacy banking modernization.

**What it does:** Give it a list of bank names → it finds executives → researches news signals → writes personalized emails → populates a Google Sheet → sends emails → follows up automatically.

---

## Stack

| Tool | Purpose | Cost |
|---|---|---|
| Hunter.io | Find people + emails by company domain | Free (25/month) |
| Serper.dev | Google news search for personalization signals | Free (100/month) |
| Groq (Llama 3.3 70B) | Persona classification + email generation | Free (14,400 req/day) |
| Google Sheets | Live output + outreach tracker | Free |
| Gmail | Send T1/T3/T4 emails | Free (500/day) |
| GitHub Actions | Daily follow-up cron job | Free |

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
copy .env.example .env
```
Open `.env` and fill in all keys (see API Keys section below).

### 3. Add `service_account.json`
Download your Google Cloud service account JSON key and place it in this folder as `service_account.json`.

### 4. Share your Google Sheet
- Create a blank Google Sheet
- Open `service_account.json`, copy the `client_email` value
- Share the sheet with that email as **Editor**
- Copy the Sheet ID from the URL into `.env`

---

## API Keys

| Key | Where to get it |
|---|---|
| `HUNTER_API_KEY` | hunter.io → Dashboard → API |
| `SERPER_API_KEY` | serper.dev → Dashboard |
| `GROQ_API_KEY` | console.groq.com → API Keys |
| `GOOGLE_SHEET_ID` | From your Google Sheet URL |
| `GOOGLE_CREDS_FILE` | `service_account.json` (default) |
| `GMAIL_USER` | Your Gmail/Workspace address |
| `GMAIL_APP_PASSWORD` | Google Account → Security → 2-Step Verification → App Passwords |

---

## Usage

### Step 1 — Enrich contacts
```bash
# Single run
python enrich.py --companies "Republic Bank, CIBC Caribbean" --region "Caribbean Banking"

# From a file (one company per line)
python enrich.py --file companies.txt --region "Dominican Republic Banking"
```

This will:
- Find executives at each company via Hunter.io
- Fetch news signals via Serper
- Generate personalized T1 emails via Groq (Llama 3.3 70B)
- Write every contact to Google Sheets live, row by row

### Step 2 — Review emails
Open your Google Sheet. Each row has:
- Contact name, title, company, email, LinkedIn
- News signal found
- AI-written T1 subject + body

Change `T1 Status` from `Ready` → `Approved` for contacts you want to send to.

### Step 3 — Send emails

```bash
# Test mode — sends to internal inboxes, safe for demo
python send.py --test --limit 4

# Preview without sending
python send.py --dry-run

# Live send to approved contacts
python send.py

# Live send, max 10 at a time
python send.py --limit 10
```

### Step 4 — Follow-ups (automated)
```bash
# Manual run
python followup.py

# Preview
python followup.py --dry-run
```

Runs automatically Mon–Fri 9am via GitHub Actions.

---

## Follow-up Sequence

| Touch | Day | Channel | Action |
|---|---|---|---|
| T1 | Day 0 | Email | Personalized cold email (sent by `send.py`) |
| T2 | Day 8 | LinkedIn | Connection note (flagged in sheet, manual send) |
| T3 | Day 14 | Email | Proof-point follow-up (auto-sent by `followup.py`) |
| T4 | Day 21 | Email | Final gracious email (auto-sent by `followup.py`) |
| T5 | Day 28 | — | Sequence marked closed |

If a contact replies at any point, mark `Reply? = Yes` in the sheet — they'll be skipped by all future follow-ups.

---

## Google Sheet Columns

| Column | Description |
|---|---|
| Company | Bank name |
| Name / Title | Contact details |
| Persona | Auto-classified (CEO/Strategic, CTO/Technical, etc.) |
| Track | C-Suite Email First or Director LinkedIn First |
| Email / LinkedIn URL | Contact info from Hunter |
| News Signal | Recent news used for personalization |
| T1 Subject / T1 Body | AI-generated email |
| T1–T4 Status + Date | Outreach tracking |
| Reply? | Mark "Yes" when contact replies |
| Notes | Auto-populated with LinkedIn notes for T2 |

---

## GitHub Actions (Automated Follow-ups)

Secrets to add in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq key |
| `GOOGLE_SHEET_ID` | Your sheet ID |
| `GOOGLE_CREDS_JSON` | Full contents of `service_account.json` |
| `GMAIL_USER` | Your email |
| `GMAIL_APP_PASSWORD` | Your 16-char app password |
| `SENDER_NAME` | `Varun Gani | InfiniAI.tech` |

After adding secrets, go to **Actions tab → Daily Follow-up Runner → Run workflow** to test manually.

---

## Personas & Outreach Tracks

| Persona | Track | Key Angle |
|---|---|---|
| CEO / Strategic | C-Suite Email First | Board-level liability, 38-52% TCO, correspondent banking |
| CTO / Technical | C-Suite Email First | No failed rewrites, Knowledge Graph, 99.97% parity |
| CRO / Compliance | C-Suite Email First | CFATF/Ley 155-17 personal liability, native audit trail |
| COO / Operations | Director LinkedIn First | 38-52% TCO, eliminate reconciliation, module-by-module |
| VP/Director Digital | Director LinkedIn First | Remove legacy constraint on digital velocity |
| VP/Director IT Ops | Director LinkedIn First | Decommission AS/400 RPG/COBOL without downtime |
| CISO / Security | Director LinkedIn First | Zero data egress, immutable audit trail, compliance-ready |

---

## Files

```
InfiniAI_Outreach/
├── enrich.py              # Main pipeline: companies → people → emails → sheet
├── send.py                # T1 email sender (Approved rows → Gmail)
├── followup.py            # Daily follow-up runner (T2 flag, T3/T4 auto-send)
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── .gitignore             # Excludes .env and service_account.json
└── .github/
    └── workflows/
        └── followup.yml   # GitHub Actions cron job
```

---

## About Infini.OS

Infini.OS by InfiniAI.tech decodes and modernizes legacy banking platforms (COBOL, Java EE, Natural/ADABAS, AS/400 RPG, Oracle, T24, 30+ systems) using AI.

- **Timeline:** 12–16 weeks per module
- **TCO reduction:** 38–52%
- **Zero data egress** — runs inside client firewall
- **Process:** Knowledge Construction → Strangler Fig → Parallel Run (99.97% parity) → Cutover
- **No big-bang rewrite.** Proof before cutover.

Contact: varun.gani@infiniai.tech | infiniai.tech
