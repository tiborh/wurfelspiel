#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "wurfelspiel.json"
LILYPOND_VERSION = "2.26.0"
DEFAULT_PAPER_SIZE = "a4"
PIECE_NAMES = ("waltz", "contredanse")


def load_data() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a LilyPond score from historical Würfelspiel tables."
    )
    parser.add_argument(
        "--piece",
        choices=("waltz", "contredanse", "both"),
        default="waltz",
        help="Which movement to generate.",
    )
    parser.add_argument(
        "--dice-mode",
        choices=("two-dice", "uniform"),
        default="two-dice",
        help="Use either two six-sided dice or a flat 2..12 draw.",
    )
    parser.add_argument(
        "--dice",
        help="Comma-separated list of 16 values between 2 and 12. Overrides random rolling.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional RNG seed for reproducible output.",
    )
    parser.add_argument(
        "--tempo",
        type=int,
        help="Tempo in eighth notes per minute.",
    )
    parser.add_argument(
        "--name",
        help="Base output name. If omitted, a reproducible name derived from the dice sequence is used.",
    )
    parser.add_argument(
        "--paper-size",
        default=DEFAULT_PAPER_SIZE,
        help="LilyPond paper size, for example a4 or letter.",
    )
    parser.add_argument(
        "--landscape",
        action="store_true",
        help="Render the score in landscape orientation.",
    )
    parser.add_argument(
        "--ly-dir",
        default=str(ROOT / "output" / "lilypond"),
        help="Directory for generated LilyPond files.",
    )
    parser.add_argument(
        "--manifest-dir",
        default=str(ROOT / "output" / "manifests"),
        help="Directory for metadata files.",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Also render PDF, MIDI and WAV files.",
    )
    parser.add_argument(
        "--keep-timestamp",
        action="store_true",
        help="Append a timestamp to automatically generated names.",
    )
    parser.add_argument(
        "--pdf-dir",
        default=str(ROOT / "output" / "pdf"),
        help="Directory for rendered PDF files.",
    )
    parser.add_argument(
        "--midi-dir",
        default=str(ROOT / "output" / "midi"),
        help="Directory for rendered MIDI files.",
    )
    parser.add_argument(
        "--wav-dir",
        default=str(ROOT / "output" / "wav"),
        help="Directory for rendered WAV files.",
    )
    parser.add_argument(
        "--lilypond-bin",
        default="lilypond",
        help="LilyPond executable to use when --render is enabled.",
    )
    parser.add_argument(
        "--timidity-bin",
        default="timidity",
        help="TiMidity executable to use when --render is enabled.",
    )
    return parser.parse_args()


def parse_dice(raw: str) -> list[int]:
    values = [segment.strip() for segment in raw.split(",")]
    dice = [int(value) for value in values if value]
    if len(dice) != 16:
        raise ValueError("Exactly 16 dice values are required.")
    for die in dice:
        if die < 2 or die > 12:
            raise ValueError("Dice values must be between 2 and 12.")
    return dice


def roll_dice(rng: random.Random, mode: str) -> list[int]:
    if mode == "uniform":
        return [rng.randint(2, 12) for _ in range(16)]
    return [rng.randint(1, 6) + rng.randint(1, 6) for _ in range(16)]


def choose_measures(table: list[list[int]], dice: list[int]) -> list[int]:
    return [table[die - 2][column] for column, die in enumerate(dice)]


def piece_slug(piece_name: str) -> str:
    return "contredanse" if piece_name == "contredanse" else "waltz"


def dice_fingerprint(dice: list[int]) -> str:
    payload = ",".join(str(die) for die in dice).encode("ascii")
    return hashlib.sha1(payload).hexdigest()[:10]


def default_name(base_name: str | None, piece_name: str, dice: list[int], keep_timestamp: bool) -> str:
    if base_name:
        return f"{base_name}-{piece_slug(piece_name)}"
    parts = ["wurfelspiel", piece_slug(piece_name), dice_fingerprint(dice)]
    if keep_timestamp:
        parts.append(datetime.now().strftime("%Y%m%d-%H%M%S"))
    return "-".join(parts)


def lilypond_header(source_package: str, piece: dict, dice: list[int], measures: list[int], args: argparse.Namespace) -> str:
    title = piece["title"]
    subtitle = "Musikalisches Würfelspiel"
    orientation = " 'landscape" if args.landscape else ""
    lines = [
        f'\\version "{LILYPOND_VERSION}"',
        "\\pointAndClickOff",
        "",
        f"% Source package: {source_package}",
        f"% Dice rolls: {', '.join(str(die) for die in dice)}",
        f"% Selected measures: {', '.join(str(measure) for measure in measures)}",
        "",
        "\\header {",
        f'  title = "{title}"',
        f'  subtitle = "{subtitle}"',
        '  composer = "Historically attributed to W. A. Mozart"',
        "}",
        "",
        "\\paper {",
        f'  #(set-paper-size "{args.paper_size}"{orientation})',
        "}",
        "",
    ]
    return "\n".join(lines)


def clean_measure_text(raw: str) -> str:
    return raw.strip().rstrip("|").rstrip()


def staff_block(
    voice_name: str,
    clef: str,
    music_map: dict[str, str],
    measures: list[int],
    alternative_measure: int,
    piece: dict,
    tempo: int,
) -> str:
    lines = [
        f'    \\new Staff = "{voice_name}" {{',
        f"      \\clef {clef}",
        f'      \\time {piece["time_signature"]}',
        "      \\key c \\major",
    ]
    if voice_name == "RH":
        lines.append(f'      \\tempo {piece["tempo_unit"]} = {tempo}')
    lines.extend(
        [
            "      \\repeat volta 2 {",
            *[f'        {clean_measure_text(music_map[str(measure)])} |' for measure in measures[:7]],
            "      }",
            "      \\alternative {",
            f'        {{ {clean_measure_text(music_map[str(alternative_measure)])} | }}',
            "      }",
            "",
            "      \\repeat volta 2 {",
            *[f'        {clean_measure_text(music_map[str(measure)])} |' for measure in measures[8:]],
            "      }",
            "    }",
        ]
    )
    return "\n".join(lines)


def effective_tempo(piece: dict, args: argparse.Namespace) -> int:
    return args.tempo if args.tempo is not None else piece["default_tempo"]


def build_lilypond(source_package: str, piece: dict, dice: list[int], measures: list[int], args: argparse.Namespace) -> str:
    tempo = effective_tempo(piece, args)
    lines = [
        lilypond_header(source_package, piece, dice, measures, args),
        f'{piece["title"].replace(" ", "")}Music =',
        "  \\new PianoStaff <<",
        staff_block(
            "RH",
            "treble",
            piece["right_hand"],
            measures,
            piece["alternative_measure"],
            piece,
            tempo,
        ),
        "",
        staff_block(
            "LH",
            "bass",
            piece["left_hand"],
            measures,
            piece["alternative_measure"],
            piece,
            tempo,
        ),
        "  >>",
        "",
        "\\score {",
        f'  \\{piece["title"].replace(" ", "")}Music',
        "  \\layout { }",
        "}",
        "",
        "\\score {",
        "  \\unfoldRepeats <<",
        f'    \\{piece["title"].replace(" ", "")}Music',
        "  >>",
        "  \\midi { }",
        "}",
        "",
    ]
    return "\n".join(lines)


def ensure_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required executable not found on PATH: {name}")


def render_outputs(
    lilypond_path: Path,
    base_name: str,
    args: argparse.Namespace,
) -> dict[str, Path]:
    ensure_tool(args.lilypond_bin)
    ensure_tool(args.timidity_bin)

    pdf_dir = Path(args.pdf_dir)
    midi_dir = Path(args.midi_dir)
    wav_dir = Path(args.wav_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    midi_dir.mkdir(parents=True, exist_ok=True)
    wav_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="wurfelspiel_") as build_dir_raw:
        build_dir = Path(build_dir_raw)
        output_prefix = build_dir / base_name
        subprocess.run(
            [args.lilypond_bin, f"--output={output_prefix}", str(lilypond_path)],
            check=True,
        )

        pdf_source = output_prefix.with_suffix(".pdf")
        midi_source = output_prefix.with_suffix(".midi")
        if not midi_source.exists():
            midi_source = output_prefix.with_suffix(".mid")
        if not pdf_source.exists() or not midi_source.exists():
            raise RuntimeError("LilyPond did not produce both PDF and MIDI output.")

        pdf_target = pdf_dir / pdf_source.name
        midi_target = midi_dir / midi_source.name
        shutil.copy2(pdf_source, pdf_target)
        shutil.copy2(midi_source, midi_target)

        wav_target = wav_dir / f"{base_name}.wav"
        subprocess.run(
            [args.timidity_bin, str(midi_target), "-Ow", "-o", str(wav_target)],
            check=True,
        )

    return {
        "pdf": pdf_target,
        "midi": midi_target,
        "wav": wav_target,
    }


def write_manifest(
    manifest_path: Path,
    piece_name: str,
    piece: dict,
    dice: list[int],
    measures: list[int],
    seed: int | None,
    args: argparse.Namespace,
    lilypond_path: Path,
    rendered: dict[str, Path] | None,
) -> None:
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "piece": piece_name,
        "piece_title": piece_name.title(),
        "dice_mode": args.dice_mode if args.dice is None else "manual",
        "dice": dice,
        "dice_fingerprint": dice_fingerprint(dice),
        "selected_measures": measures,
        "seed": seed,
        "tempo": effective_tempo(piece, args),
        "paper_size": args.paper_size,
        "landscape": args.landscape,
        "lilypond_file": str(lilypond_path),
    }
    if rendered:
        manifest["rendered_files"] = {key: str(value) for key, value in rendered.items()}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def generate_piece(
    dataset: dict,
    piece_name: str,
    dice: list[int],
    args: argparse.Namespace,
) -> tuple[Path, Path, dict[str, Path] | None]:
    piece = dataset[piece_name]
    measures = choose_measures(piece["table"], dice)

    base_name = default_name(args.name, piece_name, dice, args.keep_timestamp)
    ly_dir = Path(args.ly_dir)
    manifest_dir = Path(args.manifest_dir)
    ly_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    lilypond_path = ly_dir / f"{base_name}.ly"
    manifest_path = manifest_dir / f"{base_name}.json"

    lilypond_path.write_text(
        build_lilypond(dataset["source"]["package"], piece, dice, measures, args),
        encoding="utf-8",
    )

    rendered = render_outputs(lilypond_path, base_name, args) if args.render else None
    write_manifest(manifest_path, piece_name, piece, dice, measures, args.seed, args, lilypond_path, rendered)
    return lilypond_path, manifest_path, rendered


def main() -> int:
    args = parse_args()
    dataset = load_data()

    if args.dice:
        try:
            dice = parse_dice(args.dice)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    else:
        rng = random.Random(args.seed)
        dice = roll_dice(rng, args.dice_mode)

    pieces = PIECE_NAMES if args.piece == "both" else (args.piece,)

    for piece_name in pieces:
        lilypond_path, manifest_path, rendered = generate_piece(dataset, piece_name, dice, args)
        print(f"{piece_name}: {lilypond_path}")
        print(f"manifest: {manifest_path}")
        if rendered:
            print(f"pdf: {rendered['pdf']}")
            print(f"midi: {rendered['midi']}")
            print(f"wav: {rendered['wav']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
