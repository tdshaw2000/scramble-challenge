"""Claude Code hook: no pull request is marked ready for review until the reviewer passes it.

    review_gate.py record   SubagentStop, for the reviewer subagent. Saves its verdict
                            against the commit it reviewed.
    review_gate.py gate     PreToolUse. Blocks opening a PR that isn't a draft, and blocks
                            marking a PR ready until the current commit has passed review.

Claude Code sends the event as JSON on stdin. Exit code 2 blocks, and stderr tells Claude why.
Verdicts are kept in .git/claude-review/, so they are never committed. Standard library only,
so the hook runs with any python3.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

MAX_ROUNDS = 3
BLOCK = 2
REVIEWER = "reviewer"
LOOP = "See 'Review loop' in CLAUDE.md."

# A gh command at the start of the line or after ; & | so a quoted mention doesn't count.
GH_READY = re.compile(r"(?:^|[;&|\n])\s*gh\s+pr\s+ready\b([^;&|\n]*)")
GH_CREATE = re.compile(r"(?:^|[;&|\n])\s*gh\s+pr\s+create\b([^;&|\n]*)")
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
    commit = git(cwd, "rev-parse", "HEAD")
    verdict = parse_verdict(event.get("last_assistant_message"))
    problem = None
    if verdict is None:
        problem = (
            "Your review must end with a ```json block holding commit, blocking, "
            "suggestions and judgment_calls (see your instructions)."
        )
    elif verdict.get("commit") != commit:
        problem = f"The verdict names commit {verdict.get('commit')}, but HEAD is {commit}."
    if problem:
        if event.get("stop_hook_active"):
            return  # Already sent back once; don't loop. Nothing is recorded, so the gate holds.
        block(problem + " Fix the verdict block and finish again.")
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


def wants(event):
    """What the tool call does: 'ready', 'create-not-draft', or None for anything else."""
    tool, args = event.get("tool_name"), event.get("tool_input") or {}
    if tool == "mcp__github__update_pull_request":
        return "ready" if args.get("draft") is False else None
    if tool == "mcp__github__create_pull_request":
        return None if args.get("draft") is True else "create-not-draft"
    if tool == "Bash":
        command = args.get("command", "")
        for match in GH_READY.finditer(command):
            if "--undo" not in match.group(1).split():
                return "ready"
        for match in GH_CREATE.finditer(command):
            flags = match.group(1).split()
            if "--draft" not in flags and "-d" not in flags:
                return "create-not-draft"
    return None


def gate(event):
    action = wants(event)
    if action is None:
        return
    if action == "create-not-draft":
        block("Open the pull request as a draft. It is marked ready only after review. " + LOOP)

    cwd = event.get("cwd")
    if git(cwd, "status", "--porcelain"):
        block("There are uncommitted changes. Commit and push them, then review. " + LOOP)
    commit = git(cwd, "rev-parse", "HEAD")
    if git(cwd, "rev-parse", "@{upstream}") != commit:
        block("HEAD isn't pushed. git push, then review that commit. " + LOOP)

    rounds = load_rounds(cwd)
    this = [r for r in rounds if r["commit"] == commit]
    if this and this[-1]["blocking"] == 0:
        return
    failed = sum(1 for r in rounds if r["blocking"] > 0)
    if failed >= MAX_ROUNDS:
        block(
            f"Stop: {failed} review rounds found blocking issues. Leave the PR as a draft and "
            "tell the user what is still blocking. " + LOOP
        )
    if this:
        block(
            f"Review round {failed} of {MAX_ROUNDS} found {this[-1]['blocking']} blocking "
            "issue(s). Fix them (red/green), push, and run the reviewer subagent again. " + LOOP
        )
    block(f"Commit {commit[:7]} hasn't been reviewed. Run the reviewer subagent first. " + LOOP)


def main():
    event = json.load(sys.stdin)
    {"record": record, "gate": gate}[sys.argv[1]](event)


if __name__ == "__main__":
    main()
