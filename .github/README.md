# .github Directory

This directory contains GitHub-specific configuration files and templates to improve project organization and collaboration.

## Contents

### Workflows (`.github/workflows/`)
- **`test-deployments.yml`**: GitHub Actions workflow that runs on PRs and pushes to test deployment scripts and validate npm scripts

### Issue Templates (`.github/ISSUE_TEMPLATE/`)
- **`bug_report.md`**: Template for reporting bugs with structured fields
- **`feature_request.md`**: Template for requesting new features

### Pull Request Template
- **`pull_request_template.md`**: Template for pull requests with checklists and component tracking

### Documentation
- **`CONTRIBUTING.md`**: Comprehensive guide for contributors including setup, workflow, and guidelines

## Benefits

✅ **Standardized Issues**: Consistent bug reports and feature requests  
✅ **Automated Testing**: CI/CD pipeline for testing deployments  
✅ **Clear PRs**: Structured pull request information  
✅ **Contributor Guide**: Easy onboarding for new contributors  
✅ **Quality Control**: Checklists ensure proper testing and documentation  

## GitHub Actions

The workflow automatically:
- Tests Python and Node.js dependencies
- Runs deployment dry-runs
- Validates npm scripts
- Ensures code quality on pull requests

This helps maintain code quality and prevents deployment issues before they reach production.