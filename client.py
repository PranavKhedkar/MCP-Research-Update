"""
MCP Client – Weekly Progress Report
====================================
Connects to the local MCP server (server.py), orchestrates the four tools,
and uses Claude to generate a concise bullet-point report that is then
emailed to the professor.

Workflow:
    Step 1 – Run export_and_commit.py to commit the updated Excel file.
    Step 2 – Run this script to generate and send the report.

Usage:
    python client.py \
        --repo-path   "d:/MCP_Auto_update" \
        --excel-file  "Online Retail.xlsx" \
        --notebook-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms" \
        --to          "professor@university.edu"
"""

import argparse
import asyncio
import json
import sys

import anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_result_text(result) -> str:
    """Extract plain text from an MCP tool result."""
    if hasattr(result, "content"):
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)
    return str(result)


async def call_tool(session: ClientSession, name: str, arguments: dict) -> str:
    """Call a named MCP tool and return its text output."""
    print(f"  → calling tool: {name}({list(arguments.keys())})")
    result = await session.call_tool(name, arguments=arguments)
    text = _tool_result_text(result)
    print(f"    ✓ received {len(text)} chars")
    return text


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def run(repo_path: str, excel_file: str, notebook_id: str, to_email: str, dry_run: bool = False):
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # ── 1. Initialise and list available tools ──────────────────────
            await session.initialize()
            tools_response = await session.list_tools()
            available = [t.name for t in tools_response.tools]
            print(f"\nServer tools available: {available}\n")

            # ── 2. Gather raw data ──────────────────────────────────────────
            print("Step 1/4 – fetching git diff …")
            git_diff = await call_tool(
                session, "get_git_diff",
                {"repo_path": repo_path, "file_name": excel_file},
            )

            print("\nStep 2/4 – fetching Colab notebook …")
            notebook_content = await call_tool(
                session, "get_colab_notebook",
                {"file_id": notebook_id},
            )

            print("\nStep 3/4 – summarising notebook …")
            notebook_summary = await call_tool(
                session, "summarize_notebook",
                {"notebook_content": notebook_content},
            )

            # ── 3. Ask Claude to write the weekly report ────────────────────
            print("\nStep 4/4 – generating report with Claude …")
            claude = anthropic.Anthropic()

            system_prompt = (
                "You are a research assistant writing a concise weekly progress report "
                "to be sent to a professor. Write in professional, first-person tone. "
                "Use clear bullet points organised under short section headings. "
                "Be specific about what changed, what was analysed, and what the next steps are. "
                "Keep the entire report under 400 words."
            )

            user_message = f"""
Here is the weekly activity data. Please produce a bullet-point progress report.

## Excel File Changes (git diff for {excel_file})
{git_diff}

## Colab Notebook Summary
{notebook_summary}
""".strip()

            response = claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            report_body = response.content[0].text
            print("\n" + "=" * 60)
            print("GENERATED REPORT")
            print("=" * 60)
            print(report_body)
            print("=" * 60 + "\n")

            # ── 4. Email the report ─────────────────────────────────────────
            if dry_run:
                print("DRY RUN – email not sent. Run without --dry-run to send.")
            else:
                print("Sending email …")
                email_result = await call_tool(
                    session, "send_email",
                    {
                        "to": to_email,
                        "subject": "Weekly Research Progress Report",
                        "body": report_body,
                    },
                )
                print(f"\n{email_result}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate and email a weekly research progress report."
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Absolute path to the local Git repository.",
    )
    parser.add_argument(
        "--excel-file",
        required=True,
        help="Name (or relative path) of the Excel file tracked in the repo.",
    )
    parser.add_argument(
        "--notebook-id",
        required=True,
        help="Google Drive file ID of the Colab notebook.",
    )
    parser.add_argument(
        "--to",
        required=True,
        dest="to_email",
        help="Recipient email address (your professor).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline but skip sending the email.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        run(
            repo_path=args.repo_path,
            excel_file=args.excel_file,
            notebook_id=args.notebook_id,
            to_email=args.to_email,
            dry_run=args.dry_run,
        )
    )
