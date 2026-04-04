#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
"${ROOT}/horosa-skill/scripts/package_runtime_payload.sh"
