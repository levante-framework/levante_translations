#!/bin/bash
# Automatic deployment script for Levante Dashboard
# This script deploys to Vercel and aliases to production URLs

echo "🚀 Starting Levante Dashboard deployment..."

# Deploy to Vercel with production flag
echo "📦 Deploying to Vercel..."
DEPLOY_OUTPUT=$(vercel --prod --yes 2>&1)
echo "$DEPLOY_OUTPUT"

# Extract deployment URL from output (look for Production: line)
DEPLOYMENT_URL=$(echo "$DEPLOY_OUTPUT" | grep "Production:" | grep -o 'https://[^[:space:]]*' | head -1)

if [ -n "$DEPLOYMENT_URL" ]; then
    echo "✅ Deployment successful: $DEPLOYMENT_URL"
    
    # Alias to production URLs
    echo "🔗 Setting up production aliases..."
    vercel alias $DEPLOYMENT_URL levante-audio-dashboard.vercel.app
    vercel alias $DEPLOYMENT_URL audio-dashboard-levante.vercel.app
    
    echo "🎉 Production URLs updated:"
    echo "   Main: https://levante-audio-dashboard.vercel.app/"
    echo "   Alt:  https://audio-dashboard-levante.vercel.app/"
    echo "   New:  $DEPLOYMENT_URL"
else
    echo "❌ Deployment failed or URL not found"
    echo "Deploy output:"
    echo "$DEPLOY_OUTPUT"
    exit 1
fi

echo "✨ Deployment complete!"
