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

### `test_complete_audio_workflow.py`

**NEW** - Comprehensive test of the complete audio generation workflow.

**What it does:**
1. Creates sample translation data (3 items in 5 languages)
2. Simulates the complete TTS workflow: CSV → Audio Generation → ID3 Tagging
3. Tests multiple language/service combinations (English/PlayHT, Spanish/ElevenLabs, German/PlayHT)
4. Uses real MP3 files as templates to ensure valid audio format
5. Validates that `save_audio()` function works correctly with metadata
6. Creates detailed CSV report of all test results

**Features tested:**
- Complete pipeline from translation data to tagged audio files
- Multiple language codes (en, es-CO, de)
- Multiple TTS services (PlayHT, ElevenLabs simulation)
- Audio file generation and directory structure creation
- ID3v2 metadata embedding for all standard and custom fields
- Comprehensive validation and reporting

**Usage:**
```bash
python tests/test_complete_audio_workflow.py
```

**Output Files:**
- `test_audio_files/` - Directory tree with generated MP3 files organized by task/language
- `complete_workflow_results.csv` - Detailed test results for each generated file

**Sample Results:**
```
📈 Workflow Test Summary:
   Total items processed: 9
   Audio files created: 9
   Average metadata fields per file: 10.0
   
📁 Generated test files:
   🎵 test_audio_files/general/en/shared/test_welcome_message.mp3 (8496 bytes)
   🎵 test_audio_files/math/es-CO/shared/test_instructions.mp3 (8515 bytes)
   📊 complete_workflow_results.csv
```

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

### `test_audio_files/` Directory Structure
Generated audio files organized in the standard Levante directory structure:
```
test_audio_files/
├── general/
│   ├── en/shared/test_welcome_message.mp3
│   ├── es-CO/shared/test_welcome_message.mp3
│   └── de/shared/test_welcome_message.mp3
└── math/
    ├── en/shared/test_instructions.mp3
    ├── es-CO/shared/test_instructions.mp3
    └── de/shared/test_instructions.mp3
```

### `complete_workflow_results.csv`
Comprehensive test results including:
- **item_id, language, lang_code, service, voice**: Test parameters
- **text**: Original translation text used for generation
- **file_path**: Path to generated MP3 file
- **file_exists**: Whether the file was successfully created
- **metadata_fields_count**: Number of ID3 fields embedded
- **validation_passed**: Overall success status
- **title_match, artist_match, service_match, etc.**: Individual field validation results
- **created_timestamp**: When the file was generated
- **generation_date**: Test execution timestamp

## Test Data

The scripts use existing MP3 files from the `audio_files` directory when available, ensuring tests run against real audio files that the system generates. The comprehensive workflow test creates realistic translation data in multiple languages.

## Adding New Tests

To add new tests:
1. Create a new `.py` file in this directory
2. Follow the naming convention: `test_<feature_name>.py` 
3. Include proper error handling and cleanup
4. Document the test in this README 