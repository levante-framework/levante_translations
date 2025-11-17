# Dashboard Patch & Deploy Workflow


This guide explains how Levante Pitwall supports patching audio fixes --staring with re-generating versions of existing clips for review, selecting and approving the preferred version, and marking it for deployment.

## Summary for Colleagues

- Browse or filter every audio clip per language, audition samples, and regenerate text-to-speech as needed.
- Save preferred takes into the draft bucket using the **Save** button. Multiple saves create `_v###` versioned files tagged with `source=patch`.
- Open **Draft Audio** to review, share, and approve the subset you intend to ship.
- Share the **Review Alternative Audio Clips** link with research partners so they can approve or reject candidate versions.
- Site approvals move the chosen clips into the `deploy/<lang>/` staging folder; the “To be Deployed” view shows exactly what is queued for downstream promotion.
- DCC admins review a stoplight view of those deploy files, tag the clips that are **Okay to Push**, and downstream scripts promote the flagged set into the repo (`audio_files/…`) and `levante-assets-dev` bucket.

## Prerequisites
- Named or Firebase superadmin access to the dashboard.
- Valid Voice generation API credentials stored through the Credentials modal (PlayHT / ElevenLabs as needed).
- Access to `levante-assets-draft` -- should be built into the Pitwall via a service account.

## Detailed Workflow

### 1. Prepare the audio
- Choose the correct language tab and row in the dashboard table.
- Regenerate audio if you want to reuse/adjust existing voices; metadata is preloaded when available.
- Edit the transcription text if needed and click **Generate Audio** to audition the new clip.

### 2. Save to drafts
- When the preview sounds right, click **Save** on the row.
- The dashboard writes `audio/<lang>/<itemId>_v###.mp3` to `levante-assets-draft` and stamps the file with ID3 metadata (`voice`, `album`, `source=patch`, etc.).
- Re-saving the same item increments the numeric suffix so you can compare alternates.

### 3. Review and share drafts
- Open the **Draft Audio** modal from the dashboard or visit `/draft-share.html?bucket=levante-assets-draft&folder=audio` directly.
- Preview clips & Delete any versions you don't want to keep.
- Click **Copy Draft Link**. You can send this link to the Research Site, so they can review the alternatives and select the preferred version.

### 4. Site approval (research partner)
- Share the review link; researchers can preview, delete, or select the winning versions.
- When they click **Approve Selected**, Pitwall copies the chosen clip(s) into `deploy/<lang>/<itemId>.mp3` (stripping the version suffix) and the dashboard flags them as **Approved by Site**.
- No repo or `levante-assets-dev` writes occur during this step—research partners only control what appears in the deploy queue.

### 5. Flag site-approved audio for promotion (by DCC admin)
- Open `/draft-share.html?bucket=levante-assets-draft&folder=deploy` (no `mode=site` parameter). This presents a stoplight column:
  - **Not approved** (red) — no site-approved version exists yet.
  - **Approved by Site** (yellow) — the clip lives in `deploy/<lang>/` but has not been flagged for promotion.
  - **Ready to push** (green) — the clip has been marked with **Okay to Push** and is queued for promotion.
- Select one or more green/yellow rows and click **Okay to Push**. Pitwall writes the selection to `gs://levante-dashboard-dev/pitwall/deploy-queue/<bucket>/queue.json` (or the bucket configured via `DASHBOARD_DATA_BUCKET`), which downstream tooling consumes. No copies to the repo or `levante-assets-dev` are performed here.

### 6. Promote flagged audio (automation / engineering)
- Run the deployment script (e.g., `python utilities/promote_flagged_audio.py`) to download and process the queue JSON from `gs://levante-dashboard-dev/pitwall/deploy-queue/<bucket>/queue.json` (respecting the `DASHBOARD_DATA_BUCKET` override if set).
  - The script copies each flagged file into the repo (`audio_files/<lang>/…`) and uploads the same file to `levante-assets-dev/audio/<lang>/…`.
  - After a successful promotion it should clear the corresponding entries from the queue file so the stoplight view returns to yellow.
- Follow existing release processes (CI/CD or manual rsyncs) to push assets beyond the dev bucket.

## Notes & Troubleshooting
- **Selections reset when the table changes:** the send button reflects only the files currently visible in the Draft Audio list. If a file disappears (different folder/language), it’s automatically removed from the selection.
- **Master checkbox quirks:** the “Select all” control ignores rows without a valid path, and it will reflect the current selection if you manually toggle rows.
- **Accidental approvals:** in the research view, simply uncheck the row before clicking Approve. In the DCC view, click **Remove Selected** (which also clears the “Okay to Push” flag) if a clip should drop out of the queue.
- **Clipboard/share issues:** the Draft Audio share link button shows inline feedback; if the browser blocks clipboard access the dashboard falls back to a manual prompt.
- **Credential errors:** reopen the Credentials modal and verify PlayHT / ElevenLabs tokens for the active session.
- **Deploy failures:** ensure the dashboard service account has `storage.objects.get`, `copy`, and `delete` permissions on `levante-assets-draft`

## Follow-up after Deployment
Promoting files into `deploy/<lang>/` (and copying to the repo/dev bucket) is the last automated step. Downstream promotion—committing the updated `audio_files/<lang>/` assets or syncing to other production buckets—remains a manual/CI responsibility. Always verify the deploy folder before triggering those jobs.
