## 1. Planning Phase
- **Explore First:** Think through the problem, inspect relevant codebase files, and draft a plan at `tasks/todo/<task_name>.md`.
- **Branching:** Create a branch named `<task_name>` from latest `main`. All implementation code, plan files, and tests must reside on this branch.
- **Plan Requirements:**
  - Checkable todo items with estimated completion time per item.
  - Required tests broken down by layer: Unit, Integration, and E2E.
  - An MCP server support task for any new feature or endpoint.
  - A dedicated security task with contents read from `.claude/security.md`.
- **Review Gate:** Check in with me to verify the plan before writing any implementation code.
## 2. Execution Phase
- Work through todo items systematically, checking them off as completed.
- Provide concise, high-level chat updates after each step explaining what changes were made.
- When finished: push the branch and open a PR.
## 3. Code Standards & Simplicity
- **Simplicity First:** Keep every change as minimal and self-contained as possible. Avoid massive refactors or high-impact edits.
- **Explicit Naming:** Every variable, function, field, DB column, and test name must be fully self-explanatory on its own without needing comments or surrounding context. Always prefer a longer, descriptive name over a short, vague one.
