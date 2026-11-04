import json
import re


def parse_response_text(response_text, expected_type='object'):
    text = response_text.strip()

    try:
        return json.loads(text)
    except:
        pass
    
    # Remove common prefixes/suffixes and try again
    text = text.replace('```json', '').replace('```', '').strip()
    try:
        return json.loads(text)
    except:
        pass
    
    if expected_type == 'list':
        array_pattern = r'\[[\s\S]*?\]'
        matches = re.findall(array_pattern, text)

        for match in matches:
            try:
                result = json.loads(match)
                if isinstance(result, list):
                    return result
            except:
                continue
    
    elif expected_type == 'object':
        object_pattern = r'\{[\s\S]*?\}'
        matches = re.findall(object_pattern, text)

        for match in matches:
            try:
                result = json.loads(match)
                if isinstance(result, dict):
                    return result
            except:
                continue
    
    try:
        if expected_type == 'list':
            start_char, end_char = '[', ']'
        else:
            start_char, end_char = '{', '}'
        
        start_idx = text.find(start_char)
        if start_idx != -1:
            bracket_count = 0
            for idx, char in enumerate(text[start_idx:], start_idx):
                if char == start_char:
                    bracket_count += 1
                elif char == end_char:
                    bracket_count -= 1
                    if bracket_count == 0:
                        json_str = text[start_idx: idx+1]
                        return json.loads(json_str)
    except:
        pass
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith(('[', '{')) and line.endswith((']', '}')):
            try:
                return json.loads(line)
            except:
                continue
    
    return {}

