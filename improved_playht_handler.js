/**
 * Improved PlayHT Audio Generation Handler
 * Addresses Spanish voice issues with clipping and repetitions
 */

class ImprovedPlayHTHandler {
    constructor(apiConfig) {
        this.apiConfig = apiConfig;
        this.maxRetries = 3;
        this.retryDelay = 1000; // 1 second
        
        // Voice engine fallback order
        this.engineFallbacks = [
            'PlayDialog',
            'Play3.0-mini',
            'PlayHT2.0-turbo'
        ];
        
        // Language-specific optimizations
        this.languageOptimizations = {
            'es-CO': {
                preferredEngine: 'Play3.0-mini',  // More stable for Spanish
                sampleRate: 22050,  // Lower rate can reduce clipping
                textPreprocessing: true
            },
            'es': {
                preferredEngine: 'Play3.0-mini',
                sampleRate: 22050,
                textPreprocessing: true
            },
            'en': {
                preferredEngine: 'PlayDialog',
                sampleRate: 24000,
                textPreprocessing: false
            }
        };
    }

    /**
     * Preprocess text to reduce audio issues
     */
    preprocessSpanishText(text) {
        // Common issues with Spanish text in TTS
        let processed = text;
        
        // Replace multiple exclamation marks
        processed = processed.replace(/¡+/g, '¡');
        processed = processed.replace(/!+/g, '!');
        
        // Add slight pauses after exclamations to prevent clipping
        processed = processed.replace(/¡([^!]+)!/g, '¡$1!<break time="0.2s"/>');
        
        // Handle repeated punctuation
        processed = processed.replace(/\.{2,}/g, '.');
        processed = processed.replace(/,{2,}/g, ',');
        
        // Normalize spaces
        processed = processed.replace(/\s+/g, ' ').trim();
        
        console.log('Spanish text preprocessing:', {
            original: text,
            processed: processed
        });
        
        return processed;
    }

    /**
     * Get optimized settings for a language
     */
    getOptimizedSettings(langCode) {
        const optimization = this.languageOptimizations[langCode] || this.languageOptimizations['en'];
        return {
            engine: optimization.preferredEngine,
            sampleRate: optimization.sampleRate,
            needsPreprocessing: optimization.textPreprocessing
        };
    }

    /**
     * Generate audio with improved error handling and fallbacks
     */
    async generateAudio(voiceId, text, langCode = 'en') {
        console.log('Generating PlayHT audio with improved handler:', {
            voiceId: voiceId,
            text: text.substring(0, 50) + (text.length > 50 ? '...' : ''),
            langCode: langCode
        });

        // Check credentials
        if (!this.apiConfig.playht.apiKey || !this.apiConfig.playht.userId) {
            throw new Error('PlayHT API credentials not configured');
        }

        // Get optimized settings for this language
        const settings = this.getOptimizedSettings(langCode);
        
        // Preprocess text if needed
        let processedText = text;
        if (settings.needsPreprocessing) {
            processedText = this.preprocessSpanishText(text);
        }

        // Convert HTML to SSML
        processedText = this.htmlToSSML(processedText);

        // Try engines in fallback order
        for (let i = 0; i < this.engineFallbacks.length; i++) {
            const engine = (i === 0) ? settings.engine : this.engineFallbacks[i];
            
            console.log(`Attempting with engine: ${engine} (attempt ${i + 1}/${this.engineFallbacks.length})`);
            
            try {
                const result = await this.attemptGeneration(voiceId, processedText, engine, settings.sampleRate);
                
                if (result) {
                    console.log(`✅ Success with engine: ${engine}`);
                    return result;
                }
            } catch (error) {
                console.warn(`Engine ${engine} failed:`, error.message);
                
                // If this is the last engine, throw the error
                if (i === this.engineFallbacks.length - 1) {
                    throw error;
                }
                
                // Wait before trying next engine
                await this.delay(this.retryDelay);
            }
        }
        
        throw new Error('All PlayHT engines failed');
    }

    /**
     * Attempt generation with specific engine and settings
     */
    async attemptGeneration(voiceId, text, engine, sampleRate) {
        const requestData = {
            text: text,
            voice: voiceId,
            voice_engine: engine,
            output_format: 'mp3',
            sample_rate: sampleRate
        };

        // Add text_type if SSML tags are present
        if (text.includes('<') && text.includes('>')) {
            requestData.text_type = 'ssml';
        }

        console.log('PlayHT API Request:', {
            engine: engine,
            sampleRate: sampleRate,
            textLength: text.length,
            hasSSML: requestData.text_type === 'ssml'
        });

        // Attempt with retries
        for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
            try {
                const response = await fetch('/api/playht-proxy', {
                    method: 'POST',
                    headers: {
                        'Authorization': this.apiConfig.playht.apiKey,
                        'X-USER-ID': this.apiConfig.playht.userId,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData)
                });

                if (response.ok) {
                    const audioBuffer = await response.arrayBuffer();
                    
                    // Validate audio size (very small files might be corrupted)
                    if (audioBuffer.byteLength < 1000) {
                        throw new Error(`Generated audio too small: ${audioBuffer.byteLength} bytes`);
                    }
                    
                    console.log(`Generated audio: ${audioBuffer.byteLength} bytes`);
                    return audioBuffer;
                }
                
                // Handle specific error codes
                if (response.status === 500) {
                    const errorText = await response.text();
                    console.warn(`Server error (attempt ${attempt}):`, errorText);
                    
                    if (attempt < this.maxRetries) {
                        await this.delay(this.retryDelay * attempt);
                        continue;
                    }
                }
                
                // For other errors, get error details and throw
                let errorText;
                try {
                    const errorData = await response.json();
                    errorText = errorData.details || errorData.error || response.statusText;
                } catch (e) {
                    errorText = await response.text() || response.statusText;
                }
                
                throw new Error(`PlayHT API error: ${response.status} - ${errorText}`);
                
            } catch (fetchError) {
                console.warn(`Request attempt ${attempt} failed:`, fetchError.message);
                
                if (attempt < this.maxRetries && !fetchError.message.includes('API error:')) {
                    await this.delay(this.retryDelay * attempt);
                    continue;
                }
                
                throw fetchError;
            }
        }
        
        throw new Error(`Failed after ${this.maxRetries} attempts`);
    }

    /**
     * Convert HTML to SSML, removing wrapper for PlayHT
     */
    htmlToSSML(text) {
        // Basic HTML to SSML conversion
        let ssml = text;
        
        // Convert bold tags to emphasis
        ssml = ssml.replace(/<\s*bold\s*>/gi, '<emphasis>');
        ssml = ssml.replace(/<\s*\/\s*bold\s*>/gi, '</emphasis>');
        ssml = ssml.replace(/<\s*b\s*>/gi, '<emphasis>');
        ssml = ssml.replace(/<\s*\/\s*b\s*>/gi, '</emphasis>');
        
        // Convert line breaks to pauses
        ssml = ssml.replace(/<\s*br\s*\/?>/gi, '<break time="400ms"/>');
        ssml = ssml.replace(/<\s*p\s*\/?>/gi, '<break time="400ms"/>');
        
        // Remove any existing speak tags (PlayHT doesn't want them)
        ssml = ssml.replace(/<\s*speak[^>]*>/gi, '');
        ssml = ssml.replace(/<\s*\/\s*speak\s*>/gi, '');
        
        return ssml;
    }

    /**
     * Utility delay function
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

/**
 * Enhanced version of the dashboard's generatePlayHTAudio function
 */
async function generatePlayHTAudioImproved(voiceId, text, langCode = 'en') {
    // Create handler instance
    const handler = new ImprovedPlayHTHandler(this.apiConfig);
    
    try {
        // Update status
        this.setStatus('Generating PlayHT audio with improved handler...', 'loading');
        
        // Generate audio
        const audioBuffer = await handler.generateAudio(voiceId, text, langCode);
        
        // Create audio URL and play
        const audioBlob = new Blob([audioBuffer], { type: 'audio/mpeg' });
        const audioUrl = URL.createObjectURL(audioBlob);
        
        // Store for playback
        this.generatedAudio = audioUrl;
        this.playAudio();
        
        // Update status
        this.setStatus('PlayHT audio generated successfully with improved method', 'success');
        
        return audioBuffer;
        
    } catch (error) {
        console.error('Improved PlayHT generation failed:', error);
        
        // Try fallback to original method
        console.log('Falling back to original method...');
        this.setStatus('Improved method failed, trying fallback...', 'loading');
        
        try {
            return await this.generatePlayHTAudio(voiceId, text);
        } catch (fallbackError) {
            this.setStatus(`PlayHT generation failed: ${fallbackError.message}`, 'error');
            throw fallbackError;
        }
    }
}

// Export for use in dashboard
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ImprovedPlayHTHandler, generatePlayHTAudioImproved };
} 