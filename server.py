import os
import json
import smtplib
import textwrap
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import git
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("weekly-report-server")

# ---------------------------------------------------------------------------
# Tool 1 – Git diff for a specific file
# ---------------------------------------------------------------------------

@mcp.tool()
def get_git_diff(repo_path: str, file_name: str) -> str:
    """
    Returns a human-readable summary of the diff between the last two commits
    for a specific file in a local Git repository.

    Args:
        repo_path: Absolute path to the root of the Git repository.
        file_name: Name (or relative path) of the file to diff.

    Returns:
        A string containing the raw unified diff, or an error message.
    """
    try:
        repo = git.Repo(repo_path)
        commits = list(repo.iter_commits(paths=file_name, max_count=2))

        if len(commits) < 2:
            if len(commits) == 1:
                return (
                    f"Only one commit found for '{file_name}'. "
                    "No previous version to compare against.\n"
                    f"Latest commit: {commits[0].hexsha[:8]} – {commits[0].message.strip()}"
                )
            return f"No commits found for file '{file_name}' in repo '{repo_path}'."

        newer, older = commits[0], commits[1]
        diffs = older.diff(newer, paths=file_name, create_patch=True)

        if not diffs:
            return (
                f"No changes detected in '{file_name}' between "
                f"{older.hexsha[:8]} and {newer.hexsha[:8]}."
            )

        lines = [
            f"File: {file_name}",
            f"Comparing: {older.hexsha[:8]} ({older.message.strip()[:60]})",
            f"       vs: {newer.hexsha[:8]} ({newer.message.strip()[:60]})",
            "-" * 60,
        ]
        for diff in diffs:
            patch = diff.diff.decode("utf-8", errors="replace")
            lines.append(patch)

        return "\n".join(lines)

    except git.InvalidGitRepositoryError:
        return f"Error: '{repo_path}' is not a valid Git repository."
    except Exception as exc:
        return f"Error retrieving git diff: {exc}"


# ---------------------------------------------------------------------------
# Tool 2 – Fetch a Colab notebook from Google Drive
# ---------------------------------------------------------------------------

def _drive_service():
    """Build a Google Drive service using a service-account credentials file."""
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json")
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return build("drive", "v3", credentials=creds)


@mcp.tool()
def get_colab_notebook(file_id: str) -> str:
    """
    Fetches a Colab notebook (.ipynb) from Google Drive by its file ID.

    Args:
        file_id: The Google Drive file ID of the Colab notebook
                 (visible in the sharing URL).

    Returns:
        The notebook JSON as a string, or an error message.
    """
    try:
        service = _drive_service()
        request = service.files().get_media(fileId=file_id)
        content = request.execute()

        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        # Validate that it looks like a notebook
        json.loads(content)  # will raise if malformed
        return content

    except Exception as exc:
        return f"Error fetching notebook from Google Drive: {exc}"


# ---------------------------------------------------------------------------
# Tool 3 – Summarise a Colab notebook
# ---------------------------------------------------------------------------

@mcp.tool()
def summarize_notebook(notebook_content: str) -> str:
    """
    Parses a Colab/Jupyter notebook and extracts a structured summary of
    code cells, markdown notes, and visualisation calls.

    Args:
        notebook_content: Raw JSON string of the .ipynb notebook.

    Returns:
        A plain-text summary of what the notebook does.
    """
    try:
        nb = json.loads(notebook_content)
    except json.JSONDecodeError as exc:
        return f"Error: notebook content is not valid JSON – {exc}"

    cells = nb.get("cells", [])
    if not cells:
        return "The notebook contains no cells."

    code_cells: list[str] = []
    markdown_notes: list[str] = []
    viz_calls: list[str] = []

    viz_keywords = (
        "plt.", "sns.", "fig.", "ax.", ".plot(", ".bar(", ".hist(",
        ".scatter(", ".show(", "plotly", "altair", "bokeh",
    )

    for idx, cell in enumerate(cells, 1):
        cell_type = cell.get("cell_type", "")
        source_lines = cell.get("source", [])
        source = "".join(source_lines) if isinstance(source_lines, list) else source_lines

        if not source.strip():
            continue

        if cell_type == "markdown":
            # Keep first 200 chars of each markdown cell as a note
            note = source.strip().replace("\n", " ")
            markdown_notes.append(f"  [{idx}] {note[:200]}")

        elif cell_type == "code":
            # Truncate long cells for readability
            snippet = textwrap.shorten(source.strip(), width=300, placeholder=" …")
            code_cells.append(f"  [{idx}] {snippet}")

            # Detect visualisation calls
            for kw in viz_keywords:
                if kw in source:
                    viz_calls.append(f"  [{idx}] contains '{kw}' call")
                    break

    parts = []
    parts.append(f"=== Notebook Summary ({len(cells)} cells total) ===\n")

    if markdown_notes:
        parts.append(f"Markdown / notes ({len(markdown_notes)}):")
        parts.extend(markdown_notes)
        parts.append("")

    if code_cells:
        parts.append(f"Code cells ({len(code_cells)}):")
        parts.extend(code_cells)
        parts.append("")

    if viz_calls:
        parts.append(f"Visualisations detected ({len(viz_calls)}):")
        parts.extend(viz_calls)
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool 4 – Send an email via Gmail SMTP
# ---------------------------------------------------------------------------

@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """
    Sends a plain-text email using Gmail SMTP (TLS on port 587).
    Reads EMAIL_ADDRESS and EMAIL_PASSWORD from the .env file.

    Args:
        to:      Recipient email address.
        subject: Email subject line.
        body:    Plain-text body of the email.

    Returns:
        A success message or an error description.
    """
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    if not sender or not password:
        return (
            "Error: EMAIL_ADDRESS or EMAIL_PASSWORD not set in .env. "
            "Please configure these credentials and retry."
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, to, msg.as_string())
        return f"Email successfully sent to {to}."
    except smtplib.SMTPAuthenticationError:
        return (
            "Error: Gmail authentication failed. "
            "Ensure you are using an App Password (not your account password) "
            "and that 2-Step Verification is enabled."
        )
    except Exception as exc:
        return f"Error sending email: {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
