
### Installing Levante-Audio-Tools

Open a terminal:

Create a directory to use for your levante projects

Then:
git clone https://github.com/levante-framework/audio-generation.git

[Change into the folder with the project:]
cd audio-generation

[Checkout the Dev branch that has the SSML support:]
git checkout dev

[Go to the Tools sub-folder:]
cd tools

[Install all the needed packages:]
pip (or pip3) install . --user

[Add PlayHt credentials to your enviornment]
[For Levante team, credentials are in Slack]

[Hopefully the Dashboard will now run:]
python (or py) dashboard.py


### Generating Audio Files

1. Create/Update item_bank_translations.csv with the translations you'd like to use

2. Depending on your desired language, run:
    generate_english.[sh|bat]
    generate_spanish.[sh|bat]
    generate_german.[sh|bat]

3. By default the generated audio files will be in the audio_files
    sub-directory, in the format used for the asset repo and for serving

4. Optionally push/merge the audio files to the asset repo, and/or
    sync them to the appropriate google bucket using 'gsutil rsync -r <src> <bucket>'

## Code Flow:

Batch/Shell files call generate_speech.py with the appropriate language code and voice.

(CURRENTLY only PlayHt is supported.)

_generate_speech.py_ compares the desired audio with its persistent cache of what
it has already translated. If a string is new or changed, it is placed in
'needed_item_bank_translation.csv'

Items with no assigned task are skipped, as there is nowhere to file them.

The translations needed are passed to PlayHT/playHt_tts.py

The module iterates through the rows in the csv, requesting audio for each.

As needed, the module will wait for a status of completed.

It also restarts the request if it receives an error. Currently it will
do that 5 times before giving up.

## Error Handling

Errors aren't a problem for English and Spanish, but happen for German.
There doesn't seem to be a pattern, but it means that sometimes the batch/shell
file has to be re-run. After a couple/few runs, everything gets translated.

There is a helper script count_audio.[bat|sh] that counts the number of
audio files generated for each language, as a sanity check.

## Resetting audio transcriptions

To change to a new voice or if for some other reason you want to redo
transcriptions for a specific language, simple set the appropriate
language column to None. You can do this by importing as a DataFrame
and then just using a column operation. [At some point we should make this a function]




