import json
import math
from natsort import natsorted
import os
import requests

from prompts import prompt_template
from utils import parse_response_text

INPUT_DIR = './songs_authors'
OUTPUT_DIR = './songs_json'
OUTPUT_FILE = 'songs_data_raw.js'

OLLAMA_URL = "http://10.0.0.5:11434/api/generate"
OLLAMA_MODEL = 'llama3.1:8b'  # Models that fail: llama3.2:3b gpt-oss:20b
OLLAMA_NUM_CTX = 64000
OLLAMA_MAX_TOKENS = 32000
OLLAMA_TEMPERATURE = 0.0

# New global variables for multiple LLM calls per song
N_CALLS_PER_AUTHOR = 5  #7
#PERCENT_THRESH = 0.56
THRESHOLD = 2  #math.ceil(N_CALLS_PER_AUTHOR * PERCENT_THRESH)


def call_llm(html_text):
    payload = {
        'model': OLLAMA_MODEL,
        'prompt': prompt_template.format(html_text=html_text),
        'format': 'json',
        'stream': False,
        'options': {
            'contextLength': OLLAMA_NUM_CTX,
            'maxTokens': OLLAMA_MAX_TOKENS,
            'temperature': OLLAMA_TEMPERATURE,
            'reasoning': False,
        }
    }
    response = requests.post(OLLAMA_URL, json=payload)
    response_dict = response.json()
    return response_dict


def parse_single_author(filename, input_dir):
    # Read the input file
    input_path = os.path.join(input_dir, filename)
    with open(input_path, 'r', encoding='utf-8') as f:
        html_text = f.read()
    
    try:
        resdict = call_llm(html_text)
    except Exception as e:
        print(f"LLM call failed for {filename}: {str(e)}")
        raise e
    
    # Check the output status
    try:
        assert resdict['done']
        assert resdict['done_reason'] == 'stop'
    except Exception as e:
        print(f"Invalid response flags from LLM for {filename}: {str(e)} ({resdict['done']} | {resdict['done_reason']})")
        raise e
    
    # Read and parse the response
    try:
        response_text = resdict['response']
    except Exception as e:
        print(f"Unable to get response field from LLM result for {filename}: {str(e)}")
        raise e
    
    try:
        #parsed_response = parse_response_text(response_text)
        parsed_response = json.loads(response_text)
    except Exception as e:
        print(f"Unable to parse response text {filename}: {str(e)}")
        print(response_text)
        raise e

    return parsed_response



def parse_authors(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR):
    """Parse each HTML file, calling the LLM multiple times per author.

    For each author in the input file, the LLM is queried ``N_CALLS_PER_AUTHOR``
    times.  The responses are aggregated and only songs that appear in at
    least ``ceil(N_CALLS_PER_AUTHOR * PERCENT_THRESH)`` of the calls are
    retained.  The resulting JSON structure is written to ``output_dir``.
    """
    input_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.htm') or f.lower().endswith('.html')]
    #input_files = ['252.htm']
    sorted_files = natsorted(input_files)

    os.makedirs(output_dir, exist_ok=True)

    for i, filename in enumerate(sorted_files):
        #print('\rProgress: {:.1f}%'.format(float(i) / len(sorted_files) * 100), end='')

        # Aggregate responses for each song in a single loop
        song_counts = {}
        song_data_map = {}
        for j in range(N_CALLS_PER_AUTHOR):
            print('\rProgress: {:.1f}%'.format(float(i * N_CALLS_PER_AUTHOR + j) / (len(sorted_files) * N_CALLS_PER_AUTHOR) * 100), end='')
            try:
                resp = parse_single_author(filename, input_dir=input_dir)
            except Exception:
                continue
            if not isinstance(resp, dict) or 'songs' not in resp:
                continue
            for song in resp.get('songs', []):
                key = song.get('tab')
                if not key:
                    continue
                song_counts[key] = song_counts.get(key, 0) + 1
                # Store the first seen data for later output
                if key not in song_data_map:
                    song_data_map[key] = song
        #print(json.dumps(resp, indent=2))

        # Build final list of songs meeting threshold
        final_songs = [song_data_map[k] for k, cnt in song_counts.items() if cnt >= THRESHOLD]
        # Preserve the structure expected by create_complete_songs_js
        final_response = {'songs': final_songs}

        # Save the output file
        file_stem = filename.split('.')[0]
        final_response['author_id'] = file_stem
        output_path = os.path.join(output_dir, file_stem + '.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_response, f, indent=2)
    print('\rProgress: 100% complete!')


def create_complete_songs_js(json_dir=OUTPUT_DIR):
    json_song_files = [f for f in os.listdir(json_dir) if f.lower().endswith('.json')]
    all_songs = []
    for filename in json_song_files:
        file_path = os.path.join(json_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        author_id = data['author_id']

        # Filter out songs and only keep those that are "proper"
        songs = []
        for song in data['songs']:
            try:
                is_proper = song['proper']
            except KeyError:
                is_proper = False
                song['proper'] = False
                print(f'Warning: Missing "proper" field in {filename} song data. Setting to False.')
                print(f'Song data: {json.dumps(song, indent=2)}')
            
            if is_proper:
                songs.append(song)
        
        for song in songs:
            song['author_id'] = author_id
        
        all_songs.extend(songs)
    
    print(f'Saving output file {OUTPUT_FILE}')
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_songs, f, indent=2)


if __name__ == "__main__":
    #     html_text = """
    # <b>Mateo Diaz/b>&#160; (1978-2053)<br>
    # <a href="mateo_diaz_tab.txt">Mateo Diaz</a> - <a href="mateo_diaz_midi.mid">Mateo Diaz MIDI</a>
    #     """
    #     result = call_llm(html_text)
    #     print(type(result['response']), result['response'])
    print('Working directory:', os.getcwd())
    
    # parsed_response = parse_single_author('3.htm', input_dir=INPUT_DIR)
    # print(json.dumps(parsed_response, indent=2))

    print('Source directory:', INPUT_DIR)
    print('Output directory:', OUTPUT_DIR)
    parse_authors(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR)

    # Modify the beginning of the output file (the '[' line) to say the following:
    # export const songsData = [
    #
    create_complete_songs_js(json_dir=OUTPUT_DIR)
