from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "generate_wurfelspiel.py"
SPEC = importlib.util.spec_from_file_location("generator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class DiceParsingTests(unittest.TestCase):
    def test_generator_uses_python_310_compatible_syntax(self) -> None:
        ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT), feature_version=(3, 10))

    def test_parse_dice_requires_sixteen_valid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Exactly 16"):
            generator.parse_dice("2,3")
        with self.assertRaisesRegex(ValueError, "between 2 and 12"):
            generator.parse_dice(",".join(["13"] * 16))

    def test_default_name_is_reproducible_and_neutral(self) -> None:
        dice = [7, 5, 8, 9, 6, 7, 4, 10, 8, 5, 6, 9, 7, 11, 4, 8]
        fingerprint = hashlib.sha1(",".join(map(str, dice)).encode("ascii")).hexdigest()[:10]
        self.assertEqual(
            generator.default_name(None, "waltz", dice, False),
            f"wurfelspiel-waltz-{fingerprint}",
        )


class CommandLineTests(unittest.TestCase):
    def test_batch_script_help_and_syntax(self) -> None:
        for script_name in ("check_prerequisites.sh", "render_lilypond.sh", "render_wav.sh"):
            script = ROOT / "scripts" / script_name
            subprocess.run(["bash", "-n", str(script)], check=True)
            result = subprocess.run(
                [str(script), "--help"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Usage:", result.stdout)

    def test_generation_writes_matching_score_and_manifest(self) -> None:
        dice = [7, 5, 8, 9, 6, 7, 4, 10, 8, 5, 6, 9, 7, 11, 4, 8]
        dice_text = ",".join(map(str, dice))
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            lilypond_directory = temporary_path / "lilypond"
            manifest_directory = temporary_path / "manifests"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--piece",
                    "waltz",
                    "--dice",
                    dice_text,
                    "--ly-dir",
                    str(lilypond_directory),
                    "--manifest-dir",
                    str(manifest_directory),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            lilypond_file = next(lilypond_directory.glob("wurfelspiel-waltz-*.ly"))
            manifest_file = next(manifest_directory.glob("wurfelspiel-waltz-*.json"))
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            data = json.loads((ROOT / "data" / "wurfelspiel.json").read_text(encoding="utf-8"))

            self.assertIn("Historically attributed to W. A. Mozart", lilypond_file.read_text(encoding="utf-8"))
            self.assertEqual(manifest["dice"], dice)
            self.assertEqual(
                manifest["selected_measures"],
                generator.choose_measures(data["waltz"]["table"], dice),
            )
            self.assertIn(str(lilypond_file), result.stdout)
            self.assertIn(str(manifest_file), result.stdout)
