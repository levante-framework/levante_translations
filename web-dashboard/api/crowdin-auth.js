/**
 * API endpoint for Crowdin email-only authentication
 * Verifies user exists in Crowdin project and has editor permissions
 */

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    if (req.method !== 'POST') {
        res.status(405).json({ error: 'Method not allowed' });
        return;
    }

    try {
        const { email, projectId = process.env.LEVANTE_TRANSLATIONS_PROJECT_ID || '756721' } = req.body;
        
        if (!email) {
            res.status(400).json({ error: 'Email is required' });
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
            return res.status(401).json({
                authenticated: false,
                error: 'User not found in Crowdin project',
                email: email
            });
        }

        const memberData = userMember.data || {};
        const roles = memberData.roles || [];
        const languagesAccess = memberData.languagesAccess || [];
        const accessToAllWorkflowSteps = memberData.accessToAllWorkflowSteps || false;

        // Check if user has manager, owner, editor, or translator role
        const hasValidRole = roles.some(role => {
            const roleName = (role.name || '').toLowerCase();
            return ['manager', 'owner', 'editor', 'translator'].includes(roleName);
        });

        if (!hasValidRole && !accessToAllWorkflowSteps) {
            return res.status(403).json({
                authenticated: false,
                error: 'User does not have editor or translator permissions',
                email: email,
                roles: roles.map(r => r.name)
            });
        }

        // User is authenticated and has valid permissions
        // Return user info (without sensitive data)
        return res.status(200).json({
            authenticated: true,
            email: email,
            roles: roles.map(r => r.name),
            languagesAccess: languagesAccess.map(l => l.languageId || l.id || l),
            accessToAllWorkflowSteps: accessToAllWorkflowSteps,
            hasAllLanguagesAccess: languagesAccess.length === 0
        });

    } catch (error) {
        console.error('Error authenticating with Crowdin:', error);
        res.status(500).json({
            authenticated: false,
            error: 'Failed to authenticate with Crowdin',
            message: error.message
        });
    }
}


