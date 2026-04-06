# MCP Research Update

An automated weekly research progress report system built with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It gathers data from a Git-tracked Excel file and a Google Colab notebook, uses Claude to generate a concise report, and emails it to your professor.

## How It Works

```
Git Diff (Excel) ─┐
                  ├─► Claude ─► Weekly Report ─► Email
Colab Notebook ───┘
```

1. **`get_git_diff`** — Compares the Excel file between the last two commits and returns a human-readable row/column diff.
2. **`get_colab_notebook`** — Fetches a `.ipynb` notebook from Google Drive via the Drive API.
3. **`summarize_notebook`** — Parses the notebook and extracts code cells, markdown notes, and visualisation calls.
4. **`send_email`** — Sends the generated report via Gmail SMTP.

## Project Structure

```
MCP_Auto_update/
├── server.py                      # MCP server with 4 tools
├── client.py                      # Orchestrator: calls tools + Claude + sends email
├── requirements.txt               # Python dependencies
├── .env                           # Secrets (not committed)
├── service_account_credentials.json  # Google service account key (not committed)
└── Online Retail.xlsx             # Excel dataset tracked in git
```

## Prerequisites

- Python 3.10+
- A Google Cloud service account with Drive API enabled
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification)
- An [Anthropic API key](https://console.anthropic.com/)

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Create a `.env` file**

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
EMAIL_ADDRESS=your_gmail@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
GOOGLE_SERVICE_ACCOUNT_JSON=service_account_credentials.json
```

**3. Add your Google service account credentials**

Place your service account JSON key file in the project root. Set the path in `.env` as `GOOGLE_SERVICE_ACCOUNT_JSON`. Share your Colab notebook with the service account email so it can be fetched.

## Usage

**Step 1** — Commit your updated Excel file to git:

```bash
git add "Online Retail.xlsx"
git commit -m "Weekly update: added new data"
```

**Step 2** — Run the client to generate and send the report:

```bash
python client.py \
  --repo-path   "d:/MCP_Auto_update" \
  --excel-file  "Online Retail.xlsx" \
  --notebook-id "YOUR_GOOGLE_DRIVE_FILE_ID" \
  --to          "professor@university.edu"
```

To preview the report without sending an email:

```bash
python client.py \
  --repo-path   "d:/MCP_Auto_update" \
  --excel-file  "Online Retail.xlsx" \
  --notebook-id "YOUR_GOOGLE_DRIVE_FILE_ID" \
  --to          "professor@university.edu" \
  --dry-run
```

The Google Drive file ID is the string in the Colab sharing URL:  
`https://drive.google.com/file/d/`**`THIS_PART`**`/view`

## MCP Server Tools

| Tool | Description |
|------|-------------|
| `get_git_diff` | Extracts both Excel versions from git history and diffs them with pandas — no CSV needed |
| `get_colab_notebook` | Fetches a `.ipynb` from Google Drive using a service account |
| `summarize_notebook` | Parses notebook JSON and returns structured summary of code, notes, and plots |
| `send_email` | Sends plain-text email via Gmail SMTP (TLS, port 587) |

## Security Notes

- Never commit `.env` or `service_account_credentials.json` to version control.
- Use a Gmail App Password, not your account password.
- The service account only needs `drive.readonly` scope.
