#!/bin/bash
# Deploy PR branch (partner-tool-alpha) to production
# Updates levante-partner-tools.vercel.app with latest changes

set -e

echo "🚀 Deploying PR branch to production..."
echo ""

# Check we're on the right branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

if [ "$CURRENT_BRANCH" != "partner-tool-alpha" ]; then
    echo "⚠️  Warning: Not on partner-tool-alpha branch"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Deploy to production
echo ""
echo "📦 Deploying to Vercel production..."
if [ ! -d "../levante-web-dashboard" ]; then
    echo "❌ Sibling repo not found: ../levante-web-dashboard"
    exit 1
fi
cd ../levante-web-dashboard
DEPLOY_OUTPUT=$(vercel --prod --yes 2>&1)
echo "$DEPLOY_OUTPUT"

# Extract deployment URL
DEPLOYMENT_URL=$(echo "$DEPLOY_OUTPUT" | grep -oE 'https://[a-zA-Z0-9.-]+\.vercel\.app' | tail -1)

if [ -z "$DEPLOYMENT_URL" ]; then
    echo "❌ Could not extract deployment URL"
    echo "Deploy output:"
    echo "$DEPLOY_OUTPUT"
    exit 1
fi

echo ""
echo "✅ Deployment successful: $DEPLOYMENT_URL"
echo ""

# Update production alias
echo "🔗 Updating production alias..."
vercel alias set "$DEPLOYMENT_URL" levante-partner-tools.vercel.app

echo ""
echo "🎉 Production deployment complete!"
echo ""
echo "🌐 Production URL: https://levante-partner-tools.vercel.app/audio-approval.html"
echo "📦 Deployment URL: $DEPLOYMENT_URL"
echo ""
echo "✨ All latest changes from PR #65 are now live in production!"

