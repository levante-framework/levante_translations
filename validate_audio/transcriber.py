from typing import Optional, Dict, Any


class WhisperTranscriber:
    """Transcribe speech to text using OpenAI Whisper (openai-whisper library)."""

    def __init__(
        self,
        model_size: str = "base",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        load_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Lazy import so that installing whisper remains optional until used
        import whisper  # type: ignore

        self._whisper = whisper
        self._device = device
        self._model_size = model_size
        self._model = None
        self._compute_type = compute_type
        self._load_options = load_options or {}

    def _ensure_model(self) -> None:
        if self._model is None:
            # Whisper loads best device automatically (cuda if available)
            device = "cuda" if self._whisper.torch.cuda.is_available() else "cpu"
            self._model = self._whisper.load_model(self._model_size, device=device, **self._load_options)

    def transcribe(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        temperature: float = 0.0,
        without_timestamps: bool = True,
    ) -> Dict[str, Any]:
        self._ensure_model()
        try:
            print(f"[whisper] transcribing: {audio_file_path} (model={self._model_size})", flush=True)
        except Exception:
            pass

        # The openai-whisper API returns a dict with keys like 'text', 'segments', and 'language'
        result = self._model.transcribe(
            audio=audio_file_path,
            language=language,
            temperature=temperature,
            condition_on_previous_text=False,
            without_timestamps=without_timestamps,
        )

        # Normalize shape a bit and include compatibility fields
        normalized: Dict[str, Any] = {
            "text": result.get("text", "").strip(),
            "segments": result.get("segments", []),
            "language": result.get("language"),
        }

        # Whisper does not provide an overall confidence; keep None for consistency
        normalized["confidence"] = None
        return normalized


class GoogleSRTranscriber:
    """Transcribe speech to text using SpeechRecognition with Google Web Speech API.

    Note: This requires Internet access and may be rate-limited. Provided as a fallback.
    """

    def __init__(self, language: Optional[str] = None) -> None:
        try:
            import speech_recognition as sr  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "SpeechRecognition is not installed. Install with `pip install SpeechRecognition`"
            ) from exc
        self._sr = sr
        self._recognizer = sr.Recognizer()
        self._language = language

    def transcribe(self, audio_file_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        lang = language or self._language
        with self._sr.AudioFile(audio_file_path) as source:
            audio_data = self._recognizer.record(source)
        try:
            text = self._recognizer.recognize_google(audio_data, language=lang)  # type: ignore
        except self._sr.UnknownValueError:
            text = ""
        except self._sr.RequestError as exc:  # pragma: no cover
            raise RuntimeError(f"Google SR API request failed: {exc}") from exc

        return {
            "text": text,
            "segments": [],
            "language": lang,
            "confidence": None,  # API does not provide a single confidence value
        }
