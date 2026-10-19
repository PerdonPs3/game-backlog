# Essential instructions for AI agents

Read these rules before planning, creating, or changing any part of the project.
They apply to code, tests, documentation, and configuration.

## Language

- Use English for all work: plans, explanations, documentation, agent instructions, code comments, identifiers, tests, commit messages, branch names, and merge messages.
- Write new or updated user-facing application text in English.

## Git Flow and responsibilities

- `main` is the production branch; `develop` is the integration branch for development and testing. Use these lowercase names.
- Work autonomously on development based on `develop`. Never merge into or push to `main` without the user's explicit permission for that operation. Permission to work on or push `develop` does not authorize production publication.
- For each change, create a local branch from `develop` with a descriptive prefix such as `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, or `chore/`. Do not make changes directly on `develop` or `main`.
- Make atomic commits: each commit must represent one coherent change with a descriptive message. Do not include unrelated work.
- Stay on the local branch until its objective, including relevant validation, is complete, or the user explicitly asks to leave, cancel, or switch tasks. If blocked, report the blocker and retain the branch; do not integrate unfinished work as complete.
- Once the objective is complete, merge the branch into `develop` using `git merge --no-ff`, with a message identifying the change. Push `develop` to the remote and verify the result.
- Change branches stay local: do not push them or create remote branches for them. Only push `develop` and `main`; pushing `main` still requires the user's explicit permission.

## Preserve the visual history

- Always preserve each branch's commits and divergence in the Git graph. Use `--no-ff` merges even when a fast-forward is possible.
- Do not use squash, fast-forward, or rebase to integrate a change branch into `develop`, because they would remove the branch divergence the user wants to visualize.
- After merging and verifying the push to `develop`, the local branch reference may be deleted with `git branch -d`. Never delete commits or rewrite history to hide the branch.
- The merge commit and its two parents preserve the divergence in applications that display the graph. Deleting a local branch reference may remove its label depending on the application; preserve the branch name in the merge message. Git cannot guarantee that every application displays a deleted branch's label.
- Do not force-push or rewrite shared history. Always preserve the user's existing changes.
