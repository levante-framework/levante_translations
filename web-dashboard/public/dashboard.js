// Import comprehensive voices
// <script src="comprehensive-voices.js"></script>

/**
 * Levante Translation and Audio Generation Dashboard
 * JavaScript implementation with PlayHT and ElevenLabs API integrations
 */

class AudioDashboard {
    constructor() {
        this.languages = {
            'English': { lang_code: 'en', service: 'ElevenLabs', voice: 'Alexandra - Conversational and Real' },
            'Spanish': { lang_code: 'es-CO', service: 'PlayHT', voice: 'Spanish_Violeta Narrative' },
            'German': { lang_code: 'de', service: 'PlayHT', voice: 'German_Anke Narrative' },
            'French': { lang_code: 'fr-CA', service: 'PlayHT', voice: 'French_Ange Narrative' },
            'Dutch': { lang_code: 'nl', service: 'ElevenLabs', voice: 'Xander' }
        };

        this.data = [];
        this.currentLanguage = 'English';
        this.voiceCache = {};
        this.audioCache = {};
        this.selectedRow = null;
        
        // Track the most recently selected voice
        this.lastSelectedVoice = {
            service: null,
            voiceId: null
        };

        // API Configuration
        this.apiConfig = {
            playht: {
                apiUrl: 'https://api.play.ht/api/v2/tts/stream',
                voicesUrl: 'https://api.play.ht/api/v2/voices',
                // Note: In production, these should be set via environment variables or secure config
                apiKey: this.getApiKey('PLAY_DOT_HT_API_KEY'),
                userId: this.getApiKey('PLAY_DOT_HT_USER_ID')
            },
            elevenlabs: {
                apiUrl: 'https://api.elevenlabs.io/v1/text-to-speech',
                voicesUrl: 'https://api.elevenlabs.io/v1/voices',
                // Note: In production, this should be set via environment variables or secure config
                apiKey: this.getApiKey('ELEVENLABS_API_KEY')
            }
        };

        this.init();
    }

    getApiKey(keyName) {
        // Try to get from localStorage first
        return localStorage.getItem(keyName) || null;
    }

    // Credential management functions
    saveCredentials() {
        const credentials = {
            playhtApiKey: document.getElementById('playhtApiKey').value,
            playhtUserId: document.getElementById('playhtUserId').value,
            elevenlabsApiKey: document.getElementById('elevenlabsApiKey').value
        };

        // Save to localStorage with multiple backup keys
        localStorage.setItem('PLAY_DOT_HT_API_KEY', credentials.playhtApiKey);
        localStorage.setItem('playht_api_key', credentials.playhtApiKey);
        localStorage.setItem('PLAY_DOT_HT_USER_ID', credentials.playhtUserId);
        localStorage.setItem('playht_user_id', credentials.playhtUserId);
        localStorage.setItem('ELEVENLABS_API_KEY', credentials.elevenlabsApiKey);
        localStorage.setItem('elevenlabs_api_key', credentials.elevenlabsApiKey);

        // Also save to sessionStorage as backup
        sessionStorage.setItem('PLAY_DOT_HT_API_KEY', credentials.playhtApiKey);
        sessionStorage.setItem('PLAY_DOT_HT_USER_ID', credentials.playhtUserId);
        sessionStorage.setItem('ELEVENLABS_API_KEY', credentials.elevenlabsApiKey);

        // Update the API config
        this.apiConfig.playht.apiKey = credentials.playhtApiKey;
        this.apiConfig.playht.userId = credentials.playhtUserId;
        this.apiConfig.elevenlabs.apiKey = credentials.elevenlabsApiKey;

        // Ensure backup is current
        this.backupCredentials();

        this.setStatus('Credentials saved successfully with backup storage!', 'success');
        
        // Close the modal
        document.getElementById('credentialsModal').style.display = 'none';
    }

    loadCredentials() {
        const playhtApiKey = localStorage.getItem('PLAY_DOT_HT_API_KEY') || '';
        const playhtUserId = localStorage.getItem('PLAY_DOT_HT_USER_ID') || '';
        const elevenlabsApiKey = localStorage.getItem('ELEVENLABS_API_KEY') || '';

        document.getElementById('playhtApiKey').value = playhtApiKey;
        document.getElementById('playhtUserId').value = playhtUserId;
        document.getElementById('elevenlabsApiKey').value = elevenlabsApiKey;

        // Update the API config
        this.apiConfig.playht.apiKey = playhtApiKey;
        this.apiConfig.playht.userId = playhtUserId;
        this.apiConfig.elevenlabs.apiKey = elevenlabsApiKey;
    }

    async init() {
        // Load credentials silently on startup with backup recovery
        let playhtApiKey = localStorage.getItem('PLAY_DOT_HT_API_KEY') || '';
        let playhtUserId = localStorage.getItem('PLAY_DOT_HT_USER_ID') || '';
        let elevenlabsApiKey = localStorage.getItem('ELEVENLABS_API_KEY') || '';

        // Backup credential recovery - try alternative storage keys
        if (!playhtApiKey) {
            playhtApiKey = localStorage.getItem('playht_api_key') || 
                          localStorage.getItem('PLAYHT_API_KEY') || 
                          sessionStorage.getItem('PLAY_DOT_HT_API_KEY') || '';
        }
        if (!playhtUserId) {
            playhtUserId = localStorage.getItem('playht_user_id') || 
                          localStorage.getItem('PLAYHT_USER_ID') || 
                          sessionStorage.getItem('PLAY_DOT_HT_USER_ID') || '';
        }
        if (!elevenlabsApiKey) {
            elevenlabsApiKey = localStorage.getItem('elevenlabs_api_key') || 
                              localStorage.getItem('ELEVEN_LABS_API_KEY') || 
                              sessionStorage.getItem('ELEVENLABS_API_KEY') || '';
        }

        // Debug: Show what credentials are being loaded
        console.log('DEBUG: Loading credentials from localStorage:', {
            playhtApiKey: playhtApiKey ? 'Present' : 'Missing',
            playhtUserId: playhtUserId ? 'Present' : 'Missing',
            elevenlabsApiKey: elevenlabsApiKey ? 'Present' : 'Missing',
            playhtApiKeyLength: playhtApiKey.length,
            playhtUserIdLength: playhtUserId.length,
            elevenlabsApiKeyLength: elevenlabsApiKey.length
        });

        // Update the API config silently
        this.apiConfig.playht.apiKey = playhtApiKey;
        this.apiConfig.playht.userId = playhtUserId;
        this.apiConfig.elevenlabs.apiKey = elevenlabsApiKey;

        // Ensure credentials are backed up in multiple locations
        this.backupCredentials();
        
        await this.loadData();
        this.setupEventListeners();
        this.createTabs();
        this.updateVoiceDropdowns();
        this.showIntroModal();
    }

    // Backup credentials to multiple storage locations
    backupCredentials() {
        if (this.apiConfig.playht.apiKey) {
            localStorage.setItem('PLAY_DOT_HT_API_KEY', this.apiConfig.playht.apiKey);
            localStorage.setItem('playht_api_key', this.apiConfig.playht.apiKey);
            sessionStorage.setItem('PLAY_DOT_HT_API_KEY', this.apiConfig.playht.apiKey);
        }
        if (this.apiConfig.playht.userId) {
            localStorage.setItem('PLAY_DOT_HT_USER_ID', this.apiConfig.playht.userId);
            localStorage.setItem('playht_user_id', this.apiConfig.playht.userId);
            sessionStorage.setItem('PLAY_DOT_HT_USER_ID', this.apiConfig.playht.userId);
        }
        if (this.apiConfig.elevenlabs.apiKey) {
            localStorage.setItem('ELEVENLABS_API_KEY', this.apiConfig.elevenlabs.apiKey);
            localStorage.setItem('elevenlabs_api_key', this.apiConfig.elevenlabs.apiKey);
            sessionStorage.setItem('ELEVENLABS_API_KEY', this.apiConfig.elevenlabs.apiKey);
        }
    }

    // Recover credentials from backup storage locations
    recoverCredentials() {
        let recovered = false;
        
        // Try to recover PlayHT API Key
        let playhtApiKey = localStorage.getItem('PLAY_DOT_HT_API_KEY') || 
                          localStorage.getItem('playht_api_key') || 
                          localStorage.getItem('PLAYHT_API_KEY') || 
                          sessionStorage.getItem('PLAY_DOT_HT_API_KEY') || '';
        
        // Try to recover PlayHT User ID
        let playhtUserId = localStorage.getItem('PLAY_DOT_HT_USER_ID') || 
                          localStorage.getItem('playht_user_id') || 
                          localStorage.getItem('PLAYHT_USER_ID') || 
                          sessionStorage.getItem('PLAY_DOT_HT_USER_ID') || '';
        
        // Try to recover ElevenLabs API Key
        let elevenlabsApiKey = localStorage.getItem('ELEVENLABS_API_KEY') || 
                              localStorage.getItem('elevenlabs_api_key') || 
                              localStorage.getItem('ELEVEN_LABS_API_KEY') || 
                              sessionStorage.getItem('ELEVENLABS_API_KEY') || '';

        // Update the form fields
        if (playhtApiKey) {
            document.getElementById('playhtApiKey').value = playhtApiKey;
            this.apiConfig.playht.apiKey = playhtApiKey;
            recovered = true;
        }
        if (playhtUserId) {
            document.getElementById('playhtUserId').value = playhtUserId;
            this.apiConfig.playht.userId = playhtUserId;
            recovered = true;
        }
        if (elevenlabsApiKey) {
            document.getElementById('elevenlabsApiKey').value = elevenlabsApiKey;
            this.apiConfig.elevenlabs.apiKey = elevenlabsApiKey;
            recovered = true;
        }

        if (recovered) {
            this.setStatus('Credentials recovered successfully!', 'success');
            // Ensure they're backed up again
            this.backupCredentials();
        } else {
            this.setStatus('No credentials found to recover.', 'error');
        }
    }

    async loadData() {
        try {
            // Try to load real translation data from CSV
            console.log('Attempting to load real translation data...');
            this.data = await this.loadTranslationData();
            console.log(`Successfully loaded ${this.data.length} real translation items`);
            this.setStatus(`✅ Loaded ${this.data.length} real translation items from GitHub`);
        } catch (error) {
            console.error('Error loading translation data:', error);
            console.log('Falling back to sample data...');
            this.setStatus('⚠️ Using sample data (could not load from GitHub)');
            // Fall back to sample data if CSV loading fails
            this.data = await this.loadSampleData();
            console.log(`Loaded ${this.data.length} sample items`);
        }
        
        // Populate the task filter dropdown with available tasks
        this.populateTaskFilter();
    }

    async loadTranslationData() {
        // Use the same URL as the Python version from config.py
        const csvUrl = 'https://raw.githubusercontent.com/levante-framework/levante_translations/l10n_pending/text/translated_prompts.csv';
        
        try {
            const response = await fetch(csvUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const csvText = await response.text();
            return this.parseCSV(csvText);
        } catch (error) {
            console.warn('Could not load from GitHub, trying local file...');
            // Try local file if GitHub fails
            try {
                const response = await fetch('./translated_prompts.csv');
                if (!response.ok) {
                    throw new Error(`Local file not found: ${response.status}`);
                }
                const csvText = await response.text();
                return this.parseCSV(csvText);
            } catch (localError) {
                console.warn('Local file also failed, using sample data');
                throw new Error('Could not load translation data from any source');
            }
        }
    }

    parseCSV(csvText) {
        const lines = csvText.split('\n');
        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        
        const data = [];
        for (let i = 1; i < lines.length; i++) {
            if (lines[i].trim()) {
                const values = this.parseCSVLine(lines[i]);
                if (values.length >= headers.length) {
                    const row = {};
                    headers.forEach((header, index) => {
                        // Map CSV columns to our expected format
                        if (header === 'identifier') {
                            row.item_id = values[index];
                        } else if (header === 'text') {
                            row.en = values[index];
                        } else if (header === 'es-CO') {
                            // Keep both the original column name and simplified version
                            row['es-CO'] = values[index];
                            row.es = values[index];
                        } else if (header === 'fr-CA') {
                            // Keep both the original column name and simplified version
                            row['fr-CA'] = values[index];
                            row.fr = values[index];
                        } else if (header === 'nl-NL') {
                            // Keep both the original column name and simplified version
                            row['nl-NL'] = values[index];
                            row.nl = values[index];
                        } else {
                            row[header] = values[index];
                        }
                    });
                    data.push(row);
                }
            }
        }
        
        console.log(`Loaded ${data.length} translation items`);
        return data;
    }

    parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
                result.push(current.trim());
                current = '';
            } else {
                current += char;
            }
        }
        
        result.push(current.trim());
        return result;
    }

    async loadSampleData() {
        // Extended sample data matching the structure of the Python version
        return [
            {
                item_id: 'general_welcome',
                labels: 'general',
                en: 'Welcome to the audio dashboard',
                es: 'Bienvenido al panel de audio',
                de: 'Willkommen im Audio-Dashboard',
                fr: 'Bienvenue dans le tableau de bord audio',
                nl: 'Welkom bij het audio-dashboard'
            },
            {
                item_id: 'general_instructions',
                labels: 'general',
                en: 'Please follow the instructions carefully',
                es: 'Por favor sigue las instrucciones cuidadosamente',
                de: 'Bitte befolgen Sie die Anweisungen sorgfältig',
                fr: 'Veuillez suivre attentivement les instructions',
                nl: 'Volg de instructies zorgvuldig op'
            },
            {
                item_id: 'general_ready',
                labels: 'general',
                en: 'Are you ready to begin?',
                es: '¿Estás listo para comenzar?',
                de: 'Sind Sie bereit anzufangen?',
                fr: 'Êtes-vous prêt à commencer?',
                nl: 'Ben je klaar om te beginnen?'
            },
            {
                item_id: 'math_problem_01',
                labels: 'math',
                en: 'Please solve this math problem',
                es: 'Por favor resuelve este problema de matemáticas',
                de: 'Bitte lösen Sie dieses Matheproblem',
                fr: 'Veuillez résoudre ce problème de mathématiques',
                nl: 'Los dit wiskundeprobleem op'
            },
            {
                item_id: 'math_addition_01',
                labels: 'math, addition',
                en: 'What is 5 plus 3?',
                es: '¿Cuánto es 5 más 3?',
                de: 'Was ist 5 plus 3?',
                fr: 'Combien font 5 plus 3?',
                nl: 'Hoeveel is 5 plus 3?'
            },
            {
                item_id: 'math_subtraction_01',
                labels: 'math, subtraction',
                en: 'What is 10 minus 4?',
                es: '¿Cuánto es 10 menos 4?',
                de: 'Was ist 10 minus 4?',
                fr: 'Combien font 10 moins 4?',
                nl: 'Hoeveel is 10 min 4?'
            },
            {
                item_id: 'vocab_cat',
                labels: 'vocab',
                en: 'The cat sits on the mat',
                es: 'El gato se sienta en la alfombra',
                de: 'Die Katze sitzt auf der Matte',
                fr: 'Le chat est assis sur le tapis',
                nl: 'De kat zit op de mat'
            },
            {
                item_id: 'vocab_dog',
                labels: 'vocab',
                en: 'The dog runs in the park',
                es: 'El perro corre en el parque',
                de: 'Der Hund läuft im Park',
                fr: 'Le chien court dans le parc',
                nl: 'De hond rent in het park'
            },
            {
                item_id: 'vocab_house',
                labels: 'vocab',
                en: 'The house is very big',
                es: 'La casa es muy grande',
                de: 'Das Haus ist sehr groß',
                fr: 'La maison est très grande',
                nl: 'Het huis is heel groot'
            },
            {
                item_id: 'hearts_flowers_01',
                labels: 'hearts-and-flowers',
                en: 'Choose the correct pattern',
                es: 'Elige el patrón correcto',
                de: 'Wählen Sie das richtige Muster',
                fr: 'Choisissez le bon motif',
                nl: 'Kies het juiste patroon'
            },
            {
                item_id: 'hearts_flowers_02',
                labels: 'hearts-and-flowers',
                en: 'Look at the shapes and colors',
                es: 'Mira las formas y colores',
                de: 'Schauen Sie sich die Formen und Farben an',
                fr: 'Regardez les formes et les couleurs',
                nl: 'Kijk naar de vormen en kleuren'
            },
            {
                item_id: 'hostile_attribution_01',
                labels: 'hostile-attribution',
                en: 'What do you think happened?',
                es: '¿Qué crees que pasó?',
                de: 'Was denkst du ist passiert?',
                fr: 'Que pensez-vous qu\'il s\'est passé?',
                nl: 'Wat denk je dat er is gebeurd?'
            },
            {
                item_id: 'hostile_attribution_02',
                labels: 'hostile-attribution',
                en: 'How would you feel in this situation?',
                es: '¿Cómo te sentirías en esta situación?',
                de: 'Wie würden Sie sich in dieser Situation fühlen?',
                fr: 'Comment vous sentiriez-vous dans cette situation?',
                nl: 'Hoe zou je je voelen in deze situatie?'
            },
            {
                item_id: 'matrix_reasoning_01',
                labels: 'matrix-reasoning',
                en: 'Find the missing piece',
                es: 'Encuentra la pieza que falta',
                de: 'Finden Sie das fehlende Teil',
                fr: 'Trouvez la pièce manquante',
                nl: 'Vind het ontbrekende stuk'
            },
            {
                item_id: 'memory_game_01',
                labels: 'memory-game',
                en: 'Remember the sequence',
                es: 'Recuerda la secuencia',
                de: 'Merken Sie sich die Reihenfolge',
                fr: 'Souvenez-vous de la séquence',
                nl: 'Onthoud de volgorde'
            }
        ];
    }

    setupEventListeners() {
        // Credential management modal (with null checks)
        const manageCredentials = document.getElementById('manageCredentials');
        const saveCredentials = document.getElementById('saveCredentials');
        const recoverCredentials = document.getElementById('recoverCredentials');
        const clearCredentials = document.getElementById('clearCredentials');
        
        if (manageCredentials) {
            manageCredentials.addEventListener('click', () => {
                this.showCredentialsModal();
            });
        }

        if (saveCredentials) {
            saveCredentials.addEventListener('click', () => {
                this.saveCredentials();
            });
        }

        if (recoverCredentials) {
            recoverCredentials.addEventListener('click', () => {
                this.recoverCredentials();
            });
        }

        if (clearCredentials) {
            clearCredentials.addEventListener('click', () => {
                this.clearCredentials();
            });
        }

        // Search and filter functionality (with null checks)
        const searchInput = document.getElementById('searchInput');
        const taskFilter = document.getElementById('taskFilter');
        const clearFilters = document.getElementById('clearFilters');
        
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchItems(e.target.value);
            });
        }

        if (taskFilter) {
            taskFilter.addEventListener('change', (e) => {
                this.filterByTask(e.target.value);
            });
        }

        if (clearFilters) {
            clearFilters.addEventListener('click', () => {
                this.clearAllFilters();
            });
        }

        // Voice filter event listeners (with null checks)
        const ageFilter = document.getElementById('ageFilter');
        const accentFilter = document.getElementById('accentFilter');
        const styleFilter = document.getElementById('styleFilter');
        const categoryFilter = document.getElementById('categoryFilter');
        const libraryOnlyToggle = document.getElementById('libraryOnlyToggle');
        const clearVoiceFilters = document.getElementById('clearVoiceFilters');
        const previewVoices = document.getElementById('previewVoices');
        const showVoicePreview = document.getElementById('showVoicePreview');
        
        if (ageFilter) ageFilter.addEventListener('change', () => this.applyVoiceFilters());
        if (accentFilter) accentFilter.addEventListener('change', () => this.applyVoiceFilters());
        if (styleFilter) styleFilter.addEventListener('change', () => this.applyVoiceFilters());
        if (categoryFilter) categoryFilter.addEventListener('change', () => this.applyVoiceFilters());
        
        // Library Only toggle event listener
        if (libraryOnlyToggle) {
            libraryOnlyToggle.addEventListener('change', () => {
                this.voiceCache = {}; // Clear cache when toggling Library Only mode
                this.updateVoiceDropdowns();
                const isLibraryOnly = libraryOnlyToggle.checked;
                this.setStatus(`ElevenLabs ${isLibraryOnly ? 'Library Only' : 'All Voices'} mode enabled`, 'info');
            });
        }
        
        if (clearVoiceFilters) clearVoiceFilters.addEventListener('click', () => this.clearVoiceFilters());
        if (previewVoices) previewVoices.addEventListener('click', () => this.showVoicePreview());

        // Show voice preview (legacy element name)
        if (showVoicePreview) {
            showVoicePreview.addEventListener('click', () => {
                this.showVoicePreview();
            });
        }

        // Voice selection (with null checks)
        const playhtVoice = document.getElementById('playhtVoice');
        const elevenlabsVoice = document.getElementById('elevenlabsVoice');
        const refreshVoices = document.getElementById('refreshVoices');
        
        if (playhtVoice) {
            playhtVoice.addEventListener('change', (e) => {
                this.onVoiceSelect('PlayHT', e.target.value);
            });
        }

        if (elevenlabsVoice) {
            elevenlabsVoice.addEventListener('change', (e) => {
                this.onVoiceSelect('ElevenLabs', e.target.value);
            });
        }

        // Refresh voices
        if (refreshVoices) {
            refreshVoices.addEventListener('click', () => {
                this.refreshVoices();
            });
        }

        // SSML functionality (with null checks)
        const ssmlHelp = document.getElementById('ssmlHelp');
        const playSSML = document.getElementById('playSSML');
        
        if (ssmlHelp) {
            ssmlHelp.addEventListener('click', () => {
                this.showHelpModal();
            });
        }

        if (playSSML) {
            playSSML.addEventListener('click', () => {
                this.playSSML();
            });
        }

        // Modal close events
        window.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                e.target.style.display = 'none';
            }
        });
    }

    createTabs() {
        const tabButtons = document.getElementById('tabButtons');
        const tabContent = document.getElementById('tabContent');

        console.log('Creating language tabs...', Object.keys(this.languages));

        Object.keys(this.languages).forEach((language, index) => {
            // Create tab button
            const button = document.createElement('button');
            button.className = `tab-button ${index === 0 ? 'active' : ''}`;
            button.textContent = language;
            button.addEventListener('click', () => this.switchTab(language));
            tabButtons.appendChild(button);

            // Create tab content
            const content = document.createElement('div');
            content.className = `tab-content ${index === 0 ? 'active' : ''}`;
            content.id = `tab-${language}`;
            content.innerHTML = this.createTableHTML(language);
            tabContent.appendChild(content);
        });

        // Set initial language
        this.currentLanguage = Object.keys(this.languages)[0];
        console.log('Populating initial table for:', this.currentLanguage);
        this.populateTable(this.currentLanguage);
        console.log('Tabs created successfully');
    }

    createTableHTML(language) {
        const langCode = this.languages[language].lang_code;
        return `
            <table class="data-table" id="table-${language}">
                <thead>
                    <tr>
                        <th>Item ID</th>
                        <th>Task</th>
                        <th>English</th>
                        <th>Translated (${langCode})</th>
                        <th>Audio File</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Data will be populated by JavaScript -->
                </tbody>
            </table>
        `;
    }

    populateTable(language) {
        const table = document.getElementById(`table-${language}`);
        const tbody = table.querySelector('tbody');
        const langCode = this.languages[language].lang_code;

        tbody.innerHTML = '';

        this.data.forEach((item, index) => {
            const row = document.createElement('tr');
            row.dataset.index = index;
            row.addEventListener('click', () => this.selectRow(row, item));

            const translatedText = item[langCode] || 'No translation available';
            const englishText = item.en || 'No English text';
            const audioFilePath = `audio_files/${item.labels}/${langCode}/shared/${item.item_id}.mp3`;
            
            row.innerHTML = `
                <td>${item.item_id}</td>
                <td>${item.labels}</td>
                <td class="text-cell">${this.wrapText(englishText, 40)}</td>
                <td class="text-cell">${this.wrapText(translatedText, 40)}</td>
                <td class="audio-path">${audioFilePath}</td>
                <td>
                    <button class="btn btn-primary" onclick="dashboard.playExistingAudio('${item.item_id}', '${langCode}')">
                        <i class="fas fa-play"></i> Play
                    </button>
                </td>
            `;

            tbody.appendChild(row);
        });
    }

    switchTab(language) {
        // Update tab buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`tab-${language}`).classList.add('active');

        // Update current language and refresh voices
        this.currentLanguage = language;
        this.populateTable(language);
        this.updateVoiceDropdowns();
    }

    selectRow(row, item) {
        // Remove previous selection
        document.querySelectorAll('.data-table tr').forEach(r => {
            r.classList.remove('selected');
        });

        // Add selection to current row
        row.classList.add('selected');
        this.selectedRow = item;

        // Update SSML editor with selected text
        const langCode = this.languages[this.currentLanguage].lang_code;
        const text = item[langCode] || item.en || '';
        document.getElementById('ssmlEditor').value = text;

        this.setStatus(`Selected: ${item.item_id}`);
    }

    searchItems(query) {
        const tables = document.querySelectorAll('.data-table tbody');
        const selectedTask = document.getElementById('taskFilter').value;
        
        tables.forEach(tbody => {
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                const taskCell = row.cells[1];
                const taskText = taskCell ? taskCell.textContent.trim() : '';
                
                // Check both search query and task filter
                const matchesSearch = !query || text.includes(query.toLowerCase());
                const matchesTask = !selectedTask || taskText === selectedTask;
                
                if (matchesSearch && matchesTask) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
        
        // Update status with combined filter info
        let statusMessage = '';
        if (query && selectedTask) {
            statusMessage = `Searching for "${query}" in task: ${selectedTask}`;
        } else if (query) {
            statusMessage = `Searching for "${query}"`;
        } else if (selectedTask) {
            const filteredCount = this.data.filter(item => item.labels === selectedTask).length;
            statusMessage = `Filtered to ${filteredCount} items for task: ${selectedTask}`;
        } else {
            statusMessage = `Showing all ${this.data.length} items`;
        }
        this.setStatus(statusMessage);
    }

    populateTaskFilter() {
        // Get unique task names from the data
        const tasks = [...new Set(this.data.map(item => item.labels))].sort();
        
        const taskFilter = document.getElementById('taskFilter');
        
        // Clear existing options (keep the "All Tasks" option)
        taskFilter.innerHTML = '<option value="">All Tasks</option>';
        
        // Add task options
        tasks.forEach(task => {
            if (task && task.trim()) {
                const option = document.createElement('option');
                option.value = task;
                option.textContent = task;
                taskFilter.appendChild(option);
            }
        });
        
        console.log(`Populated task filter with ${tasks.length} tasks`);
    }

    filterByTask(selectedTask) {
        const tables = document.querySelectorAll('.data-table tbody');
        const searchQuery = document.getElementById('searchInput').value;
        
        tables.forEach(tbody => {
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {
                const taskCell = row.cells[1]; // Task is in the second column
                const text = row.textContent.toLowerCase();
                
                if (taskCell) {
                    const taskText = taskCell.textContent.trim();
                    
                    // Check both task filter and search query
                    const matchesTask = !selectedTask || taskText === selectedTask;
                    const matchesSearch = !searchQuery || text.includes(searchQuery.toLowerCase());
                    
                    if (matchesTask && matchesSearch) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                }
            });
        });
        
        // Update status with combined filter info
        let statusMessage = '';
        if (searchQuery && selectedTask) {
            statusMessage = `Searching for "${searchQuery}" in task: ${selectedTask}`;
        } else if (searchQuery) {
            statusMessage = `Searching for "${searchQuery}"`;
        } else if (selectedTask) {
            const filteredCount = this.data.filter(item => item.labels === selectedTask).length;
            statusMessage = `Filtered to ${filteredCount} items for task: ${selectedTask}`;
        } else {
            statusMessage = `Showing all ${this.data.length} items`;
        }
        this.setStatus(statusMessage);
    }

    clearAllFilters() {
        // Clear search input
        document.getElementById('searchInput').value = '';
        
        // Clear task filter
        document.getElementById('taskFilter').value = '';
        
        // Show all rows
        const tables = document.querySelectorAll('.data-table tbody');
        tables.forEach(tbody => {
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {
                row.style.display = '';
            });
        });
        
        this.setStatus('Filters cleared', 'info');
    }

    applyVoiceFilters() {
        const ageFilter = document.getElementById('ageFilter');
        const accentFilter = document.getElementById('accentFilter');
        const styleFilter = document.getElementById('styleFilter');
        const categoryFilter = document.getElementById('categoryFilter');
        const libraryOnlyToggle = document.getElementById('libraryOnlyToggle');
        
        const ageValue = ageFilter ? ageFilter.value : '';
        const accentValue = accentFilter ? accentFilter.value : '';
        const styleValue = styleFilter ? styleFilter.value : '';
        const categoryValue = categoryFilter ? categoryFilter.value : '';
        const isLibraryOnly = libraryOnlyToggle ? libraryOnlyToggle.checked : false;
        
        // Clear cache and apply filters by updating voice dropdowns
        this.voiceCache = {};
        this.updateVoiceDropdowns();
        
        const activeFilters = [];
        if (ageValue) activeFilters.push(`Age: ${ageValue}`);
        if (accentValue) activeFilters.push(`Accent: ${accentValue}`);
        if (styleValue) activeFilters.push(`Style: ${styleValue}`);
        if (categoryValue) activeFilters.push(`Category: ${categoryValue}`);
        if (isLibraryOnly) activeFilters.push('ElevenLabs Library Only');
        
        if (activeFilters.length > 0) {
            this.setStatus(`Voice filters applied: ${activeFilters.join(', ')}`, 'info');
        } else {
            this.setStatus('Voice filters cleared', 'info');
        }
    }

    clearVoiceFilters() {
        const ageFilter = document.getElementById('ageFilter');
        const accentFilter = document.getElementById('accentFilter');
        const styleFilter = document.getElementById('styleFilter');
        const categoryFilter = document.getElementById('categoryFilter');
        const libraryOnlyToggle = document.getElementById('libraryOnlyToggle');
        
        if (ageFilter) ageFilter.value = '';
        if (accentFilter) accentFilter.value = '';
        if (styleFilter) styleFilter.value = '';
        if (categoryFilter) categoryFilter.value = '';
        if (libraryOnlyToggle) libraryOnlyToggle.checked = false;
        
        // Clear cache and refresh voices
        this.voiceCache = {};
        this.updateVoiceDropdowns();
        this.setStatus('All voice filters cleared', 'info');
    }

    async showVoicePreview() {
        const langCode = this.languages[this.currentLanguage].lang_code;
        
        // Get voices using the same logic as the dropdowns
        const [playhtVoices, elevenlabsVoices] = await Promise.all([
            this.getPlayHTVoices(langCode),
            this.getElevenLabsVoices(langCode)
        ]);
        
        const isLibraryOnly = document.getElementById('libraryOnlyToggle').checked;
        
        // Show modal
        const modal = document.getElementById('voicePreviewModal');
        const grid = document.getElementById('voicePreviewGrid');
        
        // Clear existing content
        grid.innerHTML = '';
        
        // Create section headers and voice cards
        if (playhtVoices.length > 0) {
            const playhtHeader = document.createElement('h3');
            playhtHeader.textContent = `PlayHT Voices (${playhtVoices.length})`;
            playhtHeader.style.cssText = 'grid-column: 1/-1; margin: 20px 0 10px 0; color: #333; border-bottom: 2px solid #007bff;';
            grid.appendChild(playhtHeader);
            
            playhtVoices.forEach(voice => {
                const card = this.createVoiceCard(voice);
                grid.appendChild(card);
            });
        }
        
        if (elevenlabsVoices.length > 0) {
            const elevenlabsHeader = document.createElement('h3');
            elevenlabsHeader.textContent = `ElevenLabs Voices${isLibraryOnly ? ' (Library Only)' : ''} (${elevenlabsVoices.length})`;
            elevenlabsHeader.style.cssText = 'grid-column: 1/-1; margin: 20px 0 10px 0; color: #333; border-bottom: 2px solid #28a745;';
            grid.appendChild(elevenlabsHeader);
            
            elevenlabsVoices.forEach(voice => {
                const card = this.createVoiceCard(voice);
                grid.appendChild(card);
            });
        }
        
        modal.style.display = 'block';
        this.setStatus(`Showing ${playhtVoices.length} PlayHT + ${elevenlabsVoices.length} ElevenLabs voices for ${this.currentLanguage}${isLibraryOnly ? ' (Library Only)' : ''}`, 'info');
    }

    filterVoices(voices, langCode) {
        const ageFilter = document.getElementById('ageFilter').value;
        const accentFilter = document.getElementById('accentFilter').value;
        const styleFilter = document.getElementById('styleFilter').value;
        const categoryFilter = document.getElementById('categoryFilter').value;
        
        // Create a mapping from standard language codes to CSV language formats
        const langMapping = {
            'en': ['English', 'English (US)', 'English (AU)', 'English (CA)', 'English (GB)', 'English (IE)', 'English (IN)', 'English (ZA)', 'en'],
            'es': ['Spanish', 'Spanish (ES)', 'Spanish (MX)', 'Spanish (AR)', 'Spanish (CO)', 'es'],
            'es-CO': ['Spanish', 'Spanish (ES)', 'Spanish (MX)', 'Spanish (AR)', 'Spanish (CO)', 'es'],
            'de': ['German', 'German (DE)', 'de'],
            'fr': ['French', 'French (FR)', 'French (CA)', 'fr'],
            'fr-CA': ['French', 'French (FR)', 'French (CA)', 'fr'],
            'nl': ['Dutch', 'Dutch (NL)', 'nl']
        };
        
        // Get the possible language values for this language code
        const possibleLangs = langMapping[langCode] || [langCode];
        
        return voices.filter(voice => {
            // Language filter - with special handling for voices with empty language fields
            let matchesLang = false;
            
            // First check explicit language matches
            matchesLang = possibleLangs.some(lang => 
                voice.language === lang || 
                voice.language_code === lang ||
                voice.language_code === langCode ||
                voice.language_code === langCode.split('-')[0]
            );
            
            // Special handling for voices with empty language fields
            // If language is empty, use accent to determine language
            if (!matchesLang && (!voice.language || voice.language === '') && (!voice.language_code || voice.language_code === '')) {
                const accent = (voice.accent || '').toLowerCase();
                
                if (langCode === 'en') {
                    // English: American, British, Australian, Canadian, etc.
                    matchesLang = accent.includes('american') || accent.includes('british') || 
                                 accent.includes('australian') || accent.includes('canadian') ||
                                 accent.includes('english') || accent.includes('us') || accent.includes('uk');
                } else if (langCode === 'es' || langCode === 'es-CO') {
                    // Spanish: Only if explicitly Spanish accent
                    matchesLang = accent.includes('spanish') || accent.includes('mexican') || 
                                 accent.includes('argentinian') || accent.includes('colombian');
                } else if (langCode === 'de') {
                    // German: Only if explicitly German accent
                    matchesLang = accent.includes('german') || accent.includes('austrian');
                } else if (langCode === 'fr' || langCode === 'fr-CA') {
                    // French: Only if explicitly French accent
                    matchesLang = accent.includes('french') || accent.includes('canadian');
                } else if (langCode === 'nl') {
                    // Dutch: Only if explicitly Dutch accent
                    matchesLang = accent.includes('dutch') || accent.includes('netherlands');
                }
            }
            
            if (!matchesLang) {
                return false;
            }
            
            // Age filter
            if (ageFilter && voice.age !== ageFilter) {
                return false;
            }
            
            // Accent filter
            if (accentFilter && voice.accent !== accentFilter) {
                return false;
            }
            
            // Style filter
            if (styleFilter && voice.style !== styleFilter && voice.voice_type !== styleFilter) {
                return false;
            }
            
            // Category filter
            if (categoryFilter && voice.category !== categoryFilter) {
                return false;
            }
            
            return true;
        });
    }

    createVoiceCard(voice) {
        const card = document.createElement('div');
        card.className = 'voice-card';
        
        const serviceBadge = voice.service === 'ElevenLabs' ? 
            '<span style="background: #6c5ce7; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">ElevenLabs</span>' :
            '<span style="background: #00b894; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">PlayHT</span>';
        
        card.innerHTML = `
            <h4>${voice.display_name || voice.name} ${serviceBadge}</h4>
            <div class="voice-details">
                ${voice.gender ? `Gender: ${voice.gender}` : ''}
                ${voice.age ? ` • Age: ${voice.age}` : ''}
                ${voice.accent ? ` • Accent: ${voice.accent}` : ''}
                ${voice.style || voice.voice_type ? ` • Style: ${voice.style || voice.voice_type}` : ''}
                ${voice.category ? ` • Category: ${voice.category}` : ''}
            </div>
            ${voice.description ? `<p style="font-size: 12px; color: #888; margin: 5px 0;">${voice.description}</p>` : ''}
            ${voice.sample_url ? `
                <div class="voice-sample">
                    <audio controls preload="none">
                        <source src="${voice.sample_url}" type="audio/mpeg">
                        Your browser does not support the audio element.
                    </audio>
                </div>
            ` : ''}
            <button class="select-voice-btn" onclick="dashboard.selectVoiceFromPreview('${voice.service}', '${voice.voice_id || voice.id}')">
                Select This Voice
            </button>
        `;
        
        return card;
    }

    selectVoiceFromPreview(service, voiceId) {
        // Set the voice in the appropriate dropdown
        const dropdown = service === 'ElevenLabs' ? 
            document.getElementById('elevenlabsVoice') : 
            document.getElementById('playhtVoice');
        
        dropdown.value = voiceId;
        
        // Close the modal
        document.getElementById('voicePreviewModal').style.display = 'none';
        
        // Generate audio with the selected voice
        this.onVoiceSelect(service, voiceId);
        
        this.setStatus(`Selected ${service} voice`, 'success');
    }

    async updateVoiceDropdowns() {
        const langCode = this.languages[this.currentLanguage].lang_code;
        
        try {
            // Clear existing options
            const playhtSelect = document.getElementById('playhtVoice');
            const elevenlabsSelect = document.getElementById('elevenlabsVoice');
            
            playhtSelect.innerHTML = '<option value="">Loading PlayHT voices...</option>';
            elevenlabsSelect.innerHTML = '<option value="">Loading ElevenLabs voices...</option>';

            // Load voices for current language
            const [playhtVoices, elevenlabsVoices] = await Promise.all([
                this.getPlayHTVoices(langCode),
                this.getElevenLabsVoices(langCode)
            ]);

            // Populate PlayHT dropdown
            playhtSelect.innerHTML = '<option value="">Select PlayHT Voice...</option>';
            playhtVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.voice_id || voice.id;
                option.textContent = `${voice.display_name || voice.name}${voice.accent ? ` (${voice.accent})` : ''}${voice.age ? ` - ${voice.age}` : ''}`;
                option.title = voice.description || voice.name;
                playhtSelect.appendChild(option);
            });

            // Populate ElevenLabs dropdown
            elevenlabsSelect.innerHTML = '<option value="">Select ElevenLabs Voice...</option>';
            elevenlabsVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.voice_id || voice.id;
                option.textContent = `${voice.display_name || voice.name}${voice.accent ? ` (${voice.accent})` : ''}${voice.age ? ` - ${voice.age}` : ''}`;
                option.title = voice.description || voice.name;
                elevenlabsSelect.appendChild(option);
            });

        } catch (error) {
            console.error('Error updating voice dropdowns:', error);
            this.setStatus('Error loading voices');
        }
    }

    async getPlayHTVoices(langCode) {
        // Load comprehensive voice data
        const allVoices = await this.loadComprehensiveVoices();
        
        // Debug: Log the language code and first few voices
        console.log('DEBUG: Getting PlayHT voices for language:', langCode);
        console.log('DEBUG: Total voices loaded:', allVoices.length);
        console.log('DEBUG: First 3 voices:', allVoices.slice(0, 3));
        
        // Create a mapping from standard language codes to CSV language formats
        const langMapping = {
            'en': ['English', 'English (US)', 'English (AU)', 'English (CA)', 'English (GB)', 'English (IE)', 'English (IN)', 'English (ZA)', 'en'],
            'es': ['Spanish', 'Spanish (ES)', 'Spanish (MX)', 'Spanish (AR)', 'Spanish (CO)', 'es'],
            'es-CO': ['Spanish', 'Spanish (ES)', 'Spanish (MX)', 'Spanish (AR)', 'Spanish (CO)', 'es'],
            'de': ['German', 'German (DE)', 'de'],
            'fr': ['French', 'French (FR)', 'French (CA)', 'fr'],
            'fr-CA': ['French', 'French (FR)', 'French (CA)', 'fr'],
            'nl': ['Dutch', 'Dutch (NL)', 'nl']
        };
        
        // Get the possible language values for this language code
        const possibleLangs = langMapping[langCode] || [langCode];
        
        // Filter PlayHT voices for the requested language
        let playhtVoices = allVoices.filter(voice => {
            if (voice.service !== 'PlayHT') return false;
            
            // PlayHT voices use the 'language' field, not 'language_code'
            // Check both fields to be safe
            const voiceLang = voice.language || voice.language_code || '';
            return langMapping[langCode] && langMapping[langCode].includes(voiceLang);
        });
        
        // Debug: Log PlayHT filtering results
        console.log('DEBUG: PlayHT voices before filtering:', allVoices.filter(voice => voice.service === 'PlayHT').length);
        console.log('DEBUG: Language mapping for', langCode, ':', langMapping[langCode]);
        console.log('DEBUG: PlayHT voices after language filtering:', playhtVoices.length);
        
        // Special debugging for Spanish voices
        if (langCode === 'es-CO') {
            const spanishPlayHTVoices = allVoices.filter(voice => voice.service === 'PlayHT');
            console.log('DEBUG: All PlayHT voices for Spanish debugging:', spanishPlayHTVoices.map(v => ({
                name: v.name,
                language: v.language,
                language_code: v.language_code,
                service: v.service
            })));
        }
        
        // Enhanced debugging for English voices too
        if (langCode === 'en') {
            const englishPlayHTVoices = allVoices.filter(voice => voice.service === 'PlayHT').slice(0, 5);
            console.log('DEBUG: First 5 PlayHT voices for English debugging:', englishPlayHTVoices.map(v => ({
                name: v.name,
                language: v.language,
                language_code: v.language_code,
                service: v.service
            })));
        }
        
        console.log('DEBUG: PlayHT voices sample:', playhtVoices.slice(0, 3).map(v => ({
            name: v.name,
            language_code: v.language_code,
            service: v.service
        })));
        
        // Apply additional filters
        playhtVoices = this.filterVoices(playhtVoices, langCode);
        console.log('DEBUG: PlayHT voices after all filters:', playhtVoices.length);
        
        // Cache the results
        const cacheKey = `playht_${langCode}`;
        this.voiceCache[cacheKey] = playhtVoices;
        
        return playhtVoices;
    }

    async getElevenLabsVoices(langCode) {
        // Check if we have ElevenLabs API credentials
        const hasApiKey = this.apiConfig.elevenlabs.apiKey && this.apiConfig.elevenlabs.apiKey.trim() !== '';
        
        if (hasApiKey) {
            // Use live API to get voices from the user's account
            console.log('DEBUG: Using ElevenLabs API to fetch voices from your account');
            return await this.fetchElevenLabsVoicesFromAPI(langCode);
        } else {
            // Fall back to CSV data
            console.log('DEBUG: No ElevenLabs API key found, using CSV data');
            return await this.getElevenLabsVoicesFromCSV(langCode);
        }
    }

    async fetchElevenLabsVoicesFromAPI(langCode) {
        try {
            console.log('DEBUG: Fetching ElevenLabs voices from API for language:', langCode);
            console.log('DEBUG: Using API key:', this.apiConfig.elevenlabs.apiKey.substring(0, 10) + '...');
            
            // First, let's check the user info to see which account we're accessing
            try {
                console.log('DEBUG: Checking user account info...');
                const userResponse = await fetch('https://api.elevenlabs.io/v1/user', {
                    headers: {
                        'xi-api-key': this.apiConfig.elevenlabs.apiKey
                    }
                });
                
                if (userResponse.ok) {
                    const userInfo = await userResponse.json();
                    console.log('DEBUG: User account info:', userInfo);
                    console.log('DEBUG: Account ID:', userInfo.subscription?.tier || 'unknown');
                    console.log('DEBUG: User ID:', userInfo.xi_api_key?.substring(0, 10) + '...' || 'unknown');
                } else {
                    console.log('DEBUG: Could not fetch user info:', userResponse.status);
                }
            } catch (userError) {
                console.log('DEBUG: Error fetching user info:', userError);
            }
            
            // Try to get user's personal voice library first
            let response;
            let data;
            
            try {
                // First try the user's personal voice library endpoint
                console.log('DEBUG: Attempting to fetch from user voice library...');
                response = await fetch('https://api.elevenlabs.io/v1/voices?show_legacy=false', {
                    headers: {
                        'xi-api-key': this.apiConfig.elevenlabs.apiKey
                    }
                });
                
                if (response.ok) {
                    data = await response.json();
                    console.log('DEBUG: Successfully fetched from user voice library');
                    console.log('DEBUG: User library response:', data);
                } else {
                    throw new Error(`User library API error: ${response.status}`);
                }
            } catch (userLibError) {
                console.log('DEBUG: User library fetch failed, trying general voices endpoint...');
                // Fallback to general voices endpoint
                response = await fetch('https://api.elevenlabs.io/v1/voices', {
                    headers: {
                        'xi-api-key': this.apiConfig.elevenlabs.apiKey
                    }
                });
                
                if (!response.ok) {
                    console.error('DEBUG: General API response not OK:', response.status, response.statusText);
                    throw new Error(`ElevenLabs API error: ${response.status} - ${response.statusText}`);
                }
                
                data = await response.json();
                console.log('DEBUG: Using general voices endpoint as fallback');
            }

            console.log('DEBUG: Raw API response:', data);
            console.log('DEBUG: Number of voices in API response:', data.voices ? data.voices.length : 0);
            
            // Search specifically for Spanish voices like Julia
            if (data.voices && data.voices.length > 0) {
                console.log('DEBUG: Searching for Spanish voices...');
                const spanishVoices = data.voices.filter(voice => {
                    const name = voice.name.toLowerCase();
                    const lang = (voice.labels?.language || '').toLowerCase();
                    const isSpanish = name.includes('julia') || 
                                     name.includes('spanish') ||
                                     name.includes('ana maría') ||
                                     name.includes('ana maria') ||
                                     lang.includes('spanish') ||
                                     lang.includes('es');
                    return isSpanish;
                });
                console.log('DEBUG: Found Spanish voices:', spanishVoices);
                
                if (spanishVoices.length === 0) {
                    console.log('DEBUG: NO SPANISH VOICES FOUND! This suggests API key is accessing wrong account.');
                    console.log('DEBUG: Expected to find voices like "Julia" but none found.');
                }
            }
            
            // If we have exactly 27 voices, these are likely your My Voices
            if (data.voices && data.voices.length === 27) {
                console.log('DEBUG: Found exactly 27 voices - this appears to be your My Voices library!');
            } else if (data.voices && data.voices.length > 27) {
                console.log(`DEBUG: Found ${data.voices.length} voices - filtering to identify your My Voices...`);
            }
            
            // COMPREHENSIVE VOICE ANALYSIS - Show complete lab account overview
            if (data.voices && data.voices.length > 0) {
                console.log('\n=== 🎤 MY VOICES LIBRARY ANALYSIS ===');
                console.log(`Total voices returned by API: ${data.voices.length}`);
                
                // Group by language
                const voicesByLanguage = {};
                const voicesByCategory = {};
                
                data.voices.forEach((voice, index) => {
                    const lang = voice.labels?.language || 'unknown';
                    const category = voice.category || 'unknown';
                    
                    if (!voicesByLanguage[lang]) voicesByLanguage[lang] = [];
                    if (!voicesByCategory[category]) voicesByCategory[category] = [];
                    
                    voicesByLanguage[lang].push(voice);
                    voicesByCategory[category].push(voice);
                    
                    console.log(`${index + 1}. "${voice.name}" - Language: "${lang}", Category: "${category}", ID: ${voice.voice_id}`);
                });
                
                console.log('\n=== 📊 MY VOICES LANGUAGE BREAKDOWN ===');
                Object.keys(voicesByLanguage).sort().forEach(lang => {
                    console.log(`${lang.toUpperCase()}: ${voicesByLanguage[lang].length} voices`);
                    voicesByLanguage[lang].forEach(voice => {
                        console.log(`  - ${voice.name} (${voice.category})`);
                    });
                });
                
                console.log('\n=== 📂 MY VOICES CATEGORY BREAKDOWN ===');
                Object.keys(voicesByCategory).sort().forEach(category => {
                    console.log(`\n${category.toUpperCase()}: ${voicesByCategory[category].length} voices`);
                    voicesByCategory[category].forEach(voice => {
                        console.log(`  - "${voice.name}" (Language: ${voice.labels?.language || 'unknown'})`);
                    });
                });
                console.log('=== END MY VOICES ANALYSIS ===\n');
            }
            
            // Log first few voices to see their structure (original debug code)
            if (data.voices && data.voices.length > 0) {
                console.log('DEBUG: First 3 voices from API:', data.voices.slice(0, 3));
                console.log('DEBUG: Sample voice labels:', data.voices[0].labels);
                console.log('DEBUG: Sample voice category:', data.voices[0].category);
                
                // Check for ownership indicators
                console.log('DEBUG: Full structure of first voice:');
                console.log(data.voices[0]);
                
                // Look for potential ownership fields
                data.voices.slice(0, 5).forEach((voice, index) => {
                    console.log(`DEBUG: Voice ${index + 1} detailed structure:`, {
                        name: voice.name,
                        voice_id: voice.voice_id,
                        category: voice.category,
                        available_for_tiers: voice.available_for_tiers,
                        sharing: voice.sharing,
                        high_quality_base_model_ids: voice.high_quality_base_model_ids,
                        labels: voice.labels,
                        preview_url: voice.preview_url,
                        available_models: voice.available_models
                    });
                });
            }
            
            // Check if Library Only mode is enabled
            const libraryOnlyToggle = document.getElementById('libraryOnlyToggle');
            const isLibraryOnly = libraryOnlyToggle && libraryOnlyToggle.checked;
            console.log('DEBUG: Library Only mode:', isLibraryOnly);
            
            // Create a mapping from standard language codes to API language formats
            const langMapping = {
                'en': ['en', 'english'],
                'es': ['es', 'spanish'],
                'es-CO': ['es', 'spanish'],
                'de': ['de', 'german'],
                'fr': ['fr', 'french'],
                'fr-CA': ['fr', 'french'],
                'nl': ['nl', 'dutch']
            };
            
            const possibleLangs = langMapping[langCode] || [langCode];
            console.log('DEBUG: Looking for API languages:', possibleLangs);
            
            let filteredVoices = data.voices || [];
            console.log('DEBUG: Starting with voices:', filteredVoices.length);
            
            if (isLibraryOnly) {
                // Library Only mode: Show all available voices (owned + professional) filtered by language
                console.log('DEBUG: Library Only mode - showing all available voices filtered by language');
                
                // Skip category filtering completely - show all voices available to this account
                console.log(`DEBUG: Starting with all ${filteredVoices.length} available voices`);
                
                // Apply language filtering to all available voices
                const beforeLangFilter = filteredVoices.length;
                filteredVoices = filteredVoices.filter(voice => {
                    const labels = voice.labels || {};
                    const voiceLang = (labels.language || '').toLowerCase();
                    
                    // Check if voice language matches any of the possible languages
                    let matchesLang = possibleLangs.some(lang => 
                        voiceLang.includes(lang.toLowerCase())
                    );
                    
                    // Enhanced Spanish detection
                    if (!matchesLang && (langCode === 'es' || langCode === 'es-CO')) {
                        // Accept various Spanish language formats
                        matchesLang = voiceLang.includes('spanish') || 
                                     voiceLang.includes('español') ||
                                     voiceLang === 'es' ||
                                     voiceLang === 'es-es' ||
                                     voiceLang === 'es-mx' ||
                                     voiceLang === 'es-ar' ||
                                     voiceLang === 'es-co' ||
                                     voiceLang.startsWith('es-');
                        
                        if (matchesLang) {
                            console.log(`DEBUG: Found Spanish voice: "${voice.name}" with language: "${voiceLang}"`);
                        }
                    }
                    
                    // Enhanced German detection
                    if (!matchesLang && langCode === 'de') {
                        matchesLang = voiceLang.includes('german') || 
                                     voiceLang.includes('deutsch') ||
                                     voiceLang === 'de' ||
                                     voiceLang === 'de-de' ||
                                     voiceLang === 'de-at' ||
                                     voiceLang === 'de-ch' ||
                                     voiceLang.startsWith('de-');
                    }
                    
                    // Enhanced French detection
                    if (!matchesLang && (langCode === 'fr' || langCode === 'fr-CA')) {
                        matchesLang = voiceLang.includes('french') || 
                                     voiceLang.includes('français') ||
                                     voiceLang === 'fr' ||
                                     voiceLang === 'fr-fr' ||
                                     voiceLang === 'fr-ca' ||
                                     voiceLang === 'fr-ch' ||
                                     voiceLang === 'fr-be' ||
                                     voiceLang.startsWith('fr-');
                    }
                    
                    // Enhanced Dutch detection
                    if (!matchesLang && langCode === 'nl') {
                        matchesLang = voiceLang.includes('dutch') || 
                                     voiceLang.includes('nederlands') ||
                                     voiceLang === 'nl' ||
                                     voiceLang === 'nl-nl' ||
                                     voiceLang === 'nl-be' ||
                                     voiceLang.startsWith('nl-');
                    }
                    
                    // Also include voices with unknown/empty language on all tabs for now
                    if (!matchesLang && (voiceLang === '' || voiceLang === 'unknown')) {
                        console.log(`DEBUG: Including unknown language voice "${voice.name}" on ${langCode} tab for debugging`);
                        matchesLang = true; // Temporarily include all unknown voices to see what you have
                    }
                    
                    console.log(`DEBUG: Voice "${voice.name}" - Language: "${voiceLang}", Target: "${langCode}", Category: "${voice.category}", Matches: ${matchesLang}`);
                    return matchesLang;
                });
                
                console.log(`DEBUG: AFTER language filter: ${beforeLangFilter} -> ${filteredVoices.length} voices for ${langCode} tab`);
                console.log(`DEBUG: Library Only mode - Final voice count for ${langCode} tab: ${filteredVoices.length}`);
            } else {
                // Apply language filtering - be more flexible with language matching
                const beforeLangFilter = filteredVoices.length;
                filteredVoices = filteredVoices.filter(voice => {
                    const labels = voice.labels || {};
                    const voiceLang = (labels.language || '').toLowerCase();
                    
                    // Check if voice language matches any of the possible languages
                    let matchesLang = possibleLangs.some(lang => 
                        voiceLang.includes(lang.toLowerCase())
                    );
                    
                    // If no language match and we're looking for Spanish, also check if the voice can handle Spanish
                    // Most English voices from lab accounts can handle multiple languages
                    if (!matchesLang && (langCode === 'es' || langCode === 'es-CO')) {
                        // For Spanish, also accept English voices since many can handle Spanish
                        matchesLang = voiceLang === 'en' || voiceLang === 'english';
                    }
                    
                    // Similarly for other languages - English voices are often multilingual
                    if (!matchesLang && langCode !== 'en') {
                        // Accept English voices for any language as they're often multilingual
                        matchesLang = voiceLang === 'en' || voiceLang === 'english';
                    }
                    
                    console.log(`DEBUG: Voice "${voice.name}" - Language: "${voiceLang}", Target: "${langCode}", Matches: ${matchesLang}`);
                    return matchesLang;
                });
                
                console.log(`DEBUG: After language filter: ${beforeLangFilter} -> ${filteredVoices.length} voices`);
            }
            
            // If no voices match, let's see what languages are actually available
            if (filteredVoices.length === 0 && data.voices && data.voices.length > 0) {
                console.log('DEBUG: No voices matched language filter. Available languages in your account:');
                const availableLanguages = [...new Set(data.voices.map(v => v.labels?.language || 'unknown'))];
                console.log('DEBUG: Available languages:', availableLanguages);
                
                // For debugging, let's also check without language filtering
                console.log('DEBUG: All voices without language filtering:');
                data.voices.forEach((voice, i) => {
                    if (i < 5) { // Show first 5
                        console.log(`DEBUG: Voice ${i + 1}: "${voice.name}" - Language: "${voice.labels?.language || 'unknown'}", Category: "${voice.category}"`);
                    }
                });
            }
            
            // Transform to match expected format
            const transformedVoices = filteredVoices.map(voice => ({
                service: 'ElevenLabs',
                voice_id: voice.voice_id,
                id: voice.voice_id,
                name: voice.name,
                display_name: voice.name,
                language: voice.labels?.language || langCode,
                language_code: langCode,
                gender: voice.labels?.gender || 'unknown',
                accent: voice.labels?.accent || '',
                age: voice.labels?.age || '',
                category: voice.category || 'professional',
                description: voice.description || ''
            }));
            
            console.log(`DEBUG: Final filtered ElevenLabs voices from API for ${langCode}:`, transformedVoices.length);
            if (transformedVoices.length > 0) {
                console.log('DEBUG: Sample transformed voices:', transformedVoices.slice(0, 3));
            }
            
            return transformedVoices;
            
        } catch (error) {
            console.error('Error fetching ElevenLabs voices from API:', error);
            // Fall back to CSV data if API fails
            console.log('DEBUG: API failed, falling back to CSV data');
            return await this.getElevenLabsVoicesFromCSV(langCode);
        }
    }

    async getElevenLabsVoicesFromCSV(langCode) {
        // Load comprehensive voice data
        const allVoices = await this.loadComprehensiveVoices();
        
        // Check if Library Only mode is enabled
        const libraryOnlyToggle = document.getElementById('libraryOnlyToggle');
        const isLibraryOnly = libraryOnlyToggle && libraryOnlyToggle.checked;
        
        // Debug: Log the language code and first few voices
        console.log('DEBUG: Getting ElevenLabs voices from CSV for language:', langCode);
        console.log('DEBUG: Library Only mode:', isLibraryOnly);
        console.log('DEBUG: Total voices loaded:', allVoices.length);
        
        // Filter ElevenLabs voices
        let elevenlabsVoices = allVoices.filter(voice => {
            return voice.service === 'ElevenLabs';
        });
        
        console.log('DEBUG: All ElevenLabs voices from CSV:', elevenlabsVoices.length);
        
        // Create a mapping from standard language codes to CSV language formats
        const langMapping = {
            'en': ['English', 'English (US)', 'English (AU)', 'English (CA)', 'English (GB)', 'English (IE)', 'English (IN)', 'English (ZA)', 'en'],
            'es': ['Spanish', 'Spanish (ES)', 'Spanish (MX)', 'Spanish (AR)', 'Spanish (CO)', 'es'],
            'es-CO': ['Spanish', 'Spanish (ES)', 'Spanish (MX)', 'Spanish (AR)', 'Spanish (CO)', 'es'],
            'de': ['German', 'German (DE)', 'de'],
            'fr': ['French', 'French (FR)', 'French (CA)', 'fr'],
            'fr-CA': ['French', 'French (FR)', 'French (CA)', 'fr'],
            'nl': ['Dutch', 'Dutch (NL)', 'nl']
        };
        
        // Get the possible language values for this language code
        const possibleLangs = langMapping[langCode] || [langCode];
        console.log('DEBUG: Looking for languages:', possibleLangs);
        
        if (isLibraryOnly) {
            // Library Only mode: Show all available voices filtered by language
            console.log('DEBUG: Library Only mode (CSV) - showing all available voices filtered by language');
            
            // Skip category filtering - use all ElevenLabs voices and filter by language
            // Apply language filtering
            elevenlabsVoices = elevenlabsVoices.filter(voice => {
                const matchesLang = possibleLangs.some(lang => 
                    voice.language === lang || 
                    voice.language_code === lang ||
                    voice.language_code === langCode ||
                    voice.language_code === langCode.split('-')[0]
                );
                
                // Special handling for voices with empty language fields (use accent to determine language)
                if (!matchesLang && (!voice.language || voice.language === '') && (!voice.language_code || voice.language_code === '')) {
                    const accent = (voice.accent || '').toLowerCase();
                    
                    if (langCode === 'en') {
                        return accent.includes('american') || accent.includes('british') || 
                               accent.includes('australian') || accent.includes('canadian') ||
                               accent.includes('english') || accent.includes('us') || accent.includes('uk');
                    } else if (langCode === 'es' || langCode === 'es-CO') {
                        return accent.includes('spanish') || accent.includes('mexican') || 
                               accent.includes('argentinian') || accent.includes('colombian');
                    } else if (langCode === 'de') {
                        return accent.includes('german') || accent.includes('austrian');
                    } else if (langCode === 'fr' || langCode === 'fr-CA') {
                        return accent.includes('french') || accent.includes('canadian');
                    } else if (langCode === 'nl') {
                        return accent.includes('dutch') || accent.includes('netherlands');
                    }
                    return false;
                }
                
                return matchesLang;
            });
            
            console.log('DEBUG: ElevenLabs Library Only voices for', langCode, ':', elevenlabsVoices.length);
            console.log('DEBUG: Library Only mode - showing language-filtered voices on', langCode, 'tab');
        } else {
            // Normal mode: Apply language filtering
            elevenlabsVoices = elevenlabsVoices.filter(voice => {
                const matchesLang = possibleLangs.some(lang => 
                    voice.language === lang || 
                    voice.language_code === lang ||
                    voice.language_code === langCode ||
                    voice.language_code === langCode.split('-')[0]
                );
                
                // Special handling for voices with empty language fields (use accent to determine language)
                if (!matchesLang && (!voice.language || voice.language === '') && (!voice.language_code || voice.language_code === '')) {
                    const accent = (voice.accent || '').toLowerCase();
                    
                    if (langCode === 'en') {
                        return accent.includes('american') || accent.includes('british') || 
                               accent.includes('australian') || accent.includes('canadian') ||
                               accent.includes('english') || accent.includes('us') || accent.includes('uk');
                    } else if (langCode === 'es' || langCode === 'es-CO') {
                        return accent.includes('spanish') || accent.includes('mexican') || 
                               accent.includes('argentinian') || accent.includes('colombian');
                    } else if (langCode === 'de') {
                        return accent.includes('german') || accent.includes('austrian');
                    } else if (langCode === 'fr' || langCode === 'fr-CA') {
                        return accent.includes('french') || accent.includes('canadian');
                    } else if (langCode === 'nl') {
                        return accent.includes('dutch') || accent.includes('netherlands');
                    }
                    return false;
                }
                
                return matchesLang;
            });
            
            console.log('DEBUG: ElevenLabs voices after language filtering for', langCode, ':', elevenlabsVoices.length);
        }
        
        // Debug: Show sample voices
        if (elevenlabsVoices.length > 0) {
            console.log('DEBUG: Sample ElevenLabs voices:', elevenlabsVoices.slice(0, 3));
        }
        
        return elevenlabsVoices;
    }

    async loadComprehensiveVoices() {
        // Check cache first
        if (this.comprehensiveVoices) {
            return this.comprehensiveVoices;
        }

        try {
            const response = await fetch('https://raw.githubusercontent.com/levante-framework/levante_translations/main/comprehensive_female_voices_20250721_145331.csv');
            const csvText = await response.text();
            
            // Parse CSV
            const lines = csvText.split('\n');
            const headers = lines[0].split(',');
            const voices = [];
            
            console.log('DEBUG: CSV headers:', headers);
            console.log('DEBUG: Total CSV lines:', lines.length);
            
            for (let i = 1; i < lines.length; i++) {
                const line = lines[i].trim();
                if (line) {
                    const values = this.parseCSVLine(line);
                    if (values.length >= headers.length) {
                        const voice = {};
                        headers.forEach((header, index) => {
                            voice[header.trim()] = values[index] ? values[index].trim() : '';
                        });
                        
                        // Standardize the data format
                        voice.voice_id = voice.id; // ElevenLabs format
                        voice.display_name = voice.name;
                        voices.push(voice);
                        
                        // Debug: Log first few voices
                        if (i <= 5) {
                            console.log(`DEBUG: Voice ${i}:`, voice);
                        }
                    }
                }
            }
            
            this.comprehensiveVoices = voices;
            console.log(`Loaded ${voices.length} comprehensive voices`);
            
            // Debug: Count voices by service
            const serviceCount = {};
            voices.forEach(voice => {
                serviceCount[voice.service] = (serviceCount[voice.service] || 0) + 1;
            });
            console.log('DEBUG: Voices by service:', serviceCount);
            
            return voices;
            
        } catch (error) {
            console.error('Error loading comprehensive voices:', error);
            // Fallback to embedded voices if CSV loading fails
            return this.getFallbackVoices();
        }
    }

    getFallbackVoices() {
        // Fallback to the original embedded voice data
        return [
            // PlayHT voices
            { service: 'PlayHT', id: 's3://voice-cloning-zero-shot/adb83b67-8d75-48ff-ad4d-a0840d231ef1/original/manifest.json', name: 'Inara', language_code: 'en', gender: 'female', voice_id: 's3://voice-cloning-zero-shot/adb83b67-8d75-48ff-ad4d-a0840d231ef1/original/manifest.json', display_name: 'Inara' },
            { service: 'PlayHT', id: 's3://voice-cloning-zero-shot/326c3793-b5b1-4ce3-a8ec-22c95d8553f0/original/manifest.json', name: 'Violeta Narrative', language_code: 'es-CO', gender: 'female', voice_id: 's3://voice-cloning-zero-shot/326c3793-b5b1-4ce3-a8ec-22c95d8553f0/original/manifest.json', display_name: 'Violeta Narrative' },
            { service: 'PlayHT', id: 's3://voice-cloning-zero-shot/2f91566e-215a-4234-96e2-60acf07fed5e/original/manifest.json', name: 'Anke Narrative', language_code: 'de', gender: 'female', voice_id: 's3://voice-cloning-zero-shot/2f91566e-215a-4234-96e2-60acf07fed5e/original/manifest.json', display_name: 'Anke Narrative' },
            
            // ElevenLabs voices
            { service: 'ElevenLabs', id: 'kdmDKE6EkgrWrrykO9Qt', name: 'Alexandra - Conversational and Real', language_code: 'en', gender: 'female', voice_id: 'kdmDKE6EkgrWrrykO9Qt', display_name: 'Alexandra - Conversational and Real' },
            { service: 'ElevenLabs', id: 'm7yTemJqdIqrcNleANfX', name: 'Ana María - Calm & natural neutral Spanish', language_code: 'es', gender: 'female', voice_id: 'm7yTemJqdIqrcNleANfX', display_name: 'Ana María - Calm & natural neutral Spanish' },
            { service: 'ElevenLabs', id: 'v3V1d2rk6528UrLKRuy8', name: 'Susi', language_code: 'de', gender: 'female', voice_id: 'v3V1d2rk6528UrLKRuy8', display_name: 'Susi' },
            { service: 'ElevenLabs', id: 'kwhMCf63M8O3rCfnQ3oQ', name: 'Caroline - Top France - Narrative, warm, sweet', language_code: 'fr', gender: 'female', voice_id: 'kwhMCf63M8O3rCfnQ3oQ', display_name: 'Caroline - Top France - Narrative, warm, sweet' },
            { service: 'ElevenLabs', id: 'OlBRrVAItyi00MuGMbna', name: 'Emma - Natural conversations in Dutch', language_code: 'nl', gender: 'female', voice_id: 'OlBRrVAItyi00MuGMbna', display_name: 'Emma - Natural conversations in Dutch' }
        ];
    }

    async refreshVoices() {
        this.voiceCache = {}; // Clear cache
        await this.updateVoiceDropdowns();
        this.setStatus('Voices refreshed');
    }

    async onVoiceSelect(service, voiceId) {
        if (!voiceId) return;

        // Track the most recently selected voice
        this.lastSelectedVoice.service = service;
        this.lastSelectedVoice.voiceId = voiceId;

        const text = document.getElementById('ssmlEditor').value.trim();
        if (!text) {
            this.setStatus('Please enter text in the SSML editor');
            return;
        }

        await this.generateAndPlayAudio(service, voiceId, text);
    }

    async generateAndPlayAudio(service, voiceId, text) {
        this.showLoading(true);
        this.setStatus(`Generating audio with ${service}...`);

        try {
            let audioData;
            
            if (service === 'PlayHT') {
                audioData = await this.generatePlayHTAudio(voiceId, text);
            } else if (service === 'ElevenLabs') {
                audioData = await this.generateElevenLabsAudio(voiceId, text);
            }

            if (audioData) {
                await this.playAudioData(audioData);
                this.setStatus(`Audio generated and played successfully`);
            } else {
                this.setStatus('Failed to generate audio');
            }

        } catch (error) {
            console.error('Error generating audio:', error);
            this.setStatus(`Error: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    async generatePlayHTAudio(voiceId, text) {
        // Debug: Check credentials
        console.log('DEBUG: PlayHT credentials check:', {
            apiKey: this.apiConfig.playht.apiKey ? 'Present' : 'Missing',
            userId: this.apiConfig.playht.userId ? 'Present' : 'Missing',
            apiKeyLength: this.apiConfig.playht.apiKey?.length || 0,
            userIdLength: this.apiConfig.playht.userId?.length || 0
        });

        if (!this.apiConfig.playht.apiKey || !this.apiConfig.playht.userId) {
            throw new Error('PlayHT API credentials not configured. Please enter your API key and User ID in the settings.');
        }

        // Debug: Log the credentials being used (first few and last few characters for security)
        const maskedApiKey = this.apiConfig.playht.apiKey.length > 8 ? 
            this.apiConfig.playht.apiKey.substring(0, 4) + '...' + this.apiConfig.playht.apiKey.substring(this.apiConfig.playht.apiKey.length - 4) :
            this.apiConfig.playht.apiKey;
        const maskedUserId = this.apiConfig.playht.userId.length > 8 ? 
            this.apiConfig.playht.userId.substring(0, 4) + '...' + this.apiConfig.playht.userId.substring(this.apiConfig.playht.userId.length - 4) :
            this.apiConfig.playht.userId;
        
        console.log('PlayHT API Credentials being used:', {
            apiKey: maskedApiKey,
            userId: maskedUserId,
            voiceId: voiceId
        });

        // Preprocess Spanish text to reduce clipping and repetition issues
        let processedText = text;
        // Note: Tests show Spanish text works fine as-is, so minimal preprocessing
        if (this.currentLanguage === 'Spanish' || 
            this.languages[this.currentLanguage]?.lang_code === 'es-CO' ||
            this.languages[this.currentLanguage]?.lang_code === 'es') {
            // Only normalize excessive whitespace - don't modify punctuation
            processedText = text.replace(/\s+/g, ' ').trim();
        }

        // Convert HTML to SSML for PlayHT
        processedText = this.htmlToSSML(processedText);
        
        // PlayHT v2 API format - Use Play3.0-mini for better stability with Spanish
        const requestData = {
            text: processedText,
            voice: voiceId,
            voice_engine: 'Play3.0-mini',  // More stable than PlayDialog for Spanish
            output_format: 'mp3',
            sample_rate: 22050  // Lower sample rate reduces clipping issues
        };

        // Add text_type if SSML tags are present
        if (processedText.includes('<') && processedText.includes('>')) {
            requestData.text_type = 'ssml';
        }

        console.log('PlayHT API Request:', {
            url: '/api/playht-proxy',
            headers: {
                'Authorization': maskedApiKey,
                'X-USER-ID': maskedUserId,
                'Content-Type': 'application/json'
            },
            body: requestData
        });

        try {
            // Use Vercel serverless function to proxy PlayHT API calls
            const response = await fetch('/api/playht-proxy', {
                method: 'POST',
                headers: {
                    'Authorization': this.apiConfig.playht.apiKey,
                    'X-USER-ID': this.apiConfig.playht.userId,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                let errorText;
                try {
                    const errorData = await response.json();
                    errorText = errorData.details || errorData.error || response.statusText;
                } catch (e) {
                    errorText = await response.text();
                }
                
                console.error('PlayHT API error details:', {
                    status: response.status,
                    statusText: response.statusText,
                    errorText,
                    requestData,
                    credentials: {
                        apiKey: maskedApiKey,
                        userId: maskedUserId
                    }
                });

                // If Play3.0-mini fails with 500 error, try fallback to PlayDialog
                if (response.status === 500 && requestData.voice_engine === 'Play3.0-mini') {
                    console.log('Play3.0-mini failed, trying fallback to PlayDialog...');
                    
                    const fallbackData = { ...requestData, voice_engine: 'PlayDialog' };
                    
                    try {
                        const fallbackResponse = await fetch('/api/playht-proxy', {
                            method: 'POST',
                            headers: {
                                'Authorization': this.apiConfig.playht.apiKey,
                                'X-USER-ID': this.apiConfig.playht.userId,
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(fallbackData)
                        });

                        if (fallbackResponse.ok) {
                            console.log('✅ Fallback to PlayDialog succeeded');
                            return await fallbackResponse.arrayBuffer();
                        }
                    } catch (fallbackError) {
                        console.warn('Fallback to PlayDialog also failed:', fallbackError);
                    }
                }
                
                throw new Error(`PlayHT API error: ${response.status} - ${errorText || response.statusText}`);
            }

            // Validate audio size (very small files might be corrupted)
            const audioBuffer = await response.arrayBuffer();
            if (audioBuffer.byteLength < 1000) {
                console.warn(`Generated audio too small: ${audioBuffer.byteLength} bytes, retrying...`);
                
                // Try with PlayDialog engine if the audio is too small
                if (requestData.voice_engine !== 'PlayDialog') {
                    const retryData = { ...requestData, voice_engine: 'PlayDialog' };
                    
                    const retryResponse = await fetch('/api/playht-proxy', {
                        method: 'POST',
                        headers: {
                            'Authorization': this.apiConfig.playht.apiKey,
                            'X-USER-ID': this.apiConfig.playht.userId,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(retryData)
                    });

                    if (retryResponse.ok) {
                        const retryBuffer = await retryResponse.arrayBuffer();
                        if (retryBuffer.byteLength >= 1000) {
                            console.log('✅ Retry with PlayDialog generated better audio');
                            return retryBuffer;
                        }
                    }
                }
                
                throw new Error(`Generated audio file too small: ${audioBuffer.byteLength} bytes`);
            }

            console.log(`✅ Generated audio: ${audioBuffer.byteLength} bytes`);
            return audioBuffer;
            
        } catch (error) {
            console.error('PlayHT error:', error);
            if (error.message.includes('Failed to fetch')) {
                throw new Error('Network error connecting to PlayHT API proxy. The serverless function may be down.');
            }
            throw error;
        }
    }

    async generateElevenLabsAudio(voiceId, text) {
        // Debug: Check credentials
        console.log('DEBUG: ElevenLabs credentials check:', {
            apiKey: this.apiConfig.elevenlabs.apiKey ? 'Present' : 'Missing',
            apiKeyLength: this.apiConfig.elevenlabs.apiKey?.length || 0,
            apiKeyStart: this.apiConfig.elevenlabs.apiKey?.substring(0, 15) + '...' || 'None',
            fullApiKey: this.apiConfig.elevenlabs.apiKey // TEMPORARY: Show full key for debugging
        });

        if (!this.apiConfig.elevenlabs.apiKey) {
            throw new Error('ElevenLabs API key not configured. Please enter your API key in the settings.');
        }

        // Debug logging
        console.log('ElevenLabs request:', {
            voiceId,
            text: text.substring(0, 100) + '...',
            apiUrl: `${this.apiConfig.elevenlabs.apiUrl}/${voiceId}`
        });

        const requestData = {
            text: text,
            model_id: 'eleven_multilingual_v2',
            voice_settings: {
                stability: 0.65,
                similarity_boost: 0.5,
                style: 0.0,
                use_speaker_boost: true
            }
        };

        try {
            const response = await fetch(`${this.apiConfig.elevenlabs.apiUrl}/${voiceId}`, {
                method: 'POST',
                headers: {
                    'xi-api-key': this.apiConfig.elevenlabs.apiKey,
                    'Content-Type': 'application/json',
                    'Accept': 'audio/mpeg'
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('ElevenLabs API error details:', {
                    status: response.status,
                    statusText: response.statusText,
                    errorText
                });
                throw new Error(`ElevenLabs API error: ${response.status} - ${errorText || response.statusText}`);
            }

            return await response.arrayBuffer();
        } catch (error) {
            console.error('ElevenLabs error:', error);
            if (error.message.includes('Failed to fetch')) {
                throw new Error('Network error connecting to ElevenLabs API. Please check your internet connection and API key.');
            }
            throw error;
        }
    }

    async playAudioData(audioData) {
        const audioBlob = new Blob([audioData], { type: 'audio/mpeg' });
        const audioUrl = URL.createObjectURL(audioBlob);
        
        const audio = new Audio(audioUrl);
        
        return new Promise((resolve, reject) => {
            audio.addEventListener('ended', () => {
                URL.revokeObjectURL(audioUrl);
                resolve();
            });
            
            audio.addEventListener('error', (e) => {
                URL.revokeObjectURL(audioUrl);
                reject(new Error('Audio playback failed'));
            });
            
            audio.play().catch(reject);
        });
    }

    async playSSML() {
        const text = document.getElementById('ssmlEditor').value.trim();
        if (!text) {
            this.setStatus('Please enter text in the SSML editor');
            return;
        }

        // Check if we have a recently selected voice
        if (this.lastSelectedVoice.service && this.lastSelectedVoice.voiceId) {
            // Use the most recently selected voice
            await this.generateAndPlayAudio(this.lastSelectedVoice.service, this.lastSelectedVoice.voiceId, text);
            return;
        }

        // Fallback to default voice for the current language if no voice has been selected
        const languageConfig = this.languages[this.currentLanguage];
        const service = languageConfig.service;
        const voiceName = languageConfig.voice;

        // Get the voice ID for the default voice
        let voiceId = null;
        if (service === 'PlayHT') {
            const voices = await this.getPlayHTVoices(languageConfig.lang_code);
            const voice = voices.find(v => v.name === voiceName);
            voiceId = voice?.id;
        } else if (service === 'ElevenLabs') {
            const voices = await this.getElevenLabsVoices(languageConfig.lang_code);
            const voice = voices.find(v => v.name === voiceName);
            voiceId = voice?.voice_id;
        }

        if (!voiceId) {
            this.setStatus('Please select a voice from the dropdowns before playing SSML');
            return;
        }

        await this.generateAndPlayAudio(service, voiceId, text);
    }

    async playExistingAudio(itemId, langCode) {
        try {
            // Get the task from the selected item
            const task = this.selectedRow?.labels || 'general';
            
            // Construct GitHub raw URL for audio file
            const audioUrl = `https://raw.githubusercontent.com/levante-framework/levante_translations/main/audio_files/${task}/${langCode}/shared/${itemId}.mp3`;
            
            this.setStatus(`Loading existing audio for ${itemId} (${langCode})...`);
            
            // Try to load and play the audio
            const audio = new Audio(audioUrl);
            
            audio.addEventListener('loadstart', () => {
                this.setStatus(`Loading audio: ${itemId}`, 'info');
            });
            
            audio.addEventListener('canplaythrough', () => {
                this.setStatus(`Playing existing audio: ${itemId}`, 'success');
                audio.play();
            });
            
            audio.addEventListener('error', (e) => {
                console.warn('Audio file not found:', audioUrl);
                this.setStatus(`No existing audio found for ${itemId}. Try generating with PlayHT or ElevenLabs.`, 'warning');
            });
            
            audio.addEventListener('ended', () => {
                this.setStatus(`Finished playing ${itemId}`, 'success');
            });
            
        } catch (error) {
            console.error('Error playing existing audio:', error);
            this.setStatus(`Error playing existing audio: ${error.message}`, 'error');
        }
    }

    wrapText(text, width = 40) {
        if (!text) return '';
        
        const words = text.split(' ');
        const lines = [];
        let currentLine = '';
        
        words.forEach(word => {
            if ((currentLine + word).length <= width) {
                currentLine += (currentLine ? ' ' : '') + word;
            } else {
                if (currentLine) lines.push(currentLine);
                currentLine = word;
            }
        });
        
        if (currentLine) lines.push(currentLine);
        return lines.join('<br>');
    }

    htmlToSSML(html) {
        // Convert HTML tags to SSML tags
        let ssml = html
            .replace(/<\s*bold\s*>/g, '<emphasis>')
            .replace(/<\s*\/\s*bold\s*>/g, '</emphasis>')
            .replace(/<\s*br\s*\/?>/g, '<break time="400ms"/>')
            .replace(/<\s*p\s*\/?>/g, '<break time="400ms"/>');

        // Wrap in speak tags - COMMENTED OUT
        // return `<speak>${ssml}</speak>`;
        return ssml;
    }

    showLoading(show) {
        const loading = document.getElementById('loadingIndicator');
        loading.classList.toggle('show', show);
    }

    setStatus(message, type = 'info') {
        const statusBar = document.getElementById('statusBar');
        statusBar.textContent = message;
        statusBar.className = `status-bar ${type}`;
    }

    showHelpModal() {
        document.getElementById('helpModal').style.display = 'block';
    }

    showIntroModal() {
        document.getElementById('introModal').style.display = 'block';
    }

    showCredentialsModal() {
        // Load current credentials into the modal
        this.loadCredentials();
        document.getElementById('credentialsModal').style.display = 'block';
    }

    clearCredentials() {
        document.getElementById('playhtApiKey').value = '';
        document.getElementById('playhtUserId').value = '';
        document.getElementById('elevenlabsApiKey').value = '';
        this.setStatus('Credentials cleared', 'warning');
    }
}

// Global functions for modal handling
function closeModal() {
    document.getElementById('helpModal').style.display = 'none';
}

function closeIntroModal() {
    document.getElementById('introModal').style.display = 'none';
}

function closeCredentialsModal() {
    document.getElementById('credentialsModal').style.display = 'none';
}

function closeVoicePreviewModal() {
    document.getElementById('voicePreviewModal').style.display = 'none';
}

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new AudioDashboard();
});

// Export for use in HTML onclick handlers
window.dashboard = dashboard; 