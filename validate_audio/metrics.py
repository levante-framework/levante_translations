from typing import Dict, Any
from difflib import SequenceMatcher


def compute_basic_metrics(expected_text: str, transcribed_text: str) -> Dict[str, Any]:
    """Compute basic string similarity metrics and WER.

    Returns keys: similarity_ratio, word_error_rate
    """
    expected_norm = (expected_text or "").strip()
    transcribed_norm = (transcribed_text or "").strip()

    similarity_ratio = SequenceMatcher(None, expected_norm.lower(), transcribed_norm.lower()).ratio()

    try:
        import jiwer  # type: ignore

        wer_score = jiwer.wer(expected_norm, transcribed_norm)
    except Exception:
        wer_score = None

    return {
        "similarity_ratio": similarity_ratio,
        "word_error_rate": wer_score,
    }


def _ensure_nltk_resource(resource: str) -> None:
    try:
        import nltk  # type: ignore

        nltk.data.find(resource)
    except LookupError:
        try:
            nltk.download(resource.split("/")[-1], quiet=True)
        except Exception:
            # If download fails (e.g., offline), we silently continue; caller will handle fallback
            pass


def comprehensive_text_similarity(original_text: str, transcribed_text: str) -> Dict[str, Any]:
    """Compute a richer set of text similarity metrics.

    Returns keys: fuzzy_ratio, fuzzy_token_ratio, rouge_1_f, rouge_l_f, bleu_score, overall_similarity
    Some metrics may be None if optional dependencies or resources are unavailable.
    """
    original_norm = (original_text or "").strip()
    transcribed_norm = (transcribed_text or "").strip()

    # Fuzzy ratios
    try:
        from rapidfuzz import fuzz  # type: ignore

        fuzzy_ratio = fuzz.ratio(original_norm.lower(), transcribed_norm.lower()) / 100.0
        fuzzy_token_ratio = fuzz.token_sort_ratio(original_norm, transcribed_norm) / 100.0
    except Exception:
        fuzzy_ratio = None
        fuzzy_token_ratio = None

    # ROUGE
    rouge_1_f = None
    rouge_l_f = None
    try:
        from rouge import Rouge  # type: ignore

        rouge = Rouge()
        scores = rouge.get_scores(transcribed_norm, original_norm)[0]
        rouge_1_f = scores.get("rouge-1", {}).get("f")
        rouge_l_f = scores.get("rouge-l", {}).get("f")
    except Exception:
        pass

    # BLEU
    bleu_score = None
    try:
        _ensure_nltk_resource("tokenizers/punkt")
        from nltk.translate.bleu_score import sentence_bleu  # type: ignore

        reference_tokens = [original_norm.lower().split()]
        candidate_tokens = transcribed_norm.lower().split()
        bleu_score = sentence_bleu(reference_tokens, candidate_tokens)
    except Exception:
        pass

    # Overall similarity: average available components
    components = [c for c in [fuzzy_ratio, rouge_1_f, bleu_score] if c is not None]
    overall_similarity = sum(components) / len(components) if components else None

    return {
        "fuzzy_ratio": fuzzy_ratio,
        "fuzzy_token_ratio": fuzzy_token_ratio,
        "rouge_1_f": rouge_1_f,
        "rouge_l_f": rouge_l_f,
        "bleu_score": bleu_score,
        "overall_similarity": overall_similarity,
    }
