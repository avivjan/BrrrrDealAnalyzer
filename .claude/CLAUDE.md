1. First think through the problem, read the codebase for relevant files, and write a plan to tasks/todo.md.
2. The plan should have a list of todo items that you can check off as you complete them - EACH ITEM SHOULD HAVE A TIME ESTIMATE YOU THINK IT WILL TAKE YOU TO DO.
3. Before you begin working, check in with me and I will verify the plan.
4. Then, begin working on the todo items, marking them as complete as you go.
5. Please every step of the way just give me a high level explanation of what changes you made
6. Make every task and code change you do as simple as possible. We want to avoid making any massive or complex changes. Every change should impact as little code as possible. Everything is about simplicity.
7. Finally, add a review section to the [todo.md](http://todo.md/) file with a summary of the changes you made and any other relevant information.
## Hosting and the MCP server (standing rules)

- Hosting: the FastAPI backend (`BackEnd/`) runs on Render (service `BrrrrDealAnalyzer`, auto-deploys from `main`, URL https://brrrrdealanalyzer.onrender.com); the Vue frontend (`frontend/`) runs on Netlify (https://bigwhales.netlify.app).
- `BackEnd/mcp_server.py` exposes every backend endpoint as an MCP tool (Claude connector at `/mcp/<MCP_PATH_SECRET>`). This coverage is a permanent requirement, not a one-off: **every new feature or endpoint must also be supported over MCP, without being asked.** Concretely, whenever you add or change an endpoint:
  1. Add (or update) its one-line entry in `DESCRIPTIONS` in `BackEnd/mcp_server.py` (tool name = the route's function name without a trailing `_route`). The tool itself is generated from OpenAPI automatically; `tests/test_mcp.py` fails if the description is missing or stale.
  2. If the feature has no backend endpoint (client-side only), decide whether Claude needs it; if so, add a small endpoint so it becomes a tool, and if not, say so in the review section of `tasks/todo.md`.
  3. Run `cd BackEnd && pytest tests/test_mcp.py` before pushing, and mention the MCP tool(s) in the PR description.
