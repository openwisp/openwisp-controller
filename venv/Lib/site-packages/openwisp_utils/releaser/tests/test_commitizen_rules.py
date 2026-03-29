import subprocess


def run_cz_check(message):
    result = subprocess.run(
        ["cz", "-n", "cz_openwisp", "check", "--message", message],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_valid_commit_with_issue():
    """Valid: issue in both title and body, matching."""
    message = "[qa] Good commit message #1\n\n" "Some explanation.\n\n" "Fixes #1"
    code, out, err = run_cz_check(message)
    assert code == 0, f"Expected success but got: {out + err}"


def test_valid_commit_without_issue():
    """Valid: no issue referenced at all."""
    message = "[chores] Good commit message\n\n" "Some explanation."
    code, out, err = run_cz_check(message)
    assert code == 0, f"Expected success but got: {out + err}"


def test_valid_commit_without_issue_single_line_body():
    """Valid: no issue, single line body without trailing punctuation."""
    message = "[chores] Good commit message\n\nSome explanation"
    code, out, err = run_cz_check(message)
    assert code == 0, f"Expected success but got: {out + err}"


def test_valid_commit_message_double_prefix():
    """Valid: double prefix like [tests:fix]."""
    message = "[tests:fix] Good commit message"
    code, out, err = run_cz_check(message)
    assert code == 0, f"Expected success but got: {out + err}"


def test_valid_commit_with_closes():
    """Valid: issue in both, using Closes keyword."""
    message = (
        "[feature:qa] Standardized commit messages #110\n\n"
        "Commitizen has been integrated.\n\n"
        "Closes #110"
    )
    code, out, err = run_cz_check(message)
    assert code == 0, f"Expected success but got: {out + err}"


def test_valid_commit_with_related_to():
    """Valid: issue in both, using Related to keyword."""
    message = (
        "[feature] Progress on feature #110\n\n"
        "Partial implementation.\n\n"
        "Related to #110"
    )
    code, out, err = run_cz_check(message)
    assert code == 0, f"Expected success but got: {out + err}"


def test_valid_commit_with_multiple_issues():
    """Valid: multiple issues in both title and body."""
    message = (
        "[feature] Fix bugs #123 #124\n\n"
        "Fixed multiple issues.\n\n"
        "Fixes #123\n"
        "Fixes #124"
    )
    code, out, err = run_cz_check(message)
    assert code == 0, f"Expected success but got: {out + err}"


def test_valid_commit_with_multiple_issues_same_line():
    """Valid: multiple issues on same line with single keyword."""
    message = (
        "[feature] Fix bugs #123 #124\n\n"
        "Fixed multiple issues.\n\n"
        "Fixes #123 #124"
    )
    code, out, err = run_cz_check(message)
    assert code == 0, f"Multiple issues on same line should work: {out + err}"


def test_merge_commits_ignored():
    """Valid: merge commits are always allowed."""
    message = "Merge branch 'master' into issues/110-commit-convention-standardization"
    code, out, err = run_cz_check(message)
    assert code == 0, f"Expected success but got: {out + err}"


def test_empty_commit_message():
    """Invalid: empty commit message."""
    code, out, err = run_cz_check("")
    assert code != 0


def test_invalid_prefix_format():
    """Invalid: missing square brackets around prefix."""
    message = "qa Good commit message #1\n\n" "Body\n\n" "Fixes #1"
    code, out, err = run_cz_check(message)
    assert code != 0


def test_title_not_capitalized():
    """Invalid: title doesn't start with capital letter."""
    message = "[qa] bad commit message #1\n\n" "Body\n\n" "Fixes #1"
    code, out, err = run_cz_check(message)
    assert code != 0


def test_issue_only_in_title():
    """Invalid: issue in title but not in body (asymmetric)."""
    message = "[qa] Good commit message #1\n\n" "Some explanation."
    code, out, err = run_cz_check(message)
    assert code != 0
    assert "title" in (out + err).lower()
    assert "body" in (out + err).lower()


def test_issue_only_in_body():
    """Invalid: issue in body but not in title (asymmetric)."""
    message = "[qa] Good commit message\n\n" "Some explanation.\n\n" "Fixes #1"
    code, out, err = run_cz_check(message)
    assert code != 0
    assert "body" in (out + err).lower()
    assert "title" in (out + err).lower()


def test_mismatched_issue_numbers():
    """Invalid: different issues in title and body."""
    message = "[qa] Good commit message #1\n\n" "Body\n\n" "Fixes #2"
    code, out, err = run_cz_check(message)
    assert code != 0
    assert "mismatch" in (out + err).lower() or "match" in (out + err).lower()


def test_issue_in_the_middle():
    """Valid: issue reference must be at end of title."""
    message = "[qa] Good #1 commit message\n\n" "Body\n\n" "Fixes #1"
    code, out, err = run_cz_check(message)
    assert code == 0, f"Issue in middle of title should still work: {out + err}"


def test_info_includes_all_prefixes():
    """Check that all expected prefixes are documented."""
    result = subprocess.run(
        ["cz", "-n", "cz_openwisp", "info"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0
    assert "- feature" in result.stdout
    assert "- change" in result.stdout
    assert "- fix" in result.stdout
    assert "- docs" in result.stdout
    assert "- tests" in result.stdout
    assert "- ci" in result.stdout
    assert "- chores" in result.stdout
    assert "- qa" in result.stdout
    assert "- deps" in result.stdout
    assert "- release" in result.stdout
    assert "- bump" in result.stdout


def test_error_message_is_user_friendly():
    """Check that error messages are helpful and don't expose regex."""
    message = "INVALID COMMIT MESSAGE"
    code, out, err = run_cz_check(message)
    assert code != 0
    output = out + err
    assert "commit validation: failed!" in output
    assert "Invalid commit message format" in output
    assert "Expected format:" in output
    assert "[prefix]" in output
    assert "[feature]" in output
    # Make sure raw regex pattern is NOT shown
    assert "(?sm)" not in output
    assert "pattern:" not in output.lower()


def test_error_message_for_asymmetric_issues():
    """Check that asymmetric issue errors are clear."""
    # Issue only in title
    message = "[qa] Good commit message #1\n\n" "Some explanation."
    code, out, err = run_cz_check(message)
    assert code != 0
    output = out + err
    assert "title" in output.lower()
    assert "body" in output.lower()
    assert "issue" in output.lower()


def test_valid_commit_with_auto_appended_related_to():
    """Valid: issue in title auto-appended to body as 'Related to'."""
    # This simulates what message() generates when title has issue but body doesn't
    message = (
        "[feature] Add new feature #123\n\n"
        "This adds a new feature.\n\n"
        "Related to #123"
    )
    code, out, err = run_cz_check(message)
    assert code == 0, f"Auto-appended Related to should be valid: {out + err}"


def test_valid_commit_with_multiple_auto_appended_issues():
    """Valid: multiple issues in title auto-appended to body."""
    message = (
        "[feature] Fix bugs #123 #124\n\n"
        "Fixed multiple issues.\n\n"
        "Related to #123\n"
        "Related to #124"
    )
    code, out, err = run_cz_check(message)
    assert code == 0, f"Multiple auto-appended issues should be valid: {out + err}"
