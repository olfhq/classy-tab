#!/usr/bin/env python3
"""
py_split_authors.py

Reads the body‑only HTML of a classical guitar tablature collection
(e.g. “songs.htm”) and splits it into one file per composer.
The files are written to the already‑created directory
`songs_authors` as <integer>.htm (e.g. 0.htm, 1.htm, …).

Rules
-----
* A line that starts with <b…> marks a new composer.
* All following lines that start with <a href…> until the next <b…>
  belong to that composer.
* Authors that have no direct <a href…> lines are ignored.
* The integer file name is simply a counter that increments for every
  author that actually has songs.

Author lines may contain extra text (e.g. years, “?‑see” etc.) – the
entire line is preserved in the output file.  Song lines are written
unchanged.  Blank lines and other HTML fragments are omitted.

The script is deliberately simple – it processes the file line‑by‑line
and does not attempt to parse the underlying HTML structure beyond
the simple rules above.
"""

import os


INPUT_FILE   = "songs.htm"          # the file containing <body> content
OUTPUT_DIR   = "songs_authors"      # directory already created
FILE_EXT     = ".htm"


def write_author_file(index: int, author_line: str, song_lines: list[str]) -> None:
    """
    Write the collected block (author line + songs) to a file
    named "<index>.htm" inside OUTPUT_DIR.
    """
    path = os.path.join(OUTPUT_DIR, f"{index}{FILE_EXT}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(author_line.rstrip("\n") + "\n")
        for song in song_lines:
            f.write(song.rstrip("\n") + "\n")


def main() -> None:
    if not os.path.isdir(OUTPUT_DIR):
        raise FileNotFoundError(f"Output directory {OUTPUT_DIR!r} does not exist")

    counter          = 0            # file name counter
    current_author   = None         # current author line
    current_songs    = []           # list of song lines for current author

    with open(INPUT_FILE, "r", encoding="utf-8") as fin:
        for raw_line in fin:
            line = raw_line.rstrip("\n")

            # New author line – lines that start with <b
            if line.lstrip().startswith("<b"):
                # Finish previous author (if it had any songs)
                if current_author and current_songs:
                    write_author_file(counter, current_author, current_songs)
                    counter += 1

                # Start new author block
                current_author = line
                current_songs  = []
                continue

            # Song line – lines that start with <a href
            if line.lstrip().startswith("<a"):
                if current_author:          # only add if we are inside an author block
                    current_songs.append(line)
                continue

            # All other lines are ignored (e.g. “see …”, blank lines, etc.)

    # Handle the very last author block
    if current_author and current_songs:
        write_author_file(counter, current_author, current_songs)


if __name__ == "__main__":
    main()
