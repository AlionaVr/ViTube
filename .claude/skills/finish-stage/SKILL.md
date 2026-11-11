---
name: finish-stage
description: Close a ViTube stage. Before the PR: check the flow on the stack, review the stage diff once, update tasks and rules. After the merge: sync main and clean up the worktree. Use when a stage's steps are done or its PR is merged.
---

# Finish a stage

## Before the PR

1. The flow works: run the `smoke-check` skill and ask the user to click the stage's flow in the browser.
   If it fails, the stage is not done: fix it first.
2. Reviews, once per stage, on `git diff main...HEAD`:
    - `db-reviewer` if models or migrations changed;
    - `security-reviewer` if auth, sessions, upload, media, private videos, moderation, Dockerfiles or compose changed;
    - `youtube-ui-reviewer` if pages or components changed.

   Show all findings as one numbered list. The user picks; fix the picked ones in one commit; write the rest to the
   stage's backlog in `tasks/todo.md`.
3. New keys in `.env.example` (`git diff main...HEAD -- .env.example`): tell the user which keys to add to `.env`,
   why, and how to generate them. Never edit `.env`.
4. `tasks/todo.md`: tick the stage's items; open items stay in its section.
5. `tasks/lessons.md`: move stable rules into `CLAUDE.md` (own commit); keep the new ones.
6. Run the `pr-description` skill. Push and open the PR only with the user's OK.

## After the merge

7. In the main checkout: `git switch main && git pull --ff-only`.
8. Run `smoke-check` on `main` if the stage changed the stack.
9. `tasks/todo.md`: mark the stage merged (PR number, merge commit).
10. Worktree: check `git -C <worktree> status --short` is empty, the branch is in `git branch --merged main`, and
    `<worktree>/tasks` is the link, not its own folder (merge its notes into the main `tasks/` first).
    Then, with the user's OK: `git worktree remove <worktree>`, `git branch -d <branch>`.
