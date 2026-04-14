import urllib.parse

def generate_social_links(name=None, email=None, phone=None):
    """
    Generates real search URLs for major social media platforms.
    These links direct the user to search pages on each platform.
    """
    links = {}
    
    platforms = {
        "Facebook Search": "https://www.facebook.com/search/top/?q=",
        "LinkedIn Search": "https://www.linkedin.com/search/results/all/?keywords=",
        "Twitter/X Search": "https://twitter.com/search?q=",
        "Instagram Search": "https://www.instagram.com/explore/tags/", # Searching tags or using general search
        "Instagram Profile Guess": "https://www.instagram.com/",
        "TikTok Search": "https://www.tiktok.com/search?q="
    }

    query = ""
    if name:
        query = name
    elif email:
        query = email.split('@')[0]
    elif phone:
        query = phone

    if query:
        encoded_query = urllib.parse.quote(query)
        links["Facebook"] = f"{platforms['Facebook Search']}{encoded_query}"
        links["LinkedIn"] = f"{platforms['LinkedIn Search']}{encoded_query}"
        links["Twitter/X"] = f"{platforms['Twitter/X Search']}{encoded_query}"
        links["TikTok"] = f"{platforms['TikTok Search']}{encoded_query}"
        
        # Instagram specific
        links["Instagram"] = f"https://www.instagram.com/search/?q={encoded_query}"
        
    return links
