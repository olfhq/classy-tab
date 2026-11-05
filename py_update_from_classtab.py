#!/usr/bin/env python3
"""
py_update_from_classtab.py - Incrementally update Classtab UI with new additions from https://www.classtab.org/

Usage:
    python3 py_update_from_classtab.py --dry-run
    python3 py_update_from_classtab.py
    python3 py_update_from_classtab.py --limit 10
"""

import argparse
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

BASE_URL = "https://www.classtab.org/"
RECENT_URL = "https://www.classtab.org/tabadd.htm"
SONGS_DATA_PATH = "songs_data.js"
TABS_DIR = "tabs"
MIDI_DIR = "midi"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
}

def fetch_url(url: str) -> str:
    """Fetch text content from a remote URL."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='ignore')

def download_file(url: str, dest_path: str):
    """Download a binary/text file from URL to dest_path."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp, open(dest_path, 'wb') as out_f:
        out_f.write(resp.read())

def get_recent_additions_url(base_url: str) -> str:
    """Fetch base page and parse the 'What's New' / recent additions link."""
    try:
        page_html = fetch_url(base_url)
        m = re.search(r'<a\s+href=[\"\']([^\"\']+)[\"\']>[^<]*(?:recent|addition|what[\'s\s]*new)[^<]*</a>', page_html, re.IGNORECASE)
        if m:
            return urllib.parse.urljoin(base_url, m.group(1))
    except Exception as e:
        print(f"Notice: Using default recent URL ({e})", file=sys.stderr)
    return RECENT_URL

def load_existing_songs(path: str = SONGS_DATA_PATH) -> tuple[list[dict], set[str], dict[str, str]]:
    """Read songs_data.js and return songs list, existing tab set, and author->years map."""
    if not os.path.exists(path):
        return [], set(), {}
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    start = content.find('[')
    end = content.rfind(']') + 1
    songs = json.loads(content[start:end])
    existing_tabs = {s['tab'].strip() for s in songs if s.get('tab') and isinstance(s.get('tab'), str)}
    author_years_map = {}
    for s in songs:
        author = s.get('author')
        years = s.get('author_years')
        if author and years and author.lower() not in author_years_map:
            author_years_map[author.lower()] = years
    return songs, existing_tabs, author_years_map

def clean_author_name(author: str) -> str:
    """Convert author name to clean ASCII string."""
    author = html.unescape(author)
    author = re.sub(r'<[^>]+>', '', author)
    # Remove accents
    ascii_author = unicodedata.normalize('NFKD', author).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', ascii_author).strip()

def parse_recent_additions(page_html: str, base_url: str) -> list[dict]:
    """Parse tabadd.htm into structured candidate song dictionaries."""
    lines = re.split(r'<br\s*/?>|\n', page_html)
    candidates = []

    for line in lines:
        tab_match = re.search(r'<a\s+href=[\"\']([^\"\']+\.txt)[\"\']>([^<]+)</a>', line, re.IGNORECASE)
        if not tab_match:
            continue

        tab_rel = tab_match.group(1).strip()
        raw_text = html.unescape(tab_match.group(2).strip())

        # Check for MIDI link
        midi_match = re.search(r'<a\s+href=[\"\']([^\"\']+\.mid)[\"\']>([^<]*)</a>', line, re.IGNORECASE)
        midi_rel = midi_match.group(1).strip() if midi_match else ''

        # Check for Easy difficulty indicator
        is_easy = bool(re.search(r'\b(easy)\b', line, re.IGNORECASE))

        # Check for Left Hand Fingering (LHF) indicator
        is_lhf = bool(re.search(r'\b(lhf)\b', line, re.IGNORECASE))

        # Check for Video / Audio link and artist
        vid_match = re.search(r'\[(?:vid|video|audio)[\s\):]*\s*<a\s+href=[\"\']([^\"\']+)[\"\']>([^<]*)</a>', line, re.IGNORECASE)
        video_url = vid_match.group(1).strip() if vid_match else ''
        artist = html.unescape(vid_match.group(2).strip()) if vid_match else ''

        # Extract Author and Title from anchor text
        if ' - ' in raw_text:
            parts = raw_text.split(' - ', 1)
            raw_author = parts[0].strip()
            title = parts[1].strip()
        elif '(trad.)' in raw_text.lower():
            raw_author = 'Anonymous / Traditional'
            title = re.sub(r'\(trad\.?\)', '', raw_text, flags=re.IGNORECASE).strip()
        else:
            raw_author = 'Unknown Composer'
            title = raw_text

        author = clean_author_name(raw_author)
        title = html.unescape(title)

        candidates.append({
            'tab_filename': tab_rel,
            'tab_url': urllib.parse.urljoin(base_url, tab_rel),
            'midi_filename': midi_rel,
            'midi_url': urllib.parse.urljoin(base_url, midi_rel) if midi_rel else '',
            'author': author,
            'author_alternate': raw_author,
            'title': title,
            'easy': is_easy,
            'lhf': is_lhf,
            'video': video_url,
            'artist': artist,
        })

    return candidates

def inspect_downloaded_tab(tab_text: str, current_lhf: bool, author: str, author_years_map: dict[str, str]) -> tuple[bool, str]:
    """Inspect downloaded tab text to infer fingering and composer lifespan years."""
    lhf = current_lhf
    if not lhf:
        if re.search(r'\b(lhf|left\s*hand\s*finger(ing)?)\b', tab_text, re.IGNORECASE):
            lhf = True

    # Infer author years: first from known authors map, then from tab header
    author_years = author_years_map.get(author.lower(), "")
    if not author_years:
        header = "\n".join(tab_text.splitlines()[:30])
        year_match = re.search(r'\((\d{4}[-–]\d{0,4})\)', header)
        if year_match:
            author_years = f"({year_match.group(1)})"

    return lhf, author_years

def save_songs_data(songs: list[dict], path: str = SONGS_DATA_PATH):
    """Write songs list back to songs_data.js maintaining ES module export syntax."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write('export const songsData = [\n')
        for i, s in enumerate(songs):
            f.write(json.dumps(s, ensure_ascii=False, indent=2))
            if i < len(songs) - 1:
                f.write(',\n')
        f.write('\n];\n')

def main():
    parser = argparse.ArgumentParser(description="Incrementally update Classtab library from https://www.classtab.org/")
    parser.add_argument('--dry-run', action='store_true', help="Preview detected new additions without downloading files or modifying database")
    parser.add_argument('--limit', type=int, default=0, help="Limit number of new songs to download/ingest (0 = all)")
    args = parser.parse_args()

    print("=" * 60)
    print("      CLASSTAB INCREMENTAL UPDATE ENGINE")
    print("=" * 60)

    # 1. Load existing database
    print(f"Reading existing library from {SONGS_DATA_PATH}...")
    existing_songs, existing_tabs, author_years_map = load_existing_songs(SONGS_DATA_PATH)
    print(f"Found {len(existing_songs)} existing pieces ({len(existing_tabs)} unique tabs).")

    # 2. Discover and fetch recent additions page
    print(f"\nContacting {BASE_URL}...")
    recent_page_url = get_recent_additions_url(BASE_URL)
    print(f"Fetching recent additions from: {recent_page_url}")

    try:
        page_html = fetch_url(recent_page_url)
    except Exception as e:
        print(f"Error: Failed to fetch {recent_page_url}: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Parse candidates
    candidates = parse_recent_additions(page_html, recent_page_url)
    print(f"Parsed {len(candidates)} total listed pieces on the recent additions page.")

    # 4. Filter for new songs only (avoid duplicates)
    new_songs = []
    seen_in_batch = set()
    for c in candidates:
        tab_name = c['tab_filename']
        if tab_name not in existing_tabs and tab_name not in seen_in_batch:
            new_songs.append(c)
            seen_in_batch.add(tab_name)

    print(f"Found {len(new_songs)} new song addition(s) not currently in library.")

    if not new_songs:
        print("\nYour library is fully up to date! No new additions found.")
        return

    if args.limit > 0:
        new_songs = new_songs[:args.limit]
        print(f"Processing limited to first {len(new_songs)} new piece(s).")

    print("\n" + "-" * 60)
    print("NEW PIECES DETECTED:")
    print("-" * 60)
    for i, s in enumerate(new_songs, 1):
        midi_status = f"MIDI: {s['midi_filename']}" if s['midi_filename'] else "No MIDI"
        lhf_status = "LHF" if s['lhf'] else "No LHF"
        easy_status = "Easy" if s['easy'] else "Standard"
        print(f"{i:2d}. [{s['author']}] \"{s['title']}\"")
        print(f"    Tab: {s['tab_filename']} | {midi_status} | {lhf_status} | {easy_status}")
        if s['video']:
            print(f"    Video: {s['video']} ({s['artist']})")

    # Dry-run check
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY-RUN MODE: No files downloaded and songs_data.js was NOT modified.")
        print("Run without --dry-run to download tabs/MIDIs and update library.")
        print("=" * 60)
        return

    # 5. Process and download each new piece
    os.makedirs(TABS_DIR, exist_ok=True)
    os.makedirs(MIDI_DIR, exist_ok=True)

    ingested_records = []
    print("\n" + "=" * 60)
    print("DOWNLOADING & INGESTING NEW PIECES:")
    print("=" * 60)

    for i, s in enumerate(new_songs, 1):
        tab_file = s['tab_filename']
        dest_tab_path = os.path.join(TABS_DIR, tab_file)
        dest_midi_path = os.path.join(MIDI_DIR, s['midi_filename']) if s['midi_filename'] else ""

        print(f"[{i}/{len(new_songs)}] Downloading tab: {s['tab_url']}...")
        tab_text = ""
        try:
            download_file(s['tab_url'], dest_tab_path)
            with open(dest_tab_path, 'r', encoding='utf-8', errors='ignore') as f:
                tab_text = f.read()
        except Exception as e:
            print(f"  Warning: Failed to download tab {s['tab_url']}: {e}", file=sys.stderr)
            continue

        # Download MIDI if available
        if s['midi_filename']:
            print(f"         Downloading MIDI: {s['midi_url']}...")
            try:
                download_file(s['midi_url'], dest_midi_path)
            except Exception as e:
                print(f"  Warning: Failed to download MIDI {s['midi_url']}: {e}", file=sys.stderr)
                s['midi_filename'] = ""

        # Infer LHF and author_years from tab text
        is_lhf, author_years = inspect_downloaded_tab(tab_text, s['lhf'], s['author'], author_years_map)

        new_record = {
            "author": s['author'],
            "author_years": author_years,
            "title": s['title'],
            "tab": tab_file,
            "midi": s['midi_filename'],
            "video": s['video'],
            "artist": s['artist'],
            "easy": s['easy'],
            "lhf": is_lhf,
            "proper": True,
            "author_id": "",
            "author_alternate": s['author_alternate']
        }
        ingested_records.append(new_record)
        existing_songs.append(new_record)

        # Brief rate-limiting pause
        time.sleep(0.3)

    # 6. Save updated database
    if ingested_records:
        print(f"\nWriting {len(ingested_records)} new record(s) to {SONGS_DATA_PATH}...")
        save_songs_data(existing_songs, SONGS_DATA_PATH)
        print(f"Update complete! Total pieces in library: {len(existing_songs)}.")
    else:
        print("\nNo records were successfully downloaded.")

if __name__ == '__main__':
    main()
