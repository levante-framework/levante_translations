#!/bin/bash

# Audio validation script for a specific language
# Usage: ./validate_language.sh <language_code>
# Example: ./validate_language.sh de

set -e  # Exit on any error

# Check if language parameter is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <language_code>"
    echo "Example: $0 de"
    echo "Example: $0 es-CO"
    echo "Example: $0 en"
    exit 1
fi

LANGUAGE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_DIR="$SCRIPT_DIR/audio_files/$LANGUAGE"

# Map language codes for Whisper compatibility
# Whisper uses ISO 639-1 codes (2-letter), not locale codes
map_language_for_whisper() {
    case "$1" in
        es-CO|es-AR|es-MX|es-ES) echo "es" ;;
        en-US|en-GB|en-CA) echo "en" ;;
        de-DE|de-CH) echo "de" ;;
        fr-FR|fr-CA) echo "fr" ;;
        pt-BR|pt-PT) echo "pt" ;;
        zh-CN|zh-TW) echo "zh" ;;
        *) echo "$1" ;;
    esac
}

WHISPER_LANGUAGE=$(map_language_for_whisper "$LANGUAGE")

echo "🔍 Validating audio for language: $LANGUAGE"
echo "🗣️  Whisper language code: $WHISPER_LANGUAGE"
echo "📁 Audio directory: $AUDIO_DIR"

# Check if audio directory exists
if [ ! -d "$AUDIO_DIR" ]; then
    echo "❌ Error: Audio directory not found: $AUDIO_DIR"
    echo "Available languages:"
    ls -1 "$SCRIPT_DIR/audio_files/" 2>/dev/null || echo "No audio_files directory found"
    exit 1
fi

# Check if there are any MP3 files
if ! ls "$AUDIO_DIR"/*.mp3 >/dev/null 2>&1; then
    echo "❌ Error: No MP3 files found in $AUDIO_DIR"
    exit 1
fi

# Count files
FILE_COUNT=$(ls "$AUDIO_DIR"/*.mp3 2>/dev/null | wc -l)
echo "📊 Found $FILE_COUNT MP3 files to validate"

# Activate virtual environment
echo "🐍 Activating virtual environment..."
if [ -f "$SCRIPT_DIR/.venv-validate-audio/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv-validate-audio/bin/activate"
    echo "✅ Virtual environment (.venv-validate-audio) activated"
elif [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
    echo "✅ Virtual environment (.venv) activated"
else
    echo "⚠️  Warning: No virtual environment found"
    echo "Proceeding with system Python..."
fi

# Change to script directory
cd "$SCRIPT_DIR"

# Run the validation
echo "🚀 Starting audio validation..."
echo "Command: python -m validate_audio \"$AUDIO_DIR/*.mp3\" --language $WHISPER_LANGUAGE --web-dashboard --model-size base --backend whisper --no-quality"
echo ""

python -m validate_audio "$AUDIO_DIR/*.mp3" \
    --language "$WHISPER_LANGUAGE" \
    --web-dashboard \
    --model-size base \
    --backend whisper \
    --no-quality

echo ""
echo "✅ Audio validation completed for language: $LANGUAGE"
echo "📄 Results saved to: web-dashboard/data/validation-$WHISPER_LANGUAGE-$(date +%b-%d-%Y).json"
