#!/usr/bin/env bash
# Sandbox runner: create a git worktree for safe bisect / module isolation / testing.
#
# Create:  ./scripts/sandbox_runner.sh create [--name <name>]
# Run:    ./scripts/sandbox_runner.sh run [--name <name>] -- <command> [args...]
# Destroy: ./scripts/sandbox_runner.sh destroy [--name <name>]
#
# Default name is "sandbox" (worktree at ../oracle-of-secrets-sandbox).
# With --name foo, worktree is at ../oracle-of-secrets-foo.
# The sandbox shares the same Roms/ directory as the main repo (same repo root).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SANDBOX_NAME="${OOS_SANDBOX_NAME:-sandbox}"
SHARE_ROMS=0

usage() {
  echo "Usage: $(basename "$0") create [--name <name>] [--share-roms]" >&2
  echo "       $(basename "$0") run [--name <name>] -- <command> [args...]" >&2
  echo "       $(basename "$0") destroy [--name <name>]" >&2
  echo "Default name: sandbox (worktree at ../oracle-of-secrets-sandbox)" >&2
  echo "create --share-roms: symlink sandbox Roms/ to main repo Roms/" >&2
  exit 1
}

get_sandbox_path() {
  local name="$1"
  echo "$(cd "$REPO_ROOT/.." && pwd)/oracle-of-secrets-${name}"
}

cmd_create() {
  local path
  path="$(get_sandbox_path "$SANDBOX_NAME")"
  if [[ -d "$path" ]]; then
    echo "Sandbox already exists: $path" >&2
    echo "Use 'destroy' first or --name <other>." >&2
    return 1
  fi
  git -C "$REPO_ROOT" worktree add "$path" HEAD
  if [[ "$SHARE_ROMS" -eq 1 ]]; then
    rm -rf "${path}/Roms"
    ln -s "$REPO_ROOT/Roms" "${path}/Roms"
    echo "Linked sandbox Roms/ to main repo Roms/"
  fi
  echo "Created sandbox at: $path"
  echo "Run: $0 run --name $SANDBOX_NAME -- <command>"
  echo "Destroy: $0 destroy --name $SANDBOX_NAME"
}

cmd_run() {
  local path
  path="$(get_sandbox_path "$SANDBOX_NAME")"
  if [[ ! -d "$path" ]]; then
    echo "Sandbox not found: $path" >&2
    echo "Run: $0 create --name $SANDBOX_NAME" >&2
    return 1
  fi
  if [[ $# -eq 0 ]]; then
    echo "run requires a command after --" >&2
    usage
  fi
  (cd "$path" && exec "$@")
}

cmd_destroy() {
  local path
  path="$(get_sandbox_path "$SANDBOX_NAME")"
  if [[ ! -d "$path" ]]; then
    echo "Sandbox not found: $path" >&2
    return 0
  fi
  git -C "$REPO_ROOT" worktree remove "$path" --force
  echo "Removed sandbox: $path"
}

# Parse --name and --share-roms before subcommand
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      if [[ -n "${2:-}" ]]; then
        SANDBOX_NAME="$2"
        shift 2
      else
        echo "Missing value for --name" >&2
        usage
      fi
      ;;
    --share-roms)
      SHARE_ROMS=1
      shift
      ;;
    create)
      shift
      cmd_create
      exit $?
      ;;
    run)
      shift
      # Consume remaining --name if present
      while [[ $# -gt 0 && "$1" != "--" ]]; do
        if [[ "$1" == "--name" && -n "${2:-}" ]]; then
          SANDBOX_NAME="$2"
          shift 2
        else
          shift
        fi
      done
      [[ $# -gt 0 && "$1" == "--" ]] && shift
      cmd_run "$@"
      exit $?
      ;;
    destroy)
      shift
      cmd_destroy
      exit $?
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      ;;
    *)
      echo "Unknown command: $1" >&2
      usage
      ;;
  esac
done

usage
