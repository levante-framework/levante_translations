# Crowdin to Google Cloud Storage (GCS) Downloader

This utility downloads translation files from Crowdin and uploads them to appropriate Google Cloud Storage dev buckets for the LEVANTE project.

## 🔧 Features

- **Automated Download**: Downloads translation bundles from Crowdin using their official API
- **Smart Organization**: Automatically organizes files by task type for appropriate bucket placement
- **GCS Integration**: Uploads files to the correct dev buckets based on task configuration
- **Error Handling**: Comprehensive error handling and logging throughout the process
- **Dry Run Mode**: Test the workflow without actually uploading files
- **CLI Interface**: Easy-to-use command-line interface with helpful options

## 📋 Prerequisites

### Dependencies

Install the required Python packages:

```bash
pip install crowdin-api-client>=1.24.0 google-cloud-storage>=2.10.0
```

Or install from the project requirements:

```bash
pip install -r requirements.txt
```

### Credentials

You'll need the following credentials:

1. **Crowdin API Token**: Get from your Crowdin project settings
2. **Crowdin Project ID**: Your Crowdin project identifier  
3. **Google Cloud Credentials**: Service account JSON for GCS access

## 🚀 Quick Start

### 1. Set Environment Variables

```bash
export CROWDIN_TOKEN='your_crowdin_api_token_here'
export CROWDIN_PROJECT_ID='your_project_id_here'
export GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'
```

### 2. Basic Usage

```bash
# Download and upload to dev buckets
python utilities/crowdin_to_gcs.py

# Test run without uploading (recommended first time)
python utilities/crowdin_to_gcs.py --dry-run

# Use specific bundle ID
python utilities/crowdin_to_gcs.py --bundle-id 18
```

### 3. Advanced Options

```bash
# Full command with all options
python utilities/crowdin_to_gcs.py \
    --bundle-id 18 \
    --crowdin-token "your_token" \
    --crowdin-project-id "12345" \
    --dry-run
```

## 📁 How It Works

### Workflow Overview

1. **Connect to Crowdin**: Uses the Crowdin API client to authenticate
2. **Build Bundle**: Triggers a build of the specified bundle (default: 18)
3. **Download**: Downloads the built bundle as a ZIP file
4. **Extract**: Extracts all files to a temporary directory
5. **Organize**: Analyzes file paths to determine which task they belong to
6. **Upload**: Uploads files to the appropriate GCS dev buckets
7. **Cleanup**: Removes temporary files

### File Organization Logic

The system automatically determines which GCS bucket to use based on:

- **File path analysis**: Looks for task names in the directory structure
- **Task mapping**: Maps to configured bucket names from `utilities/buckets.py`
- **Fallback**: Files that don't match specific tasks go to the 'shared' bucket

### GCS Bucket Structure

Files are uploaded with the following structure:
```
gs://bucket-name/crowdin_downloads/YYYYMMDD_HHMMSS/original/file/path.ext
```

## 🎯 Task to Bucket Mapping

The system maps files to these dev buckets:

| Task | Bucket Name |
|------|-------------|
| vocab | levante-vocabulary-dev |
| intro | levante-intro-dev |
| memorygame | levante-memory-dev |
| egmamath | levante-math-dev |
| shared | levante-tasks-shared-dev |
| ... | (see `utilities/buckets.py` for complete list) |

## ⚙️ Configuration

### Bundle Configuration

The default bundle ID (18) is defined in `crowdin.yml`:

```yaml
bundles:
  - 18
```

### Bucket Configuration

Bucket mappings are configured in `utilities/buckets.py`. To add new tasks or modify bucket names, update the configuration there.

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CROWDIN_TOKEN` | Crowdin API token | Yes |
| `CROWDIN_PROJECT_ID` | Crowdin project ID | Yes |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | GCS service account JSON | Yes |

## 🔍 Troubleshooting

### Common Issues

1. **"Crowdin credentials required"**
   - Set the `CROWDIN_TOKEN` and `CROWDIN_PROJECT_ID` environment variables
   - Verify your Crowdin API token has the necessary permissions

2. **"Failed to initialize GCS client"**
   - Check your `GOOGLE_APPLICATION_CREDENTIALS_JSON` environment variable
   - Ensure the service account has `Storage Object Admin` permissions

3. **"Bundle build failed"**
   - Verify the bundle ID exists in your Crowdin project
   - Check that the bundle has translatable content

4. **"No bucket configured"**
   - The file path couldn't be mapped to a known task
   - Files will be uploaded to the 'shared' bucket as fallback

### Debug Mode

For detailed output, the script provides extensive logging:

```bash
python utilities/crowdin_to_gcs.py --dry-run  # See what would happen
```

## 📊 Example Output

```
✅ Initialized CrowdinToGCS
   Crowdin Project ID: 12345
   Bundle ID: 18
   GCS Client: ✅ Ready

📥 Starting bundle download from Crowdin...
🔨 Building bundle...
   Build ID: 67890
⏳ Waiting for build completion...
   Status: finished (attempt 3/30)
💾 Downloading bundle...
✅ Bundle downloaded successfully!
   Size: 1,234,567 bytes

📂 Extracting bundle...
✅ Extracted 145 files

🗂️  Organizing files by task...
✅ Organized files by task:
   vocab: 45 files → levante-vocabulary-dev
   intro: 23 files → levante-intro-dev
   shared: 77 files → levante-tasks-shared-dev

☁️  Starting upload to GCS buckets...
📤 Uploading 45 files to levante-vocabulary-dev...
✅ vocab: uploaded 45 files

🎉 Workflow completed successfully!
   Total files uploaded: 145
   Tasks processed: 3
```

## 🔐 Security Notes

- **Credentials**: Never commit API tokens or credentials to version control
- **Permissions**: Use principle of least privilege for GCS service accounts
- **Cleanup**: Temporary files are automatically cleaned up after processing

## 🤝 Integration

### With CI/CD

You can integrate this into your CI/CD pipeline:

```yaml
# Example GitHub Actions step
- name: Download Crowdin translations
  env:
    CROWDIN_TOKEN: ${{ secrets.CROWDIN_TOKEN }}
    CROWDIN_PROJECT_ID: ${{ secrets.CROWDIN_PROJECT_ID }}
    GOOGLE_APPLICATION_CREDENTIALS_JSON: ${{ secrets.GCS_CREDENTIALS }}
  run: python utilities/crowdin_to_gcs.py
```

### Programmatic Usage

```python
from utilities.crowdin_to_gcs import CrowdinToGCS

# Initialize
downloader = CrowdinToGCS(
    crowdin_token="your_token",
    crowdin_project_id="12345",
    bundle_id=18
)

# Download and upload
results = downloader.download_and_upload()
print(f"Uploaded files: {sum(results.values())}")
```

## 📝 License

This tool is part of the LEVANTE project and follows the same licensing terms.