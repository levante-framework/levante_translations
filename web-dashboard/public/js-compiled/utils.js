// Type definitions for the utilities module
/**
 * Retrieves stored credentials from localStorage
 * @returns {Credentials} The stored credentials object, or empty object if none found
 */
function getCredentials() {
    try {
        const stored = localStorage.getItem('levante_credentials');
        return stored ? JSON.parse(stored) : {};
    }
    catch (error) {
        console.error('Error parsing stored credentials:', error);
        return {};
    }
}
/**
 * Updates the availability/state of validation buttons based on API key presence
 * @param {boolean} hasGoogleTranslateKey - Whether Google Translate API key is available
 */
function updateValidationAvailability(hasGoogleTranslateKey) {
    const validateButtons = document.querySelectorAll('.validation-button');
    const validateBtns = document.querySelectorAll('.validate-btn');
    const enabledTitle = 'Validation enabled';
    const disabledTitle = 'Add Google Translate API key';
    const clickTitle = 'Click to validate';
    validateButtons.forEach((btn) => {
        btn.disabled = !hasGoogleTranslateKey;
        btn.title = hasGoogleTranslateKey ? enabledTitle : disabledTitle;
    });
    validateBtns.forEach((btn) => {
        btn.disabled = !hasGoogleTranslateKey;
        btn.title = hasGoogleTranslateKey ? clickTitle : disabledTitle;
    });
}
/**
 * Formats a byte count into human-readable file size
 * @param {number | null | undefined} bytes - The number of bytes
 * @returns {string} Formatted size string (e.g., "1.5 MB") or "N/A"
 */
function formatFileSize(bytes) {
    if (!bytes || bytes === 0)
        return 'N/A';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < sizes.length - 1) {
        size /= 1024;
        i++;
    }
    return `${size.toFixed(1)} ${sizes[i]}`;
}
/**
 * Formats a date string into localized date/time representation
 * @param {string | null | undefined} dateString - ISO date string or similar
 * @returns {string} Formatted date string or "N/A" if invalid
 */
function formatDate(dateString) {
    if (!dateString)
        return 'N/A';
    try {
        const date = new Date(dateString);
        // Check if date is valid
        if (isNaN(date.getTime())) {
            return dateString; // Return original if invalid
        }
        return date.toLocaleString();
    }
    catch (error) {
        console.warn('Error formatting date:', error);
        return dateString;
    }
}
/**
 * Clears the translation cache and reloads the page after user confirmation
 */
function clearCacheAndReload() {
    const message = 'Clear translation data cache and reload? This will fetch fresh data from GitHub.';
    if (confirm(message)) {
        console.log('🗑️ Clearing localStorage cache and reloading...');
        localStorage.removeItem('levante_translations_cache');
        alert('Cache cleared! Page will reload to fetch fresh data.');
        location.reload();
    }
}
export { getCredentials, updateValidationAvailability, formatFileSize, formatDate, clearCacheAndReload };
//# sourceMappingURL=utils.js.map