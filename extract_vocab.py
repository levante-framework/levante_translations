#!/usr/bin/env python3

import pandas as pd
from utilities import config as conf

def extract_vocab_list():
    """Extract vocab entries from the data, get English text, and remove 'the' prefixes"""
    
    print("Loading data from:", conf.item_bank_translations)
    
    # Load the data
    df = pd.read_csv(conf.item_bank_translations)
    
    print(f"Total rows in dataset: {len(df)}")
    print(f"Available columns: {df.columns.tolist()}")
    
    # Filter for vocab entries
    vocab_df = df[df['labels'] == 'vocab']
    print(f"Found {len(vocab_df)} vocab rows")
    
    if len(vocab_df) == 0:
        print("No vocab entries found!")
        return []
    
    # Check what columns are available for English text
    english_columns = [col for col in df.columns if col.lower() in ['en', 'en-us', 'english', 'text', 'eo']]
    print(f"Potential English columns found: {english_columns}")
    
    # Try to find the English text column
    english_col = None
    if 'en' in df.columns:
        english_col = 'en'
    elif 'en-US' in df.columns:
        english_col = 'en-US'
    elif 'text' in df.columns:
        english_col = 'text'
    elif 'eo' in df.columns:
        english_col = 'eo'
    else:
        print("Could not find English text column. Available columns:")
        for col in df.columns:
            print(f"  - {col}")
        return []
    
    print(f"Using column '{english_col}' for English text")
    
    # Extract English text from vocab entries
    vocab_texts = vocab_df[english_col].dropna().tolist()
    
    print(f"Found {len(vocab_texts)} vocab texts")
    print("First few examples:")
    for i, text in enumerate(vocab_texts[:5]):
        print(f"  {i+1}. {text}")
    
    # Remove "the" prefix and filter out instruction sentences
    cleaned_texts = []
    for text in vocab_texts:
        if isinstance(text, str):
            text = text.strip()
            
            # Skip long instruction sentences (likely > 10 words or contain specific phrases)
            word_count = len(text.split())
            if (word_count > 10 or 
                'in this game' in text.lower() or
                'you are going to' in text.lower() or
                'your job is to' in text.lower() or
                'make sure to' in text.lower() or
                'if you need to' in text.lower() or
                'some words are' in text.lower() or
                'press the' in text.lower()):
                print(f"  Skipping instruction: {text[:60]}...")
                continue
            
            # Remove leading articles (case insensitive)
            cleaned_text = text
            if cleaned_text.lower().startswith('the '):
                cleaned_text = cleaned_text[4:]  # Remove "the "
            elif cleaned_text.lower().startswith('der '):
                cleaned_text = cleaned_text[4:]  # Remove "der " (German)
            elif cleaned_text.lower().startswith('die '):
                cleaned_text = cleaned_text[4:]  # Remove "die " (German)
            elif cleaned_text.lower().startswith('das '):
                cleaned_text = cleaned_text[4:]  # Remove "das " (German)
            
            cleaned_texts.append(cleaned_text.strip())
    
    print(f"\nCleaned {len(cleaned_texts)} vocab entries")
    print("First few cleaned examples:")
    for i, text in enumerate(cleaned_texts[:10]):
        print(f"  {i+1}. {text}")
    
    return cleaned_texts

if __name__ == "__main__":
    vocab_list = extract_vocab_list()
    
    print(f"\n{'='*50}")
    print(f"FINAL VOCAB LIST ({len(vocab_list)} items):")
    print(f"{'='*50}")
    
    for i, item in enumerate(vocab_list, 1):
        print(f"{i:3d}. {item}")
    
    # Save to file
    with open('vocab_list.txt', 'w', encoding='utf-8') as f:
        for item in vocab_list:
            f.write(f"{item}\n")
    
    print(f"\nVocab list saved to 'vocab_list.txt'") 