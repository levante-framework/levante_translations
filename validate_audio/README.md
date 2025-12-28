# Audio Validation System

Advanced utilities to validate generated TTS audio by comparing ASR transcriptions to expected text using multiple similarity metrics and perceptual quality assessment.

## Features

### 🎯 **Multi-Backend Transcription**
- **OpenAI Whisper** (`openai-whisper`) - State-of-the-art speech recognition
- **Google Speech Recognition** (`speech_recognition`) - Cloud-based ASR
- **Automatic GPU detection** for PyTorch-based models (Whisper, CLAP)

### 📊 **Advanced Text Similarity Metrics**
- **Word-level similarity** with compound word matching
- **Fuzzy string matching** using `rapidfuzz`
- **BLEU scores** for n-gram overlap assessment
- **ROUGE scores** for summarization-quality metrics
- **Word Error Rate (WER)** calculation
- **Phonetic normalization** for better matching

### 🔧 **Robust Text Preprocessing**
- **Case-insensitive** comparisons
- **Punctuation normalization** (handles apostrophes, hyphens, etc.)
- **German-specific** umlaut handling (ä→a, ö→o, ü→u, ß→ss)
- **Compound word** splitting and matching
- **Common spelling variations** detection

### 🎵 **Audio Quality Assessment**
- **CLAP model** for perceptual audio quality
- **Duration analysis** and validation
- **ID3 tag reading** for expected text extraction

### 🌐 **Web Dashboard Integration**
- **JSON export** with web-compatible format
- **Automatic file naming** (`validation-{language}-{Month-Day-Year}.json`)
- **Interactive UI** for viewing, regenerating, and managing audio
- **ElevenLabs integration** for audio regeneration with speed/style options

### 📈 **Comprehensive Validation Status**
- **EXCELLENT** (>0.95 similarity): Perfect match
- **GOOD** (>0.85 similarity): Minor differences
- **ACCEPTABLE** (>0.70 similarity): Some discrepancies
- **NEEDS_REVIEW** (<0.70 similarity): Significant issues

## Installation

### Option 1: Dedicated Virtual Environment (Recommended)
```bash
# Create dedicated environment for audio validation
python -m venv .venv-validate-audio
source .venv-validate-audio/bin/activate  # Linux/Mac
# or
.venv-validate-audio\Scripts\activate     # Windows

# Install dependencies
pip install -r validate_audio/requirements.txt
```

### Option 2: Existing Environment
```bash
# Install in existing environment
pip install -r validate_audio/requirements.txt
```

### GPU Support (Optional)
For faster processing with CUDA-enabled GPUs:
```bash
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Usage

### Basic Usage

**Single file validation:**
```bash
python -m validate_audio path/to/audio.mp3 --language en --pretty
```

**Directory or glob pattern:**
```bash
python -m validate_audio "audio_files/en/*.mp3" --language en --web-dashboard
python -m validate_audio audio_files/es-CO/ --language es --backend whisper
```

### Advanced Options

**Full validation with all metrics:**
```bash
python -m validate_audio "audio_files/de/*.mp3" \
    --language de \
    --web-dashboard \
    --model_size large \
    --backend whisper \
    --pretty
```

**High-performance batch processing:**
```bash
python -m validate_audio "audio_files/en/*.mp3" \
    --language en \
    --web-dashboard \
    --model_size base \
    --backend whisper \
    --no-quality  # Skip CLAP analysis for speed
```

### Language-Specific Validation Scripts

Use the convenient shell script for automated validation:

```bash
# Validate German audio
./validate_language.sh de

# Validate Spanish audio (maps es-CO to whisper-compatible 'es')
./validate_language.sh es-CO

# Validate English audio
./validate_language.sh en
```

This script automatically:
- Maps language codes for Whisper compatibility
- Activates the appropriate virtual environment
- Saves results to `web-dashboard/data/` with proper naming
- Handles error cases gracefully

### Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--language` | Whisper language code (2-letter) | `--language en` |
| `--backend` | ASR backend (`whisper`, `google`) | `--backend whisper` |
| `--model_size` | Whisper model size | `--model_size base` |
| `--web-dashboard` | Export for web dashboard | `--web-dashboard` |
| `--pretty` | Human-readable JSON output | `--pretty` |
| `--no-quality` | Skip audio quality assessment | `--no-quality` |
| `--expected` | Override expected text | `--expected "Hello world"` |
| `--output` | Custom output file | `--output results.json` |

## Output Format

### Individual Validation Result
```json
{
  "filename": "vocab-item-001.mp3",
  "language": "en",
  "expected_text": "Hello world",
  "transcribed_text": "hello world",
  "elevenlabs_validation": {
    "similarity_score": 0.95,
    "word_level_similarity": 1.0,
    "character_similarity": 0.98,
    "validation_status": "EXCELLENT",
    "perfect_matches": [["Hello", "hello", 1.0], ["world", "world", 1.0]],
    "phonetic_matches": [],
    "mismatched_words": [],
    "recommendations": ["Excellent match - no action needed"]
  },
  "basic_metrics": {
    "similarity_ratio": 0.95,
    "wer": 0.0,
    "total_words_original": 2,
    "total_words_transcribed": 2
  },
  "comprehensive_metrics": {
    "fuzzy_similarity": 0.95,
    "rouge_1_f": 1.0,
    "rouge_2_f": 1.0,
    "rouge_l_f": 1.0,
    "bleu_score": 1.0
  },
  "quality": {
    "clap_score": 0.85,
    "duration_seconds": 1.2
  }
}
```

### Web Dashboard Export
When using `--web-dashboard`, results are saved to:
```
web-dashboard/data/validation-{language}-{Month-Day-Year}.json
```

Example: `web-dashboard/data/validation-en-Sep-08-2025.json`

By default the CLI also syncs every generated report to the dashboard data bucket
(`gs://$DASHBOARD_DATA_BUCKET/$VALIDATION_DATA_PREFIX`) via `gsutil rsync`, so
Pitwall and the deployed dashboard can read the new file immediately. Disable
this behavior with `--skip-publish` if you need to keep a local-only draft.

## Integration with Web Dashboard

The validation results integrate seamlessly with the web dashboard:

1. **Automatic Import**: Results are automatically available in the validation UI
2. **Interactive Review**: Sort, filter, and analyze results
3. **Audio Playback**: Play original audio files
4. **Regeneration**: Regenerate audio with ElevenLabs using different speed/style options
5. **Bulk Operations**: Save improved audio back to Google Cloud Storage

### Accessing Validation Results
1. Open the web dashboard
2. Click the "Audio Validation" button in the validation bar
3. Select your validation results file from the dropdown
4. Review, regenerate, and manage audio files

## Troubleshooting

### Common Issues

**SSL Certificate Errors (PlayHT)**
- **Fixed**: Conditional imports now only load required TTS services
- English uses ElevenLabs and won't import PlayHT dependencies

**Language Code Mapping**
- Use 2-letter ISO codes for Whisper: `en`, `es`, `de`, `fr`
- Locale codes like `es-CO` are automatically mapped to `es`

**GPU Not Detected**
```bash
# Check if CUDA is available
python -c "import torch; print(torch.cuda.is_available())"
```

**Virtual Environment Issues**
- Ensure you're using the correct environment: `.venv-validate-audio`
- Use `which python` to verify the active environment

### Performance Tips

1. **Use Base Model**: `--model_size base` for faster processing
2. **Skip Quality**: `--no-quality` to disable CLAP analysis
3. **GPU Acceleration**: Ensure CUDA is properly installed
4. **Batch Processing**: Process multiple files in single command

## Recent Improvements

### Text Similarity Enhancements
- **Multi-pass word matching**: Exact → Compound → Phonetic → Fuzzy
- **German language support**: Umlaut normalization and spelling variations
- **Compound word handling**: "medium-sized" ↔ "medium sized"
- **Punctuation robustness**: Handles apostrophes, hyphens, case differences

### System Reliability
- **Conditional TTS imports**: Eliminates SSL errors for ElevenLabs-only languages
- **Enhanced error handling**: Graceful failure with detailed error messages
- **Language mapping**: Automatic conversion between locale and Whisper codes
- **Warning suppression**: Filters noisy NLTK BLEU warnings for short texts

### Web Integration
- **Standalone validation page**: Resizable, draggable interface
- **Enhanced audio controls**: Play, regenerate with speed/style options
- **Bulk operations**: Save regenerated audio to cloud storage
- **Real-time feedback**: Progress indicators and error handling
