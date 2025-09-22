#!/usr/bin/env python3
"""
Comprehensive es-CO validation report with additional analysis columns.
Shows before/after comparison with detailed metrics and recommendations.
"""

import json
import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

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
        "old_issues": "Comma-separated text causing parsing issues",
        "category": "Math - Number Identification"
    },
    "vocab-item-119": {
        "old_text": "traer", 
        "old_similarity": 0.346,
        "old_issues": "Simple word, should be high quality",
        "category": "Vocabulary - Action Verb"
    },
    "vocab-item-034": {
        "old_text": "la golosa",
        "old_similarity": 0.365,
        "old_issues": "Regional term for hopscotch",
        "category": "Vocabulary - Game/Activity"
    },
    "vocab-item-028": {
        "old_text": "la lavapiés",
        "old_similarity": 0.367,
        "old_issues": "Compound word translation",
        "category": "Vocabulary - Household Item"
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

def analyze_transcription_quality(transcribed_text, expected_text):
    """Analyze the quality of transcription."""
    if not transcribed_text or not expected_text:
        return "No data"
    
    # Basic analysis
    transcribed_clean = transcribed_text.lower().strip()
    expected_clean = expected_text.lower().strip()
    
    # Check for exact match
    if transcribed_clean == expected_clean:
        return "Perfect match"
    
    # Check for major issues
    issues = []
    
    # Check for missing words
    expected_words = set(expected_clean.split())
    transcribed_words = set(transcribed_clean.split())
    missing_words = expected_words - transcribed_words
    if missing_words:
        issues.append(f"Missing: {', '.join(missing_words)}")
    
    # Check for extra words
    extra_words = transcribed_words - expected_words
    if extra_words:
        issues.append(f"Extra: {', '.join(extra_words)}")
    
    # Check for number issues
    if any(char.isdigit() for char in expected_text) and not any(char.isdigit() for char in transcribed_text):
        issues.append("Numbers missing")
    
    if issues:
        return "; ".join(issues)
    else:
        return "Minor differences"

def get_improvement_category(old_score, new_score):
    """Categorize the improvement level."""
    if new_score is None:
        return "No Data"
    
    diff = new_score - old_score
    if diff >= 0.5:
        return "🚀 Dramatic Improvement"
    elif diff >= 0.3:
        return "📈 Major Improvement"
    elif diff >= 0.1:
        return "↗️ Good Improvement"
    elif diff >= 0:
        return "➡️ Slight Improvement"
    else:
        return "📉 Regression"

def get_recommendation(item_id, old_score, new_score, transcribed_text, expected_text):
    """Get recommendations based on the analysis."""
    if new_score is None:
        return "Run validation to get current scores"
    
    if new_score >= 0.85:
        return "✅ Excellent - No action needed"
    elif new_score >= 0.70:
        return "⚠️ Good - Monitor for consistency"
    else:
        return "🔴 Needs attention - Consider audio regeneration"

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

def main():
    print("🔍 COMPREHENSIVE es-CO VALIDATION REPORT")
    print("=" * 120)
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 120)
    
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
    
    # Create comprehensive results
    results = []
    
    print("\n🎯 Analyzing troublesome items...")
    print("-" * 120)
    
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
        category = prev_data.get("category", "Unknown")
        
        print(f"   Previous text: '{old_text}'")
        print(f"   Previous score: {old_similarity:.3f}")
        print(f"   Category: {category}")
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
        comprehensive_metrics = {}
        elevenlabs_validation = {}
        
        if validation_data:
            # Find validation result for this item
            for result in validation_data:
                if result.get("audio_path", "").endswith(f"/{item_id}.mp3"):
                    basic_metrics = result.get("basic_metrics", {})
                    new_similarity = basic_metrics.get("similarity_ratio")
                    transcribed_text = result.get("transcribed_text", "")
                    comprehensive_metrics = result.get("comprehensive_metrics", {})
                    elevenlabs_validation = result.get("elevenlabs_validation", {})
                    
                    quality = result.get("quality", {})
                    quality_score = quality.get("overall_score") if quality else None
                    
                    print(f"   📊 Found validation data")
                    print(f"   📝 Transcribed: '{transcribed_text}'")
                    print(f"   📊 Similarity: {format_score(new_similarity)}")
                    if quality_score:
                        print(f"   🎵 Quality: {quality_score:.3f}")
                    break
        
        # Analyze transcription quality
        transcription_analysis = analyze_transcription_quality(transcribed_text, current_text)
        
        # Get improvement category
        improvement_category = get_improvement_category(old_similarity, new_similarity)
        
        # Get recommendation
        recommendation = get_recommendation(item_id, old_similarity, new_similarity, transcribed_text, current_text)
        
        # Store comprehensive results
        results.append({
            "item_id": item_id,
            "category": category,
            "old_text": old_text,
            "new_text": current_text,
            "text_changed": text_changed,
            "old_similarity": old_similarity,
            "new_similarity": new_similarity,
            "improvement_category": improvement_category,
            "transcribed_text": transcribed_text,
            "transcription_analysis": transcription_analysis,
            "quality_score": quality_score,
            "old_issues": old_issues,
            "audio_exists": audio_info['exists'],
            "audio_size_mb": audio_info['size_mb'],
            "recommendation": recommendation,
            "comprehensive_metrics": comprehensive_metrics,
            "elevenlabs_validation": elevenlabs_validation
        })
    
    # Print comprehensive comparison table
    print("\n" + "=" * 150)
    print("📊 COMPREHENSIVE COMPARISON RESULTS")
    print("=" * 150)
    
    # Table header
    print(f"{'Item ID':<25} {'Category':<20} {'Text Changed':<12} {'Old Score':<12} {'New Score':<12} {'Improvement':<20} {'Audio':<8} {'Quality':<10} {'Recommendation'}")
    print("-" * 150)
    
    for result in results:
        item_id = result["item_id"]
        category = result["category"][:19]  # Truncate for display
        text_changed = "✅ Yes" if result["text_changed"] else "❌ No"
        old_score = format_score(result["old_similarity"])
        new_score = format_score(result["new_similarity"])
        improvement = result["improvement_category"][:19]  # Truncate for display
        audio_status = "✅ Yes" if result["audio_exists"] else "❌ No"
        quality = f"{result['quality_score']:.3f}" if result['quality_score'] else "N/A"
        recommendation = result["recommendation"][:20]  # Truncate for display
        
        print(f"{item_id:<25} {category:<20} {text_changed:<12} {old_score:<12} {new_score:<12} {improvement:<20} {audio_status:<8} {quality:<10} {recommendation}")
    
    # Detailed analysis table
    print("\n" + "=" * 150)
    print("🔍 DETAILED ANALYSIS")
    print("=" * 150)
    
    for result in results:
        print(f"\n📋 {result['item_id']} ({result['category']}):")
        print(f"   📝 Text: '{result['old_text']}' → '{result['new_text']}'")
        print(f"   📊 Score: {result['old_similarity']:.3f} → {format_score(result['new_similarity'])}")
        print(f"   🎵 Transcribed: '{result['transcribed_text']}'")
        print(f"   🔍 Analysis: {result['transcription_analysis']}")
        if result['quality_score']:
            print(f"   🎵 Audio Quality: {result['quality_score']:.3f}")
        print(f"   📋 Previous Issues: {result['old_issues']}")
        print(f"   🎵 Audio: {'✅' if result['audio_exists'] else '❌'} ({result['audio_size_mb']} MB)")
        print(f"   💡 Recommendation: {result['recommendation']}")
        
        # Show additional metrics if available
        if result['comprehensive_metrics']:
            comp = result['comprehensive_metrics']
            print(f"   📊 Additional Metrics:")
            if 'fuzzy_ratio' in comp:
                print(f"      Fuzzy Ratio: {comp['fuzzy_ratio']:.3f}")
            if 'jaro_winkler' in comp:
                print(f"      Jaro-Winkler: {comp['jaro_winkler']:.3f}")
        
        if result['elevenlabs_validation']:
            elv = result['elevenlabs_validation']
            print(f"   🎤 ElevenLabs Validation:")
            if 'similarity_score' in elv:
                print(f"      Similarity: {elv['similarity_score']:.3f}")
            if 'word_level_similarity' in elv:
                print(f"      Word Level: {elv['word_level_similarity']:.3f}")
    
    # Summary statistics
    print("\n" + "=" * 150)
    print("📈 SUMMARY STATISTICS")
    print("=" * 150)
    
    total_items = len(results)
    text_changed_count = sum(1 for r in results if r["text_changed"])
    audio_exists_count = sum(1 for r in results if r["audio_exists"])
    improved_count = sum(1 for r in results if r["new_similarity"] and r["new_similarity"] > r["old_similarity"])
    excellent_count = sum(1 for r in results if r["new_similarity"] and r["new_similarity"] >= 0.85)
    warning_count = sum(1 for r in results if r["new_similarity"] and 0.70 <= r["new_similarity"] < 0.85)
    poor_count = sum(1 for r in results if r["new_similarity"] and r["new_similarity"] < 0.70)
    no_validation_count = sum(1 for r in results if r["new_similarity"] is None)
    
    # Calculate average improvements
    valid_improvements = [r["new_similarity"] - r["old_similarity"] for r in results if r["new_similarity"] is not None]
    avg_improvement = sum(valid_improvements) / len(valid_improvements) if valid_improvements else 0
    
    print(f"📊 Total items analyzed: {total_items}")
    print(f"📝 Items with text changes: {text_changed_count}/{total_items} ({text_changed_count/total_items*100:.1f}%)")
    print(f"🎵 Items with audio files: {audio_exists_count}/{total_items} ({audio_exists_count/total_items*100:.1f}%)")
    print(f"📈 Items improved: {improved_count}/{total_items} ({improved_count/total_items*100:.1f}%)")
    print(f"✅ Items with excellent scores (≥85%): {excellent_count}/{total_items} ({excellent_count/total_items*100:.1f}%)")
    print(f"⚠️ Items with warning scores (70-84%): {warning_count}/{total_items} ({warning_count/total_items*100:.1f}%)")
    print(f"🔴 Items with poor scores (<70%): {poor_count}/{total_items} ({poor_count/total_items*100:.1f}%)")
    print(f"⚠️ Items without validation data: {no_validation_count}/{total_items} ({no_validation_count/total_items*100:.1f}%)")
    print(f"📊 Average improvement: +{avg_improvement:.3f}")
    
    # Category breakdown
    print(f"\n📂 CATEGORY BREAKDOWN:")
    categories = {}
    for result in results:
        cat = result["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "excellent": 0, "improved": 0}
        categories[cat]["total"] += 1
        if result["new_similarity"] and result["new_similarity"] >= 0.85:
            categories[cat]["excellent"] += 1
        if result["new_similarity"] and result["new_similarity"] > result["old_similarity"]:
            categories[cat]["improved"] += 1
    
    for cat, stats in categories.items():
        print(f"   {cat}: {stats['excellent']}/{stats['total']} excellent, {stats['improved']}/{stats['total']} improved")
    
    # Save comprehensive results
    output_file = "comprehensive_es_co_validation_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_items": total_items,
                "text_changed_count": text_changed_count,
                "audio_exists_count": audio_exists_count,
                "improved_count": improved_count,
                "excellent_count": excellent_count,
                "warning_count": warning_count,
                "poor_count": poor_count,
                "no_validation_count": no_validation_count,
                "average_improvement": avg_improvement
            },
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Comprehensive results saved to: {output_file}")

if __name__ == "__main__":
    main()
