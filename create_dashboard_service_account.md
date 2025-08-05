# Creating Service Account for levante-dashboard-dev Bucket

This guide helps you create a Google Cloud Service Account with write permissions to the `levante-dashboard-dev` bucket.

## Option 1: Using Google Cloud Console (Web UI)

### Step 1: Create Service Account
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (where the bucket exists)
3. Navigate to **IAM & Admin** → **Service Accounts**
4. Click **+ CREATE SERVICE ACCOUNT**
5. Fill in details:
   - **Service account name**: `levante-dashboard-writer`
   - **Service account ID**: `levante-dashboard-writer` (auto-generated)
   - **Description**: `Service account for writing to levante-dashboard-dev bucket`
6. Click **CREATE AND CONTINUE**

### Step 2: Grant Permissions
1. In the **Grant this service account access to project** section:
   - Click **Select a role**
   - Choose **Cloud Storage** → **Storage Object Admin**
   - Or use custom role: **Storage Legacy Bucket Writer** + **Storage Object Creator**
2. Click **CONTINUE**
3. Skip **Grant users access to this service account** (optional)
4. Click **DONE**

### Step 3: Create and Download Key
1. Find your new service account in the list
2. Click on the service account name
3. Go to the **KEYS** tab
4. Click **ADD KEY** → **Create new key**
5. Choose **JSON** format
6. Click **CREATE**
7. The key file will download automatically

## Option 2: Using gcloud CLI

### Prerequisites
```bash
# Install gcloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Set your project (replace with your actual project ID)
gcloud config set project YOUR_PROJECT_ID
```

### Create Service Account and Key
```bash
# Set variables
PROJECT_ID="YOUR_PROJECT_ID"  # Replace with your actual project ID
SA_NAME="levante-dashboard-writer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
BUCKET_NAME="levante-dashboard-dev"

# Create service account
gcloud iam service-accounts create ${SA_NAME} \
    --display-name="Levante Dashboard Writer" \
    --description="Service account for writing to levante-dashboard-dev bucket"

# Grant bucket-specific permissions (recommended)
gsutil iam ch serviceAccount:${SA_EMAIL}:objectAdmin gs://${BUCKET_NAME}

# Alternative: Grant broader Storage Object Admin role (if bucket-specific doesn't work)
# gcloud projects add-iam-policy-binding ${PROJECT_ID} \
#     --member="serviceAccount:${SA_EMAIL}" \
#     --role="roles/storage.objectAdmin"

# Create and download key
gcloud iam service-accounts keys create levante-dashboard-service-account.json \
    --iam-account=${SA_EMAIL}

echo "✅ Service account created and key saved to: levante-dashboard-service-account.json"
echo "📧 Service account email: ${SA_EMAIL}"
```

## Option 3: Minimal Permissions (Most Secure)

If you want to grant only the minimum required permissions:

```bash
# Grant only specific bucket permissions
gsutil iam ch serviceAccount:${SA_EMAIL}:roles/storage.legacyBucketWriter gs://${BUCKET_NAME}
gsutil iam ch serviceAccount:${SA_EMAIL}:roles/storage.objectCreator gs://${BUCKET_NAME}
gsutil iam ch serviceAccount:${SA_EMAIL}:roles/storage.objectViewer gs://${BUCKET_NAME}
```

## Verification

Test the service account permissions:

```bash
# Set the key as your default credentials
export GOOGLE_APPLICATION_CREDENTIALS="./levante-dashboard-service-account.json"

# Test bucket access
gsutil ls gs://levante-dashboard-dev

# Test write permissions (upload a test file)
echo "test" > test-file.txt
gsutil cp test-file.txt gs://levante-dashboard-dev/test-upload.txt
gsutil rm gs://levante-dashboard-dev/test-upload.txt
rm test-file.txt

echo "✅ Service account has write access to the bucket!"
```

## Using with the Crowdin Downloader

Once you have the service account key:

```bash
# Set environment variable for the Crowdin to GCS tool
export GOOGLE_APPLICATION_CREDENTIALS_JSON="$(cat levante-dashboard-service-account.json)"

# Or set the file path (alternative method)
export GOOGLE_APPLICATION_CREDENTIALS="./levante-dashboard-service-account.json"

# Test the Crowdin downloader
python utilities/crowdin_to_gcs.py --dry-run
```

## Security Best Practices

1. **Store securely**: Never commit the JSON key to version control
2. **Rotate keys**: Regularly rotate service account keys
3. **Minimum permissions**: Only grant the permissions actually needed
4. **Monitor usage**: Monitor service account usage in Cloud Console
5. **Delete unused keys**: Remove old or unused service account keys

## Environment Variables for Different Environments

### For Development
```bash
export GOOGLE_APPLICATION_CREDENTIALS="./levante-dashboard-service-account.json"
```

### For Production/CI
```bash
# Store the entire JSON content as an environment variable
export GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account","project_id":"..."}'
```

## Troubleshooting

### Common Issues

1. **"Access Denied" errors**:
   - Verify the service account has the correct permissions
   - Check that you're using the right project and bucket name

2. **"Bucket not found"**:
   - Verify the bucket name is correct: `levante-dashboard-dev`
   - Ensure the bucket exists in your project

3. **"Invalid credentials"**:
   - Check the JSON key file is valid and complete
   - Verify the service account hasn't been deleted

### Testing Commands

```bash
# Check current authentication
gcloud auth list

# Test bucket existence
gsutil ls gs://levante-dashboard-dev

# Check bucket permissions
gsutil iam get gs://levante-dashboard-dev
```