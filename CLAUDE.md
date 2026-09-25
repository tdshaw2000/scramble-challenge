# scramble-challenge

SPEC.md is the spec. Work test-first, with red and green commits so the history shows TDD.
Open PRs as drafts. Mark them ready for review once CI is green and review has passed. Never
merge: the owner does that, with a merge commit.

## Review loop

Every PR is reviewed by the `reviewer` subagent (.claude/agents/reviewer.md) before it is marked
ready. A hook (.claude/hooks/review_gate.py) enforces this. It blocks opening a PR that isn't a
draft, and it blocks marking a PR ready until the pushed HEAD commit has a passing review.

1. Finish the work, commit, push, and open the PR as a draft.
2. Run the `reviewer` subagent. Give it the PR number and one line on what the change is for.
   Don't tell it what to conclude. Its verdict is recorded automatically when it stops.
3. **Blocking findings**: fix each one test-first, push, and run the reviewer again. The hook
   allows 3 rounds with blocking findings. After the third, stop: leave the PR as a draft and
   tell the owner what is still blocking and why. If you think a blocking finding is wrong,
   give the reviewer your evidence on the next round; it still counts as a round.
4. **Once it passes**, post the suggestions as one PR review with event COMMENT and one inline
   comment per suggestion (pull_request_review_write create, add_comment_to_pending_review,
   then submit_pending). Don't act on suggestions unless they are trivial.
5. **Judgment calls** go to the owner, never guessed. Ask each one in the thread as a short
   question with the options and your recommendation, and list them in the PR review body too.
6. Once CI is green, mark the PR ready for review.

The hook only runs inside Claude Code sessions. A PR pushed by hand is not reviewed.
Verdicts live in .git/claude-review/, one file per branch, and are never committed.
