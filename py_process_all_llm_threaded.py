import json
import math
from natsort import natsorted
import os
import queue
import requests
import threading
import time

from prompts import prompt_template
from utils import parse_response_text, seconds_to_hms


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

# Multithreading variables
N_THREADS = 4  # how many authors do we process simultaneously?
CALLS_MADE = 0
CALLS_LOCK = threading.Lock()
TOTAL_CALLS = 0


def call_llm(prompt,
             ollama_url=OLLAMA_URL, 
             ollama_model=OLLAMA_MODEL, 
             ollama_num_ctx=OLLAMA_NUM_CTX, 
             ollama_max_tokens=OLLAMA_MAX_TOKENS, 
             ollama_temperature=OLLAMA_TEMPERATURE
             ):
    payload = {
        'model': ollama_model,
        'prompt': prompt,
        'format': 'json',
        'stream': False,
        'options': {
            'contextLength': ollama_num_ctx,
            'maxTokens': ollama_max_tokens,
            'temperature': ollama_temperature,
            'reasoning': False,
        }
    }
    response = requests.post(ollama_url, json=payload)
    response_dict = response.json()
    return response_dict


def parse_single_author(filename, input_dir=INPUT_DIR, output_dir=OUTPUT_DIR):
    global CALLS_MADE, CALLS_LOCK

    # Read the input file and create the prompt
    input_path = os.path.join(input_dir, filename)
    with open(input_path, 'r', encoding='utf-8') as f:
        html_text = f.read()
    prompt = prompt_template.format(html_text=html_text)

    # Aggregate responses for each song in a single loop
    song_counts = {}
    song_data_map = {}

    for j in range(N_CALLS_PER_AUTHOR):
        try:
            # Call the LLM
            try:
                resdict = call_llm(prompt)
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
        except Exception as e:
            print('Skipping this response due to error in processing: ' + str(e))
            with CALLS_LOCK:
                CALLS_MADE += 1
            continue
        
        # Ensure the response has the expected structure before continuing songs
        if not isinstance(parsed_response, dict) or 'songs' not in parsed_response:
            print('Skipping this response due to missing \"songs\" key: ' + json.dumps(parsed_response, indent=2))
            with CALLS_LOCK:
                CALLS_MADE += 1
            continue

        for song in parsed_response.get('songs', []):
            key = song.get('tab')
            if not key:
                continue
            song_counts[key] = song_counts.get(key, 0) + 1
            # Store the first seen data for later output
            if key not in song_data_map:
                song_data_map[key] = song
        #print(json.dumps(parsed_response, indent=2))

        with CALLS_LOCK:
            CALLS_MADE += 1

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

    return parsed_response


def worker_main(job_queue):
    tname = threading.current_thread().name

    while job_queue.qsize() > 0:
        try:
            filename = job_queue.get(timeout=10)
        except queue.Empty:
            break
        
        # Process the file
        try:
            parse_single_author(filename)
        except Exception as e:
            print(f"Error processing {filename} in thread {tname}: {str(e)}")
            continue
        #job_queue.task_done()
    print(f'\nThread {tname} finished processing.')


def thread_monitor_main(thread_list):
    global CALLS_LOCK, CALLS_MADE, TOTAL_CALLS
    t0 = time.time()

    def check_completion_status():
        any_threads_alive = False
        for worker in thread_list:
            any_threads_alive = any_threads_alive or worker.is_alive()
        return any_threads_alive

    threads_incomplete = check_completion_status()
    while threads_incomplete:
        time.sleep(1)
        threads_incomplete = check_completion_status()
        with CALLS_LOCK:
            t1 = time.time()
            calls = CALLS_MADE
            processed_pct = (calls / TOTAL_CALLS) * 100 if TOTAL_CALLS > 0 else 0
        print(f'\rProgress: {processed_pct:.1f}% ({calls}/{TOTAL_CALLS} calls | {(t1 - t0) / calls if calls > 0 else 0:.1f} sec/call)', end='', flush=True)
    print('\rProgress: 100% ({CALLS_MADE}/{TOTAL_CALLS} calls)                                      ')


def parse_authors(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR):
    """Parse each HTML file, calling the LLM multiple times per author.

    For each author in the input file, the LLM is queried ``N_CALLS_PER_AUTHOR``
    times.  The responses are aggregated and only songs that appear in at
    least ``ceil(N_CALLS_PER_AUTHOR * PERCENT_THRESH)`` of the calls are
    retained.  The resulting JSON structure is written to ``output_dir``.
    """
    global TOTAL_CALLS

    input_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.htm') or f.lower().endswith('.html')]
    #input_files = ['252.htm']
    sorted_files = natsorted(input_files)

    os.makedirs(output_dir, exist_ok=True)
    job_queue = queue.Queue()

    for i, filename in enumerate(sorted_files):
        job_queue.put(filename)
        TOTAL_CALLS += N_CALLS_PER_AUTHOR
    
    # Create the threads
    n_workers = max(1, min(N_THREADS, job_queue.qsize()))
    thread_list = []
    t0 = time.time()
    for i in range(n_workers):
        worker_name = f'WRK_{i+1}/{n_workers}'
        worker = threading.Thread(
            target=worker_main,
            name=worker_name,
            args=[job_queue],
            daemon=True
        )
        worker.start()
        thread_list.append(worker)
    
    # Monitor the progress
    thread_monitor_main(thread_list)


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
    t0 = time.time()
    parse_authors(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR)
    t1 = time.time()
    hms = seconds_to_hms(t1 - t0)
    print(f'\nTotal LLM processing time: {hms} (avg: {(t1 - t0) / CALLS_MADE:.1f} sec/call)')

    # Modify the beginning of the output file (the '[' line) to say the following:
    # export const songsData = [
    #
    print('Creating complete songs JS file...')
    #create_complete_songs_js(json_dir=OUTPUT_DIR)
