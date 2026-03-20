"""
ElevenLabs text-to-speech model IDs.

See: https://elevenlabs.io/docs/overview/models

- ``eleven_v3`` — Eleven v3 (expressive, 70+ languages), default for new generations.
- ``eleven_multilingual_v2`` — legacy multilingual v2 (still valid for ``--model-id``).
"""

DEFAULT_ELEVENLABS_MODEL_ID = "eleven_v3"

# Kept for explicit fallback / regression comparisons
ELEVENLABS_MULTILINGUAL_V2_MODEL_ID = "eleven_multilingual_v2"
