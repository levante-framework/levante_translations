# GitHub Actions Deployment

This document explains the automated deployment workflow and how to set it up.

## Workflow Overview

The `Deploy and Test` workflow automatically:

### On Pull Requests
1. **Tests**: Runs all dry-run tests to validate changes
2. **Validates**: Checks that required CSV files exist
3. **Deploys to Dev**: Automatically deploys to `levante-dashboard-dev` for testing (if credentials are available)

### On Main Branch Push
1. **Tests**: Runs the same validation tests
2. **Deploys to Production**: Deploys to `levante-dashboard-prod` after successful tests

## Required Secrets

To enable automatic deployment, you need to set up Google Cloud credentials and add them as a GitHub secret.

### Step 1: Create Google Cloud Service Account
If you don't have a service account yet, follow the guide in [`create_dashboard_service_account.md`](../create_dashboard_service_account.md) to create one with the proper permissions.

### Step 2: Add GitHub Secret

**`GOOGLE_APPLICATION_CREDENTIALS_JSON`**
The complete JSON content of your Google Cloud service account key.

**To add this secret:**
1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. **Name**: `GOOGLE_APPLICATION_CREDENTIALS_JSON`
4. **Value**: Paste the entire JSON content of your service account key file

Example JSON structure:
```json
{
  "type": "service_account",
  "project_id": "your-project",
  "private_key_id": "...",
  "private_key": "...",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "...",
  "token_uri": "...",
  "auth_provider_x509_cert_url": "...",
  "client_x509_cert_url": "..."
}
```

## Workflow Behavior

### With Secrets Configured
- ✅ Full deployment automation
- ✅ PR deploys to dev bucket for testing
- ✅ Main branch deploys to production
- ✅ All tests run

### Without Secrets
- ✅ All tests still run (with mock credentials)
- ⚠️ Deployment steps are skipped (continue-on-error)
- ✅ CI still passes for development

## Safety Features

### Security
- **Fork Protection**: Only deploys from the main repository, not forks
- **Branch Protection**: Production deploys only from main branch
- **Conditional Deployment**: Deployments only run if tests pass

### Error Handling
- **Graceful Failures**: Missing credentials don't break CI
- **Test Validation**: CSV files are checked before deployment
- **Clear Reporting**: Summary shows what actions were taken

## Manual Deployment

You can still deploy manually using npm scripts:

```bash
# Test first
npm run deploy:levante-dev-dry
npm run deploy:levante-prod-dry

# Deploy
npm run deploy:levante-dev
npm run deploy:levante-prod
```

## Extending the Workflow

To add more deployment targets or tests:

1. Add new npm scripts to `package.json`
2. Add corresponding steps to the workflow
3. Use appropriate `if` conditions for when they should run
4. Add any new secrets needed

## Troubleshooting

### Common Issues

**"Deployment failed"**
- Check that `GOOGLE_APPLICATION_CREDENTIALS_JSON` secret is set correctly
- Verify the service account has proper bucket permissions

**"CSV file missing"**
- Ensure `translation_text/item_bank_translations.csv` exists in the repository
- Check that the file is committed and pushed

**"Permission denied"**
- Verify the service account has `Storage Object Admin` role
- Check bucket names match the configured ones in `deploy_levante.py`

### Debug Steps
1. Check the workflow logs in GitHub Actions
2. Test deployments locally with `npm run deploy:levante-dev-dry`
3. Verify bucket permissions with `gsutil ls gs://levante-dashboard-dev`