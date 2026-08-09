# AGENTS.md — working agreement for the next FinApp v2 release

`CLAUDE.md` is a symlink to this file. Claude Code and Codex work from the same
agreement; edit this file, never a copy of it.

Start every session with this file, `docs/PROGRESS.md`, and the one task file
you are working on. Read further only when the task needs it —
`docs/README.md` lists what exists and when to open it. The primary product and
technical specification is `docs/specs/FinnApp-v2.md`; `docs/BUILD_PLAN-v2.md`
and `docs/REVIEW_PROTOCOL-v2.md` govern phase order and review. Historical
files within `docs/specs/` and the root-level v2 markdown pointers cannot
override these active documents.

## Tech stack

- Python 3.12, FastAPI, Pydantic v2.
- SQLAlchemy 2.x async ORM and Alembic.
- SQLite through `aiosqlite` for local development.
- `pytest` and `httpx` for automated tests.
- Plain HTML, CSS and vanilla JavaScript; no frontend build step.

Do not deviate from the stack without recording the reason in
`docs/PROGRESS.md`.

## Hard rules

- The health endpoint is exactly `/health`.
- Money and rates always use `Decimal`, never `float`.
- Asset precision is explicit; ledger storage must support crypto precision.
- Account balances, totals, and account-period values derive from posted ledger
  movements.
- Keep daily-budget calculations in `app/budget.py` pure: no DB or framework
  imports.
- All active product and technical specifications live in `docs/`.
- The public application API uses `/api/v1`.
- UI copy is English only.
- Do not add Redis, Celery, Prometheus, a queue, or a background worker.
- Google Sheets, Telegram Mini App, XLSX export, crypto sync, savings goals,
  category limits, pools, and full analytics are outside this release.
- Docker is added only in Phase 13. Do not add dependencies that are not used.

## V2 reset rule

The release starts with a clean database and a new Alembic history. No legacy
rows are migrated. Before replacing or deleting local `finapp.db`, create a
timestamped recoverable copy in `.backups/`, record its SHA-256 checksum and
open/restore verification in `docs/PROGRESS.md`, then proceed.

## Mandatory workflow

Work strictly phase by phase from `docs/BUILD_PLAN-v2.md`; do not skip ahead.
Every phase is split into bounded logical blocks.

After **every written logical block**:

1. Run targeted tests.
2. Create a separate, read-only reviewer sub-agent following
   `docs/REVIEW_PROTOCOL-v2.md`.
3. Fix all review findings and re-review if those fixes change behavior or
   coverage.
4. The implementer records reviewer identity, exact reviewed diff/range,
   verbatim findings, resolution, and test evidence in the task file under
   `docs/tasks/`. The read-only reviewer never edits repository files.

After every phase:

1. Run phase tests, complete `pytest`, `node --check app/static/app.js`, and
   `git diff --check`, plus the phase-specific migration/browser/Docker checks.
2. Update `docs/PROGRESS.md` with the phase status, 2–4 completed-work lines,
   exact gate results, and links to task files containing detailed review
   evidence. Decisions go to `docs/decisions/`, linked rather than restated.
3. The repository owner accepts the phase, archives its closed task files, and
   creates a final `v2 phase N: <short summary>` commit only after all P0–P2
   review findings are closed. Task-level commits use
   `T-NNN: <short summary>` and are expected before the phase closes.

If blocked, record the blocker and attempted fixes in the task file, update
`docs/PROGRESS.md` only when release state changed, commit a clean runnable
checkpoint on the task branch, and stop. The app and tests must be runnable at
the end of every phase.

## Session protocol

One task, one exact branch, and one active implementer at a time. A task may
span several sequential sessions; every handoff is written to its append-only
session log. A task is the logical block that `BUILD_PLAN-v2.md` and
`REVIEW_PROTOCOL-v2.md` already require; the task file is where its detailed
evidence lives.

The cycle, and who owns each step:

| Step | Owner | Output |
|------|-------|--------|
| Prioritise | repository owner only | order of `docs/BACKLOG.md` |
| Specify | agent + independent readiness reviewer | reviewed `docs/tasks/T-NNN.md` from `TEMPLATE.md` — no code |
| Implement | agent, own branch | code + `Session log` entry |
| Review | a **different** agent, read-only | returned findings, transcribed verbatim by implementer |
| Accept | repository owner | merge, mark task `done`, update `PROGRESS.md` |

### Starting a session

1. Read this file, `docs/PROGRESS.md`, and the task file. Do not read the whole
   `docs/` tree, and do not read `docs/history/` unless you need evidence for a
   specific closed decision.
2. Confirm the task has passed readiness review, is unblocked, and its
   `blocked-by` tasks are accepted. Readiness means a separate read-only agent
   checked the task goal, bounded acceptance criteria, Touches/Out-of-scope,
   dependencies, and verification commands against the named specs. The task
   file records reviewer identity, reviewed task-file commit, and verdict. The
   repository owner performs and commits the `backlog` → `todo` promotion only
   after that evidence exists.
3. For an initial claim, require `status: todo` in the current accepted
   integration `HEAD`, create the exact task branch from that `HEAD`, and stop
   if the branch already exists. Branch creation is the atomic claim. In the
   first task commit record that resolved integration hash as `base-commit`,
   set the task and matching backlog row to `in-progress`, and record the
   implementer. This avoids asking the owner promotion commit to contain its
   own hash.
4. For a resumed session, require `status: in-progress` or `review`, the same
   recorded implementer, existing task branch, and unchanged `base-commit`.
   Switch to that branch and continue from the append-only session log. If any
   identity, branch, or base invariant disagrees, stop for owner resolution.
   The task file is lifecycle authority; backlog status mirrors it.
5. Work on that task only. Discovering adjacent work is normal: append a row to
   the **Icebox** table in `docs/BACKLOG.md` and carry on. Never widen the
   current task, and never promote your own row into **Next**.

### Ending a session

A session is not finished until all of the following are written:

1. A `Session log` entry in the task file: date, which agent, what landed, what
   is left, open questions. Write it even when the session achieved nothing —
   especially then.
2. Any decision that would cost real work to reverse, as an ADR in
   `docs/decisions/`, indexed in `docs/DECISIONS.md`. A sentence beginning "we
   decided" belongs there, not in a session log.
3. `docs/PROGRESS.md` updated if the release state changed. Replace the stale
   lines; do not append a new log entry.

Owner acceptance merges the task and marks it `done`; the task file remains in
`docs/tasks/` so phase-level evidence stays together. The owner moves all
closed task files to `docs/tasks/archive/` only when accepting the phase.

An unwritten handoff is the same as no work: the next session, possibly the
other vendor, starts blind.

### Two agents

- Claude Code: specification, decomposition, anything touching money, the
  ledger, or the schema.
- Codex: tasks whose acceptance criteria are already written and checkable;
  long mechanical runs.
- The reviewer is the other vendor when available. If the other vendor is not
  callable, a fresh independent reviewer of the same vendor is allowed; record
  that fallback explicitly in the task file.
- Never run two active implementers in the same worktree. Parallel
  implementation uses `git worktree`. A read-only reviewer may inspect the
  implementer's paused worktree and uncommitted manifest; it must not edit or
  continue implementation there.

### Repository as shared memory

State that must survive a session lives in a committed file — see
`docs/decisions/ADR-0006-repo-is-the-shared-agent-memory.md`.

A design decision that exists only in a `claude.ai/design` project or a chat
link does not exist: Codex cannot reach it and neither can the next session.
Land the decision in `docs/design/` in the same commit as the code that depends
on it. Never write a task instruction that says "match the design" — name a
token, a rule in `docs/design/DESIGN-NOTES.md`, or a state described in the
task file.

## Definition of done

All acceptance criteria in the active specifications and task files are met,
every logical block has an independent reviewer pass, the full automated suite
passes, the SPA passes scratch-database browser checks at the specified mobile
viewport and the preserved desktop width, and README documents install, run,
migrate, test, Docker persistence, backup, and restore.
