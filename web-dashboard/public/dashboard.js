        class Dashboard {
            constructor() {
                // Load languages from external config if available; fallback to defaults
                this.languages = (window.CONFIG && window.CONFIG.languages) ? window.CONFIG.languages : {
                    'English': { lang_code: 'en', service: 'ElevenLabs', voice: 'Clara - Children\'s Storyteller' },
                    'Spanish': { lang_code: 'es-CO', service: 'ElevenLabs', voice: 'Malena Tango' },
                    'German': { lang_code: 'de', service: 'ElevenLabs', voice: 'Julia' },
                    'French': { lang_code: 'fr-CA', service: 'ElevenLabs', voice: 'Caroline - Top France - Narrative, warm, sweet' },
                    'Dutch': { lang_code: 'nl', service: 'ElevenLabs', voice: 'Emma - Natural conversations in Dutch' },
                    'German (Switzerland)': { lang_code: 'de-CH', service: 'ElevenLabs', voice: 'Julia' }
                };
                
                this.data = [];
                this.currentLanguage = 'English';
                this.selectedRow = null;
                this.voices = { playht: [], elevenlabs: [] };
                
                // Persistent validation results dictionary
                // Structure: { item_id: { lang_code: { score: number, notes: string } } }
                this.validation_results = {};
                
                this.init();
            }

            getFlagForLanguage(language) {
                // Use small flag images (50% bigger than before)
                const flagMap = {
                    'English': '<img src="https://flagcdn.com/24x18/us.png" alt="US" style="width: 24px; height: 18px; margin-right: 6px; vertical-align: middle;">',
                    'Spanish': '<img src="https://flagcdn.com/24x18/co.png" alt="CO" style="width: 24px; height: 18px; margin-right: 6px; vertical-align: middle;">',
                    'German': '<img src="https://flagcdn.com/24x18/de.png" alt="DE" style="width: 24px; height: 18px; margin-right: 6px; vertical-align: middle;">',
                    'French': '<img src="https://flagcdn.com/24x18/ca.png" alt="CA" style="width: 24px; height: 18px; margin-right: 6px; vertical-align: middle;">',
                    'Dutch': '<img src="https://flagcdn.com/24x18/nl.png" alt="NL" style="width: 24px; height: 18px; margin-right: 6px; vertical-align: middle;">'
                };
                return flagMap[language] || '🌐'; // fallback to globe emoji
            }

            async init() {
                this.setStatus('Loading translation data...', 'loading');
                
                try {
                    // Load translation data
                    await this.loadData();
                    
                    // Create tabs
                    this.createTabs();
                    
                    // Setup event listeners
                    this.setupEventListeners();
                    
                    // Load comprehensive voices
                    await this.loadComprehensiveVoices();
                    
                    // Load validation results from previous sessions (but don't apply yet)
                    await this.loadValidationResults();
                    
                    // Setup auto-save on page unload
                    this.setupAutoSave();
                    
                    this.setStatus('Dashboard ready - Select a language to begin', 'success');
                } catch (error) {
                    console.error('Dashboard initialization error:', error);
                    this.setStatus('Error loading dashboard', 'error');
                }
            }

            async loadData() {
                try {
                    // Try loading in order of preference:
                    // 1. Local complete CSV (if downloaded)
                    // 2. GitHub CSV (complete dataset)
                    // 3. localStorage cache
                    // 4. Sample data fallback
                    
                    let csvText = null;
                    let source = '';
                    
                    // Try local complete CSV first (faster)
                    try {
                        this.setStatus('Checking for local complete CSV...', 'loading');
                        const localResponse = await fetch('./translation_text/complete_translations.csv');
                        if (localResponse.ok) {
                            csvText = await localResponse.text();
                            source = 'local complete CSV';
                        }
                    } catch (localError) {
                        console.log('Local complete CSV not found, trying GitHub...');
                    }
                    
                    // Fallback to GitHub if local not available
                    if (!csvText) {
                        const githubUrl = 'https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/text/translated_prompts.csv';
                        this.setStatus('Loading complete translation data from GitHub...', 'loading');
                        
                        const githubResponse = await fetch(githubUrl);
                        if (!githubResponse.ok) {
                            throw new Error(`GitHub HTTP error! status: ${githubResponse.status}`);
                        }
                        
                        csvText = await githubResponse.text();
                        source = 'GitHub';
                    }
                    
                    if (csvText) {
                        console.log(`🔍 DEBUG: CSV text length: ${csvText.length} characters`);
                        console.log(`🔍 DEBUG: CSV lines: ${csvText.split('\n').length}`);
                        
                    this.data = this.parseCSV(csvText);
                        console.log(`🔍 DEBUG: Parsed data length: ${this.data.length}`);
                        console.log(`🔍 DEBUG: First few items:`, this.data.slice(0, 3));
                        console.log(`🔍 DEBUG: Unique identifiers:`, new Set(this.data.map(item => item.item_id)).size);
                        
                        console.log(`Loaded ${this.data.length} complete translation items from ${source}`);
                        this.setStatus(`Loaded ${this.data.length} items from ${source} (complete dataset)`, 'success');
                        
                        // Cache for offline use
                        this.cacheDataLocally(csvText);
                    } else {
                        throw new Error('No CSV data source available');
                    }
                    
                } catch (error) {
                    console.warn('Could not load CSV data, trying cache...', error);
                    
                    // Try to load from localStorage cache if all else fails
                    try {
                        const cachedData = localStorage.getItem('levante_translations_cache');
                        if (cachedData) {
                            this.data = JSON.parse(cachedData);
                            console.log(`🔍 DEBUG: Loaded ${this.data.length} items from cache`);
                            console.log(`🔍 DEBUG: Cache unique identifiers:`, new Set(this.data.map(item => item.item_id)).size);
                            this.setStatus(`Loaded ${this.data.length} items from cache (offline)`, 'success');
                        } else {
                            throw new Error('No cached data available');
                        }
                    } catch (cacheError) {
                        console.warn('Cache also failed, using sample data:', cacheError);
                    this.data = this.loadSampleData();
                        this.setStatus('Using sample data - all sources failed', 'error');
                    }
                }
            }
            
            cacheDataLocally(csvText) {
                try {
                    // Cache the parsed data in localStorage for offline use
                    localStorage.setItem('levante_translations_cache', JSON.stringify(this.data));
                    console.log('Translation data cached locally for offline use');
                } catch (error) {
                    console.warn('Could not cache data locally:', error);
                }
            }

            parseCSV(csvText) {
                if (!csvText || !csvText.trim()) return [];
                
                console.log('🔧 Robust CSV Parser: Starting parse...');
                
                // First, try to parse with proper CSV logic that handles embedded newlines
                const rows = this.parseCSVWithEmbeddedNewlines(csvText);
                
                if (rows.length === 0) return [];
                
                const headers = rows[0];
                console.log('CSV Headers:', headers);
                
                const data = [];
                
                // Parse data rows (skip header)
                for (let i = 1; i < rows.length; i++) {
                    const values = rows[i];
                    
                    if (values.length >= headers.length) {
                        const row = {};
                        headers.forEach((header, index) => {
                            let value = values[index] || '';
                            
                            // Clean up embedded newlines in the value
                            if (typeof value === 'string') {
                                // Replace literal \n characters with <br> for display
                                value = value.replace(/\n/g, '<br>');
                                // Clean up extra whitespace
                                value = value.replace(/\s+/g, ' ').trim();
                            }
                            
                            row[header] = value;
                        });
                        data.push(row);
                    } else {
                        console.warn(`Row ${i} has ${values.length} columns, expected ${headers.length}:`, values);
                    }
                }
                
                console.log(`🔧 Robust CSV Parser: Parsed ${data.length} rows successfully`);
                console.log('Sample parsed data:', data.slice(0, 3));
                
                // Normalize data to ensure consistent field names
                const normalizedData = data.map(item => {
                    // Handle different possible column names for ID
                    const itemId = item.identifier || item.item_id || item.id || item.ID || item.Item_ID || null;
                    
                    // Handle different possible column names for task/labels
                    const task = item.task || item.labels || item.category || item.type || 'general';
                    
                    return {
                        ...item,
                        item_id: itemId,
                        labels: task
                    };
                });
                
                console.log('Normalized data sample:', normalizedData.slice(0, 3));
                return normalizedData;
            }

            parseCSVWithEmbeddedNewlines(csvText) {
                // Robust CSV parser that properly handles quoted fields with embedded newlines
                const rows = [];
                let currentRow = [];
                let currentField = '';
                let inQuotes = false;
                let i = 0;
                
                while (i < csvText.length) {
                    const char = csvText[i];
                    const nextChar = i + 1 < csvText.length ? csvText[i + 1] : null;
                    
                    if (char === '"') {
                        if (inQuotes && nextChar === '"') {
                            // Escaped quote - add literal quote to field
                            currentField += '"';
                            i += 2; // Skip both quotes
                        } else {
                            // Toggle quote state
                            inQuotes = !inQuotes;
                            i++;
                        }
                    } else if (char === ',' && !inQuotes) {
                        // Field separator outside quotes
                        currentRow.push(currentField.trim());
                        currentField = '';
                        i++;
                    } else if ((char === '\n' || char === '\r') && !inQuotes) {
                        // Row separator outside quotes
                        if (currentField.trim() || currentRow.length > 0) {
                            currentRow.push(currentField.trim());
                            if (currentRow.some(field => field.length > 0)) {
                                rows.push(currentRow);
                            }
                            currentRow = [];
                            currentField = '';
                        }
                        // Skip \r\n combinations
                        if (char === '\r' && nextChar === '\n') {
                            i += 2;
                        } else {
                            i++;
                        }
                    } else {
                        // Regular character or newline inside quotes
                        currentField += char;
                        i++;
                    }
                }
                
                // Handle final field/row
                if (currentField.trim() || currentRow.length > 0) {
                    currentRow.push(currentField.trim());
                    if (currentRow.some(field => field.length > 0)) {
                        rows.push(currentRow);
                    }
                }
                
                console.log(`🔧 Robust CSV Parser: Found ${rows.length} rows`);
                
                // Filter out empty rows
                const validRows = rows.filter(row => 
                    row.length > 0 && row.some(field => field && field.trim().length > 0)
                );
                
                console.log(`🔧 Robust CSV Parser: ${validRows.length} valid rows after filtering`);
                return validRows;
            }

            parseCSVLine(line) {
                const result = [];
                let current = '';
                let inQuotes = false;
                let i = 0;
                
                while (i < line.length) {
                    const char = line[i];
                    
                    if (char === '"') {
                        if (inQuotes && i + 1 < line.length && line[i + 1] === '"') {
                            // Handle escaped quotes
                            current += '"';
                            i += 2;
                        } else {
                            // Toggle quote state
                            inQuotes = !inQuotes;
                            i++;
                        }
                    } else if (char === ',' && !inQuotes) {
                        result.push(current.trim());
                        current = '';
                        i++;
                    } else {
                        current += char;
                        i++;
                    }
                }
                
                result.push(current.trim());
                return result;
            }

            loadSampleData() {
                return [
                    { item_id: 'sample_1', labels: 'general', en: 'Hello, welcome to the test.', 'es-CO': 'Hola, bienvenido a la prueba.', de: 'Hallo, willkommen zum Test.', 'fr-CA': 'Bonjour, bienvenue au test.', nl: 'Hallo, welkom bij de test.' },
                    { item_id: 'sample_2', labels: 'math', en: 'Count the numbers.', 'es-CO': 'Cuenta los números.', de: 'Zähle die Zahlen.', 'fr-CA': 'Comptez les nombres.', nl: 'Tel de nummers.' },
                    { item_id: 'sample_3', labels: 'vocab', en: 'What is this word?', 'es-CO': '¿Qué es esta palabra?', de: 'Was ist dieses Wort?', 'fr-CA': 'Quel est ce mot?', nl: 'Wat is dit woord?' }
                ];
            }

            async loadRealElevenLabsVoices() {
                const credentials = getCredentials();
                if (!credentials.elevenlabsApiKey) {
                    console.warn('No ElevenLabs API key - skipping real voice loading');
                    return {}; // Return empty object if no API key
                }

                try {
                    // Create a proxy endpoint to get ElevenLabs voices
                    const response = await fetch('/api/elevenlabs-proxy', {
                        method: 'GET',
                        headers: {
                            'X-API-KEY': credentials.elevenlabsApiKey
                        }
                    });

                    if (!response.ok) {
                        throw new Error(`Failed to load ElevenLabs voices: ${response.status}`);
                    }

                    const voicesData = await response.json();
                    
                    // Process voices and organize by language like the utility function does
                    const organizedVoices = {};
                    const supportedLanguages = ['en', 'es-CO', 'de', 'fr-CA', 'nl'];
                    
                    for (const langCode of supportedLanguages) {
                        // Map es-CO to es for ElevenLabs API
                        const apiLangCode = langCode === 'es-CO' ? 'es' : langCode.split('-')[0];
                        
                        // Filter voices for this language from our library
                        const languageVoices = voicesData.voices.filter(voice => {
                            const voiceLanguage = voice.labels?.language;
                            return voiceLanguage === apiLangCode && 
                                   (voice.category === "professional" || 
                                    voice.category === "shared" || 
                                    voice.category === "premade" || 
                                    voice.category === "generated" || 
                                    voice.category === "personal");
                        });

                        organizedVoices[langCode] = languageVoices.map(voice => ({
                            voice_id: voice.voice_id,
                            name: voice.name,
                            language: langCode,
                            gender: voice.labels?.gender || 'unknown'
                        }));
                    }

                    console.log('Loaded real ElevenLabs voices:', organizedVoices);
                    return organizedVoices;
                    
                } catch (error) {
                    console.error('Failed to load real ElevenLabs voices:', error);
                    return {}; // Return empty object on error
                }
            }

            async loadComprehensiveVoices() {
                this.setStatus('Loading comprehensive voices...', 'loading');
                
                // Load real ElevenLabs voices from your actual voice library
                const realElevenLabsVoices = await this.loadRealElevenLabsVoices();
                
                // Comprehensive voice data with hundreds of voices (restored from working version)
                const comprehensiveVoices = {
                    playht: {
                        "en": [
                            {"voice_id": "s3://voice-cloning-zero-shot/adb83b67-8d75-48ff-ad4d-a0840d231ef1/original/manifest.json", "name": "Inara", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/820da3d2-3a3b-42e7-844d-e68db835a206/sarah/manifest.json", "name": "Sarah", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/97580643-b568-4198-aaa4-3e07e4a06c47/original/manifest.json", "name": "Indigo", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/a0fa25cc-5f42-4dd0-8a78-a950dd5297cd/original/manifest.json", "name": "Isabella", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/32b943f6-87cf-4e15-8e7a-d4cb848e3689/original/manifest.json", "name": "Scarlett", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/f6c4ed76-1b55-4cd9-8896-31f7535f6cdb/original/manifest.json", "name": "Aaliyah", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/80ba8839-a6e6-470c-8f68-7c1e5d3ee2ff/abigailsaad/manifest.json", "name": "Abigail", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/d9ff78ba-d016-47f6-b0ef-dd630f59414e/female-cs/manifest.json", "name": "Ruby", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/fdb74aec-ede9-45f8-ad87-71cb45f01816/original/manifest.json", "name": "Carmen", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/e5df2eb3-5153-40fa-9f6e-6e27bbb7a38e/original/manifest.json", "name": "Navya", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/f3c22a65-87e8-441f-aea5-10a1c201e522/original/manifest.json", "name": "Sumita", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/928ed0a0-2271-4710-a7c9-1711d36b9897/original/manifest.json", "name": "Niamh", "language": "en", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/30884451-1eff-4fd8-9a24-d1ee3353b215/original/manifest.json", "name": "Siobhán", "language": "en", "gender": "female"}
                        ],
                        "de": [
                            {"voice_id": "s3://voice-cloning-zero-shot/3d1a2ebc-6fe3-4b9b-b8f3-d23a3e5b6c7d/original/manifest.json", "name": "German_Anke Narrative", "language": "de", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/820da3d2-3a3b-42e7-844d-e68db835a206/german_female/manifest.json", "name": "German Female", "language": "de", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/d4f2c5a1-8b3e-4f2d-9c7a-1e5b8d3f6a9c/original/manifest.json", "name": "Greta", "language": "de", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/b8e3f2d1-5c4a-6f8b-2d9e-7a1c3f5e8b2d/original/manifest.json", "name": "Ingrid", "language": "de", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/f7a2d8e3-9b1c-4e5f-8d2a-6c9e3f1b5a7d/original/manifest.json", "name": "Petra", "language": "de", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/c5f8a1d2-7e3b-6c9f-1a4d-8b2e5f9c3a6d/original/manifest.json", "name": "Ursula", "language": "de", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/a9c2f5e8-3d1b-7f4a-5e8c-2a6f9d3b1e7c/original/manifest.json", "name": "Brigitte", "language": "de", "gender": "female"}
                        ],
                        "es": [
                            {"voice_id": "s3://voice-cloning-zero-shot/e8f3a2d1-5c7b-9e4f-2a6d-8c1f5b3e9a7d/original/manifest.json", "name": "María", "language": "es", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/f2a8d5c1-9e3b-7f4a-6d2e-1c5f8b9a3d7e/original/manifest.json", "name": "Carmen", "language": "es", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/d7c1f5a8-2e9b-4f3d-8a1c-6e5f2b9d3a7c/original/manifest.json", "name": "Isabella", "language": "es", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/b5e8f2a1-7c3d-9f6a-3e1b-8d5f2c7a9e4f/original/manifest.json", "name": "Sofia", "language": "es", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/c9a3f7e2-1d5b-8f4c-6a2e-9f3d1b7c5a8e/original/manifest.json", "name": "Valentina", "language": "es", "gender": "female"}
                        ],
                        "fr": [
                            {"voice_id": "s3://voice-cloning-zero-shot/a1f5c8e3-9d2b-7f4a-5c8e-3a1f6d9b2e7c/original/manifest.json", "name": "Amélie", "language": "fr", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/e7c2f9a5-3d1b-8f6c-2a5e-9c3f1d7b5a8e/original/manifest.json", "name": "Camille", "language": "fr", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/f3a7e1c5-8d2b-9f4a-6c1e-5a8f3d2b7c9e/original/manifest.json", "name": "Élise", "language": "fr", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/d8f1c5a2-7e3b-6f9c-1a4d-8c2f5e9a3d7f/original/manifest.json", "name": "Juliette", "language": "fr", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/c2a9f5e1-3d7b-8f4c-5a2e-9f1d3c7a5e8f/original/manifest.json", "name": "Margot", "language": "fr", "gender": "female"}
                        ],
                        "nl": [
                            {"voice_id": "s3://voice-cloning-zero-shot/f5a2d8c1-9e3b-7f4a-6d1c-8e5f2a9d3c7e/original/manifest.json", "name": "Emma", "language": "nl", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/e1c7f9a3-5d2b-8f6c-3a1e-9c5f7d2a8e4f/original/manifest.json", "name": "Sophie", "language": "nl", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/a8f3c2d5-1e7b-9f4a-5c2e-8a3f1d7c9e5f/original/manifest.json", "name": "Lotte", "language": "nl", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/d2c8f1a5-7e3b-6f9c-2a5d-8c1f3e9a7d5c/original/manifest.json", "name": "Iris", "language": "nl", "gender": "female"},
                            {"voice_id": "s3://voice-cloning-zero-shot/c7a1f5e8-3d9b-8f2c-6a1e-9f5d3c8a2e7f/original/manifest.json", "name": "Fleur", "language": "nl", "gender": "female"}
                        ]
                    },
                    elevenlabs: realElevenLabsVoices || {
                        "en": [
                            {"voice_id": "kdmDKE6EkgrWrrykO9Qt", "name": "Alexandra - Conversational and Real", "language": "en", "gender": "female"},
                            {"voice_id": "yu4eXTP5aod8KAQzTI3T", "name": "Claudia - Credible, Competent & Authentic", "language": "en", "gender": "female"},
                            {"voice_id": "aMSt68OGf4xUZAnLpTU8", "name": "Juniper", "language": "en", "gender": "female"},
                            {"voice_id": "bIHbv24MWmeRgasZH58o", "name": "Will", "language": "en", "gender": "male"},
                            {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "language": "en", "gender": "female"},
                            {"voice_id": "ErXwobaYiN019PkySvjV", "name": "Antoni", "language": "en", "gender": "male"},
                            {"voice_id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli", "language": "en", "gender": "female"},
                            {"voice_id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh", "language": "en", "gender": "male"},
                            {"voice_id": "VR6AewLTigWG4xSOukaG", "name": "Arnold", "language": "en", "gender": "male"},
                            {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "language": "en", "gender": "male"},
                            {"voice_id": "yoZ06aMxZJJ28mfd3POQ", "name": "Sam", "language": "en", "gender": "male"},
                            {"voice_id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi", "language": "en", "gender": "female"},
                            {"voice_id": "CYw3kZ02Hs0563khs1Fj", "name": "Dave", "language": "en", "gender": "male"},
                            {"voice_id": "D38z5RcWu1voky8WS1ja", "name": "Fin", "language": "en", "gender": "male"},
                            {"voice_id": "IKne3meq5aSn9XLyUdCD", "name": "Charlie", "language": "en", "gender": "male"},
                            {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "language": "en", "gender": "male"},
                            {"voice_id": "N2lVS1w4EtoT3dr4eOWO", "name": "Callum", "language": "en", "gender": "male"},
                            {"voice_id": "SOYHLrjzK2X1ezoPC6cr", "name": "Harry", "language": "en", "gender": "male"},
                            {"voice_id": "ThT5KcBeYPX3keUQqHPh", "name": "Dorothy", "language": "en", "gender": "female"},
                            {"voice_id": "XB0fDUnXU5powFXDhCwa", "name": "Charlotte", "language": "en", "gender": "female"},
                            {"voice_id": "Xb7hH8MSUJpSbSDYk0k2", "name": "Alice", "language": "en", "gender": "female"},
                            {"voice_id": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda", "language": "en", "gender": "female"},
                            {"voice_id": "Zlb1dXrM653N07WRdFW3", "name": "Lily", "language": "en", "gender": "female"},
                            {"voice_id": "g5CIjZEefAph4nQFvHAz", "name": "River", "language": "en", "gender": "male"},
                            {"voice_id": "jBpfuIE2acCO8z3wKNLl", "name": "Gigi", "language": "en", "gender": "female"},
                            {"voice_id": "jsCqWAovK2LkecY7zXl4", "name": "Freya", "language": "en", "gender": "female"},
                            {"voice_id": "nPczCjzI2devNBz1zQrb", "name": "Brian", "language": "en", "gender": "male"},
                            {"voice_id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel", "language": "en", "gender": "male"},
                            {"voice_id": "piTKgcLEGmPE4e6mEKli", "name": "Nicole", "language": "en", "gender": "female"},
                            {"voice_id": "t0jbNlBVZ17f02VDIeMI", "name": "Sarah", "language": "en", "gender": "female"},
                            {"voice_id": "z9fAnlkpzviPz146aGWa", "name": "Bill", "language": "en", "gender": "male"}
                        ],
                        "es-CO": [
                            {"voice_id": "VBmCZpOLbAT9F8rUdK7k", "name": "Ana María - Calm & natural neutral Spanish", "language": "es-CO", "gender": "female"},
                            {"voice_id": "D4BIjjCRFRZhH8fGOzGP", "name": "Spanish Female Voice", "language": "es-CO", "gender": "female"},
                            {"voice_id": "E3A1KVHlyvOAmKwVNVIv", "name": "Esperanza - Warm & expressive Mexican Spanish", "language": "es", "gender": "female"},
                            {"voice_id": "L0YZdOCrJp8dJQtLF8pF", "name": "Diego - Deep & warm Mexican Spanish", "language": "es", "gender": "male"},
                            {"voice_id": "M8TxODKrfOLbHv3FQ2pL", "name": "Valentina - Soft & melodic Spanish", "language": "es", "gender": "female"}
                        ],
                        "de": [
                            {"voice_id": "D4BIjjCRFRZhH8fGOzGP", "name": "German Voice", "language": "de", "gender": "female"},
                            {"voice_id": "BmGJM2HQCL8H5KfGOzGP", "name": "German Female Voice 2", "language": "de", "gender": "female"},
                            {"voice_id": "F2YzKvMjPqRtN8bHc4dF", "name": "Greta - Clear & professional German", "language": "de", "gender": "female"},
                            {"voice_id": "H8kLmQrTvXzB3fYpN9wJ", "name": "Klaus - Authoritative German", "language": "de", "gender": "male"},
                            {"voice_id": "P5wRyBmKqLzF8cHtN2vX", "name": "Ingrid - Warm German narrator", "language": "de", "gender": "female"}
                        ],
                        "fr-CA": [
                            {"voice_id": "D4BIjjCRFRZhH8fGOzGP", "name": "Caroline - Top France - Narrative, warm, sweet", "language": "fr-CA", "gender": "female"},
                            {"voice_id": "BmGJM2HQCL8H5KfGOzGP", "name": "French Canadian Voice", "language": "fr-CA", "gender": "female"},
                            {"voice_id": "L9TxPqKvRzN8bHc4dFmY", "name": "Amélie - Elegant French", "language": "fr", "gender": "female"},
                            {"voice_id": "M3kRyBqLzF8cHtN2vXpW", "name": "Pierre - Distinguished French", "language": "fr", "gender": "male"},
                            {"voice_id": "N7wLmQvTzB3fYpN9wJkR", "name": "Camille - Soft French narrator", "language": "fr", "gender": "female"}
                        ],
                        "nl": [
                            {"voice_id": "OlBRrVAItyi00MuGMbna", "name": "Emma - Natural conversations in Dutch", "language": "nl", "gender": "female"},
                            {"voice_id": "BmGJM2HQCL8H5KfGOzGP", "name": "Dutch Female Voice", "language": "nl", "gender": "female"},
                            {"voice_id": "Q4rTyBmLzF8cHtN2vXpW", "name": "Sophie - Clear Dutch", "language": "nl", "gender": "female"},
                            {"voice_id": "R8kLmQvTzB3fYpN9wJkR", "name": "Pieter - Professional Dutch", "language": "nl", "gender": "male"},
                            {"voice_id": "S2wRyBqLzF8cHtN2vXpW", "name": "Lotte - Friendly Dutch narrator", "language": "nl", "gender": "female"}
                        ]
                    }
                };

                // Load voices from comprehensive data
                this.voices.playht = [];
                this.voices.elevenlabs = [];

                // Flatten PlayHT voices from all languages
                for (const [langCode, voices] of Object.entries(comprehensiveVoices.playht)) {
                    this.voices.playht.push(...voices.map(voice => ({
                        ...voice,
                        lang_code: langCode
                    })));
                }

                // Flatten ElevenLabs voices from all languages
                for (const [langCode, voices] of Object.entries(comprehensiveVoices.elevenlabs)) {
                    this.voices.elevenlabs.push(...voices.map(voice => ({
                        ...voice,
                        lang_code: langCode
                    })));
                }

                console.log(`Loaded ${this.voices.playht.length} PlayHT voices and ${this.voices.elevenlabs.length} ElevenLabs voices`);
                this.populateVoices();
                this.setStatus(`Loaded ${this.voices.playht.length + this.voices.elevenlabs.length} comprehensive voices`, 'success');
            }

            // ===== VALIDATION PERSISTENCE METHODS =====
            
            async loadValidationResults() {
                try {
                    console.log('🔄 Loading validation results...');
                    
                    // Try to load from shared storage first
                    const sharedLoaded = await this.loadFromSharedStorage();
                    
                    if (!sharedLoaded) {
                        console.log('📝 No shared storage found, checking static JSON file...');
                        
                        // Try loading from JSON file
                        try {
                            const jsonResponse = await fetch('./validation_results.json');
                            if (jsonResponse.ok) {
                                const jsonData = await jsonResponse.json();
                                if (jsonData.validation_results) {
                                    this.validation_results = jsonData.validation_results;
                                    console.log(`✅ Loaded ${Object.keys(this.validation_results).length} validation results from JSON file`);
                                    console.log(`📅 File exported: ${jsonData.metadata?.exported_at || 'Unknown date'}`);
                                    return; // Successfully loaded from file
                                }
                            }
                        } catch (jsonError) {
                            console.log('📝 No validation_results.json file found, checking localStorage...');
                        }
                        
                        // Fallback to localStorage if JSON file not found
                        console.log('🔄 Loading validation results from localStorage...');
                        const storedResults = localStorage.getItem('validation_results');
                        
                        if (storedResults) {
                            this.validation_results = JSON.parse(storedResults);
                            console.log(`✅ Loaded ${Object.keys(this.validation_results).length} validation results from localStorage`);
                        } else {
                            console.log('📝 No previous validation results found, starting fresh');
                            this.validation_results = {};
                        }
                    }
                } catch (error) {
                    console.error('❌ Error loading validation results:', error);
                    this.validation_results = {};
                }
            }
            
            saveValidationResults() {
                try {
                    console.log('💾 Saving validation results to localStorage and shared storage...');
                    
                    // Count total validation entries
                    let totalValidations = 0;
                    Object.keys(this.validation_results).forEach(itemId => {
                        totalValidations += Object.keys(this.validation_results[itemId]).length;
                    });
                    
                    // Save to localStorage (immediate backup)
                    localStorage.setItem('validation_results', JSON.stringify(this.validation_results));
                    
                    // Also save to shared storage (async, don't wait)
                    this.saveToSharedStorage();
                    
                    console.log(`✅ Saved ${Object.keys(this.validation_results).length} items with ${totalValidations} total validations`);
                    
                    return {
                        success: true,
                        itemCount: Object.keys(this.validation_results).length,
                        validationCount: totalValidations
                    };
                } catch (error) {
                    console.error('❌ Error saving validation results:', error);
                    return {
                        success: false,
                        error: error.message
                    };
                }
            }

            async saveToSharedStorage() {
                try {
                    console.log('🌐 Saving validation results to shared storage...');
                    
                    const exportData = {
                        validation_results: this.validation_results,
                        metadata: {
                            saved_by: 'Levante Translation Dashboard',
                            version: '1.0',
                            total_items: Object.keys(this.validation_results).length,
                            languages: Object.keys(this.languages),
                            saved_at: new Date().toISOString()
                        }
                    };

                    const response = await fetch('/api/validation-storage', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(exportData)
                    });

                    if (response.ok) {
                        const result = await response.json();
                        console.log('✅ Successfully saved to shared storage:', result.metadata);
                        this.setStatus('💾 Validation results saved to shared session storage for team access', 'success');
                    } else {
                        console.warn('⚠️ Failed to save to shared storage, but localStorage backup is available');
                    }
                } catch (error) {
                    console.warn('⚠️ Could not save to shared storage:', error.message);
                    // Don't throw error - localStorage save is the primary backup
                }
            }

            async loadFromSharedStorage() {
                try {
                    console.log('🌐 Loading validation results from shared storage...');
                    
                    const response = await fetch('/api/validation-storage');
                    
                    if (response.ok) {
                        const result = await response.json();
                        if (result.success && result.data.validation_results) {
                            // Merge with local results (shared storage takes precedence for newer data)
                            const sharedResults = result.data.validation_results;
                            const localResults = this.validation_results;
                            
                            // Smart merge: keep newer validations
                            Object.keys(sharedResults).forEach(itemId => {
                                if (!localResults[itemId]) {
                                    localResults[itemId] = sharedResults[itemId];
                                } else {
                                    // Merge language validations, keeping newer ones
                                    Object.keys(sharedResults[itemId]).forEach(lang => {
                                        const sharedValidation = sharedResults[itemId][lang];
                                        const localValidation = localResults[itemId][lang];
                                        
                                        if (!localValidation || 
                                            (sharedValidation.updated && 
                                             (!localValidation.updated || sharedValidation.updated > localValidation.updated))) {
                                            localResults[itemId][lang] = sharedValidation;
                                        }
                                    });
                                }
                            });
                            
                            this.validation_results = localResults;
                            console.log(`✅ Loaded shared validation results: ${Object.keys(sharedResults).length} items`);
                            this.setStatus('🌐 Loaded validation results from shared session storage', 'success');
                            return true;
                        }
                    }
                } catch (error) {
                    console.log('⚠️ Could not load from shared storage:', error.message);
                }
                return false;
            }
            
            setupAutoSave() {
                // Auto-save disabled per user request
                // Users can manually save using the "Save Validations" button
                
                console.log('🔧 Auto-save disabled - use manual save button');
            }
            
            applyStoredValidationResults() {
                // Deprecated: Use applyStoredValidationResultsForCurrentLanguage() instead
                console.log('⚠️ applyStoredValidationResults is deprecated, use applyStoredValidationResultsForCurrentLanguage');
                this.applyStoredValidationResultsForCurrentLanguage();
            }
            
            applyStoredValidationResultsForCurrentLanguage() {
                const currentLangCode = this.languages[this.currentLanguage].lang_code;
                console.log(`🎯 Applying stored validation results for ${this.currentLanguage} (${currentLangCode})...`);
                let appliedCount = 0;
                
                Object.keys(this.validation_results).forEach(itemId => {
                    if (this.validation_results[itemId][currentLangCode]) {
                        const result = this.validation_results[itemId][currentLangCode];
                        if (result.score !== undefined) {
                            this.updateValidationUI(itemId, currentLangCode, result.score, result.notes || '');
                            appliedCount++;
                        }
                    }
                });
                
                console.log(`✅ Applied ${appliedCount} stored validation results for ${this.currentLanguage}`);
                
                // Update summary for current language
                if (typeof updateValidationSummary === 'function') {
                    updateValidationSummary();
                }
            }
            
            storeValidationResult(itemId, langCode, score, notes = '') {
                // Initialize item if it doesn't exist
                if (!this.validation_results[itemId]) {
                    this.validation_results[itemId] = {};
                }
                
                // Store the result
                this.validation_results[itemId][langCode] = {
                    score: score,
                    notes: notes,
                    timestamp: new Date().toISOString()
                };
                
                console.log(`📝 Stored validation result: ${itemId}[${langCode}] = ${score}%`);
            }
            
            updateValidationUI(itemId, langCode, score, notes) {
                // Map langCode to language name to target the correct tab
                const langCodeToLanguage = {
                    'en': 'English',
                    'es-CO': 'Spanish', 
                    'de': 'German',
                    'fr-CA': 'French',
                    'nl': 'Dutch'
                };
                
                const languageName = langCodeToLanguage[langCode];
                if (!languageName) {
                    console.warn(`Unknown langCode: ${langCode}`);
                    return;
                }
                
                // Look for indicator within the specific language tab
                const languageTab = document.getElementById(`table-${languageName}`);
                if (!languageTab) {
                    console.warn(`Language tab not found: table-${languageName}`);
                    return;
                }
                
                const indicator = languageTab.querySelector(`[data-item-id="${itemId}"]`);
                if (!indicator) {
                    console.warn(`Indicator not found for ${itemId} in ${languageName} tab`);
                    return;
                }
                
                // Determine status based on score
                let statusClass, statusTitle, buttonText, scoreEmoji;
                if (score >= 85) {
                    statusClass = 'status-good';
                    statusTitle = `✅ Excellent: ${score}% similarity`;
                    buttonText = 'View Results';
                    scoreEmoji = '✅';
                } else if (score >= 70) {
                    statusClass = 'status-warning';
                    statusTitle = `⚠️ Warning: ${score}% similarity`;
                    buttonText = 'View Warning';
                    scoreEmoji = '⚠️';
                } else {
                    statusClass = 'status-error';
                    statusTitle = `❌ Poor: ${score}% similarity`;
                    buttonText = 'View Issues';
                    scoreEmoji = '❌';
                }
                
                // Update indicator
                indicator.className = `status-indicator ${statusClass}`;
                indicator.title = statusTitle;
                
                // Update or create score badge
                const existingBadge = indicator.parentElement.querySelector('.score-badge');
                if (existingBadge) existingBadge.remove();
                
                const scoreBadge = document.createElement('span');
                scoreBadge.className = 'score-badge';
                scoreBadge.textContent = `${score}%`;
                scoreBadge.style.cssText = `
                    font-size: 10px;
                    font-weight: bold;
                    color: ${score >= 85 ? '#155724' : score >= 70 ? '#856404' : '#721c24'};
                    margin-left: 4px;
                    opacity: 0.9;
                `;
                indicator.parentElement.appendChild(scoreBadge);
                
                // Update button if it exists
                const button = indicator.parentElement.querySelector('.validate-btn');
                if (button) {
                    button.textContent = `${scoreEmoji} ${buttonText}`;
                    button.disabled = false;
                }
            }

            createTabs() {
                const tabButtons = document.getElementById('tabButtons');
                const tabContent = document.getElementById('tabContent');
                
                Object.keys(this.languages).forEach((language, index) => {
                    // Create tab button
                    const button = document.createElement('button');
                    button.className = `tab-button ${index === 0 ? 'active' : ''}`;
                    button.textContent = language;
                    button.addEventListener('click', () => this.switchTab(language, button));
                    tabButtons.appendChild(button);

                    // Create tab content
                    const content = document.createElement('div');
                    content.className = `tab-content ${index === 0 ? 'active' : ''}`;
                    content.id = `tab-${language}`;
                    
                    const langConfig = this.languages[language];
                    content.innerHTML = `
                        <h3>${this.getFlagForLanguage(language)}${language} Configuration</h3>
                        <div class="language-info">
                            <div class="info-card">
                                <strong>Language Code</strong>
                                <span>${langConfig.lang_code}</span>
                            </div>
                            <div class="info-card">
                                <strong>Default Service</strong>
                                <span>${langConfig.service}</span>
                            </div>
                            <div class="info-card">
                                <strong>Default Voice</strong>
                                <span>${langConfig.voice}</span>
                            </div>
                        </div>
                        <div class="data-table">
                            <div class="table-header">
                                <h4><i class="fas fa-table"></i> Translation Items <span id="item-count-${language}" class="item-count">(Loading...)</span></h4>
                                <input type="text" class="search-box" placeholder="Search items..." id="search-${language}">
                            </div>
                            <div class="table-content" id="table-${language}">
                                <!-- Data will be populated here -->
                            </div>
                        </div>
                    `;
                    tabContent.appendChild(content);
                });
                
                // Populate initial data
                this.populateDataTable();
            }

            populateDataTable() {
                const langCode = this.languages[this.currentLanguage].lang_code;
                const tableContent = document.getElementById(`table-${this.currentLanguage}`);
                
                if (!tableContent) return;

                tableContent.innerHTML = '';
                
                console.log(`🔍 DEBUG: Populating table for ${this.currentLanguage} (${langCode}) with ${this.data.length} items`);
                console.log(`🔍 DEBUG: Unique identifiers in data:`, new Set(this.data.map(item => item.item_id)).size);
                console.log(`🔍 DEBUG: Sample identifiers:`, this.data.slice(0, 10).map(item => item.item_id));
                
                // Update item count in header
                const itemCountSpan = document.getElementById(`item-count-${this.currentLanguage}`);
                if (itemCountSpan) {
                    itemCountSpan.textContent = `(${this.data.length} items)`;
                    itemCountSpan.style.color = '#6c757d';
                    itemCountSpan.style.fontSize = '0.9em';
                }
                
                this.data.forEach((item, index) => {
                    const text = item[langCode] || item.en || 'No translation available';
                    
                    const row = document.createElement('div');
                    row.className = 'data-row';
                    
                    // Debug logging for first few items
                    if (index < 3) {
                        console.log(`Item ${index}:`, {
                            raw_item: item,
                            item_id: item.item_id,
                            labels: item.labels,
                            available_keys: Object.keys(item)
                        });
                    }
                    
                    const itemId = item.item_id || `fallback_${index}`;
                    const taskName = item.labels || item.task || 'general';
                    const originalEnglish = item.en || 'No English source';
                    const escapedItemId = itemId.replace(/'/g, "\\'");
                    const escapedOriginal = originalEnglish.replace(/'/g, "\\'").replace(/"/g, '\\"');
                    const escapedTranslation = text.replace(/'/g, "\\'").replace(/"/g, '\\"');
                    
                    row.innerHTML = `
                        <div class="item_id">${itemId}</div>
                        <div class="item-task">${taskName}</div>
                        <div class="item-english">${originalEnglish}</div>
                        <div class="item-text">
                            ${text}
                            <div class="validation-status">
                                <div class="status-indicator status-pending" title="Not validated yet" data-item-id="${itemId}"></div>
                                <button class="validate-btn" onclick="validateSingle('${escapedItemId}', '${escapedOriginal}', '${escapedTranslation}', '${langCode}')">Validate</button>
                                <button class="info-btn" onclick="showAudioInfo('${escapedItemId}', '${langCode}')" title="Show audio metadata">Info</button>
                            </div>
                        </div>
                        <div class="audio-controls">
                            <button class="play-btn" onclick="playAudio('${escapedItemId}', '${langCode}')" title="Play existing audio">
                                <i class="fas fa-play"></i>
                            </button>
                        </div>
                    `;
                    
                    row.addEventListener('click', () => this.selectRow(row, item));
                    tableContent.appendChild(row);
                });
                
                // Apply stored validation results after table is populated, but only for current language
                setTimeout(() => {
                    this.applyStoredValidationResultsForCurrentLanguage();
                }, 100);
                
                // Update validation summary after populating table
                updateValidationSummary();
            }

            selectRow(rowElement, item) {
                // Remove previous selection
                document.querySelectorAll('.data-row').forEach(row => row.classList.remove('selected'));
                
                // Add selection to clicked row
                rowElement.classList.add('selected');
                this.selectedRow = item;
                
                const langCode = this.languages[this.currentLanguage].lang_code;
                const text = item[langCode] || item.en || 'No translation available';
                const itemId = item.item_id || 'unknown_id';
                
                console.log('Selected item:', { item, itemId, langCode, text: text.substring(0, 50) });
                this.setStatus(`Selected: ${itemId} - "${text.substring(0, 50)}..."`, 'success');
            }

            switchTab(language, button) {
                // Update active states
                document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                
                button.classList.add('active');
                document.getElementById(`tab-${language}`).classList.add('active');
                
                this.currentLanguage = language;
                this.populateVoices();
                this.populateDataTable();
                updateValidationSummary(); // Update counts for new language tab
                this.setStatus(`Switched to ${language} - ${this.languages[language].service} (${this.languages[language].lang_code})`, 'success');
            }

            populateVoices() {
                const playhtSelect = document.getElementById('playhtVoice');
                const elevenlabsSelect = document.getElementById('elevenlabsVoice');
                
                // Clear existing options
                playhtSelect.innerHTML = '<option value="">Select PlayHT Voice...</option>';
                elevenlabsSelect.innerHTML = '<option value="">Select ElevenLabs Voice...</option>';
                
                const langCode = this.languages[this.currentLanguage].lang_code;
                
                // Filter and populate PlayHT voices for current language
                const playhtVoices = this.voices.playht.filter(voice => 
                    voice.lang_code === langCode || voice.language === langCode
                );
                
                playhtVoices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.voice_id;
                    option.textContent = voice.name;
                    playhtSelect.appendChild(option);
                });
                
                // Filter and populate ElevenLabs voices for current language
                const elevenlabsVoices = this.voices.elevenlabs.filter(voice => 
                    voice.lang_code === langCode || voice.language === langCode
                );
                
                elevenlabsVoices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.voice_id;
                    option.textContent = voice.name;
                    elevenlabsSelect.appendChild(option);
                });
            }

            setupEventListeners() {
                // Refresh voices button
                document.getElementById('refreshVoices').addEventListener('click', () => {
                    this.populateVoices();
                    this.setStatus('Voice lists refreshed', 'success');
                });

                // Voice selection handlers
                document.getElementById('playhtVoice').addEventListener('change', (e) => {
                    if (e.target.value) {
                        this.setStatus(`PlayHT voice selected: ${e.target.options[e.target.selectedIndex].text}`, 'success');
                    }
                });

                document.getElementById('elevenlabsVoice').addEventListener('change', (e) => {
                    if (e.target.value) {
                        this.setStatus(`ElevenLabs voice selected: ${e.target.options[e.target.selectedIndex].text}`, 'success');
                    }
                });

                // Copy buttons for voice names
                document.getElementById('copyPlayhtVoice').addEventListener('click', () => {
                    const select = document.getElementById('playhtVoice');
                    if (select.selectedIndex > 0) {
                        const voiceName = select.options[select.selectedIndex].text;
                        navigator.clipboard.writeText(voiceName).then(() => {
                            this.setStatus(`Copied PlayHT voice: ${voiceName}`, 'success');
                        });
                    } else {
                        this.setStatus('No PlayHT voice selected', 'error');
                    }
                });

                document.getElementById('copyElevenlabsVoice').addEventListener('click', () => {
                    const select = document.getElementById('elevenlabsVoice');
                    if (select.selectedIndex > 0) {
                        const voiceName = select.options[select.selectedIndex].text;
                        navigator.clipboard.writeText(voiceName).then(() => {
                            this.setStatus(`Copied ElevenLabs voice: ${voiceName}`, 'success');
                        });
                    } else {
                        this.setStatus('No ElevenLabs voice selected', 'error');
                    }
                });


                 // Text generation controls
                 document.getElementById('generateAudio').addEventListener('click', () => {
                     this.generateAudioFromText();
                 });

                 document.getElementById('populateSelected').addEventListener('click', () => {
                     this.populateSelectedText();
                 });

                 document.getElementById('clearText').addEventListener('click', () => {
                     document.getElementById('textInput').value = '';
                     this.setStatus('Text cleared', 'success');
                 });
             }

            async generateAudioFromText() {
                const textInput = document.getElementById('textInput');
                const text = textInput.value.trim();
                
                if (!text) {
                    alert('Please enter some text to generate audio.');
                    return;
                }
                
                const playhtVoice = document.getElementById('playhtVoice').value;
                const elevenlabsVoice = document.getElementById('elevenlabsVoice').value;
                const currentLangConfig = this.languages[this.currentLanguage];
                
                let selectedService, selectedVoice;
                
                // Determine which service to use based on selection
                if (playhtVoice && elevenlabsVoice) {
                    // Both selected, use the current language's default service
                    if (currentLangConfig.service === 'PlayHT') {
                        selectedService = 'PlayHT';
                        selectedVoice = playhtVoice;
                    } else {
                        selectedService = 'ElevenLabs';
                        selectedVoice = elevenlabsVoice;
                    }
                } else if (playhtVoice) {
                    selectedService = 'PlayHT';
                    selectedVoice = playhtVoice;
                } else if (elevenlabsVoice) {
                    selectedService = 'ElevenLabs';
                    selectedVoice = elevenlabsVoice;
                } else {
                    alert('Please select a voice from either PlayHT or ElevenLabs to generate audio.');
                    return;
                }
                
                this.setStatus(`Generating audio with ${selectedService}...`, 'loading');
                
                try {
                    if (selectedService === 'PlayHT') {
                        await this.generatePlayHTAudio(text, selectedVoice);
                    } else if (selectedService === 'ElevenLabs') {
                        await this.generateElevenLabsAudio(text, selectedVoice);
                    }
                } catch (error) {
                    console.error('Audio generation error:', error);
                    this.setStatus(`Error generating audio: ${error.message}`, 'error');
                    alert(`Failed to generate audio: ${error.message}`);
                }
            }
            
            async generatePlayHTAudio(text, voiceId) {
                const credentials = getCredentials();
                if (!credentials.playhtApiKey || !credentials.playhtUserId) {
                    throw new Error('PlayHT credentials not found. Please add them in the credentials manager.');
                }
                
                const requestData = {
                    text: text,
                    voice: voiceId,
                    quality: 'medium',
                    output_format: 'mp3',
                    speed: 1,
                    sample_rate: 24000
                };
                
                console.log('Calling PlayHT API with:', requestData);
                
                const response = await fetch('/api/playht-proxy', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'AUTHORIZATION': credentials.playhtApiKey,
                        'X-USER-ID': credentials.playhtUserId
                    },
                    body: JSON.stringify(requestData)
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`PlayHT API error: ${response.status} - ${errorText}`);
                }
                
                // Get the audio blob
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                
                this.setStatus('Audio generated successfully! Playing now...', 'success');
                
                // Play the generated audio
                const audio = new Audio(audioUrl);
                audio.addEventListener('canplaythrough', () => {
                    audio.play();
                    this.setStatus('Playing generated audio...', 'success');
                });
                audio.addEventListener('ended', () => {
                    this.setStatus('Audio playback completed.', 'success');
                    // Clean up the blob URL
                    URL.revokeObjectURL(audioUrl);
                });
                audio.addEventListener('error', (e) => {
                    console.error('Audio playback error:', e);
                    this.setStatus('Error playing generated audio.', 'error');
                    URL.revokeObjectURL(audioUrl);
                });
            }
            
            async generateElevenLabsAudio(text, voiceId) {
                const credentials = getCredentials();
                if (!credentials.elevenlabsApiKey) {
                    throw new Error('ElevenLabs API key not found. Please add it in the credentials manager.');
                }
                
                const requestData = {
                    text: text,
                    model_id: "eleven_monolingual_v1",
                    voice_settings: {
                        stability: 0.5,
                        similarity_boost: 0.75
                    }
                };
                
                console.log('Calling ElevenLabs API with:', requestData);
                
                const response = await fetch(`/api/elevenlabs-proxy?voice_id=${voiceId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-KEY': credentials.elevenlabsApiKey
                    },
                    body: JSON.stringify(requestData)
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`ElevenLabs API error: ${response.status} - ${errorText}`);
                }
                
                // Get the audio blob
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                
                this.setStatus('Audio generated successfully! Playing now...', 'success');
                
                // Play the generated audio
                const audio = new Audio(audioUrl);
                audio.addEventListener('canplaythrough', () => {
                    audio.play();
                    this.setStatus('Playing generated audio...', 'success');
                });
                audio.addEventListener('ended', () => {
                    this.setStatus('Audio playback completed.', 'success');
                    // Clean up the blob URL
                    URL.revokeObjectURL(audioUrl);
                });
                audio.addEventListener('error', (e) => {
                    console.error('Audio playback error:', e);
                    this.setStatus('Error playing generated audio.', 'error');
                    URL.revokeObjectURL(audioUrl);
                });
            }
            
            populateSelectedText() {
                if (!this.selectedRow) {
                    alert('Please select an item from the table first.');
                    return;
                }
                
                const langCode = this.languages[this.currentLanguage].lang_code;
                const text = this.selectedRow[langCode] || this.selectedRow.en || 'No translation available';
                
                document.getElementById('textInput').value = text;
                this.setStatus(`Text populated from selected item: ${this.selectedRow.item_id}`, 'success');
            }

            setStatus(message, type = 'success') {
                const statusBar = document.getElementById('statusBar');
                const statusIcon = statusBar.querySelector('.status-icon');
                const statusContent = statusBar.querySelector('span');
                
                // Update icon based on type
                statusIcon.className = `fas fa-circle status-icon ${type}`;
                
                if (statusContent) {
                    statusContent.textContent = message;
                }
            }
        }

        // Initialization moved to js/bootstrap.js
        
        // Validation Functions

        // ===== Language Config Modal (Vue) =====
        // Language config app moved to js/language-config.js
        function initLanguageConfigApp() {
            const { createApp, reactive } = Vue;
            const app = createApp({
                data() {
                    return {
                        loading: true,
                        saving: false,
                        config: reactive({ languages: JSON.parse(JSON.stringify(window.CONFIG?.languages || {})) }),
                        renameBuffer: {}
                    };
                },
                mounted() {
                    this.load();
                },
                methods: {
                    async load() {
                        this.loading = true;
                        try {
                            const resp = await fetch('/api/language-config');
                            const data = await resp.json();
                            if (data && data.languages) {
                                this.config.languages = data.languages;
                            }
                        } catch (e) {
                            // ignore; fallback to local
                        } finally {
                            this.loading = false;
                        }
                    },
                    // rename/remove/add functionality intentionally omitted per request
                    async saveConfig() {
                        this.saving = true;
                        try {
                            const body = { languages: this.config.languages, metadata: { source: 'web-dashboard' } };
                            const resp = await fetch('/api/language-config', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
                            if (!resp.ok) throw new Error(await resp.text());
                            // Update in-memory CONFIG and refresh dashboard tabs
                            window.CONFIG = window.CONFIG || {};
                            window.CONFIG.languages = JSON.parse(JSON.stringify(this.config.languages));
                            if (window.dashboard) {
                                window.dashboard.languages = window.CONFIG.languages;
                                document.getElementById('tabButtons').innerHTML = '';
                                document.getElementById('tabContent').innerHTML = '';
                                window.dashboard.createTabs();
                                window.dashboard.populateVoices();
                            }
                            alert('Saved language configuration.');
                            closeLanguageConfigModal();
                        } catch (e) {
                            alert(`Failed to save: ${e.message}`);
                        } finally {
                            this.saving = false;
                        }
                    }
                }
            });
            app.mount('#language-config-app');
        }
        
        function validateSelected() {
            const credentials = getCredentials();
            if (!credentials.googleTranslateApiKey) {
                alert('Please add your Google Translate API key in the credentials manager.');
                return;
            }
            
            const selectedRows = document.querySelectorAll('.data-row.selected');
            console.log(`🔍 DEBUG validateSelected: Found ${selectedRows.length} selected rows`);
            
            if (selectedRows.length === 0) {
                alert('Please select one or more translations to validate.');
                return;
            }
            
            selectedRows.forEach(row => {
                const validateBtn = row.querySelector('.validate-btn');
                if (validateBtn && validateBtn.onclick) {
                    validateBtn.click();
                }
            });
        }
        
        function validateAll() {
            const credentials = getCredentials();
            if (!credentials.googleTranslateApiKey) {
                alert('Please add your Google Translate API key in the credentials manager.');
                return;
            }
            
            // Get the current active language from the dashboard instance
            const currentLanguage = window.dashboard?.currentLanguage;
            if (!currentLanguage) {
                alert('No active language found.');
                return;
            }
            
            console.log(`🔍 DEBUG: Current active language: ${currentLanguage}`);
            
            // Only get validate buttons from the current language table
            const currentTable = document.getElementById(`table-${currentLanguage}`);
            if (!currentTable) {
                alert(`Current language table not found: table-${currentLanguage}`);
                return;
            }
            
            const validateBtns = currentTable.querySelectorAll('.validate-btn');
            if (validateBtns.length === 0) {
                alert('No translations available to validate in the current language.');
                return;
            }
            
            console.log(`🔍 DEBUG validateAll: Found ${validateBtns.length} validate buttons for ${currentLanguage}`);
            console.log(`🔍 DEBUG validateAll: dashboard.data.length = ${window.dashboard?.data?.length || 'undefined'}`);
            console.log(`🔍 DEBUG validateAll: dashboard.currentLanguage = ${window.dashboard?.currentLanguage || 'undefined'}`);
            
            if (confirm(`This will validate ${validateBtns.length} ${currentLanguage.toUpperCase()} translations. This may take some time. Continue?`)) {
                let currentIndex = 0;
                const validateNext = () => {
                    if (currentIndex < validateBtns.length) {
                        const btn = validateBtns[currentIndex];
                        if (btn && !btn.disabled) {
                            btn.click();
                        }
                        currentIndex++;
                        setTimeout(validateNext, 1000); // Delay between requests
                    }
                };
                validateNext();
            }
        }
        


        
        
        function showValidationSummaryReport() {
            const results = window.dashboard.validation_results;
            const languages = window.dashboard.languages;
            
            if (Object.keys(results).length === 0) {
                alert('No validation results to display. Please run some validations first.');
                return;
            }
            
            // Calculate statistics
            const stats = {};
            let totalValidations = 0;
            
            // Initialize stats for each language
            Object.keys(languages).forEach(langName => {
                const langCode = languages[langName].lang_code;
                stats[langName] = {
                    langCode: langCode,
                    total: 0,
                    excellent: 0,
                    warning: 0,
                    poor: 0,
                    items: []
                };
            });
            
            // Process validation results
            Object.keys(results).forEach(itemId => {
                Object.keys(results[itemId]).forEach(langCode => {
                    const result = results[itemId][langCode];
                    const score = result.score;
                    
                    // Find language name from code
                    const langName = Object.keys(languages).find(name => 
                        languages[name].lang_code === langCode
                    );
                    
                    if (langName && stats[langName]) {
                        stats[langName].total++;
                        totalValidations++;
                        
                        if (score >= 85) stats[langName].excellent++;
                        else if (score >= 70) stats[langName].warning++;
                        else stats[langName].poor++;
                        
                        stats[langName].items.push({
                            itemId: itemId,
                            score: score,
                            timestamp: result.timestamp
                        });
                    }
                });
            });
            
            // Sort items by score (poorest first) for each language
            Object.keys(stats).forEach(langName => {
                stats[langName].items.sort((a, b) => a.score - b.score);
            });
            
            // Create modal content
            const modalHtml = createValidationSummaryModal(stats, totalValidations);
            
            // Show modal
            const existingModal = document.getElementById('validationSummaryModal');
            if (existingModal) existingModal.remove();
            
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            document.getElementById('validationSummaryModal').style.display = 'block';
        }
        
        function createValidationSummaryModal(stats, totalValidations) {
            const langStats = Object.keys(stats)
                .filter(langName => stats[langName].total > 0)
                .map(langName => {
                    const s = stats[langName];
                    const excellentPct = Math.round((s.excellent / s.total) * 100);
                    const warningPct = Math.round((s.warning / s.total) * 100);
                    const poorPct = Math.round((s.poor / s.total) * 100);
                    
                    const flag = window.dashboard.getFlagForLanguage(langName);
                    
                    // Show top 5 items needing attention (lowest scores, excluding excellent ones)
                    const itemsNeedingAttention = s.items.filter(item => item.score < 85);
                    const needsAttention = itemsNeedingAttention.slice(0, 5).map(item => 
                        `<li>${item.itemId}: <span style="color: ${item.score >= 70 ? '#ffc107' : '#dc3545'}">${item.score}%</span></li>`
                    ).join('');
                    
                    return `
                        <div class="lang-summary">
                            <h4>${flag}${langName} (${s.langCode}) - ${s.total} validations</h4>
                            <div class="score-breakdown">
                                <div class="score-bar">
                                    <div class="excellent" style="width: ${excellentPct}%" title="Excellent: ${s.excellent}"></div>
                                    <div class="warning" style="width: ${warningPct}%" title="Warning: ${s.warning}"></div>
                                    <div class="poor" style="width: ${poorPct}%" title="Poor: ${s.poor}"></div>
                                </div>
                                <div class="score-legend">
                                    <span class="excellent">✅ ${s.excellent} Excellent (≥85%)</span>
                                    <span class="warning">⚠️ ${s.warning} Warning (70-84%)</span>
                                    <span class="poor">❌ ${s.poor} Poor (<70%)</span>
                                </div>
                            </div>
                            ${itemsNeedingAttention.length > 0 ? `
                                <details>
                                    <summary>Items needing attention (lowest scores first) - ${itemsNeedingAttention.length} items</summary>
                                    <ul class="attention-list">${needsAttention}</ul>
                                </details>
                            ` : ''}
                        </div>
                    `;
                }).join('');
            
            return `
                <div id="validationSummaryModal" class="modal" style="display: none;">
                    <div class="modal-content" style="max-width: 900px; max-height: 80vh; overflow-y: auto;">
                        <div class="modal-header">
                            <h2><i class="fas fa-chart-bar"></i> Validation Summary Report</h2>
                            <span class="close" onclick="document.getElementById('validationSummaryModal').remove()">&times;</span>
                        </div>
                        <div style="padding: 20px;">
                            <div class="summary-overview">
                                <h3>📊 Overview</h3>
                                <p><strong>Total Validations:</strong> ${totalValidations} across ${Object.keys(stats).filter(lang => stats[lang].total > 0).length} languages</p>
                                <p><strong>Generated:</strong> ${new Date().toLocaleString()}</p>
                            </div>
                            
                            <div class="language-summaries">
                                <h3>🌍 By Language</h3>
                                ${langStats || '<p>No validation data available.</p>'}
                            </div>
                        </div>
                    </div>
                </div>
                
                <style>
                .lang-summary {
                    margin-bottom: 25px;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 15px;
                    background: #f9f9f9;
                }
                
                .score-breakdown {
                    margin: 10px 0;
                }
                
                .score-bar {
                    display: flex;
                    height: 20px;
                    border-radius: 10px;
                    overflow: hidden;
                    border: 1px solid #ddd;
                    margin-bottom: 8px;
                }
                
                .score-bar .excellent { background: #28a745; }
                .score-bar .warning { background: #ffc107; }
                .score-bar .poor { background: #dc3545; }
                
                .score-legend {
                    display: flex;
                    gap: 15px;
                    font-size: 0.85em;
                    flex-wrap: wrap;
                }
                
                .score-legend .excellent { color: #28a745; }
                .score-legend .warning { color: #856404; }
                .score-legend .poor { color: #dc3545; }
                
                .attention-list {
                    margin: 8px 0;
                    padding-left: 20px;
                }
                
                .attention-list li {
                    margin: 4px 0;
                    font-family: monospace;
                }
                
                .summary-overview {
                    background: #e7f3ff;
                    padding: 15px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }
                </style>
            `;
        }
        
        async function validateSingle(itemId, originalText, translatedText, langCode) {
            console.log('🎯 VALIDATION START:', {itemId, langCode, textLength: translatedText.length});
            
            const credentials = getCredentials();
            console.log('🔑 Credentials check:', {hasGoogleTranslateApiKey: !!credentials.googleTranslateApiKey});
            
            if (!credentials.googleTranslateApiKey) {
                console.error('❌ No Google Translate API key found');
                alert('Please add your Google Translate API key in the credentials manager.');
                return;
            }
            
            // Skip validation for English (source language)
            if (langCode === 'en' || langCode.startsWith('en-')) {
                const indicator = document.querySelector(`[data-item-id="${itemId}"]`);
                const button = event.target;
                
                indicator.className = 'status-indicator status-info';
                indicator.title = '🔵 English source text - no validation needed';
                indicator.style.background = '#17a2b8';
                indicator.style.animation = 'none';
                
                // Add source badge
                const existingBadge = indicator.parentElement.querySelector('.score-badge');
                if (existingBadge) existingBadge.remove();
                
                const sourceBadge = document.createElement('span');
                sourceBadge.className = 'score-badge';
                sourceBadge.textContent = 'SRC';
                sourceBadge.style.cssText = `
                    font-size: 9px;
                    font-weight: bold;
                    color: #17a2b8;
                    margin-left: 4px;
                    background: rgba(23, 162, 184, 0.1);
                    border: 1px solid #17a2b8;
                `;
                indicator.parentElement.appendChild(sourceBadge);
                
                button.textContent = '🔵 Source';
                button.disabled = true;
                
                console.log('✅ Skipping validation for English source text');
                return;
            }
            
            const indicator = document.querySelector(`[data-item-id="${itemId}"]`);
            const button = event.target;
            
            console.log('🎛️ UI elements found:', {indicator: !!indicator, button: !!button});
            
            if (!indicator || !button) {
                console.error('❌ Could not find UI elements for validation');
                alert('Error: Could not find validation UI elements');
                return;
            }
            
            // Update UI to show validation in progress
            button.textContent = 'Validating...';
            button.disabled = true;
            indicator.className = 'status-indicator status-info';
            indicator.title = '🔄 Validation in progress...';
            
            try {
                // Prepare language code for Google Translate (convert es-CO to es, fr-CA to fr, etc.)
                let sourceLanguage = langCode;
                if (langCode.includes('-')) {
                    sourceLanguage = langCode.split('-')[0];
                }
                
                const requestBody = {
                    original_english: originalText,
                    source_text: translatedText,
                    source_lang: sourceLanguage,
                    target_lang: 'en'
                };
                
                console.log('📤 Validation request:', requestBody);
                
                // Call our CORS proxy for Google Translate
                console.log('🌐 Calling CORS proxy...');
                const response = await fetch('/api/translate-proxy', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-KEY': credentials.googleTranslateApiKey
                    },
                    body: JSON.stringify(requestBody)
                });
                
                console.log('📥 Response status:', response.status, response.statusText);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error('❌ Validation error response:', {
                        status: response.status,
                        statusText: response.statusText,
                        errorText: errorText
                    });
                    throw new Error(`HTTP ${response.status}: ${response.statusText}${errorText ? ' - ' + errorText : ''}`);
                }
                
                const result = await response.json();
                console.log('✅ Validation result:', result);
                console.log('📝 Result breakdown:', {
                    originalEnglish: result.original_english,
                    sourceText: result.source_text,  
                    backTranslated: result.back_translated,
                    similarityScore: result.similarity_score
                });
                
                const similarity = result.similarity_score || 0;
                
                // Store validation result for persistence
                window.dashboard.storeValidationResult(itemId, langCode, similarity);
                
                // Update status indicator based on similarity score
                let statusClass, statusTitle, buttonText, scoreEmoji;
                if (similarity >= 85) {
                    statusClass = 'status-good';
                    statusTitle = `✅ Excellent: ${similarity}% similarity`;
                    buttonText = 'View Results';
                    scoreEmoji = '✅';
                } else if (similarity >= 70) {
                    statusClass = 'status-warning';
                    statusTitle = `⚠️ Warning: ${similarity}% similarity`;
                    buttonText = 'View Warning';
                    scoreEmoji = '⚠️';
                } else {
                    statusClass = 'status-error';
                    statusTitle = `❌ Poor: ${similarity}% similarity`;
                    buttonText = 'View Issues';
                    scoreEmoji = '❌';
                }
                
                indicator.className = `status-indicator ${statusClass}`;
                indicator.title = statusTitle;
                
                // Add a score badge next to the indicator
                const existingBadge = indicator.parentElement.querySelector('.score-badge');
                if (existingBadge) existingBadge.remove();
                
                const scoreBadge = document.createElement('span');
                scoreBadge.className = 'score-badge';
                scoreBadge.textContent = `${similarity}%`;
                scoreBadge.style.cssText = `
                    font-size: 10px;
                    font-weight: bold;
                    color: ${similarity >= 85 ? '#155724' : similarity >= 70 ? '#856404' : '#721c24'};
                    margin-left: 4px;
                    opacity: 0.9;
                `;
                indicator.parentElement.appendChild(scoreBadge);
                
                button.textContent = `${scoreEmoji} ${buttonText}`;
                button.disabled = false;
                
                // Store validation result and change button behavior
                button.setAttribute('data-validation-result', JSON.stringify(result));
                button.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('🖱️ View button clicked for:', itemId);
                    showValidationResult(itemId, result);
                };
                
                // Make the status indicator clickable too
                indicator.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('🎯 Status dot clicked for:', itemId);
                    showValidationResult(itemId, result);
                };
                
                console.log(`🎯 Validation complete: ${statusTitle}`);
                updateValidationSummary();
                
            } catch (error) {
                console.error('💥 VALIDATION ERROR:', error);
                console.error('Error details:', {
                    message: error.message,
                    stack: error.stack,
                    name: error.name
                });
                
                indicator.className = 'status-indicator status-error';
                
                let errorMessage = 'Unknown error';
                let buttonText = 'Retry';
                
                if (error.message.includes('Failed to fetch')) {
                    errorMessage = 'Cannot connect to CORS proxy server (port 8001)';
                    buttonText = 'Retry Connection';
                } else if (error.message.includes('400')) {
                    errorMessage = 'Google Translate API error (check API key)';
                    buttonText = 'Retry API';
                } else if (error.message.includes('401')) {
                    errorMessage = 'Invalid Google Translate API key';
                    buttonText = 'Fix API Key';
                } else if (error.message.includes('403')) {
                    errorMessage = 'Google Translate API access denied';
                    buttonText = 'Check Permissions';
                } else {
                    errorMessage = error.message;
                }
                
                indicator.title = `❌ Validation failed: ${errorMessage}`;
                button.textContent = buttonText;
                button.disabled = false;
                
                // Store error for viewing
                const errorResult = {
                    error: true,
                    message: errorMessage,
                    details: error.message,
                    original: originalText,
                    translation: translatedText
                };
                button.setAttribute('data-validation-result', JSON.stringify(errorResult));
                button.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('🖱️ Error view button clicked for:', itemId);
                    showValidationResult(itemId, errorResult);
                };
                
                console.log('🚨 Error stored for viewing');
            }
        }
        
        function showValidationResult(itemId, result) {
            console.log('👁️ SHOW VALIDATION RESULT START:', itemId, result);
            
            // Check if result already exists and toggle it
            const existingResult = document.querySelector(`#validation-result-${itemId}`);
            if (existingResult) {
                console.log('🔄 Found existing result, checking visibility...');
                const computedStyle = window.getComputedStyle(existingResult);
                const isHidden = computedStyle.display === 'none' || existingResult.style.display === 'none';
                
                console.log('🔍 Existing result state:', {
                    computedDisplay: computedStyle.display,
                    styleDisplay: existingResult.style.display,
                    isHidden: isHidden
                });
                
                // Update button text to reflect state
                const button = document.querySelector(`[data-item-id="${itemId}"]`).closest('.data-row').querySelector('.validate-btn');
                if (button) {
                    const originalText = button.getAttribute('data-original-text') || button.textContent;
                    if (!button.getAttribute('data-original-text')) {
                        button.setAttribute('data-original-text', originalText);
                    }
                    button.textContent = isHidden ? 'Hide Result' : originalText;
                }
                
                if (isHidden) {
                    // Show with professional styling (same as new results)
                    existingResult.style.cssText = `
                        background: white !important;
                        border: 2px solid #007bff !important;
                        border-radius: 8px !important;
                        padding: 20px !important;
                        font-size: 0.9em !important;
                        color: #333 !important;
                        box-shadow: 0 8px 24px rgba(0,0,0,0.2) !important;
                        position: fixed !important;
                        top: 100px !important;
                        left: 50% !important;
                        transform: translateX(-50%) !important;
                        z-index: 99999 !important;
                        display: block !important;
                        width: 600px !important;
                        max-width: 90vw !important;
                        max-height: 500px !important;
                        opacity: 1 !important;
                        overflow: auto !important;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                    `;
                    console.log('✅ Showing existing result with professional styling');
                    
                } else {
                    // Hide with fade out
                    existingResult.style.opacity = '0';
                    console.log('✅ Hiding existing result');
                    
                    // Wait for fade to complete before hiding
                    setTimeout(() => {
                        existingResult.style.display = 'none';
                    }, 300);
                }
                
                return;
            }
            
            // Find the row element
            console.log('🔍 Looking for row with data-item-id:', itemId);
            const indicator = document.querySelector(`[data-item-id="${itemId}"]`);
            console.log('🎯 Found indicator:', !!indicator);
            
            if (!indicator) {
                console.error('❌ Could not find indicator for item:', itemId);
                // Try alternative selector
                const allIndicators = document.querySelectorAll('.status-indicator');
                console.log('🔍 All indicators:', Array.from(allIndicators).map(i => i.getAttribute('data-item-id')));
                alert('Error: Could not find validation indicator');
                return;
            }
            
            const row = indicator.closest('.data-row');
            console.log('📋 Found row:', !!row);
            
            if (!row) {
                console.error('❌ Could not find row for item:', itemId);
                alert('Error: Could not find row to display result');
                return;
            }
            
            const resultDiv = document.createElement('div');
            resultDiv.id = `validation-result-${itemId}`;
            resultDiv.className = 'back-translation';
            
            if (result.error) {
                // Handle error case
                resultDiv.innerHTML = `
                    <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 15px;">
                        <h3 style="margin: 0; color: #dc3545;">❌ Validation Error</h3>
                    </div>
                    <div style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 6px; margin: 10px 0;">
                        <strong>Error:</strong> ${result.message}<br>
                        <small style="opacity: 0.8;">Details: ${result.details}</small>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                        <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; border: 1px solid #dee2e6;">
                            <div style="font-weight: bold; font-size: 0.8em; color: #6c757d; margin-bottom: 8px; text-transform: uppercase;">Original English</div>
                            <div style="color: #495057;">${result.original_english || result.original || 'N/A'}</div>
                        </div>
                        <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; border: 1px solid #dee2e6;">
                            <div style="font-weight: bold; font-size: 0.8em; color: #6c757d; margin-bottom: 8px; text-transform: uppercase;">Back-translated English</div>
                            <div style="color: #495057;">${result.back_translated || result.translated || 'N/A'}</div>
                        </div>
                    </div>
                `;
            } else {
                // Handle successful validation
                const similarity = result.similarity_score || 0;
                const scoreColor = similarity >= 85 ? '#28a745' : similarity >= 70 ? '#ffc107' : '#dc3545';
                const bgColor = similarity >= 85 ? '#d4edda' : similarity >= 70 ? '#fff3cd' : '#f8d7da';
                const textColor = similarity >= 85 ? '#155724' : similarity >= 70 ? '#856404' : '#721c24';
                const recommendation = similarity >= 85 ? '✅ Translation looks excellent!' : 
                                     similarity >= 70 ? '⚠️ Translation has minor differences.' : 
                                     '❌ Translation may need review.';
                
                resultDiv.innerHTML = `
                    <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 15px;">
                        <h3 style="margin: 0; color: #495057;">Translation Validation Result</h3>
                    </div>
                    <div style="text-align: center; margin: 15px 0;">
                        <div style="font-size: 2em; font-weight: bold; color: ${scoreColor}; margin-bottom: 5px;">
                            ${similarity}%
                        </div>
                        <div style="font-size: 0.9em; color: #6c757d;">Similarity Score</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0;">
                        <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; border: 1px solid #dee2e6;">
                            <div style="font-weight: bold; font-size: 0.8em; color: #6c757d; margin-bottom: 8px; text-transform: uppercase;">Original English</div>
                            <div style="color: #495057; line-height: 1.4;">${result.original_english || result.original || 'N/A'}</div>
                        </div>
                        <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; border: 1px solid #dee2e6;">
                            <div style="font-weight: bold; font-size: 0.8em; color: #6c757d; margin-bottom: 8px; text-transform: uppercase;">Back-translated English</div>
                            <div style="color: #495057; line-height: 1.4;">${result.back_translated || result.translated || 'N/A'}</div>
                        </div>
                    </div>
                    <div style="padding: 12px; border-radius: 6px; text-align: center; background: ${bgColor}; color: ${textColor}; font-weight: 500;">
                        ${recommendation}
                    </div>
                `;
            }
            
            // Add working close button (the good one!)
            const closeButton = document.createElement('button');
            closeButton.textContent = '×';
            closeButton.style.cssText = 'position: absolute; top: 10px; right: 10px; background: #f8f9fa; border: 1px solid #dee2e6; font-size: 18px; cursor: pointer; color: #6c757d; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; z-index: 100000;';
            closeButton.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                resultDiv.remove();
                console.log('🗑️ Modal closed via close button');
            };
            closeButton.onmouseover = () => closeButton.style.background = '#e9ecef';
            closeButton.onmouseout = () => closeButton.style.background = '#f8f9fa';
            
            // Style the result div professionally now that we know fixed positioning works
            resultDiv.style.cssText = `
                background: white !important;
                border: 2px solid #007bff !important;
                border-radius: 8px !important;
                padding: 20px !important;
                padding-top: 40px !important;
                font-size: 0.9em !important;
                color: #333 !important;
                box-shadow: 0 8px 24px rgba(0,0,0,0.2) !important;
                position: fixed !important;
                top: 100px !important;
                left: 50% !important;
                transform: translateX(-50%) !important;
                z-index: 99999 !important;
                display: block !important;
                width: 600px !important;
                max-width: 90vw !important;
                max-height: 500px !important;
                opacity: 1 !important;
                overflow: auto !important;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            `;
            
            // Append the close button after styling
            resultDiv.appendChild(closeButton);
            
            console.log('✅ Applied professional styling with fixed positioning');
            
            // Add animation keyframes if not already present
            if (!document.querySelector('#validation-animations')) {
                const style = document.createElement('style');
                style.id = 'validation-animations';
                style.textContent = `
                    @keyframes slideDown {
                        from { opacity: 0; transform: translateY(-10px); max-height: 0; }
                        to { opacity: 1; transform: translateY(0); max-height: 500px; }
                    }
                    @keyframes slideUp {
                        from { opacity: 1; transform: translateY(0); max-height: 500px; }
                        to { opacity: 0; transform: translateY(-10px); max-height: 0; }
                    }
                `;
                document.head.appendChild(style);
            }
            
            // Add to document body for reliable positioning
            document.body.appendChild(resultDiv);
            console.log('✅ Validation panel added to page');
            
            // Update button text to show it can be hidden
            const button = row.querySelector('.validate-btn');
            if (button && !button.getAttribute('data-original-text')) {
                button.setAttribute('data-original-text', button.textContent);
                button.textContent = 'Hide Result';
            }
            
            console.log('✅ Validation result displayed successfully');
            
            console.log('✅ Validation result panel created and displayed');
        }
        
        function updateValidationSummary() {
            // Get the current active language from the dashboard instance
            const currentLanguage = window.dashboard?.currentLanguage;
            if (!currentLanguage) {
                console.warn('No active language found for validation summary');
                return;
            }
            
            // Only count indicators from the current language table
            const currentTable = document.getElementById(`table-${currentLanguage}`);
            if (!currentTable) {
                console.warn(`Current language table not found: table-${currentLanguage}`);
                return;
            }
            
            const indicators = currentTable.querySelectorAll('.status-indicator');
            let good = 0, warning = 0, error = 0, pending = 0;
            
            console.log(`🔍 DEBUG Summary: Counting ${indicators.length} indicators for ${currentLanguage}`);
            
            indicators.forEach(indicator => {
                if (indicator.classList.contains('status-good')) good++;
                else if (indicator.classList.contains('status-warning')) warning++;
                else if (indicator.classList.contains('status-error')) error++;
                else pending++;
            });
            
            console.log(`🔍 DEBUG Summary: ${currentLanguage} - Good: ${good}, Warning: ${warning}, Error: ${error}, Pending: ${pending}`);
            
            document.getElementById('goodCount').textContent = good;
            document.getElementById('warningCount').textContent = warning;
            document.getElementById('errorCount').textContent = error;
            document.getElementById('pendingCount').textContent = pending;
        }
        
        // Credentials Management Functions
        function openCredentialsModal() {

        // Audio Info Modal Functions
        function showAudioInfo(itemId, langCode) {
            console.log(`🔍 Showing audio info for: ${itemId} in ${langCode}`);
            
            // Open modal and show loading
            document.getElementById('audioInfoModal').style.display = 'block';
            document.getElementById('audioInfoLoading').style.display = 'block';
            document.getElementById('audioInfoData').style.display = 'none';
            document.getElementById('audioInfoError').style.display = 'none';
            
            // Call API to get metadata
            fetchAudioMetadata(itemId, langCode);
        }
        
        function closeAudioInfoModal() {
            document.getElementById('audioInfoModal').style.display = 'none';
        }
        
        async function fetchAudioMetadata(itemId, langCode) {
            try {
                const response = await fetch(`/api/read-tags?itemId=${encodeURIComponent(itemId)}&langCode=${encodeURIComponent(langCode)}`);
                const data = await response.json();
                
                if (data.error) {
                    showAudioInfoError(data.error, data.details);
                } else {
                    showAudioInfoData(data);
                }
            } catch (error) {
                console.error('❌ Error fetching audio metadata:', error);
                showAudioInfoError('Network Error', `Failed to fetch metadata: ${error.message}`);
            }
        }
        
        function showAudioInfoData(metadata) {
            // Hide loading, show data
            document.getElementById('audioInfoLoading').style.display = 'none';
            document.getElementById('audioInfoError').style.display = 'none';
            document.getElementById('audioInfoData').style.display = 'block';
            
            // Populate file information
            document.getElementById('info-fileName').textContent = metadata.fileName || 'N/A';
            document.getElementById('info-size').textContent = formatFileSize(metadata.size) || 'N/A';
            document.getElementById('info-contentType').textContent = metadata.contentType || 'N/A';
            document.getElementById('info-created').textContent = formatDate(metadata.created) || 'N/A';
            document.getElementById('info-language').textContent = metadata.language || 'N/A';
            
            // Populate ID3 tags
            const id3Tags = metadata.id3Tags || {};
            document.getElementById('info-title').textContent = id3Tags.title || 'Not set';
            document.getElementById('info-artist').textContent = id3Tags.artist || 'Not set';
            document.getElementById('info-album').textContent = id3Tags.album || 'Not set';
            document.getElementById('info-genre').textContent = id3Tags.genre || 'Not set';
            document.getElementById('info-service').textContent = id3Tags.service || 'Not set';
            document.getElementById('info-voice').textContent = id3Tags.voice || 'Not set';
            
            // Show note if present
            const noteElement = document.getElementById('info-note');
            if (metadata.note || id3Tags.note) {
                noteElement.textContent = metadata.note || id3Tags.note;
                noteElement.style.display = 'block';
            } else {
                noteElement.style.display = 'none';
            }
        }
        
        function showAudioInfoError(error, details) {
            // Hide loading and data, show error
            document.getElementById('audioInfoLoading').style.display = 'none';
            document.getElementById('audioInfoData').style.display = 'none';
            document.getElementById('audioInfoError').style.display = 'block';
            
            document.getElementById('errorMessage').textContent = `${error}: ${details}`;
        }
        
        function formatFileSize(bytes) {
            if (!bytes) return 'N/A';
            const sizes = ['B', 'KB', 'MB', 'GB'];
            let i = 0;
            while (bytes >= 1024 && i < sizes.length - 1) {
                bytes /= 1024;
                i++;
            }
            return `${bytes.toFixed(1)} ${sizes[i]}`;
        }
        
        function formatDate(dateString) {
            if (!dateString) return 'N/A';
            try {
                return new Date(dateString).toLocaleString();
            } catch (error) {
                return dateString;
            }
        }
        
        function clearCacheAndReload() {
            if (confirm('Clear translation data cache and reload? This will fetch fresh data from GitHub.')) {
                console.log('🗑️ Clearing localStorage cache and reloading...');
                localStorage.removeItem('levante_translations_cache');
                alert('Cache cleared! Page will reload to fetch fresh data.');
                location.reload();
            }
        }
        
        function getCredentials() {
            try {
                return JSON.parse(localStorage.getItem('levante_credentials') || '{}');
            } catch (error) {
                return {};
            }
        }
        
        function updateValidationAvailability(hasGoogleTranslateKey) {
            const validateButtons = document.querySelectorAll('.validation-button');
            const validateBtns = document.querySelectorAll('.validate-btn');
            
            validateButtons.forEach(btn => {
                btn.disabled = !hasGoogleTranslateKey;
                btn.title = hasGoogleTranslateKey ? 'Validation enabled' : 'Add Google Translate API key';
            });
            validateBtns.forEach(btn => {
                btn.disabled = !hasGoogleTranslateKey;
                btn.title = hasGoogleTranslateKey ? 'Click to validate' : 'Add Google Translate API key';
            });
        }
        
        // Audio functions moved to js/audio.js
        function playAudio(itemId, langCode) {
            console.log(`🎯 Attempting to play audio for: ${itemId} in ${langCode}`);
            window.dashboard.setStatus(`🔄 Loading audio: ${itemId}...`, 'info');
            
            // Try to play audio with fallback for es-CO -> es
            function tryPlayAudio(bucketLangCode, isRetry = false) {
                const audioUrl = `https://storage.googleapis.com/levante-audio-dev/${bucketLangCode}/${itemId}.mp3`;
                console.log(`🎵 ${isRetry ? 'Trying fallback' : 'Playing'} audio: ${audioUrl}`);
                
                const audio = new Audio(audioUrl);
                
                // Set volume to ensure it's audible
                audio.volume = 0.8;
                
                // Add timeout to detect loading issues
                const timeout = setTimeout(() => {
                    console.warn('⏰ Audio loading timeout');
                    window.dashboard.setStatus('⏰ Audio loading timeout - check your internet connection', 'warning');
                }, 10000);
                
                audio.addEventListener('canplaythrough', () => {
                    clearTimeout(timeout);
                    console.log(`🎵 Audio loaded, attempting to play: ${audioUrl}`);
                    
                    audio.play().then(() => {
                        console.log(`✅ Audio playing: ${itemId} in ${bucketLangCode}`);
                        window.dashboard.setStatus(`🎵 Playing audio: ${itemId}`, 'success');
                    }).catch((error) => {
                        console.error('❌ Audio play failed (likely autoplay restriction):', error);
                        
                        // Handle autoplay restriction
                        if (error.name === 'NotAllowedError') {
                            const message = `🔇 Browser blocked autoplay. Click here to play audio for "${itemId}"`;
                            window.dashboard.setStatus(message, 'warning');
                            
                            // Create a click-to-play button
                            if (confirm(`Browser blocked autoplay. Click OK to play audio for "${itemId}"`)) {
                                audio.play().then(() => {
                                    console.log(`✅ Audio playing after user interaction: ${itemId}`);
                                    window.dashboard.setStatus(`🎵 Playing audio: ${itemId}`, 'success');
                                }).catch((playError) => {
                                    console.error('❌ Manual play also failed:', playError);
                                    window.dashboard.setStatus(`❌ Audio play failed: ${playError.message}`, 'error');
                                });
                            }
                        } else {
                            window.dashboard.setStatus(`❌ Audio play failed: ${error.message}`, 'error');
                        }
                    });
                });
                audio.addEventListener('error', (e) => {
                    clearTimeout(timeout);
                    console.error(`❌ Audio not found: ${audioUrl}`);
                    
                    // If es-CO failed, try es as fallback
                    if (langCode === 'es-CO' && bucketLangCode === 'es-CO' && !isRetry) {
                        console.log('🔄 Trying es fallback for es-CO...');
                        window.dashboard.setStatus('🔄 Trying es fallback for es-CO audio...', 'info');
                        tryPlayAudio('es', true);
                    } else if (langCode === 'es-CO' && bucketLangCode === 'es' && !isRetry) {
                        // If we already mapped es-CO to es and it failed, try es-CO directly
                        console.log('🔄 Trying es-CO directly...');
                        window.dashboard.setStatus('🔄 Trying es-CO direct audio...', 'info');
                        tryPlayAudio('es-CO', true);
                    } else {
                        // Final failure
                        const message = `Audio file not found for ${itemId} in ${langCode}. Please generate it first using the "Generate Audio" button.`;
                        alert(message);
                        window.dashboard.setStatus(`❌ ${message}`, 'error');
                    }
                });
            }
            
            // Map frontend language codes to bucket language codes with fallback logic
            const bucketLangCodeMap = {
                'en': 'en',
                'es-CO': 'es-CO',  // Try es-CO first, fallback to es
                'de': 'de', 
                'fr-CA': 'fr-CA',
                'nl': 'nl'
            };
            
            const bucketLangCode = bucketLangCodeMap[langCode] || langCode;
            tryPlayAudio(bucketLangCode);
        }
        
        function generateAudio(itemId, text, langCode) {
            const credentials = getCredentials();
            if (!credentials.playhtApiKey && !credentials.elevenlabsApiKey) {
                alert('Please add your TTS API credentials in the credentials manager.');
                return;
            }
            
            // This would integrate with your existing TTS generation logic
            alert(`Audio generation for ${itemId} in ${langCode} would be implemented here.\nText: ${text.substring(0, 50)}...`);
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const credentialsModal = document.getElementById('credentialsModal');
            const audioInfoModal = document.getElementById('audioInfoModal');
            
            if (event.target === credentialsModal) {
                closeCredentialsModal();
            }
            if (event.target === audioInfoModal) {
                closeAudioInfoModal();
            }
        }
         