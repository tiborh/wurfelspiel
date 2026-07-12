# Wurfelspiel

Generate playable LilyPond scores from historical musical dice-game tables. A
roll of two six-sided dice selects one precomposed measure at each of 16 table
positions, producing a waltz, contredanse, or both.

The game is often attributed to W. A. Mozart, but that attribution is disputed.
This project is named for the game, not for Mozart; the name appears only in
that historical context and in the generated score's qualified attribution.

## Requirements

- Python 3.10 or newer
- Optional rendering: [LilyPond](https://lilypond.org/) and
  [TiMidity++](https://timidity.sourceforge.net/)

The generator has no Python package dependencies.

## Prerequisite check

On Linux, check that the generator and rendering scripts have their required
tools before use:

```bash
./scripts/check_prerequisites.sh
```

The command checks Python 3.10+, LilyPond, TiMidity++, Bash, and the standard
command-line utilities used by the scripts. It exits with a nonzero status and
identifies every missing prerequisite.

> **Audio note:** LilyPond supplies the music fonts used to engrave PDFs, but
> it does not supply the instrument soundfont used for WAV playback. TiMidity++
> must have a working patch set or SoundFont configuration to synthesize WAV
> files. The prerequisite checker confirms that `timidity` is installed; it
> does not validate its SoundFont configuration.

## Usage

```bash
./generate_wurfelspiel.py
./generate_wurfelspiel.py --piece contredanse --seed 1787
./generate_wurfelspiel.py --dice 7,5,8,9,6,7,4,10,8,5,6,9,7,11,4,8
./generate_wurfelspiel.py --render
```

By default, source scores and manifests are written below `output/`. Rendering
also creates PDF, MIDI, and WAV files there. `--seed` makes randomly selected
measures reproducible; `--dice` accepts exactly 16 values from 2 through 12
and overrides random rolling. Run `./generate_wurfelspiel.py --help` for all
options.

## Rendering existing files

The generator's `--render` option is the simplest way to render scores that it
creates. For arbitrary LilyPond or MIDI files, use the standalone batch
scripts:

```bash
./scripts/render_lilypond.sh path/to/score.ly another-score.ly
./scripts/render_wav.sh output/midi/score.midi
```

`render_lilypond.sh` writes PDFs to `output/pdf/` and MIDI files to
`output/midi/`. If a source score lacks a `\midi` block, the script adds one
only to a temporary copy before rendering. `render_wav.sh` writes WAV files to
`output/wav/`. Both commands accept multiple input files and provide
`--pdf-dir`, `--midi-dir`, `--wav-dir`, and executable override options; use
`--help` for details.

## Development

Run the standard-library test suite:

```bash
python3 -m unittest discover -s tests -v
```

## Limitations

The command-line scripts support Linux only. They rely on Bash and standard
Linux utilities; macOS and Windows are not supported.

## Data provenance

`data/wurfelspiel.json` contains the dice tables and LilyPond measure
transcriptions extracted from the `DiceWaltz-1.2.1WithContredanse` package.
Its recorded upstream download location is
`http://r.newman.ch/rpi/sounding-off/dwcontredanse.zip`. See [NOTICE](NOTICE)
for the applicable provenance notice. The historical composition may be in the
public domain, but this repository makes no claim about rights in the
transcription data.

## License

The generator, tests, and project documentation are licensed under the
[MIT License](LICENSE). The musical-data provenance is described separately in
[NOTICE](NOTICE).
