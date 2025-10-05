# Force-ID Flag Implementation Summary

## Overview
Added a new `--force-id` flag to the audio generation system that controls whether files without ID3 tags should be regenerated.

## Problem
Previously, `npm run generate:<language>` would attempt to regenerate all existing audio files that lacked ID3 tags, even if they were valid audio files. This was inefficient and could overwrite intentionally preserved files.

## Solution
Implemented a `--force-id` flag that:
- **By default (without flag)**: Skips existing audio files that don't have ID3 tags
- **With `--force-id`**: Forces regeneration of files without ID3 tags

## Changes Made

### 1. `utilities/audio_validation.py`
- Modified `needs_regeneration()` to accept a `force_id` parameter (default: `False`)
- When `force_id=False` and a file has no ID3 tags, it returns `(False, "Skipping file without ID3 tags")`
- When `force_id=True` and a file has no ID3 tags, it returns `(True, "Cannot read audio metadata - forcing regeneration")`
- Updated `validate_audio_files_for_language()` to accept and pass through `force_id`

### 2. `generate_speech.py`
- Added `force_id` parameter to `generate_audio()` function
- Added `force_id` parameter to `main()` function
- Added `--force-id` CLI argument
- Updated all calls to `needs_regeneration()` to pass the `force_id` flag
- Added informative console output about skip/force-id mode

### 3. `package.json`
Added new npm scripts for each language with the `-force-id` suffix:
- `generate:english-force-id`
- `generate:spanish-force-id`
- `generate:spanish-colombia-force-id`
- `generate:spanish-argentina-force-id`
- `generate:german-force-id`
- `generate:german-switzerland-force-id`

## Usage Examples

### Default behavior (skip files without ID3 tags)
```bash
npm run generate:spanish
# OR
python3 generate_speech.py Spanish
```

### Force regeneration of files without ID3 tags
```bash
npm run generate:spanish-force-id
# OR
python3 generate_speech.py Spanish --force-id
```

### Force regeneration of ALL files (existing behavior)
```bash
npm run generate:spanish-force
# OR
python3 generate_speech.py Spanish --force
```

### Combine flags
```bash
python3 generate_speech.py Spanish --force --force-id
```

## Console Output

### Without `--force-id` (default)
```
=== Starting Audio Generation for Levante Translations ===
Target Language: Spanish
⏭️  SKIP MODE: Will skip existing files without ID3 tags (use --force-id to regenerate)
...
✅ Audio file is up to date: audio_files/es-CO/item_123.mp3
```

### With `--force-id`
```
=== Starting Audio Generation for Levante Translations ===
Target Language: Spanish
🔄 FORCE-ID MODE: Will regenerate files without ID3 tags
...
🔄 Audio needs regeneration: Cannot read audio metadata (missing ID3 tags) - forcing regeneration
```

## Benefits
1. **Faster generation**: Skips files without ID3 tags by default, avoiding unnecessary regeneration
2. **Preserves existing files**: Won't overwrite valid audio files that lack metadata
3. **Explicit control**: Use `--force-id` when you specifically want to regenerate files without tags
4. **Backward compatible**: Existing scripts work as before, just with better default behavior

## Migration Notes
- **No breaking changes**: All existing scripts continue to work
- **New default behavior**: Files without ID3 tags are now skipped by default
- **To restore old behavior**: Use the `--force-id` flag when needed

## Improved Statistics Output

The final statistics now provide a clearer breakdown:

```
Final Statistics for German:
   Language: German
   Language Code: de
   Service: ElevenLabs
   Voice: Julia
   Items attempted this run: 0

   📊 Dataset Overview:
   Total items in dataset: 789
   Items with valid de translations: 786
   Items with empty/missing translations: 3

   💾 Audio Files on Disk:
   Total existing audio files: 788
   Expected audio files: 786
   ⚠️  Extra files on disk: 2 (possibly orphaned)
```

This makes it clear:
- **Total items**: All rows in the CSV (including those without translations)
- **Valid translations**: Items that actually have text to generate audio for
- **Empty/missing**: Items skipped because they have no translation
- **Expected vs Actual**: Shows if you have orphaned files or missing files
