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
3. **Triggers E2E Tests**: Automatically triggers Cypress e2e tests in the `core-tasks` repository

## Required Secrets

To enable automatic deployment and e2e test triggering, you need to set up credentials as GitHub secrets.

### For Deployment: Google Cloud Service Account

#### Step 1: Create Google Cloud Service Account
If you don't have a service account yet, follow the guide in [`create_dashboard_service_account.md`](../create_dashboard_service_account.md) to create one with the proper permissions.

#### Step 2: Add Deployment Secrets

**`GOOGLE_APPLICATION_CREDENTIALS_JSON_DEV`** (for dev deployments)
**`GOOGLE_APPLICATION_CREDENTIALS_JSON_PROD`** (for production deployments)
The complete JSON content of your Google Cloud service account key.

### For E2E Test Triggering: Repository Dispatch Token

**`REPO_DISPATCH_TOKEN`** (for triggering core-tasks tests)
A GitHub Personal Access Token with `repo` scope to trigger workflows in other repositories.

**To add these secrets:**
1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Add each secret:
   - **Name**: `GOOGLE_APPLICATION_CREDENTIALS_JSON_DEV` / `GOOGLE_APPLICATION_CREDENTIALS_JSON_PROD`
   - **Value**: Paste the entire JSON content of your service account key file
   - **Name**: `REPO_DISPATCH_TOKEN`
   - **Value**: Your GitHub Personal Access Token (see below for setup)

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

#### Setting up REPO_DISPATCH_TOKEN

1. **Create a Personal Access Token**:
   - Go to GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
   - Click **"Generate new token (classic)"**
   - **Note**: "Levante cross-repo workflows"
   - **Expiration**: Choose appropriate duration (90 days recommended)
   - **Scopes**: Select **`repo`** (Full control of private repositories)
   - Click **"Generate token"**
   - **Copy the token immediately** (you won't see it again)

2. **Add to Repository Secret**:
   - Name: `REPO_DISPATCH_TOKEN`
   - Value: The PAT you just created

**Note**: This token allows triggering workflows in the `core-tasks` repository. For team use, consider using a shared organization token or GitHub App instead of a personal token.

## Workflow Behavior

### With All Secrets Configured
- ✅ Full deployment automation
- ✅ PR deploys to dev bucket for testing
- ✅ Main branch deploys to production
- ✅ Main branch triggers core-tasks e2e tests
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