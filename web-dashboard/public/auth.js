/**
 * Firebase Authentication Module for Levante Dashboard
 * Handles superadmin authentication and role verification
 */

class AuthManager {
    constructor() {
        this.firebase = null;
        this.auth = null;
        this.db = null;
        this.currentUser = null;
        this.isSuperadmin = false;
        
        // Firebase configuration - loaded from external config
        this.firebaseConfig = window.FIREBASE_CONFIG || {
            apiKey: "your-api-key",
            authDomain: "your-project.firebaseapp.com",
            projectId: "your-project-id",
            storageBucket: "your-project.appspot.com",
            messagingSenderId: "123456789",
            appId: "your-app-id"
        };
        
        this.init();
    }

    async init() {
        try {
            console.log('🔐 Initializing authentication system...');
            
            // Show login screen by default
            this.showLogin();
            
            // Initialize Firebase
            this.firebase = firebase;
            this.firebase.initializeApp(this.firebaseConfig);
            this.auth = this.firebase.auth();
            this.db = this.firebase.firestore();
            
            console.log('✅ Firebase initialized successfully');
            
            // Set up auth state listener
            this.auth.onAuthStateChanged((user) => {
                console.log('🔄 Auth state changed:', user ? 'User logged in' : 'User logged out');
                this.handleAuthStateChange(user);
            });
            
            // Set up UI event listeners
            this.setupEventListeners();
            
        } catch (error) {
            console.error('❌ Firebase initialization error:', error);
            this.showError('Failed to initialize authentication system');
        }
    }

    setupEventListeners() {
        // Login form submission
        const authForm = document.getElementById('authForm');
        if (authForm) {
            authForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleLogin();
            });
        }

        // SSO Login buttons
        const googleLoginBtn = document.getElementById('googleLoginBtn');
        if (googleLoginBtn) {
            googleLoginBtn.addEventListener('click', () => {
                this.handleGoogleLogin();
            });
        }

        const microsoftLoginBtn = document.getElementById('microsoftLoginBtn');
        if (microsoftLoginBtn) {
            microsoftLoginBtn.addEventListener('click', () => {
                this.handleMicrosoftLogin();
            });
        }

        // Logout button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                this.handleLogout();
            });
        }
    }

    async handleAuthStateChange(user) {
        if (user) {
            this.currentUser = user;
            console.log('User authenticated:', user.email);
            
            // Check if user is superadmin
            this.isSuperadmin = await this.checkSuperadminRole(user.uid);
            
            if (this.isSuperadmin) {
                this.showDashboard();
            } else {
                this.showError('Access denied. Superadmin privileges required.');
                await this.auth.signOut();
            }
        } else {
            this.currentUser = null;
            this.isSuperadmin = false;
            this.showLogin();
        }
    }

    async checkSuperadminRole(uid) {
        try {
            // First check if email is in the hardcoded superadmin list
            if (window.SUPERADMIN_EMAILS && window.SUPERADMIN_EMAILS.includes(this.currentUser.email)) {
                return true;
            }
            
            // Then check Firestore for user role
            const userDoc = await this.db.collection('users').doc(uid).get();
            
            if (userDoc.exists) {
                const userData = userDoc.data();
                return userData.role === 'superadmin' || userData.isSuperadmin === true;
            }
            
            // If no user document exists, check if email is in superadmin collection
            const superadminDoc = await this.db.collection('superadmins').doc(this.currentUser.email).get();
            return superadminDoc.exists;
            
        } catch (error) {
            console.error('Error checking superadmin role:', error);
            return false;
        }
    }

    async handleLogin() {
        const email = document.getElementById('emailInput').value;
        const password = document.getElementById('passwordInput').value;
        
        if (!email || !password) {
            this.showError('Please enter both email and password');
            return;
        }

        this.showLoading(true);
        this.clearMessages();

        try {
            await this.auth.signInWithEmailAndPassword(email, password);
            this.showSuccess('Authentication successful!');
        } catch (error) {
            console.error('Login error:', error);
            this.showError(this.getErrorMessage(error));
        } finally {
            this.showLoading(false);
        }
    }

    async handleGoogleLogin() {
        this.showLoading(true);
        this.clearMessages();

        try {
            const provider = new this.firebase.auth.GoogleAuthProvider();
            // Add additional scopes if needed
            provider.addScope('email');
            provider.addScope('profile');
            
            await this.auth.signInWithPopup(provider);
            this.showSuccess('Google authentication successful!');
        } catch (error) {
            console.error('Google login error:', error);
            this.showError(this.getErrorMessage(error));
        } finally {
            this.showLoading(false);
        }
    }

    async handleMicrosoftLogin() {
        this.showLoading(true);
        this.clearMessages();

        try {
            const provider = new this.firebase.auth.OAuthProvider('microsoft.com');
            provider.addScope('email');
            provider.addScope('profile');
            
            await this.auth.signInWithPopup(provider);
            this.showSuccess('Microsoft authentication successful!');
        } catch (error) {
            console.error('Microsoft login error:', error);
            this.showError(this.getErrorMessage(error));
        } finally {
            this.showLoading(false);
        }
    }

    async handleLogout() {
        try {
            await this.auth.signOut();
            this.showLogin();
        } catch (error) {
            console.error('Logout error:', error);
            this.showError('Error during logout');
        }
    }

    showLogin() {
        console.log('🔑 Showing login screen...');
        const authContainer = document.getElementById('authContainer');
        const dashboardContainer = document.querySelector('.dashboard-container');
        const userInfo = document.getElementById('userInfo');
        
        console.log('Auth container found:', !!authContainer);
        console.log('Dashboard container found:', !!dashboardContainer);
        console.log('User info found:', !!userInfo);
        
        if (authContainer) {
            authContainer.style.display = 'block';
            console.log('✅ Auth container shown');
        } else {
            console.error('❌ Auth container not found!');
        }
        if (dashboardContainer) dashboardContainer.style.display = 'none';
        if (userInfo) userInfo.style.display = 'none';
    }

    showDashboard() {
        const authContainer = document.getElementById('authContainer');
        const dashboardContainer = document.querySelector('.dashboard-container');
        const userInfo = document.getElementById('userInfo');
        const userName = document.getElementById('userName');
        
        if (authContainer) authContainer.style.display = 'none';
        if (dashboardContainer) dashboardContainer.style.display = 'block';
        if (userInfo) userInfo.style.display = 'flex';
        if (userName) userName.textContent = this.currentUser.email;
        
        // Clear login form
        document.getElementById('emailInput').value = '';
        document.getElementById('passwordInput').value = '';
        this.clearMessages();
        
        // Initialize dashboard if not already initialized
        if (!window.dashboardInstance) {
            console.log('Initializing dashboard after authentication...');
            window.dashboardInstance = new Dashboard();
        }
    }

    showLoading(show) {
        const loading = document.getElementById('authLoading');
        const loginBtn = document.getElementById('loginBtn');
        
        if (loading) loading.style.display = show ? 'block' : 'none';
        if (loginBtn) loginBtn.disabled = show;
    }

    showError(message) {
        const errorDiv = document.getElementById('authError');
        const successDiv = document.getElementById('authSuccess');
        
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
        }
        if (successDiv) successDiv.style.display = 'none';
    }

    showSuccess(message) {
        const successDiv = document.getElementById('authSuccess');
        const errorDiv = document.getElementById('authError');
        
        if (successDiv) {
            successDiv.textContent = message;
            successDiv.style.display = 'block';
        }
        if (errorDiv) errorDiv.style.display = 'none';
    }

    clearMessages() {
        const errorDiv = document.getElementById('authError');
        const successDiv = document.getElementById('authSuccess');
        
        if (errorDiv) errorDiv.style.display = 'none';
        if (successDiv) successDiv.style.display = 'none';
    }

    getErrorMessage(error) {
        switch (error.code) {
            case 'auth/user-not-found':
                return 'No account found with this email address';
            case 'auth/wrong-password':
                return 'Incorrect password';
            case 'auth/invalid-email':
                return 'Invalid email address';
            case 'auth/user-disabled':
                return 'This account has been disabled';
            case 'auth/too-many-requests':
                return 'Too many failed attempts. Please try again later';
            default:
                return 'Authentication failed. Please check your credentials';
        }
    }

    // Public methods for other modules to check auth status
    isAuthenticated() {
        return this.currentUser !== null && this.isSuperadmin;
    }

    getCurrentUser() {
        return this.currentUser;
    }

    // Method to protect API calls
    async makeAuthenticatedRequest(url, options = {}) {
        if (!this.isAuthenticated()) {
            throw new Error('User not authenticated');
        }

        const token = await this.currentUser.getIdToken();
        
        return fetch(url, {
            ...options,
            headers: {
                ...options.headers,
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
    }
}

// Initialize auth manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.authManager = new AuthManager();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuthManager;
}
