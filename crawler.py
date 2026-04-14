import requests
from bs4 import BeautifulSoup
import re
import random
import urllib.parse
import time

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

def fetch_page(url):
    """Fetches HTML using requests with random user-agent and timeout."""
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        # Add a small delay to avoid blocking
        time.sleep(random.uniform(1, 2))
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        # Silently skip broken URLs or handle timeouts
        return None

def extract_emails(text):
    """Extracts emails using a robust regex."""
    if not text: return []
    # Improved regex for emails: ensures it matches common patterns
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}"
    # Also look for common obfuscation like (at) or [at]
    obfuscated_email_regex = r"[a-zA-Z0-9._%+-]+\s*[\[\(]at[\]\)]\s*[a-zA-Z0-9.-]+\s*[\[\(]dot[\]\)]\s*[a-z]{2,}"
    
    found = re.findall(email_regex, text)
    obfuscated = re.findall(obfuscated_email_regex, text)
    
    # Clean up obfuscated emails
    for email in obfuscated:
        clean = email.replace(" [at] ", "@").replace("(at)", "@").replace(" [dot] ", ".").replace("(dot)", ".")
        found.append(clean.replace(" ", ""))
        
    return list(set(found))

def extract_phones(text):
    """Extracts phone numbers using a robust regex and basic validation."""
    if not text: return []
    # Improved regex for phones: matches standard international and national formats
    # Allows optional +, digits, spaces, hyphens, and parentheses
    # Ensures it doesn't just match any long string of digits
    phone_regex = r"(\+?\d[\d\s\-\(\)]{7,}\d)"
    matches = re.findall(phone_regex, text)
    
    results = []
    for match in matches:
        # Basic validation:
        # 1. Strip whitespace and separators to count actual digits
        digits = re.sub(r"\D", "", match)
        if len(digits) < 7 or len(digits) > 15:
            continue
            
        # 2. Exclude common date patterns (YYYY-MM-DD, DD-MM-YYYY)
        if re.search(r"\d{4}-\d{2}-\d{2}", match) or re.search(r"\d{2}-\d{2}-\d{4}", match):
            continue

        results.append(match.strip())
        
    return list(set(results))

def extract_links(html, base_url):
    """Extracts absolute links from HTML."""
    if not html: return []
    try:
        soup = BeautifulSoup(html, 'lxml')
        links = []
        for a in soup.find_all('a', href=True):
            link = urllib.parse.urljoin(base_url, a['href'])
            if link.startswith("http"):
                links.append(link)
        return list(set(links))
    except:
        return []

def extract_images(html, base_url):
    """Extracts image URLs from HTML."""
    if not html: return []
    try:
        soup = BeautifulSoup(html, 'lxml')
        images = []
        for img in soup.find_all('img', src=True):
            img_url = urllib.parse.urljoin(base_url, img['src'])
            if img_url.startswith("http"):
                images.append(img_url)
        return list(set(images))
    except:
        return []

def extract_social_links(html):
    """
    Extracts social media profile links from a page's HTML.
    Looks for links to major platforms.
    """
    if not html: return []
    platforms = ["facebook.com", "linkedin.com", "twitter.com", "x.com", "instagram.com", "tiktok.com", "github.com", "youtube.com"]
    try:
        soup = BeautifulSoup(html, 'lxml')
        social_links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if any(platform in href for platform in platforms):
                # Clean up the link (remove tracking parameters etc if possible)
                clean_link = href.split('?')[0].rstrip('/')
                if clean_link.startswith("http"):
                    social_links.append(clean_link)
        return list(set(social_links))
    except:
        return []

def extract_names(html, text):
    """
    Enhanced name extraction.
    Uses page title as primary candidate, plus simple heuristics.
    """
    names = []
    
    # 1. Page Title extraction
    if html:
        try:
            soup = BeautifulSoup(html, 'lxml')
            title = soup.title.string if soup.title else ""
            if title:
                # Often titles are like "Name - Platform" or "Name's Profile"
                # Clean common social suffixes
                clean_title = re.split(r' - | \| | \u2013 | \u2014', title)[0]
                # Remove common profile suffixes
                clean_title = re.sub(r"'s Professional Profile", "", clean_title, flags=re.I)
                clean_title = re.sub(r"'s Profile", "", clean_title, flags=re.I)
                clean_title = re.sub(r" Profile", "", clean_title, flags=re.I)
                clean_title = clean_title.strip()
                
                if 3 < len(clean_title) < 50 and any(c.isupper() for c in clean_title):
                    names.append(clean_title)
        except:
            pass

    # 2. Simple heuristic (Capitalized words)
    if text:
        name_regex = r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"
        names.extend(re.findall(name_regex, text))
        
    return list(set(names))
