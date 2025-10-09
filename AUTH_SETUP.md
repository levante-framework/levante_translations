# Levante Dashboard Authentication Setup

This document explains how to set up Firebase authentication for the Levante Translation & Audio Dashboard using the existing `hs-levante-admin-dev` Firebase project.

## Overview

The dashboard now requires superadmin authentication to access. Users must:
1. Have a Firebase account in the `hs-levante-admin-dev` project
2. Be listed as a superadmin (either in Firestore or hardcoded list)
3. Sign in with their credentials (Email/Password, Google SSO, or Microsoft SSO)

## Setup Instructions

### 1. Firebase Project Configuration

The dashboard uses the existing `hs-levante-admin-dev` Firebase project. To configure:

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select the `hs-levante-admin-dev` project
3. Enable Authentication providers:
   - Go to Authentication > Sign-in method
   - Enable "Email/Password" provider
   - Enable "Google" provider (for SSO)
   - Enable "Microsoft" provider (for SSO)
4. Ensure Firestore Database is enabled:
   - Go to Firestore Database
   - Verify database exists and is accessible
5. Get your Firebase configuration:
   - Go to Project Settings > General
   - Scroll down to "Your apps" and find the web app
   - Copy the configuration object

### 2. Update Configuration Files

Edit `firebase-config.js` and replace the placeholder values:

```javascript
const FIREBASE_CONFIG = {
    apiKey: "your-actual-api-key",
    authDomain: "hs-levante-admin-dev.firebaseapp.com",
    projectId: "hs-levante-admin-dev",
    storageBucket: "hs-levante-admin-dev.appspot.com",
    messagingSenderId: "your-actual-sender-id",
    appId: "your-actual-app-id"
};

const SUPERADMIN_EMAILS = [
    "admin@levante.com",
    "superadmin@levante.com"
    // Add more superadmin emails here
];
```

### 3. Configure SSO Providers (Optional)

To enable Google and Microsoft SSO:

#### Google SSO Setup:
1. In Firebase Console, go to Authentication > Sign-in method
2. Click on "Google" provider
3. Enable the provider
4. Add your domain to authorized domains if needed

#### Microsoft SSO Setup:
1. In Firebase Console, go to Authentication > Sign-in method  
2. Click on "Microsoft" provider
3. Enable the provider
4. Configure OAuth settings with your Microsoft Azure app

### 4. Set Up Superadmin Users

You have two options for managing superadmin access:

#### Option A: Hardcoded Email List (Simpler)
Add superadmin emails to the `SUPERADMIN_EMAILS` array in `firebase-config.js`.

#### Option B: Firestore Database (More Flexible)
Create a Firestore collection called `superadmins` with documents for each superadmin:

```javascript
// Collection: superadmins
// Document ID: user@email.com
{
    email: "user@email.com",
    role: "superadmin",
    addedBy: "admin@email.com",
    addedAt: "2024-01-01T00:00:00Z"
}
```

Or create a `users` collection with user documents:

```javascript
// Collection: users
// Document ID: {user-uid}
{
    email: "user@email.com",
    role: "superadmin",
    isSuperadmin: true,
    createdAt: "2024-01-01T00:00:00Z"
}
```

### 4. Security Rules (Optional but Recommended)

Set up Firestore security rules to protect the superadmin collections:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Only authenticated users can read superadmin data
    match /superadmins/{email} {
      allow read: if request.auth != null && request.auth.token.email == email;
    }
    
    // Only superadmins can read user data
    match /users/{userId} {
      allow read: if request.auth != null && 
        (request.auth.token.email in get(/databases/$(database)/documents/superadmins/$(request.auth.token.email)).data ||
         request.auth.token.email in ['admin@yourcompany.com', 'superadmin@yourcompany.com']);
    }
  }
}
```

## How It Works

1. **Page Load**: Dashboard shows login modal
2. **Authentication**: User enters email/password
3. **Role Check**: System verifies user is superadmin
4. **Access Granted**: Dashboard becomes available
5. **Session Management**: User stays logged in until logout

## Features

- ✅ Firebase Authentication integration
- ✅ Superadmin role verification
- ✅ Secure session management
- ✅ Automatic logout on role change
- ✅ Protected API calls
- ✅ Clean login/logout UI
- ✅ Error handling and user feedback

## Troubleshooting

### Common Issues

1. **"Firebase initialization error"**
   - Check your Firebase configuration in `firebase-config.js`
   - Ensure all required fields are filled

2. **"Access denied. Superadmin privileges required"**
   - User is authenticated but not a superadmin
   - Add user email to `SUPERADMIN_EMAILS` or Firestore

3. **"Authentication failed"**
   - Check if user account exists in Firebase
   - Verify email/password are correct
   - Check if account is disabled

4. **Dashboard not loading after login**
   - Check browser console for JavaScript errors
   - Verify all script files are loaded correctly

### Debug Mode

To enable debug logging, add this to your browser console:

```javascript
localStorage.setItem('debug', 'true');
```

## Security Considerations

1. **Never commit Firebase config with real credentials to public repos**
2. **Use environment variables in production**
3. **Regularly audit superadmin access**
4. **Monitor authentication logs in Firebase Console**
5. **Consider implementing additional security measures like 2FA**

## Support

For issues or questions about the authentication system, check:
1. Browser console for error messages
2. Firebase Console for authentication logs
3. Network tab for failed API calls
