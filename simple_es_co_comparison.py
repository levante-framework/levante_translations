#!/usr/bin/env python3
"""
Simple comparison of es-CO validation scores before and after updates.
Uses existing validation data and checks current audio files.
"""

import json
import os
import sys
from pathlib import Path
import pandas as pd

# Troublesome items identified from previous analysis
TROUBLESOME_ITEMS = [
    "number-identification-20",
    "vocab-item-119", 
    "vocab-item-034",
    "vocab-item-028"
]

# Previous validation results (from XCOMET report and previous analysis)
PREVIOUS_RESULTS = {
    "number-identification-20": {
        "old_text": "Escoge, el,, setecientos, treinta y uno.",
        "old_similarity": 0.346,
        "old_issues": "Comma-separated text causing parsing issues"
    },
    "vocab-item-119": {
        "old_text": "traer", 
        "old_similarity": 0.346,
        "old_issues": "Simple word, should be high quality"
    },
    "vocab-item-034": {
        "old_text": "la golosa",
        "old_similarity": 0.365,
        "old_issues": "Regional term for hopscotch"
    },
    "vocab-item-028": {
        "old_text": "la lavapiés",
        "old_similarity": 0.367,
        "old_issues": "Compound word translation"
    }
}

def load_current_translations():
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

def load_validation_data():
    """Load existing validation data if available."""
    validation_files = [
        "web-dashboard/public/data/validation-es-Sep-11-2025.json",
        "web-dashboard/data/validation-es-Sep-11-2025.json"
    ]
    
    for file_path in validation_files:
        if os.path.exists(file_path):
            print(f"📖 Loading validation data from: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    print("⚠️ No validation data found, will show text comparison only")
    return None

def check_audio_files():
    """Check if audio files exist for the troublesome items."""
    audio_status = {}
    
    for item_id in TROUBLESOME_ITEMS:
        audio_path = f"audio_files/es-CO/{item_id}.mp3"
        exists = os.path.exists(audio_path)
        size = os.path.getsize(audio_path) if exists else 0
        audio_status[item_id] = {
            "exists": exists,
            "path": audio_path,
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2) if exists else 0
        }
    
    return audio_status

def format_score(score):
    """Format similarity score with color coding."""
    if score is None:
        return "N/A"
    
    if score >= 0.85:
        return f"🟢 {score:.3f}"
    elif score >= 0.70:
        return f"🟡 {score:.3f}"
    else:
        return f"🔴 {score:.3f}"

def format_improvement(old_score, new_score):
    """Format improvement indicator."""
    if new_score is None:
        return "❌ No data"
    
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
    print("=" * 100)
    
    # Load current translations
    print("📖 Loading current translations...")
    try:
        current_translations = load_current_translations()
        print(f"✅ Loaded {len(current_translations)} translations")
    except Exception as e:
        print(f"❌ Error loading translations: {e}")
        return
    
    # Load validation data
    validation_data = load_validation_data()
    
    # Check audio files
    print("\n🎵 Checking audio files...")
    audio_status = check_audio_files()
    
    # Create results table
    results = []
    
    print("\n🎯 Analyzing troublesome items...")
    print("-" * 100)
    
    for item_id in TROUBLESOME_ITEMS:
        print(f"\n🔍 Processing {item_id}...")
        
        # Get current translation
        current_text = current_translations.get(item_id, "NOT FOUND")
        print(f"   Current text: '{current_text}'")
        
        # Get previous data
        prev_data = PREVIOUS_RESULTS.get(item_id, {})
        old_text = prev_data.get("old_text", "Unknown")
        old_similarity = prev_data.get("old_similarity", 0.0)
        old_issues = prev_data.get("old_issues", "Unknown issues")
        
        print(f"   Previous text: '{old_text}'")
        print(f"   Previous score: {old_similarity:.3f}")
        print(f"   Previous issues: {old_issues}")
        
        # Check if text changed
        text_changed = current_text != old_text
        print(f"   Text changed: {'✅ Yes' if text_changed else '❌ No'}")
        
        # Check audio file
        audio_info = audio_status[item_id]
        print(f"   Audio file: {'✅ Exists' if audio_info['exists'] else '❌ Missing'}")
        if audio_info['exists']:
            print(f"   Audio size: {audio_info['size_mb']} MB")
        
        # Look for validation data
        new_similarity = None
        transcribed_text = "No validation data"
        quality_score = None
        
        if validation_data:
            # Find validation result for this item
            for result in validation_data:
                if result.get("audio_path", "").endswith(f"/{item_id}.mp3"):
                    basic_metrics = result.get("basic_metrics", {})
                    new_similarity = basic_metrics.get("similarity_ratio")
                    transcribed_text = result.get("transcribed_text", "")
                    
                    quality = result.get("quality", {})
                    quality_score = quality.get("overall_score") if quality else None
                    
                    print(f"   📊 Found validation data")
                    print(f"   📝 Transcribed: '{transcribed_text}'")
                    print(f"   📊 Similarity: {format_score(new_similarity)}")
                    if quality_score:
                        print(f"   🎵 Quality: {quality_score:.3f}")
                    break
        
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
            "old_issues": old_issues,
            "audio_exists": audio_info['exists'],
            "audio_size_mb": audio_info['size_mb']
        })
    
    # Print comparison table
    print("\n" + "=" * 120)
    print("📊 COMPARISON RESULTS")
    print("=" * 120)
    
    # Table header
    print(f"{'Item ID':<25} {'Text Changed':<12} {'Old Score':<12} {'New Score':<12} {'Improvement':<12} {'Audio':<8} {'Quality':<10} {'Status'}")
    print("-" * 120)
    
    for result in results:
        item_id = result["item_id"]
        text_changed = "✅ Yes" if result["text_changed"] else "❌ No"
        old_score = format_score(result["old_similarity"])
        new_score = format_score(result["new_similarity"])
        improvement = result["improvement"]
        audio_status = "✅ Yes" if result["audio_exists"] else "❌ No"
        quality = f"{result['quality_score']:.3f}" if result['quality_score'] else "N/A"
        
        # Determine overall status
        if not result["audio_exists"]:
            status = "❌ No Audio"
        elif result["new_similarity"] is None:
            status = "⚠️ No Validation"
        elif result["new_similarity"] >= 0.85:
            status = "✅ Excellent"
        elif result["new_similarity"] >= 0.70:
            status = "⚠️ Warning"
        else:
            status = "🔴 Poor"
        
        print(f"{item_id:<25} {text_changed:<12} {old_score:<12} {new_score:<12} {improvement:<12} {audio_status:<8} {quality:<10} {status}")
    
    # Summary
    print("\n" + "=" * 120)
    print("📈 SUMMARY")
    print("=" * 120)
    
    total_items = len(results)
    text_changed_count = sum(1 for r in results if r["text_changed"])
    audio_exists_count = sum(1 for r in results if r["audio_exists"])
    improved_count = sum(1 for r in results if r["new_similarity"] and r["new_similarity"] > r["old_similarity"])
    excellent_count = sum(1 for r in results if r["new_similarity"] and r["new_similarity"] >= 0.85)
    no_validation_count = sum(1 for r in results if r["new_similarity"] is None)
    
    print(f"📊 Total items analyzed: {total_items}")
    print(f"📝 Items with text changes: {text_changed_count}/{total_items}")
    print(f"🎵 Items with audio files: {audio_exists_count}/{total_items}")
    print(f"📈 Items improved: {improved_count}/{total_items}")
    print(f"✅ Items with excellent scores (≥85%): {excellent_count}/{total_items}")
    print(f"⚠️ Items without validation data: {no_validation_count}/{total_items}")
    
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
        print(f"   🎵 Audio: {'✅' if result['audio_exists'] else '❌'} ({result['audio_size_mb']} MB)")
    
    # Save detailed results
    output_file = "es_co_validation_comparison.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: {output_file}")

if __name__ == "__main__":
    main()
