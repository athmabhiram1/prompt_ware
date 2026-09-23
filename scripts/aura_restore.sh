#!/usr/bin/env bash
# =============================================================================
# aura_restore.sh — Aura Free dump / restore / count (W1.4 warm-DB procedure)
# =============================================================================
# Aura Free verified quotas (plan §6, Sep 2026):
#   200k nodes / 400k rels, GCP us-central1 only, 72 h idle -> auto-pause,
#   30 d paused -> DELETED (non-recoverable), 1 on-demand snapshot.
# Procedure:
#   1. PRIMARY backup = Aura console on-demand snapshot (the single backup
#      slot). Take it before every preindex run.
#   2. This script = secondary cypher-level export + node-count receipt for
#      the <180k guard (10% buffer under the 200k Free cap).
# Dumps default OUTSIDE the repo ($HOME/nyayamitra-aura-dumps, or
# $AURA_DUMP_DIR) so a >10 MB dump can never break the repo diet (W1.2).
# Env: AURA_URI, AURA_USERNAME, AURA_PASSWORD, AURA_DATABASE (default neo4j).
# Fallback chain per var: AURA_* -> NEO4J_CLOUD_* -> NEO4J_* (legacy).
# Requires: cypher-shell on PATH (ships with Neo4j Desktop / community
# tarball). Never commits .env or keys (W1.1 owns secrets).
# Usage:
#   ./scripts/aura_restore.sh count                # prints node/rel counts
#   ./scripts/aura_restore.sh dump                 # writes $DUMP_DIR dump
#   ./scripts/aura_restore.sh restore <file.cypher>  # replays a dump
# =============================================================================
set -euo pipefail

AURA_URI="${AURA_URI:-${NEO4J_CLOUD_URI:-${NEO4J_URI:-}}}"
AURA_USERNAME="${AURA_USERNAME:-${NEO4J_CLOUD_USERNAME:-${NEO4J_USERNAME:-}}}"
AURA_PASSWORD="${AURA_PASSWORD:-${NEO4J_CLOUD_PASSWORD:-${NEO4J_PASSWORD:-}}}"
AURA_DATABASE="${AURA_DATABASE:-${NEO4J_CLOUD_DATABASE:-${NEO4J_DATABASE:-neo4j}}}"
DUMP_DIR="${AURA_DUMP_DIR:-$HOME/nyayamitra-aura-dumps}"
# 180k = 200k Free node cap minus 10% safety buffer (W1.4 verify gate).
NODE_BUDGET="${AURA_NODE_BUDGET:-180000}"

die() { echo "aura_restore: ERROR: $*" >&2; exit 1; }

need_creds() {
  [[ -n "$AURA_URI" && -n "$AURA_USERNAME" && -n "$AURA_PASSWORD" ]] \
    || die "set AURA_URI / AURA_USERNAME / AURA_PASSWORD first (never commit them)."
}

need_shell() {
  command -v cypher-shell >/dev/null 2>&1 \
    || die "cypher-shell not found — install Neo4j (Desktop/tarball) and retry."
}

# Warn if a dump path would land inside a git repo (diet guard, W1.2).
guard_path() {
  local target="$1"
  if git -C "$(dirname "$target")" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local size_hint="unknown size"
    echo "aura_restore: WARN: dump target is inside a git repo ($target, $size_hint)." >&2
    echo "aura_restore: WARN: keep dumps OUTSIDE git-tracked caps — set AURA_DUMP_DIR. Continuing anyway." >&2
  fi
}

cypher() { # $1 = query ; prints plain value
  cypher-shell -a "$AURA_URI" -u "$AURA_USERNAME" -p "$AURA_PASSWORD" \
    -d "$AURA_DATABASE" --format plain "$1" | tr -d ' \r'
}

cmd_count() {
  need_creds; need_shell
  local nodes rels
  nodes="$(cypher 'MATCH (n) RETURN count(n)')"
  rels="$(cypher 'MATCH ()-[r]->() RETURN count(r)')"
  echo "nodes=$nodes rels=$rels budget_nodes=$NODE_BUDGET"
  echo "paste-able receipt: MATCH (n) RETURN count(n)  -->  $nodes"
  if [[ "$nodes" =~ ^[0-9]+$ ]] && (( nodes >= NODE_BUDGET )); then
    die "node count $nodes >= budget $NODE_BUDGET (200k Free cap minus 10%). Index NOTHING new — prune or restore a smaller dump."
  fi
  echo "OK: node count under budget."
}

cmd_dump() {
  need_creds; need_shell
  mkdir -p "$DUMP_DIR"
  local stamp file
  stamp="$(date +%Y%m%d-%H%M)"
  file="$DUMP_DIR/aura-$stamp.cypher"
  guard_path "$file"
  echo "aura_restore: primary backup reminder — take the Aura console on-demand snapshot first (1 slot)."
  cmd_count
  {
    echo "// NyayaMitra Aura dump $stamp (db=$AURA_DATABASE)"
    echo "// Restore with: ./scripts/aura_restore.sh restore $file"
    # Portable cypher export: schema + data as CREATE statements.
    cypher-shell -a "$AURA_URI" -u "$AURA_USERNAME" -p "$AURA_PASSWORD" \
      -d "$AURA_DATABASE" --format plain \
      "CALL apoc.export.cypher.all(null, {format: 'cypher-shell', streamStatements: true, useOptimizations: {type: 'UNWIND_BATCH', unwindBatchSize: 50}}) YIELD cypherStatements UNWIND cypherStatements AS s RETURN s" \
      || die "export failed — is APOC available on Aura Free? Fallback: Aura console snapshot download."
  } > "$file"
  echo "aura_restore: wrote $file"
}

cmd_restore() {
  local file="${1:-}"
  [[ -n "$file" && -f "$file" ]] || die "usage: $0 restore <file.cypher>"
  need_creds; need_shell
  echo "aura_restore: replaying $file into $AURA_DATABASE ..."
  cypher-shell -a "$AURA_URI" -u "$AURA_USERNAME" -p "$AURA_PASSWORD" \
    -d "$AURA_DATABASE" -f "$file"
  cmd_count
}

case "${1:-}" in
  count)   cmd_count ;;
  dump)    cmd_dump ;;
  restore) cmd_restore "${2:-}" ;;
  *) die "usage: $0 {count|dump|restore <file.cypher>}" ;;
esac
