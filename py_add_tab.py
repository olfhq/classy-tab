#!/usr/bin/env python3
"""
py_add_tab.py - Automated Tab & MIDI Ingestion Helper for Classtab UI

Usage:
    python3 py_add_tab.py path/to/tab.txt [--midi path/to/song.mid]
    python3 py_add_tab.py path/to/tab.txt --author "Francisco Tarrega" --title "Adelita" --easy --lhf --non-interactive
"""

import argparse
import json
import os
import re
import shutil
import sys
import unicodedata

SONGS_DATA_PATH = 'songs_data.js'
TABS_DIR = 'tabs'
MIDI_DIR = 'midi'

def slugify(text: str) -> str:
    """Convert text to safe lowercase ASCII slug with underscores."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

def get_known_authors() -> list[str]:
    """Extract list of known authors from songs_data.js for matching heuristics."""
    if not os.path.exists(SONGS_DATA_PATH):
        return []
    try:
        with open(SONGS_DATA_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        start = content.find('[')
        end = content.rfind(']') + 1
        data = json.loads(content[start:end])
        authors = sorted({s.get('author') for s in data if s.get('author')}, key=lambda x: -len(x))
        return authors
    except Exception:
        return []

def inspect_tab_header(file_path: str, known_authors: list[str]) -> dict:
    """Analyze the top header lines of a tablature file to extract metadata."""
    guesses = {
        'title': '',
        'author': '',
        'tuning': '',
        'lhf': False,
        'easy': False
    }

    if not os.path.isfile(file_path):
        return guesses

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        header_lines = [f.readline().rstrip() for _ in range(40)]

    header_text = "\n".join(header_lines)

    # 1. Left Hand Fingering (LHF) detection
    if re.search(r'\b(lhf|left\s*hand\s*finger(ing)?)\b', header_text, re.IGNORECASE):
        guesses['lhf'] = True

    # 2. Easy difficulty detection
    if re.search(r'\b(easy|beginner|facile|elementarstufe|grade\s*1)\b', header_text, re.IGNORECASE):
        guesses['easy'] = True

    # 3. Tuning detection
    tuning_m = re.search(r'(tuning|tune|standard|drop\s*d|dadgbe|eadgbe)[\s:\-]+([^\r\n]+)', header_text, re.IGNORECASE)
    if tuning_m:
        guesses['tuning'] = tuning_m.group(0).strip()

    # 4. Explicit Author and Title labels
    for line in header_lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        # Check for Title: ...
        title_m = re.match(r'^(?:title|piece|song|name)\s*:\s*(.+)$', clean_line, re.IGNORECASE)
        if title_m and not guesses['title']:
            guesses['title'] = title_m.group(1).strip()

        # Check for Composer: / Author: ...
        author_m = re.match(r'^(?:composer|author|music\s+by|arranged\s+by|arr\.?)\s*:\s*(.+)$', clean_line, re.IGNORECASE)
        if author_m and not guesses['author']:
            guesses['author'] = author_m.group(1).strip()

    # 5. Known author cross-reference
    if not guesses['author']:
        for author in known_authors:
            # Check for author name in header text (whole-word boundary)
            pattern = r'\b' + re.escape(author) + r'\b'
            if re.search(pattern, header_text, re.IGNORECASE):
                guesses['author'] = author
                break

    # 6. Fallback line heuristics if title or author still blank
    non_empty = [l.strip() for l in header_lines if l.strip() and not l.strip().startswith('---')]
    if not guesses['title'] and non_empty:
        # Often the first non-empty line is the title
        candidate = non_empty[0]
        # Remove common delimiters
        candidate = re.sub(r'^[#=*\s]+|[#=*\s]+$', '', candidate)
        if ' by ' in candidate.lower():
            parts = re.split(r'\s+by\s+', candidate, flags=re.IGNORECASE)
            guesses['title'] = parts[0].strip()
            if not guesses['author'] and len(parts) > 1:
                guesses['author'] = parts[1].strip()
        elif ' - ' in candidate:
            parts = candidate.split(' - ', 1)
            # If part 0 matches a known author, part 1 is title
            if any(p.lower() in parts[0].lower() for p in known_authors):
                guesses['author'] = parts[0].strip()
                guesses['title'] = parts[1].strip()
            else:
                guesses['title'] = candidate
        else:
            guesses['title'] = candidate

    return guesses

def generate_unique_filename(directory: str, author: str, title: str, extension: str) -> str:
    """Generate normalized filename (e.g. tarrega_adelita.txt), appending index if collision exists."""
    author_parts = author.strip().split()
    author_slug = slugify(author_parts[-1]) if author_parts else 'unknown'
    title_slug = slugify(title) or 'untitled'
    base = f"{author_slug}_{title_slug}"

    candidate = f"{base}.{extension.lstrip('.')}"
    counter = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{base}_{counter}.{extension.lstrip('.')}"
        counter += 1
    return candidate

def prompt_value(prompt_text: str, default: str) -> str:
    """Interactive input prompt with default value."""
    display_default = f" [{default}]" if default != '' else ""
    val = input(f"{prompt_text}{display_default}: ").strip()
    return val if val else default

def prompt_bool(prompt_text: str, default: bool) -> bool:
    """Interactive boolean prompt with default value."""
    default_str = 'y' if default else 'n'
    val = input(f"{prompt_text} (y/n) [{default_str}]: ").strip().lower()
    if not val:
        return default
    return val in ('y', 'yes', 'true', '1')

def append_to_songs_data(record: dict, prepend: bool = False):
    """Safely append or prepend a new song record to songs_data.js."""
    if not os.path.exists(SONGS_DATA_PATH):
        songs = [record]
    else:
        with open(SONGS_DATA_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        start = content.find('[')
        end = content.rfind(']') + 1
        songs = json.loads(content[start:end])
        if prepend:
            songs.insert(0, record)
        else:
            songs.append(record)

    with open(SONGS_DATA_PATH, 'w', encoding='utf-8') as f:
        f.write('export const songsData = [\n')
        for i, s in enumerate(songs):
            f.write(json.dumps(s, ensure_ascii=False, indent=2))
            if i < len(songs) - 1:
                f.write(',\n')
        f.write('\n];\n')

def main():
    parser = argparse.ArgumentParser(description="Ingest new Classical Guitar Tab & MIDI files into Classtab")
    parser.add_argument('tab_path', help="Path to the source .txt tablature file")
    parser.add_argument('--midi', help="Optional path to source .mid MIDI file", default="")
    parser.add_argument('--author', help="Composer / Author name", default="")
    parser.add_argument('--title', help="Song / Work Title", default="")
    parser.add_argument('--easy', action=argparse.BooleanOptionalAction, default=None, help="Set easy difficulty flag")
    parser.add_argument('--lhf', action=argparse.BooleanOptionalAction, default=None, help="Set Left-Hand Fingering flag")
    parser.add_argument('--video', help="Optional YouTube Video URL", default="")
    parser.add_argument('--artist', help="Optional Performer / Artist credit", default="")
    parser.add_argument('--prepend', action='store_true', help="Prepend song to list instead of appending")
    parser.add_argument('-y', '--non-interactive', action='store_true', help="Run without interactive confirmation prompts")

    args = parser.parse_args()

    if not os.path.isfile(args.tab_path):
        print(f"Error: Tab file not found: {args.tab_path}", file=sys.stderr)
        sys.exit(1)

    if args.midi and not os.path.isfile(args.midi):
        print(f"Error: MIDI file not found: {args.midi}", file=sys.stderr)
        sys.exit(1)

    # Make sure target directories exist
    os.makedirs(TABS_DIR, exist_ok=True)
    os.makedirs(MIDI_DIR, exist_ok=True)

    known_authors = get_known_authors()
    guesses = inspect_tab_header(args.tab_path, known_authors)

    # Initial values
    author = args.author or guesses['author'] or "Unknown Composer"
    title = args.title or guesses['title'] or os.path.splitext(os.path.basename(args.tab_path))[0]
    is_easy = args.easy if args.easy is not None else guesses['easy']
    is_lhf = args.lhf if args.lhf is not None else guesses['lhf']
    video = args.video
    artist = args.artist

    is_interactive = not args.non_interactive and sys.stdin.isatty()

    if is_interactive:
        print("\n" + "=" * 55)
        print("          CLASSTAB INGESTION WIZARD")
        print("=" * 55)
        print(f"Source Tab:  {args.tab_path}")
        if guesses.get('tuning'):
            print(f"Tuning Info: {guesses['tuning']}")
        if args.midi:
            print(f"Source MIDI: {args.midi}")
        print("-" * 55)

        author = prompt_value("Composer / Author", author)
        title = prompt_value("Song / Work Title", title)
        is_easy = prompt_bool("Easy piece?", is_easy)
        is_lhf = prompt_bool("Contains LHF (Left Hand Fingering)?", is_lhf)
        video = prompt_value("YouTube Video URL (optional)", video)
        artist = prompt_value("Performer / Artist credit (optional)", artist)

        print("-" * 55)
        confirm = prompt_bool("Confirm and ingest into Classtab?", True)
        if not confirm:
            print("Ingestion cancelled.")
            sys.exit(0)

    # 1. Normalize and copy tab file
    target_tab_filename = generate_unique_filename(TABS_DIR, author, title, 'txt')
    dest_tab_path = os.path.join(TABS_DIR, target_tab_filename)
    shutil.copyfile(args.tab_path, dest_tab_path)
    print(f"-> Copied tab to: {dest_tab_path}")

    # 2. Normalize and copy MIDI file (if provided)
    target_midi_filename = ""
    if args.midi:
        target_midi_filename = generate_unique_filename(MIDI_DIR, author, title, 'mid')
        dest_midi_path = os.path.join(MIDI_DIR, target_midi_filename)
        shutil.copyfile(args.midi, dest_midi_path)
        print(f"-> Copied MIDI to: {dest_midi_path}")

    # 3. Create record
    new_record = {
        "author": author,
        "author_years": "",
        "title": title,
        "tab": target_tab_filename,
        "midi": target_midi_filename,
        "video": video,
        "artist": artist,
        "easy": is_easy,
        "lhf": is_lhf,
        "proper": True,
        "author_id": "",
        "author_alternate": author
    }

    # 4. Save to songs_data.js
    append_to_songs_data(new_record, prepend=args.prepend)
    print(f"-> Record successfully added to {SONGS_DATA_PATH}!")
    print("\nRecord Summary:")
    print(json.dumps(new_record, indent=2))

if __name__ == '__main__':
    main()
