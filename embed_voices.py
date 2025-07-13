#!/usr/bin/env python3
"""
Script to embed comprehensive voices data directly into the HTML file
This fixes the issue where the external JavaScript file isn't loading due to Vercel routing
"""

import re

def embed_voices_in_html():
    # Read the comprehensive voices JavaScript file
    with open('web-dashboard/comprehensive-voices.js', 'r', encoding='utf-8') as f:
        voices_content = f.read()
    
    # Extract just the COMPREHENSIVE_VOICES constant definition
    # Find the start of the const declaration
    start_pattern = r'const COMPREHENSIVE_VOICES = {'
    
    start_match = re.search(start_pattern, voices_content)
    if not start_match:
        print("Could not find COMPREHENSIVE_VOICES declaration")
        return False
    
    # Find the matching closing brace
    start_pos = start_match.start()
    brace_count = 0
    end_pos = None
    
    for i, char in enumerate(voices_content[start_pos:], start_pos):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end_pos = i + 1
                break
    
    if end_pos is None:
        print("Could not find matching closing brace")
        return False
    
    # Extract the complete COMPREHENSIVE_VOICES definition
    voices_definition = voices_content[start_pos:end_pos]
    
    # Read the HTML file
    with open('web-dashboard/index.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Find and replace the script tag
    script_start = html_content.find('<script>')
    if script_start == -1:
        print("Could not find script tag")
        return False
    
    # Find the comment that indicates where we want to insert
    comment_pos = html_content.find('// Embedded JavaScript to avoid serving issues', script_start)
    if comment_pos == -1:
        print("Could not find insertion point comment")
        return False
    
    # Insert the voices definition before the comment
    insertion_point = comment_pos
    new_content = (
        html_content[:insertion_point] +
        '// Embedded comprehensive voices data\n        ' +
        voices_definition + '\n        \n        ' +
        html_content[insertion_point:]
    )
    
    # Write the updated HTML file
    with open('web-dashboard/index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Successfully embedded comprehensive voices data into HTML file")
    return True

if __name__ == "__main__":
    embed_voices_in_html() 