import re

def extract_text_from_response(text_: str) -> str:
    pattern = r"b'(.*?)'"
    matches = re.findall(pattern, text_)
    if matches:
        return matches[0]

    pattern = r'b"(.*?)"'
    matches = re.findall(pattern, text_)
    return matches[0] if matches else text_

