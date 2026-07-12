#!/usr/bin/env bash

set -u -o pipefail

failures=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [--help]

Check Linux prerequisites for the Wurfelspiel generator and rendering scripts.
EOF
}

pass() {
  printf 'PASS  %s\n' "$*"
}

fail() {
  printf 'FAIL  %s\n' "$*" >&2
  failures=$((failures + 1))
}

check_command() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    pass "$name: $(command -v "$name")"
  else
    fail "$name is not available on PATH."
  fi
}

case "${1:-}" in
  "")
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

if [[ "$(uname -s)" == "Linux" ]]; then
  pass "Linux: $(uname -r)"
else
  fail "This project supports Linux only; detected: $(uname -s)"
fi

if (( BASH_VERSINFO[0] >= 4 )); then
  pass "Bash: ${BASH_VERSION}"
else
  fail "Bash 4 or newer is required; detected: ${BASH_VERSION}"
fi

if command -v python3 >/dev/null 2>&1; then
  python_version="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  if python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    pass "Python: ${python_version}"
  else
    fail "Python 3.10 or newer is required; detected: ${python_version}"
  fi
else
  fail "python3 is not available on PATH."
fi

for command_name in awk grep mktemp realpath; do
  check_command "$command_name"
done

for command_name in lilypond timidity; do
  check_command "$command_name"
done

if (( failures > 0 )); then
  printf '\n%d prerequisite check(s) failed.\n' "$failures" >&2
  exit 1
fi

printf '\nAll prerequisites are available.\n'
