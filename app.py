import streamlit as st
import requests
from PIL import Image
from PIL.ExifTags import TAGS
import re
import social
import analysis
import crawler
import file_processor
import urllib.parse
from bs4 import BeautifulSoup
# from duckduckgo_search import DDGS  # Moved inside search_web to suppress rename warning
import time

    # --- API CONFIGURATION ---
API_URL = "http://192.168.18.126:8080/api/tc-search"
API_TOKEN = "9f2b1e3a7c4d5f6a8b0c1d2e3f4a5b6c"

def validate_name(name):
    """Validates that the name contains only alphabets, spaces, and common name characters."""
    if not name:
        return True
    # Allow alphabets, spaces, dots, hyphens, and digits (some names include numbers).
    # Block if it's purely digits.
    if name.isdigit():
        return False
    import re
    # Allow a-z, A-Z, 0-9, spaces, dots, and hyphens.
    return bool(re.match(r'^[a-zA-Z0-9\s.-]+$', name))

def validate_phone(phone):
    """Validates that the phone number contains only digits."""
    if not phone:
        return True
    # Remove common formatting and check if only digits remain
    clean_phone = phone.replace(" ", "").replace("+", "").replace("-", "").replace("(", "").replace(")", "")
    return clean_phone.isdigit()

def call_truecaller_api(name="", phone="", email="", tag=""):
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
        # Use a slightly more "real" browser header
        headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Bing search results can also be in 'li.b_algo'
        for item in soup.select('.b_algo h2 a, .b_algo h3 a'):
            href = item.get('href')
            if href and href.startswith("http") and "bing.com" not in href:
                results.append(href)
    except Exception as e:
        print(f"Bing search error for '{query}': {e}")
    return list(set(results))

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
                # Use a broader search if possible or just stick to text
                search_results = list(ddgs.text(cleaned, max_results=10))
                for r in search_results:
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
        metadata = {}
        
        # Basic info
        metadata["Format"] = img.format
        metadata["Mode"] = img.mode
        metadata["Size"] = img.size
        metadata["Filename"] = getattr(image_file, 'name', 'Unknown')
        
        if exif_data:
            for tag, value in exif_data.items():
                tag_name = TAGS.get(tag, tag)
                # Handle bytes values
                if isinstance(value, bytes):
                    try:
                        value = value.decode(errors='ignore')
                    except:
                        value = str(value)
                metadata[tag_name] = value
        
        return metadata
    except Exception as e:
        return {"Error": f"Error extracting metadata: {e}"}

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

        # --- Strict Input Validation ---
        if name_input and not validate_name(name_input):
            st.error("The Name field should only accept text (alphabets).")
            return
        
        if phone_input and not validate_phone(phone_input):
            st.error("The Phone Number field should only accept numeric values.")
            return

        # Prepare lists for OSINT pipeline
        # Use data from local file and user input as base
        all_names = [name_input] if name_input else []
        all_phones = [phone_input] if phone_input else []
        all_emails = [email_input] if email_input else []

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

        # 0. Image Metadata Extraction (Moved before API call to feed into it)
        if image_upload:
            with st.status("Analyzing uploaded image..."):
                osint_data["metadata"] = get_image_metadata(image_upload)
                osint_data["reverse_search_links"] = reverse_image_search_links(image_upload)
                
                if osint_data["metadata"] and isinstance(osint_data["metadata"], dict):
                    # Try to find a name or info in metadata
                    artist = osint_data["metadata"].get("Artist")
                    author = osint_data["metadata"].get("Author")
                    xp_author = osint_data["metadata"].get("XPAuthor")
                    xp_comment = osint_data["metadata"].get("XPComment")
                    image_desc = osint_data["metadata"].get("ImageDescription")
                    user_comment = osint_data["metadata"].get("UserComment")
                    
                    if artist: all_names.append(artist)
                    if author: all_names.append(author)
                    if xp_author: all_names.append(xp_author)
                    
                    # Search for emails/phones in comments/descriptions
                    for text_field in [xp_comment, image_desc, user_comment]:
                        if text_field and isinstance(text_field, str):
                            osint_data["emails"].extend(crawler.extract_emails(text_field))
                            osint_data["phones"].extend(crawler.extract_phones(text_field))
                            osint_data["names"].extend(crawler.extract_names(None, text_field))

                    # If no name found yet but filename is descriptive (not IMG_123 or file)
                    filename = osint_data["metadata"].get("Filename", "")
                    if filename and not re.match(r"^(IMG_|DSC|P_|IMAGE|PHOTO|FILE|UPLOAD)\d*", filename, re.I):
                        # Strip extension
                        name_from_file = filename.rsplit('.', 1)[0]
                        # Avoid generic names
                        if len(name_from_file) > 3 and name_from_file.lower() not in ["image", "photo", "file", "upload", "pic"]:
                            all_names.append(name_from_file)

                # Ensure extracted data is added to search lists
                all_names = list(set([n for n in all_names if n and len(n) > 2]))
                all_emails = list(set(all_emails + osint_data["emails"]))
                all_phones = list(set(all_phones + osint_data["phones"]))
                image_upload.seek(0)

        # If searching by name, ensure phone is empty and vice versa (requirement 3)
        if name_input and phone_input:
            st.warning("Searching by both Name and Phone Number may limit API results, but OSINT pipeline will use both.")
        
        # Requirement 3: If phone number is entered, search only by PHONE. 
        # If name is entered, search only by NAME.
        # NOW: If image provides a name and input is empty, use image name.
        api_name = name_input
        if not api_name and all_names:
            api_name = all_names[0]
            st.info(f"Using name from image: {api_name}")

        api_phone = phone_input
        if not api_phone and all_phones:
            api_phone = all_phones[0]
            st.info(f"Using phone from image: {api_phone}")

        api_email = email_input
        if not api_email and all_emails:
            api_email = all_emails[0]
            st.info(f"Using email from image: {api_email}")
            
        # Refined requirement 3 logic for API call
        final_api_name = api_name if not api_phone else ""
        final_api_phone = api_phone if not api_name else ""

        # API call - Skip ONLY if no text input is provided and no data was extracted from the image
        # User requested skipping when image is uploaded because "api did not have images details"
        # but we should still call it if we have a name or phone to search for.
        api_results = {"results": []}
        
        # Decide whether to call the API
        # We call it if:
        # 1. No image is uploaded (standard search)
        # 2. Image is uploaded BUT we have a phone or name to search for (either from input or extracted)
        should_call_api = False
        if not image_upload:
            should_call_api = True
        elif final_api_name or final_api_phone or api_email:
            should_call_api = True
            
        if should_call_api:
            with st.spinner("Calling API..."):
                api_results = call_truecaller_api(name=final_api_name, phone=final_api_phone, email=api_email)
        else:
            st.info("No text or phone data to search in primary API.")
        
        results_list = api_results.get("results", [])
        
        # Display API results if found
        if results_list:
            st.success(f"API returned {len(results_list)} results!")
            for i, r in enumerate(results_list):
                with st.expander(f"👤 Result {i+1}: {r.get('NAME', 'Unknown')}"):
                    name = r.get('NAME') or r.get('name')
                    phone = r.get('PHONE') or r.get('phone')
                    email = r.get('EMAIL') or r.get('email')
                    tags = r.get('TAGS') or r.get('tags') or r.get('tag')
                    
                    st.write(f"**NAME:** {name}")
                    st.write(f"**PHONE:** {phone}")
                    st.write(f"**EMAIL:** {email}")
                    if tags:
                        st.write(f"**TAGS:** {tags}")
                    else:
                        st.write("**TAGS:** None")
                        
                    # Ensure ASONDATE is displayed - prioritize ASONDATE from API
                    as_on_date = r.get('ASONDATE') or r.get('asondate') or r.get('AsonDate')
                    if as_on_date:
                        st.write(f"**ASONDATE:** {as_on_date}")
                    else:
                        # Try to find it in other possible keys just in case
                        alt_date = r.get('date') or r.get('DATE') or r.get('as_on_date') or r.get('AS_ON_DATE')
                        if alt_date:
                            st.write(f"**ASONDATE:** {alt_date}")
                        else:
                            st.write("**ASONDATE:** None")
                    
                    # Add API results to the lists for OSINT pipeline
                    if name: all_names.append(name)
                    if phone: all_phones.append(phone)
                    if email: all_emails.append(email)
            
            if data_entities['names']: all_names.extend(data_entities['names'])
            if data_entities['emails']: all_emails.extend(data_entities['emails'])
            if data_entities['phones']: all_phones.extend(data_entities['phones'])

            # De-duplicate lists after adding API and file results
            all_names = list(set([n for n in all_names if n and len(n) > 2]))
            all_phones = list(set(all_phones))
            all_emails = list(set(all_emails))

            st.header("🕸️ Connection Engine")
            # Update connection engine to include ASONDATE
            connections = analysis.connection_engine(api_results, {})
            st.json(connections)
            
            # If API results are found, show them and then proceed to OSINT pipeline for social media
            st.info("API data retrieved. Searching internet for related social media and additional details...")
        else:
            st.error("No corresponding data found")
        
        # OSINT pipeline - Always run if searched to find social media as requested
        if True:
            if not any([all_names, all_phones, all_emails]) and image_upload:
                st.info("No text data found, proceeding with image OSINT...")
            elif not results_list:
                # Handled above with "No corresponding data found. from db"
                st.info("Triggering REAL OSINT pipeline...")
            else:
                st.info("Processing internet OSINT...")
            
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

            # 5. Image Results Display
            if image_upload:
                st.write("### Image Analysis Results")
                if osint_data.get("metadata"):
                    with st.expander("Technical Metadata"):
                        st.json(osint_data["metadata"])
                
                st.info("To find the identity using visual search, please use the reverse search links below. Any text details found in image metadata have been added to the OSINT pipeline.")

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
                    st.image(image_upload, caption="Uploaded Image", use_container_width=True)
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
