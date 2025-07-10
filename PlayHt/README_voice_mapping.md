# PlayHT Voice Mapping System

This system provides a clean way to manage PlayHT voice IDs by mapping them to readable names, making your code more maintainable and easier to understand.

## Problem

The new PlayHT API uses hard-to-read voice IDs like:
```
s3://voice-cloning-zero-shot/d9ff78ba-d016-47f6-b0ef-dd630f59414e/female-cs/manifest.json
```

These are difficult to work with in code and make it hard to understand which voice is being used.

## Solution

The voice mapping system allows you to use readable names like:
- `Spanish_Female_Professional`
- `German_Female_Neural`
- `French_Female_Elegant`

These names are automatically mapped to the actual PlayHT voice IDs behind the scenes.

## How It Works

1. **Automatic Voice Discovery**: The system fetches all available voices from PlayHT API
2. **Intelligent Mapping**: Creates multiple mapping entries for each voice (full name, simplified name, etc.)
3. **Caching**: Caches voice mappings locally to avoid repeated API calls
4. **Fallback**: If no mapping is found, the system warns you but still tries to use the voice directly

## Usage

### Basic Usage

```python
from PlayHt import voice_mapping

# Get a PlayHT voice ID from a readable name
voice_id = voice_mapping.get_voice_id("Spanish_Female_Professional")

# Get a readable name from a voice ID
readable_name = voice_mapping.get_readable_name("s3://voice-cloning-zero-shot/...")

# List all available voices
voices = voice_mapping.list_voices()

# List voices for a specific language
spanish_voices = voice_mapping.list_voices("es-CO")
```

### Setting Up Custom Mappings

```python
from PlayHt import voice_mapping

# Add a custom mapping
voice_mapping.add_voice_mapping(
    "MySpanishVoice",
    "s3://voice-cloning-zero-shot/abc123-def456/spanish-female/manifest.json"
)

# Update voice cache from API
voice_mapping.update_voices(force=True)
```

### Integration with Existing Code

The system is already integrated into your existing PlayHT modules:

```python
# In your existing code, you can now use readable names
# and they will be automatically converted to voice IDs

# This works in playHt_tts.py
voice = "Spanish_Female_Professional"  # Instead of the long S3 URL

# This works in playHt_utilities.py
audio = get_audio("Hello world", "German_Female_Neural")
```

## Command Line Tools

Use the `manage_voices.py` script to manage your voice mappings:

```bash
# List all available voices
python PlayHt/manage_voices.py list

# List voices for a specific language
python PlayHt/manage_voices.py list --language es-CO

# Find voices matching a pattern
python PlayHt/manage_voices.py find "Salome"

# Add a custom mapping
python PlayHt/manage_voices.py add "MyVoice" "s3://voice-cloning-zero-shot/..."

# Test a voice mapping
python PlayHt/manage_voices.py test "Spanish_Female_Professional"

# Show voices from your config.py
python PlayHt/manage_voices.py config

# Force update the voice cache
python PlayHt/manage_voices.py update
```

## Configuration

### Current Configuration
Your existing `config.py` uses these voice names:
- `es-CO-SalomeNeural` (Spanish)
- `VickiNeural` (German)
- `Gabrielle` (French)
- `FennaNeural` (Dutch)

### Migration Options

**Option 1: Keep existing names**
The system will try to find mappings for your existing names automatically.

**Option 2: Use new readable names**
Update your `config.py` to use more descriptive names:

```python
language_list = {
    'Spanish': {
        'lang_code': 'es-CO', 
        'service': 'PlayHt', 
        'voice': 'Spanish_Female_Professional'
    },
    'German': {
        'lang_code': 'de-DE', 
        'service': 'PlayHt', 
        'voice': 'German_Female_Neural'
    },
    # ... etc
}
```

## Files Created

- `PlayHt/voice_mapping.py` - Core voice mapping functionality
- `PlayHt/manage_voices.py` - Command line management tool
- `PlayHt/voice_config_example.py` - Example configuration
- `voice_cache.json` - Local cache file (auto-generated)

## Automatic Features

- **Cache Management**: Voice mappings are cached for 24 hours by default
- **Fallback Handling**: If no mapping is found, the system tries to use the voice name directly
- **Multiple Mapping Types**: Each voice gets multiple mapping entries for flexibility
- **Case-Insensitive Search**: Searches work regardless of case
- **Partial Matching**: Finds voices even with partial name matches

## Getting Started

1. **Test your current setup**:
   ```bash
   python PlayHt/manage_voices.py config
   ```

2. **See what voices are available**:
   ```bash
   python PlayHt/manage_voices.py list
   ```

3. **Find voices for your languages**:
   ```bash
   python PlayHt/manage_voices.py find "Spanish"
   python PlayHt/manage_voices.py find "German"
   ```

4. **Add mappings for voices you want to use**:
   ```bash
   python PlayHt/manage_voices.py add "MySpanishVoice" "s3://voice-cloning-zero-shot/..."
   ```

5. **Test your mappings**:
   ```bash
   python PlayHt/manage_voices.py test "MySpanishVoice"
   ```

## Benefits

- **Readable Code**: Use descriptive names instead of cryptic IDs
- **Easy Maintenance**: Change voice IDs in one place
- **Automatic Updates**: Voice list stays current with PlayHT API
- **Backward Compatible**: Existing code continues to work
- **Flexible**: Multiple ways to reference the same voice
- **Cached**: Fast performance with local caching

## Troubleshooting

- **"No mapping found" warnings**: Use `manage_voices.py find` to locate the correct voice name
- **Cache issues**: Use `manage_voices.py update` to refresh the cache
- **API errors**: Check your PlayHT credentials in environment variables
- **Import errors**: Make sure you're running from the correct directory

The voice mapping system makes working with PlayHT voices much more pleasant while maintaining all the flexibility you need! 