interface Credentials {
    playhtApiKey?: string;
    playhtUserId?: string;
    elevenlabsApiKey?: string;
    googleTranslateApiKey?: string;
}
/**
 * Retrieves stored credentials from localStorage
 * @returns {Credentials} The stored credentials object, or empty object if none found
 */
declare function getCredentials(): Credentials;
/**
 * Updates the availability/state of validation buttons based on API key presence
 * @param {boolean} hasGoogleTranslateKey - Whether Google Translate API key is available
 */
declare function updateValidationAvailability(hasGoogleTranslateKey: boolean): void;
/**
 * Formats a byte count into human-readable file size
 * @param {number | null | undefined} bytes - The number of bytes
 * @returns {string} Formatted size string (e.g., "1.5 MB") or "N/A"
 */
declare function formatFileSize(bytes: number | null | undefined): string;
/**
 * Formats a date string into localized date/time representation
 * @param {string | null | undefined} dateString - ISO date string or similar
 * @returns {string} Formatted date string or "N/A" if invalid
 */
declare function formatDate(dateString: string | null | undefined): string;
/**
 * Clears the translation cache and reloads the page after user confirmation
 */
declare function clearCacheAndReload(): void;
export type { Credentials };
export { getCredentials, updateValidationAvailability, formatFileSize, formatDate, clearCacheAndReload };
//# sourceMappingURL=utils.d.ts.map