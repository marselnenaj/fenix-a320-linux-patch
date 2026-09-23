#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec python3 -m fenix_patch "$@"
