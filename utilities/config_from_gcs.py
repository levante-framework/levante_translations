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
from typing import Dict, Any, Optional
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

try:
    from google.cloud import storage  # type: ignore
except Exception:
    storage = None  # Optional dependency for offline/local use


DEFAULT_BUCKET = os.environ.get('AUDIO_DEV_BUCKET', 'levante-audio-dev')
DEFAULT_OBJECT = os.environ.get('LANGUAGE_CONFIG_OBJECT', 'language_config.json')
EXPLICIT_URL = os.environ.get('LANGUAGE_CONFIG_URL')
DEFAULT_DASHBOARD_API = os.environ.get(
    'LANGUAGE_CONFIG_API_URL',
    'https://levante-audio-dashboard.vercel.app/api/language-config'
)


def _load_json_from_url(url: str) -> Optional[Dict[str, Any]]:
    try:
        with urlopen(url, timeout=20) as r:
            data = r.read().decode('utf-8', 'ignore')
        return json.loads(data)
    except (URLError, HTTPError, json.JSONDecodeError):
        return None


def _load_from_public_gcs(bucket_name: str, object_name: str) -> Optional[Dict[str, Any]]:
    # Try both GCS public URL styles
    candidates = [
        f'https://storage.googleapis.com/{bucket_name}/{object_name}',
        f'https://{bucket_name}.storage.googleapis.com/{object_name}',
    ]
    for url in candidates:
        j = _load_json_from_url(url)
        if isinstance(j, dict):
            return j
    return None


def load_from_gcs(bucket_name: str = DEFAULT_BUCKET, object_name: str = DEFAULT_OBJECT) -> Optional[Dict[str, Any]]:
    """Load config preferring freshest remotely visible source.

    Priority:
      1) LANGUAGE_CONFIG_URL (explicit override)
      2) Public GCS object (ensures what dashboard made public is used)
      3) Dashboard API JSON
      4) Authenticated GCS object (fallback)
    """
    # 1) Explicit URL override
    if EXPLICIT_URL:
        j = _load_json_from_url(EXPLICIT_URL)
        if isinstance(j, dict):
            return j

    # Collect candidates with rough staleness ordering
    candidates: list[Dict[str, Any]] = []

    # 2) Public GCS (no creds required)
    j_pub = _load_from_public_gcs(bucket_name, object_name)
    if isinstance(j_pub, dict):
        candidates.append(j_pub)

    # 3) Dashboard API
    j_api = _load_json_from_url(DEFAULT_DASHBOARD_API)
    if isinstance(j_api, dict):
        # Some responses include success flag; unwrap languages if present
        candidates.append(j_api)

    # 4) Authenticated GCS
    j_auth = None
    if storage is not None:
        creds_json = os.environ.get('GCP_SERVICE_ACCOUNT_JSON')
        if creds_json:
            try:
                credentials = json.loads(creds_json)
                client = storage.Client.from_service_account_info(credentials)
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(object_name)
                if blob.exists():
                    content = blob.download_as_text(encoding='utf-8')
                    j_auth = json.loads(content)
                    candidates.append(j_auth)
            except Exception:
                pass

    # Prefer the candidate with the newest metadata.saved_at if available
    def get_saved_at(obj: Dict[str, Any]) -> str:
        meta = obj.get('metadata')
        if isinstance(meta, dict):
            sa = meta.get('saved_at')
            if isinstance(sa, str):
                return sa
        return ''

    if candidates:
        candidates.sort(key=get_saved_at, reverse=True)
        return candidates[0]

    return None


def get_languages_config(fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Return languages config, preferring remote GCS JSON, merging with fallback for missing entries."""
    remote = load_from_gcs()
    if isinstance(remote, dict):
        # Accept either top-level mapping or nested under 'languages'
        if 'languages' in remote and isinstance(remote['languages'], dict):
            remote_map = remote['languages']
        else:
            # If the object itself looks like the languages map, use it
            looks_like_map = all(
                isinstance(v, dict) and {'lang_code', 'service', 'voice'} & set(v.keys())
                for v in remote.values()
            ) if remote else False
            remote_map = remote if looks_like_map else None

        if isinstance(remote_map, dict):
            # Merge: remote entries take precedence; fallback fills missing languages
            merged = {**fallback, **remote_map}
            return merged  # type: ignore[return-value]
    return fallback


