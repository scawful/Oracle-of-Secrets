#!/usr/bin/env bash
set -euo pipefail

PIDS_FILE="/tmp/oos_agent_workflow.pids"

if [[ ! -f "$PIDS_FILE" ]]; then
  echo "No PID file found at $PIDS_FILE" >&2
  exit 1
fi

PIDS=$(tr '\n' ' ' < "$PIDS_FILE" | xargs)
if [[ -z "$PIDS" ]]; then
  echo "PID file is empty: $PIDS_FILE" >&2
  exit 1
fi

echo "Stopping: $PIDS"
kill $PIDS
