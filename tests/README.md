# Tests Directory

This directory contains test scripts for the Levante Translation Framework.

## Test Scripts

### `test_id3_metadata.py`

Tests the ID3v2 metadata functionality in `utilities.py`.

**What it does:**
1. Finds an existing MP3 file in the `audio_files` directory (or creates a minimal one)
2. Writes comprehensive ID3v2 metadata including custom fields
3. Reads the metadata back and validates all fields were preserved
4. Saves the test MP3 file and tag comparison data for inspection
5. Displays detailed results and validation status

**Features tested:**
- Standard ID3v2 tags (title, artist, album, date, genre, comment, created)
- Custom fields stored as TXXX frames (lang_code, service, voice, etc.)
- Read/write roundtrip validation
- Error handling and cleanup

**Usage:**
```bash
python tests/test_id3_metadata.py
```

**Output Files:**
- `test_audio_with_metadata.mp3` - MP3 file with complete ID3v2 metadata embedded
- `test_metadata_results.csv` - Detailed comparison of written vs read tag values

**Prerequisites:**
- `mutagen` library: `pip install mutagen`
- At least one MP3 file in the `audio_files` directory (or the script will create a minimal one)

**Sample Output:**
```
🎯 Test suite completed successfully!
✅ All tests PASSED! ID3 metadata functionality is working correctly.

📁 Files saved in tests folder:
   🎵 MP3 with metadata: test_audio_with_metadata.mp3
   📊 Tag comparison CSV: test_metadata_results.csv
```

## Test Output Files

### `test_audio_with_metadata.mp3`
MP3 audio file with comprehensive ID3v2 metadata including:
- **Standard tags**: Title, Artist, Album, Date, Genre, Comment
- **Custom tags**: Language code, TTS service, voice ID, creation timestamp, quality metrics, research notes

### `test_metadata_results.csv`
Detailed comparison table showing:
- **field**: Name of each metadata field
- **written_value**: Value that was written to the MP3 file
- **read_value**: Value that was read back from the MP3 file  
- **status**: ✅ MATCH or ❌ MISMATCH for validation

## Test Data

The script uses existing MP3 files from the `audio_files` directory when available, ensuring tests run against real audio files that the system generates.

## Adding New Tests

To add new tests:
1. Create a new `.py` file in this directory
2. Follow the naming convention: `test_<feature_name>.py` 
3. Include proper error handling and cleanup
4. Document the test in this README 