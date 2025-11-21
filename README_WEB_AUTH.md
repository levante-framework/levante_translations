# Web Dashboard Authentication Guide

This document describes the authentication and authorization system for the Levante Partner Audio Approval Tool.

## Authentication Methods

The dashboard supports three authentication methods:

1. **Firebase Authentication** - Email and password login
2. **SuperAdmin Passwordless Login** - Email-only login for SuperAdmin users (no password required)
3. **Crowdin Email Authentication** - Email-only login (verifies email exists in Crowdin project)

## Authorization Levels

### Access Control Table

| User Type | Access Level | Login Method | Notes |
|-----------|-------------|-------------|-------|
| **Firebase SuperAdmin** | Full Access | Email + Password | Can access all languages and all features |
| **SuperAdmin Override** | Full Access | Email only (no password) | Hardcoded email list, passwordless login |
| **Crowdin Owner** | Full Access | Email only (no password) | Project owner in Crowdin, can access all languages |
| **Crowdin Manager** | Full Access | Email only (no password) | Manager role in Crowdin, can access all languages |
| **Crowdin Editor** | Language-Specific | Email only (no password) | Can access languages they have editor permissions for |
| **Crowdin Translator** | Language-Specific | Email only (no password) | Can access languages they have translator permissions for. Other languages appear grayed out in dropdown |

### Full Access Definition

Users with **Full Access** can:
- Access all languages in the dropdown
- View and approve audio for any language
- Use all dashboard features without restrictions

### Language-Specific Access Definition

Users with **Language-Specific Access** can:
- Only access languages they have permissions for in Crowdin
- View and approve audio only for their assigned languages
- See language dropdown filtered to their accessible languages

## Implementation Details

### Firebase SuperAdmin

- Checked via Firebase custom claims (`super_admin: true`)
- Set in Firebase Admin Console or via backend service
- Grants immediate full access
- Requires email and password login

### SuperAdmin Override (Passwordless)

- Hardcoded list of SuperAdmin emails in `firebase-config.js`
- Emails include: `sachino@stanford.edu`, `david81@stanford.edu`, `cuskley@stanford.edu`, `aal@stanford.edu`, `zdwatson@stanford.edu`, `serlee@stanford.edu`, `mcfrank@stanford.edu`, `acardinal42@gmail.com`, `admin@levante.com`, `superadmin@levante.com`
- **Passwordless login**: Users can log in by entering only their email (password field can be left empty)
- Checked at the very start of `handlePasswordLogin()` function before any password validation
- Completely bypasses Firebase authentication
- Grants immediate full access to all languages
- Login happens automatically when SuperAdmin email is detected

### Crowdin Owner/Manager

- Verified via Crowdin API `/projects/{id}/members` endpoint
- Roles checked: `owner` or `manager` (case-insensitive)
- Project owner also checked via `/projects/{id}` endpoint
- Grants full access automatically

### Crowdin Editor/Translator

- Verified via Crowdin API `/projects/{id}/members` endpoint
- Roles checked: `editor` or `translator` (case-insensitive)
- Language access determined by `languagesAccess` array in member data
- If `languagesAccess` is empty, user has access to all languages

## API Endpoints

### `/api/crowdin-auth`

Authenticates a user via Crowdin email verification.

**Request:**
```json
{
  "email": "user@example.com",
  "projectId": "756721" // optional, defaults to env var
}
```

**Response (Success):**
```json
{
  "authenticated": true,
  "email": "user@example.com",
  "roles": ["owner"],
  "languagesAccess": [],
  "accessToAllWorkflowSteps": true,
  "hasAllLanguagesAccess": true,
  "isOwner": true,
  "isManager": false
}
```

**Response (Failure):**
```json
{
  "authenticated": false,
  "error": "User not found in Crowdin project",
  "email": "user@example.com"
}
```

### `/api/crowdin-check-permissions`

Checks if a user has access to a specific language.

**Request:**
```json
{
  "email": "user@example.com",
  "langCode": "pt-PT",
  "projectId": "756721" // optional
}
```

**Response:**
```json
{
  "hasAccess": true,
  "reason": "User is the project owner",
  "email": "user@example.com",
  "langCode": "pt-PT",
  "roles": ["owner"],
  "isProjectOwner": true
}
```

## Environment Variables

Required environment variables for Crowdin authentication:

- `CROWDIN_API_TOKEN` - Crowdin API token with project access
- `LEVANTE_TRANSLATIONS_PROJECT_ID` - Crowdin project ID (default: "756721")

## Error Handling

- If Crowdin API is unavailable, authentication fails gracefully
- Project owner check failures fall back to members list check
- All errors are logged for debugging

## Security Notes

- Crowdin email authentication does NOT require a password
- Email verification is done server-side via Crowdin API
- No sensitive data is exposed to the client
- All API endpoints use CORS headers appropriately

