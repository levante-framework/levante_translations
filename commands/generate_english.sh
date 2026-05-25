#!/usr/bin/env bash
set -euo pipefail

python generate_speech.py "English (United States)" --translation-source draft "$@"