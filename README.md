# Classtab UI

A lightweight, static web interface for browsing and playing classical guitar tablature from the [Classtab](https://classtab.com) website.

## What is this?

The original Classtab site hosts a large collection of guitar tablature in a single, monolithic HTML page.  This repository contains a **cleaned‑up, split‑up** version of that data and a small front‑end that:

* Lists songs grouped by author.
* Allows quick filtering by author, difficulty, video availability, and bookmarks.
* Shows a table with columns for **Author**, **Title**, **Easy**, **LHF**, **MIDI**, and **Video**.
* Opens the corresponding `.txt` tablature file in a side‑panel when a title is clicked.

The UI is built with plain HTML, CSS and vanilla JavaScript – no build step or dependencies are required.

## Getting started

The repository contains two main folders:

* `tabs/` – contains all the `.txt` tablature files.
* `midi/` – contains all the `.mid` MIDI files.

### 1. Serve the site locally

The simplest way to view the UI is to run a local HTTP server.  Two common options are shown below.

#### Python 3 (recommended)

```bash
python -m http.server 8000
```

Open your browser to `http://localhost:8000/index.html`.

#### Node.js (http-server)

If you have Node.js installed you can use the `http-server` package:

```bash
npm install -g http-server
http-server -p 8000
```

Again, visit `http://localhost:8000/index.html`.

### 2. Using the UI

* **Author filter** – type an author’s name (or part of it) into the text box.
* **Easy / Video** – toggle the checkboxes to show only easy songs or songs that have a YouTube video.
* **Bookmarks** – click the star icon next to a song to bookmark it.  Bookmarks are stored in `localStorage` and persist across page reloads.
* **Tabs panel** – click a song title to load the corresponding `.txt` file in the right‑hand panel.

## How the data was generated

1. **Download the original Classtab page** – the raw HTML was saved locally.
2. **Split the page** – `py_split_authors.py` parsed the HTML and created a set of files in the `songs_html_chunks` directory (each ~500 lines of code).  These files are not committed to the repo.
3. **Process with LLM** – `py_process_all_llm.py` ran a language‑model pipeline on the chunks, producing `songs_json` and `songs_data_raw.js`.
4. **Clean up** – `py_clean_songs.py` cleaned author and title fields, producing `songs_data.js`, which is used by `index.html`.
5. **Manual tweaks** – the UI was built and the file renamed to `index.html`.

Feel free to explore the scripts if you want to regenerate the data or adapt the pipeline for other sources.

---

**Author:** mathybit

**License:** The code in this repository is licensed under the Creative Commons Attribution‑NonCommercial 4.0 International (CC BY‑NC 4.0).  The tablature files are governed by the original Classtab website’s license.
See the full license text in the [LICENSE](LICENSE) file.

**Note:** The song data snapshot was taken from the Classtab website in January 2026.  It may not include songs added after that date.
