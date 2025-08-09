// Import functions from other modules
import { loadCredentials } from './credentials.js';
import { closeCredentialsModal } from './credentials.js';
/**
 * Initializes the dashboard after DOM content is loaded
 */
document.addEventListener('DOMContentLoaded', () => {
    // Create the global dashboard instance using the global class
    const DashboardClass = window.Dashboard;
    if (DashboardClass) {
        window.dashboard = new DashboardClass();
    }
    else {
        console.error('Dashboard class not found');
    }
    /**
     * Waits for modals to load before initializing credentials and language config
     */
    function initializeAfterModals() {
        const credentialsModal = document.getElementById('credentialsModal');
        if (credentialsModal) {
            loadCredentials();
            // Call initLanguageConfigApp if it exists
            if (typeof initLanguageConfigApp === 'function') {
                initLanguageConfigApp();
            }
        }
        else {
            // Retry in 50ms if modals aren't loaded yet
            setTimeout(initializeAfterModals, 50);
        }
    }
    // Start initialization after a brief delay
    setTimeout(initializeAfterModals, 100);
});
/**
 * Loads remote language configuration from the API
 */
async function loadRemoteLanguagesIntoConfig() {
    try {
        const response = await fetch('/api/language-config');
        if (!response.ok) {
            console.log('No remote language_config.json found; using local config.js');
            return;
        }
        const data = await response.json();
        if (data && data.languages && typeof data.languages === 'object') {
            const windowAny = window;
            windowAny.CONFIG = windowAny.CONFIG || {};
            windowAny.CONFIG.languages = data.languages;
            console.log('Loaded languages from remote language_config.json');
        }
        else {
            console.log('Invalid language config format; using local config.js');
        }
    }
    catch (error) {
        console.log('Failed to load remote language_config.json; using local config.js');
    }
}
// Load remote configuration immediately
loadRemoteLanguagesIntoConfig();
/**
 * Global click handler to close modals when clicking outside them
 */
window.onclick = function (event) {
    const target = event.target;
    if (!target)
        return;
    const credentialsModal = document.getElementById('credentialsModal');
    const audioInfoModal = document.getElementById('audioInfoModal');
    if (target === credentialsModal) {
        closeCredentialsModal();
    }
    else if (target === audioInfoModal) {
        closeAudioInfoModal();
    }
};
// Export for module system
export { loadRemoteLanguagesIntoConfig };
//# sourceMappingURL=bootstrap.js.map