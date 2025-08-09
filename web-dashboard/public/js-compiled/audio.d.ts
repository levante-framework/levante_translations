interface AudioMetadata {
    fileName?: string;
    size?: number;
    contentType?: string;
    created?: string;
    language?: string;
    note?: string;
    id3Tags?: {
        title?: string;
        artist?: string;
        album?: string;
        genre?: string;
        service?: string;
        voice?: string;
        note?: string;
    };
}
interface AudioMetadataResponse {
    error?: string;
    details?: string;
    fileName?: string;
    size?: number;
    contentType?: string;
    created?: string;
    language?: string;
    note?: string;
    id3Tags?: AudioMetadata['id3Tags'];
}
type LanguageCode = 'en' | 'es-CO' | 'de' | 'fr-CA' | 'nl';
type BucketLanguageCode = 'en' | 'es-CO' | 'es' | 'de' | 'fr-CA' | 'nl';
/**
 * Plays audio for a specific item and language
 * @param itemId - The item identifier
 * @param langCode - The language code
 */
declare function playAudio(itemId: string, langCode: string): void;
/**
 * Shows the audio info modal and fetches metadata
 * @param itemId - The item identifier
 * @param langCode - The language code
 */
declare function showAudioInfo(itemId: string, langCode: string): void;
/**
 * Closes the audio info modal
 */
declare function closeAudioInfoModal(): void;
/**
 * Fetches audio metadata from the API
 * @param itemId - The item identifier
 * @param langCode - The language code
 */
declare function fetchAudioMetadata(itemId: string, langCode: string): Promise<void>;
/**
 * Displays audio metadata in the info modal
 * @param metadata - The audio metadata object
 */
declare function showAudioInfoData(metadata: AudioMetadata): void;
/**
 * Displays an error in the audio info modal
 * @param error - The error message
 * @param details - Additional error details
 */
declare function showAudioInfoError(error: string, details: string): void;
export { playAudio, showAudioInfo, closeAudioInfoModal, fetchAudioMetadata, showAudioInfoData, showAudioInfoError };
export type { AudioMetadata, AudioMetadataResponse, LanguageCode, BucketLanguageCode };
//# sourceMappingURL=audio.d.ts.map