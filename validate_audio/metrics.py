import re
from typing import Dict, Any, Optional
from difflib import SequenceMatcher
import warnings

# Suppress BLEU score warnings for short texts (common in audio validation)
warnings.filterwarnings("ignore", message=".*BLEU score evaluates to 0.*")
warnings.filterwarnings("ignore", message=".*counts of.*gram overlaps.*")


def preprocess_text_for_comparison(text: str) -> str:
    """
    Normalize text for better similarity comparison by handling common transcription variations
    """
    # Convert to lowercase
    text = text.lower()
    
    # Normalize possessives (Mika's -> Mikas, etc.)
    text = re.sub(r"(\w)'s\b", r"\1s", text)
    text = re.sub(r"(\w)'(\w)", r"\1\2", text)  # Handle other apostrophes
    
    # Normalize hyphens in compound words (medium-sized -> medium sized)
    text = re.sub(r'(\w)-(\w)', r'\1 \2', text)
    
    # Remove extra punctuation and normalize whitespace
    text = re.sub(r'[,;:!?]+', ' ', text)  # Replace punctuation with spaces
    text = re.sub(r'\.+', '.', text)  # Normalize multiple periods
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def robust_similarity_comparison(original_text: str, transcribed_text: str) -> Dict[str, Any]:
    """
    Robust similarity comparison that handles common transcription variations
    """
    # Clean both texts
    orig_clean = preprocess_text_for_comparison(original_text)
    trans_clean = preprocess_text_for_comparison(transcribed_text)
    
    # Calculate similarity on cleaned texts
    similarity = SequenceMatcher(None, orig_clean, trans_clean).ratio()
    
    # Additional metrics for validation
    orig_words = set(orig_clean.split())
    trans_words = set(trans_clean.split())
    
    word_overlap = len(orig_words.intersection(trans_words)) / len(orig_words.union(trans_words)) if orig_words.union(trans_words) else 0
    
    return {
        "similarity_ratio": similarity,
        "word_overlap": word_overlap,
        "original_cleaned": orig_clean,
        "transcribed_cleaned": trans_clean,
        "words_matched": len(orig_words.intersection(trans_words)),
        "total_unique_words": len(orig_words.union(trans_words))
    }


def advanced_similarity_with_phonetics(original_text: str, transcribed_text: str) -> Dict[str, Any]:
    """
    Advanced similarity comparison with phonetic awareness and word-level analysis
    """
    # Clean both texts
    orig_clean = preprocess_text_for_comparison(original_text)
    trans_clean = preprocess_text_for_comparison(transcribed_text)
    
    # Split into words for detailed analysis
    orig_words = orig_clean.split()
    trans_words = trans_clean.split()
    
    # Calculate overall similarity
    similarity = SequenceMatcher(None, orig_clean, trans_clean).ratio()
    
    # Word-level analysis
    perfect_matches = []
    phonetic_matches = []
    mismatched_words = []
    
    # Simple phonetic similarity patterns (can be enhanced with phonetic libraries)
    phonetic_patterns = {
        r'ph': 'f',
        r'ck': 'k',
        r'qu': 'kw',
        r'x': 'ks',
        r'c([ei])': r's\1',  # ce, ci -> se, si
        r'g([ei])': r'j\1',  # ge, gi -> je, ji
    }
    
    def apply_phonetic_normalization(word):
        """Apply basic phonetic normalization"""
        normalized = word.lower()
        
        # Remove spaces and hyphens for compound word matching
        normalized = re.sub(r'[\s\-]', '', normalized)
        
        # German umlaut normalization
        normalized = re.sub(r'ä', 'a', normalized)
        normalized = re.sub(r'ö', 'o', normalized)
        normalized = re.sub(r'ü', 'u', normalized)
        normalized = re.sub(r'ß', 'ss', normalized)
        
        # Common spelling variations (double letters and endings)
        normalized = re.sub(r'tte', 'tt', normalized)  # omelette -> omelett
        normalized = re.sub(r'tt', 't', normalized)    # omelett -> omelet
        normalized = re.sub(r'lle', 'll', normalized)  # belle -> bell
        normalized = re.sub(r'll', 'l', normalized)    # bell -> bel
        normalized = re.sub(r'sse', 'ss', normalized)  # classe -> class
        normalized = re.sub(r'ss', 's', normalized)    # class -> clas
        normalized = re.sub(r'nne', 'nn', normalized)  # bonne -> bonn
        normalized = re.sub(r'nn', 'n', normalized)    # bonn -> bon
        normalized = re.sub(r'mme', 'mm', normalized)  # pomme -> pomm
        normalized = re.sub(r'mm', 'm', normalized)    # pomm -> pom
        
        # Basic phonetic patterns
        for pattern, replacement in phonetic_patterns.items():
            normalized = re.sub(pattern, replacement, normalized)
        return normalized
    
    # Compare words with fuzzy matching
    for i, orig_word in enumerate(orig_words):
        best_match = None
        best_score = 0
        
        # Clean word for comparison (remove punctuation, normalize case)
        def clean_word_for_matching(word):
            return re.sub(r'[^\w]', '', word.lower())
        
        orig_clean_word = clean_word_for_matching(orig_word)
        
        for trans_word in trans_words:
            trans_clean_word = clean_word_for_matching(trans_word)
            
            # Exact match (case-insensitive, punctuation-insensitive)
            if orig_clean_word == trans_clean_word:
                perfect_matches.append((orig_word, trans_word, 1.0))
                best_match = (trans_word, 1.0, "perfect")
                break
            
            # Fuzzy similarity on cleaned words
            fuzzy_score = SequenceMatcher(None, orig_clean_word, trans_clean_word).ratio()
            if fuzzy_score > best_score:
                best_score = fuzzy_score
                best_match = (trans_word, fuzzy_score, "fuzzy")
            
            # Phonetic similarity on cleaned words
            orig_phonetic = apply_phonetic_normalization(orig_clean_word)
            trans_phonetic = apply_phonetic_normalization(trans_clean_word)
            phonetic_score = SequenceMatcher(None, orig_phonetic, trans_phonetic).ratio()
            
            if phonetic_score > 0.8 and phonetic_score > best_score:
                best_score = phonetic_score
                best_match = (trans_word, phonetic_score, "phonetic")
        
        if best_match:
            if best_match[2] == "perfect":
                continue  # Already added to perfect_matches
            elif best_match[2] == "phonetic" and best_match[1] > 0.8:
                phonetic_matches.append((orig_word, best_match[0], best_match[1]))
            elif best_match[1] < 0.7:  # Low similarity threshold
                mismatched_words.append((orig_word, best_match[0] if best_match else "", best_match[1] if best_match else 0))
        else:
            mismatched_words.append((orig_word, "", 0))
    
    # Calculate word-level similarity
    total_words = len(orig_words)
    matched_words = len(perfect_matches) + len(phonetic_matches)
    word_level_similarity = matched_words / total_words if total_words > 0 else 0
    
    return {
        "similarity_ratio": word_level_similarity,  # Use word-level similarity as main score
        "word_level_similarity": word_level_similarity,
        "original_cleaned": orig_clean,
        "transcribed_cleaned": trans_clean,
        "perfect_matches": perfect_matches,
        "phonetic_matches": phonetic_matches,
        "mismatched_words": mismatched_words,
        "total_words": total_words,
        "words_matched": matched_words,
        "total_unique_words": len(set(orig_words).union(set(trans_words))),
        "character_similarity": similarity  # Keep the original character-level similarity for reference
    }


def determine_validation_status(similarity_results: Dict[str, Any], wer_score: float) -> Dict[str, Any]:
    """
    Determine validation status with different quality levels
    """
    similarity = similarity_results["similarity_ratio"]
    mismatches = len(similarity_results["mismatched_words"])
    total_words = similarity_results["total_words"]
    
    # Calculate mismatch percentage
    mismatch_rate = mismatches / total_words if total_words > 0 else 0
    
    if similarity >= 0.95 and wer_score <= 0.05:
        return {
            "passed": True,
            "level": "EXCELLENT",
            "recommendations": ["Audio quality is excellent, no action needed"]
        }
    elif similarity >= 0.85 and wer_score <= 0.15 and mismatch_rate <= 0.1:
        return {
            "passed": True,
            "level": "GOOD",
            "recommendations": ["Audio quality is good, minor phonetic variations acceptable"]
        }
    elif similarity >= 0.70 and wer_score <= 0.25:
        return {
            "passed": True,
            "level": "ACCEPTABLE",
            "recommendations": [
                "Audio quality is acceptable but monitor for patterns",
                f"Found {mismatches} mismatched words out of {total_words}"
            ]
        }
    else:
        return {
            "passed": False,
            "level": "NEEDS_REVIEW",
            "recommendations": [
                "Audio quality below acceptable threshold",
                f"Similarity: {similarity:.3f}, WER: {wer_score:.3f}",
                "Consider regenerating audio or reviewing input text"
            ]
        }


def validate_elevenlabs_audio(expected_text: str, transcribed_text: str, language: str = None) -> Dict[str, Any]:
    """
    Comprehensive audio validation for ElevenLabs generated content
    """
    # Step 1: Advanced similarity with phonetic awareness
    similarity_results = advanced_similarity_with_phonetics(expected_text, transcribed_text)
    
    # Step 2: Calculate Word Error Rate on cleaned text
    wer_score = None
    try:
        import jiwer  # type: ignore
        wer_score = jiwer.wer(similarity_results["original_cleaned"], 
                             similarity_results["transcribed_cleaned"])
    except Exception:
        wer_score = 1.0  # Fallback to worst case if jiwer unavailable
    
    # Step 3: Determine validation status
    validation_status = determine_validation_status(similarity_results, wer_score)
    
    return {
        "transcribed_text": transcribed_text,
        "similarity_score": similarity_results["similarity_ratio"],
        "word_level_similarity": similarity_results["word_level_similarity"],
        "perfect_matches": similarity_results["perfect_matches"],
        "phonetic_matches": similarity_results["phonetic_matches"],
        "total_words": similarity_results["total_words"],
        "mismatched_words": similarity_results["mismatched_words"],
        "word_error_rate": wer_score,
        "validation_passed": validation_status["passed"],
        "validation_level": validation_status["level"],
        "recommendations": validation_status["recommendations"],
        "original_cleaned": similarity_results["original_cleaned"],
        "transcribed_cleaned": similarity_results["transcribed_cleaned"]
    }


def compute_basic_metrics(expected_text: str, transcribed_text: str) -> Dict[str, Any]:
    """Compute basic string similarity metrics and WER using robust text preprocessing.

    Returns keys: similarity_ratio, word_error_rate, word_overlap, words_matched, total_unique_words
    """
    expected_norm = (expected_text or "").strip()
    transcribed_norm = (transcribed_text or "").strip()

    # Use robust similarity comparison instead of basic SequenceMatcher
    similarity_results = robust_similarity_comparison(expected_norm, transcribed_norm)

    # Calculate Word Error Rate on cleaned texts (more accurate)
    wer_score = None
    try:
        import jiwer  # type: ignore
        wer_score = jiwer.wer(similarity_results["original_cleaned"], 
                             similarity_results["transcribed_cleaned"])
    except Exception:
        pass

    return {
        "similarity_ratio": similarity_results["similarity_ratio"],  # This will now be much more accurate
        "word_error_rate": wer_score,
        "word_overlap": similarity_results["word_overlap"],
        "words_matched": similarity_results["words_matched"],
        "total_unique_words": similarity_results["total_unique_words"],
        "original_cleaned": similarity_results["original_cleaned"],
        "transcribed_cleaned": similarity_results["transcribed_cleaned"],
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
    """Compute a richer set of text similarity metrics using robust preprocessing.

    Returns keys: fuzzy_ratio, fuzzy_token_ratio, rouge_1_f, rouge_l_f, bleu_score, overall_similarity
    Some metrics may be None if optional dependencies or resources are unavailable.
    """
    original_norm = (original_text or "").strip()
    transcribed_norm = (transcribed_text or "").strip()

    # Use preprocessed text for all comparisons
    orig_clean = preprocess_text_for_comparison(original_norm)
    trans_clean = preprocess_text_for_comparison(transcribed_norm)

    # Fuzzy ratios on cleaned text
    try:
        from rapidfuzz import fuzz  # type: ignore

        fuzzy_ratio = fuzz.ratio(orig_clean, trans_clean) / 100.0
        fuzzy_token_ratio = fuzz.token_sort_ratio(orig_clean, trans_clean) / 100.0
    except Exception:
        fuzzy_ratio = None
        fuzzy_token_ratio = None

    # ROUGE on cleaned text
    rouge_1_f = None
    rouge_l_f = None
    try:
        from rouge import Rouge  # type: ignore

        rouge = Rouge()
        scores = rouge.get_scores(trans_clean, orig_clean)[0]
        rouge_1_f = scores.get("rouge-1", {}).get("f")
        rouge_l_f = scores.get("rouge-l", {}).get("f")
    except Exception:
        pass

    # BLEU on cleaned text
    bleu_score = None
    try:
        _ensure_nltk_resource("tokenizers/punkt")
        from nltk.translate.bleu_score import sentence_bleu  # type: ignore

        reference_tokens = [orig_clean.split()]
        candidate_tokens = trans_clean.split()
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


# ----------------------------
# Meaning similarity (multilingual)
# ----------------------------
_SBERT_MODEL = None  # Lazy singleton
_SBERT_MODEL_NAME = None
_SBERT_WARNED = False


def _get_sbert_model(model_name: str):
    global _SBERT_MODEL, _SBERT_MODEL_NAME, _SBERT_WARNED
    if _SBERT_MODEL is not None:
        return _SBERT_MODEL
    # Allow environment override
    try:
        import os
        env_name = os.environ.get('MEANING_MODEL')
        if env_name:
            model_name = env_name.strip()
    except Exception:
        pass
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        print(f"[meaning] loading model: {model_name}", flush=True)
        # Prefer GPU if available
        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                _SBERT_MODEL = SentenceTransformer(model_name, device='cuda')
            else:
                _SBERT_MODEL = SentenceTransformer(model_name)
        except Exception:
            _SBERT_MODEL = SentenceTransformer(model_name)
        _SBERT_MODEL_NAME = model_name
        return _SBERT_MODEL
    except Exception as e:
        if not _SBERT_WARNED:
            print(f"[meaning] failed to load {model_name}: {e}. Trying LaBSE...", flush=True)
            _SBERT_WARNED = True
        # Fallback to LaBSE
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            fallback = "sentence-transformers/LaBSE"
            print(f"[meaning] loading fallback model: {fallback}", flush=True)
            try:
                import torch  # type: ignore
                if torch.cuda.is_available():
                    _SBERT_MODEL = SentenceTransformer(fallback, device='cuda')
                else:
                    _SBERT_MODEL = SentenceTransformer(fallback)
            except Exception:
                _SBERT_MODEL = SentenceTransformer(fallback)
            _SBERT_MODEL_NAME = fallback
            return _SBERT_MODEL
        except Exception as e2:
            if _SBERT_WARNED:
                print(f"[meaning] fallback LaBSE failed: {e2}. Meaning will be None.", flush=True)
            _SBERT_MODEL = None
            _SBERT_MODEL_NAME = None
            return None


def crosslingual_meaning_similarity(text_a: str, text_b: str, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") -> Optional[float]:
    """
    Compute cosine similarity between two sentences that may be in different languages.
    Returns None if the model or dependency is unavailable.
    """
    try:
        from sentence_transformers import util as st_util  # type: ignore
    except Exception:
        return None

    model = _get_sbert_model(model_name)
    if model is None:
        return None

    try:
        embeddings = model.encode([text_a or "", text_b or ""], convert_to_tensor=True, normalize_embeddings=True)
        # Cosine similarity of the two vectors (0 and 1)
        sim = st_util.cos_sim(embeddings[0:1], embeddings[1:2])[0][0]
        return float(sim.detach().cpu().item())
    except Exception:
        return None
