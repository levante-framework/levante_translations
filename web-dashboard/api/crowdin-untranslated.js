/**
 * API endpoint to fetch untranslated items from Crowdin
 * Returns untranslated items with source file, item_id, and source text
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
        const { lang, env = 'dev' } = req.query;
        
        if (!lang) {
            res.status(400).json({ error: 'Language parameter is required' });
            return;
        }
        
        // Crowdin API configuration
        const CROWDIN_API_BASE = 'https://api.crowdin.com/api/v2';
        const CROWDIN_PROJECT_ID = process.env.LEVANTE_TRANSLATIONS_PROJECT_ID || '756721';
        const CROWDIN_TOKEN = process.env.CROWDIN_API_TOKEN;
        
        if (!CROWDIN_TOKEN) {
            res.status(500).json({ 
                error: 'Crowdin API token not configured',
                details: 'CROWDIN_API_TOKEN environment variable is required'
            });
            return;
        }

        // Get project information first
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
        
        // Get translation progress for the specific language
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
        
        // Find the language progress
        const languageProgress = progressData.data.find(p => p.data.languageId === lang);
        
        if (!languageProgress) {
            res.status(404).json({ 
                error: 'Language not found',
                details: `No progress data found for language: ${lang}`
            });
            return;
        }
        
        // Use CroQL to get strings that have translations for this language
        // We'll process the results to determine which are unapproved
        const croql = `count of translations where (language = @language:"${lang}") > 0`;
        
        const stringsResponse = await fetch(`${CROWDIN_API_BASE}/projects/${CROWDIN_PROJECT_ID}/strings?croql=${encodeURIComponent(croql)}`, {
            headers: {
                'Authorization': `Bearer ${CROWDIN_TOKEN}`,
                'Content-Type': 'application/json'
            }
        });

        if (!stringsResponse.ok) {
            const errorText = await stringsResponse.text();
            throw new Error(`Crowdin strings API error: ${stringsResponse.status} ${stringsResponse.statusText} - ${errorText}`);
        }

        const stringsData = await stringsResponse.json();
        
        // Get file information for mapping
        const filesResponse = await fetch(`${CROWDIN_API_BASE}/projects/${CROWDIN_PROJECT_ID}/files`, {
            headers: {
                'Authorization': `Bearer ${CROWDIN_TOKEN}`,
                'Content-Type': 'application/json'
            }
        });

        let filesMap = {};
        if (filesResponse.ok) {
            const filesData = await filesResponse.json();
            if (filesData.data && Array.isArray(filesData.data)) {
                for (const file of filesData.data) {
                    filesMap[file.data.id] = file.data.name || 'Unknown file';
                }
            }
        }
        
        // Get translation details for each string to check approval status
        const untranslated = [];
        let unapprovedCount = 0;
        
        if (stringsData.data && Array.isArray(stringsData.data)) {
            for (const stringItem of stringsData.data) {
                const stringId = stringItem.data.id;
                
                // Get translations for this specific string
                const translationResponse = await fetch(`${CROWDIN_API_BASE}/projects/${CROWDIN_PROJECT_ID}/strings/${stringId}/translations?languageId=${lang}`, {
                    headers: {
                        'Authorization': `Bearer ${CROWDIN_TOKEN}`,
                        'Content-Type': 'application/json'
                    }
                });
                
                if (translationResponse.ok) {
                    const translationData = await translationResponse.json();
                    
                    // Check if any translation is approved
                    let hasApprovedTranslation = false;
                    if (translationData.data && Array.isArray(translationData.data)) {
                        for (const translation of translationData.data) {
                            if (translation.data.approved === true) {
                                hasApprovedTranslation = true;
                                break;
                            }
                        }
                    }
                    
                    // If no approved translation found, add to unapproved list
                    if (!hasApprovedTranslation) {
                        unapprovedCount++;
                        
                        // Add to display list (limit to 20 for UI)
                        if (untranslated.length < 20) {
                            const fileId = stringItem.data.fileId;
                            const fileName = filesMap[fileId] || 'Unknown file';
                            const sourceText = stringItem.data.text || stringItem.data.sourceText || 'No text available';
                            
                            untranslated.push({
                                item_id: stringItem.data.identifier || stringItem.data.id,
                                source_file: fileName,
                                source_text: sourceText
                            });
                        }
                    }
                }
            }
        }
        
        // Add summary if there are more items than displayed
        if (unapprovedCount > 20) {
            untranslated.push({
                item_id: `... and ${unapprovedCount - 20} more unapproved items`,
                source_file: 'Multiple source files',
                source_text: `Total unapproved items: ${unapprovedCount}. Showing first 20 items above.`
            });
        }
        
        res.status(200).json({
            language: lang,
            environment: env,
            total_untranslated: unapprovedCount,
            untranslated: untranslated,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        console.error('Crowdin untranslated API error:', error);
        res.status(500).json({ 
            error: 'Failed to fetch untranslated items',
            details: error.message
        });
    }
}
