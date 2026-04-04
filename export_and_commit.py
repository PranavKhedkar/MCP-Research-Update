"""
export_and_commit.py – Stage and commit the weekly Excel file to git.
======================================================================
Run this manually after finishing your weekly work, before running client.py.

Usage:
    python export_and_commit.py \
        --repo-path  "d:/MCP_Auto_update" \
        --excel-file "Online Retail.xlsx" \
        --message    "Week 14: updated sales data"   # optional
"""

import argparse
import os
import sys

import git


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stage and commit the weekly Excel file to git."
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Absolute path to the root of the Git repository.",
    )
    parser.add_argument(
        "--excel-file",
        required=True,
        help="Name (or relative path) of the Excel file inside the repo.",
    )
    parser.add_argument(
        "--message", "-m",
        default=None,
        help="Git commit message. If omitted, you will be prompted interactively.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_path = args.repo_path
    excel_file_name = args.excel_file

    excel_path = os.path.join(repo_path, excel_file_name)
    if not os.path.isfile(excel_path):
        print(f"Error: Excel file not found: {excel_path}")
        sys.exit(1)

    try:
        repo = git.Repo(repo_path)
    except git.InvalidGitRepositoryError:
        print(f"Error: '{repo_path}' is not a valid Git repository.")
        sys.exit(1)

    repo.index.add([excel_file_name])
    print(f"Staged   : {excel_file_name}")

    commit_message = args.message.strip() if args.message else input("Enter commit message: ").strip()
    if not commit_message:
        print("Error: Commit message cannot be empty.")
        sys.exit(1)

    repo.index.commit(commit_message)
    print(f"Committed: \"{commit_message}\"")
    print("\nDone. You can now run client.py to generate and send the report.")


if __name__ == "__main__":
    main()
