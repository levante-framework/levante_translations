/**
 * API endpoint to check if a user has editor permissions for a language in Crowdin
 * Checks if user is superadmin OR has editor access to the selected language
 */

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    if (req.method !== 'POST') {
        res.status(405).json({ error: 'Method not allowed' });
        return;
    }

    try {
        const { email, langCode, projectId = process.env.LEVANTE_TRANSLATIONS_PROJECT_ID || '756721' } = req.body;
        
        if (!email) {
            res.status(400).json({ error: 'Email is required' });
            return;
        }

        if (!langCode) {
            res.status(400).json({ error: 'Language code is required' });
            return;
        }

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

        // Map language codes to Crowdin language IDs
        const langCodeToCrowdinId = {
            'pt-PT': 'pt',
            'pt': 'pt',
            'es-CO': 'es-CO',
            'es-AR': 'es-AR',
            'de': 'de',
            'de-CH': 'de-CH',
            'fr-CA': 'fr-CA',
            'nl': 'nl',
            'en': 'en'
        };

        const crowdinLangId = langCodeToCrowdinId[langCode] || langCode;

        // First, try to check if user is the project owner
        // If this fails, we'll fall back to checking members list
        let isProjectOwner = false;
        try {
            const projectResponse = await fetch(
                `${CROWDIN_API_BASE}/projects/${CROWDIN_PROJECT_ID}`,
                {
                    headers: {
                        'Authorization': `Bearer ${CROWDIN_TOKEN}`,
                        'Content-Type': 'application/json'
                    }
                }
            );

            if (projectResponse.ok) {
                const projectData = await projectResponse.json();
                const projectOwner = projectData.data?.owner;
                const ownerEmail = projectOwner?.email || projectOwner?.user?.email || projectOwner?.username || '';
                
                // If user is the project owner, grant access to all languages
                if (ownerEmail && ownerEmail.toLowerCase() === email.toLowerCase()) {
                    isProjectOwner = true;
                }
            }
        } catch (ownerError) {
            // If owner check fails, log but continue to members check
            console.warn('Could not check project owner, falling back to members list:', ownerError.message);
        }

        if (isProjectOwner) {
            return res.status(200).json({
                hasAccess: true,
                reason: 'User is the project owner',
                email: email,
                langCode: langCode,
                roles: ['owner'],
                isProjectOwner: true
            });
        }

        // Get all project members
        let allMembers = [];
        let offset = 0;
        const limit = 500;
        let hasMore = true;

        while (hasMore) {
            const membersResponse = await fetch(
                `${CROWDIN_API_BASE}/projects/${CROWDIN_PROJECT_ID}/members?limit=${limit}&offset=${offset}`,
                {
                    headers: {
                        'Authorization': `Bearer ${CROWDIN_TOKEN}`,
                        'Content-Type': 'application/json'
                    }
                }
            );

            if (!membersResponse.ok) {
                const errorText = await membersResponse.text();
                throw new Error(`Crowdin API error: ${membersResponse.status} ${membersResponse.statusText} - ${errorText}`);
            }

            const membersData = await membersResponse.json();
            const members = membersData.data || [];
            allMembers = allMembers.concat(members);

            // Check if there are more pages
            const pagination = membersData.pagination;
            if (pagination && pagination.offset + pagination.limit < pagination.total) {
                offset += limit;
            } else {
                hasMore = false;
            }
        }

        // Find member by email (case-insensitive)
        const userMember = allMembers.find(member => {
            const memberEmail = member.data?.user?.email || member.data?.email || '';
            return memberEmail.toLowerCase() === email.toLowerCase();
        });

        if (!userMember) {
            // User not found in Crowdin project members
            return res.status(200).json({
                hasAccess: false,
                reason: 'User not found in Crowdin project members',
                email: email,
                langCode: langCode
            });
        }

        const memberData = userMember.data || {};
        const roles = memberData.roles || [];
        const languagesAccess = memberData.languagesAccess || [];
        const accessToAllWorkflowSteps = memberData.accessToAllWorkflowSteps || false;

        // Check if user has manager or owner role (these have full access)
        const hasManagerRole = roles.some(role => {
            const roleName = role.name || '';
            return roleName.toLowerCase() === 'manager' || roleName.toLowerCase() === 'owner';
        });

        if (hasManagerRole || accessToAllWorkflowSteps) {
            return res.status(200).json({
                hasAccess: true,
                reason: 'User has manager/owner role or access to all workflow steps',
                email: email,
                langCode: langCode,
                roles: roles.map(r => r.name)
            });
        }

        // Check if user has editor role
        const hasEditorRole = roles.some(role => {
            const roleName = role.name || '';
            return roleName.toLowerCase() === 'editor' || roleName.toLowerCase() === 'translator';
        });

        if (!hasEditorRole) {
            return res.status(200).json({
                hasAccess: false,
                reason: 'User does not have editor or translator role',
                email: email,
                langCode: langCode,
                roles: roles.map(r => r.name)
            });
        }

        // Check language-specific access
        // If languagesAccess is empty, user has access to all languages
        if (languagesAccess.length === 0) {
            return res.status(200).json({
                hasAccess: true,
                reason: 'User has editor role with access to all languages',
                email: email,
                langCode: langCode,
                roles: roles.map(r => r.name)
            });
        }

        // Check if user has access to the specific language
        const hasLanguageAccess = languagesAccess.some(lang => {
            const langId = lang.languageId || lang.id || lang;
            return langId === crowdinLangId || langId === langCode;
        });

        if (hasLanguageAccess) {
            return res.status(200).json({
                hasAccess: true,
                reason: `User has editor role with access to language ${crowdinLangId}`,
                email: email,
                langCode: langCode,
                crowdinLangId: crowdinLangId,
                roles: roles.map(r => r.name)
            });
        } else {
            return res.status(200).json({
                hasAccess: false,
                reason: `User has editor role but no access to language ${crowdinLangId}`,
                email: email,
                langCode: langCode,
                crowdinLangId: crowdinLangId,
                roles: roles.map(r => r.name),
                accessibleLanguages: languagesAccess.map(l => l.languageId || l.id || l)
            });
        }

    } catch (error) {
        console.error('Error checking Crowdin permissions:', error);
        res.status(500).json({
            error: 'Failed to check Crowdin permissions',
            message: error.message
        });
    }
}


