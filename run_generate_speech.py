#!/usr/bin/env python3
import argparse
import sys
from typing import List

try:
    import utilities.config as conf
except Exception as e:
    print(f"Error importing utilities.config: {e}")
    sys.exit(1)

try:
    import generate_speech as gen
except Exception as e:
    print(f"Error importing generate_speech: {e}")
    sys.exit(1)


def print_languages_table(languages: dict):
    print("\nCurrent language configuration:\n")
    header = f"{'Language':30} {'Code':8} {'Service':12} Voice"
    print(header)
    print("-" * len(header))
    for name, cfg in languages.items():
        lang_code = cfg.get('lang_code', '')
        service = cfg.get('service', '')
        voice = cfg.get('voice', '')
        print(f"{name:30} {lang_code:8} {service:12} {voice}")
    print()


def parse_language_selection(selection: str, available_names: List[str]) -> List[str]:
    """Accepts display names or language codes (e.g., 'Spanish (Argentina)' or 'es-AR')."""
    selection = (selection or '').strip()
    if not selection:
        return []
    if selection.lower() in ('all', '*'):
        return available_names

    # Build lookup maps: name -> name, code -> name
    try:
        import utilities.config as conf
        langs_map = conf.get_languages() or {}
    except Exception:
        langs_map = {}
    name_lookup = {name.lower(): name for name in available_names}
    code_lookup = {}
    for name, cfg in langs_map.items():
        code = (cfg.get('lang_code') or '').lower()
        if code:
            code_lookup[code] = name
            # Accept underscore variant and base language code as well
            code_lookup[code.replace('_', '-')] = name
            code_lookup[code.replace('-', '_')] = name
            base = code.split('-')[0]
            if base:
                code_lookup[base] = name if base == code else code_lookup.get(base, name)

    chosen_tokens = [s.strip() for s in selection.split(',') if s.strip()]
    resolved: List[str] = []
    for token in chosen_tokens:
        key = token.lower()
        # Try name match
        if key in name_lookup:
            resolved.append(name_lookup[key])
            continue
        # Try exact/normalized code match
        if key in code_lookup:
            resolved.append(code_lookup[key])
            continue
        # Try normalized hyphen/underscore variants
        norm = key.replace('_', '-').lower()
        if norm in code_lookup:
            resolved.append(code_lookup[norm])
            continue
        print(f"Warning: '{token}' not found by name or code; skipping")
    # De-duplicate while preserving order
    seen = set()
    unique_resolved = []
    for name in resolved:
        if name not in seen:
            seen.add(name)
            unique_resolved.append(name)
    return unique_resolved


def main():
    parser = argparse.ArgumentParser(description="Front-end for generate_speech: show voices, confirm, and run")
    parser.add_argument('--languages', '-l', help="Comma-separated language display names or codes (e.g., 'Spanish (Argentina)', 'es-AR'; use 'all' for all). If omitted, you'll be prompted.")
    parser.add_argument('--force', '-f', action='store_true', help="Force regenerate for selected languages (clears cache column and regenerates all items)")
    parser.add_argument('--yes', '-y', action='store_true', help="Skip interactive confirmation and proceed")
    args = parser.parse_args()

    languages = conf.get_languages()
    if not languages:
        print("No languages found in configuration.")
        sys.exit(1)

    print_languages_table(languages)

    available_names = list(languages.keys())

    selected_names: List[str] = []
    if args.languages:
        selected_names = parse_language_selection(args.languages, available_names)
    else:
        # Prompt for selection
        try:
            raw = input("Enter language names (comma-separated), or 'all' for all: ").strip()
        except EOFError:
            raw = ''
        selected_names = parse_language_selection(raw, available_names)

    if not selected_names:
        print("No languages selected. Exiting.")
        sys.exit(0)

    print("You selected:")
    for name in selected_names:
        cfg = languages[name]
        print(f"  - {name} ({cfg.get('lang_code','')}) via {cfg.get('service','')} | voice: {cfg.get('voice','')}")

    proceed = args.yes
    if not proceed:
        try:
            ans = input(f"Proceed with audio generation for {len(selected_names)} language(s)? [y/N]: ").strip().lower()
            proceed = ans in ('y', 'yes')
        except EOFError:
            proceed = False

    if not proceed:
        print("Cancelled.")
        sys.exit(0)

    # Run generation per language
    any_errors = False
    for name in selected_names:
        try:
            print("\n" + "="*80)
            print(f"Starting generate_speech for: {name}")
            gen.main(language=name, force_regenerate=args.force)
        except Exception as e:
            any_errors = True
            print(f"Error generating for {name}: {e}")

    if any_errors:
        sys.exit(1)
    print("\nAll selected generations finished.")


if __name__ == '__main__':
    main()
