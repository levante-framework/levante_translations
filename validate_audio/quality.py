from typing import Dict, Any, List


_CLAP_MODEL = None
_CLAP_PROCESSOR = None


def _ensure_clap_model() -> None:
    global _CLAP_MODEL, _CLAP_PROCESSOR
    if _CLAP_MODEL is not None and _CLAP_PROCESSOR is not None:
        return
    from transformers import ClapModel, ClapProcessor  # type: ignore

    _CLAP_MODEL = ClapModel.from_pretrained("laion/larger_clap_music_and_speech")
    _CLAP_PROCESSOR = ClapProcessor.from_pretrained("laion/larger_clap_music_and_speech")


def assess_audio_quality_with_clap(audio_file_path: str) -> Dict[str, Any]:
    """Assess perceptual audio quality using CLAP similarity prompts.

    Returns keys: quality_score, noise_score, quality_confidence
    """
    import torch  # type: ignore
    import librosa  # type: ignore

    _ensure_clap_model()

    quality_prompts: List[str] = [
        "the sound is clear and clean",
        "the audio has good quality",
        "the speech is natural and fluent",
    ]
    noise_prompts: List[str] = [
        "the sound is noisy and distorted",
        "the audio has poor quality",
        "the speech sounds robotic and unnatural",
    ]

    audio_data, sample_rate = librosa.load(audio_file_path, sr=48000)

    quality_scores: List[float] = []
    noise_scores: List[float] = []

    for prompt in quality_prompts:
        inputs = _CLAP_PROCESSOR(
            text=[prompt],
            audios=[audio_data],
            return_tensors="pt",
            sampling_rate=sample_rate,
        )
        with torch.no_grad():
            outputs = _CLAP_MODEL(**inputs)
            score = torch.cosine_similarity(outputs.audio_embeds, outputs.text_embeds).item()
            quality_scores.append(float(score))

    for prompt in noise_prompts:
        inputs = _CLAP_PROCESSOR(
            text=[prompt],
            audios=[audio_data],
            return_tensors="pt",
            sampling_rate=sample_rate,
        )
        with torch.no_grad():
            outputs = _CLAP_MODEL(**inputs)
            score = torch.cosine_similarity(outputs.audio_embeds, outputs.text_embeds).item()
            noise_scores.append(float(score))

    quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    noise_score = sum(noise_scores) / len(noise_scores) if noise_scores else 0.0
    quality_confidence = max(0.0, (quality_score - noise_score))

    return {
        "quality_score": quality_score,
        "noise_score": noise_score,
        "quality_confidence": quality_confidence,
    }
