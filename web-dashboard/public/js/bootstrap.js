document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
    loadCredentials();
    initLanguageConfigApp();
});

function loadRemoteLanguagesIntoConfig() {
    (async () => {
        try {
            const resp = await fetch('/api/language-config');
            if (!resp.ok) return;
            const data = await resp.json();
            if (data && data.languages && typeof data.languages === 'object') {
                window.CONFIG = window.CONFIG || {};
                window.CONFIG.languages = data.languages;
                console.log('Loaded languages from remote language_config.json');
            } else {
                console.log('No remote language_config.json found; using local config.js');
            }
        } catch (e) {
            console.log('Failed to load remote language_config.json; using local config.js');
        }
    })();
}
loadRemoteLanguagesIntoConfig();

// Global click handler to close modals when clicking outside
window.onclick = function(event) {
    const credentialsModal = document.getElementById('credentialsModal');
    const audioInfoModal = document.getElementById('audioInfoModal');
    if (event.target === credentialsModal) {
        closeCredentialsModal();
    }
    if (event.target === audioInfoModal) {
        closeAudioInfoModal();
    }
};
