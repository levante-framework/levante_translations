### Creating a new Levante task (and variants)

This document summarizes what code and data you must add to introduce a new task (or a variant of an existing task) to the Levante core-tasks launcher. It is based on the current launcher implementation in `core-tasks/task-launcher/src/tasks/`.

---

#### 1) Registry: wire your task in `taskConfig.ts`
- File (in core-tasks): `core-tasks/task-launcher/src/tasks/taskConfig.ts`
- Add a new key using the camelCase form of your task’s dashed name (e.g., `egma-math` → `egmaMath`).
- Provide the following entries for your task:
  - `setConfig`
  - `getCorpus`
  - `getTranslations`
  - `buildTaskTimeline`
  - `variants` (optional)

---

#### 2) Implement your task timeline
- Location (in core-tasks): `core-tasks/task-launcher/src/tasks/<my-task>/timeline.ts`
- Export a default function that builds and returns the jsPsych timeline using the task config and resolved media assets.

---

#### 3) Corpus CSV (stimulus) data in GCS
- Upload corpus to:
  - Dev: `gs://levante-assets-dev/corpus/<task-name>/<corpus>.csv`
  - Prod: `gs://levante-assets-prod/corpus/<task-name>/<corpus>.csv`
- The loader expects headers such as: `task`, `trial_type`, `item`, `response_alternatives`, `assessment_stage`, `time_limit`, `audio_file`, `item_id`, `item_uid`, `chance_level`, `d`/`difficulty`, `randomize`, `block_index`, `trial_num`.

---

#### 4) Media assets (audio/visual) in GCS
- Buckets switch automatically by environment:
  - Dev: `levante-assets-dev/*`
  - Prod: `levante-assets-prod/*`
- Folder conventions:
  - Visual: `visual/<task-name>/...`
  - Audio: `audio/<language>/...` and `audio/shared/...`

---

#### 5) Declare required assets (assets-per-task.json)
- Hosted at: `https://storage.googleapis.com/levante-assets-{dev|prod}/audio/assets-per-task.json`
- Minimal shape:
  ```json
  {
    "<task-name>": { "audio": ["beep", "click", "intro_voiceover"] },
    "shared": { "audio": ["correct", "incorrect"] }
  }
  ```

---

#### 6) Translations
- Source (GCS): `https://storage.googleapis.com/levante-assets-{dev|prod}/translations/item-bank-translations.csv`
- Ensure all strings referenced by your timeline are present; keys are typically camel-cased.

---

#### 7) Variants
- Define per-task variants in the registry with only the fields that differ (e.g., `corpus`, `numOfPracticeTrials`, `sequentialStimulus`, `buttonLayout`, `stimulusBlocks`, `cat`, `heavyInstructions`, `language`).

---

#### 8) Environment switching
- Determined by Firebase project ID; buckets change automatically—no code changes required.

---

#### 9) End-to-end flow (launcher)
1) Resolve buckets and fetch media listings
2) setSharedConfig → compute final task config and persist params
3) Fetch corpus (as applicable)
4) Fetch translations and `assets-per-task.json`
5) Combine/filter media assets
6) Build and run jsPsych timeline

---

#### 10) Checklist
- [ ] Create `core-tasks/task-launcher/src/tasks/<task-name>/timeline.ts`
- [ ] Register in `core-tasks/task-launcher/src/tasks/taskConfig.ts`
- [ ] (Optional) Default corpus mapping in `shared/helpers/config.ts`
- [ ] Upload corpus CSV to `levante-assets-{dev|prod}/corpus/<task-name>/<corpus>.csv`
- [ ] Upload visual/audio assets to `levante-assets-{dev|prod}`
- [ ] Update `assets-per-task.json` with required audio keys
- [ ] Ensure translations in `item-bank-translations.csv`
- [ ] (Optional) Add `variants`

---

For implementation specifics, see files in `core-tasks/task-launcher/src/tasks/shared/helpers/` (e.g., `getCorpus.ts`, `getMediaAssets.ts`, `getTranslations.ts`).

