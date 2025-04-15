import re
import os
import requests
import json
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# User agent to mimic a browser
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Rate limiting parameters
MAX_REQUESTS_PER_MINUTE = 20
REQUEST_INTERVAL = 60 / MAX_REQUESTS_PER_MINUTE  # seconds between requests
last_request_time = 0

def rate_limit():
    """Simple rate limiting mechanism"""
    global last_request_time
    current_time = time.time()
    time_since_last_request = current_time - last_request_time
    
    if time_since_last_request < REQUEST_INTERVAL:
        sleep_time = REQUEST_INTERVAL - time_since_last_request
        time.sleep(sleep_time)
    
    last_request_time = time.time()

def extract_username_from_url(url: str, platform: str) -> Optional[str]:
    """Extract username from a social media URL"""
    if not url:
        return None
    
    url = url.strip()
    
    if platform == "twitter":
        # Match Twitter/X URLs: twitter.com/username or x.com/username
        pattern = r'(?:twitter\.com|x\.com)/(@?[\w\d\-_]+)'
        match = re.search(pattern, url)
        if match:
            username = match.group(1)
            if username.startswith('@'):
                username = username[1:]
            return username
    
    elif platform == "github":
        # Match GitHub URLs: github.com/username
        pattern = r'github\.com/([\w\d\-_]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    elif platform == "bluesky":
        # Match Bluesky URLs: bsky.app/profile/username or bsky.social/profile/username
        pattern = r'(?:bsky\.app|bsky\.social)/profile/([\w\d\-_\.]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def scrape_twitter_profile(username: str) -> Dict[str, Any]:
    """
    Scrape Twitter profile information using multiple methods.
    
    This function tries several approaches:
    1. HTML scraping via Nitter instances
    2. Fallback to direct HTML scraping if available
    3. Public API endpoints if configured
    
    Returns a dictionary with profile information or empty values if unavailable.
    """
    rate_limit()
    
    profile_data = {
        "platform": "twitter",
        "username": username,
        "display_name": None,
        "bio": None,
        "location": None,
        "followers_count": None,
        "following_count": None,
        "tweet_count": None,
        "profile_image": None,
        "url": f"https://twitter.com/{username}"
    }
    
    # Check if Twitter API token is available
    twitter_bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
    
    # Method 1: Try Nitter instances first if no API is available
    if not twitter_bearer_token:
        print(f"Twitter API key not available. Using Nitter fallback for {username}")
        nitter_instances = [
            "https://nitter.net",
            "https://nitter.unixfox.eu",
            "https://nitter.42l.fr",
            "https://nitter.pussthecat.org",
            "https://nitter.nixnet.services"
        ]
        
        for instance in nitter_instances:
            try:
                url = f"{instance}/{username}"
                headers = {"User-Agent": USER_AGENT}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    continue
                    
                # Simple HTML parsing to extract data
                html = response.text
                
                # Extract display name
                display_name_match = re.search(r'<title>(.*?)\(@.*?\)</title>', html)
                if display_name_match:
                    profile_data["display_name"] = display_name_match.group(1).strip()
                
                # Extract bio
                bio_match = re.search(r'<div class="profile-bio">(.*?)</div>', html, re.DOTALL)
                if bio_match:
                    bio = bio_match.group(1).strip()
                    # Clean HTML tags
                    bio = re.sub(r'<[^>]+>', '', bio)
                    profile_data["bio"] = bio
                
                # Extract location
                location_match = re.search(r'<div class="profile-location">(.*?)</div>', html)
                if location_match:
                    profile_data["location"] = location_match.group(1).strip()
                
                # Extract follower count
                followers_match = re.search(r'<span class="profile-stat-header">Followers</span>\s*<span class="profile-stat-num">(.*?)</span>', html)
                if followers_match:
                    followers_str = followers_match.group(1).strip()
                    # Convert K/M to numbers
                    if 'K' in followers_str:
                        profile_data["followers_count"] = int(float(followers_str.replace('K', '')) * 1000)
                    elif 'M' in followers_str:
                        profile_data["followers_count"] = int(float(followers_str.replace('M', '')) * 1000000)
                    else:
                        profile_data["followers_count"] = int(followers_str.replace(',', ''))
                
                # Extract following count
                following_match = re.search(r'<span class="profile-stat-header">Following</span>\s*<span class="profile-stat-num">(.*?)</span>', html)
                if following_match:
                    following_str = following_match.group(1).strip()
                    # Convert K/M to numbers
                    if 'K' in following_str:
                        profile_data["following_count"] = int(float(following_str.replace('K', '')) * 1000)
                    elif 'M' in following_str:
                        profile_data["following_count"] = int(float(following_str.replace('M', '')) * 1000000)
                    else:
                        profile_data["following_count"] = int(following_str.replace(',', ''))
                
                # If we got this far, we have some data, so break out of the loop
                if profile_data["display_name"]:
                    break
                    
            except Exception as e:
                # Silently continue to the next instance
                continue
    
        # Method 2: Try direct HTML scraping (limited effectiveness due to Twitter's JS rendering)
        if not profile_data["display_name"]:
            try:
                url = f"https://twitter.com/{username}"
                headers = {"User-Agent": USER_AGENT}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    html = response.text
                    
                    # Try to extract name from meta tags or other static HTML elements
                    display_name_match = re.search(r'<meta name="twitter:title" content="(.*?)(?:\(@.*?\))?"/>', html)
                    if display_name_match:
                        profile_data["display_name"] = display_name_match.group(1).strip()
                    
                    # Extract bio from meta description
                    bio_match = re.search(r'<meta name="description" content="(.*?)"/>', html)
                    if bio_match:
                        profile_data["bio"] = bio_match.group(1).strip()
            
            except Exception:
                # Silent failure - move to next method
                pass
    
    # Method 3: If available, try Twitter API v2 with bearer token
    # This requires a developer account and proper authentication
    if twitter_bearer_token and not profile_data["display_name"]:
        try:
            print(f"Using Twitter API for {username}")
            url = f"https://api.twitter.com/2/users/by/username/{username}?user.fields=description,location,public_metrics,profile_image_url"
            headers = {
                "Authorization": f"Bearer {twitter_bearer_token}",
                "User-Agent": USER_AGENT
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    user_data = data["data"]
                    
                    profile_data["display_name"] = user_data.get("name")
                    profile_data["bio"] = user_data.get("description")
                    profile_data["location"] = user_data.get("location")
                    profile_data["profile_image"] = user_data.get("profile_image_url")
                    
                    if "public_metrics" in user_data:
                        metrics = user_data["public_metrics"]
                        profile_data["followers_count"] = metrics.get("followers_count")
                        profile_data["following_count"] = metrics.get("following_count")
                        profile_data["tweet_count"] = metrics.get("tweet_count")
        except Exception as e:
            print(f"Error using Twitter API: {e}")
    
    return profile_data

def scrape_github_profile(username: str) -> Dict[str, Any]:
    """
    Scrape GitHub profile information using public GitHub API or HTML scraping as fallback
    
    The GitHub API allows a limited number of unauthenticated requests.
    This function tries the API first, then falls back to HTML scraping if needed.
    """
    rate_limit()
    
    profile_data = {
        "platform": "github",
        "username": username,
        "display_name": None,
        "bio": None,
        "location": None,
        "followers_count": None,
        "following_count": None,
        "repo_count": None,
        "profile_image": None,
        "url": f"https://github.com/{username}",
        "company": None,
        "blog": None
    }
    
    # Method 1: Try GitHub API
    try:
        # GitHub's public API endpoint for user data
        url = f"https://api.github.com/users/{username}"
        
        # Set up headers
        headers = {"User-Agent": USER_AGENT}
        
        # Add token if available for higher rate limits
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            profile_data["display_name"] = data.get("name")
            profile_data["bio"] = data.get("bio")
            profile_data["location"] = data.get("location")
            profile_data["followers_count"] = data.get("followers")
            profile_data["following_count"] = data.get("following")
            profile_data["repo_count"] = data.get("public_repos")
            profile_data["profile_image"] = data.get("avatar_url")
            profile_data["company"] = data.get("company")
            profile_data["blog"] = data.get("blog")
        else:
            # If API fails, we'll try HTML scraping next
            print(f"GitHub API returned status code {response.status_code}, trying HTML scraping")
            
    except Exception as e:
        # If API fails, we'll try HTML scraping next
        print(f"Error with GitHub API: {e}, trying HTML scraping")
    
    # Method 2: If API failed, try HTML scraping
    if not profile_data["display_name"]:
        try:
            url = f"https://github.com/{username}"
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                html = response.text
                
                # Extract name
                name_match = re.search(r'<span class="p-name vcard-fullname d-block overflow-hidden".*?>(.*?)</span>', html)
                if name_match:
                    profile_data["display_name"] = name_match.group(1).strip()
                
                # Extract bio
                bio_match = re.search(r'<div class="p-note user-profile-bio mb-3.*?>\s*<div.*?>(.*?)</div>', html, re.DOTALL)
                if bio_match:
                    profile_data["bio"] = bio_match.group(1).strip()
                
                # Extract location
                location_match = re.search(r'<li.*?><svg.*?octicon-location.*?>\s*<span class="p-label">(.*?)</span>', html)
                if location_match:
                    profile_data["location"] = location_match.group(1).strip()
                
                # Extract company
                company_match = re.search(r'<li.*?><svg.*?octicon-organization.*?>\s*<span class="p-org">(.*?)</span>', html)
                if company_match:
                    profile_data["company"] = company_match.group(1).strip()
                
        except Exception as e:
            print(f"Error with GitHub HTML scraping: {e}")
    
    return profile_data

def scrape_bluesky_profile(identifier: str) -> Dict[str, Any]:
    """
    Scrape Bluesky profile information using Bluesky API
    
    This function tries the public API first, then falls back to HTML scraping if needed.
    The authenticated API would provide more data, but requires credentials.
    """
    rate_limit()
    
    profile_data = {
        "platform": "bluesky",
        "username": identifier,
        "display_name": None,
        "bio": None,
        "followers_count": None,
        "following_count": None,
        "post_count": None,
        "profile_image": None,
        "url": f"https://bsky.app/profile/{identifier}"
    }
    
    # Method 1: Try official API endpoint
    try:
        url = f"https://bsky.social/xrpc/com.atproto.repo.getRecord?repo={identifier}&collection=app.bsky.actor.profile&rkey=self"
        
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            profile_value = data.get("value", {})
            
            profile_data["display_name"] = profile_value.get("displayName")
            profile_data["bio"] = profile_value.get("description")
            
            # For followers and following, we would need authenticated APIs
            # This is just placeholder logic
            
            # Try to get the avatar URL if available
            if "avatar" in profile_value:
                profile_data["profile_image"] = profile_value.get("avatar")
        else:
            print(f"Bluesky API returned status code {response.status_code}")
            
    except Exception as e:
        print(f"Error with Bluesky API: {e}")
    
    # Method 2: If API fails, try HTML scraping
    if not profile_data["display_name"]:
        try:
            url = f"https://bsky.app/profile/{identifier}"
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                html = response.text
                
                # These patterns may need updating as Bluesky's HTML structure changes
                display_name_match = re.search(r'<title>(.*?) \(.*?\) - Bluesky</title>', html)
                if display_name_match:
                    profile_data["display_name"] = display_name_match.group(1).strip()
                
                # Try to extract bio from meta tags
                bio_match = re.search(r'<meta name="description" content="(.*?)"/>', html)
                if bio_match:
                    profile_data["bio"] = bio_match.group(1).strip()
                
        except Exception as e:
            print(f"Error with Bluesky HTML scraping: {e}")
    
    return profile_data

def identify_platform(url: str) -> Optional[str]:
    """Identify which social media platform a URL belongs to"""
    if not url:
        return None
    
    url = url.lower()
    
    if "twitter.com" in url or "x.com" in url:
        return "twitter"
    elif "github.com" in url:
        return "github"
    elif "bsky.app" in url or "bsky.social" in url:
        return "bluesky"
    
    return None

def scrape_social_profiles(social_urls: List[str]) -> List[Dict]:
    """
    Scrape multiple social media profiles and return enriched data
    
    Args:
        social_urls: List of social media profile URLs
        
    Returns:
        List of dictionaries containing profile data for each URL
    """
    if not social_urls:
        return []
    
    results = []
    
    for url in social_urls:
        platform = identify_platform(url)
        if not platform:
            continue
        
        username = extract_username_from_url(url, platform)
        if not username:
            continue
        
        # Call the appropriate scraper based on the platform
        if platform == "twitter":
            profile_data = scrape_twitter_profile(username)
        elif platform == "github":
            profile_data = scrape_github_profile(username)
        elif platform == "bluesky":
            profile_data = scrape_bluesky_profile(username)
        else:
            continue
        
        results.append(profile_data)
    
    return results

def enrich_persona_with_social_data(persona: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich a persona dictionary with data from social media profiles
    
    Args:
        persona: Dictionary containing person information
        
    Returns:
        Enriched persona dictionary
    """
    if not persona or not isinstance(persona, dict):
        return persona
    
    social_profiles = persona.get("social_profile", [])
    if not social_profiles:
        return persona
    
    # Scrape social profiles
    social_data = scrape_social_profiles(social_profiles)
    
    # Add consolidated social data to persona
    persona["scraped_social_data"] = social_data
    
    # Try to fill in missing fields from social data if they don't exist in persona
    if not persona.get("name") and social_data:
        # Try to get name from any platform, prioritizing GitHub, then Twitter, then Bluesky
        for platform in ["github", "twitter", "bluesky"]:
            for profile in social_data:
                if profile.get("platform") == platform and profile.get("display_name"):
                    persona["name"] = profile.get("display_name")
                    break
            if persona.get("name"):
                break
    
    # Fill in location if missing
    if not persona.get("location") and social_data:
        for profile in social_data:
            if profile.get("location"):
                persona["location"] = profile.get("location")
                break
    
    # Fill in bio/intro if missing
    if not persona.get("intro") and social_data:
        for profile in social_data:
            if profile.get("bio"):
                persona["intro"] = profile.get("bio")
                break
    
    # Add company information if available from GitHub
    for profile in social_data:
        if profile.get("platform") == "github" and profile.get("company") and not persona.get("company"):
            persona["company"] = profile.get("company")
    
    return persona

# Example usage
if __name__ == "__main__":
    # Example social profile URLs
    social_urls = [
        "https://twitter.com/github",
        "https://github.com/octocat",
        "https://bsky.app/profile/bsky.app"
    ]
    
    # Scrape profiles
    profiles = scrape_social_profiles(social_urls)
    
    # Print results
    for profile in profiles:
        print(f"\n{profile['platform'].upper()} Profile for {profile['username']}:")
        for key, value in profile.items():
            if key not in ["platform", "username"] and value is not None:
                print(f"  {key}: {value}")
    
    # Example of enriching a persona
    sample_persona = {
        "name": "",
        "social_profile": [
            "https://twitter.com/github",
            "https://github.com/octocat"
        ]
    }
    
    enriched = enrich_persona_with_social_data(sample_persona)
    print("\nEnriched persona:")
    print(json.dumps(enriched, indent=2))