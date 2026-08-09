# ADR-0001 — v2 starts from a clean database and a new Alembic history

Status: accepted · 2026-07-19 · Phase 9

## Context

The repository carried a Tracker/commitment prototype whose storage could not
express account-scoped periods, workspace-scoped manual rates, or crypto-
precision ledger values. Migrating those rows forward would have preserved a
data model the release explicitly rejects.

## Decision

The release starts with a clean database and a new Alembic history. No legacy
rows are migrated.

Before any local `finapp.db` is replaced or deleted, a timestamped copy is
written to `.backups/`, its SHA-256 recorded, and both open and restore
verification logged. Phase 9 retained both a SQLite online backup and the exact
original file; Git history retains the removed migration chain.

## Consequences

- There is no upgrade path from the prototype database. This is intentional.
- Any future migration starts from `0001_release_v2`.
- The backup ritual is mandatory and is repeated for every destructive local
  database action.
