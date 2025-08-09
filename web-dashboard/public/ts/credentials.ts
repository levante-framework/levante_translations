// Import types from utils module
import type { Credentials } from './utils.js';
import { updateValidationAvailability } from './utils.js';

// DOM element IDs for type safety
const CREDENTIAL_ELEMENT_IDS = {
    modal: 'credentialsModal',
    playhtApiKey: 'playhtApiKey',
    playhtUserId: 'playhtUserId',
    elevenlabsApiKey: 'elevenlabsApiKey',
    googleTranslateApiKey: 'googleTranslateApiKey'
} as const;

/**
 * Type-safe helper to get credential input element
 */
function getCredentialInput(id: string): HTMLInputElement | null {
    const element = document.getElementById(id);
    return element instanceof HTMLInputElement ? element : null;
}

/**
 * Type-safe helper to get modal element
 */
function getModal(): HTMLElement | null {
    return document.getElementById(CREDENTIAL_ELEMENT_IDS.modal);
}

/**
 * Opens the credentials modal and loads existing credentials
 */
function openCredentialsModal(): void {
    const modal = getModal();
    if (!modal) {
        console.error('Credentials modal not found');
        return;
    }
    
    modal.style.display = 'block';
    loadCredentials();
}

/**
 * Closes the credentials modal
 */
function closeCredentialsModal(): void {
    const modal = getModal();
    if (!modal) {
        console.error('Credentials modal not found');
        return;
    }
    
    modal.style.display = 'none';
}

/**
 * Saves credentials from form inputs to localStorage
 */
function saveCredentials(): void {
    const playhtApiKeyInput = getCredentialInput(CREDENTIAL_ELEMENT_IDS.playhtApiKey);
    const playhtUserIdInput = getCredentialInput(CREDENTIAL_ELEMENT_IDS.playhtUserId);
    const elevenlabsApiKeyInput = getCredentialInput(CREDENTIAL_ELEMENT_IDS.elevenlabsApiKey);
    const googleTranslateApiKeyInput = getCredentialInput(CREDENTIAL_ELEMENT_IDS.googleTranslateApiKey);
    
    if (!playhtApiKeyInput || !playhtUserIdInput || !elevenlabsApiKeyInput || !googleTranslateApiKeyInput) {
        alert('Error: Could not find all credential input fields');
        return;
    }
    
    const credentials: Credentials = {
        playhtApiKey: playhtApiKeyInput.value.trim() || undefined,
        playhtUserId: playhtUserIdInput.value.trim() || undefined,
        elevenlabsApiKey: elevenlabsApiKeyInput.value.trim() || undefined,
        googleTranslateApiKey: googleTranslateApiKeyInput.value.trim() || undefined
    };
    
    try {
        localStorage.setItem('levante_credentials', JSON.stringify(credentials));
        alert('Credentials saved successfully!');
        updateValidationAvailability(!!credentials.googleTranslateApiKey);
    } catch (error) {
        console.error('Error saving credentials:', error);
        alert('Error saving credentials. Please try again.');
    }
}

/**
 * Loads credentials from localStorage and populates form inputs
 */
function loadCredentials(): void {
    try {
        const storedData = localStorage.getItem('levante_credentials');
        const credentials: Credentials = storedData ? JSON.parse(storedData) : {};
        
        // Type-safe element retrieval with null checks
        const elements = {
            playhtApiKey: getCredentialInput(CREDENTIAL_ELEMENT_IDS.playhtApiKey),
            playhtUserId: getCredentialInput(CREDENTIAL_ELEMENT_IDS.playhtUserId),
            elevenlabsApiKey: getCredentialInput(CREDENTIAL_ELEMENT_IDS.elevenlabsApiKey),
            googleTranslateApiKey: getCredentialInput(CREDENTIAL_ELEMENT_IDS.googleTranslateApiKey)
        };
        
        // Safely set values only if elements exist
        if (elements.playhtApiKey) {
            elements.playhtApiKey.value = credentials.playhtApiKey || '';
        }
        if (elements.playhtUserId) {
            elements.playhtUserId.value = credentials.playhtUserId || '';
        }
        if (elements.elevenlabsApiKey) {
            elements.elevenlabsApiKey.value = credentials.elevenlabsApiKey || '';
        }
        if (elements.googleTranslateApiKey) {
            elements.googleTranslateApiKey.value = credentials.googleTranslateApiKey || '';
        }
        
        updateValidationAvailability(!!credentials.googleTranslateApiKey);
        
    } catch (error) {
        console.error('Error loading credentials:', error);
    }
}

/**
 * Clears all stored credentials after user confirmation
 */
function clearCredentials(): void {
    if (!confirm('Are you sure you want to clear all credentials?')) {
        return;
    }
    
    try {
        localStorage.removeItem('levante_credentials');
        
        // Clear form inputs
        const inputs = [
            getCredentialInput(CREDENTIAL_ELEMENT_IDS.playhtApiKey),
            getCredentialInput(CREDENTIAL_ELEMENT_IDS.playhtUserId),
            getCredentialInput(CREDENTIAL_ELEMENT_IDS.elevenlabsApiKey),
            getCredentialInput(CREDENTIAL_ELEMENT_IDS.googleTranslateApiKey)
        ];
        
        inputs.forEach(input => {
            if (input) {
                input.value = '';
            }
        });
        
        updateValidationAvailability(false);
        alert('All credentials cleared.');
        
    } catch (error) {
        console.error('Error clearing credentials:', error);
        alert('Error clearing credentials. Please try again.');
    }
}

// Export functions for use in other modules
export {
    openCredentialsModal,
    closeCredentialsModal,
    saveCredentials,
    loadCredentials,
    clearCredentials
};
