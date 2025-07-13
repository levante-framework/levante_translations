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

        // Save to localStorage
        localStorage.setItem('PLAY_DOT_HT_API_KEY', credentials.playhtApiKey);
        localStorage.setItem('PLAY_DOT_HT_USER_ID', credentials.playhtUserId);
        localStorage.setItem('ELEVENLABS_API_KEY', credentials.elevenlabsApiKey);

        // Update the API config
        this.apiConfig.playht.apiKey = credentials.playhtApiKey;
        this.apiConfig.playht.userId = credentials.playhtUserId;
        this.apiConfig.elevenlabs.apiKey = credentials.elevenlabsApiKey;

        this.setStatus('Credentials saved successfully!', 'success');
        
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
        // Load credentials silently on startup
        const playhtApiKey = localStorage.getItem('PLAY_DOT_HT_API_KEY') || '';
        const playhtUserId = localStorage.getItem('PLAY_DOT_HT_USER_ID') || '';
        const elevenlabsApiKey = localStorage.getItem('ELEVENLABS_API_KEY') || '';

        // Update the API config silently
        this.apiConfig.playht.apiKey = playhtApiKey;
        this.apiConfig.playht.userId = playhtUserId;
        this.apiConfig.elevenlabs.apiKey = elevenlabsApiKey;
        
        await this.loadData();
        this.setupEventListeners();
        this.createTabs();
        this.displayStats();
        this.updateVoiceDropdowns();
        this.showIntroModal();
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
                            row.es = values[index];
                        } else if (header === 'fr-CA') {
                            row.fr = values[index];
                        } else if (header === 'nl-NL') {
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
        // Credential management modal
        document.getElementById('manageCredentials').addEventListener('click', () => {
            this.showCredentialsModal();
        });

        document.getElementById('saveCredentials').addEventListener('click', () => {
            this.saveCredentials();
        });

        document.getElementById('clearCredentials').addEventListener('click', () => {
            this.clearCredentials();
        });

        // Search functionality
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.searchItems(e.target.value);
        });

        // Voice selection
        document.getElementById('playhtVoice').addEventListener('change', (e) => {
            this.onVoiceSelect('PlayHT', e.target.value);
        });

        document.getElementById('elevenlabsVoice').addEventListener('change', (e) => {
            this.onVoiceSelect('ElevenLabs', e.target.value);
        });

        // Refresh voices
        document.getElementById('refreshVoices').addEventListener('click', () => {
            this.refreshVoices();
        });

        // SSML functionality
        document.getElementById('ssmlHelp').addEventListener('click', () => {
            this.showHelpModal();
        });

        document.getElementById('playSSML').addEventListener('click', () => {
            this.playSSML();
        });

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
        
        tables.forEach(tbody => {
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query.toLowerCase())) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
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
                option.value = voice.id;
                option.textContent = voice.name;
                playhtSelect.appendChild(option);
            });

            // Populate ElevenLabs dropdown
            elevenlabsSelect.innerHTML = '<option value="">Select ElevenLabs Voice...</option>';
            elevenlabsVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.voice_id;
                option.textContent = voice.name;
                elevenlabsSelect.appendChild(option);
            });

        } catch (error) {
            console.error('Error updating voice dropdowns:', error);
            this.setStatus('Error loading voices');
        }
    }

    async getPlayHTVoices(langCode) {
        // Use embedded voice lists instead of API calls to avoid CORS issues
        const playhtVoices = {
            'en': [
                { id: 'adb83b67-8d75-48ff-ad4d-a0840d231ef1', name: 'Inara', language: 'en', gender: 'female' },
                { id: '831bd330-85c6-4333-b2b4-10c476ea3491', name: 'Nia', language: 'en', gender: 'female' },
                { id: '801a663f-efd0-4254-98d0-5c175514c3e8', name: 'Jennifer', language: 'en', gender: 'female' },
                { id: '7c38b588-14e8-42b9-bacd-e03d1d673c3c', name: 'Nicole', language: 'en', gender: 'female' },
                { id: '1f44b3e7-22ea-4c2e-87d0-b4d9c8f1d47d', name: 'Sophia', language: 'en', gender: 'female' }
            ],
            'es-CO': [
                { id: 'e0bf73c2-2b50-455a-8524-cc29de4360d1', name: 'Patricia Conversational', language: 'es-CO', gender: 'female' },
                { id: '5694d5e5-2dfe-4440-8cc8-e2a69c3e7560', name: 'Patricia Narrative', language: 'es-CO', gender: 'female' },
                { id: '4289181f-48fc-4c52-911f-6e769086eb98', name: 'Violeta Conversational', language: 'es-CO', gender: 'female' },
                { id: '326c3793-b5b1-4ce3-a8ec-22c95d8553f0', name: 'Violeta Narrative', language: 'es-CO', gender: 'female' }
            ],
            'es': [
                { id: 'e0bf73c2-2b50-455a-8524-cc29de4360d1', name: 'Patricia Conversational', language: 'es', gender: 'female' },
                { id: '326c3793-b5b1-4ce3-a8ec-22c95d8553f0', name: 'Violeta Narrative', language: 'es', gender: 'female' }
            ],
            'de': [
                { id: 'c1cb7f62-4a59-4593-b6c6-6b430892541d', name: 'Anke Conversational', language: 'de', gender: 'female' },
                { id: '3d1a2ebc-6fe3-4b9b-b8f3-d23a3e5b6c7d', name: 'Anke Narrative', language: 'de', gender: 'female' },
                { id: '4b5c6d7e-8f9a-1b2c-3d4e-5f6a7b8c9d0e', name: 'German_Anke Narrative', language: 'de', gender: 'female' }
            ],
            'fr-CA': [
                { id: 'f1e2d3c4-b5a6-9c8d-7e6f-5a4b3c2d1e0f', name: 'Ange Conversational', language: 'fr-CA', gender: 'female' },
                { id: 'a9b8c7d6-e5f4-3c2b-1a0f-9e8d7c6b5a4f', name: 'Ange Narrative', language: 'fr-CA', gender: 'female' },
                { id: 'c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f', name: 'French_Ange Narrative', language: 'fr-CA', gender: 'female' }
            ],
            'fr': [
                { id: 'f1e2d3c4-b5a6-9c8d-7e6f-5a4b3c2d1e0f', name: 'Ange Conversational', language: 'fr', gender: 'female' },
                { id: 'a9b8c7d6-e5f4-3c2b-1a0f-9e8d7c6b5a4f', name: 'Ange Narrative', language: 'fr', gender: 'female' }
            ],
            'nl': [
                { id: 'e8f7a6b5-c4d3-2e1f-0a9b-8c7d6e5f4a3b', name: 'Dutch Female 1', language: 'nl', gender: 'female' },
                { id: 'b3c4d5e6-f7a8-9b0c-1d2e-3f4a5b6c7d8e', name: 'Dutch Female 2', language: 'nl', gender: 'female' }
            ]
        };

        // Return voices for the requested language, fallback to simplified language code
        const voices = playhtVoices[langCode] || playhtVoices[langCode.split('-')[0]] || [];
        
        // Cache the results
        const cacheKey = `playht_${langCode}`;
        this.voiceCache[cacheKey] = voices;
        
        return voices;
    }

    async getElevenLabsVoices(langCode) {
        // Use embedded voice lists instead of API calls to avoid CORS issues
        const elevenlabsVoices = {
            'en': [
                { voice_id: 'kdmDKE6EkgrWrrykO9Qt', name: 'Alexandra - Conversational and Real', language: 'en', gender: 'female' },
                { voice_id: 'y2TOWGCXSYEgBanvKsYJ', name: 'Aunt Annie', language: 'en', gender: 'female' },
                { voice_id: 'XrExE9yKIg1WjnnlVkGZ', name: 'Matilda', language: 'en', gender: 'female' },
                { voice_id: 'EXAVITQu4vr4xnSDxMaL', name: 'Bella', language: 'en', gender: 'female' },
                { voice_id: 'MF3mGyEYCl7XYWbV9V6O', name: 'Elli', language: 'en', gender: 'female' }
            ],
            'es-CO': [
                { voice_id: 'm7yTemJqdIqrcNleANfX', name: 'Ana María - Calm & natural neutral Spanish', language: 'es-CO', gender: 'female' },
                { voice_id: 'VBmCZpOLbAT9F8rUdK7k', name: 'Spanish Female Voice', language: 'es-CO', gender: 'female' }
            ],
            'es': [
                { voice_id: 'm7yTemJqdIqrcNleANfX', name: 'Ana María - Calm & natural neutral Spanish', language: 'es', gender: 'female' }
            ],
            'de': [
                { voice_id: 'v3V1d2rk6528UrLKRuy8', name: 'Susi', language: 'de', gender: 'female' },
                { voice_id: 'AnvlJBAqSLDzEevYr9Ap', name: 'Ava', language: 'de', gender: 'female' },
                { voice_id: 'D4BIjjCRFRZhH8fGOzGP', name: 'German Female Voice', language: 'de', gender: 'female' }
            ],
            'fr-CA': [
                { voice_id: 'kwhMCf63M8O3rCfnQ3oQ', name: 'Caroline - Top France - Narrative, warm, sweet', language: 'fr-CA', gender: 'female' },
                { voice_id: 'xNtG3W2oqJs0cJZuTyBc', name: 'Chloé', language: 'fr-CA', gender: 'female' }
            ],
            'fr': [
                { voice_id: 'kwhMCf63M8O3rCfnQ3oQ', name: 'Caroline - Top France - Narrative, warm, sweet', language: 'fr', gender: 'female' },
                { voice_id: 'xNtG3W2oqJs0cJZuTyBc', name: 'Chloé', language: 'fr', gender: 'female' }
            ],
            'nl': [
                { voice_id: 'OlBRrVAItyi00MuGMbna', name: 'Emma - Natural conversations in Dutch', language: 'nl', gender: 'female' },
                { voice_id: 'BmGJM2HQCL8H5KfGOzGP', name: 'Dutch Female Voice', language: 'nl', gender: 'female' }
            ]
        };

        // Return voices for the requested language, fallback to simplified language code
        const voices = elevenlabsVoices[langCode] || elevenlabsVoices[langCode.split('-')[0]] || [];
        
        // Cache the results
        const cacheKey = `elevenlabs_${langCode}`;
        this.voiceCache[cacheKey] = voices;
        
        return voices;
    }

    async refreshVoices() {
        this.voiceCache = {}; // Clear cache
        await this.updateVoiceDropdowns();
        this.setStatus('Voices refreshed');
    }

    async onVoiceSelect(service, voiceId) {
        if (!voiceId) return;

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
        if (!this.apiConfig.playht.apiKey || !this.apiConfig.playht.userId) {
            throw new Error('PlayHT API credentials not configured');
        }

        // Convert HTML to SSML and remove wrapper tags for PlayHT
        let ssmlText = this.htmlToSSML(text);
        if (ssmlText.startsWith('<speak>') && ssmlText.endsWith('</speak>')) {
            ssmlText = ssmlText.slice(7, -8);
        }

        const requestData = {
            text: ssmlText,
            voice: voiceId,
            voice_engine: 'PlayDialog',
            output_format: 'mp3',
            sample_rate: 24000
        };

        // Add text_type if SSML tags are present
        if (ssmlText.includes('<') && ssmlText.includes('>')) {
            requestData.text_type = 'ssml';
        }

        try {
            const response = await fetch(this.apiConfig.playht.apiUrl, {
                method: 'POST',
                headers: {
                    'AUTHORIZATION': this.apiConfig.playht.apiKey,
                    'X-USER-ID': this.apiConfig.playht.userId,
                    'Content-Type': 'application/json',
                    'Accept': 'audio/mpeg'
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                throw new Error(`PlayHT API error: ${response.status} - ${response.statusText}`);
            }

            return await response.arrayBuffer();
        } catch (error) {
            // Handle CORS errors specifically
            if (error.message.includes('CORS') || error.message.includes('Failed to fetch')) {
                throw new Error('PlayHT API blocked by CORS policy. Please use the Python utilities for PlayHT audio generation, or try ElevenLabs voices which work from browsers.');
            }
            throw error;
        }
    }

    async generateElevenLabsAudio(voiceId, text) {
        if (!this.apiConfig.elevenlabs.apiKey) {
            throw new Error('ElevenLabs API key not configured');
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

        // Use the default voice for the current language
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
            this.setStatus('Default voice not found, please select a voice manually');
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

        // Wrap in speak tags
        return `<speak>${ssml}</speak>`;
    }

    displayStats() {
        const statsContainer = document.getElementById('statsContainer');
        
        // Sample statistics - in a real implementation, this would load from stats.csv
        const stats = {
            'English': { errors: 0, noTask: 0, voice: 'Alexandra' },
            'Spanish': { errors: 2, noTask: 1, voice: 'Violeta' },
            'German': { errors: 1, noTask: 0, voice: 'Anke' },
            'French': { errors: 0, noTask: 1, voice: 'Ange' },
            'Dutch': { errors: 1, noTask: 2, voice: 'Xander' }
        };

        Object.entries(stats).forEach(([language, data]) => {
            const card = document.createElement('div');
            card.className = 'stat-card';
            card.innerHTML = `
                <h3>${language}</h3>
                <div class="stat-value">${data.errors}</div>
                <p>Errors</p>
                <small>Voice: ${data.voice}</small>
            `;
            statsContainer.appendChild(card);
        });
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

// Initialize the dashboard when the page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new AudioDashboard();
});

// Export for use in HTML onclick handlers
window.dashboard = dashboard; 