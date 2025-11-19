#!/usr/bin/env python3
"""
Import a Cursor chat markdown file into Cursor's database.

This script parses a Cursor-exported markdown chat file and imports it
into Cursor's SQLite database so it appears in the chat history.
"""

import sqlite3
import json
import re
import uuid
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Path to Cursor's state database
CURSOR_DB_PATH = Path("/mnt/c/Users/digit/AppData/Roaming/Cursor/User/globalStorage/state.vscdb")
CURSOR_DB_BACKUP_PATH = CURSOR_DB_PATH.with_suffix('.vscdb.backup_import')


def parse_markdown_chat(md_file: Path) -> Dict[str, Any]:
    """Parse a Cursor markdown chat export into structured data."""
    print(f"Reading markdown file: {md_file}")
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract title and export date from header
    title_match = re.match(r'^# (.+?)\n_Exported on (.+?)_', content)
    title = title_match.group(1) if title_match else "Imported Chat"
    export_date = title_match.group(2) if title_match else None
    
    # Remove the header (everything before the first ---)
    header_end = content.find('\n---\n')
    if header_end != -1:
        content = content[header_end + 5:]  # Skip the "---\n"
    
    # Split by message separators (---)
    # Messages alternate between **User** and **Cursor**
    messages = []
    parts = re.split(r'\n---\n', content)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Check if it starts with **User** or **Cursor**
        if part.startswith('**User**'):
            # Extract content after **User**\n\n
            content_start = part.find('**User**')
            if content_start != -1:
                # Find the content after **User**\n\n
                msg_content = part[content_start + 8:].strip()
                # Remove leading newlines
                msg_content = re.sub(r'^\n+', '', msg_content)
                if msg_content:
                    messages.append({
                        'role': 'user',
                        'content': msg_content
                    })
        elif part.startswith('**Cursor**'):
            # Extract content after **Cursor**\n\n
            content_start = part.find('**Cursor**')
            if content_start != -1:
                # Find the content after **Cursor**\n\n
                msg_content = part[content_start + 10:].strip()
                # Remove leading newlines
                msg_content = re.sub(r'^\n+', '', msg_content)
                if msg_content:
                    messages.append({
                        'role': 'assistant',
                        'content': msg_content
                    })
    
    print(f"Parsed {len(messages)} messages")
    return {
        'title': title,
        'export_date': export_date,
        'messages': messages
    }


def get_workspace_id() -> str:
    """Get the current workspace ID from Cursor's database."""
    conn = sqlite3.connect(CURSOR_DB_PATH)
    cursor = conn.cursor()
    
    # Try to find a workspace ID from existing entries
    cursor.execute("SELECT key FROM cursorDiskKV WHERE key LIKE 'bubbleId:%' LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        # Extract workspace ID from key format: bubbleId:workspaceId:conversationId
        parts = row[0].split(':')
        if len(parts) >= 2:
            return parts[1]
    
    # Generate a new workspace ID if we can't find one
    return str(uuid.uuid4())


def create_rich_text_node(text: str) -> Dict[str, Any]:
    """Create a rich text node structure for Cursor."""
    return {
        "root": {
            "children": [{
                "children": [{
                    "detail": 0,
                    "format": 0,
                    "mode": "normal",
                    "style": "",
                    "text": text,
                    "type": "text",
                    "version": 1
                }],
                "direction": "ltr",
                "format": "",
                "indent": 0,
                "type": "paragraph",
                "version": 1
            }],
            "direction": "ltr",
            "format": "",
            "indent": 0,
            "type": "root",
            "version": 1
        }
    }


def create_bubble_entry(workspace_id: str, bubble_id: str, title: str, messages: List[Dict]) -> Dict[str, Any]:
    """Create a bubble entry for Cursor's database."""
    # Get the first user message as the "prompt" for the bubble
    first_user_msg = None
    for msg in messages:
        if msg['role'] == 'user':
            first_user_msg = msg['content']
            break
    
    prompt = first_user_msg or ""
    # Truncate for the text field (seems to be a preview)
    text_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
    
    # Combine all messages into a single conversation text
    conversation_text = "\n\n".join([
        f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
        for msg in messages
    ])
    
    bubble_data = {
        "_v": 2,
        "type": 1,  # Regular chat bubble
        "approximateLintErrors": [],
        "lints": [],
        "codebaseContextChunks": [],
        "commits": [],
        "pullRequests": [],
        "attachedCodeChunks": [],
        "assistantSuggestedDiffs": [],
        "gitDiffs": [],
        "interpreterResults": [],
        "images": [],
        "attachedFolders": [],
        "attachedFoldersNew": [],
        "bubbleId": bubble_id,
        "userResponsesToSuggestedCodeBlocks": [],
        "suggestedCodeBlocks": [],
        "diffsForCompressingFiles": [],
        "relevantFiles": [],
        "toolResults": [],
        "notepads": [],
        "capabilities": [],
        "capabilityStatuses": {},
        "text": text_preview,
        "richText": create_rich_text_node(conversation_text),
        "createdAt": datetime.now().isoformat() + "Z",
        "checkpointId": str(uuid.uuid4()),
        "isAgentic": False,
        "isQuickSearchQuery": False,
        "isRefunded": False,
        "editToolSupportsSearchAndReplace": False,
        "existedPreviousTerminalCommand": False,
        "existedSubsequentTerminalCommand": False,
        "unifiedMode": 0,
        "useWeb": False,
        "attachedHumanChanges": False,
        "aiWebSearchResults": [],
        "allThinkingBlocks": [],
        "attachedFileCodeChunksMetadataOnly": [],
        "attachedFileCodeChunksUris": [],
        "attachedFoldersListDirResults": [],
        "capabilitiesRan": {},
        "capabilityContexts": [],
        "consoleLogs": [],
        "context": {
            "notepads": [],
            "composers": [],
            "quotes": [],
            "selectedCommits": [],
            "selectedPullRequests": []
        },
        "contextPieces": [],
        "cursorRules": [],
        "deletedFiles": [],
        "diffHistories": [],
        "diffsSinceLastApply": [],
        "docsReferences": [],
        "documentationSelections": [],
        "editTrailContexts": [],
        "externalLinks": [],
        "fileDiffTrajectories": [],
        "humanChanges": [],
        "knowledgeItems": [],
        "multiFileLinterErrors": [],
        "projectLayouts": [],
        "recentLocationsHistory": [],
        "recentlyViewedFiles": [],
        "requestId": "",
        "summarizedComposers": [],
        "supportedTools": [],
        "tokenCount": {
            "inputTokens": 0,
            "outputTokens": 0
        },
        "tokenCountUpUntilHere": 0,
        "tokenDetailsUpUntilHere": [],
        "uiElementPicked": [],
        "webReferences": []
    }
    
    return bubble_data


def create_message_context(workspace_id: str, bubble_id: str) -> Dict[str, Any]:
    """Create a message request context entry."""
    return {
        "terminalFiles": [],
        "cursorRules": [],
        "attachedFoldersListDirResults": [],
        "summarizedComposers": []
    }


def check_database_lock() -> bool:
    """Check if the database is locked (Cursor is running)."""
    try:
        conn = sqlite3.connect(CURSOR_DB_PATH, timeout=1.0)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return False
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            return True
        raise


def import_chat(md_file: Path, workspace_id: Optional[str] = None) -> bool:
    """Import a markdown chat file into Cursor's database."""
    if not md_file.exists():
        print(f"Error: File not found: {md_file}")
        return False
    
    # Check if database is locked
    print("Checking if Cursor database is accessible...")
    if check_database_lock():
        print("❌ ERROR: Cursor database is locked!")
        print("   Cursor must be closed before importing chats.")
        print("   Please:")
        print("   1. Close Cursor completely")
        print("   2. Run this script again")
        return False
    
    # Parse the markdown file
    chat_data = parse_markdown_chat(md_file)
    
    if not chat_data['messages']:
        print("Error: No messages found in the chat file")
        return False
    
    # Get or generate workspace ID
    if not workspace_id:
        workspace_id = get_workspace_id()
    
    print(f"Using workspace ID: {workspace_id}")
    
    # Generate a bubble ID for this conversation
    bubble_id = str(uuid.uuid4())
    print(f"Creating bubble with ID: {bubble_id}")
    
    # Create database entries
    bubble_data = create_bubble_entry(
        workspace_id,
        bubble_id,
        chat_data['title'],
        chat_data['messages']
    )
    
    message_context = create_message_context(workspace_id, bubble_id)
    
    # Backup the database first
    print(f"Backing up database to {CURSOR_DB_BACKUP_PATH}")
    import shutil
    shutil.copy2(CURSOR_DB_PATH, CURSOR_DB_BACKUP_PATH)
    
    # Connect to database and insert
    print("Inserting chat into database...")
    conn = sqlite3.connect(CURSOR_DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Insert bubble entry
        bubble_key = f"bubbleId:{workspace_id}:{bubble_id}"
        cursor.execute(
            "INSERT OR REPLACE INTO cursorDiskKV (key, value) VALUES (?, ?)",
            (bubble_key, json.dumps(bubble_data))
        )
        
        # Insert message context entry
        context_key = f"messageRequestContext:{workspace_id}:{bubble_id}"
        cursor.execute(
            "INSERT OR REPLACE INTO cursorDiskKV (key, value) VALUES (?, ?)",
            (context_key, json.dumps(message_context))
        )
        
        conn.commit()
        print(f"✅ Successfully imported chat!")
        print(f"   Title: {chat_data['title']}")
        print(f"   Messages: {len(chat_data['messages'])}")
        print(f"   Bubble ID: {bubble_id}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error importing chat: {e}")
        print(f"   Database backup available at: {CURSOR_DB_BACKUP_PATH}")
        return False
    finally:
        conn.close()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python import_cursor_chat.py <markdown_file>")
        print(f"\nExample:")
        print(f"  python import_cursor_chat.py '/mnt/c/Users/digit/OneDrive/Stanford/cursor_identify_es_co_audio_clips_witho.md'")
        sys.exit(1)
    
    md_file = Path(sys.argv[1])
    
    if not md_file.exists():
        print(f"Error: File not found: {md_file}")
        sys.exit(1)
    
    print("=" * 60)
    print("Cursor Chat Importer")
    print("=" * 60)
    print(f"Database: {CURSOR_DB_PATH}")
    print(f"Chat file: {md_file}")
    print("=" * 60)
    print()
    
    # Confirm before proceeding
    response = input("This will modify Cursor's database. Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        sys.exit(0)
    
    success = import_chat(md_file)
    
    if success:
        print("\n✅ Import complete! Restart Cursor to see the imported chat.")
    else:
        print("\n❌ Import failed. Check the error messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

