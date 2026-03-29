"""Common Quality Assurance checks for OpenWISP modules."""

import argparse
import os
import re
import sys


def _parse_migration_check_args():
    parser = argparse.ArgumentParser(
        description="Ensures migration files "
        "created have a descriptive name. If "
        "default name pattern is found, "
        "raise exception!"
    )
    parser.add_argument(
        "--migration-path", required=True, help="Path to `migrations/` folder"
    )
    parser.add_argument(
        "--migrations-to-ignore",
        type=int,
        help="Number of migrations after which checking of "
        "migration file names should begin, say, if checking "
        "needs to start after `0003_auto_20150410_3242.py` "
        "value should be `3`",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    return parser.parse_args()


def check_migration_name():
    """Ensure migration files created have a descriptive name.

    If the default name pattern is found, it will raise an exception.
    """
    args = _parse_migration_check_args()
    if args.migrations_to_ignore is None:
        args.migrations_to_ignore = 0
    # QA Check
    migrations_set = set()
    migrations = os.listdir(args.migration_path)
    for migration in migrations:
        if (
            re.match(r"^[0-9]{4}_auto_[0-9]{2}", migration)
            and int(migration[:4]) > args.migrations_to_ignore
        ):
            migrations_set.add(migration)
    if bool(migrations_set):
        migrations = list(migrations_set)
        file_ = "file" if len(migrations) < 2 else "files"
        message = (
            "Migration %s %s in directory %s must "
            "be renamed to something more descriptive."
            % (file_, ", ".join(migrations), args.migration_path)
        )
        if not args.quiet:
            print(message)
        sys.exit(1)


def _parse_commit_check_args():
    parser = argparse.ArgumentParser(
        description="Ensures the commit message "
        "follows the OpenWISP commit guidelines."
    )
    parser.add_argument("--message", help="Commit message", required=True)
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    return parser.parse_args()


def check_commit_message():
    args = _parse_commit_check_args()
    if "#noqa" in args.message.lower():
        return
    long_desc = None
    lines = args.message.split("\n")
    short_desc = lines[0].strip()
    if len(lines) > 1:
        long_desc = lines[1:]
    skip_cases = [
        # merges
        r"^Merge pull request #[A-Za-z0-9.]* from",
        r"^Merge branch '(.*?)' into",
        # releases
        r"^[A-Za-z0-9.]* release$",
        r"^Bumped VERSION to (.*?)$",
        r"^Bump (.*?) from (.*?) to (.*?)$",
    ]
    for case in skip_cases:
        if re.match(case, short_desc):
            return
    errors = []
    # no final dot
    if short_desc and short_desc[-1] == ".":
        errors.append(
            "please do not add a final dot at the end of commit short description"
        )
    # ensure prefix is present
    prefix = re.match(r"\[(.*?)\]", short_desc)
    if not prefix:
        errors.append(
            "missing prefix in the commit short description\n  "
            'Eg: "[feature/fix/change] Action performed"'
        )
    else:
        # ensure there's a capital letter after the prefix
        suffix = short_desc.replace(prefix.group(), "").strip()
        if not suffix[0].isupper():
            errors.append("please add a capital letter after the prefix")
    # default issue mentions
    issues = []
    # ensure there's a blank line between short and long desc
    if long_desc:
        if len(lines) > 1 and lines[1] != "":
            errors.append(
                "please ensure there is a blank line between "
                "the commit short and long description"
            )
        message = " ".join(long_desc)
        result = _find_issue_mentions(message)
        issues = result["issues"]
        good_mentions = result["good_mentions"]
        # check issue mentions in long desc
        issue_location = re.search(r"\#(\d+)", message)
        if issue_location:
            if good_mentions != len(issues):
                errors.append(
                    "You are mentioning an issue in the long description "
                    "without closing it: is it intentional?\n  "
                    'If not, please use "Closes #<issue>" or "Fixes #<issue>"\n  '
                    'Otherwise, use "Related to #<issue>'
                )
            shot_desc_mentions = 0
            for issue in issues:
                if re.search(r"\{}".format(issue), short_desc):
                    shot_desc_mentions += 1
            if shot_desc_mentions < 1:
                errors.append(
                    "if you mention an issue in the long description, "
                    "please show it in the short description too\n  "
                    "eg: [prefix] Action performed #234\n\n      "
                    "Long desc. Closes #234"
                )
    # if short description mentions an issue
    # ensure the issue is either closed or mentioned as "related"
    if re.search(r"\#(\d+)", short_desc):
        mentions = 0
        for issue in issues:
            if re.search(r"\{}".format(issue), short_desc):
                mentions += 1
        if mentions < 1:
            errors.append(
                "You are mentioning an issue in the short description "
                "but it is not clear whether the issue is resolved or not;\n  "
                "if it is resolved, please add to the commit long description:\n  "
                '"Closes #<issue-number>" or "Fixes #<issue-number>";\n  '
                "if the issue is not resolved yet, please use the following form:\n  "
                '"Related to #<issue-number>"'
            )
    # fail in case of error
    if len(errors):
        body = (
            "Your commit message does not follow our "
            "commit message style guidelines:\n\n"
        )
        for error in errors:
            body += "- {}\n".format(error)
        url = (
            "http://openwisp.io/docs/developer/contributing.html"
            "#commit-message-style-guidelines"
        )
        body = "{}\nPlease read our guidelines at: {}".format(body, url)
        if not args.quiet:
            print(body)
        sys.exit(1)


def _find_issue_mentions(message):
    """Looks for issue mentions in ``message``.

    Returns a dict which contains:

    - List of mentioned issues.
    - Count of mentions performed correctly (using one of the common
      github keywords).
    """
    words = message.split()
    issues = []
    issue_locations = []
    counter = 0
    # search issue mentions
    for word in words:
        if re.search(r"\#(\d+)", word):
            issue_locations.append(counter)
        counter += 1
    # check if issue mentions are preceded with the right word
    good_mentions = 0
    for issue_location in issue_locations:
        word = words[issue_location - 1]
        issue = words[issue_location]
        issue = issue.replace(".", "")
        issues.append(issue)
        # check whether issue is just being referred to
        if issue_location > 1:
            preceding_2words = "{} {}".format(
                words[issue_location - 2], words[issue_location - 1]
            )
            allowed_refs = ["related to", "refers to"]
            if preceding_2words.lower() in allowed_refs:
                good_mentions += 1
                continue
        # check whether issue is being closed
        allowed_closure = ["fix", "fixes", "close", "closes"]
        if word.lower() in allowed_closure:
            good_mentions += 1
    return {"issues": issues, "good_mentions": good_mentions}
