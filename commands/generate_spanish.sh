#!/usr/bin/env bash
set -euo pipefail

python generate_speech.py "Spanish (Colombia)" --translation-source draft "$@"