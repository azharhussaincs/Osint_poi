import re

def extract_entities(text):
    """
    Extracts emails, phones, and names from text using regex.
    """
    if not text:
        return {"emails": [], "phones": [], "names": []}
    
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}"
    phone_regex = r"\+?\d[\d\s-]{8,}\d"
    name_regex = r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"
    
    emails = list(set(re.findall(email_regex, text)))
    phones = list(set(re.findall(phone_regex, text)))
    names = list(set(re.findall(name_regex, text)))
    
    return {
        "emails": emails,
        "phones": phones,
        "names": names
    }

def process_local_file(file_path):
    """
    Processes a local text file and extracts entities.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            return extract_entities(text)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return {"emails": [], "phones": [], "names": []}
