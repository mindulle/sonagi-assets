#!/usr/bin/env bash
# ingest_client_assets.py 래퍼. 사용법은 --help 참고.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "${SCRIPT_DIR}/ingest_client_assets.py" "$@"
