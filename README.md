
### Levante Audio Tools

Our audio tools include three main utilities:

generate_speech.py: Designed to generate audio files for one or more languages in the voices specified in config.py. The audio files are laid out in a filesystem
format that matches that needed for core assets and our GCP buckets.

dashboard.py: This standalone utility does four things:

web_dashboard.py: This utility is designed to be run as a web server that can be accessed from a browser. It is used to display the audio generation stats and the translations and audio by language.

1) Shows current audio generation stats in the top frame
2) Shows all our current translations and audio by language
   in the bottom frame. Selecting one will play it.
3) For evaluation purposes, allows selecting a voice from
   PlayHt or ElevenLabs to play the same text.
4) Allows the addition of SSML tags to an edit box to evaluate their effect.


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
pip (or pip3) install . --user

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

### Usage Examples

```bash
# Export comprehensive voice data
python utilities/export_comprehensive_voices.py

# Export female voices only
python utilities/export_female_voices.py  

# Fix CSV formatting issues
python utilities/fix_csv_formatting.py input.csv output.csv

# Deploy Levante dashboard (itembank_translations.csv only)
python deploy_levante.py -dev

# Deploy web dashboard (via Vercel)
cd web-dashboard && npm run deploy

# Advanced deployment options
python utilities/deploy_dashboard.py --env dev --dashboard-only

# Download from Crowdin to GCS
python utilities/crowdin_to_gcs.py --bundle-id 18
```

## Deployment

There are two different deployment scripts for different purposes:

### Levante Dashboard Deployment
Use `deploy_levante.py` to deploy **only** the `itembank_translations.csv` file to the Levante dashboard buckets:

```bash
# Deploy to dev environment
python deploy_levante.py -dev

# Deploy to prod environment  
python deploy_levante.py -prod

# Test deployment (dry run)
python deploy_levante.py -dev --dry-run
```

**Target buckets**: `levante-dashboard-dev` / `levante-dashboard-prod`  
**Files deployed**: `itembank_translations.csv` only

### Web Dashboard Deployment
The web dashboard is deployed through Vercel using npm scripts:

```bash
# Navigate to web dashboard directory
cd web-dashboard

# Deploy to production (recommended)
npm run deploy

# Alternative deployment method
npm run deploy-bat

# Local development server
npm start
```

**Target**: Vercel hosting with automatic aliasing  
**URLs**: 
- Primary: https://audio-dashboard-levante.vercel.app
- Secondary: https://levante-audio-dashboard.vercel.app  
**Files deployed**: HTML, CSS, JavaScript, API functions, web assets

