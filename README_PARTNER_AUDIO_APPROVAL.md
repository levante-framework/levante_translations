# Partner Audio Approval Tool

This guide explains how research partners can review and approve audio translations for their site using the Partner Audio Approval Tool.

## Overview

The Partner Audio Approval Tool is a streamlined interface designed for research partners to:
- Review audio translations for their specific language
- Listen to existing audio clips
- Generate audio for items without audio files
- Regenerate audio with custom text if needed
- Approve audio clips for deployment (immediate approval workflow)
- Search and filter items for efficient review

## Access

The Partner Audio Approval Tool is available at:
- **Production**: https://levante-partner-tools.vercel.app/audio-approval.html
- **Development**: https://levante-pitwall.vercel.app/partner-audio-dashboard.html

## Prerequisites

- Valid admin credentials for your research site
- Access granted by Levante administrators
- Your site's language must be configured in the system

## Authentication

The dashboard supports three authentication methods:

### 1. Firebase Password Login
- Enter your email address and password
- Standard authentication for users with Firebase accounts
- The system will automatically restrict you to your site's assigned language

### 2. SuperAdmin Passwordless Login
- **SuperAdmin emails can log in without a password**
- Enter your SuperAdmin email address
- Leave the password field empty (or don't fill it)
- Click "Sign In with Password"
- You will be automatically logged in
- SuperAdmin users have full access to all languages

**SuperAdmin Email List:**
- `sachino@stanford.edu`
- `david81@stanford.edu`
- `cuskley@stanford.edu`
- `aal@stanford.edu`
- `zdwatson@stanford.edu`
- `serlee@stanford.edu`
- `mcfrank@stanford.edu`
- `acardinal42@gmail.com`
- `admin@levante.com`
- `superadmin@levante.com`

### 3. Crowdin Email Login
- Click the "Crowdin Email" tab
- Enter your Crowdin email address (no password needed)
- Click "Sign In with Crowdin Email"
- The system verifies your email with Crowdin and grants access based on your role:
  - **Crowdin Owner/Manager**: Full access to all languages
  - **Crowdin Editor**: Access to languages you have editor permissions for
  - **Crowdin Translator**: Access to languages you have translator permissions for (other languages appear grayed out in dropdown)

### Language Access
- **Full Access Users** (SuperAdmin, Crowdin Owner/Manager): Can access all languages
- **Language-Specific Users** (Crowdin Editor/Translator): Can only access languages they have permissions for
- **Crowdin Translators**: See language dropdown with accessible languages enabled and others grayed out

## Workflow

### 1. Select Language

- If you have access to multiple languages, select your language from the dropdown
- If you're restricted to a single language, it will be automatically selected
- The dashboard will load all available audio items for your language
- Items display immediately after language selection

### 2. Review Items

The dashboard shows three tabs:

#### **To Be Approved Tab**
- Displays all audio items that need review
- Shows source text (English) and translated text
- Each item includes:
  - **Source (English)**: The original English text
  - **Translation**: The translated text in your language
  - **Audio-enhanced string**: Editable text field for custom audio generation
  - **Action buttons**: Play, Approve, Regenerate, Save

#### **Approved Tab**
- Shows all items you've approved
- Compact view with item ID, translated text, and Unapprove button
- Items in this tab have been moved to the approved bucket (`levante-assets-dev`)
- Unapproving moves items back to the draft bucket

#### **No Audio Tab**
- Displays items that don't have audio files yet
- Compact card layout showing:
  - Item ID
  - Source text (English)
  - Translated text
  - **Generate Audio** button: Creates audio from the translated text
  - **Save & Approve** button: Saves generated audio and immediately approves it
- Items can be generated and approved in one workflow

### 3. Listen to Audio

- Click the **Play** button to listen to the current audio clip
- Audio is fetched from the draft bucket (`levante-assets-draft`) for pending items
- Audio is fetched from the dev bucket (`levante-assets-dev`) for approved items
- If no audio exists, you'll need to generate it (use the "No Audio" tab)

### 4. Generate Audio (No Audio Tab)

For items without audio files:

1. Navigate to the **No Audio** tab
2. Review the source text and translation
3. Click **Generate Audio** to create audio from the translated text
4. The audio will play automatically after generation
5. Click **Save & Approve** to save the audio and immediately approve it
6. The item will move to the "Approved" tab

### 5. Regenerate Audio (Optional)

If you want to customize the audio:

1. Edit the **Audio-enhanced string** text field (pre-filled with translated text)
2. Click **Regenerate** to generate new audio with your custom text
3. The audio will play automatically after generation
4. Click **Save** to save the regenerated audio
5. Click **Approve** to immediately approve the audio

### 6. Approve Items

**Immediate Approval Workflow:**
- Click the **Approve** button on any item
- The audio file is immediately moved from `levante-assets-draft` to `levante-assets-dev`
- The item disappears from the "To Be Approved" tab
- The item appears in the "Approved" tab
- Statistics update automatically
- No batch confirmation needed

### 7. Unapprove Items (if needed)

- Switch to the **Approved** tab
- Click **Unapprove** on any item
- The audio file is immediately moved back from `levante-assets-dev` to `levante-assets-draft`
- The item disappears from the "Approved" tab
- The item appears back in the "To Be Approved" tab
- Statistics update automatically

## Search Functionality

- Use the search box above the tabs to find specific items
- Search by:
  - Item ID (e.g., "vocab-item-119")
  - Any text content (source text, translated text, etc.)
- Search works in real-time as you type
- Search filters work across all tabs
- Click the X button to clear the search

## Statistics

The top of the dashboard shows four statistics:
- **Total Items**: All items with translations for your language
- **Approved**: Items that have been approved and moved to dev bucket
- **Pending**: Items still awaiting approval in the draft bucket
- **No Audio**: Items without audio files that need generation

Statistics update automatically as you approve/unapprove items.

## Tips

- **Immediate Feedback**: All approval actions happen immediately - no need to confirm batches
- **Audio Generation**: Use the "No Audio" tab to quickly generate audio for missing items
- **Audio Enhancement**: Use the "Audio-enhanced string" field to customize pronunciation or add pauses
- **Search**: Use search to quickly find specific items you need to review
- **Tab Navigation**: Switch between tabs to track your progress
- **Save & Approve**: On the "No Audio" tab, use "Save & Approve" to generate and approve in one step

## Troubleshooting

### "No items found"
- Ensure your language has translations in the CSV file
- Check that translations exist for your language
- Contact Levante support if items should be available

### "ElevenLabs API key missing"
- Audio generation requires API credentials
- These are configured server-side
- Contact Levante support if generation fails

### Items not appearing after approval
- Approved items move to the "Approved" tab immediately
- Check the Approved tab to see your approved items
- Statistics update automatically
- Refresh the page if items don't appear

### Can't see my language
- Your account may be restricted to a specific language
- Contact Levante administrators to verify your language assignment
- Superadmins can access all languages

### Items not displaying after language selection
- Items should display immediately after selecting a language
- If items don't appear, try switching tabs
- Check the browser console (F12 → Console) for errors
- Contact Levante support if the issue persists

## Technical Details

### Buckets
- **levante-assets-draft**: Contains draft audio files awaiting approval
- **levante-assets-dev**: Contains approved audio files ready for deployment

### File Structure
- Audio files are stored as: `audio/{language-code}/{item-id}.mp3`
- Versioned files use format: `{item-id}_v###.mp3`

### Approval Process
1. User clicks "Approve" → File immediately moves from draft to dev bucket
2. UI updates to show item in "Approved" tab
3. Statistics update automatically
4. No batch confirmation needed

### Unapproval Process
1. User clicks "Unapprove" → File immediately moves from dev back to draft bucket
2. UI updates to show item in "To Be Approved" tab
3. Statistics update automatically

## Support

For issues or questions:
- Contact your Levante administrator
- Check the documentation link at the top of the dashboard
- Review the console for error messages (F12 → Console)

## Related Documentation

- [README_PATCHING.md](./README_PATCHING.md) - Patch & Deploy Workflow for administrators
- [README_WebDashboard.md](./README_WebDashboard.md) - Main dashboard documentation
