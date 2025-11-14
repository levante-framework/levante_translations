# Dashboard Patch & Deploy Workflow

This guide explains how to use the Levante Pitwall to create small "patch" audio fixes and move them into the deploy queue without touching the Git repo manually.

## Prerequisites
- Access to the dashboard (Firebase superadmin role).
- Valid API credentials stored through the Credentials modal (PlayHT / ElevenLabs as needed).
- Draft audio bucket (`levante-assets-draft`) reachable from the dashboard runtime.

## Quick Reference
1. **Select an item** in the language table.
2. **Generate or re-generate audio** using the current voice selection.
3. **Save the audio** to the draft bucket (creates `audio/<lang>/<itemId>_v###.mp3`).
4. **Open Draft Audio** (folder icon button) and review entries.
5. **Approve** the files you want to ship.
6. **Deploy** the approved files.
7. **To be Deployed** button opens `deploy/<lang>/` in the draft bucket so you can confirm the final state.

## Detailed Workflow

### 1. Prepare the audio
- Pick the correct language tab and table row.
- If you need the voice from an existing asset, use **Re-generate Audio**; the dashboard pulls voice info from the metadata when available.
- Generate or edit the text box manually as needed.
- Click **Generate Audio**.

### 2. Save to drafts
- Once the preview sounds correct, use the **Save** button in the item row.
- Each save creates / updates `audio/<lang>/<itemId>_v###.mp3` in the `levante-assets-draft` bucket and tags it with `source=patch`.

### 3. Review drafts
- Click **Draft Audio** to open the draft modal.
- Use the play buttons for spot checks.
- Select the rows you intend to ship and ensure the metadata columns match expectations.

### 4. Approve for deployment
- Tick the **Approve** checkbox for each file you want in the deploy set.
- Selecting a row also enables the **Copy Draft Link** button if you need to share the folder with someone else.

### 5. Deploy
- After marking all desired files, hit **Deploy**.
- The backend now:
  - Copies each approved file to `deploy/<lang>/<itemId>.mp3` (version suffix removed).
  - Deletes every other version of the same root from both `audio/<lang>/` and `deploy/<lang>/`.
- A status alert confirms how many files moved and how many old versions were removed.

### 6. Verify
- Use the **To be Deployed** button (replaces the old Clear Text button) to open the deploy folder in a new tab.
- Confirm the cleaned set of files before promoting them to production buckets (manual or pipeline step).

## Notes & Troubleshooting
- **Accidental approvals:** simply uncheck the row before running Deploy.
- **Missing buttons:** refresh the dashboard—SPA updates may lag after a deployment.
- **Clipboard issues:** the Copy Draft Link button now shows inline feedback; if the clipboard is blocked, the dashboard falls back to a manual prompt.
- **Credential errors:** re-open the Credentials modal and ensure PlayHT / ElevenLabs tokens are valid for the current session.
- **Deploy failures:** the Deploy button operates entirely within GCS now. If it errors, check:
  - The service account attached to the dashboard has `storage.objects.get`, `copy`, and `delete` permissions on `levante-assets-draft`.
  - The selected objects still exist (saving over a deleted file will fail).

## Follow-up after Deployment
Moving files into `deploy/<lang>/` is the last step this dashboard performs. Downstream promotion (e.g., syncing to production buckets or repositories) remains a manual/CI task and should only run after verifying the deploy folder contents.
