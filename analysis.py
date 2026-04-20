from textblob import TextBlob
import phonenumbers
from phonenumbers import geocoder

def analyze_sentiment(text):
    if not text:
        return "Neutral"
    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        if polarity > 0.1:
            return "Positive"
        elif polarity < -0.1:
            return "Negative"
        else:
            return "Neutral"
    except Exception:
        return "Neutral"

def get_location_from_phone(phone_number):
    try:
        parsed_number = phonenumbers.parse(phone_number)
        return geocoder.description_for_number(parsed_number, "en")
    except Exception:
        return "Unknown"

def connection_engine(api_results, osint_results):
    """
    Creates a simple dictionary graph of connections between entities.
    """
    graph = {
        "names": set(),
        "emails": set(),
        "phones": set(),
        "social_links": set()
    }

    # Add API data
    if api_results:
        # Assuming api_results is a dict or list of dicts
        # If it's the raw response with 'results' key:
        results = api_results.get('results', [])
        if isinstance(results, list):
            for res in results:
                # Handle both upper and lower case keys
                name = res.get('NAME') or res.get('name')
                email = res.get('EMAIL') or res.get('email')
                phone = res.get('PHONE') or res.get('phone')
                asondate = res.get('ASONDATE') or res.get('asondate') or res.get('AsonDate')
                if name: graph['names'].add(name)
                if email: graph['emails'].add(email)
                if phone: graph['phones'].add(phone)
                if asondate:
                    if 'asondates' not in graph: graph['asondates'] = set()
                    graph['asondates'].add(asondate)
        elif isinstance(results, dict):
            # Maybe it's not a list but a single result
            name = results.get('NAME') or results.get('name')
            email = results.get('EMAIL') or results.get('email')
            phone = results.get('PHONE') or results.get('phone')
            asondate = results.get('ASONDATE') or results.get('asondate') or results.get('AsonDate')
            if name: graph['names'].add(name)
            if email: graph['emails'].add(email)
            if phone: graph['phones'].add(phone)
            if asondate:
                if 'asondates' not in graph: graph['asondates'] = set()
                graph['asondates'].add(asondate)

    # Add OSINT data
    if osint_results:
        # Prioritize names found from page titles or multiple sources
        osint_names = osint_results.get('names', [])
        # Simple heuristic: longer names (within reason) might be more complete
        osint_names = sorted(list(set(osint_names)), key=len, reverse=True)
        graph['names'].update(osint_names)
        
        graph['emails'].update(osint_results.get('emails', []))
        graph['phones'].update(osint_results.get('phones', []))
        
        social_links = osint_results.get('social_links', {})
        if isinstance(social_links, dict):
             graph['social_links'].update(social_links.values())
        else:
             graph['social_links'].update(social_links)

    # Convert sets back to lists for JSON compatibility
    return {k: list(v) for k, v in graph.items()}
