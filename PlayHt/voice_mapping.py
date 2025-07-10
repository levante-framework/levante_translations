# Voice mapping for PlayHT API
# This module provides a mapping between readable voice names and PlayHT voice IDs
# to make the code more maintainable and readable

import requests
import os
from typing import Dict, Optional, List
import json
from datetime import datetime, timedelta

class VoiceMapper:
    """
    Manages the mapping between readable voice names and PlayHT voice IDs.
    Provides caching and automatic updates of voice mappings.
    """
    
    def __init__(self, cache_duration_hours: int = 24):
        self.cache_duration_hours = cache_duration_hours
        self.cache_file = "voice_cache.json"
        self.voice_mappings = {}
        self.last_updated = None
        self._load_cache()
        
        # Default readable name mappings for commonly used voices
        self.readable_mappings = {
            # Spanish voices (updated to current API names)
            'es-CO-SalomeNeural': 'Spanish_Violeta Narrative',
            'Spanish_Female_1': 'Spanish_Violeta Narrative',
            'Spanish_Conversational': 'Spanish_Violeta Conversational',
            'SalomeNeural': 'Spanish_Violeta Narrative',
            
            # German voices (updated to current API names)
            'VickiNeural': 'German_Anke Narrative',
            'German_Female_1': 'German_Anke Narrative',
            'German_Conversational': 'German_Anke Conversational',
            
            # French voices (updated to current API names)
            'Gabrielle': 'French_Ange Narrative',
            'French_Female_1': 'French_Ange Narrative',
            'French_Conversational': 'French_Ange Conversational',
            
            # Dutch voices (no Dutch voices found in current API)
            'FennaNeural': 'FennaNeural',  # Keep as fallback
            'Dutch_Female_1': 'FennaNeural',
            'Dutch_Conversational': 'FennaNeural',
        }
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for PlayHT API requests."""
        return {
            "Authorization": os.environ["PLAY_DOT_HT_API_KEY"],
            "X-USER-ID": os.environ["PLAY_DOT_HT_USER_ID"],
            'Accept': 'application/json',
            "Content-Type": "application/json"
        }
    
    def _load_cache(self):
        """Load voice mappings from cache file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    self.voice_mappings = cache_data.get('mappings', {})
                    self.last_updated = datetime.fromisoformat(cache_data.get('last_updated', ''))
        except (json.JSONDecodeError, ValueError, KeyError):
            # If cache is corrupted or missing, start fresh
            self.voice_mappings = {}
            self.last_updated = None
    
    def _save_cache(self):
        """Save voice mappings to cache file."""
        cache_data = {
            'mappings': self.voice_mappings,
            'last_updated': datetime.now().isoformat()
        }
        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
    
    def _is_cache_expired(self) -> bool:
        """Check if the cache needs to be refreshed."""
        if not self.last_updated:
            return True
        return datetime.now() - self.last_updated > timedelta(hours=self.cache_duration_hours)
    
    def update_voice_mappings(self, force_update: bool = False):
        """
        Update voice mappings from PlayHT API.
        
        Args:
            force_update: If True, update even if cache is not expired
        """
        if not force_update and not self._is_cache_expired():
            return
            
        try:
            # Use the new v2 API endpoint
            url = "https://api.play.ht/api/v2/voices"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                voices_data = response.json()
                
                # Clear existing mappings
                self.voice_mappings = {}
                
                # Process each voice
                for voice in voices_data:
                    voice_name = voice.get('name', '')
                    # Handle both new API ('id') and old API ('value') formats
                    voice_id = voice.get('id', voice.get('value', ''))
                    
                    if voice_name and voice_id:
                        # Create multiple mapping entries for flexibility
                        self.voice_mappings[voice_name] = voice_id
                        
                        # Also create simplified names (remove spaces, special chars)
                        simplified_name = voice_name.replace(' ', '').replace('-', '').replace('_', '')
                        self.voice_mappings[simplified_name] = voice_id
                        
                        # Create language-specific mappings if language info is available
                        if 'language' in voice:
                            lang_name = f"{voice['language']}_{voice_name}"
                            self.voice_mappings[lang_name] = voice_id
                
                self.last_updated = datetime.now()
                self._save_cache()
                print(f"Updated voice mappings: {len(self.voice_mappings)} voices loaded")
                
            else:
                print(f"Failed to fetch voices: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error updating voice mappings: {e}")
    
    def get_voice_id(self, readable_name: str) -> Optional[str]:
        """
        Get the PlayHT voice ID for a readable name.
        
        Args:
            readable_name: The readable name (e.g., 'SalomeNeural', 'Spanish_Female_1')
            
        Returns:
            The PlayHT voice ID (S3 URL) or None if not found
        """
        # Update cache if needed
        self.update_voice_mappings()
        
        # Check if we have a direct mapping
        if readable_name in self.voice_mappings:
            return self.voice_mappings[readable_name]
        
        # Check if we have a readable mapping alias
        if readable_name in self.readable_mappings:
            actual_name = self.readable_mappings[readable_name]
            if actual_name in self.voice_mappings:
                return self.voice_mappings[actual_name]
        
        # Try case-insensitive search
        for name, voice_id in self.voice_mappings.items():
            if name.lower() == readable_name.lower():
                return voice_id
        
        # Try partial matching
        for name, voice_id in self.voice_mappings.items():
            if readable_name.lower() in name.lower() or name.lower() in readable_name.lower():
                return voice_id
        
        print(f"Warning: Could not find voice ID for '{readable_name}'")
        return None
    
    def get_readable_name(self, voice_id: str) -> Optional[str]:
        """
        Get a readable name for a PlayHT voice ID.
        
        Args:
            voice_id: The PlayHT voice ID (S3 URL)
            
        Returns:
            A readable name or None if not found
        """
        # Update cache if needed
        self.update_voice_mappings()
        
        # Find the name that maps to this ID
        for name, vid in self.voice_mappings.items():
            if vid == voice_id:
                return name
        
        return None
    
    def list_available_voices(self, language_filter: Optional[str] = None) -> List[Dict[str, str]]:
        """
        List all available voices with their readable names and IDs.
        
        Args:
            language_filter: Optional language code to filter by (e.g., 'es-CO')
            
        Returns:
            List of dictionaries with 'name' and 'id' keys
        """
        self.update_voice_mappings()
        
        voices = []
        for name, voice_id in self.voice_mappings.items():
            if language_filter:
                # Simple language filtering - you can enhance this
                if language_filter.lower() not in name.lower():
                    continue
            
            voices.append({
                'name': name,
                'id': voice_id
            })
        
        return voices
    
    def add_custom_mapping(self, readable_name: str, voice_id: str):
        """
        Add a custom mapping between a readable name and voice ID.
        
        Args:
            readable_name: The readable name to use
            voice_id: The actual PlayHT voice ID
        """
        self.voice_mappings[readable_name] = voice_id
        self._save_cache()
    
    def remove_mapping(self, readable_name: str):
        """
        Remove a voice mapping.
        
        Args:
            readable_name: The readable name to remove
        """
        if readable_name in self.voice_mappings:
            del self.voice_mappings[readable_name]
            self._save_cache()


# Global instance for easy access
voice_mapper = VoiceMapper()

# Convenience functions
def get_voice_id(readable_name: str) -> Optional[str]:
    """Get PlayHT voice ID for a readable name."""
    return voice_mapper.get_voice_id(readable_name)

def get_readable_name(voice_id: str) -> Optional[str]:
    """Get readable name for a PlayHT voice ID."""
    return voice_mapper.get_readable_name(voice_id)

def list_voices(language_filter: Optional[str] = None) -> List[Dict[str, str]]:
    """List available voices."""
    return voice_mapper.list_available_voices(language_filter)

def add_voice_mapping(readable_name: str, voice_id: str):
    """Add a custom voice mapping."""
    voice_mapper.add_custom_mapping(readable_name, voice_id)

def update_voices(force: bool = False):
    """Update voice mappings from PlayHT API."""
    voice_mapper.update_voice_mappings(force_update=force) 