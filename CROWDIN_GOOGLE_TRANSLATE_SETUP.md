# Setting Up Google Translate in Crowdin

This guide explains how to configure Google Translate in your Crowdin project for machine translation.

## Quick Check

First, check if Google Translate is already configured:

```bash
export CROWDIN_API_TOKEN=your_token
export CROWDIN_PROJECT_ID=your_project_id
python3 check_crowdin_mt_config.py
```

## Manual Setup Steps

If Google Translate is not configured, follow these steps:

### 1. Get a Google Cloud API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Cloud Translation API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Cloud Translation API"
   - Click "Enable"
4. Create an API key:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy the API key (you'll need it in step 3)

### 2. Configure in Crowdin

1. Go to your Crowdin project dashboard
2. Navigate to **Settings** > **Machine Translation**
   - Direct URL: `https://crowdin.com/project/YOUR_PROJECT/settings/machine-translation`
3. Click **"Add Engine"** or **"Configure"**
4. Select **"Google Translate"** from the list
5. Enter your Google Cloud API key
6. Click **"Save"** or **"Add"**

### 3. Verify Configuration

Run the check script:

```bash
python3 check_crowdin_mt_config.py
```

You should see:
```
✅ Available Machine Translation Engines:
   • Google Translate (google)
     Type: google
     ✅ Google Translate is configured!
```

## Using Pre-Translate

Once configured, you can use the pre-translate script:

```bash
# Pre-translate Esperanto using Google Translate
python3 crowdin_pretranslate_esperanto.py

# Or for any other language
python3 crowdin_pretranslate_esperanto.py --lang pt-BR
```

## Troubleshooting

### "No machine translation engines configured"
- Make sure you've added Google Translate in Crowdin settings
- Verify you have the correct project permissions

### "Google Translate not found"
- Double-check that Google Translate was added successfully
- Try refreshing the Crowdin page and checking again

### API Errors
- Verify your Google Cloud API key is valid
- Check that Cloud Translation API is enabled in Google Cloud Console
- Ensure your API key has the necessary permissions

## Additional Resources

- [Crowdin Machine Translation Documentation](https://support.crowdin.com/project-settings/machine-translation/)
- [Google Cloud Translation API Documentation](https://cloud.google.com/translate/docs)

