# Service Account Creation Script

This script automates the creation of Google Cloud service accounts for Levante dashboard deployment.

## Quick Start

### Using npm (Recommended)
```bash
# Create service account for dev environment
npm run setup:service-account-dev --project_id=your-project-id

# Create service account for production environment  
npm run setup:service-account-prod --project_id=your-project-id

# Create service accounts for both dev and prod
npm run setup:service-account-both --project_id=your-project-id
```

### Direct Python Usage
```bash
# Basic usage
python3 utilities/create_service_account.py --project-id your-project-id

# Production environment
python3 utilities/create_service_account.py --project-id your-project-id --prod

# Both environments
python3 utilities/create_service_account.py --project-id your-project-id --both

# Include permission testing
python3 utilities/create_service_account.py --project-id your-project-id --test
```

## Prerequisites

1. **Google Cloud CLI installed and authenticated**
   ```bash
   # Install gcloud CLI
   # https://cloud.google.com/sdk/docs/install
   
   # Authenticate
   gcloud auth login
   
   # Set your project (optional, script can do this)
   gcloud config set project your-project-id
   ```

2. **Required permissions**
   - `iam.serviceAccounts.create` (to create service accounts)
   - `resourcemanager.projects.setIamPolicy` (to grant roles)
   - `iam.serviceAccountKeys.create` (to create keys)

3. **Target buckets exist**
   - `levante-dashboard-dev` (for dev environment)
   - `levante-dashboard-prod` (for prod environment)

## What the Script Does

### 1. **Creates Service Account**
- Name: `levante-dashboard-writer-{env}`
- Description: Service account for writing to Levante dashboard buckets
- Display name: `Levante Dashboard Writer (DEV/PROD)`

### 2. **Grants Permissions**
- **Preferred**: Bucket-specific `objectAdmin` role using `gsutil`
- **Fallback**: Project-level `storage.objectAdmin` role if bucket-specific fails

### 3. **Creates JSON Key**
- Downloads service account key to `levante-dashboard-{env}-key.json`
- Displays the JSON content for copying to GitHub secrets

### 4. **Optional Testing**
- Tests bucket access using the created service account
- Verifies permissions are working correctly

## Output Files

The script creates these files:
- `levante-dashboard-dev-key.json` (dev environment)
- `levante-dashboard-prod-key.json` (prod environment)

## GitHub Secret Setup

After running the script:

1. **Copy the JSON content** displayed in the terminal
2. **Go to GitHub repository** → Settings → Secrets and variables → Actions  
3. **Add secret**: `GOOGLE_APPLICATION_CREDENTIALS_JSON`
4. **Paste the JSON content** as the secret value

## Example Output

```bash
$ npm run setup:service-account-dev --project_id=my-project

🔧 Levante Dashboard Service Account Creator
==================================================
🔍 Checking gcloud authentication...
   ✅ Authenticated as: user@example.com
   ✅ Current project: my-project

🔧 Setting project to my-project...
   ✅ Success

🚀 Creating service account for DEV environment
   Service Account: levante-dashboard-writer-dev
   Email: levante-dashboard-writer-dev@my-project.iam.gserviceaccount.com
   Target Bucket: levante-dashboard-dev
   Key File: levante-dashboard-dev-key.json

🔧 Creating service account 'levante-dashboard-writer-dev'...
   ✅ Success

🔧 Granting permissions to bucket 'levante-dashboard-dev'...
   ✅ Success

🔧 Creating service account key...
   ✅ Success

✅ Service account created successfully!
   📧 Email: levante-dashboard-writer-dev@my-project.iam.gserviceaccount.com
   🔑 Key file: levante-dashboard-dev-key.json
   🪣 Target bucket: gs://levante-dashboard-dev

📋 GitHub Secret Content (copy this to GOOGLE_APPLICATION_CREDENTIALS_JSON):
================================================================================
{
  "type": "service_account",
  "project_id": "my-project",
  ...
}
================================================================================
```

## Troubleshooting

### Common Errors

**"Permission denied"**
- Ensure you have the required IAM permissions in your Google Cloud project
- Your account needs to be able to create service accounts and grant roles

**"Bucket not found"**
- Make sure the target buckets exist:
  - `gs://levante-dashboard-dev`
  - `gs://levante-dashboard-prod`

**"gcloud not found"**
- Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
- Run `gcloud auth login` to authenticate

**"Project not set"**
- Either pass `--project-id` parameter or run `gcloud config set project YOUR_PROJECT_ID`

### Manual Verification

Test the created service account manually:
```bash
# Set the credentials
export GOOGLE_APPLICATION_CREDENTIALS="./levante-dashboard-dev-key.json"

# Test bucket access
gsutil ls gs://levante-dashboard-dev

# Test file upload
echo "test" | gsutil cp - gs://levante-dashboard-dev/test.txt
gsutil rm gs://levante-dashboard-dev/test.txt
```

## Security Notes

- **Keep JSON keys secure** - never commit them to version control
- **Use minimal permissions** - the script grants only necessary bucket access
- **Rotate keys regularly** - consider setting up key rotation for production
- **Environment separation** - use different service accounts for dev vs prod

## Alternative: Manual Creation

If you prefer to create service accounts manually, follow the detailed guide in [`create_dashboard_service_account.md`](../create_dashboard_service_account.md).