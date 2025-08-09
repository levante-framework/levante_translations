"""
Shared language configuration loader.

Loads language configuration JSON from GCS bucket (levante-audio-dev by default)
with a local fallback to the existing config structure in utilities/config.py.

Environment options:
- GCP_SERVICE_ACCOUNT_JSON: JSON credentials string for service account
- AUDIO_DEV_BUCKET: Bucket name (default: levante-audio-dev)
- LANGUAGE_CONFIG_OBJECT: Object name (default: language_config.json)
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any

try:
    from google.cloud import storage  # type: ignore
except Exception:
    storage = None  # Optional dependency for offline/local use


DEFAULT_BUCKET = os.environ.get('AUDIO_DEV_BUCKET', 'levante-audio-dev')
DEFAULT_OBJECT = os.environ.get('LANGUAGE_CONFIG_OBJECT', 'language_config.json')


def load_from_gcs(bucket_name: str = DEFAULT_BUCKET, object_name: str = DEFAULT_OBJECT) -> Dict[str, Any] | None:
    if storage is None:
        return None

    creds_json = os.environ.get('GCP_SERVICE_ACCOUNT_JSON')
    if not creds_json:
        return None

    try:
        credentials = json.loads(creds_json)
    except json.JSONDecodeError:
        return None

    client = storage.Client.from_service_account_info(credentials)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    if not blob.exists():
        return None
    content = blob.download_as_text(encoding='utf-8')
    return json.loads(content)


def get_languages_config(fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Return languages config, preferring remote GCS JSON, falling back to provided structure."""
    remote = load_from_gcs()
    if isinstance(remote, dict) and 'languages' in remote and isinstance(remote['languages'], dict):
        return remote['languages']
    return fallback


