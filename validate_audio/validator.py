from typing import Optional, Dict, Any, List
from pathlib import Path

from .id3_utils import read_expected_text_from_audio
from .transcriber import WhisperTranscriber, GoogleSRTranscriber
from .metrics import compute_basic_metrics, comprehensive_text_similarity, validate_elevenlabs_audio
try:
    from .quality import assess_audio_quality_with_clap
except Exception:  # pragma: no cover
    assess_audio_quality_with_clap = None  # type: ignore


def validate_audio_file(
    audio_file_path: str,
    expected_text: Optional[str] = None,
    language: Optional[str] = None,
    backend: str = "whisper",
    model_size: str = "base",
    include_quality: bool = True,
    id3_preferred_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate a single audio file against expected text using transcription and metrics.

    backend: "whisper" or "google"
    """
    audio_path = str(Path(audio_file_path))

    # 1) Resolve expected text
    expected = (expected_text or "").strip() or read_expected_text_from_audio(
        audio_file_path=audio_path, preferred_key=id3_preferred_key
    ) or ""

    # 2) Transcribe
    if backend == "google":
        transcriber = GoogleSRTranscriber(language=language)
        result = transcriber.transcribe(audio_path, language=language)
    else:
        transcriber = WhisperTranscriber(model_size=model_size)
        result = transcriber.transcribe(audio_path, language=language)

    transcribed_text = result.get("text", "").strip()

    # 3) Enhanced Metrics - Use the new comprehensive validation
    elevenlabs_validation = validate_elevenlabs_audio(expected, transcribed_text, language)
    
    # Keep the old metrics for backward compatibility
    basic = compute_basic_metrics(expected, transcribed_text)
    comp = comprehensive_text_similarity(expected, transcribed_text)

    # 4) Quality
    quality: Optional[Dict[str, Any]] = None
    if include_quality and assess_audio_quality_with_clap is not None:
        try:
            quality = assess_audio_quality_with_clap(audio_path)
        except Exception:
            quality = None

    # 5) Aggregate - Include both old and new metrics
    return {
        "audio_path": audio_path,
        "language": result.get("language") or language,
        "backend": backend,
        "whisper_model_size": model_size if backend == "whisper" else None,
        "expected_text": expected,
        "transcribed_text": transcribed_text,
        "confidence": result.get("confidence"),
        "basic_metrics": basic,
        "comprehensive_metrics": comp,
        "elevenlabs_validation": elevenlabs_validation,
        "quality": quality,
    }


def validate_many(
    audio_paths: List[str],
    expected_texts: Optional[List[Optional[str]]] = None,
    language: Optional[str] = None,
    backend: str = "whisper",
    model_size: str = "base",
    include_quality: bool = True,
    id3_preferred_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for idx, audio_file in enumerate(audio_paths):
        expected = None
        if expected_texts and idx < len(expected_texts):
            expected = expected_texts[idx]
        results.append(
            validate_audio_file(
                audio_file_path=audio_file,
                expected_text=expected,
                language=language,
                backend=backend,
                model_size=model_size,
                include_quality=include_quality,
                id3_preferred_key=id3_preferred_key,
            )
        )
    return results
