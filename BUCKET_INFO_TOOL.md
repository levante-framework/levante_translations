# Bucket Info Tool

## Overview

The Bucket Info tool is a web-based interface for managing README and LICENSE files across all LEVANTE Google Cloud Storage buckets. It provides a centralized way to document bucket purposes and apply appropriate licenses.

## Features

### 1. **Bucket Management Interface**
- View all development and production buckets in organized tables
- Edit bucket descriptions and license types in a user-friendly form
- Save changes locally (persisted in browser localStorage)
- Deploy README and LICENSE files to buckets with one click

### 2. **License Templates**
Two license options are available:

#### Creative Commons Attribution 4.0 (CC BY 4.0)
- Suitable for open educational resources
- Allows sharing and adaptation with attribution
- Full license text included automatically

#### ROAR License
- Proprietary license for restricted use
- Suitable for assessment materials and confidential data
- Includes contact information for licensing inquiries

### 3. **Automated Deployment**
- Generates README.md with bucket description and metadata
- Generates LICENSE file with full license text
- Uploads both files to the bucket root
- Provides deployment status feedback

## Usage

### Accessing the Tool
1. Open the LEVANTE Dashboard
2. Click **Tools** menu in the header
3. Select **Bucket Info**

### Managing Bucket Information
1. **Refresh Buckets**: Load the current list of buckets
2. **Edit Information**: 
   - Select a license type from the dropdown (Creative Commons or ROAR)
   - Enter a description for each bucket
3. **Save Changes**: Click "Save Changes" to persist locally
4. **Deploy All**: Click "Deploy All" to upload README and LICENSE files to all buckets with descriptions

### What Gets Deployed

For each bucket, two files are created:

#### README.md
```markdown
# bucket-name

[Your description here]

## License
[License information]

## About LEVANTE
[Project information]

---
*Last updated: YYYY-MM-DD*
```

#### LICENSE
Full license text based on the selected license type (Creative Commons or ROAR).

## Technical Details

### Files Created
- **Frontend**: `/web-dashboard/public/bucket-info.html`
- **API Endpoint**: `/web-dashboard/api/deploy-bucket-docs.js`
- **Menu Integration**: Updated `/web-dashboard/public/index.html`

### Buckets Managed

**Development Buckets (18):**
- levante-assets-dev
- levante-assets-draft
- levante-audio-dev
- levante-corpora-airtable
- levante-dashboard-dev
- levante-external-data
- levante-hearts-and-flowers-dev
- levante-images-dev
- levante-intro-dev
- levante-math-dev
- levante-memory-dev
- levante-pattern-matching-dev
- levante-same-different-dev
- levante-sentence-understanding-dev
- levante-shape-rotation-dev
- levante-stories-dev
- levante-tasks-shared-dev
- levante-vocabulary-dev

**Production Buckets (17):**
- levante-assets-prod
- levante-audio-prod
- levante-audiofiles
- levante-auth-backup
- levante-dashboard-prod
- levante-hearts-and-flowers-prod
- levante-intro-prod
- levante-math-prod
- levante-memory-prod
- levante-pattern-matching-prod
- levante-roar-data-bucket-prod
- levante-same-different-prod
- levante-sentence-understanding-prod
- levante-shape-rotation-prod
- levante-stories-prod
- levante-tasks-shared-prod
- levante-vocabulary-prod

### API Endpoint

**POST** `/api/deploy-bucket-docs`

**Request Body:**
```json
{
  "bucket": "bucket-name",
  "license": "Creative Commons" | "ROAR",
  "description": "Bucket description text"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully deployed README and LICENSE to bucket-name",
  "files": [
    "gs://bucket-name/README.md",
    "gs://bucket-name/LICENSE"
  ]
}
```

### Data Persistence
- Bucket information is saved to browser localStorage
- Key: `bucketInfo`
- Format: JSON object with bucket names as keys

## Best Practices

1. **Fill in descriptions before deploying**: The tool skips buckets without descriptions
2. **Save frequently**: Use the "Save Changes" button to persist your work locally
3. **Review before deploying**: Check all descriptions and license selections before clicking "Deploy All"
4. **Use appropriate licenses**:
   - **Creative Commons**: For public educational resources, translations, open data
   - **ROAR**: For proprietary assessments, confidential data, restricted materials

## Troubleshooting

### Deployment Fails
- Ensure you have write permissions to the bucket
- Check that the bucket exists and is accessible
- Verify you're authenticated with the correct GCP project

### Changes Not Saved
- Check browser console for errors
- Ensure localStorage is enabled in your browser
- Try refreshing the page and re-entering data

### Bucket Not Listed
- Update the bucket lists in `bucket-info.html` if new buckets are added
- Buckets are hardcoded in the DEV_BUCKETS and PROD_BUCKETS arrays

## Future Enhancements

Potential improvements:
- Dynamic bucket discovery via GCS API
- Preview README/LICENSE before deployment
- Deploy to individual buckets (not just all at once)
- Version history for README/LICENSE files
- Custom license templates
- Bulk import/export of bucket information

---

*Created: 2025-10-08*
*Last Updated: 2025-10-08*

