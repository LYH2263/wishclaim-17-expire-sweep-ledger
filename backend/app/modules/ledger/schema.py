"""Sweep ledger tables: release batches and per-lock entries."""

DDL = """
CREATE TABLE IF NOT EXISTS sweep_batches(
  batch_id TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'sweep',
  created_at TEXT NOT NULL,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  released_count INTEGER NOT NULL DEFAULT 0,
  skipped_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sweep_ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL REFERENCES sweep_batches(batch_id),
  wish_id INTEGER NOT NULL,
  claimer TEXT,
  claimed_at TEXT NOT NULL,
  released_at TEXT NOT NULL,
  lock_key TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_ledger_batch ON sweep_ledger(batch_id);
CREATE INDEX IF NOT EXISTS idx_ledger_wish ON sweep_ledger(wish_id);
"""
