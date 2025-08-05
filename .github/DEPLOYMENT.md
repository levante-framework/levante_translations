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
2. **Deploys to Dev**: Deploys to `levante-dashboard-dev` for testing (production requires manual deployment)
3. **Triggers E2E Tests**: Automatically triggers Cypress e2e tests in the `core-tasks` repository against dev environment

## Required Secrets

To enable automatic deployment and e2e test triggering, you need to set up credentials as GitHub secrets.

### For Deployment: Google Cloud Service Account

#### Step 1: Create Google Cloud Service Account
If you don't have a service account yet, follow the guide in [`create_dashboard_service_account.md`](../create_dashboard_service_account.md) to create one with the proper permissions.

#### Step 2: Add Deployment Secrets

**`GOOGLE_APPLICATION_CREDENTIALS_JSON_DEV`** (for dev deployments)
**`GOOGLE_APPLICATION_CREDENTIALS_JSON_PROD`** (for production deployments)
The complete JSON content of your Google Cloud service account key.

### For E2E Test Triggering: GitHub App (Recommended)

**GitHub App Secrets** (for triggering core-tasks tests)
- **`GITHUB_APP_ID`**: Your GitHub App's ID number
- **`GITHUB_APP_PRIVATE_KEY`**: The private key (.pem file contents)

**Alternative: Personal Access Token (Fallback)**
- **`REPO_DISPATCH_TOKEN`**: A GitHub PAT with `repo` scope

**To add these secrets:**
1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Add each secret:
   - **Name**: `GOOGLE_APPLICATION_CREDENTIALS_JSON_DEV` / `GOOGLE_APPLICATION_CREDENTIALS_JSON_PROD`
   - **Value**: Paste the entire JSON content of your service account key file
   - **Name**: `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY`
   - **Value**: Your GitHub App credentials (see below for setup)
   - **Name**: `REPO_DISPATCH_TOKEN` (optional fallback)
   - **Value**: Your GitHub Personal Access Token

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

#### Setting up GitHub App (Recommended)

1. **Create GitHub App** (Organization admin required):
   - Go to Organization → **Settings** → **Developer settings** → **GitHub Apps**
   - **New GitHub App** with these settings:
     - **Name**: "Levante Workflow Automation"
     - **Repository permissions**: Actions (Read & write), Contents (Read), Metadata (Read)
     - **Install on**: `levante_translations` and `core-tasks` repositories

2. **Generate Private Key**:
   - In the GitHub App settings → **Generate a private key**
   - Download the `.pem` file

3. **Add to Repository Secrets**:
   - **`GITHUB_APP_ID`**: The App ID from the GitHub App settings page
   - **`GITHUB_APP_PRIVATE_KEY`**: Complete contents of the `.pem` file

#### Alternative: Personal Access Token (Fallback)

If you prefer not to use a GitHub App:
1. **Create PAT**: GitHub → Settings → Developer settings → Personal access tokens
2. **Scopes**: Select `repo` (Full control of private repositories)  
3. **Add Secret**: `REPO_DISPATCH_TOKEN` with the PAT value

**Note**: GitHub App is more secure and team-friendly than PATs.

## Workflow Behavior

### With All Secrets Configured
- ✅ Full deployment automation
- ✅ PR deploys to dev bucket for testing
- ✅ Main branch deploys to dev bucket and triggers e2e tests
- ✅ Production deployment requires manual trigger
- ✅ All tests run

### With Partial Configuration
- ✅ All tests still run (with mock credentials)
- ⚠️ Missing deployment secrets: deployment steps are skipped
- ⚠️ Missing REPO_DISPATCH_TOKEN: e2e test triggering is skipped
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

**"Repository dispatch failed"**
- Ensure `REPO_DISPATCH_TOKEN` secret is set correctly
- Verify the token has `repo` scope
- Check that the token owner has access to the `core-tasks` repository

### Debug Steps
1. Check the workflow logs in GitHub Actions
2. Test deployments locally with `npm run deploy:levante-dev-dry`
3. Verify bucket permissions with `gsutil ls gs://levante-dashboard-dev`