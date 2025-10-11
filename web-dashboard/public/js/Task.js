/**
 * Task.js
 * Core Task class for Levante task management and validation
 * 
 * Handles task creation, display, and validation of dependencies
 */

class Task {
    constructor(data = {}) {
        // Basic Information
        this.taskName = data.taskName || '';
        this.registryKey = data.registryKey || this._toRegistryKey(this.taskName);
        this.description = data.description || '';
        this.trialType = data.trialType || '';
        this.assessmentStage = data.assessmentStage || '';
        this.corpusFile = data.corpusFile || '';
        this.notes = data.notes || '';

        // Registry Configuration
        this.hasSetConfig = data.hasSetConfig !== false;
        this.hasGetCorpus = data.hasGetCorpus !== false;
        this.hasGetTranslations = data.hasGetTranslations !== false;
        this.hasBuildTaskTimeline = data.hasBuildTaskTimeline !== false;

        // CSV Headers
        this.csvHeaders = data.csvHeaders || [];

        // Media Assets - Visual
        this.hasVisualAssets = data.hasVisualAssets || false;
        this.visualAssetCount = data.visualAssetCount || 0;
        this.visualAssetTypes = data.visualAssetTypes || [];
        this.visualAssetsList = data.visualAssetsList || [];

        // Media Assets - Audio
        this.hasAudioAssets = data.hasAudioAssets !== false;
        this.audioAssetCount = data.audioAssetCount || 0;
        this.requiredAudioIds = data.requiredAudioIds || [];
        this.sharedAudioIds = data.sharedAudioIds || [];
        this.audioIdsWithoutText = data.audioIdsWithoutText || [];

        // Translations
        this.translationKeys = data.translationKeys || [];
        this.languages = data.languages || ['en'];

        // Variants
        this.hasVariants = data.hasVariants || false;
        this.variants = data.variants || [];

        // Deployment
        this.bucketNameDev = data.bucketNameDev || '';
        this.bucketNameProd = data.bucketNameProd || '';

        // Validation state
        this._validationResults = null;
        this._hydrated = false;
        this._hydrationMeta = { audio: null, visual: null };
    }

    /**
     * Convert kebab-case to camelCase for registry keys
     */
    _toRegistryKey(taskName) {
        return taskName.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
    }

    /**
     * Create a new task from form data
     * @param {HTMLFormElement} formElement - The task template form
     * @returns {Task} New Task instance
     */
    static createNew(formElement) {
        const formData = new FormData(formElement);
        
        // Helper to get selected languages
        const getSelectedLanguages = () => {
            const checkboxes = formElement.querySelectorAll('input[name="languages"]:checked');
            return Array.from(checkboxes).map(cb => cb.value);
        };

        // Helper to parse multiline text into array
        const parseLines = (text) => {
            return text.split('\n')
                .map(line => line.trim())
                .filter(line => line.length > 0);
        };

        // Helper to parse CSV header checkboxes
        const getSelectedCsvHeaders = () => {
            const headers = [];
            const checkboxMapping = {
                'csv_task': 'task',
                'csv_trial_type': 'trial_type',
                'csv_item': 'item',
                'csv_item_id': 'item_id',
                'csv_item_uid': 'item_uid',
                'csv_audio_file': 'audio_file',
                'csv_response_alternatives': 'response_alternatives',
                'csv_assessment_stage': 'assessment_stage',
                'csv_time_limit': 'time_limit',
                'csv_difficulty': 'difficulty'
            };

            Object.entries(checkboxMapping).forEach(([id, header]) => {
                const checkbox = formElement.querySelector(`#${id}`);
                if (checkbox && checkbox.checked) {
                    headers.push(header);
                }
            });

            return headers;
        };

        const taskData = {
            taskName: formData.get('taskName') || '',
            registryKey: formData.get('registryKey') || '',
            description: formData.get('taskDescription') || '',
            trialType: formData.get('trialType') || '',
            assessmentStage: formData.get('assessmentStage') || '',
            corpusFile: formData.get('corpusFile') || '',
            notes: formData.get('taskNotes') || '',

            csvHeaders: getSelectedCsvHeaders(),

            hasVisualAssets: formElement.querySelector('#hasVisualAssets')?.checked || false,
            visualAssetCount: parseInt(formData.get('visualAssetCount')) || 0,
            visualAssetTypes: formData.get('visualAssetTypes')?.split(',').map(t => t.trim()).filter(Boolean) || [],
            visualAssetsList: parseLines(formData.get('visualAssetsList') || ''),

            hasAudioAssets: formElement.querySelector('#hasAudioAssets')?.checked || false,
            audioAssetCount: parseInt(formData.get('audioAssetCount')) || 0,
            requiredAudioIds: parseLines(formData.get('requiredAudioIds') || ''),
            audioIdsWithoutText: parseLines(formData.get('audioIdsWithoutText') || ''),
            sharedAudioIds: parseLines(formData.get('sharedAudioIds') || ''),

            translationKeys: parseLines(formData.get('translationKeys') || ''),
            languages: getSelectedLanguages(),

            hasVariants: formElement.querySelector('#hasVariants')?.checked || false,
            variants: parseLines(formData.get('variantsList') || ''),
        };

        return new Task(taskData);
    }

    /**
     * Display task data in the form
     * @param {HTMLFormElement} formElement - The task template form
     */
    display(formElement) {
        // Update mode indicator
        const modeIndicator = document.getElementById('modeIndicator');
        if (modeIndicator) {
            modeIndicator.className = 'mode-indicator mode-viewing';
            modeIndicator.innerHTML = `<i class="fas fa-eye"></i> Viewing: ${this.taskName}`;
        }

        // Basic Information
        this._setFieldValue(formElement, 'taskName', this.taskName);
        this._setFieldValue(formElement, 'registryKey', this.registryKey);
        this._setFieldValue(formElement, 'taskDescription', this.description);
        this._setFieldValue(formElement, 'trialType', this.trialType);
        this._setFieldValue(formElement, 'assessmentStage', this.assessmentStage);
        this._setFieldValue(formElement, 'taskNotes', this.notes);

        // Corpus
        this._setFieldValue(formElement, 'corpusFile', this.corpusFile);

        // CSV Headers
        this._clearAllCsvHeaders(formElement);
        this._selectCsvHeaders(formElement, this.csvHeaders);

        // Visual Assets
        this._setCheckbox(formElement, 'hasVisualAssets', this.hasVisualAssets);
        this._toggleVisibility('visualAssetsDetails', this.hasVisualAssets);
        
        if (this.hasVisualAssets) {
            this._setFieldValue(formElement, 'visualAssetCount', this.visualAssetCount);
            this._setFieldValue(formElement, 'visualAssetTypes', this.visualAssetTypes.join(', '));
            this._setFieldValue(formElement, 'visualAssetsList', this.visualAssetsList.join('\n'));
        }

        // Audio Assets
        this._setCheckbox(formElement, 'hasAudioAssets', this.hasAudioAssets);
        this._toggleVisibility('audioAssetsDetails', this.hasAudioAssets);
        
        if (this.hasAudioAssets) {
            this._setFieldValue(formElement, 'audioAssetCount', this.audioAssetCount);
        }

        // Required Audio IDs
        this._setFieldValue(formElement, 'requiredAudioIds', this.requiredAudioIds.join('\n'));
        this._setFieldValue(formElement, 'audioIdsWithoutText', this.audioIdsWithoutText.join('\n'));
        this._setFieldValue(formElement, 'sharedAudioIds', this.sharedAudioIds.join('\n'));

        // Translation Keys
        this._setFieldValue(formElement, 'translationKeys', this.translationKeys.join('\n'));

        // Languages
        this._clearAllLanguages(formElement);
        this._selectLanguages(formElement, this.languages);

        // Variants
        this._setCheckbox(formElement, 'hasVariants', this.hasVariants);
        this._toggleVisibility('variantsDetails', this.hasVariants);
        
        if (this.hasVariants) {
            this._setFieldValue(formElement, 'variantsList', this.variants.join('\n'));
        }
    }

    /**
     * Validate task dependencies and configuration
     * @returns {ValidationResult} Validation results with issues categorized by severity
     */
    async validate() {
        // Ensure latest authoritative assets are loaded before validating
        if (!this._hydrated) {
            try { await this.hydrate(); } catch (_) { /* non-fatal */ }
        }
        const results = {
            isValid: true,
            errors: [],      // Critical issues that prevent task from working
            warnings: [],    // Issues that may cause problems
            info: [],        // Informational notices
            checks: {
                registry: { passed: false, issues: [] },
                timeline: { passed: false, issues: [] },
                corpus: { passed: false, issues: [] },
                visualAssets: { passed: false, issues: [] },
                audioAssets: { passed: false, issues: [] },
                translations: { passed: false, issues: [] },
                languages: { passed: false, issues: [] },
                variants: { passed: false, issues: [] }
            },
            _warningContext: {}
        };

        // 1. Registry Validation
        await this._validateRegistry(results);

        // 2. Timeline Validation
        await this._validateTimeline(results);

        // 3. Corpus Validation
        await this._validateCorpus(results);

        // 4. Visual Assets Validation
        await this._validateVisualAssets(results);

        // 5. Audio Assets Validation
        await this._validateAudioAssets(results);

        // 6. Translations Validation
        await this._validateTranslations(results);

        // 7. Language Support Validation
        await this._validateLanguages(results);

        // 8. Variants Validation
        await this._validateVariants(results);

        // Set overall validity
        results.isValid = results.errors.length === 0;

        this._validationResults = results;
        return results;
    }

    /**
     * Hydrate task with authoritative asset data from backend (GCS)
     * @param {('dev'|'prod')} env
     */
    async hydrate(env = 'dev') {
        if (!this.taskName) return;
        try {
            const params = new URLSearchParams();
            params.set('task', this.taskName);
            if (this.corpusFile) params.set('corpus', this.corpusFile);
            params.set('env', env);
            const resp = await fetch(`/api/task-assets?${params.toString()}`);
            if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
            const data = await resp.json();

            // Merge audio
            if (data.audio && Array.isArray(data.audio.requiredIds) && data.audio.requiredIds.length > 0) {
                this.requiredAudioIds = data.audio.requiredIds.slice();
                this.audioAssetCount = data.audio.count || this.requiredAudioIds.length;
                this.hasAudioAssets = true;
                this._hydrationMeta.audio = {
                    source: 'gcs-assets-per-task',
                    bucket: `levante-assets-${env}`,
                    path: 'audio/assets-per-task.json'
                };
            }

            // Merge visual
            if (data.visual && typeof data.visual.count === 'number') {
                this.visualAssetCount = data.visual.count;
                this.hasVisualAssets = this.hasVisualAssets || data.visual.count > 0;
                this._hydrationMeta.visual = {
                    source: 'gcs-list',
                    bucket: `levante-assets-${env}`,
                    prefix: `visual/${this.taskName}/`
                };
            }

            this._hydrated = true;
        } catch (e) {
            // Hydration is best-effort; keep going if it fails
            // console.warn('Hydration failed:', e);
        }
    }

    /**
     * Validate registry configuration
     */
    async _validateRegistry(results) {
        const check = results.checks.registry;

        // Check task name format
        if (!this.taskName) {
            results.errors.push('Task name is required');
            check.issues.push('Missing task name');
        } else if (!/^[a-z][a-z0-9-]*$/.test(this.taskName)) {
            results.errors.push('Task name must be kebab-case (lowercase with hyphens)');
            check.issues.push('Invalid task name format');
        }

        // Check registry key
        if (!this.registryKey) {
            results.errors.push('Registry key is required');
            check.issues.push('Missing registry key');
        } else if (!/^[a-z][a-zA-Z0-9]*$/.test(this.registryKey)) {
            results.warnings.push('Registry key should be camelCase');
            check.issues.push('Registry key format may be incorrect');
        }

        // Check required registry entries
        if (!this.hasSetConfig) {
            results.errors.push('setConfig is required in taskConfig.ts');
            check.issues.push('Missing setConfig');
        }
        if (!this.hasGetCorpus) {
            results.warnings.push('getCorpus should be defined if task uses corpus data');
            check.issues.push('Missing getCorpus');
        }
        if (!this.hasGetTranslations) {
            results.errors.push('getTranslations is required in taskConfig.ts');
            check.issues.push('Missing getTranslations');
        }
        if (!this.hasBuildTaskTimeline) {
            results.errors.push('buildTaskTimeline is required in taskConfig.ts');
            check.issues.push('Missing buildTaskTimeline');
        }

        check.passed = check.issues.length === 0;
    }

    /**
     * Validate timeline implementation
     */
    async _validateTimeline(results) {
        const check = results.checks.timeline;

        if (!this.taskName) {
            check.issues.push('Cannot validate timeline without task name');
            return;
        }

        // Check if timeline file would exist at expected location
        const expectedPath = `core-tasks/task-launcher/src/tasks/${this.taskName}/timeline.ts`;
        results.info.push(`Timeline should exist at: ${expectedPath}`);

        // Placeholder for actual file check (would require API endpoint)
        check.passed = true; // Assume passed for now
    }

    /**
     * Validate corpus configuration
     */
    async _validateCorpus(results) {
        const check = results.checks.corpus;

        if (!this.corpusFile) {
            results.info.push('No corpus file specified (may not be required for this task)');
            check.passed = true;
            return;
        }

        // Check corpus file naming
        if (!this.corpusFile.endsWith('.csv')) {
            results.warnings.push('Corpus file should be a CSV file');
            check.issues.push('Non-CSV corpus file');
        }

        // Check CSV headers
        if (this.csvHeaders.length === 0) {
            results.warnings.push('No CSV headers specified - may cause issues reading corpus');
            check.issues.push('No CSV headers defined');
        }

        // Validate expected headers
        const requiredHeaders = ['task', 'item_id'];
        const missingRequired = requiredHeaders.filter(h => !this.csvHeaders.includes(h));
        
        if (missingRequired.length > 0) {
            results.warnings.push(`Missing recommended CSV headers: ${missingRequired.join(', ')}`);
            check.issues.push(`Missing headers: ${missingRequired.join(', ')}`);
        }

        // Check corpus file would be uploaded to correct location
        const devPath = `gs://levante-assets-dev/corpus/${this.taskName}/${this.corpusFile}`;
        const prodPath = `gs://levante-assets-prod/corpus/${this.taskName}/${this.corpusFile}`;
        results.info.push(`Corpus should be uploaded to:\n  Dev: ${devPath}\n  Prod: ${prodPath}`);

        check.passed = check.issues.length === 0;
    }

    /**
     * Validate visual assets
     */
    async _validateVisualAssets(results) {
        const check = results.checks.visualAssets;

        if (!this.hasVisualAssets) {
            results.info.push('Task does not use visual assets');
            check.passed = true;
            return;
        }

        // Check asset count
        if (this.visualAssetCount === 0) {
            results.warnings.push('Visual assets enabled but count is 0');
            check.issues.push('Zero visual assets specified');
        }

        // Check asset types
        if (this.visualAssetTypes.length === 0) {
            results.warnings.push('No visual asset types specified');
            check.issues.push('No asset type categories');
        }

        // Check expected location
        const expectedPath = `gs://levante-assets-{dev|prod}/visual/${this.taskName}/`;
        results.info.push(`Visual assets should be in: ${expectedPath}`);
        results.info.push(`Expected format: .webp files (${this.visualAssetCount} files)`);

        check.passed = check.issues.length === 0;
    }

    /**
     * Validate audio assets
     */
    async _validateAudioAssets(results) {
        const check = results.checks.audioAssets;

        if (!this.hasAudioAssets) {
            results.info.push('Task does not use audio assets');
            check.passed = true;
            return;
        }

        // Check required audio IDs
        if (this.requiredAudioIds.length === 0) {
            results.warnings.push('Audio assets enabled but no audio IDs specified');
            check.issues.push('No audio IDs listed');
        }

        // Validate audio ID format
        const invalidIds = this.requiredAudioIds.filter(id => {
            // Check for valid characters and format
            return !/^[a-z0-9-]+$/.test(id);
        });

        if (invalidIds.length > 0) {
            results.warnings.push(`Invalid audio ID format: ${invalidIds.slice(0, 3).join(', ')}${invalidIds.length > 3 ? '...' : ''}`);
            check.issues.push(`${invalidIds.length} invalid audio IDs`);
        }

        // Check asset count matches
        if (this.audioAssetCount > 0 && this.audioAssetCount !== this.requiredAudioIds.length) {
            const expected = this.audioAssetCount;
            const listed = this.requiredAudioIds.length;
            results.warnings.push(
                `Audio count mismatch: expected ${expected} total task-level audio files (from assets-per-task.json / existing-tasks.json), ` +
                `but you listed ${listed} IDs under "Required Audio Item IDs". ` +
                `Add the missing ${Math.max(0, expected - listed)} IDs here if they are task-level audios, or update the expected count if it is incorrect. ` +
                `Note: corpus-specific audio that varies per row should NOT be listed here.`
            );
            results.info.push('Upload location: gs://levante-assets-{dev|prod}/audio/<language>/ and definition file: audio/assets-per-task.json');
            check.issues.push('Audio count mismatch');
        }

        // Check assets-per-task.json update needed
        results.info.push(`Audio assets should be added to assets-per-task.json under "${this.taskName}"`);
        results.info.push(`Audio files should be uploaded to: gs://levante-assets-{dev|prod}/audio/<language>/`);

        check.passed = check.issues.length === 0;
    }

    /**
     * Validate translations
     */
    async _validateTranslations(results) {
        const check = results.checks.translations;

        if (this.translationKeys.length === 0) {
            results.errors.push('No translation keys specified - task will have no text');
            check.issues.push('No translation keys');
            return;
        }

        // Validate translation key format (should be camelCase)
        const invalidKeys = this.translationKeys.filter(key => {
            return !/^[a-z][a-zA-Z0-9]*$/.test(key);
        });

        if (invalidKeys.length > 0) {
            const exampleMappings = invalidKeys.slice(0, 5).map(key => {
                // Suggest camelCase conversion from kebab-case/snake-case
                const suggested = key
                    .replace(/[-_]+([a-zA-Z0-9])/g, (m, p1) => String(p1).toUpperCase())
                    .replace(/^[A-Z]/, s => s.toLowerCase());
                return { from: key, to: suggested };
            });
            results.warnings.push(`Invalid translation key format (should be camelCase): ${invalidKeys.slice(0, 3).join(', ')}${invalidKeys.length > 3 ? '...' : ''}`);
            results._warningContext.invalidTranslation = {
                total: invalidKeys.length,
                examples: exampleMappings,
                rule: 'Keys must be camelCase: start with a lowercase letter; only letters and digits thereafter. Hyphens/underscores are not allowed.',
                why: 'Translation keys are used as TypeScript object properties and must be consistent across code and CSV to resolve text at runtime.',
                howToFix: [
                    'Convert each key to camelCase (e.g., vocab-instruct-1 → vocabInstruct1).',
                    'Update the Required Translation Keys list to use the corrected names.',
                    'Ensure the corrected keys exist in item-bank-translations.csv for each target language.'
                ]
            };
            check.issues.push(`${invalidKeys.length} invalid translation keys`);
        }

        // Check for audio ID / translation key consistency
        const exempt = new Set(this.audioIdsWithoutText || []);
        const audioIdsWithoutTranslations = this.requiredAudioIds.filter(audioId => {
            if (exempt.has(audioId)) return false;
            const expectedKey = audioId.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
            return !this.translationKeys.includes(expectedKey);
        });

        if (audioIdsWithoutTranslations.length > 0) {
            const examplePairs = audioIdsWithoutTranslations.slice(0, 5).map(id => {
                const expectedKey = id.replace(/-([a-z0-9])/g, (g) => g[1].toUpperCase());
                return { audioId: id, expectedKey };
            });
            const missingKeys = audioIdsWithoutTranslations.map(id => id.replace(/-([a-z0-9])/g, (g) => g[1].toUpperCase()));
            const csvHeader = 'key,en,es-AR,es-CO,de,de-CH';
            const csvRows = missingKeys.slice(0, 10).map(k => `${k},"EN text here","ES-AR text","ES-CO text","DE text","DE-CH text"`).join('\n');

            results.warnings.push(
                `${audioIdsWithoutTranslations.length} audio IDs may not have corresponding translation keys. ` +
                `Examples: ${examplePairs.map(p => `${p.audioId} → ${p.expectedKey}`).join(', ')}. ` +
                `Add the missing camelCase keys to "Required Translation Keys" and ensure they exist in item-bank-translations.csv.`
            );
            results._warningContext.audioMissingTranslations = {
                total: audioIdsWithoutTranslations.length,
                examples: examplePairs,
                rule: 'For task-level audios, the default expected translation key is the kebab-case audio ID converted to camelCase (e.g., number-identification-1 → numberIdentification1).',
                caveats: [
                    'Not all audio requires a separate translation key (e.g., purely nonverbal sounds).',
                    'Corpus row-specific audio typically should not be listed as task-level required audio.'
                ],
                howToFix: [
                    'Add the missing camelCase keys to the Required Translation Keys list.',
                    'Confirm those keys exist in item-bank-translations.csv for each language.',
                    'If an audio should not have a translation key, list it under "Audio IDs Without Text" to exempt it from this check.'
                ],
                note: 'This check is heuristic. If your audio has no textual counterpart shown to the user, you can ignore or remove it from Required Audio.',
                bucketPaths: {
                    dev: `gs://levante-assets-dev/audio/<language>/...`,
                    prod: `gs://levante-assets-prod/audio/<language>/...`
                },
                csvPath: {
                    dev: `gs://levante-assets-dev/translations/item-bank-translations.csv`,
                    prod: `gs://levante-assets-prod/translations/item-bank-translations.csv`
                },
                missingKeys,
                csvSnippet: `${csvHeader}\n${csvRows}${missingKeys.length > 10 ? '\n...' : ''}`,
                source: this._hydrationMeta.audio || { source: 'form-or-existing-data' },
                conventions: {
                    idDefinition: 'Audio ID is the logical name used across code/CSV; file names typically follow audio/<language>/<audio-id>.mp3',
                    filenameExample: `audio/en/${(examplePairs[0]?.audioId) || 'task-intro'}.mp3 → translation key ${(examplePairs[0]?.expectedKey) || 'taskIntro'}`
                }
            };
            results.info.push('Rule: expected translation key is derived from the audio ID by converting kebab-case to camelCase (e.g., number-identification-1 → numberIdentification1).');
            check.issues.push('Potential audio/translation mismatch');
        }

        results.info.push(`Translations should be added to item-bank-translations.csv in Crowdin`);
        results.info.push(`Total translation keys: ${this.translationKeys.length}`);

        check.passed = check.issues.length === 0;
    }

    /**
     * Validate language support
     */
    async _validateLanguages(results) {
        const check = results.checks.languages;

        if (this.languages.length === 0) {
            results.errors.push('No languages selected - task must support at least one language');
            check.issues.push('No languages selected');
            return;
        }

        // Check English is included
        if (!this.languages.includes('en')) {
            results.warnings.push('English (en) should be included as the base language');
            check.issues.push('English not included');
        }

        // Validate language codes
        const validLanguages = ['en', 'es-AR', 'es-CO', 'de', 'de-CH'];
        const invalidLanguages = this.languages.filter(lang => !validLanguages.includes(lang));

        if (invalidLanguages.length > 0) {
            results.errors.push(`Invalid language codes: ${invalidLanguages.join(', ')}`);
            check.issues.push('Invalid language codes');
        }

        results.info.push(`Languages supported: ${this.languages.join(', ')}`);
        results.info.push(`Each language requires: ${this.requiredAudioIds.length} audio files + ${this.translationKeys.length} translations`);

        check.passed = check.issues.length === 0;
    }

    /**
     * Validate variants configuration
     */
    async _validateVariants(results) {
        const check = results.checks.variants;

        if (!this.hasVariants) {
            results.info.push('Task does not have variants');
            check.passed = true;
            return;
        }

        if (this.variants.length === 0) {
            results.warnings.push('Variants enabled but none specified');
            check.issues.push('No variants defined');
            return;
        }

        results.info.push(`Variants defined: ${this.variants.length}`);
        results.info.push('Variants should only override fields that differ from the base configuration');

        check.passed = check.issues.length === 0;
    }

    /**
     * Generate a validation report as HTML
     */
    getValidationReport() {
        if (!this._validationResults) {
            return '<p>No validation has been run yet. Call task.validate() first.</p>';
        }

        const results = this._validationResults;
        let html = '<div class="validation-report">';

        // Overall status
        html += '<div class="validation-summary">';
        if (results.isValid) {
            html += '<h3 class="status-success"><i class="fas fa-check-circle"></i> Task Configuration Valid</h3>';
        } else {
            html += '<h3 class="status-error"><i class="fas fa-exclamation-circle"></i> Task Has Issues</h3>';
        }
        html += `<p>Errors: ${results.errors.length} | Warnings: ${results.warnings.length} | Info: ${results.info.length}</p>`;
        html += '</div>';

        // Errors
        if (results.errors.length > 0) {
            html += '<div class="validation-section validation-errors">';
            html += '<h4><i class="fas fa-times-circle"></i> Errors (Must Fix)</h4>';
            html += '<ul>';
            results.errors.forEach(error => {
                html += `<li>${this._escapeHtml(error)}</li>`;
            });
            html += '</ul></div>';
        }

        // Warnings
        if (results.warnings.length > 0) {
            html += '<div class="validation-section validation-warnings">';
            html += '<h4><i class="fas fa-exclamation-triangle"></i> Warnings (Should Fix)</h4>';
            html += '<ul>';
            results.warnings.forEach(warning => {
                html += `<li>${this._escapeHtml(warning)}</li>`;
            });
            html += '</ul></div>';
        }

        // Info
        if (results.info.length > 0) {
            html += '<div class="validation-section validation-info">';
            html += '<h4><i class="fas fa-info-circle"></i> Information</h4>';
            html += '<ul>';
            results.info.forEach(info => {
                html += `<li>${this._escapeHtml(info).replace(/\n/g, '<br>')}</li>`;
            });
            html += '</ul></div>';
        }

        // Detailed check results
        html += '<div class="validation-checks">';
        html += '<h4><i class="fas fa-clipboard-check"></i> Detailed Checks</h4>';
        html += '<div class="checks-grid">';

        Object.entries(results.checks).forEach(([checkName, checkResult]) => {
            const statusClass = checkResult.passed ? 'check-passed' : 'check-failed';
            const statusIcon = checkResult.passed ? 'fa-check' : 'fa-times';
            
            html += `<div class="check-item ${statusClass}">`;
            html += `<div class="check-header">`;
            html += `<i class="fas ${statusIcon}"></i> ${this._formatCheckName(checkName)}`;
            html += `</div>`;
            
            if (checkResult.issues.length > 0) {
                html += '<ul class="check-issues">';
                checkResult.issues.forEach(issue => {
                    html += `<li>${this._escapeHtml(issue)}</li>`;
                });
                html += '</ul>';
            }
            html += '</div>';
        });

        html += '</div></div>';
        html += '</div>';

        return html;
    }

    /**
     * Export task as JSON
     */
    toJSON() {
        return {
            taskName: this.taskName,
            registryKey: this.registryKey,
            description: this.description,
            trialType: this.trialType,
            assessmentStage: this.assessmentStage,
            corpusFile: this.corpusFile,
            notes: this.notes,
            hasVisualAssets: this.hasVisualAssets,
            visualAssetCount: this.visualAssetCount,
            visualAssetTypes: this.visualAssetTypes,
            visualAssetsList: this.visualAssetsList,
            hasAudioAssets: this.hasAudioAssets,
            audioAssetCount: this.audioAssetCount,
            requiredAudioIds: this.requiredAudioIds,
            sharedAudioIds: this.sharedAudioIds,
            translationKeys: this.translationKeys,
            languages: this.languages,
            hasVariants: this.hasVariants,
            variants: this.variants,
            bucketNameDev: this.bucketNameDev,
            bucketNameProd: this.bucketNameProd,
            csvHeaders: this.csvHeaders
        };
    }

    // Helper methods

    _setFieldValue(formElement, fieldId, value) {
        const field = formElement.querySelector(`#${fieldId}`);
        if (field) {
            field.value = value || '';
        }
    }

    _setCheckbox(formElement, fieldId, checked) {
        const checkbox = formElement.querySelector(`#${fieldId}`);
        if (checkbox) {
            checkbox.checked = checked;
        }
    }

    _toggleVisibility(elementId, show) {
        const element = document.getElementById(elementId);
        if (element) {
            element.style.display = show ? 'block' : 'none';
        }
    }

    _clearAllCsvHeaders(formElement) {
        const checkboxIds = [
            'csv_task', 'csv_trial_type', 'csv_item', 'csv_item_id', 'csv_item_uid',
            'csv_audio_file', 'csv_response_alternatives', 'csv_assessment_stage',
            'csv_time_limit', 'csv_difficulty'
        ];

        checkboxIds.forEach(id => {
            const checkbox = formElement.querySelector(`#${id}`);
            if (checkbox) checkbox.checked = false;
        });
    }

    _selectCsvHeaders(formElement, headers) {
        const checkboxMapping = {
            'task': 'csv_task',
            'trial_type': 'csv_trial_type',
            'item': 'csv_item',
            'item_id': 'csv_item_id',
            'item_uid': 'csv_item_uid',
            'audio_file': 'csv_audio_file',
            'response_alternatives': 'csv_response_alternatives',
            'assessment_stage': 'csv_assessment_stage',
            'time_limit': 'csv_time_limit',
            'difficulty': 'csv_difficulty'
        };

        headers.forEach(header => {
            const checkboxId = checkboxMapping[header];
            if (checkboxId) {
                const checkbox = formElement.querySelector(`#${checkboxId}`);
                if (checkbox) checkbox.checked = true;
            }
        });
    }

    _clearAllLanguages(formElement) {
        const checkboxes = formElement.querySelectorAll('input[name="languages"]');
        checkboxes.forEach(cb => cb.checked = false);
    }

    _selectLanguages(formElement, languages) {
        languages.forEach(lang => {
            const checkbox = formElement.querySelector(`#lang_${lang.replace('-', '_')}`);
            if (checkbox) checkbox.checked = true;
        });
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    _formatCheckName(name) {
        return name.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase());
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Task;
}

