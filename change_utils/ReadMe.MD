# Overview

The change_check package provides tools for adding new languages to the LEVANTE platform, patching specific strings or audio files for specific languages, and checking the LEVANTE source for surveys and tasks for changes. While in the `change_utils` folder, run `pip install -r requirements.txt` to install the package itself (including endpoints), and dependencies.

There are three parts of the package:

# transition_sot

This part of the package contains a series of scripts for a one-time operation (circa Dec 2025 - Jan 2026) to:

- Move the source of truth for English (en-US) strings (which form the basis for all translation) out of Crowdin and to Airtable for the itembank (`crowdin_airtable_sync.py`) and SurveyJS for adult surveys.

- Create new XLIFF files for adult surveys with informative flattened keys for more robust JSON schema creation when adding new languages, while retaining existing translations.
- Create new XLIFF files for the itembank, with a separate file for each task (`split_itembank.py`. This will allow translation efforts to more easily target specific tasks.
- Preserve comments on source strings we planned to deprecate (`preserve_comments.py`)
- Put new stringIds for split itembank into Airtable (`get_split_stringIds.py`)
- Attach task images to new split itembank strings (`attach_screenshots.py`)
- A lot of other garbage files  and one-off operations (sorry)

Most of these operations do not have built-in endpoints, as the expectation is that these will not run again now that the source of truth for source strings has been moved out of Crowdin. 

## Endpoints

The scripts in this folder will work if we need to re-run any transition operations, but  endpoings are generally not exposed or built into workflows as these were intended to be onetime operations. 

###  `crowdin-backup`

The sole endpoint available from `transition_sot` is `crowdin-backup`, which will pull a full XLIFF backup file of a specific language or languages into a `crowdin-backup/` folder from wherever the endpoint is run _locally_. This endpoint is not connected to a github action.

The backup XLIFF file contains _all_ files in the project for a given language in one XLIFF, with a new `<file>` element for each file for easy iteration. For example,

- `crowdin-backup --langs en-US es-CO` backs up all translations for US English and Colombian Spanish, with each language in a separate XLIFF file.
- `crowdin-backup --langs all` backs up all translations in all languages currently in the levantetranslations project, including e.g., the approval statuses and comments for a specific string.

**Backup files will go to our dev assets bucket: `levante-assets-dev/translations/crowdin-backup`**

# update_source_strings

This contains operations for updating source strings, incluidng changing existing strings and adding new ones. 

## Endpoints

### `check-newsource`

Associated workflow: 

`check-newsource`  requires a `--platform` argument of either `tasks` or `surveys`. **Note that this endpoint _only_ queues changes but does not cascade them to Crowdin.** Because Crowdin source strings determine a lot about what ends up in our front end, actually changing them requires reviewing the queued changes in Airtable and then executing the `update-source` endpoint separately (see below). 

For tasks, this endpoint handles both changes to existing source strings *and* the addition of new source strings. For surveys, the addition of new source strings requires a change to the structure of the survey which is not currently supported by automation. See Unsupported Actions for more information.

- `--platform tasks` will automatically iterate over strings in airtable, compare these to strings in the split itembank files on Crowdin, and add each change as a row to the itembank source string tracker in Airtable.

- `--platform surveys` automatically pulls the latest surveys from Prod and uses these to query current source strings in Crowdin. To compare this to a surveyjs source of truth (i.e., changes made to survey strings) requires some additional work on the part of the user. The endpoint requires `newsurveys/` folder which contains the latest JSON files downloaded from SurveyJS, i.e., it requires one or more of the following JSON files: `parent_survey_child.json`,`parent_survey_family.json`,`teacher_survey_classroom.json`, and/or`teacher_survey_general.json`. There is currently no way to "pull" these in a more automated way unless we host our own SurveyCreator instance.
  - If the folder isn't found, it will create it and flag to the user that it is empty, prompt them to upload valid files and re-run.
  - If the folder is found but has no valid json files, it will throw an error.
  - the `newsurveys` folder must have one or more of the following JSON files: `parent_survey_child.json`,`parent_survey_family.json`,`teacher_survey_classroom.json`, and/or `teacher_survey_general.json`
    - The endpoint will only check files which are present; e.g., if you wish to only check/process changes to `teacher_survey_classroom.json`, only put this file in the `newsurveys/` folder when prompted.
  - When the `update_strings --platform survey`  endpoint runs, it wiill delete the `newsurveys/` folder and its contents.
  - **Further advice and consultation needed on connecting this e.g., to a draft bucket to avoid branching/re-committing within the repo**.

### `pilot-strings`

This endpoint only works for tasks and exists for the purpose of piloting string _changes_ in English tasks before they are cascaded to other languages. 

Use the endpoint `pilot-strings` to:

- Implemenet changes to existing strings by updating the en-US _translation_ only, keeping the master source string intact to avoid affecting translations in other languages.
- For new strings, this will create new source strings and:
  - flag them with a comment "PILOT PHASE ONLY - Do not translate."
  - create and approve translations for _en-US only_ mirroring the source strings.
- Creates an "active piloting" flag in airtable

### `update-strings`

This endpoint also requires a platform argument of either `--platform surveys` or `--platform tasks`. This starts by checking the source string change tracker in Airtable. If no changes are listed there, no actions will be taken. Once updates have been performed, the `updated` field in the source string tracker will be changed to true, and the change will be ignored by future updates.

#### `--platform tasks --pilot done`

- This assumes string changes and new strings have undergone piloting. Source strings are changed _and_ translations are approved for en-US only.
- Translations for other en- varieties are changed to match the new English string and toggled to an _unapproved_ state.
- Translations for other languages are unaltered in terms of their content, but toggled to an _unapproved_ state.
- `updated` flag in airtable is set to true to keep a record of the update but make sure it is ignored in future

#### `--platform tasks --pilot none`

- This assumes string changes and new strings have not undergone piloting, but that this step is being intentionally skipped.
- Source strings are changed, and translations are implemented for all en- varieties to match the new/altered strings, but all in an _unapproved_ state.
- Translations for other languages are unaltered in terms of their content, but toggled to an _unapproved_ state.
- `updated` flag in airtable is set to true to keep a record of the update but make sure it is ignored in future

#### `--platform survey`

- This takes changes to survey strings queued in airtable, and puts them through to Crowdin by
  - Changing the source string
  - Changing the translation for en-US and other en- varieties and putting these in an _unapproved_ state
  - Preserving translations for other languages, but putting these in an _unapproved_ state.
- To approve en-US translations add the `--forceapprove en-US` argument.

# update_platform

## `build-survey`

### `--whitelist [approved or codelist]`

### `--slist [caregiver-child,cargiver-family, teacher-classroom,teacher-general]`

This endpoint builds new survey json files and places them in the `levante-assets-dev/surveys/drafts` folder. At this point they should be previewed using the preview tool before overwriting files in the main `levante-assets-dev/surveys` folder. These should be reviewed using the preview tool and can be deployed on dev using the `upgrade-survey-drafts` end point, which moves existing surveys to a datestamped backup folder, replaces existiing surveys `levante-assets-dev/surveys` with those in `/drafts` folder, and deletes the `surveys/draft` folder.  

For deployment to prod, the main `/surveys` folder on dev will be echoed to `levante-assets-prod/surveys`

- `--whitelist approved` will only make drafts including languages where survey translations are 100% approved. This is the recommended choice for deployment. 
- `--whitelist [codelist]` will pull through specific language codes, including unapproved translations. This can be used to preview surveys in a specific language through the drafts folder, e.g., `--whitelist pt-BR he-He` will build Portuguese and Hebrew surveys for testing even though these translations are not yet approved.
- `--slist` takes a list of survey types to build. `--slist all` will rebuild all four adult surveys; `--slist caregiver-child caregiver-family` will only rebuild caregiver surveys, etc.

Note: **The file on SurveyJS will _only_ ever contain accurate strings for English.** SurveyJS is the source of truth for _English source strings only_. For all other languages the source of truth should be considered Crowdin, which whitelisted/approved languages, should match the .json file in production.

## `build-corpus --tasks [all or list]`

This endpoint builds new corpus files and places them in `levante-assets-draft/corpus` for review. Use `--tasks all` to build new corpus files for all tasks; use e.g., `--tasks math vocab` to update math and vocab. Valid options for a list are `adult-reasoning`, `child-survey`,`math`,`hostile-attribution`,`matrix-reasoning`,`mental-rotation`,`same-different-selection`,`theory-of 

## `generate-audio`



# Unsupported actions

## Structure changes for surveys
