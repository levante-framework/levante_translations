# Validate Audio

Utilities to validate generated TTS audio by comparing ASR transcriptions to the expected text and assessing perceptual quality.

## Install

Create a virtualenv and install dependencies (heavy models are optional):

```bash
pip install -r requirements.txt
```

Notes:
- Whisper Python package is `openai-whisper` (imported as `whisper`).
- CLAP quality assessment uses `transformers`, `torch`, and `librosa`. GPU is optional.

## Usage

Single file:

```bash
python -m validate_audio path/to/audio.mp3 --language en --pretty
```

Directory or glob:

```bash
python -m validate_audio data/ --language es --pretty
python -m validate_audio "data/*.wav" --backend google --no-quality
```

If `--expected` is not provided, the tool attempts to read it from audio tags (e.g., ID3 TXXX/USLT/COMM/TIT2).

Output can be written to JSON or JSONL:

```bash
python -m validate_audio data/ --output results.jsonl
```
