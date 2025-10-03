/**
 * API endpoint to fetch Crowdin translation statistics
 * Returns approved translations count and total strings for each language
 */

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    if (req.method !== 'GET') {
        res.status(405).json({ error: 'Method not allowed' });
        return;
    }

    try {
        const { projectId = process.env.LEVANTE_TRANSLATIONS_PROJECT_ID || '756721' } = req.query;
        
        // Crowdin API configuration
        const CROWDIN_API_BASE = 'https://api.crowdin.com/api/v2';
        const CROWDIN_PROJECT_ID = projectId;
        const CROWDIN_TOKEN = process.env.CROWDIN_API_TOKEN;
        
        if (!CROWDIN_TOKEN) {
            res.status(500).json({ 
                error: 'Crowdin API token not configured',
                details: 'CROWDIN_API_TOKEN environment variable is required'
            });
            return;
        }

        // Try to get project information directly
        const projectResponse = await fetch(`${CROWDIN_API_BASE}/projects/${CROWDIN_PROJECT_ID}`, {
            headers: {
                'Authorization': `Bearer ${CROWDIN_TOKEN}`,
                'Content-Type': 'application/json'
            }
        });

        if (!projectResponse.ok) {
            const errorText = await projectResponse.text();
            throw new Error(`Crowdin API error: ${projectResponse.status} ${projectResponse.statusText} - ${errorText}`);
        }

        const projectData = await projectResponse.json();
        
        // Fetch translation progress for all target languages
        const progressResponse = await fetch(`${CROWDIN_API_BASE}/projects/${CROWDIN_PROJECT_ID}/languages/progress`, {
            headers: {
                'Authorization': `Bearer ${CROWDIN_TOKEN}`,
                'Content-Type': 'application/json'
            }
        });

        if (!progressResponse.ok) {
            const errorText = await progressResponse.text();
            throw new Error(`Crowdin progress API error: ${progressResponse.status} ${progressResponse.statusText} - ${errorText}`);
        }

        const progressData = await progressResponse.json();
        
        // Debug: log the progress data to understand the structure
        console.log('Progress data structure:', JSON.stringify(progressData.data, null, 2));
        
        // Process the data to extract statistics
        const stats = {};
        
        // Get source language info
        const sourceLanguage = projectData.data.sourceLanguageId;
        
        // Get total strings from the first language progress entry
        let totalStrings = 0;
        if (Array.isArray(progressData.data) && progressData.data.length > 0) {
            totalStrings = progressData.data[0].data.words?.total || 0;
        }
        
        // Debug: log the project data to understand the structure
        console.log('Project data structure:', JSON.stringify(projectData.data, null, 2));
        
        // Process each target language - progressData.data is an array
        if (Array.isArray(progressData.data)) {
            for (const languageProgress of progressData.data) {
                const languageId = languageProgress.data.languageId;
                const approved = languageProgress.data.words?.approved || 0;
                const translated = languageProgress.data.words?.translated || 0;
                
                // Map Crowdin language IDs to our language codes
                const langCode = mapCrowdinLanguageId(languageId);
                
                if (langCode) {
                    stats[langCode] = {
                        approved,
                        translated,
                        total: totalStrings,
                        percentage: totalStrings > 0 ? Math.round((approved / totalStrings) * 100) : 0
                    };
                }
            }
        }
        
        // Add source language (should be 100% approved)
        const sourceLangCode = mapCrowdinLanguageId(sourceLanguage);
        if (sourceLangCode) {
            stats[sourceLangCode] = {
                approved: totalStrings,
                translated: totalStrings,
                total: totalStrings,
                percentage: 100
            };
        }
        
        res.status(200).json({
            project: projectData.data.name,
            sourceLanguage: sourceLanguage,
            totalStrings,
            languages: stats,
            timestamp: new Date().toISOString(),
            debug: {
                projectId: CROWDIN_PROJECT_ID,
                projectDataKeys: Object.keys(projectData.data || {}),
                progressDataKeys: Object.keys(progressData.data || {}),
                totalStrings,
                progressDataSample: Array.isArray(progressData.data) ? progressData.data[0] : progressData.data
            }
        });

    } catch (error) {
        console.error('Crowdin API error:', error);
        res.status(500).json({ 
            error: 'Failed to fetch Crowdin statistics',
            details: error.message
        });
    }
}

/**
 * Map Crowdin language IDs to our language codes
 */
function mapCrowdinLanguageId(crowdinLangId) {
    const mapping = {
        'en': 'en',
        'es-CO': 'es-CO', 
        'es': 'es-CO',
        'de': 'de',
        'fr-CA': 'fr-CA',
        'fr': 'fr-CA',
        'nl': 'nl',
        'de-CH': 'de-CH',
        'es-AR': 'es-AR',
        'en-GH': 'en-GH'
    };
    
    return mapping[crowdinLangId] || null;
}
