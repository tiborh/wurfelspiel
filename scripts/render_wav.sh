#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WAV_DIR="${ROOT_DIR}/output/wav"
TIMIDITY_BIN="timidity"

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS] FILE.mid|FILE.midi [FILE.mid|FILE.midi ...]

Render one or more MIDI files to WAV.

Options:
  --wav-dir DIR      Directory for rendered WAV files (default: ${WAV_DIR})
  --timidity-bin BIN TiMidity executable to use (default: timidity)
  -h, --help         Show this help and exit
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

INPUTS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --wav-dir)
      [[ $# -ge 2 ]] || die "Option --wav-dir requires a directory."
      WAV_DIR="$2"
      shift 2
      ;;
    --timidity-bin)
      [[ $# -ge 2 ]] || die "Option --timidity-bin requires an executable."
      TIMIDITY_BIN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      die "Unknown option: $1"
      ;;
    *)
      INPUTS+=("$1")
      shift
      ;;
  esac
done

[[ ${#INPUTS[@]} -gt 0 ]] || {
  usage >&2
  exit 2
}
command -v "$TIMIDITY_BIN" >/dev/null 2>&1 ||
  die "TiMidity executable not found on PATH: $TIMIDITY_BIN"

mkdir -p "$WAV_DIR"
for input_path in "${INPUTS[@]}"; do
  [[ -f "$input_path" ]] || die "File not found: $input_path"
  [[ -r "$input_path" ]] || die "File is not readable: $input_path"
  [[ "$input_path" == *.mid || "$input_path" == *.midi ]] ||
    die "Expected a .mid or .midi file: $input_path"

  base_name="$(basename "$input_path")"
  base_name="${base_name%.midi}"
  base_name="${base_name%.mid}"
  output_path="${WAV_DIR}/${base_name}.wav"

  "$TIMIDITY_BIN" "$input_path" -Ow -o "$output_path"
  printf 'WAV: %s\n' "$output_path"
done
