#!/usr/bin/env bash
# Thin wrapper: Scripts/Mesen2/oos_director_capture.py
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python3 "${ROOT}/Scripts/Mesen2/oos_director_capture.py" "$@"
