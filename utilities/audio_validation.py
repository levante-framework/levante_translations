#!/usr/bin/env python3
"""
Audio file validation utilities for detecting when audio needs regeneration.

This module provides functions to check if audio files need to be regenerated
based on text content changes or voice changes.
"""

import os
import pandas as pd
from typing import Optional, Dict, Any, Tuple
from utilities.utilities import audio_file_path

# Import ID3 tag reading utilities
try:
    from validate_audio.id3_utils import read_expected_text_from_audio
    ID3_AVAILABLE = True
except ImportError:
    ID3_AVAILABLE = False
    print("Warning: ID3 utilities not available. Audio validation will be limited.")


def read_audio_metadata(audio_file_path: str) -> Optional[Dict[str, Any]]:
    """
    Read metadata from an audio file's ID3 tags.
    
    Args:
        audio_file_path (str): Path to the audio file
        
    Returns:
        Dict containing metadata or None if not available
    """
    if not ID3_AVAILABLE or not os.path.exists(audio_file_path):
        return None
    
    try:
        from mutagen import File
        from mutagen.id3 import ID3, TXXX
        
        audio_file = File(audio_file_path, easy=False)
        if audio_file is None or audio_file.tags is None:
            return None
        
        metadata = {}
        
        # Read standard ID3 tags
        if hasattr(audio_file.tags, 'TIT2'):
            metadata['title'] = str(audio_file.tags['TIT2'][0])
        if hasattr(audio_file.tags, 'TPE1'):
            metadata['artist'] = str(audio_file.tags['TPE1'][0])
        if hasattr(audio_file.tags, 'TALB'):
            metadata['album'] = str(audio_file.tags['TALB'][0])
        if hasattr(audio_file.tags, 'TDRC'):
            metadata['date'] = str(audio_file.tags['TDRC'][0])
        if hasattr(audio_file.tags, 'TCON'):
            metadata['genre'] = str(audio_file.tags['TCON'][0])
        
        # Read custom TXXX frames
        for frame in audio_file.tags.getall('TXXX'):
            if hasattr(frame, 'desc') and hasattr(frame, 'text'):
                key = frame.desc
                value = str(frame.text[0]) if frame.text else ""
                metadata[key] = value
        
        return metadata
        
    except Exception as e:
        print(f"Warning: Could not read metadata from {audio_file_path}: {e}")
        return None


def needs_regeneration(
    audio_file_path: str, 
    current_text: str, 
    current_voice: str, 
    current_service: str,
    current_lang_code: str,
    force_id: bool = False,
    current_model_id: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Check if an audio file needs regeneration based on text or voice changes.
    
    Args:
        audio_file_path (str): Path to the audio file
        current_text (str): Current text content
        current_voice (str): Current voice name
        current_service (str): Current TTS service (ElevenLabs, PlayHT)
        current_lang_code (str): Current language code
        force_id (bool): If True, regenerate files without ID3 tags. If False, skip them.
        current_model_id (Optional[str]): Expected model ID, when model-specific validation is needed.
        
    Returns:
        Tuple of (needs_regeneration: bool, reason: str)
    """
    if not os.path.exists(audio_file_path):
        return True, "Audio file does not exist"
    
    metadata = read_audio_metadata(audio_file_path)
    if not metadata:
        if force_id:
            return True, "Cannot read audio metadata (missing ID3 tags) - forcing regeneration"
        else:
            return False, "Skipping file without ID3 tags (use --force-id to regenerate)"
    
    # Check text content
    stored_text = metadata.get('text', '').strip()
    current_text_clean = current_text.strip()
    
    if stored_text != current_text_clean:
        return True, f"Text changed: '{stored_text[:50]}...' -> '{current_text_clean[:50]}...'"
    
    # Check voice
    stored_voice = metadata.get('voice', '').strip()
    if stored_voice != current_voice:
        return True, f"Voice changed: '{stored_voice}' -> '{current_voice}'"
    
    # Check service
    stored_service = metadata.get('service', '').strip()
    if stored_service != current_service:
        return True, f"Service changed: '{stored_service}' -> '{current_service}'"
    
    # Check language code
    stored_lang = metadata.get('lang_code', '').strip()
    if stored_lang != current_lang_code:
        return True, f"Language code changed: '{stored_lang}' -> '{current_lang_code}'"

    # Check model ID only when explicitly provided
    if current_model_id is not None:
        stored_model_id = metadata.get('model_id', '').strip()
        expected_model_id = str(current_model_id).strip()
        if stored_model_id != expected_model_id:
            return True, f"Model changed: '{stored_model_id}' -> '{expected_model_id}'"
    
    return False, "Audio file is up to date"


def validate_audio_files_for_language(
    language: str,
    language_dict: Dict[str, Any],
    translation_data: pd.DataFrame,
    audio_base_dir: str,
    force_id: bool = False
) -> pd.DataFrame:
    """
    Validate all audio files for a language and return items that need regeneration.
    
    Args:
        language (str): Language name (e.g., "Spanish")
        language_dict (Dict): Language configuration dictionary
        translation_data (pd.DataFrame): Translation data
        audio_base_dir (str): Base directory for audio files
        force_id (bool): If True, regenerate files without ID3 tags. If False, skip them.
        
    Returns:
        pd.DataFrame: Items that need audio regeneration
    """
    if language not in language_dict:
        print(f"Error: Language '{language}' not found in configuration")
        return pd.DataFrame()
    
    lang_config = language_dict[language]
    lang_code = lang_config['lang_code']
    service = lang_config['service']
    voice = lang_config['voice']
    
    print(f"🔍 Validating audio files for {language} ({lang_code})...")
    print(f"   Service: {service}")
    print(f"   Voice: {voice}")
    
    items_to_regenerate = []
    
    for index, row in translation_data.iterrows():
        # Resolve translation text from primary language column, then common aliases.
        candidates = [lang_code]
        base = (lang_code or "").split("-")[0]
        if base and base != lang_code:
            candidates.append(base)

        reverse_regional = {
            "en": "en-US",
            "de": "de-DE",
            "es": "es-CO",
            "fr": "fr-CA",
            "nl": "nl-NL",
        }
        reverse_cand = reverse_regional.get(lang_code)
        if reverse_cand:
            candidates.append(reverse_cand)

        regional_fallbacks = {
            "es-AR": "es-CO",
            "es-MX": "es-CO",
            "fr-FR": "fr-CA",
            "de-CH": "de",
        }
        regional_cand = regional_fallbacks.get(lang_code)
        if regional_cand:
            candidates.append(regional_cand)

        translation_text = None
        used_col = None
        for cand in dict.fromkeys(candidates):
            if cand not in row:
                continue
            candidate_text = row[cand]
            if pd.isna(candidate_text) or candidate_text == "":
                continue
            translation_text = candidate_text
            used_col = cand
            break

        if translation_text is None:
            print(f"Warning: No translation found for {lang_code} (or fallbacks) in row {row['item_id']}")
            continue
        if used_col and used_col != lang_code:
            print(f"Using fallback column '{used_col}' for {lang_code} in row {row['item_id']}")
        
        # Get expected audio file path
        task_name = str(row.get('labels', 'general'))
        item_id = str(row['item_id'])
        expected_audio_path = audio_file_path(task_name, item_id, audio_base_dir, lang_code)
        
        # Check if regeneration is needed
        needs_regen, reason = needs_regeneration(
            expected_audio_path,
            translation_text,
            voice,
            service,
            lang_code,
            force_id
        )
        
        if needs_regen:
            print(f"🔄 {row['item_id']}: {reason}")
            items_to_regenerate.append(row)
        else:
            print(f"✅ {row['item_id']}: Up to date")
    
    print(f"\n📊 Validation Summary for {language}:")
    print(f"   Total items: {len(translation_data)}")
    print(f"   Need regeneration: {len(items_to_regenerate)}")
    print(f"   Up to date: {len(translation_data) - len(items_to_regenerate)}")
    
    return pd.DataFrame(items_to_regenerate) if items_to_regenerate else pd.DataFrame()


if __name__ == "__main__":
    # Example usage
    print("Audio validation utilities loaded successfully!")
    print("Use validate_audio_files_for_language() to check which files need regeneration.")
