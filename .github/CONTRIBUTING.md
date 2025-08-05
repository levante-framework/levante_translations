# Contributing to Levante Translations

Thank you for your interest in contributing to the Levante Translations project! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+
- Git

### Setup
1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/levante_translations.git`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   npm install
   ```

## Development Workflow

### Making Changes
1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Test your changes: `npm run test:dry-run-all`
4. Commit your changes: `git commit -m "Description of changes"`
5. Push to your fork: `git push origin feature/your-feature-name`
6. Create a Pull Request

### NPM Scripts
Use the provided npm scripts for common tasks:

```bash
# Deployment testing
npm run deploy:levante-dev-dry
npm run deploy:crowdin-dry
npm run test:dry-run-all

# Audio generation
npm run generate:english
npm run generate:spanish
npm run generate:german

# Utilities
npm run fix:csv
npm run export:voices
npm run help
```

## Project Structure

```
levante_translations/
├── deploy_levante.py           # Levante dashboard deployment
├── generate_speech.py          # Main audio generation script
├── web-dashboard/             # Web dashboard application
├── utilities/                 # Utility scripts
│   ├── deploy_dashboard.py    # Advanced deployment
│   ├── crowdin_to_gcs.py     # Crowdin integration
│   ├── export_*.py           # Voice export tools
│   └── fix_*.py              # CSV utilities
├── commands/                  # Shell/batch command scripts
├── translation_text/          # Translation data
└── audio_files/              # Generated audio files
```

## Component Guidelines

### Audio Generation
- Use the voice mapping system in `PlayHt/voice_mapping.py`
- Follow the audio tags template in `utilities/utilities.py`
- Test with multiple languages

### Web Dashboard
- Deployed via Vercel (`web-dashboard/`)
- Use `npm run deploy:web` for deployment
- Test locally with `npm run start:web`

### Levante Dashboard
- Only deploys `itembank_translations.csv`
- Use `npm run deploy:levante-dev-dry` to test
- Target buckets: `levante-dashboard-dev/prod`

### Utilities
- Place utility scripts in `utilities/` folder
- Update `package.json` scripts for new utilities
- Include comprehensive error handling

## Code Style

### Python
- Use Python 3.9+ features
- Follow PEP 8 style guidelines
- Include docstrings for functions and classes
- Use type hints where appropriate

### JavaScript
- Use modern ES6+ features
- Follow consistent naming conventions
- Comment complex logic

### Documentation
- Update README.md for new features
- Include usage examples
- Update npm scripts documentation

## Testing

### Before Submitting
- [ ] Run `npm run test:dry-run-all`
- [ ] Test affected components locally
- [ ] Check that documentation is updated
- [ ] Verify npm scripts work correctly

### Deployment Testing
- Always test deployments with dry-run flags first
- Verify bucket permissions for new GCS features
- Test Vercel deployments in the web-dashboard directory

## Commit Messages

Use clear, descriptive commit messages:
- `feat: add new voice export utility`
- `fix: resolve CSV parsing issue with embedded newlines`
- `docs: update deployment instructions`
- `refactor: organize utility scripts in dedicated folder`

## Dependencies

### Adding New Dependencies

**Python:**
```bash
pip install new-package
pip freeze > requirements.txt
```

**Node.js:**
```bash
npm install new-package
# Update package.json automatically
```

### Common Dependencies
- **Python**: `google-cloud-storage`, `pandas`, `requests`, `mutagen`
- **Node.js**: `@google-cloud/storage` (for Vercel functions)

## Deployment

### Levante Dashboard
- Deploys only `itembank_translations.csv`
- Uses Google Cloud Storage buckets
- Test with: `npm run deploy:levante-dev-dry`

### Web Dashboard  
- Deployed via Vercel
- Includes API functions and static files
- Deploy with: `npm run deploy:web`

## Getting Help

- Check the README.md for usage instructions
- Review existing issues and PRs
- Use `npm run help` for available commands
- Create an issue for questions or problems

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.