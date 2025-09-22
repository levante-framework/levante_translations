#!/usr/bin/env python3
"""
Compare validation scores for troublesome es-CO translations before and after updates.
This script validates the current audio files and compares them with previous results.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

# Add the validate_audio module to the path
sys.path.append(str(Path(__file__).parent / "validate_audio"))

from validator import validate_audio_file

# Troublesome items identified from previous analysis
TROUBLESOME_ITEMS = [
    "number-identification-20",
    "vocab-item-119", 
    "vocab-item-034",
    "vocab-item-028"
]

# Previous validation results (from the old analysis)
PREVIOUS_RESULTS = {
    "number-identification-20": {
        "expected_text": "Escoge, el,, setecientos, treinta y uno.",
        "old_similarity": 0.346,  # From XCOMET report
        "old_issues": "Comma-separated text causing parsing issues"
    },
    "vocab-item-119": {
        "expected_text": "traer", 
        "old_similarity": 0.346,  # From XCOMET report
        "old_issues": "Simple word, should be high quality"
    },
    "vocab-item-034": {
        "expected_text": "la golosa",
        "old_similarity": 0.365,  # From XCOMET report  
        "old_issues": "Regional term for hopscotch"
    },
    "vocab-item-028": {
        "expected_text": "la lavapiés",
        "old_similarity": 0.367,  # From XCOMET report
        "old_issues": "Compound word translation"
    }
}

def load_current_translations() -> Dict[str, str]:
    """Load current es-CO translations from CSV."""
    csv_path = Path("translation_text/item_bank_translations.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"Translation CSV not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    translations = {}
    
    for _, row in df.iterrows():
        item_id = row['item_id']
        es_co_text = row.get('es-CO', '')
        if pd.notna(es_co_text) and es_co_text.strip():
            translations[item_id] = es_co_text.strip()
    
    return translations

def validate_current_audio(item_id: str, expected_text: str) -> Dict[str, Any]:
    """Validate current audio file for an item."""
    audio_path = f"audio_files/es-CO/{item_id}.mp3"
    
    if not os.path.exists(audio_path):
        return {
            "error": "Audio file not found",
            "audio_path": audio_path
        }
    
    try:
        result = validate_audio_file(
            audio_file_path=audio_path,
            expected_text=expected_text,
            language="es",
            backend="whisper",
            model_size="base",
            include_quality=True
        )
        return result
    except Exception as e:
        return {
            "error": str(e),
            "audio_path": audio_path
        }

def format_score(score: Optional[float]) -> str:
    """Format similarity score with color coding."""
    if score is None:
        return "N/A"
    
    if score >= 0.85:
        return f"🟢 {score:.3f}"
    elif score >= 0.70:
        return f"🟡 {score:.3f}"
    else:
        return f"🔴 {score:.3f}"

def format_improvement(old_score: float, new_score: Optional[float]) -> str:
    """Format improvement indicator."""
    if new_score is None:
        return "❌ Error"
    
    diff = new_score - old_score
    if diff > 0.05:
        return f"📈 +{diff:.3f}"
    elif diff > 0:
        return f"↗️ +{diff:.3f}"
    elif diff > -0.05:
        return f"➡️ {diff:.3f}"
    else:
        return f"📉 {diff:.3f}"

def main():
    print("🔍 Comparing es-CO Validation Scores: Old vs New")
    print("=" * 80)
    
    # Load current translations
    print("📖 Loading current translations...")
    try:
        current_translations = load_current_translations()
        print(f"✅ Loaded {len(current_translations)} translations")
    except Exception as e:
        print(f"❌ Error loading translations: {e}")
        return
    
    # Results table
    results = []
    
    print("\n🎯 Validating troublesome items...")
    print("-" * 80)
    
    for item_id in TROUBLESOME_ITEMS:
        print(f"\n🔍 Processing {item_id}...")
        
        # Get current translation
        current_text = current_translations.get(item_id, "NOT FOUND")
        print(f"   Current text: '{current_text}'")
        
        # Get previous data
        prev_data = PREVIOUS_RESULTS.get(item_id, {})
        old_text = prev_data.get("expected_text", "Unknown")
        old_similarity = prev_data.get("old_similarity", 0.0)
        old_issues = prev_data.get("old_issues", "Unknown issues")
        
        print(f"   Previous text: '{old_text}'")
        print(f"   Previous score: {old_similarity:.3f}")
        print(f"   Previous issues: {old_issues}")
        
        # Check if text changed
        text_changed = current_text != old_text
        print(f"   Text changed: {'✅ Yes' if text_changed else '❌ No'}")
        
        # Validate current audio
        print("   🎵 Validating current audio...")
        validation_result = validate_current_audio(item_id, current_text)
        
        if "error" in validation_result:
            print(f"   ❌ Validation error: {validation_result['error']}")
            new_similarity = None
            transcribed_text = "ERROR"
            quality_score = None
        else:
            # Extract key metrics
            basic_metrics = validation_result.get("basic_metrics", {})
            new_similarity = basic_metrics.get("similarity_ratio")
            transcribed_text = validation_result.get("transcribed_text", "")
            
            # Get quality score if available
            quality = validation_result.get("quality", {})
            quality_score = quality.get("overall_score") if quality else None
            
            print(f"   ✅ Validation complete")
            print(f"   📝 Transcribed: '{transcribed_text}'")
            print(f"   📊 Similarity: {format_score(new_similarity)}")
            if quality_score:
                print(f"   🎵 Quality: {quality_score:.3f}")
        
        # Store results
        results.append({
            "item_id": item_id,
            "old_text": old_text,
            "new_text": current_text,
            "text_changed": text_changed,
            "old_similarity": old_similarity,
            "new_similarity": new_similarity,
            "improvement": format_improvement(old_similarity, new_similarity),
            "transcribed_text": transcribed_text,
            "quality_score": quality_score,
            "old_issues": old_issues
        })
    
    # Print comparison table
    print("\n" + "=" * 120)
    print("📊 COMPARISON RESULTS")
    print("=" * 120)
    
    # Table header
    print(f"{'Item ID':<25} {'Text Changed':<12} {'Old Score':<12} {'New Score':<12} {'Improvement':<12} {'Quality':<10} {'Status'}")
    print("-" * 120)
    
    for result in results:
        item_id = result["item_id"]
        text_changed = "✅ Yes" if result["text_changed"] else "❌ No"
        old_score = format_score(result["old_similarity"])
        new_score = format_score(result["new_similarity"])
        improvement = result["improvement"]
        quality = f"{result['quality_score']:.3f}" if result['quality_score'] else "N/A"
        
        # Determine overall status
        if result["new_similarity"] is None:
            status = "❌ Error"
        elif result["new_similarity"] >= 0.85:
            status = "✅ Excellent"
        elif result["new_similarity"] >= 0.70:
            status = "⚠️ Warning"
        else:
            status = "🔴 Poor"
        
        print(f"{item_id:<25} {text_changed:<12} {old_score:<12} {new_score:<12} {improvement:<12} {quality:<10} {status}")
    
    # Summary
    print("\n" + "=" * 120)
    print("📈 SUMMARY")
    print("=" * 120)
    
    total_items = len(results)
    text_changed_count = sum(1 for r in results if r["text_changed"])
    improved_count = sum(1 for r in results if r["new_similarity"] and r["new_similarity"] > r["old_similarity"])
    excellent_count = sum(1 for r in results if r["new_similarity"] and r["new_similarity"] >= 0.85)
    error_count = sum(1 for r in results if r["new_similarity"] is None)
    
    print(f"📊 Total items analyzed: {total_items}")
    print(f"📝 Items with text changes: {text_changed_count}/{total_items}")
    print(f"📈 Items improved: {improved_count}/{total_items}")
    print(f"✅ Items with excellent scores (≥85%): {excellent_count}/{total_items}")
    print(f"❌ Items with errors: {error_count}/{total_items}")
    
    # Detailed analysis
    print("\n🔍 DETAILED ANALYSIS")
    print("-" * 80)
    
    for result in results:
        print(f"\n📋 {result['item_id']}:")
        print(f"   📝 Text: '{result['old_text']}' → '{result['new_text']}'")
        print(f"   📊 Score: {result['old_similarity']:.3f} → {format_score(result['new_similarity'])}")
        print(f"   🎵 Transcribed: '{result['transcribed_text']}'")
        if result['quality_score']:
            print(f"   🎵 Audio Quality: {result['quality_score']:.3f}")
        print(f"   📋 Previous Issues: {result['old_issues']}")
    
    # Save detailed results
    output_file = "es_co_validation_comparison.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: {output_file}")

if __name__ == "__main__":
    main()
