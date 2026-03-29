import re

from commitizen.cz.base import BaseCommitizen, ValidationResult

_TITLE_ISSUE_EXTRACT_RE = re.compile(r" #(\d+)")
_BODY_ISSUE_RE = re.compile(
    r"(?:Close|Closes|Closed|Fix|Fixes|Fixed|Resolve|Resolves|Resolved|Related to)((?:\s+#\d+)+)",
    re.IGNORECASE,
)


class OpenWispCommitizen(BaseCommitizen):
    """Commitizen plugin for OpenWISP commit conventions."""

    # Single source for allowed prefixes
    ALLOWED_PREFIXES = [
        "feature",
        "change",
        "fix",
        "docs",
        "tests",
        "ci",
        "chores",
        "qa",
        "deps",
        "release",
        "bump",
    ]

    ERROR_TEMPLATE = (
        "Invalid commit message format\n\n"
        "Expected format:\n\n"
        "  [prefix] Capitalized title\n\n"
        "  <description>\n\n"
        "Or with issue reference (must be symmetric):\n\n"
        "  [prefix] Capitalized title #<issue>\n\n"
        "  <description>\n\n"
        "  Fixes #<issue>\n\n"
        "Examples:\n\n"
        "  [chores] Updated documentation\n\n"
        "  Added new installation instructions.\n\n"
        "Or with issue reference:\n\n"
        "  [feature] Added subnet import support #104\n\n"
        "  Added support for importing multiple subnets from a CSV file.\n\n"
        "  Closes #104\n\n"
    )

    def _validate_title(self, value: str) -> bool | str:
        value = value.strip()
        if not value:
            return "Commit title cannot be empty."
        if not value[0].isupper():
            return "Commit title must start with a capital letter."
        return True

    def questions(self):
        return [
            {
                "type": "list",
                "name": "change_type",
                "message": "Select the type of change you are committing",
                "choices": [
                    {"value": prefix, "name": f"[{prefix}]"}
                    for prefix in self.ALLOWED_PREFIXES
                ],
            },
            {
                "type": "input",
                "name": "title",
                "message": "Commit title (short, first letter capital, optional #issue)",
                "validate": self._validate_title,
            },
            {
                "type": "input",
                "name": "how",
                "message": ("Describe what you changed"),
                "validate": lambda v: (
                    True if v.strip() else "Commit body cannot be empty."
                ),
            },
        ]

    def message(self, answers):
        prefix_value = answers["change_type"]
        prefix = f"[{prefix_value}]"
        title = answers["title"].strip()
        body = answers["how"].strip()
        # Extract issue numbers from title and body
        title_issues = set(_TITLE_ISSUE_EXTRACT_RE.findall(title))
        body_issues = set()
        for match in _BODY_ISSUE_RE.findall(body):
            body_issues.update(_TITLE_ISSUE_EXTRACT_RE.findall(match))
        # If issues are in title but not in body, auto-append "Related to"
        missing_issues = title_issues - body_issues
        if missing_issues:
            body += "\n"
            for issue in sorted(missing_issues):
                body += f"\nRelated to #{issue}"
        return f"{prefix} {title}\n\n{body.strip()}"

    def _extract_title_issues(self, commit_msg: str) -> set[str]:
        """Extract issue numbers from the commit title."""
        lines = commit_msg.split("\n")
        if not lines:
            return set()
        title = lines[0]
        # Find all #<number> patterns at the end of the title
        return set(_TITLE_ISSUE_EXTRACT_RE.findall(title))

    def _extract_body_issues(self, commit_msg: str) -> set[str]:
        """Extract issue numbers from the commit body."""
        lines = commit_msg.split("\n")
        if len(lines) < 2:
            return set()
        # Body is everything after the first line
        body = "\n".join(lines[1:])
        # Find all matches and extract individual issue numbers
        issues = set()
        for match in _BODY_ISSUE_RE.findall(body):
            # Each match contains something like " #123 #124"
            # Extract all #\d+ patterns from it
            issues.update(_TITLE_ISSUE_EXTRACT_RE.findall(match))
        return issues

    def validate_commit_message(
        self,
        *,
        commit_msg: str,
        pattern: re.Pattern[str],
        allow_abort: bool,
        allowed_prefixes: list[str],
        max_msg_length: int | None,
        commit_hash: str,
    ) -> ValidationResult:
        """Validate commit message and return user-friendly errors."""
        if not commit_msg:
            return ValidationResult(
                allow_abort, [] if allow_abort else ["commit message is empty"]
            )
        # Check if it's a merge commit
        if commit_msg.startswith("Merge "):
            return ValidationResult(True, [])
        # Check prefix is allowed
        if not any(
            re.match(rf"\[{prefix}([!/:]|\])", commit_msg)
            for prefix in self.ALLOWED_PREFIXES
        ):
            return ValidationResult(False, [self.ERROR_TEMPLATE])
        # Check title starts with capital letter
        lines = commit_msg.split("\n")
        if lines:
            title = lines[0]
            # Remove prefix to get the actual title text
            title_match = re.match(r"\[[^\]]+\] (.+)", title)
            if title_match:
                title_text = title_match.group(1)
                if title_text and not title_text[0].isupper():
                    return ValidationResult(
                        False,
                        [
                            "Commit title must start with a capital letter after the prefix."
                        ],
                    )
        # Extract issues from title and body
        title_issues = self._extract_title_issues(commit_msg)
        body_issues = self._extract_body_issues(commit_msg)
        # Validate issue reference symmetry
        # Either both have issues (and they match) or neither has issues
        if title_issues != body_issues:
            if title_issues and not body_issues:
                return ValidationResult(
                    False,
                    [
                        "Issue referenced in title but not in body. "
                        "If you reference an issue in the title, "
                        "you must also reference it in the body using "
                        "Fixes/Closes/Related to #<issue>."
                    ],
                )
            elif body_issues and not title_issues:
                return ValidationResult(
                    False,
                    [
                        "Issue referenced in body but not in title. "
                        "If you reference an issue in the body, "
                        "you must also reference it in the title (e.g., '[prefix] Title #123')."
                    ],
                )
            else:
                # Both have issues but they don't match
                return ValidationResult(
                    False,
                    [
                        f"Issue mismatch between title ({title_issues}) "
                        f"and body ({body_issues}). "
                        "The issues referenced must match exactly."
                    ],
                )
        # Check message length limit
        if max_msg_length is not None and max_msg_length > 0:
            msg_len = len(commit_msg.partition("\n")[0].strip())
            if msg_len > max_msg_length:
                return ValidationResult(
                    False,
                    [
                        f"commit message length exceeds the limit ({max_msg_length} chars)",
                    ],
                )
        return ValidationResult(True, [])

    def format_error_message(self, message: str) -> str:
        return self.ERROR_TEMPLATE

    def example(self) -> str:
        return (
            "[feature] Add commit convention enforcement #110\n\n"
            "Introduce a Commitizen-based commit workflow to standardize\n"
            "commit messages across the OpenWISP project.\n\n"
            "Fixes #110"
        )

    def schema(self) -> str:
        return "[<type>] <Title> [#<issue>]"

    def schema_pattern(self) -> str:
        """Provides regex for basic checks, but skips symmetry enforcement.

        The actual symmetry enforcement of referenced issues (issues must
        be referenced both in title and body) happens in the
        validate_commit_message method
        """
        # Allow merge commits (starting with "Merge") or regular commits with prefix
        merge_pattern = r"Merge .*"
        # Regular commits with allowed prefix
        # Title: [prefix] Capitalized title, optional issue references at end
        # Body: optional, with optional footer containing issue references
        # Issue references must be symmetric (same in title and body)
        # Pattern for commits without issues
        no_issue_pattern = (
            r"\[[a-z0-9!/:-]+\] [A-Z][^\n]*"
            r"$(?!\n\n.*(?:Close|Closes|Closed|Fix|Fixes|Fixed"
            r"|Resolve|Resolves|Resolved|Related to) #\d+)"
        )
        # Pattern for commits with issues
        with_issue_pattern = (
            r"\[[a-z0-9!/:-]+\] [A-Z][^\n]*(?P<title_issues>(?: #\d+)+)$"
            r"\n\n.*"
            r"(?:Close|Closes|Closed|Fix|Fixes|Fixed"
            r"|Resolve|Resolves|Resolved|Related to)"
            r"(?P<body_issues>(?: #\d+)+)\n?"
        )
        return rf"(?sm)^(?:{merge_pattern}|{no_issue_pattern}|{with_issue_pattern})\Z"

    def info(self) -> str:
        prefixes_list = "\n".join(f"  - {prefix}" for prefix in self.ALLOWED_PREFIXES)
        return (
            "OpenWISP Commit Convention\n\n"
            "Commit messages must follow this structure:\n\n"
            "With issue reference (symmetric, must be in both title and body):\n\n"
            "  [type] Capitalized title #<issue_number>\n\n"
            "  <description>\n\n"
            "  Fixes #<issue_number>\n\n"
            "Without issue reference (for minor changes or urgent fixes):\n\n"
            "  [type] Capitalized title\n\n"
            "  <description>\n\n"
            f"Allowed commit prefixes:\n\n{prefixes_list}\n\n"
            "If in doubt, use chores."
        )


__all__ = ["OpenWispCommitizen"]
