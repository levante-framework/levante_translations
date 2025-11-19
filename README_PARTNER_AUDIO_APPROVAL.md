# Partner Audio Approval Tool

This guide explains how research partners can review and approve audio translations for their site using the Partner Audio Approval Tool.

## Overview

The Partner Audio Approval Tool is a streamlined interface designed for research partners to:
- Review audio translations for their specific language
- Listen to existing audio clips
- Regenerate audio with custom text if needed
- Approve audio clips for deployment
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

1. Navigate to the Partner Audio Approval Tool
2. Sign in with your admin email and password
3. The system will automatically restrict you to your site's assigned language
4. Superadmins and override users can access all languages

## Workflow

### 1. Select Language

- If you have access to multiple languages, select your language from the dropdown
- If you're restricted to a single language, it will be automatically selected
- The dashboard will load all available audio items for your language

### 2. Review Items

The dashboard shows two tabs:

#### **To Be Approved Tab**
- Displays all audio items that need review
- Shows source text (English) and translated text
- Each item includes:
  - **Source (English)**: The original English text
  - **Translation**: The translated text in your language
  - **Audio-enhanced string**: Editable text field for custom audio generation
  - **Action buttons**: Play, Approve, Regenerate, Approve & Save

#### **Approved Tab**
- Shows all items you've approved
- Compact view with item ID, translated text, and Unapprove button
- Items in this tab have been moved to the approved bucket

### 3. Listen to Audio

- Click the **Play** button to listen to the current audio clip
- Audio is fetched from the draft bucket (`levante-assets-draft`)
- If no audio exists, you'll need to regenerate it

### 4. Regenerate Audio (Optional)

If you want to customize the audio:

1. Edit the **Audio-enhanced string** text field (pre-filled with translated text)
2. Click **Regenerate** to generate new audio with your custom text
3. The audio will play automatically after generation
4. Click **Approve & Save** to save the regenerated audio and mark it for approval

### 5. Approve Items

You can approve items in two ways:

#### **Quick Approve**
- Click the **Approve** button on any item
- The item is marked for approval (yellow border)
- It will be included in the next batch approval

#### **Approve & Save**
- After regenerating audio, click **Approve & Save**
- Saves the regenerated audio and marks it for approval
- Combines saving and approval in one action

### 6. Batch Approval

When you've marked items for approval:

1. A yellow banner appears at the top showing "X item(s) marked for approval"
2. Review all marked items (they have yellow borders)
3. Click **Confirm Approvals** to process all pending approvals
4. The system will:
   - Move all approved audio files from `levante-assets-draft` to `levante-assets-dev`
   - Update the approval status
   - Remove items from the "To Be Approved" tab
   - Add them to the "Approved" tab

### 7. Unapprove Items (if needed)

- Switch to the **Approved** tab
- Click **Unapprove** on any item
- The item will be removed from approved status
- Note: The file remains in the approved bucket, but it won't show as approved in the UI

## Search Functionality

- Use the search box above the tabs to find specific items
- Search by:
  - Item ID (e.g., "vocab-item-119")
  - Any text content (source text, translated text, etc.)
- Search works in real-time as you type
- Click the X button to clear the search

## Statistics

The top of the dashboard shows:
- **Total Items**: All items with audio files for your language
- **Approved**: Items that have been approved and moved to dev bucket
- **Pending**: Items still awaiting approval

## Tips

- **Batch Processing**: Mark multiple items for approval, then confirm all at once for efficiency
- **Audio Enhancement**: Use the "Audio-enhanced string" field to customize pronunciation or add pauses
- **Search**: Use search to quickly find specific items you need to review
- **Tab Navigation**: Switch between "To Be Approved" and "Approved" tabs to track your progress

## Troubleshooting

### "No items found"
- Ensure your language has audio files in the draft bucket
- Check that translations exist for your language
- Contact Levante support if items should be available

### "ElevenLabs API key missing"
- Audio regeneration requires API credentials
- These are configured server-side
- Contact Levante support if regeneration fails

### Items not appearing after approval
- Approved items move to the "Approved" tab
- Check the Approved tab to see your approved items
- Statistics update automatically

### Can't see my language
- Your account may be restricted to a specific language
- Contact Levante administrators to verify your language assignment
- Superadmins can access all languages

## Technical Details

### Buckets
- **levante-assets-draft**: Contains draft audio files awaiting approval
- **levante-assets-dev**: Contains approved audio files ready for deployment

### File Structure
- Audio files are stored as: `audio/{language-code}/{item-id}.mp3`
- Versioned files use format: `{item-id}_v###.mp3`

### Approval Process
1. Items are marked for approval (stored in browser state)
2. "Confirm Approvals" triggers batch processing
3. Files are moved from draft to dev bucket
4. Metadata is preserved during the move
5. UI updates to reflect new approval status

## Support

For issues or questions:
- Contact your Levante administrator
- Check the documentation link at the top of the dashboard
- Review the console for error messages (F12 → Console)

## Related Documentation

- [README_PATCHING.md](./README_PATCHING.md) - Patch & Deploy Workflow for administrators
- [README_WebDashboard.md](./README_WebDashboard.md) - Main dashboard documentation

