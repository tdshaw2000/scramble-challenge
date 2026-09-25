"""Claude Code hook: no pull request is marked ready for review until the reviewer passes it.

    review_gate.py record   SubagentStop, for the reviewer subagent. Saves its verdict
                            against the commit it reviewed.
    review_gate.py gate     PreToolUse. Blocks opening a PR that isn't a draft, and blocks
                            marking a PR ready until the current commit has passed review.

Claude Code sends the event as JSON on stdin. Exit code 2 blocks, and stderr tells Claude why.
Any other failure would let the tool call through, so the gate turns its own errors into blocks.
Verdicts are kept in .git/claude-review/, so they are never committed. Standard library only,
so the hook runs with any python3.
"""

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

MAX_ROUNDS = 3
BLOCK = 2
REVIEWER = "reviewer"
LOOP = "See 'Review loop' in CLAUDE.md."

# Fail closed: anything that looks like marking ready is gated, even a quoted mention.
# A false block only costs a retry; a missed one skips the review.
# Each "pr ready" is exempt only if its own part of the command (up to ; & | or #) says --undo.
GH_READY = re.compile(r"\bpr\s+ready\b([^;&|#\n]*)")
GRAPHQL_READY = "markPullRequestReadyForReview"
GH_CREATE = re.compile(r"\bgh\b.*\bpr\s+create\b", re.DOTALL)
SEPARATORS = {";", "&", "&&", "|", "||", "\n", "(", ")"}
DRAFT_FLAGS = {"--draft", "-d", "--draft=true"}
VERDICT = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def git(cwd, *args):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def block(message):
    print(message, file=sys.stderr)
    sys.exit(BLOCK)


def state_file(cwd):
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    folder = Path(git(cwd, "rev-parse", "--absolute-git-dir")) / "claude-review"
    return folder / (branch.replace("/", "__") + ".json")


def load_rounds(cwd):
    path = state_file(cwd)
    return json.loads(path.read_text())["rounds"] if path.exists() else []


def save_round(cwd, round_):
    path = state_file(cwd)
    rounds = load_rounds(cwd) + [round_]
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"rounds": rounds}, indent=2))


# --- record ---


def parse_verdict(message):
    blocks = VERDICT.findall(message or "")
    if not blocks:
        return None
    try:
        verdict = json.loads(blocks[-1])
    except json.JSONDecodeError:
        return None
    keys = ("blocking", "suggestions", "judgment_calls")
    if not isinstance(verdict, dict) or not all(isinstance(verdict.get(k), list) for k in keys):
        return None
    return verdict


def record(event):
    if event.get("agent_type") != REVIEWER:
        return
    cwd = event.get("cwd")
    verdict = parse_verdict(event.get("last_assistant_message"))
    problem = None
    if verdict is None:
        problem = (
            "Your review must end with a ```json block holding commit, blocking, "
            "suggestions and judgment_calls (see your instructions)."
        )
    else:
        # The verdict counts for the commit it names. If HEAD has moved on since, the gate
        # simply won't find a review for HEAD; the reviewer must never relabel its verdict.
        named = verdict.get("commit")
        commit = None
        if isinstance(named, str) and re.fullmatch(r"[0-9a-f]{40}", named):
            commit = git(cwd, "rev-parse", "--verify", "--quiet", f"{named}^{{commit}}")
        if commit is None:
            problem = (
                f"The verdict names commit {verdict.get('commit')}, which isn't a full sha of a "
                f"commit here. Name the commit you actually reviewed (HEAD is "
                f"{git(cwd, 'rev-parse', 'HEAD')} now; if that isn't what you reviewed, say so "
                "and review it from scratch)."
            )
    if problem:
        if event.get("stop_hook_active"):
            return  # Already sent back once; don't loop. Nothing is recorded, so the gate holds.
        block(problem)
    save_round(
        cwd,
        {
            "commit": commit,
            "blocking": len(verdict["blocking"]),
            "suggestions": len(verdict["suggestions"]),
            "judgment_calls": len(verdict["judgment_calls"]),
        },
    )


# --- gate ---


def marks_ready(command):
    command = command.replace("\\\n", " ")  # join backslash line continuations
    if GRAPHQL_READY in command:
        return True
    return any(
        "--undo" not in match.group(1).split()
        for line in command.split("\n")
        if re.search(r"\bgh\b", line)
        for match in GH_READY.finditer(line)
    )


def creates_without_draft(command):
    """True if any gh pr create in the command lacks its own --draft. Unsure means True."""
    if not GH_CREATE.search(command):
        return False
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        return True  # unbalanced quotes
    segments, current = [], []
    for word in words + [";"]:
        if word in SEPARATORS or set(word) <= set(";&|()\n"):
            segments.append(current)
            current = []
        else:
            current.append(word)
    creates = [
        seg
        for seg in segments
        if any(seg[i : i + 2] == ["pr", "create"] and "gh" in seg[:i] for i in range(len(seg)))
    ]
    if not creates:
        return True  # gh pr create is in there somewhere we can't read, such as bash -c "..."
    return any(not DRAFT_FLAGS & set(seg) for seg in creates)


def wants(event):
    """What the tool call does: 'ready', 'create-not-draft', or None for anything else."""
    tool, args = event.get("tool_name") or "", event.get("tool_input") or {}
    if tool.startswith("mcp__") and tool.endswith("__update_pull_request"):
        return "ready" if args.get("draft") is False else None
    if tool.startswith("mcp__") and tool.endswith("__create_pull_request"):
        return None if args.get("draft") is True else "create-not-draft"
    if tool == "Bash":
        command = str(args.get("command") or "")
        if marks_ready(command):
            return "ready"
        if creates_without_draft(command):
            return "create-not-draft"
    return None


def check_ready(cwd):
    if git(cwd, "rev-parse", "--abbrev-ref", "HEAD") in (None, "HEAD"):
        block("Not on a git branch here, so the review state can't be checked. " + LOOP)
    if git(cwd, "status", "--porcelain"):
        block("There are uncommitted changes. Commit and push them, then review. " + LOOP)
    commit = git(cwd, "rev-parse", "HEAD")
    upstream = git(cwd, "rev-parse", "@{upstream}")
    if upstream is None:
        block("This branch has no upstream. git push -u origin HEAD, then try again. " + LOOP)
    if upstream != commit:
        block("HEAD isn't pushed. git push, then review that commit. " + LOOP)

    rounds = load_rounds(cwd)
    failed = len({r["commit"] for r in rounds if r["blocking"] > 0})
    if failed >= MAX_ROUNDS:
        block(
            f"Stop: {failed} review rounds found blocking issues. Leave the PR as a draft and "
            "tell the user what is still blocking. " + LOOP
        )
    this = [r for r in rounds if r["commit"] == commit]
    if this and this[-1]["blocking"] == 0:
        return
    if this:
        block(
            f"Review round {failed} of {MAX_ROUNDS} found {this[-1]['blocking']} blocking "
            "issue(s). Fix them (red/green), push, and run the reviewer subagent again. " + LOOP
        )
    block(f"Commit {commit[:7]} hasn't been reviewed. Run the reviewer subagent first. " + LOOP)


def gate(event):
    action = wants(event)
    if action is None:
        return
    if action == "create-not-draft":
        block("Open the pull request as a draft. It is marked ready only after review. " + LOOP)
    try:
        check_ready(event.get("cwd"))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        block(f"The review gate failed ({error!r}), so it is blocking to be safe. " + LOOP)


def main():
    event = json.load(sys.stdin)
    {"record": record, "gate": gate}[sys.argv[1]](event)


if __name__ == "__main__":
    main()
