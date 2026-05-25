#!/usr/bin/env bash
set -euo pipefail

python generate_speech.py "German" --translation-source draft "$@"