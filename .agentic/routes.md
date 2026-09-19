# Routing Table

Route by task type. `∥` means run in parallel (only if they touch different files or are read-only).

| # | Task type | Chain |
|---|---|---|
| A | New app / feature | `business-analyst` → `api-designer` (+ `postgres-pro`) → `backend-developer` ∥ `frontend-developer` → `test-automator` → `verifier` → `code-reviewer` → `security-auditor` → `documentation-engineer` → `deployment-engineer` (gate) |
| B | Bug fix | `debugger` → owner agent (the domain the bug lives in) → `test-automator` (regression test) → `verifier` → `code-reviewer` |
| C | Refactor / migration | `architect-reviewer` → `refactoring-specialist` → `test-automator` → `verifier` → `code-reviewer` |
| D | Infra / deploy | `cloud-architect` → `devops-engineer` → `deployment-engineer` → `security-auditor` → human gate |
| E | Security audit | `security-auditor` ∥ `code-reviewer` → `verifier` |
| F | Performance | `performance-engineer` → owner agent → `verifier` |
| G | Data / ML pipeline | `postgres-pro` → `python-pro` → `test-automator` → `verifier` → `performance-engineer` |
| H | LLM / AI feature | `research-analyst` → `python-pro` + `api-designer` → `test-automator` → `verifier` |
| I | Research / report | `research-analyst` → `verifier` (every claim sourced) |
| J | Content / docs | `documentation-engineer` → `code-reviewer` |
| K | Incident | `debugger` → `devops-engineer` |
| L | Product validation | `business-analyst` → `product-manager` → `research-analyst` |
| U | **Unknown task** | `research-analyst` → propose a plan and a proposed chain to the user → proceed only after approval |
