import json
import re
import html
import os
import unicodedata

# Determine source data file (prefer raw if available, else current songs_data.js)
source_file = 'songs_data_raw.js' if os.path.exists('songs_data_raw.js') else 'songs_data.js'
print(f"Reading songs dataset from: {source_file}")

with open(source_file, 'r', encoding='utf-8') as f:
    data = f.read()

# Extract array literal
export_start = data.find('export const songsData =')
array_start = data.find('[', export_start) + 1
array_end = data.rfind(']')
array_text = data[array_start:array_end]

# Parse as JSON
songs = json.loads('[' + array_text + ']')

TAG_RE = re.compile(r'<[^>]+>')

def clean_html(text: str) -> str:
    """Recursively decode HTML entities, strip residual HTML tags, and normalize spaces."""
    if not text:
        return ''
    prev = None
    curr = str(text)
    # Recursively unescape in case of nested/double entity encoding
    while prev != curr:
        prev = curr
        curr = html.unescape(curr)
    curr = TAG_RE.sub('', curr)
    curr = curr.replace('\xa0', ' ')
    curr = re.sub(r'\s+', ' ', curr)
    return curr.strip()

def clean_author(author: str, year: str) -> tuple[str, str]:
    """Return cleaned ASCII author and decoded alternate name."""
    original = clean_html(author)
    author_clean = original

    # Strip trailing year block if present
    if re.search(r'\(\d{4}[-–]\d{0,4}\)$', author_clean):
        author_clean = re.sub(r'\s*\(\d{4}[-–]\d{0,4}\)$', '', author_clean)

    # Find alternate parenthetical at the end
    alt_match = re.search(r'\([^)]*\)$', author_clean)
    alternate = None
    if alt_match:
        alternate = original
        author_clean = author_clean[:alt_match.start()].strip()
    
    # Convert main author to ASCII
    ascii_author = unicodedata.normalize('NFKD', author_clean).encode('ascii', 'ignore').decode('ascii').strip()
    return ascii_author, alternate

missing_tabs = []
missing_midis = []
valid_tabs_count = 0
valid_midis_count = 0

print("Processing and sanitizing song records...")

for song in songs:
    # 1. Sanitize Title
    if 'title' in song and song['title']:
        song['title'] = clean_html(song['title'])

    # 2. Sanitize Author & Author Alternate
    if 'author' in song and song['author']:
        ascii_author, alternate = clean_author(song['author'], song.get('author_years', ''))
        song['author'] = ascii_author
        if 'author_alternate' in song and song['author_alternate']:
            song['author_alternate'] = clean_html(song['author_alternate'])
        elif alternate:
            song['author_alternate'] = clean_html(alternate)
        else:
            song['author_alternate'] = ascii_author

    # 3. Sanitize Artist
    if 'artist' in song and song['artist']:
        song['artist'] = clean_html(song['artist'])

    # 4. Normalize MIDI field
    midi_val = song.get('midi')
    if isinstance(midi_val, list):
        # If list, take first valid .mid filename
        found_mid = next((m for m in midi_val if isinstance(m, str) and m.strip().endswith('.mid')), "")
        song['midi'] = found_mid
    elif isinstance(midi_val, str):
        song['midi'] = midi_val.strip()
    else:
        song['midi'] = ""

    # 5. Verify Tab file exists in tabs/
    tab_file = song.get('tab', '').strip()
    if tab_file and os.path.isfile(os.path.join('tabs', tab_file)):
        valid_tabs_count += 1
    else:
        missing_tabs.append({
            'author': song.get('author'),
            'title': song.get('title'),
            'tab': tab_file
        })

    # 6. Verify MIDI file exists in midi/ (if specified)
    if song['midi']:
        if os.path.isfile(os.path.join('midi', song['midi'])):
            valid_midis_count += 1
        else:
            missing_midis.append({
                'author': song.get('author'),
                'title': song.get('title'),
                'midi': song['midi']
            })

# Write cleaned data back to songs_data.js
output_file = 'songs_data.js'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('export const songsData = [\n')
    for i, song in enumerate(songs):
        f.write(json.dumps(song, ensure_ascii=False, indent=2))
        if i < len(songs) - 1:
            f.write(',\n')
    f.write('\n];\n')

print("\n" + "=" * 55)
print("           DATA SANITIZATION REPORT")
print("=" * 55)
print(f"Total songs processed:      {len(songs)}")
print(f"Tabs verified on disk:      {valid_tabs_count} / {len(songs)}")
print(f"Missing tabs detected:      {len(missing_tabs)}")
print(f"MIDIs verified on disk:     {valid_midis_count}")
print(f"Missing MIDIs detected:     {len(missing_midis)}")
print("=" * 55)

if missing_tabs:
    print(f"\nMissing Tabs Sample (First {min(10, len(missing_tabs))}):")
    for mt in missing_tabs[:10]:
        print(f"  - [{mt['author']}] \"{mt['title']}\" -> {mt['tab']}")

if missing_midis:
    print(f"\nMissing MIDIs Sample (First {min(10, len(missing_midis))}):")
    for mm in missing_midis[:10]:
        print(f"  - [{mm['author']}] \"{mm['title']}\" -> {mm['midi']}")

print(f"\nSanitized database successfully written to {output_file}")
