import json, re, html

# Load the original songs_data.js
with open('songs_data_raw.js', 'r', encoding='utf-8') as f:
    data = f.read()

# Extract the array literal
export_start = data.find('export const songsData =')
array_start = data.find('[', export_start) + 1
array_end = data.rfind(']')
array_text = data[array_start:array_end]

# Parse as JSON
songs = json.loads('[' + array_text + ']')

# Compile regex for removing HTML tags
TAG_RE = re.compile(r'<[^>]+>')

# Helper to clean author strings

def clean_author(author: str, year: str) -> tuple[str, str]:
    """Return cleaned author and optional alternate name.
    """
    import unicodedata
    # Preserve original cleaned string for alternate
    original = author
    # Decode HTML entities
    author = html.unescape(author)
    # Strip any remaining tags
    author = TAG_RE.sub('', author)
    # Strip trailing year block if present
    if re.search(r'\(\d{4}[-–]\d{0,4}\)$', author):
        author = re.sub(r'\s*\(\d{4}[-–]\d{0,4}\)$', '', author)
    # Find alternate parenthetical at the end
    alt_match = re.search(r'\([^)]*\)$', author)
    alternate = None
    if alt_match:
        # Include parentheses in alternate
        alternate = original
        # Remove the alternate part from author
        author = author[:alt_match.start()].strip()
    else:
        # No alternate; keep author as is
        pass
    # Convert main author to ASCII (remove accents)
    ascii_author = unicodedata.normalize('NFKD', author).encode('ascii', 'ignore').decode('ascii')
    ascii_author = ascii_author.strip()
    return ascii_author, alternate


# Process all songs
for song in songs:
    if 'title' in song:
        song['title'] = html.unescape(song['title'])


    if 'author' in song:
        ascii_author, alternate = clean_author(song['author'], song.get('author_years', ''))
        song['author'] = ascii_author
        if alternate:
            song['author_alternate'] = alternate
        else:
            song['author_alternate'] = ascii_author

# Write cleaned data to a new file
with open('songs_data.js', 'w', encoding='utf-8') as f:
    f.write('export const songsData = [\n')
    for i, song in enumerate(songs):
        f.write(json.dumps(song, ensure_ascii=False, indent=2))
        if i < len(songs)-1:
            f.write(',\n')
    f.write('\n];\n')

print('Cleaned file written to songs_data.js')