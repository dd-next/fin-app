# ADR-0006 — The repository is the only shared memory between agents

Status: accepted · 2026-08-08

## Context

Work runs across two agent vendors — Claude Code and Codex — and across many
short sessions. Each session starts with no memory of the last one. Some tools
are reachable by only one of them: `claude.ai/design` projects, for example,
are visible to Claude Code and invisible to Codex.

Anything held only in a chat thread, a design project, or a personal note is
therefore unavailable to at least one participant, including the author two
weeks later.

## Decision

State that must survive a session lives in the repository as a committed file.
Concretely:

- priorities → [`BACKLOG.md`](../BACKLOG.md)
- what a task means and what happened to it → `tasks/T-NNN.md`
- decisions → this directory
- current release state → [`PROGRESS.md`](../PROGRESS.md)
- design truth → `design/`, including the tokens the application actually
  imports

A design *decision* that exists only in a `claude.ai/design` project or a chat
link does not exist. The decision — tokens, states, spacing rules, what is
deliberately not themed — is landed in `design/` in the same commit as the code
that depends on it. The remote design project is a rendering surface, not the
source of truth.

Heavy design *material* may be exempt. Reference images, recordings, and large
exports are inputs a human reads, not state an agent needs in order to make a
decision, so they may stay outside the repository. Whatever the owner supplies
is listed in [`design/DESIGN-NOTES.md`](../design/DESIGN-NOTES.md); material
that is not listed there is not part of the design.

A task instruction never says "match the design". It names a token in the
stylesheet, a rule in `DESIGN-NOTES.md`, or a specific screen the owner has
already described in the task file.

## Consequences

- Context cost per session is bounded: `AGENTS.md` plus one task file, not the
  whole repository.
- An agent without design-tool access is never blocked by that.
- Heavy reference material may stay outside git when it is not needed to make a
  decision, provided `design/DESIGN-NOTES.md` records where it lives.
