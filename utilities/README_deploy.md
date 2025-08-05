# Dashboard and Translations Deployment

This deployment system uploads the Levante dashboard files and translation CSV files to Google Cloud Storage buckets for dev and prod environments.

## 🔧 Features

- **Environment Support**: Deploy to dev or prod buckets
- **Dashboard Deployment**: Uploads HTML, CSS, JS, and API files
- **Translation Deployment**: Uploads CSV files with translation data
- **File Validation**: Checks files exist and are readable before upload
- **Content Type Detection**: Sets appropriate MIME types and cache headers
- **Progress Reporting**: Detailed logging of upload progress
- **Dry Run Mode**: Test deployments without actually uploading

## 📋 Prerequisites

### Dependencies

```bash
pip install google-cloud-storage
```

### Credentials

Set your Google Cloud credentials:

```bash
export GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'
```

### Bucket Configuration

The system uses these buckets (configured in `utilities/buckets.py`):

| Environment | Dashboard Bucket | Translations Bucket |
|-------------|------------------|---------------------|
| Dev | `levante-dashboard-dev` | `levante-translations-dev` |
| Prod | `levante-dashboard-prod` | `levante-translations-prod` |

## 🚀 Quick Start

### Simple Interface

Use the simple `deploy.py` script:

```bash
# Deploy to dev environment
python deploy.py -dev

# Deploy to prod environment  
python deploy.py -prod

# Test deployment (dry run)
python deploy.py -dev --dry-run
```

### Advanced Interface

Use the full `utilities/deploy_dashboard.py` script:

```bash
# Deploy everything to dev
python utilities/deploy_dashboard.py --env dev

# Deploy everything to prod
python utilities/deploy_dashboard.py --env prod

# Deploy only dashboard files
python utilities/deploy_dashboard.py --env dev --dashboard-only

# Deploy only translation files
python utilities/deploy_dashboard.py --env dev --translations-only

# Test deployment without uploading
python utilities/deploy_dashboard.py --env dev --dry-run
```

## 📁 Files Deployed

### Dashboard Files

The deployment includes:

- **`index.html`**: Main dashboard interface
- **`config.js`**: Configuration file
- **`package.json`**: Node.js dependencies
- **`vercel.json`**: Vercel deployment configuration
- **`api/`**: Serverless function files
  - `elevenlabs-proxy.js`
  - `playht-proxy.js`
  - `translate-proxy.js`
  - `validation-storage.js`
- **`translation_text/`**: CSV files for the dashboard

### Translation Files

- **`translation_master.csv`**: Main translation dataset
- **`translation_text/item_bank_translations.csv`**: Item bank translations
- **`translation_text/complete_translations.csv`**: Complete translation dataset

## 🔄 Deployment Process

1. **File Discovery**: Scans for dashboard and translation files
2. **Validation**: Checks all files exist and are readable
3. **Content Type Detection**: Sets appropriate MIME types
4. **Upload**: Uploads files with metadata to GCS buckets
5. **Cache Headers**: Sets cache control for optimal performance
6. **Verification**: Reports success/failure for each file

## ⚙️ Configuration

### Content Types

The system automatically sets content types:

| File Extension | Content Type |
|----------------|--------------|
| `.html` | `text/html` |
| `.js` | `application/javascript` |
| `.css` | `text/css` |
| `.csv` | `text/csv` |
| `.json` | `application/json` |

### Cache Control

Cache headers are optimized by file type:

| File Type | Cache Duration |
|-----------|----------------|
| HTML files | 5 minutes |
| JS/CSS files | 1 hour |
| CSV files | 30 minutes |
| Other files | 10 minutes |

## 📊 Example Output

```
🚀 Levante Dashboard Deployment
   Environment: dev
   Mode: DEPLOY
==================================================
✅ Initialized DashboardDeployer
   Environment: dev
   Dashboard Bucket: levante-dashboard-dev
   Translations Bucket: levante-translations-dev
   GCS Client: ✅ Ready

🌐 Deploying dashboard to dev environment...
🔍 Validating files...
✅ All 8 files validated (total size: 1,234,567 bytes)
📤 Uploading 8 dashboard files to levante-dashboard-dev...
   ✅ index.html (45,678 bytes) → index.html
   ✅ config.js (1,234 bytes) → config.js
   ✅ package.json (567 bytes) → package.json
   ... uploading remaining files...
✅ dashboard files: uploaded 8/8 files to levante-dashboard-dev

📊 Deploying translations to dev environment...
🔍 Validating files...
✅ All 3 files validated (total size: 2,345,678 bytes)
📤 Uploading 3 translation files to levante-translations-dev...
   ✅ translation_master.csv (1,234,567 bytes) → translation_master.csv
   ✅ item_bank_translations.csv (567,890 bytes) → translation_text/item_bank_translations.csv
   ✅ complete_translations.csv (543,221 bytes) → translation_text/complete_translations.csv
✅ translation files: uploaded 3/3 files to levante-translations-dev

🎉 Deployment completed!
   Dashboard: ✅ Success
   Translations: ✅ Success

🌐 Dashboard URLs:
   Dashboard: https://storage.googleapis.com/levante-dashboard-dev/index.html
   Translations: https://storage.googleapis.com/levante-translations-dev/translation_master.csv
```

## 🔐 Security

### Bucket Permissions

Ensure your service account has these permissions:

- **Storage Object Admin** on the target buckets
- Or minimum: **Storage Object Creator** + **Storage Object Viewer**

### Public Access

For web hosting, buckets may need public read access:

```bash
# Make bucket publicly readable (if needed for web hosting)
gsutil iam ch allUsers:objectViewer gs://levante-dashboard-dev
```

## 🛠️ Troubleshooting

### Common Issues

1. **"GCS client not initialized"**
   - Check `GOOGLE_APPLICATION_CREDENTIALS_JSON` environment variable
   - Verify service account has bucket permissions

2. **"Bucket not found"**
   - Ensure buckets exist in your GCP project
   - Check bucket names in `utilities/buckets.py`

3. **"File not found"**
   - Run from the project root directory
   - Check that dashboard files exist (especially `index.html`)

4. **"Permission denied"**
   - Verify service account has Storage Object Admin role
   - Check bucket-level IAM permissions

### Testing Commands

```bash
# Test GCS access
gsutil ls gs://levante-dashboard-dev

# Test file uploads
echo "test" > test.txt
gsutil cp test.txt gs://levante-dashboard-dev/
gsutil rm gs://levante-dashboard-dev/test.txt
rm test.txt

# Dry run deployment
python deploy.py -dev --dry-run
```

## 🔄 Integration

### CI/CD Integration

```yaml
# Example GitHub Actions workflow
- name: Deploy Dashboard
  env:
    GOOGLE_APPLICATION_CREDENTIALS_JSON: ${{ secrets.GCS_CREDENTIALS }}
  run: |
    python deploy.py -prod
```

### Automated Deployment

```bash
#!/bin/bash
# Deploy script with error handling
set -e

echo "Starting deployment..."
python deploy.py -dev --dry-run
echo "Dry run successful, proceeding with deployment..."
python deploy.py -dev
echo "Deployment completed!"
```

## 📝 File Structure

```
levante_translations/
├── deploy.py                          # Simple deploy interface
├── utilities/
│   ├── deploy_dashboard.py            # Full deployment functionality
│   ├── buckets.py                     # Bucket configuration
│   └── README_deploy.md              # This documentation
├── index.html                         # Main dashboard
├── config.js                          # Dashboard config
├── api/                               # Serverless functions
├── translation_text/                  # Translation CSV files
└── translation_master.csv             # Main translations
```