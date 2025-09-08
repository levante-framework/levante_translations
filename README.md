
### Levante Audio Tools

[Help: Add a New Language Guide](https://github.com/levante-framework/levante_translations/blob/main/README_ADD_LANGUAGE.md) · [Project README on GitHub](https://github.com/levante-framework/levante_translations#readme) · [📝 Changelog](CHANGELOG.md)

Our audio tools include four main utilities:

**generate_speech.py**: Designed to generate audio files for one or more languages in the voices specified in config.py. The audio files are laid out in a filesystem format that matches that needed for core assets and our GCP buckets.

**validate_audio**: Advanced audio validation system that compares ASR transcriptions to expected text using multiple similarity metrics. Features include multi-backend transcription (Whisper, Google), robust text preprocessing, web dashboard integration, and comprehensive quality assessment. [📖 Detailed Documentation](validate_audio/README.md)

**dashboard.py**: This standalone utility does four things:

**web_dashboard.py**: This utility is designed to be run as a web server that can be accessed from a browser. It is used to display the audio generation stats and the translations and audio by language.

1) Shows current audio generation stats in the top frame
2) Shows all our current translations and audio by language
   in the bottom frame. Selecting one will play it.
3) For evaluation purposes, allows selecting a voice from
   PlayHt or ElevenLabs to play the same text.
4) Allows the addition of SSML tags to an edit box to evaluate their effect.
5) **Audio Validation Interface**: Interactive validation system for reviewing, regenerating, and managing audio quality with ElevenLabs integration.


### Installing Levante-Audio-Tools

Open a terminal:

Create a directory to use for your levante projects

Then:
git clone https://github.com/levante-framework/levante_translations.git

[If you've already cloned it, use "git pull"]

[Change into the folder with the project:]
cd levante_translations

[For stable behavior, use the main branch]
git checkout main

[Install all the needed packages:]
pip (or pip3) install -r requirements.txt --user

# If you get externally-managed-environment error:
pip3 install -r requirements.txt --break-system-packages

[Add PlayHt credentials to your enviornment]
[For Levante team, credentials are in Slack]
[For python, They are placed in an environment variable called PLAY_DOT_HT_API_KEY, and PLAY_DOT_HT_USER_ID]
[For Web Dashboard, you'll be prompted to enter them]

For Mac, edit ~/.zshrc and use:
export PLAY_DOT_HT_API_KEY=<API_KEY>
export PLAY_DOT_HT_USER_ID=<USER_ID>
[then exit the editor and do "source ~/.zshrc"]

You may also need to install ffmpeg to hear some of the audio.

[Hopefully the Dashboard will now run:]
python (or py) dashboard.py

### Generating Audio Files

1. Create/Update item_bank_translations.csv with the translations you'd like to use

2. Depending on your desired language, run:
    commands/generate_english.[sh|bat]
    commands/generate_spanish.[sh|bat]
    commands/generate_german.[sh|bat]
    etc.

#### Force Regeneration

To regenerate all audio files even if they already exist (useful when switching voices or improving audio quality):

```bash
# Using Python directly
python generate_speech.py English --force
python generate_speech.py Spanish -f

# Using npm scripts with force flag  
npm run generate:english -- --force
npm run generate:spanish -- -f
```

The `--force` (or `-f`) flag will regenerate all audio files using the current voice configuration, regardless of whether files already exist.

### Command Scripts

The `commands/` directory contains convenient shell and batch scripts for common operations:

- **Language Generation**: `generate_english.[sh|bat]`, `generate_spanish.[sh|bat]`, `generate_german.[sh|bat]`
- **Audio Counting**: `count_audio.[sh|bat]` - counts generated audio files for each language
- **Translation Fetching**: `get_translation_text.bat` - downloads translation data

3. By default the generated audio files will be in the audio_files
   sub-directory, in the format used for the asset repo and for serving

4. Optionally push/merge the audio files to the asset repo, and/or
    sync them to the appropriate google bucket using 'gsutil rsync -r <src> <bucket>'

## Code Flow:

Command files (batch/shell) call generate_speech.py with the appropriate language code and voice.

(CURRENTLY PlayHt v2 and ElevenLabs are supported.)

_generate_speech.py_ compares the desired text with its persistent cache of what
it has already generated audio for. If a string is new or changed, it is placed in
'needed_item_bank_translation.csv'

Items with no assigned task are skipped, as there is nowhere to file them.

New items are added to the item_bank_translations.csv file.

The translations needed are passed to PlayHT/playHt_tts.py or ElevenLabs/elevenLabs_tts.py

The module iterates through the rows in the csv, requesting audio generation for each.

As needed, the module will wait for a status of completed.

It also restarts the request if it receives an error. Currently it will
do that 5 times before giving up.

## Error Handling

Errors aren't a problem for English and Spanish, but happen for German and French.
There doesn't seem to be a pattern, but it means that sometimes the command
file has to be re-run. After a couple/few runs, everything gets translated.

There is a helper command file commands/count_audio.[bat|sh] that counts the number of
audio files generated for each language, as a sanity check.

## Recent Updates

### ElevenLabs API Compatibility (January 2025)
- **Fixed ElevenLabs SDK compatibility**: Updated to work with ElevenLabs Python SDK v2.9.1
- **Updated API calls**: Migrated from deprecated `generate()` function to `text_to_speech.convert()` method
- **Improved error handling**: Better handling of different audio response formats
- **Backwards compatible**: No changes needed to voice configurations

### Force Regeneration Feature
- **Added `--force` flag**: `generate_speech.py` now supports `--force` or `-f` to regenerate existing audio files
- **Use cases**: Voice updates, quality improvements, troubleshooting
- **CLI improvement**: Better argument parsing with `argparse` for cleaner usage

## Resetting audio transcriptions

To change to a new voice or if for some other reason you want to redo
transcriptions for a specific language, simple set the appropriate
language column to None. You can do this by importing as a DataFrame
and then just using a column operation. [At some point we should make this a function]

## Web Dashboard

The web dashboard is a modern web application for audio generation and translation management. It provides:

- Audio generation stats and visualization
- Translation and audio management by language  
- Voice comparison tools for PlayHT and ElevenLabs
- Real-time audio generation and playback
- Translation validation with similarity scoring

The web dashboard is located in the `web-dashboard/` directory and deployed via Vercel. See the deployment section below for instructions.

## Utility Scripts

The `utilities/` folder contains various helper scripts for data management and voice analysis:

### Voice Export Tools
- **`export_comprehensive_voices.py`**: Exports comprehensive voice data from ElevenLabs including personal library, shared library, and professional voices. Filters out advertising voices and searches across multiple languages.
- **`export_female_voices.py`**: Exports only female voices from PlayHT and ElevenLabs to CSV format, excluding advertising voices. Useful for curating voice libraries.

### CSV Formatting Tools
- **`fix_csv_formatting.py`**: Fixes general CSV formatting issues in translation files, removes embedded newlines and aligns fields.
- **`fix_csv_newlines.py`**: Simple script to fix embedded newlines in CSV files without requiring pandas dependency.
- **`fix_embedded_newlines.py`**: Fixes embedded newlines in CSV files by replacing them with `<br>` tags or spaces.

### Data Management Tools  
- **`deploy_dashboard.py`**: Advanced deployment tool for custom GCS bucket deployments (internal use).
- **`crowdin_to_gcs.py`**: Downloads translation files from Crowdin and uploads them to appropriate GCS buckets.
- **`buckets.py`**: Configuration for Google Cloud Storage bucket names and helper functions.
- **`seed_crowdin_language.py`**: Creates translation seed files for new languages in Crowdin by duplicating source language content.

### Usage Examples

```bash
# Export comprehensive voice data
python utilities/export_comprehensive_voices.py

# Export female voices only
python utilities/export_female_voices.py  

# Fix CSV formatting issues
python utilities/fix_csv_formatting.py input.csv output.csv

# Create Crowdin seed files for new languages
python seed_crowdin_language.py en pt-BR    # English to Portuguese (Brazil)
python seed_crowdin_language.py es-CO es-MX # Spanish (Colombia) to Spanish (Mexico)

# Deploy Levante dashboard (itembank_translations.csv only)
npm run deploy:levante-dev

# Deploy web dashboard (via Vercel)
npm run deploy:web

# Download from Crowdin to GCS
npm run deploy:crowdin-dev

# Generate audio files
npm run generate:english
npm run generate:spanish

# Fix CSV formatting
npm run fix:csv

# Export voice data
npm run export:voices

# Create Crowdin seed files
npm run seed:crowdin en pt-BR
```

## Crowdin Localization Workflow

### Creating New Language Seeds

To set up a new language for translation in Crowdin, use the seeding script to create a starting CSV file:

```bash
# Create seed file for a new language
npm run seed:crowdin <source_lang> <new_lang>

# Examples
npm run seed:crowdin en pt-BR         # English to Portuguese (Brazil)
npm run seed:crowdin en fr            # English to French
npm run seed:crowdin es-CO es-MX      # Spanish (Colombia) to Spanish (Mexico)
npm run seed:crowdin en en-GH         # English to English (Ghana) for localization
```

### Crowdin Workflow Steps

1. **Generate seed CSV**: `npm run seed:crowdin en pt-BR`
2. **Upload to Crowdin**: Import the generated `pt-BR_translations.csv` file
3. **Set up project**: Configure source (en) and target (pt-BR) languages
4. **Assign translators**: Add team members to begin translation work
5. **Download completed**: Export finished translations from Crowdin
6. **Update main CSV**: Add the new language column to `item_bank_translations.csv`
7. **Deploy translations**: Use `npm run deploy:levante-dev` to publish

### Seed File Format

The generated CSV contains:
- **Header**: `source_lang,new_lang` (e.g., `en,pt-BR`)
- **Content**: Source language text duplicated in both columns
- **Purpose**: Provides starting point for translators with context

This workflow ensures consistent translation quality and proper integration with the Levante translation system.

## Deployment

### Bucket Overview

Our Google Cloud Storage buckets have specific purposes:

| Bucket | Purpose | Files | Deployment Method |
|--------|---------|-------|------------------|
| `levante-dashboard-dev/prod` | **Translation CSV only** | `item-bank-translations.csv` | `deploy_levante.py` |
| `levante-translations-dev/prod` | Translation archives | CSV files | `crowdin_to_gcs.py` |
| `levante-audio-dev/prod` | Generated audio files | MP3s with ID3 tags | `generate_speech.py` |
| Web hosting buckets | Web dashboard files | HTML, CSS, JS, API | Vercel |

> ⚠️ **Critical**: Never upload code files to `levante-dashboard` buckets - they are CSV-only!

### Deployment Scripts

There are two different deployment scripts for different purposes:

### Levante Dashboard Deployment
Deploy **only** the translation CSV file to the Levante dashboard buckets (uploads as `item-bank-translations.csv`):

```bash
# Deploy to dev environment
npm run deploy:levante-dev

# Deploy to prod environment
npm run deploy:levante-prod

# Test deployment (dry run)
npm run deploy:levante-dev-dry
npm run deploy:levante-prod-dry
```

**Target buckets**: `levante-dashboard-dev` / `levante-dashboard-prod`
**Files deployed**: `item-bank-translations.csv` (source: `translation_text/item_bank_translations.csv`)

> ⚠️ **Important**: The `levante-dashboard` buckets contain **ONLY translation CSV files**. Never upload code files (HTML, JS, CSS) to these buckets.

### Web Dashboard Deployment
The web dashboard is deployed through Vercel:

```bash
# Deploy web dashboard to production
npm run deploy:web

# Start local development server
npm run start:web
```

**Target**: Vercel hosting with automatic aliasing  
**URLs**: 
- Primary: https://audio-dashboard-levante.vercel.app
- Secondary: https://levante-audio-dashboard.vercel.app  
**Files deployed**: HTML, CSS, JavaScript, API functions, web assets

## NPM Scripts Reference

The project provides convenient npm scripts for all common operations:

### Setup Commands
```bash
# Google Cloud Service Account Creation
npm run setup:service-account-dev --project_id=YOUR_PROJECT     # Create dev service account
npm run setup:service-account-prod --project_id=YOUR_PROJECT    # Create prod service account
npm run setup:service-account-both --project_id=YOUR_PROJECT    # Create both dev and prod
```

### Deployment Commands
```bash
# Levante Dashboard
npm run deploy:levante-dev          # Deploy to dev
npm run deploy:levante-prod         # Deploy to prod  
npm run deploy:levante-dev-dry      # Test dev deployment
npm run deploy:levante-prod-dry     # Test prod deployment

# Web Dashboard
npm run deploy:web                  # Deploy web dashboard
npm run start:web                   # Local development server

# Crowdin Integration
npm run deploy:crowdin-dev          # Download from Crowdin to GCS
npm run deploy:crowdin-dry          # Test Crowdin download
```

### Audio Generation Commands
```bash
npm run generate:english            # Generate English audio
npm run generate:spanish            # Generate Spanish audio  
npm run generate:german             # Generate German audio

# Force regeneration (rebuild all audio files)
npm run generate:english -- --force # Force regenerate English audio
npm run generate:spanish -- -f      # Force regenerate Spanish audio (short flag)
```

### Utility Commands
```bash
npm run fix:csv                     # Fix CSV formatting issues
npm run export:voices               # Export comprehensive voice data
npm run export:female-voices        # Export female voices only
npm run seed:crowdin en pt-BR       # Create Crowdin seed CSV for new language
npm run test:dry-run-all           # Test all deployments
npm run help                       # Show available commands
```

### Why Use npm Scripts?

✅ **Consistent Interface**: Same `npm run` pattern for all commands  
✅ **Cross-Platform**: Works on Windows, Mac, and Linux  
✅ **Easy to Remember**: Descriptive command names  
✅ **No Path Issues**: Scripts run from project root  
✅ **Team Friendly**: Everyone uses the same commands

## Contributing

This project welcomes contributions! Please see:

- **[Contributing Guide](.github/CONTRIBUTING.md)**: Comprehensive guide for contributors
- **[Issue Templates](.github/ISSUE_TEMPLATE/)**: Report bugs or request features
- **[GitHub Workflows](.github/workflows/)**: Automated testing and quality checks

Before contributing, run `npm run test:dry-run-all` to ensure your changes work correctly.

## Troubleshooting

### Common Issues

#### ElevenLabs API Errors
```bash
# Error: 'ElevenLabs' object has no attribute 'generate'
# Solution: Update to latest code (fixed in January 2025)
git pull origin main
```

#### Missing Dependencies
```bash
# Error: ModuleNotFoundError: No module named 'pandas'
sudo apt install python3-pandas

# Error: ModuleNotFoundError: No module named 'playsound'  
sudo apt install python3-playsound
# OR
pip3 install playsound --break-system-packages
```

#### Force Regeneration Not Working
```bash
# Make sure to use -- before the flag with npm
npm run generate:english -- --force

# Or use Python directly
python generate_speech.py English --force
```

#### Environment Management Issues
```bash
# If pip install fails with externally-managed-environment
pip3 install -r requirements.txt --break-system-packages

# For system packages
sudo apt install python3-pandas python3-playsound
```

# Permissions fixed - testing deployment

### End-to-End Workflow

This repository now supports a streamlined, mostly automated pipeline to prepare and deploy all translation artifacts.

1) Retrieve translations from GitHub (CSV + XLIFF) and normalize

- Fetch and normalize the Item Bank CSV (maps identifier→item_id, labels/label→task; normalizes language headers):
```bash
python utilities/get_translations_csv_merged.py --force
# Output: translation_text/item_bank_translations.csv (normalized headers)
```
- Generate ICU JSON files from XLIFF (by language):
```bash
python xliff/convert_xliff_to_icu.py --overwrite --verbose
# Output: xliff/translations-icu/<lang>.json
```

2) (Optional, manual) Generate audio files for specified languages

- Use the audio generator to produce MP3s with ID3 tags for one or more languages:
```bash
# Examples
npm run generate:english
npm run generate:spanish
# Force re-generate all audio
npm run generate:english -- --force
```

3) Deploy all artifacts via a single deploy command

- The deployment uses fast, checksum-based rsync to skip identical files (add --force to clear remote before uploading).
- What gets deployed:
  - Dashboard CSV (normalized):
    - gs://levante-dashboard-<env>/itembank_translations.csv and item-bank-translations.csv
  - Assets mirrors:
    - CSV mirror → gs://levante-assets-<env>/translations/item-bank-translations.csv
    - ICU JSON   → gs://levante-assets-<env>/translations/icu/
    - XLIFF      → gs://levante-assets-<env>/translations/xliff/
    - Audio      → gs://levante-assets-<env>/audio/

- Commands:
```bash
# Deploy CSV + ICU + XLIFF mirrors + Audio (dev)
npm run deploy:translations-dev
# Dry-run
npm run deploy:translations-dev-dry
# Audio-only
npm run deploy:translations-audio-only-dev
# CSV-only
npm run deploy:translations-csv-only-dev
# Force re-upload (remove then rsync)
npm run deploy:translations-dev -- --force
```

Notes
- The deploy commands automatically fetch and normalize the CSV before uploading.
- XLIFF files are fetched directly from GitHub and mirrored; ICU JSONs are synced from xliff/translations-icu.
- All uploads use rsync with checksums to minimize transfer time.

4) Survey translations (levante-surveys)

- The `levante-surveys` repository contains survey/UI JSON translations.
- Add new languages and translations there; our web dashboard can report coverage.

## Recent System Improvements

### 🔧 **Audio Generation Reliability (September 2025)**

**Problem Solved: SSL Certificate Errors**
- **Issue**: PlayHT imports were causing SSL certificate failures even for ElevenLabs-only languages (English)
- **Solution**: Implemented conditional TTS imports - only loads the required service (PlayHT or ElevenLabs)
- **Impact**: English audio generation now works flawlessly without PlayHT dependencies

**Enhanced Error Handling**
- Graceful failure with detailed error messages when TTS services are unavailable
- Better debugging information for import and dependency issues

### 📊 **Audio Validation System Enhancements**

**Advanced Text Similarity**
- **Multi-pass word matching**: Exact → Compound → Phonetic → Fuzzy matching
- **German language support**: Automatic umlaut normalization (ä→a, ö→o, ü→u, ß→ss)
- **Compound word handling**: Matches "medium-sized" ↔ "medium sized"
- **Punctuation robustness**: Handles apostrophes, hyphens, case differences

**Language Code Mapping**
- Automatic conversion between locale codes (`es-CO`) and Whisper-compatible codes (`es`)
- Shell script (`validate_language.sh`) for streamlined validation workflows

**Warning Suppression**
- Filters noisy NLTK BLEU score warnings for short texts
- Cleaner console output during batch processing

### 🌐 **Web Dashboard Integration**

**Standalone Audio Validation Page**
- Resizable, draggable interface replacing modal dialogs
- Enhanced audio controls with speed/style regeneration options
- Real-time duration comparison (original vs. regenerated)
- Bulk save operations to Google Cloud Storage

**Improved User Experience**
- Better error handling and user feedback
- Consistent button placement and functionality
- Cache-busting for reliable deployment updates

### 🚀 **Deployment & Performance**

**Efficient Audio Deployment**
- Rsync-based uploads avoid re-transferring identical files
- Separate audio-only deployment options for faster updates
- Successful deployment of 785 English audio files (11.7 MiB) to dev environment

**GPU Acceleration**
- Automatic detection and utilization of CUDA-enabled GPUs
- Significantly faster processing for Whisper and CLAP models

---

For detailed audio validation documentation, see: [validate_audio/README.md](validate_audio/README.md)
