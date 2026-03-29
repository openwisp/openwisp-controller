import re
import subprocess
import sys
import time

import pypandoc
import questionary
import requests


class SkipSignal(Exception):
    """Signal that the user has chosen to skip an operation."""

    pass


def retryable_request(**kwargs):
    """Executes a requests call and provides a retry/skip/abort prompt on failure."""
    while True:
        try:
            response = requests.request(**kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            error_message = str(e)
            if e.response is not None:
                try:
                    data = e.response.json()
                    details = data.get("message")
                    if not details:
                        error_obj = data.get("error")
                        if isinstance(error_obj, dict):
                            details = error_obj.get("message")

                    if details:
                        error_message = f"{e}\n      └── Details: {details}"
                except requests.JSONDecodeError:
                    pass

            print(f"\n❌ Network error: {error_message}", file=sys.stderr)
            decision = questionary.select(
                "An error occurred. What would you like to do?",
                choices=["Retry", "Skip", "Abort"],
            ).ask()

            if decision == "Retry":
                time.sleep(1)
                continue
            elif decision == "Skip":
                raise SkipSignal("User chose to skip this operation.")
            else:  # Abort
                print("\n❌ Operation aborted by user.")
                sys.exit(1)


def adjust_markdown_headings(markdown_text):
    """Adjusts heading levels for the CHANGES.md file (## -> ###, etc.)."""
    markdown_text = re.sub(
        r"(?m)^### (Other changes|Dependencies|Backward-incompatible changes)",
        r"#### \1",
        markdown_text,
    )
    markdown_text = re.sub(
        r"(?m)^## (Features|Changes|Bugfixes)", r"### \1", markdown_text
    )
    return markdown_text


def demote_markdown_headings(markdown_text):
    """Reduces heading levels for the GitHub release body"""
    markdown_text = re.sub(r"(?m)^### ", "# ", markdown_text)
    markdown_text = re.sub(r"(?m)^#### ", "## ", markdown_text)
    return markdown_text


def get_current_branch():
    """Get the current Git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def rst_to_markdown(text):
    """Convert reStructuredText to Markdown using pypandoc."""
    escaped_text = re.sub(r"(?<!`)_", r"\\_", text)
    return pypandoc.convert_text(
        escaped_text, "gfm", format="rst", extra_args=["--wrap=none"]
    ).strip()


def _call_docstrfmt(file_path):
    return subprocess.run(
        [
            "docstrfmt",
            "--ignore-cache",
            "--section-adornments",
            "=-~+^\"'.:",
            "--line-length",
            "74",
            file_path,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def format_file_with_docstrfmt(file_path):
    """Format a file using `docstrfmt`."""
    while True:
        try:
            _call_docstrfmt(file_path)
            print(f"✅ Formatted {file_path} successfully.")
            break
        except subprocess.CalledProcessError as e:
            print(
                f"\n❌ ERROR: `docstrfmt` failed to format '{file_path}'.",
                file=sys.stderr,
            )
            print("Linter output:", file=sys.stderr)
            # Indent the error for readability
            indented_stderr = "\n".join(
                [f"    {line}" for line in e.stderr.strip().split("\n")]
            )
            print(indented_stderr, file=sys.stderr)

            print(
                f"\nThis is likely caused by a syntax error in '{file_path}'.\n"
                "Please open the file in another terminal, fix the issue, and save it."
            )
            decision = questionary.select(
                "How would you like to proceed?",
                choices=[
                    "I have fixed the file, try again.",
                    "Skip formatting and continue with the unformatted file.",
                    "Abort the release process.",
                ],
            ).ask()

            if decision == "I have fixed the file, try again.":
                continue
            elif decision == "Skip formatting and continue with the unformatted file.":
                print(f"⚠️  Skipped formatting for '{file_path}'.")
                break
            else:  # Abort or None
                print("\n❌ Release process aborted by user.")
                sys.exit(1)
