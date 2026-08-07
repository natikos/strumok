"""Report delivery and project-health metrics derived from git and GitHub history.

Read-only: runs `git` and `gh` queries and prints a report. Nothing is written to
history, issues, or PRs.

The metrics here deliberately avoid cycle time and throughput. This project has
been agentic since its first commit, so there is no pre-agentic baseline to
compare against, and issue open/close timestamps measure the `commit-work` flow
filing and closing an issue minutes apart rather than the duration of any work.
Rework -- did a change need fixing shortly after it landed -- needs no baseline
to be meaningful, so that is what this measures.

Usage:
    python3 scripts/project_metrics.py
    python3 scripts/project_metrics.py --since 2026-08-01
    python3 scripts/project_metrics.py --coverage
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

# The commit that introduced docs/contributing.md, and with it the requirement
# that subjects carry a type, scope, and issue number. Commits before this
# predate the convention, so measuring them against it would report a
# compliance problem that is really just project history.
CONVENTION_SINCE = date(2026, 8, 6)

# Subject line budget from docs/contributing.md. Squash-merging appends the PR
# number, so a subject at the limit still lands near 70 in `git log --oneline`.
SUBJECT_LIMIT = 65

# A fix landing within this window of the change it repairs reads as rework
# rather than as a defect surfaced by real-world use.
REWORK_WINDOW_DAYS = 14

CONVENTIONAL = re.compile(r"^(?P<type>feat|fix|chore|refactor|docs|test|style)"
                          r"(?:\((?P<scope>[^)]+)\))?: (?P<desc>.+)$")

# Squash-merges append the PR number, so subjects can end with both an issue and
# a PR reference: "...(#13) (#14)". Capture every trailing reference.
TRAILING_REFS = re.compile(r"\s*\(#(\d+)\)(?=(?:\s*\(#\d+\))*\s*$)")

FIX_TYPES = {"fix"}
CHANGE_TYPES = {"feat", "refactor"}


REPO_ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> str | None:
    """Return stdout, or None if the command is unavailable or fails."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout, cwd=cwd or REPO_ROOT)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


class Commit:
    def __init__(self, sha: str, day: date, subject: str, files: list[str]):
        self.sha = sha
        self.day = day
        self.subject = subject
        self.files = files

        match = CONVENTIONAL.match(subject)
        self.type = match.group("type") if match else None
        self.scope = match.group("scope") if match else None
        self.conventional = match is not None
        self.issues = [int(n) for n in TRAILING_REFS.findall(subject)]

        # Squash-merging appends the PR number to whatever was authored. The
        # length budget governs the subject as written, so measure it with any
        # trailing PR reference removed -- but keep the issue reference, which
        # the author is responsible for including.
        authored = subject
        if len(self.issues) > 1:
            authored = TRAILING_REFS.sub("", subject).strip()
            authored = f"{authored} (#{self.issues[0]})"
        self.authored_length = len(authored)


def load_commits(since: str | None) -> list[Commit]:
    """Read commits oldest-first, each with the files it touched."""
    cmd = ["git", "log", "--reverse", "--name-only", "--date=short",
           "--format=%x00%H|%ad|%s"]
    if since:
        cmd.append(f"--since={since}")

    out = run(cmd)
    if out is None:
        sys.exit("error: `git log` failed -- is this a git repository?")

    commits = []
    for block in out.split("\x00"):
        if not block.strip():
            continue
        header, _, rest = block.partition("\n")
        sha, day, subject = header.split("|", 2)
        files = [line for line in rest.splitlines() if line.strip()]
        commits.append(Commit(sha[:7], date.fromisoformat(day), subject, files))
    return commits


def report_rework(commits: list[Commit]) -> None:
    """Fix commits that repair a recent change in the same scope."""
    print("\nRework")
    print("-" * 60)

    changes: dict[str | None, list[Commit]] = defaultdict(list)
    pairs: list[tuple[Commit, Commit]] = []

    for commit in commits:
        if commit.type in FIX_TYPES:
            for prior in reversed(changes[commit.scope]):
                if commit.day - prior.day > timedelta(days=REWORK_WINDOW_DAYS):
                    continue
                # Same scope within the window is not enough on its own -- two
                # unrelated changes can share a scope. Require the fix to touch
                # a file the original change touched.
                if not set(commit.files) & set(prior.files):
                    continue
                pairs.append((prior, commit))
                break
        if commit.type in CHANGE_TYPES:
            changes[commit.scope].append(commit)

    total_changes = sum(len(v) for v in changes.values())
    if total_changes:
        rate = len(pairs) / total_changes * 100
        print(f"  {len(pairs)} of {total_changes} feat/refactor commits were "
              f"followed by a fix in the same scope within "
              f"{REWORK_WINDOW_DAYS}d ({rate:.0f}%)")
    else:
        print("  no feat/refactor commits in range")

    for prior, fix in pairs:
        print(f"    {prior.sha} {prior.subject}")
        print(f"      -> {fix.sha} {fix.subject} (+{(fix.day - prior.day).days}d)")

    # A file rewritten days after it was last touched suggests the first pass
    # did not settle, independent of how the commits were labelled.
    touched: dict[str, Commit] = {}
    churn: list[tuple[str, Commit, Commit]] = []
    for commit in commits:
        for path in commit.files:
            prior = touched.get(path)
            if prior and commit.day - prior.day <= timedelta(days=REWORK_WINDOW_DAYS):
                churn.append((path, prior, commit))
            touched[path] = commit

    counts: dict[str, int] = defaultdict(int)
    for path, _, _ in churn:
        counts[path] += 1

    if counts:
        print(f"\n  Files re-touched within {REWORK_WINDOW_DAYS}d (top 10):")
        for path, count in sorted(counts.items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {count:2d}x  {path}")


def report_duplicate_subjects(commits: list[Commit]) -> None:
    """Identical subjects usually mean a change was redone rather than extended."""
    seen: dict[str, list[Commit]] = defaultdict(list)
    for commit in commits:
        seen[commit.subject].append(commit)

    repeats = {s: cs for s, cs in seen.items() if len(cs) > 1}
    if not repeats:
        return

    print("\n  Repeated commit subjects:")
    for subject, group in repeats.items():
        shas = ", ".join(c.sha for c in group)
        print(f"    {len(group)}x  {subject}  [{shas}]")


def report_convention(commits: list[Commit]) -> None:
    """Compliance with the subject rules in docs/contributing.md."""
    print("\nCommit convention compliance")
    print("-" * 60)

    scoped = [c for c in commits if c.day >= CONVENTION_SINCE]
    skipped = len(commits) - len(scoped)
    if skipped:
        print(f"  ({skipped} commits before {CONVENTION_SINCE} predate the "
              f"convention and are excluded)")

    if not scoped:
        print("  no commits in range since the convention landed")
        return

    problems: list[tuple[Commit, str]] = []
    for commit in scoped:
        if not commit.conventional:
            problems.append((commit, "not Conventional Commits format"))
            continue
        if not commit.scope:
            problems.append((commit, "missing scope"))
        if not commit.issues:
            problems.append((commit, "missing issue number"))
        if commit.authored_length > SUBJECT_LIMIT:
            problems.append((commit, f"subject {commit.authored_length} chars "
                                     f"(limit {SUBJECT_LIMIT}, excluding any "
                                     f"appended PR number)"))

    clean = len(scoped) - len({c.sha for c, _ in problems})
    print(f"  {clean} of {len(scoped)} commits fully compliant")
    for commit, issue in problems:
        print(f"    {commit.sha}  {issue}")
        print(f"             {commit.subject}")


def report_issues() -> None:
    """Open defects and how long they have been sitting."""
    print("\nOpen issues")
    print("-" * 60)

    out = run(["gh", "issue", "list", "--state", "open", "--limit", "200",
               "--json", "number,title,createdAt,labels"])
    if out is None:
        print("  unavailable (`gh` not installed, unauthenticated, or offline)")
        return

    issues = json.loads(out)
    if not issues:
        print("  none open")
        return

    today = datetime.now().date()
    rows = []
    for issue in issues:
        created = datetime.fromisoformat(issue["createdAt"]).date()
        labels = {label["name"] for label in issue["labels"]}
        is_bug = bool(labels & {"bug", "defect"})
        rows.append((( today - created).days, issue["number"], issue["title"], is_bug))

    rows.sort(reverse=True)
    bugs = [r for r in rows if r[3]]
    print(f"  {len(rows)} open ({len(bugs)} labelled as defects)")
    if bugs:
        print(f"  oldest defect: {bugs[0][0]}d")
    for age, number, title, is_bug in rows:
        marker = "BUG " if is_bug else "    "
        print(f"    {marker}#{number:<4} {age:4d}d  {title}")


def report_coverage() -> None:
    """Frontend coverage via vitest. The backend has no pytest-cov dependency."""
    print("\nTest coverage")
    print("-" * 60)

    out = run(["bun", "run", "test", "--", "--coverage",
               "--coverage.reporter=text-summary"],
              cwd=REPO_ROOT / "frontend", timeout=300)
    if out is None:
        print("  frontend: unavailable (`bun` missing or the suite failed)")
    else:
        lines = [line.strip() for line in out.splitlines()
                 if re.search(r"(Statements|Branches|Functions|Lines)\s*:", line)]
        if lines:
            print("  frontend:")
            for line in lines:
                print(f"    {line}")
        else:
            print("  frontend: suite ran but reported no coverage summary")

    print("  backend:  unavailable (no pytest-cov dependency; add it to the dev "
          "extra in backend/pyproject.toml to enable)")


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--since", help="only consider commits after this date "
                                        "(any format git accepts)")
    parser.add_argument("--coverage", action="store_true",
                        help="also run the frontend test suite for coverage "
                             "(slow; off by default)")
    args = parser.parse_args()

    commits = load_commits(args.since)
    if not commits:
        print("No commits in range.")
        return 0

    span = f"{commits[0].day} to {commits[-1].day}"
    print("=" * 60)
    print(f"Strumok project metrics -- {len(commits)} commits, {span}")
    print("=" * 60)

    report_rework(commits)
    report_duplicate_subjects(commits)
    report_convention(commits)
    report_issues()
    if args.coverage:
        report_coverage()

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
