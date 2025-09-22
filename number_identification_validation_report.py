#!/usr/bin/env python3
"""
Focused validation report for the 5 troublesome number identification items in es-CO.
These items had comma-separated text issues that were causing parsing problems.
"""

import json
import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# The 5 troublesome number identification items with comma-separated text issues
TROUBLESOME_NUMBER_ITEMS = [
    "number-identification-18",  # "Escoge el,, doscientos, cuarenta y cinco."
    "number-identification-20",  # "Escoge, el,, setecientos, treinta y uno."
    "number-identification-21",  # " Escoge,, el,, novecientos ochenta y nueve"
    "number-identification-31",  # "Escoge, el, 66."
    "number-identification-36"   # " Escoge,, el ciento, treinta y uno" (incomplete in CSV)
]

# Previous validation results (from XCOMET report and analysis)
PREVIOUS_RESULTS = {
    "number-identification-18": {
        "old_text": "Escoge el,, doscientos, cuarenta y cinco.",
        "old_similarity": 0.308,  # Estimated from XCOMET report
        "old_issues": "Comma-separated text causing parsing issues",
        "number": "245"
    },
    "number-identification-20": {
        "old_text": "Escoge, el,, setecientos, treinta y uno.",
        "old_similarity": 0.346,  # From XCOMET report
        "old_issues": "Comma-separated text causing parsing issues",
        "number": "731"
    },
    "number-identification-21": {
        "old_text": " Escoge,, el,, novecientos ochenta y nueve",
        "old_similarity": 0.308,  # Estimated from XCOMET report
        "old_issues": "Comma-separated text causing parsing issues",
        "number": "989"
    },
    "number-identification-31": {
        "old_text": "Escoge, el, 66.",
        "old_similarity": 0.308,  # Estimated from XCOMET report
        "old_issues": "Comma-separated text causing parsing issues",
        "number": "66"
    },
    "number-identification-36": {
        "old_text": " Escoge,, el ciento, treinta y uno",
        "old_similarity": 0.308,  # Estimated from XCOMET report
        "old_issues": "Comma-separated text causing parsing issues",
        "number": "131"
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
    """Check if audio files exist for the troublesome number items."""
    audio_status = {}
    
    for item_id in TROUBLESOME_NUMBER_ITEMS:
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

def analyze_number_transcription(transcribed_text, expected_text, number):
    """Analyze the quality of number transcription specifically."""
    if not transcribed_text or not expected_text:
        return "No data"
    
    # Basic analysis
    transcribed_clean = transcribed_text.lower().strip()
    expected_clean = expected_text.lower().strip()
    
    # Check for exact match
    if transcribed_clean == expected_clean:
        return "Perfect match"
    
    # Check for number presence
    number_in_transcribed = number in transcribed_text
    number_in_expected = number in expected_text
    
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
    if number_in_expected and not number_in_transcribed:
        issues.append(f"Number {number} missing")
    elif number_in_transcribed and not number_in_expected:
        issues.append(f"Unexpected number {number}")
    
    # Check for comma issues
    if "," in expected_text and "," not in transcribed_text:
        issues.append("Commas removed")
    elif "," not in expected_text and "," in transcribed_text:
        issues.append("Unexpected commas")
    
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

def get_recommendation(item_id, old_score, new_score, transcribed_text, expected_text, number):
    """Get recommendations based on the analysis."""
    if new_score is None:
        return "Run validation to get current scores"
    
    if new_score >= 0.85:
        return "✅ Excellent - Comma issues resolved"
    elif new_score >= 0.70:
        return "⚠️ Good - Monitor for consistency"
    else:
        return "🔴 Needs attention - Comma issues persist"

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
    print("🔢 NUMBER IDENTIFICATION VALIDATION REPORT - es-CO")
    print("=" * 100)
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 Focus: 5 troublesome number items with comma-separated text issues")
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
    
    # Create focused results
    results = []
    
    print("\n🔢 Analyzing troublesome number identification items...")
    print("-" * 100)
    
    for item_id in TROUBLESOME_NUMBER_ITEMS:
        print(f"\n🔍 Processing {item_id}...")
        
        # Get current translation
        current_text = current_translations.get(item_id, "NOT FOUND")
        print(f"   Current text: '{current_text}'")
        
        # Get previous data
        prev_data = PREVIOUS_RESULTS.get(item_id, {})
        old_text = prev_data.get("old_text", "Unknown")
        old_similarity = prev_data.get("old_similarity", 0.0)
        old_issues = prev_data.get("old_issues", "Unknown issues")
        number = prev_data.get("number", "Unknown")
        
        print(f"   Previous text: '{old_text}'")
        print(f"   Number: {number}")
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
        
        # Analyze number transcription quality
        transcription_analysis = analyze_number_transcription(transcribed_text, current_text, number)
        
        # Get improvement category
        improvement_category = get_improvement_category(old_similarity, new_similarity)
        
        # Get recommendation
        recommendation = get_recommendation(item_id, old_similarity, new_similarity, transcribed_text, current_text, number)
        
        # Store focused results
        results.append({
            "item_id": item_id,
            "number": number,
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
    
    # Print focused comparison table
    print("\n" + "=" * 120)
    print("🔢 NUMBER IDENTIFICATION COMPARISON RESULTS")
    print("=" * 120)
    
    # Table header
    print(f"{'Item ID':<25} {'Number':<8} {'Text Changed':<12} {'Old Score':<12} {'New Score':<12} {'Improvement':<20} {'Audio':<8} {'Quality':<10} {'Recommendation'}")
    print("-" * 120)
    
    for result in results:
        item_id = result["item_id"]
        number = result["number"]
        text_changed = "✅ Yes" if result["text_changed"] else "❌ No"
        old_score = format_score(result["old_similarity"])
        new_score = format_score(result["new_similarity"])
        improvement = result["improvement_category"][:19]  # Truncate for display
        audio_status = "✅ Yes" if result["audio_exists"] else "❌ No"
        quality = f"{result['quality_score']:.3f}" if result['quality_score'] else "N/A"
        recommendation = result["recommendation"][:20]  # Truncate for display
        
        print(f"{item_id:<25} {number:<8} {text_changed:<12} {old_score:<12} {new_score:<12} {improvement:<20} {audio_status:<8} {quality:<10} {recommendation}")
    
    # Detailed analysis table
    print("\n" + "=" * 120)
    print("🔍 DETAILED NUMBER ANALYSIS")
    print("=" * 120)
    
    for result in results:
        print(f"\n🔢 {result['item_id']} (Number: {result['number']}):")
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
    print("\n" + "=" * 120)
    print("📈 NUMBER IDENTIFICATION SUMMARY")
    print("=" * 120)
    
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
    
    print(f"🔢 Total number items analyzed: {total_items}")
    print(f"📝 Items with text changes: {text_changed_count}/{total_items} ({text_changed_count/total_items*100:.1f}%)")
    print(f"🎵 Items with audio files: {audio_exists_count}/{total_items} ({audio_exists_count/total_items*100:.1f}%)")
    print(f"📈 Items improved: {improved_count}/{total_items} ({improved_count/total_items*100:.1f}%)")
    print(f"✅ Items with excellent scores (≥85%): {excellent_count}/{total_items} ({excellent_count/total_items*100:.1f}%)")
    print(f"⚠️ Items with warning scores (70-84%): {warning_count}/{total_items} ({warning_count/total_items*100:.1f}%)")
    print(f"🔴 Items with poor scores (<70%): {poor_count}/{total_items} ({poor_count/total_items*100:.1f}%)")
    print(f"⚠️ Items without validation data: {no_validation_count}/{total_items} ({no_validation_count/total_items*100:.1f}%)")
    print(f"📊 Average improvement: +{avg_improvement:.3f}")
    
    # Comma issue resolution analysis
    print(f"\n🔧 COMMA ISSUE RESOLUTION:")
    comma_resolved = sum(1 for r in results if r["new_similarity"] and r["new_similarity"] >= 0.70)
    print(f"   Items with resolved comma issues: {comma_resolved}/{total_items} ({comma_resolved/total_items*100:.1f}%)")
    
    # Save focused results
    output_file = "number_identification_validation_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "focus": "Number identification items with comma-separated text issues",
            "summary": {
                "total_items": total_items,
                "text_changed_count": text_changed_count,
                "audio_exists_count": audio_exists_count,
                "improved_count": improved_count,
                "excellent_count": excellent_count,
                "warning_count": warning_count,
                "poor_count": poor_count,
                "no_validation_count": no_validation_count,
                "average_improvement": avg_improvement,
                "comma_issues_resolved": comma_resolved
            },
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Focused results saved to: {output_file}")

if __name__ == "__main__":
    main()
