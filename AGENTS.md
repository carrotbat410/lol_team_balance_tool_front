# Agent Guide

- Start with @CLAUDE.md.
- Use @README.md for product overview and @package.json for available scripts.
- Keep changes focused. Do not rewrite unrelated files.
- After UI or routing changes, run the smallest useful verification from @.claude/rules/verification.md.
- Prefer referencing existing docs with `@filename` instead of duplicating long explanations.
- For feature development, bug fixes, refactoring, database, security, or deployment changes, use `$lol-ai-workflow` to run Researcher, Planner, human approval, Implementer, and blind Reviewer stages.
- The Coordinator routes outputs between subagents. The user approves the plan but never has to copy it between threads.
- Commit, push, and deploy only when the user explicitly requests them.
