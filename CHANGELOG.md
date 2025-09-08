# Changelog

All notable changes to the Levante Audio Tools project will be documented in this file.

## [Unreleased] - 2025-09-08

### Added

#### Audio Validation System
- **Comprehensive audio validation system** in `validate_audio/` module
- **Multi-backend transcription support**: OpenAI Whisper and Google Speech Recognition
- **Advanced text similarity metrics**: Word-level, fuzzy matching, BLEU, ROUGE, WER
- **Perceptual audio quality assessment** using CLAP model
- **Web dashboard integration** with interactive validation interface
- **Language-specific validation scripts** (`validate_language.sh`)
- **Automatic GPU detection** for PyTorch-based models

#### Text Preprocessing & Similarity
- **Multi-pass word matching algorithm**: Exact → Compound → Phonetic → Fuzzy
- **German language support**: Umlaut normalization (ä→a, ö→o, ü→u, ß→ss)
- **Compound word handling**: Matches "medium-sized" ↔ "medium sized"
- **Punctuation robustness**: Handles apostrophes, hyphens, case differences
- **Common spelling variations** detection for improved matching accuracy

#### Web Dashboard Features
- **Standalone audio validation page** with resizable, draggable interface
- **Enhanced audio controls**: Play, regenerate with speed/style options (.9x, .7x speed, boost style)
- **Real-time duration comparison** between original and regenerated audio
- **Bulk save operations** to Google Cloud Storage
- **Interactive validation results** with sortable tables and filtering
- **Voice tag reading** from audio files for regeneration consistency

### Fixed

#### Audio Generation Reliability
- **SSL Certificate Errors**: Conditional TTS imports eliminate PlayHT dependency issues for ElevenLabs languages
- **Import failures**: Enhanced error handling with graceful degradation
- **Language code mapping**: Automatic conversion between locale codes (`es-CO`) and Whisper codes (`es`)

#### User Interface
- **Modal dialog issues**: Replaced with standalone validation page
- **Button placement**: Consistent validation button in dashboard toolbar
- **Cache-busting**: Reliable deployment updates without browser cache issues
- **Error feedback**: Improved user messaging and error handling

#### Performance & Reliability
- **Warning suppression**: Filtered noisy NLTK BLEU score warnings
- **Virtual environment**: Dedicated `.venv-validate-audio` for validation dependencies
- **Memory optimization**: Efficient processing of large audio datasets

### Improved

#### Text Similarity Accuracy
- **Enhanced preprocessing**: Case-insensitive, punctuation-normalized comparisons
- **Word-level analysis**: Detailed mismatch tracking and phonetic matching
- **Similarity scoring**: More accurate assessment of transcription quality
- **Validation status**: Categorical quality assessment (EXCELLENT, GOOD, ACCEPTABLE, NEEDS_REVIEW)

#### Development Workflow
- **Automated validation scripts**: Simplified language-specific validation
- **Comprehensive documentation**: Detailed README files with examples
- **Error diagnostics**: Better debugging information for troubleshooting

#### Deployment Process
- **Rsync optimization**: Avoid re-transferring identical files
- **Audio-only deployment**: Faster updates for audio file changes
- **Environment isolation**: Separate validation environment prevents conflicts

### Technical Details

#### Dependencies Added
- `openai-whisper`: State-of-the-art speech recognition
- `rapidfuzz`: Fast fuzzy string matching
- `jiwer`: Word Error Rate calculation
- `rouge`: ROUGE score computation
- `transformers`: CLAP model for audio quality assessment
- `librosa`: Audio processing utilities

#### File Structure Changes
```
validate_audio/
├── README.md              # Comprehensive documentation
├── requirements.txt       # Python dependencies
├── __init__.py           # Module initialization
├── __main__.py           # CLI entry point
├── cli.py                # Command-line interface
├── validator.py          # Main validation orchestration
├── transcriber.py        # ASR backend implementations
├── metrics.py            # Text similarity calculations
├── quality.py            # Audio quality assessment
└── id3_utils.py          # Audio metadata handling

validate_language.sh       # Automated validation script
```

#### Configuration Updates
- **Conditional TTS imports** in `generate_speech.py`
- **Language code mapping** in validation scripts
- **GPU detection** for PyTorch models
- **Web dashboard** validation integration

### Performance Metrics
- **English audio generation**: 785 files processed with 0 errors
- **Deployment efficiency**: 11.7 MiB uploaded using rsync optimization
- **Validation accuracy**: Significant improvement in similarity score reliability
- **Processing speed**: GPU acceleration for Whisper and CLAP models

---

## Previous Versions

### [Legacy] - Pre-2025-09-08
- Basic audio generation with PlayHT and ElevenLabs
- Web dashboard for translation management
- CSV-based translation workflows
- Simple audio validation (basic similarity only)

---

**Legend:**
- 🆕 **Added**: New features and capabilities
- 🔧 **Fixed**: Bug fixes and error resolution
- ⚡ **Improved**: Performance and usability enhancements
- 🗑️ **Removed**: Deprecated or removed features
- 🔒 **Security**: Security-related changes
