#!/usr/bin/env bash

# Render one or more LilyPond sources to PDF and MIDI. Scores without a
# \midi block receive one in a temporary copy so their source remains intact.
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PDF_DIR="${ROOT_DIR}/output/pdf"
MIDI_DIR="${ROOT_DIR}/output/midi"
LILYPOND_BIN="lilypond"
TEMPORARY_PATHS=()

cleanup() {
  if [[ ${#TEMPORARY_PATHS[@]} -gt 0 ]]; then
    rm -rf -- "${TEMPORARY_PATHS[@]}"
  fi
}
trap cleanup EXIT

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS] FILE.ly [FILE.ly ...]

Render LilyPond sources to PDF and MIDI.

Options:
  --pdf-dir DIR       Directory for rendered PDFs (default: ${PDF_DIR})
  --midi-dir DIR      Directory for rendered MIDI files (default: ${MIDI_DIR})
  --lilypond-bin BIN  LilyPond executable to use (default: lilypond)
  -h, --help          Show this help and exit
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

inject_midi_block() {
  local input_path="$1"
  local output_path="$2"

  awk '
    BEGIN {
      in_score = 0
      depth = 0
      has_midi = 0
      score_text = ""
    }

    /\\score[[:space:]]*\{/ && !in_score {
      in_score = 1
      depth = 0
      has_midi = 0
      score_text = $0 "\n"

      count = split($0, characters, "")
      for (character_index = 1; character_index <= count; character_index++) {
        if (characters[character_index] == "{") depth++
        else if (characters[character_index] == "}") depth--
      }
      next
    }

    in_score {
      score_text = score_text $0 "\n"

      count = split($0, characters, "")
      for (character_index = 1; character_index <= count; character_index++) {
        if (characters[character_index] == "{") depth++
        else if (characters[character_index] == "}") depth--
      }

      if ($0 ~ /\\midi/) has_midi = 1

      if (depth == 0) {
        if (!has_midi) {
          sub(/\}\n$/, "", score_text)
          score_text = score_text "  \\midi { }\n}\n"
        }
        printf "%s", score_text
        in_score = 0
        score_text = ""
      }
      next
    }

    { print }
  ' "$input_path" > "$output_path"
}

render_one() {
  local input_path="$1"
  local source_path source_dir base_name work_path build_dir output_prefix
  local midi_source=""

  [[ -f "$input_path" ]] || die "File not found: $input_path"
  [[ -r "$input_path" ]] || die "File is not readable: $input_path"
  [[ "$input_path" == *.ly ]] || die "Expected a .ly file: $input_path"

  source_path="$(realpath "$input_path")"
  source_dir="$(dirname "$source_path")"
  base_name="$(basename "${source_path%.ly}")"
  build_dir="$(mktemp -d "${TMPDIR:-/tmp}/wurfelspiel-render.XXXXXX")"
  TEMPORARY_PATHS+=("$build_dir")
  output_prefix="${build_dir}/${base_name}"

  if grep -qE '\\midi' "$source_path"; then
    work_path="$source_path"
  else
    work_path="$(mktemp "${source_dir}/.${base_name}.midi.XXXXXX.ly")"
    TEMPORARY_PATHS+=("$work_path")
    inject_midi_block "$source_path" "$work_path"
  fi

  mkdir -p "$PDF_DIR" "$MIDI_DIR"
  "$LILYPOND_BIN" "--output=${output_prefix}" "$work_path"

  [[ -f "${output_prefix}.pdf" ]] || die "LilyPond did not produce a PDF for: $input_path"
  mv "${output_prefix}.pdf" "${PDF_DIR}/${base_name}.pdf"

  for candidate in "${output_prefix}.midi" "${output_prefix}.mid"; do
    if [[ -f "$candidate" ]]; then
      midi_source="$candidate"
      break
    fi
  done
  [[ -n "$midi_source" ]] || die "LilyPond did not produce MIDI for: $input_path"
  mv "$midi_source" "${MIDI_DIR}/${base_name}.midi"

  printf 'PDF: %s\nMIDI: %s\n' \
    "${PDF_DIR}/${base_name}.pdf" \
    "${MIDI_DIR}/${base_name}.midi"
}

INPUTS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pdf-dir)
      [[ $# -ge 2 ]] || die "Option --pdf-dir requires a directory."
      PDF_DIR="$2"
      shift 2
      ;;
    --midi-dir)
      [[ $# -ge 2 ]] || die "Option --midi-dir requires a directory."
      MIDI_DIR="$2"
      shift 2
      ;;
    --lilypond-bin)
      [[ $# -ge 2 ]] || die "Option --lilypond-bin requires an executable."
      LILYPOND_BIN="$2"
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
command -v "$LILYPOND_BIN" >/dev/null 2>&1 ||
  die "LilyPond executable not found on PATH: $LILYPOND_BIN"

for input_path in "${INPUTS[@]}"; do
  render_one "$input_path"
done
