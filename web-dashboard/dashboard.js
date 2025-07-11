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
        // In a real implementation, you'd get this from environment variables or secure storage
        // For demo purposes, we'll prompt the user or use a config file
        const stored = localStorage.getItem(keyName);
        if (stored) return stored;
        
        // Prompt user for API key if not found
        const key = prompt(`Please enter your ${keyName}:`);
        if (key) {
            localStorage.setItem(keyName, key);
            return key;
        }
        return null;
    }

    async init() {
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
        const cacheKey = `playht_${langCode}`;
        if (this.voiceCache[cacheKey]) {
            return this.voiceCache[cacheKey];
        }

        if (!this.apiConfig.playht.apiKey || !this.apiConfig.playht.userId) {
            console.warn('PlayHT API credentials not configured');
            return [];
        }

        try {
            const response = await fetch(this.apiConfig.playht.voicesUrl, {
                headers: {
                    'AUTHORIZATION': this.apiConfig.playht.apiKey,
                    'X-USER-ID': this.apiConfig.playht.userId,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`PlayHT API error: ${response.status}`);
            }

            const data = await response.json();
            
            // Filter voices by language and gender (female only)
            const filteredVoices = data.filter(voice => {
                const matchesLang = voice.languageCode === langCode || 
                                  voice.language?.toLowerCase().includes(langCode.split('-')[0]);
                const isFemale = voice.gender?.toLowerCase() === 'female';
                return matchesLang && isFemale;
            });

            // Cache the results
            this.voiceCache[cacheKey] = filteredVoices;
            return filteredVoices;

        } catch (error) {
            console.error('Error fetching PlayHT voices:', error);
            return [];
        }
    }

    async getElevenLabsVoices(langCode) {
        const cacheKey = `elevenlabs_${langCode}`;
        if (this.voiceCache[cacheKey]) {
            return this.voiceCache[cacheKey];
        }

        if (!this.apiConfig.elevenlabs.apiKey) {
            console.warn('ElevenLabs API key not configured');
            return [];
        }

        try {
            const response = await fetch(this.apiConfig.elevenlabs.voicesUrl, {
                headers: {
                    'xi-api-key': this.apiConfig.elevenlabs.apiKey
                }
            });

            if (!response.ok) {
                throw new Error(`ElevenLabs API error: ${response.status}`);
            }

            const data = await response.json();
            
            // Filter voices by language and gender (female only)
            const filteredVoices = data.voices.filter(voice => {
                const labels = voice.labels || {};
                const matchesLang = labels.language === langCode || 
                                  labels.language === langCode.split('-')[0];
                const isFemale = labels.gender?.toLowerCase() === 'female';
                const isProfessional = voice.category === 'professional';
                return matchesLang && isFemale && isProfessional;
            });

            // Cache the results
            this.voiceCache[cacheKey] = filteredVoices;
            return filteredVoices;

        } catch (error) {
            console.error('Error fetching ElevenLabs voices:', error);
            return [];
        }
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
    }

    async generateElevenLabsAudio(voiceId, text) {
        if (!this.apiConfig.elevenlabs.apiKey) {
            throw new Error('ElevenLabs API key not configured');
        }

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
            throw new Error(`ElevenLabs API error: ${response.status} - ${response.statusText}`);
        }

        return await response.arrayBuffer();
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
        // In a real implementation, this would load existing audio files
        // For demo purposes, we'll just show a message
        this.setStatus(`Playing existing audio for ${itemId} (${langCode})`);
        
        // You could implement actual audio file loading here
        // const audioUrl = `audio_files/general/${langCode}/shared/${itemId}.mp3`;
        // const audio = new Audio(audioUrl);
        // audio.play();
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

    setStatus(message) {
        document.getElementById('statusBar').textContent = message;
    }

    showHelpModal() {
        document.getElementById('helpModal').style.display = 'block';
    }

    showIntroModal() {
        document.getElementById('introModal').style.display = 'block';
    }
}

// Global functions for modal handling
function closeModal() {
    document.getElementById('helpModal').style.display = 'none';
}

function closeIntroModal() {
    document.getElementById('introModal').style.display = 'none';
}

// Initialize the dashboard when the page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new AudioDashboard();
});

// Export for use in HTML onclick handlers
window.dashboard = dashboard; 