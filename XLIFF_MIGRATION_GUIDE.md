# XLIFF Migration Guide

## Overview

This guide covers migrating from CSV-based translations to XLIFF (XML Localization Interchange File Format) for a more robust, industry-standard localization workflow.

## Why Migrate to XLIFF?

### Current CSV Limitations
- ❌ No translation state tracking (new/translated/approved)
- ❌ No context or comments for translators
- ❌ Poor version control (CSV diffs are messy)
- ❌ No translation memory integration
- ❌ Limited metadata support
- ❌ No workflow management
- ❌ Fragile parsing (encoding issues, special characters)

### XLIFF Benefits
- ✅ **Translation States**: Track new/translated/approved/rejected states
- ✅ **Rich Context**: Comments, notes, and metadata for translators
- ✅ **Translation Memory**: Better reuse across projects and updates
- ✅ **Pluralization**: Native ICU plural form support
- ✅ **Workflow Integration**: CAT tool compatibility (Trados, MemoQ, etc.)
- ✅ **Version Control**: Structured XML with meaningful diffs
- ✅ **Quality Assurance**: Built-in validation and review workflows
- ✅ **Industry Standard**: Supported by all major localization platforms

## Migration Strategy

### Phase 1: Parallel System (Recommended)
Run both CSV and XLIFF in parallel during transition:

1. **Convert existing CSV to XLIFF**
2. **Upload XLIFF to Crowdin alongside CSV**
3. **Test XLIFF workflow with subset of languages**
4. **Gradually migrate consumers to XLIFF**
5. **Deprecate CSV once XLIFF is stable**

### Phase 2: XLIFF-First
Make XLIFF the primary source:

1. **Update Crowdin project configuration**
2. **Modify deployment pipeline**
3. **Update audio generation scripts**
4. **Remove CSV dependencies**

## Tools Created

### 1. CSV to XLIFF Converter
**File**: `utilities/csv_to_xliff_converter.py`

Converts existing CSV translations to XLIFF 1.2 format:

```bash
# Convert item bank translations
python utilities/csv_to_xliff_converter.py \
  --input translation_text/item_bank_translations.csv \
  --output-dir xliff-export/

# Convert surveys
python utilities/csv_to_xliff_converter.py \
  --input surveys.csv \
  --output-dir xliff-export/ \
  --file-type surveys
```

**Features**:
- Automatic language column detection
- Translation state inference (new/translated)
- Context preservation from CSV metadata
- XML encoding safety
- Proper XLIFF 1.2 structure

### 2. Crowdin XLIFF Manager
**File**: `utilities/crowdin_xliff_manager.py`

Manages XLIFF files in Crowdin projects:

```bash
# Upload XLIFF files to Crowdin
python utilities/crowdin_xliff_manager.py upload \
  --project-id 756721 \
  --source-dir xliff-export/

# Download translated XLIFF files
python utilities/crowdin_xliff_manager.py download \
  --project-id 756721 \
  --output-dir xliff-downloads/

# Full sync: upload sources + download translations
python utilities/crowdin_xliff_manager.py sync \
  --project-id 756721 \
  --source-dir xliff/ \
  --output-dir xliff/
```

**Features**:
- Bulk XLIFF upload/download
- Automatic file management
- Language mapping
- Error handling and retry logic

## Step-by-Step Migration

### Step 1: Convert Current CSV to XLIFF

```bash
# Create XLIFF versions of current translations
python utilities/csv_to_xliff_converter.py \
  --input translation_text/item_bank_translations.csv \
  --output-dir xliff-migration/

# Review generated files
ls -la xliff-migration/
head -50 xliff-migration/itembank-es-CO.xliff
```

### Step 2: Upload to Crowdin (Test)

```bash
# Upload to Crowdin for testing
python utilities/crowdin_xliff_manager.py upload \
  --project-id 756721 \
  --source-dir xliff-migration/ \
  --crowdin-path /translations/xliff-test/
```

### Step 3: Test XLIFF Workflow

1. **Verify uploads in Crowdin UI**
2. **Make test translations in Crowdin**
3. **Download translated XLIFF files**
4. **Convert XLIFF to ICU JSON for testing**

```bash
# Download test translations
python utilities/crowdin_xliff_manager.py download \
  --project-id 756721 \
  --output-dir xliff-test-downloads/

# Convert to ICU JSON (existing tool)
python xliff/convert_xliff_to_icu.py \
  --repo your-repo/xliff-test-downloads \
  --output-dir xliff/translations-icu-test/
```

### Step 4: Update Deployment Pipeline

Modify `deploy_translations.py` to prioritize XLIFF:

```python
def deploy_translations(environment: str, dry_run: bool = False, force: bool = False):
    """Deploy translations with XLIFF-first strategy."""
    
    # Try XLIFF first
    xliff_success = deploy_xliff_to_assets_from_github(environment, dry_run, force)
    
    if xliff_success:
        print("✅ XLIFF deployment successful")
        # Still deploy CSV as backup during transition
        deploy_csv_to_assets(environment, dry_run, force)
    else:
        print("⚠️  XLIFF deployment failed, falling back to CSV")
        csv_success = deploy_csv_to_assets(environment, dry_run, force)
        if not csv_success:
            raise Exception("Both XLIFF and CSV deployment failed")
```

### Step 5: Update Audio Generation

Modify `generate_speech.py` to read from XLIFF-derived ICU JSON:

```python
def load_translations(language):
    """Load translations with XLIFF-first strategy."""
    
    # Try ICU JSON from XLIFF first
    icu_path = f"xliff/translations-icu/{language_code}.json"
    if os.path.exists(icu_path):
        with open(icu_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Fallback to CSV
    return load_csv_translations(language)
```

### Step 6: Full Migration

Once XLIFF workflow is stable:

1. **Update Crowdin project to XLIFF-primary**
2. **Remove CSV upload/download scripts**
3. **Update documentation**
4. **Train team on new workflow**

## XLIFF File Structure

Generated XLIFF files follow this structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file source-language="en" target-language="es-CO" datatype="plaintext" 
        original="levante-translations" date="2025-08-31T11:20:59.400938">
    <header>
      <tool tool-id="csv-to-xliff-converter" 
            tool-name="Levante CSV to XLIFF Converter" 
            tool-version="1.0"/>
    </header>
    <body>
      <trans-unit id="general-intro1" resname="general-intro1" approved="yes">
        <source>Hi! We are excited to have you play some games with us today!</source>
        <target state="translated">¡Hola! ¡Estamos encantados de que juegues hoy con nosotros!</target>
        <note from="developer">Task: general</note>
      </trans-unit>
      <!-- More translation units... -->
    </body>
  </file>
</xliff>
```

### Key Elements

- **`<trans-unit>`**: Individual translation pair
- **`id`**: Unique identifier for the string
- **`resname`**: Resource name (preferred over id)
- **`approved`**: Translation approval status
- **`<source>`**: Original text
- **`<target>`**: Translated text with state attribute
- **`<note>`**: Context information for translators

## Workflow Comparison

### Current CSV Workflow
```
Crowdin → CSV Export → GitHub → Deployment Pipeline → GCS
                                      ↓
                              Audio Generation (CSV)
```

### New XLIFF Workflow
```
Crowdin → XLIFF Export → GitHub → XLIFF to ICU → GCS
                                       ↓
                               Audio Generation (ICU JSON)
```

## Benefits Realized

### For Translators
- **Better Context**: Notes and comments explain string usage
- **Translation Memory**: Leverage previous translations
- **CAT Tool Integration**: Use professional translation tools
- **Quality Assurance**: Built-in validation and review

### For Developers
- **Structured Data**: XML is more robust than CSV
- **Version Control**: Meaningful diffs for translation changes
- **Metadata**: Rich information about translation states
- **Industry Standard**: Compatible with all localization tools

### For Project Management
- **Workflow Tracking**: See translation progress and states
- **Quality Control**: Approval workflows and review processes
- **Automation**: Better integration with CI/CD pipelines
- **Scalability**: Easier to add new languages and manage large projects

## Migration Checklist

- [ ] Convert existing CSV to XLIFF using converter tool
- [ ] Upload test XLIFF files to Crowdin
- [ ] Verify XLIFF structure and content in Crowdin
- [ ] Test translation workflow with sample strings
- [ ] Download translated XLIFF files
- [ ] Test XLIFF to ICU JSON conversion
- [ ] Update deployment pipeline for XLIFF support
- [ ] Test audio generation with XLIFF-derived data
- [ ] Train team on new XLIFF workflow
- [ ] Update documentation and processes
- [ ] Gradually migrate languages to XLIFF
- [ ] Monitor for issues during transition
- [ ] Deprecate CSV workflow once XLIFF is stable

## Troubleshooting

### Common Issues

**XML Encoding Errors**
- Solution: The converter handles encoding automatically
- Check for control characters in source text

**Crowdin Upload Failures**
- Verify API token permissions
- Check file size limits
- Ensure valid XLIFF structure

**Missing Translations**
- Check language code mapping
- Verify target language configuration in Crowdin
- Review translation state filters

**ICU Conversion Issues**
- Ensure XLIFF files are valid XML
- Check namespace declarations
- Verify trans-unit structure

## Next Steps

1. **Test the migration tools** with your current data
2. **Review generated XLIFF files** for accuracy
3. **Plan the migration timeline** (recommend gradual rollout)
4. **Train your team** on XLIFF workflow
5. **Set up monitoring** for the new pipeline

The migration to XLIFF will significantly improve your localization workflow's robustness, scalability, and maintainability while providing better tools for translators and project managers.
