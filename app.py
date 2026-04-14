import streamlit as st
import requests
from PIL import Image
from PIL.ExifTags import TAGS
import social
import analysis
import crawler
import file_processor
import urllib.parse
from bs4 import BeautifulSoup
# from duckduckgo_search import DDGS  # Moved inside search_web to suppress rename warning
import time

# --- API CONFIGURATION ---
API_URL = "http://192.168.18.29:8080/api/tc-search"
API_TOKEN = "9f2b1e3a7c4d5f6a8b0c1d2e3f4a5b6c"

def call_truecaller_api(name="", phone="", email="", tag=""):
    # --- Auto-Detect and Fix Swapped Inputs (Name/Phone/Email) ---
    
    # Check if name contains only digits (likely a phone number)
    name_is_phone = name and name.isdigit() or (name and all(c.isdigit() or c in "+-() " for c in name) and any(c.isdigit() for c in name))
    
    # Check if phone contains letters (likely a name)
    phone_is_name = phone and any(c.isalpha() for c in phone)
    
    # Swapping logic
    if name_is_phone and not phone:
        phone = name
        name = ""
    elif phone_is_name and not name:
        name = phone
        phone = ""
    elif name_is_phone and phone_is_name:
        # Both are swapped
        name, phone = phone, name

    # If name looks like an email, move it to email
    if name and not email and "@" in name and "." in name:
        email = name
        name = ""

    # Clean phone number (keep only digits)
    if phone:
        phone = "".join(filter(str.isdigit, phone))

    payload = {
        "token": API_TOKEN,
        "name": name,
        "phone": phone,
        "phones": [phone] if phone else [],
        "email": email,
        "tag": tag
    }
    try:
        response = requests.post(API_URL, json=payload, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {e}")
        return {"results": []}

def clean_query(query):
    """
    Cleans a search query by removing quotes, '+' signs, and extra spaces.
    Example: "+91 91234 56789" -> "91 91234 56789"
    """
    if not query:
        return ""
    # Remove quotes
    query = query.replace('"', '').replace("'", "")
    # Remove + sign
    query = query.replace('+', '')
    # Remove extra spaces
    query = " ".join(query.split())
    return query

def search_bing(query):
    """
    Fallback search using Bing (requests + BeautifulSoup).
    """
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Bing search results are often in <h2> tags with class 'b_algo'
        for item in soup.select('.b_algo h2 a'):
            href = item.get('href')
            if href and href.startswith("http"):
                results.append(href)
    except Exception as e:
        print(f"Bing search error for '{query}': {e}")
    return results

def search_web(query):
    """Takes a search query and returns real URLs from DuckDuckGo or Bing fallback"""
    cleaned = clean_query(query)
    print(f"Searching: {cleaned}")
    results = []
    
    # Try DuckDuckGo first
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                # max_results=5 as per performance requirements
                for r in ddgs.text(cleaned, max_results=5):
                    # Ensure URL extraction is correct - check multiple keys
                    url = r.get('href') or r.get('url') or r.get('link')
                    if url:
                        results.append(url)
    except Exception as e:
        print(f"DuckDuckGo search error for '{cleaned}': {e}")

    # Fallback to Bing if DDG returns empty
    if not results:
        print(f"DuckDuckGo returned 0 results for '{cleaned}'. Retrying with Bing...")
        results = search_bing(cleaned)
    
    print(f"Found: {len(results)} results")
    return results

def generate_phone_variations(phone):
    """Generates multiple search variations for a phone number."""
    # Clean phone number: keep only digits
    digits = "".join(filter(str.isdigit, phone))
    
    variations = [
        digits,                           # 919123456789
        phone,                            # Original +91 91234 56789 (cleaned later)
        digits[-10:],                     # 9123456789 (last 10 digits)
        f"{digits[-10:]} contact",        # 9123456789 contact
        f"{digits[-10:]} whatsapp",       # 9123456789 whatsapp
        f"{digits[-10:]} owner",          # 9123456789 owner
        f"{digits[-10:]} name"            # 9123456789 name
    ]
    # Filter out very short or empty strings
    return list(set([v for v in variations if len(v) > 5]))

def generate_dorks(input_data):
    """Generates strong OSINT dorks based on input data."""
    dorks = []
    if input_data.get('phone'):
        phone_vars = generate_phone_variations(input_data['phone'])
        for pv in phone_vars:
            dorks.append(pv)
            # Add site-specific dorks for the basic phone string
            if len(dorks) < 10: # Limit within dork generator
                dorks.append(f"{pv} site:facebook.com")
                dorks.append(f"{pv} site:linkedin.com")
                dorks.append(f"{pv} site:instagram.com")
                
    if input_data.get('email'):
        e = clean_query(input_data['email'])
        dorks.append(e)
        dorks.append(f"{e} site:facebook.com")
        dorks.append(f"{e} site:linkedin.com")
        
    if input_data.get('name'):
        n = clean_query(input_data['name'])
        dorks.append(f"{n} filetype:pdf")
        dorks.append(f"{n} contact")
        dorks.append(f"{n} site:linkedin.com")
    
    # Remove duplicates and empty dorks
    dorks = list(set([d for d in dorks if d]))
    # Limit to max 10 dorks here; main pipeline will limit further if needed
    return dorks

def get_image_metadata(image_file):
    try:
        img = Image.open(image_file)
        exif_data = img._getexif()
        if not exif_data:
            return "No metadata found."
        
        metadata = {}
        for tag, value in exif_data.items():
            tag_name = TAGS.get(tag, tag)
            metadata[tag_name] = value
        return metadata
    except Exception as e:
        return f"Error extracting metadata: {e}"

def reverse_image_search_links(image_file):
    """Generates real reverse image search URLs."""
    # Since we can't upload the image to Google/Yandex here, 
    # we provide the search engine URLs for manual use or simulated placeholders.
    # In a real system, you'd use an API like TinEye or Google Lens.
    return [
        "https://images.google.com/",
        "https://yandex.com/images/",
        "https://www.tineye.com/"
    ]

# --- MAIN APP ---

def main():
    st.set_page_config(page_title="REAL OSINT Intelligence System", layout="wide")
    st.title("🕵️ REAL OSINT Intelligence System")

    # --- LOCAL FILE PROCESSING ---
    DATA_FILE = "API_Request.txt"
    
    with st.spinner("Reading data..."):
        # TXT file is for functional data
        data_entities = file_processor.process_local_file(DATA_FILE)
    
    if any(data_entities.values()) and False: # Disabled by default to avoid confusion
        with st.expander("📁 Data found in API_Request.txt"):
            if data_entities['names']: st.write(f"**Names:** {', '.join(data_entities['names'])}")
            if data_entities['emails']: st.write(f"**Emails:** {', '.join(data_entities['emails'])}")
            if data_entities['phones']: st.write(f"**Phones:** {', '.join(data_entities['phones'])}")

    with st.sidebar:
        st.header("🔍 Search Parameters")
        name_input = st.text_input("Name")
        phone_input = st.text_input("Phone Number")
        email_input = st.text_input("Email")
        image_upload = st.file_uploader("Upload Image", type=['jpg', 'jpeg', 'png'])
        search_button = st.button("Search")

    if search_button:
        if not any([name_input, phone_input, email_input, image_upload]):
            st.warning("Please provide at least one input.")
            return

        with st.spinner("Calling API..."):
            api_results = call_truecaller_api(name=name_input, phone=phone_input, email=email_input)
        
        results_list = api_results.get("results", [])
        
        # Prepare lists for OSINT pipeline
        # Use data from local file and user input as base
        all_names = [name_input] if name_input else []
        all_phones = [phone_input] if phone_input else []
        all_emails = [email_input] if email_input else []

        # Display API results if found
        if results_list:
            st.success(f"API returned {len(results_list)} results!")
            for i, r in enumerate(results_list):
                with st.expander(f"👤 Result {i+1}: {r.get('NAME', 'Unknown')}"):
                    name = r.get('NAME')
                    phone = r.get('PHONE')
                    email = r.get('EMAIL')
                    st.write(f"**Name:** {name}")
                    st.write(f"**Phone:** {phone}")
                    st.write(f"**Email:** {email}")
                    st.write(f"**Date:** {r.get('ASONDATE')}")
                    
                    # Add API results to the lists for OSINT pipeline
                    if name: all_names.append(name)
                    if phone: all_phones.append(phone)
                    if email: all_emails.append(email)
            
            # De-duplicate lists after adding API results
            all_names = list(set(all_names))
            all_phones = list(set(all_phones))
            all_emails = list(set(all_emails))

            st.header("🕸️ Connection Engine")
            st.json(analysis.connection_engine(api_results, {}))
            
            # If API results are found, show them and then proceed to OSINT pipeline for social media
            st.info("API data retrieved. Searching internet for related social media and additional details...")
        
        # OSINT pipeline - Always run if searched to find social media as requested
        if True:
            if not any([all_names, all_phones, all_emails]) and image_upload:
                st.info("No text data found, proceeding with image OSINT...")
            elif not results_list:
                st.info("API returned empty results. Triggering REAL OSINT pipeline...")
            else:
                st.info("Processing internet OSINT...")
            
            osint_data = {
                "emails": [],
                "phones": [],
                "names": [],
                "social_links": {},
                "images": [],
                "source_urls": [],
                "metadata": None,
                "sentiment": "Neutral",
                "location": "Unknown"
            }

    # 1. Dorking Engine
            # Use all collected data (including API results) for dorking
            dorks = []
            for n in all_names: 
                if n: dorks.extend(generate_dorks({"name": n}))
            for p in all_phones: 
                if p: dorks.extend(generate_dorks({"phone": p}))
            for e in all_emails: 
                if e: dorks.extend(generate_dorks({"email": e}))
            
            dorks = list(set(dorks))
            
            # Limit to max 5 dorks for searching initially
            search_dorks = dorks[:5]
            
            # 2. Web Search & Crawling
            all_urls = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, dork in enumerate(search_dorks):
                status_text.text(f"Searching for: {dork}")
                urls = search_web(dork)
                all_urls.extend(urls)
                progress_bar.progress((i + 1) / len(search_dorks))
                time.sleep(1) # Delay between searches

            # 8. UPDATE PIPELINE: IF no URLs, retry with more variations
            if not all_urls and len(dorks) > 5:
                status_text.text("Initial search returned 0 results. Retrying with more variations...")
                remaining_dorks = dorks[5:10] # Try next 5
                for i, dork in enumerate(remaining_dorks):
                    urls = search_web(dork)
                    all_urls.extend(urls)
                    time.sleep(1)

            all_urls = list(set(all_urls))
            osint_data["source_urls"] = all_urls
            
            st.write(f"Found {len(all_urls)} URLs to crawl.")
            
            # 3. Fetching and Extracting
            crawled_count = 0
            for url in all_urls:
                if crawled_count >= 10: # Safety limit for all dorks combined
                    break
                status_text.text(f"Crawling: {url}")
                html = crawler.fetch_page(url)
                if html:
                    soup = BeautifulSoup(html, 'lxml')
                    text = soup.get_text()
                    
                    osint_data["emails"].extend(crawler.extract_emails(text))
                    osint_data["phones"].extend(crawler.extract_phones(text))
                    osint_data["names"].extend(crawler.extract_names(html, text))
                    osint_data["images"].extend(crawler.extract_images(html, url))
                    
                    # 7. NEW: Extract social profile links from found pages
                    new_socials = crawler.extract_social_links(html)
                    for slink in new_socials:
                        # Try to categorize them
                        if "facebook.com" in slink: osint_data["social_links"]["Facebook Profile"] = slink
                        elif "linkedin.com" in slink: osint_data["social_links"]["LinkedIn Profile"] = slink
                        elif "twitter.com" in slink or "x.com" in slink: osint_data["social_links"]["Twitter/X Profile"] = slink
                        elif "instagram.com" in slink: osint_data["social_links"]["Instagram Profile"] = slink
                        elif "tiktok.com" in slink: osint_data["social_links"]["TikTok Profile"] = slink
                        elif "github.com" in slink: osint_data["social_links"]["GitHub Profile"] = slink
                        elif "youtube.com" in slink: osint_data["social_links"]["YouTube Profile"] = slink

                    crawled_count += 1
            
            # De-duplicate results
            osint_data["emails"] = list(set(osint_data["emails"]))
            osint_data["phones"] = list(set(osint_data["phones"]))
            osint_data["names"] = list(set(osint_data["names"]))
            osint_data["images"] = list(set(osint_data["images"]))

            # 4. Social Discovery
            # Use current inputs but also prioritize results found during crawling
            social_input_name = name_input
            if not social_input_name and osint_data["names"]:
                social_input_name = osint_data["names"][0]
                
            social_input_email = email_input
            if not social_input_email and osint_data["emails"]:
                social_input_email = osint_data["emails"][0]

            social_links_generated = social.generate_social_links(social_input_name, social_input_email, phone_input)
            
            # Merge generated links with extracted links, extracted links (Profiles) take precedence
            for key, val in social_links_generated.items():
                if key not in osint_data["social_links"]:
                    osint_data["social_links"][key] = val

            # 5. Image Search & Metadata
            if image_upload:
                st.write("### Image Analysis")
                osint_data["metadata"] = get_image_metadata(image_upload)
                osint_data["reverse_search_links"] = reverse_image_search_links(image_upload)
                
                if osint_data["metadata"] and isinstance(osint_data["metadata"], dict):
                    # Try to find a name or info in metadata
                    artist = osint_data["metadata"].get("Artist")
                    author = osint_data["metadata"].get("Author")
                    if artist: osint_data["names"].append(artist)
                    if author: osint_data["names"].append(author)
                
                st.info("To find the identity, please use the reverse search links below. If you find a name, re-enter it in the search box.")
                image_upload.seek(0)

            # 6. Analysis
            combined_text = f"{name_input} {email_input} {phone_input} " + " ".join(osint_data["names"])
            osint_data["sentiment"] = analysis.analyze_sentiment(combined_text)
            if phone_input:
                osint_data["location"] = analysis.get_location_from_phone(phone_input)

        # --- DISPLAY RESULTS ---
            status_text.text("Search Complete.")
            
            st.header("📊 Overview")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("URLs Crawled", crawled_count)
            col2.metric("Emails Found", len(osint_data["emails"]))
            col3.metric("Phones Found", len(osint_data["phones"]))
            col4.metric("Sentiment", osint_data["sentiment"])

            st.header("🔍 Extracted OSINT Data")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.subheader("Emails")
                for email in osint_data["emails"]:
                    st.write(email)
                if not osint_data["emails"]: st.write("None found")
            with c2:
                st.subheader("Phone Numbers")
                for phone in osint_data["phones"]:
                    st.write(phone)
                if not osint_data["phones"]: st.write("None found")
            with c3:
                st.subheader("Possible Names")
                for name in osint_data["names"]:
                    st.write(name)
                if not osint_data["names"]: st.write("None found")

            st.header("📱 Social Media Search Links")
            for platform, link in osint_data["social_links"].items():
                st.markdown(f"- [{platform}]({link})")

            st.header("🌐 Source URLs")
            with st.expander("Show all source URLs"):
                for url in osint_data["source_urls"]:
                    st.write(url)

            st.header("🖼️ Images & Metadata")
            im1, im2 = st.columns(2)
            with im1:
                if image_upload:
                    st.image(image_upload, caption="Uploaded Image", use_column_width=True)
                else:
                    st.write("No image uploaded.")
            with im2:
                if osint_data.get("metadata"):
                    st.write("### Metadata")
                    st.json(osint_data["metadata"])
                if osint_data.get("reverse_search_links"):
                    st.write("### Reverse Search Engines")
                    for l in osint_data["reverse_search_links"]:
                        st.markdown(f"- [Search on {l.split('.')[1].capitalize()}]({l})")

            st.header("🕸️ Connection Engine")
            connections = analysis.connection_engine(api_results, osint_data)
            st.json(connections)

        # No extra 'else' needed here as results are handled above
        pass

if __name__ == "__main__":
    main()
