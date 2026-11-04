prompt_template = """
==== BACKGROUND ====

I have the HTML source code from the "<body>" of a website for classical guitar tablature ("tab"). 
The HTML source code contains author/composer information, together with a list of songs. Each song 
links to its respective tablature files. 


==== TASK ====

Parse the source code and extract the following information for each song present in the source code:
- the author (composer) name
- the years during which the author lived (if applicable)
- the song title
- the song tablature file name (if available): this is inside a <a href> tag pointing to a ".txt" file
- the song MIDI (if available): this is inside a <a href> tag too, pointing to ".mid" files
- any video link (if present): these appear like [vid: <a href .... >Artist name</a> in the code
- whether the song is "easy" or not, which appears as [<b>easy</b>] somewhere on the same line as the song
- whether the song has "LHF" (I think this means Left Hand Fingering in the tablature)

The input HTML is structured such that authors are easy to find:
- the author's name and years during which they lived appear on a single line, and that line always begins with a <b> tag. 
- There are other <b> tags in the code, but the author-related ones always start on a new line. 
- whenever a new line starts with <b>, it is an author line. 

After the author's name, a series of songs available from that composer appear, each on a separate line, with each song beginning with "<a href>" tags when the tab is available:
- each line starting with <a href="tablature_filename.txt">Song Title</a> is guaranteed to be a single song
- all the information for that song will be on that same line (there are no multi-line songs)

It is possible for a song line to have multiple <a href> tags on its line, but it must start with <a href="tablature_filename.txt">.

If it doesn't start like that, ignore the line, as it is not a proper song (i.e. its tablature is not available).

Many songs will have multiple <a> tags on the same line, because they are linking to different attributes / resources related to that 
song (MIDI, video, etc.). These attributes are essential and need to be parsed as well.


==== OUTPUT FORMAT ====

Write your output in JSON format, with each song being a JSON object capturing the following attributes:
- "author": include the whole text for the author name (this will just be repeated for each song)
- "author_years": include the parentheses for the years, or empty string of not available
- "title": the title of the song - this is the text between the <a href=".txt"> </a> tags which specify the text file corresponding to that song
- "tab": this is the tablature file - the ".txt" file specified inside the <a href".txt"></a> tag
- "midi": some songs have a "MIDI" file inside another <a href> tag on the same line, inside which the text is "MIDI"; if there is no MIDI link, use an empty string ""
- "video": some songs have a link to a YouTube video inside a <a href> tag on the same line; if there is no video link available, use an empty string
- "artist": for the songs that DO have a video link, the artist performing that song is specified inside the corresponding <a href> tag; use an empty string if no video link was available
- "easy": true or false, depending on whether the "[<b>easy</b>]" text was present on the same line for the song
- "lhf": true or false, depending on whether the "LHF" text was present on the same line for the song (it might be between <b> tags)


==== EXAMPLE INPUT ====

EXAMPLE 1
<b>Joan Ambrosio Dalza (Joanambrosio Dalza)</b>&#160; (1483-1533)<br>
<a href="dalza_prima_calata_ala_spagnola.txt">Prima Calata ala Spagnola</a> - from Intabulatura de lauto - libro quarto<br>
<a href="dalza_calata_ala_spagnola.txt">Calata ala Spagnola</a> - from Intabulatura de lauto - libro quarto<br>

EXAMPLE 2
<b>Malcolm Arnold</b>&#160; (1921-2006)<br>
<a href="arnold_malcolm_op107_fantasy_for_guitar_1_prelude.txt">Op 107, Fantasy For Guitar - 1. Prelude</a> - <b>LHF</b> - [vid: <a href="https://www.youtube.com/watch?v=yDUb2a1jSw4">Joseph Regan</a>]<br>

EXAMPLE 3
<b>Hector Ayala &#160;(H&eacute;ctor Ayala)</b>&#160; (1914-1990)<br>
<a href="ayala_el_sureno_malambo.txt">El Sure&ntilde;o - Malambo</a> (El Sureno) - <a href="ayala_el_sureno_malambo.mid">MIDI</a><br>
<a href="ayala_pequeno_preludio.txt">Peque&ntilde;o Preludio (Short Prelude)</a> - <a href="ayala_pequeno_preludio.mid">MIDI</a> - <b>LHF</b> - [<b>easy</b>] - [vid: <a href="https://www.youtube.com/watch?v=FiWKrR_EUOQ">Adri&aacute;n Bassi</a>]<br>

3XAMPLE 4
<b>Matteo Carcassi</b>&#160; (1792-1853)<br>
<a href="carcassi_op60_no07_study_in_am.txt">Op 60 Study No 7 in Am</a> - from 25 Studi Melodici e Progressivi - <a href="carcassi_op60_no07_study_in_am.mid">MIDI</a> - [<b>easy</b>] - [vid: <a href="https://www.youtube.com/watch?v=PYdIUmWIiUU&t=10s">Thu Le</a>]<br>

In these examples, we have 4 authors with specified years during which they lived:
- EXAMPLE 1: "Joan Ambrosio Dalza (Joanambrosio Dalza)", who lived during "(1483-1533)", and has 2 songs
- EXAMPLE 2: "Malcolm Arnold", who lived "(1921-2006)", and has one song
- EXAMPLE 3: "Hector Ayala &#160;(H&eacute;ctor Ayala)", who lived "(1914-1990)", and has 2 songs
- EXAMPLE 4: "Matteo Carcassi", who lived "(1792-1853)", and has one song


==== EXPECTED OUTPUT ====

EXAMPLE 1 output:
{{
    "songs": [
        {{
            "author": "Joan Ambrosio Dalza (Joanambrosio Dalza)",  # include the whole text for the author name
            "author_years": "(1483-1533)",  # include the parentheses for the years, or empty string of not available
            "title": "Prima Calata ala Spagnola",  # the title of the song (This is the text between the <a href=".txt"> </a> tags)
            "tab": "dalza_prima_calata_ala_spagnola.txt",  # this is the tablature file
            "midi": "",  # there is no MIDI file for this song -- use an empty string
            "video": "",  # there is no video link available for this song -- use an empty string
            "artist": "",  # since there is no video, there is no artist performing that video -- use an empty string
            "easy": false,
            "lhf": false,
            "proper": true  # the input follows expected pattern and could be parsed correctly
        }},
        {{
            "author": "Joan Ambrosio Dalza (Joanambrosio Dalza)",
            "author_years": "(1483-1533)",
            "title": "Calata ala Spagnola",
            "tab": "dalza_calata_ala_spagnola.txt",
            "midi": null,
            "video": "",
            "artist": "",
            "easy": false,
            "lhf": false,
            "proper": true
        }}
    ]
}}


EXAMPLE 2 output:
{{
    "songs": [
        {{
            "author": "Malcolm Arnold",
            "author_years": "(1921-2006)",
            "title": "Op 107, Fantasy For Guitar - 1. Prelude",
            "tab": "arnold_malcolm_op107_fantasy_for_guitar_1_prelude.txt",
            "midi": null,
            "video": "https://www.youtube.com/watch?v=yDUb2a1jSw4",  # this song has a video available
            "artist": "Joseph Regan",  # inside the video link, the performing artist's name is listed as Joseph Regan
            "easy": false,
            "lhf": true,  # this song also has "LHF" mentioned
            "proper": true
        }}
    ]
}}


EXAMPLE 3 output:
{{
    "songs": [
        {{
            "author": "Hector Ayala (H&eacute;ctor Ayala)",
            "author_years": "(1914-1990)",
            "title": "El Sure&ntilde;o - Malambo (El Sureno)",
            "tab": "ayala_el_sureno_malambo.txt",
            "midi": "ayala_el_sureno_malambo.mid",  # this song has a MIDI file listed
            "video": "https://www.youtube.com/watch?v=yDUb2a1jSw4",
            "artist": "Joseph Regan",
            "easy": false,
            "lhf": false,
            "proper": true
        }},
        {{
            "author": "Hector Ayala (H&eacute;ctor Ayala)",
            "author_years": "(1914-1990)",
            "title": "Peque&ntilde;o Preludio (Short Prelude)",
            "tab": "ayala_pequeno_preludio.txt",
            "midi": "ayala_pequeno_preludio.mid",
            "video": "",
            "artist": "",
            "easy": true,  # this song is listed as "easy"
            "lhf": true,  # this song also has LHF mentioned
            "proper": true
        }}
    ]
}}


EXAMPLE 4 output:
{{
    "songs": [
        {{
            "author": "Matteo Carcassi",
            "author_years": "(1792-1853)",
            "title": "Op 60 Study No 7 in Am",  # we can drop the "from 25 Studi Melodici e Progressivi" part of the title, since it is not between the <a href=".txt"> </a> tags
            "tab": "carcassi_op60_no07_study_in_am.txt",
            "midi": "carcassi_op60_no07_study_in_am.mid",
            "video": "https://www.youtube.com/watch?v=PYdIUmWIiUU&t=10s",
            "artist": "Thu Le",
            "easy": true,
            "lhf": false,
            "proper": true
        }}
    ]
}}


I will be parsing the output JSON in Python, so make sure to use double curly brackets.


==== EDGE CASES ====

1. Some of the songs have an unknown author, or come from video games or other popular media such as movie tracks:

<b>Anonymous / Traditional</b><br>
<a href="anon_adeste_fidelis_pratten_guitar_school_033.txt">Adeste Fidelis</a> (arr Catharina Josepha Pratten) - <a href="anon_adeste_fidelis_pratten_guitar_school_033.mid">MIDI</a> - Christmas carol - <b>LHF</b> - [<b>easy</b>] - [vid: <a href="https://www.youtube.com/watch?v=iLh4iLlhv6U">Norbert Neunzling</a>]<br>
<a href="anon_afro-cuban_lullaby.txt">Afro-Cuban Lullaby</a> - (see also <a href="#brouwer">Leo Brouwer "Canci&ograve;n de Cuna (Berceuse)"</a>)<br>

Expected behaviour: In this situation, use "Anonymous / Traditional" for the author for these two songs, and "" (empty string) for the author_years. 
Parse the rest of the song information as usual.


2. Sometimes an author is listed, and a link to another section of the file is provided (where presumably those songs have dual authorship):

<b>Ronaldo Leme</b>&#160; (?) - see <a href="#bonfa_leme">Luiz Bonfa &amp; Ronaldo Leme</a><br><br>

<b>Nobuo Uematsu</b>&#160; (1959-)<br>
see <a href="#finalfantasy">Final Fantasy</a><br><br>

Expected behaviour: While both authors "Ronaldo Leme" and "Nobuo Uematsu" appear, there are no songs listed directly under them. You can ignore those authors completely.


3. If there is any <a href> line without a text file specified inside, where the <a href="xyz.txt"> tag is the FIRST tag on the line, ignore it completely.


==== ADDITIONAL INSTRUCTIONS ====

Return only the output JSON, no markdown or anything else.

HTML entities (e.g. &ntilde;) should be kept as-is. Do not resolve them to Unicode characters in the output JSON.

If you encounter any edge cases besides those I mentioned, create a JSON object for each such exception with the "proper" attribute set to false. 
It should look like this in your output JSON "songs" list:
{{
    "author": "",
    "author_years": "",
    "title": "",
    "tab": "",
    "midi": "",
    "video": "",
    "artist": "",
    "easy": false,
    "lhf": false,
    "proper": false
}}


==== HTML TO PARSE ====

{html_text}

==== END OF HTML ====
"""


