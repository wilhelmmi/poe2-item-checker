
# Codex project instructions

## Subagent routing

Use subagents whenever delegating bounded work would improve reliability,
reduce context pollution, or allow independent analysis.

### Routing rules

- Use `project-explorer` before implementation when the affected architecture,
  data flow, dependencies, or file locations are unclear.
- Use `quick-implementer` for small, clearly defined, low-risk implementation
  tasks such as isolated bug fixes, focused tests, simple configuration changes,
  and tightly bounded mechanical refactorings.
- Use `feature-implementer` for implementation tasks that span multiple files or
  components, require investigation, involve design decisions, or have meaningful
  regression risk.
- When uncertain between `quick-implementer` and `feature-implementer`, use
  `feature-implementer`.
- Do not use `quick-implementer` for authentication, authorization, security,
  persistence formats, database migrations, concurrency, distributed state,
  public API changes, or broad refactorings.
- Use `code-reviewer` after non-trivial code changes.
- For complex bugs, first delegate investigation to `project-explorer`, then
  implement based on its report.
- For changes affecting authentication, authorization, persistence, concurrency,
  external APIs, or migrations, always run `code-reviewer`.
- For an empty or newly initialized repository, do not use `quick-implementer`.
  Use `project-explorer` to propose the initial structure, then use
  `feature-implementer` to create the project skeleton, and run
  `code-reviewer` afterward.
- Do not use subagents for trivial typo fixes or isolated mechanical edits that
  can be completed safely by the main agent.
- Prefer parallel agents for independent read-only analysis.
- Avoid parallel writes to overlapping files.
- The main agent remains responsible for scope, final decisions, integration,
  validation, and the final response.


## Workflow

### Small, clearly bounded implementation task

1. Confirm that the requirements and affected code are sufficiently clear.
2. Delegate the change to `quick-implementer`.
3. Inspect the resulting diff and verification results.
4. Run additional tests or checks when warranted.
5. Summarize changes, validation, and remaining risks.

### Non-trivial feature

1. Analyze the request and identify independent work packages.
2. Delegate architecture or codebase exploration when needed.
3. Wait for relevant exploration results.
4. Delegate implementation to `feature-implementer`.
5. Run tests and inspect the resulting diff.
6. Delegate final review to `code-reviewer`.
7. Resolve material review findings.
8. Summarize changes, validation, and remaining risks.
