# Update Crowdin Source Keys

This utility updates source string identifiers (keys) directly in Crowdin to fix navigation terms that currently show as "unknown" source keys.

## 🎯 Purpose

Updates the following navigation keys to proper source-based names:

| Current Key | New Key |
|-------------|---------|
| `parent_survey_family_337` | `navigation.startSurvey` |
| `parent_survey_family_338` | `navigation.previous` |
| `parent_survey_family_339` | `navigation.next` |
| `parent_survey_family_340` | `navigation.finish` |
| `teacher_survey_classroom_117` | `navigation.startSurvey` |
| `teacher_survey_classroom_118` | `navigation.previous` |
| `teacher_survey_classroom_119` | `navigation.next` |
| `teacher_survey_classroom_120` | `navigation.finish` |
| `teacher_survey_general_141` | `navigation.startSurvey` |
| `teacher_survey_general_142` | `navigation.previous` |
| `teacher_survey_general_143` | `navigation.next` |
| `teacher_survey_general_144` | `navigation.finish` |

## 🔧 Prerequisites

Set your Crowdin credentials:

```bash
export CROWDIN_API_TOKEN='your_crowdin_api_token_here'
export CROWDIN_PROJECT_ID='your_project_id_here'
```

## 🚀 Usage

### Test Run (Recommended First)

```bash
python3 utilities/update_crowdin_source_keys.py --dry-run
```

### Apply Changes

```bash
python3 utilities/update_crowdin_source_keys.py
```

## ✅ Benefits

- **Preserves all existing translations** - Only updates the source key names
- **Fixes "unknown" source keys** - Crowdin will recognize proper source-based names
- **Consolidates navigation terms** - Multiple surveys will use the same navigation keys
- **No duplicate translations** - Each navigation term appears only once per language

## 🛡️ Safety

- The script only modifies source string identifiers, not translations
- All existing translations in all languages remain intact
- Dry-run mode allows you to preview changes before applying
- Only affects the specific navigation keys listed above

## 📋 Expected Output

```
📌 Project 12345
🔍 Fetching source strings...
📋 Found 2365 strings
🔄 Updating string 54321: 'parent_survey_family_337' → 'navigation.startSurvey'
   ✅ Updated successfully
🔄 Updating string 54322: 'parent_survey_family_338' → 'navigation.previous'  
   ✅ Updated successfully
...

✅ Done!
   Updated: 12
   Skipped: 2353
```

After running this utility, the navigation terms in Crowdin will have proper source keys and won't show as "unknown" anymore.

