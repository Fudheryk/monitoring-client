#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker run --rm \
  -v "${PROJECT_ROOT}:/build" \
  -w /build \
  monitoring-build \
  ./scripts/rpm_build.sh
