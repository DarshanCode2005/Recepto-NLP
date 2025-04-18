"""
Profile Scoring Module

This module provides functions for scoring LinkedIn profile candidates against a user persona
using a hybrid matching approach that considers name similarity, semantic similarity,
industry matching, location proximity, social profile matching, and image similarity.
"""

import os
import re
import json
import math
from typing import Dict, List, Optional, Tuple, Union
import logging
import google.generativeai as genai
from dotenv import load_dotenv

from fuzzywuzzy import fuzz
import geopy.distance
from timezonefinder import TimezoneFinder
import pytz
from datetime import datetime
import requests
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.social_scraper import scrape_social_profiles, enrich_persona_with_social_data

# Load environment variables
load_dotenv()

# Initialize Gemini API
try:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    gemini_model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    logging.warning(f"Could not initialize Gemini API: {e}")
    gemini_model = None

# Initialize TimezoneFinder for location scoring
tf = TimezoneFinder()

def compute_name_score(persona_name: str, candidate_name: str) -> float:
    """
    Compute a similarity score between the persona name and candidate name.
    
    Args:
        persona_name: The name from the persona
        candidate_name: The name from the LinkedIn candidate
        
    Returns:
        float: A score between 0 and 1 indicating name similarity
    """
    if not persona_name or not candidate_name:
        return 0.0
    
    # Clean and normalize names
    persona_name = persona_name.lower().strip()
    candidate_name = candidate_name.lower().strip()
    
    # Calculate different fuzzy match scores
    ratio = fuzz.ratio(persona_name, candidate_name) / 100
    partial_ratio = fuzz.partial_ratio(persona_name, candidate_name) / 100
    token_sort_ratio = fuzz.token_sort_ratio(persona_name, candidate_name) / 100
    
    # Check if all parts of persona name are in candidate name
    persona_parts = set(persona_name.split())
    candidate_parts = set(candidate_name.split())
    all_parts_match = all(part in candidate_parts for part in persona_parts)
    parts_match_bonus = 0.2 if all_parts_match else 0.0
    
    # Combine scores with weights
    weighted_score = (ratio * 0.3) + (partial_ratio * 0.4) + (token_sort_ratio * 0.3) + parts_match_bonus
    
    # Cap at 1.0
    return min(weighted_score, 1.0)

def compute_semantic_score(persona_intro: str, candidate_intro: str) -> float:
    """
    Compute a semantic similarity score between persona intro and candidate intro using Gemini API.
    
    Args:
        persona_intro: The introduction text from the persona
        candidate_intro: The introduction text from the LinkedIn candidate
        
    Returns:
        float: A score between 0 and 1 indicating semantic similarity
    """
    if not persona_intro or not candidate_intro or not gemini_model:
        return 0.0
    
    try:
        # Create a prompt for semantic similarity analysis
        prompt = f"""Compare the following two professional descriptions and provide a similarity score between 0 and 1.
        Only respond with the numerical score, nothing else.

        Description 1: {persona_intro}
        Description 2: {candidate_intro}"""

        # Get response from Gemini
        response = gemini_model.generate_content(prompt)
        
        # Extract the score from the response
        try:
            score = float(response.text.strip())
            # Ensure score is between 0 and 1
            score = max(0.0, min(1.0, score))
            return score
        except ValueError:
            logging.error("Could not parse similarity score from Gemini response")
            return 0.0
            
    except Exception as e:
        logging.error(f"Error computing semantic score with Gemini: {e}")
        return 0.0

def compute_industry_score(persona_industry: str, candidate_industry: str) -> float:
    """
    Compute a similarity score between the persona industry and candidate industry.
    
    Args:
        persona_industry: The industry from the persona
        candidate_industry: The industry from the LinkedIn candidate
        
    Returns:
        float: A score between 0 and 1 indicating industry similarity
    """
    if not persona_industry or not candidate_industry:
        return 0.0
    
    # Clean and normalize industry strings
    persona_industry = persona_industry.lower().strip()
    candidate_industry = candidate_industry.lower().strip()
    
    # Calculate fuzzy match scores
    ratio = fuzz.ratio(persona_industry, candidate_industry) / 100
    partial_ratio = fuzz.partial_ratio(persona_industry, candidate_industry) / 100
    token_sort_ratio = fuzz.token_sort_ratio(persona_industry, candidate_industry) / 100
    
    # Combine scores with weights
    weighted_score = (ratio * 0.2) + (partial_ratio * 0.3) + (token_sort_ratio * 0.5)
    
    return weighted_score

def compute_location_score(persona_location: str, candidate_location: str, 
                          persona_timezone: Optional[str] = None) -> float:
    """
    Compute a location similarity score based on geographic proximity and timezone.
    
    Args:
        persona_location: The location from the persona
        candidate_location: The location from the LinkedIn candidate
        persona_timezone: The timezone from the persona (optional)
        
    Returns:
        float: A score between 0 and 1 indicating location similarity
    """
    if not persona_location or not candidate_location:
        return 0.0
    
    # Clean and normalize location strings
    persona_location = persona_location.lower().strip()
    candidate_location = candidate_location.lower().strip()
    
    # Calculate basic text similarity
    text_similarity = fuzz.token_sort_ratio(persona_location, candidate_location) / 100
    
    # Try to get more precise location matching with geopy
    location_match_score = 0.0
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="linkedin_profile_finder")
        
        persona_geo = geolocator.geocode(persona_location)
        candidate_geo = geolocator.geocode(candidate_location)
        
        if persona_geo and candidate_geo:
            # Calculate distance in km
            distance = geopy.distance.distance(
                (persona_geo.latitude, persona_geo.longitude),
                (candidate_geo.latitude, candidate_geo.longitude)
            ).km
            
            # Convert distance to a similarity score (closer = higher score)
            # Scale: 0km = 1.0, 100km = 0.9, 500km = 0.5, 1000km+ = 0.0
            if distance <= 0:
                location_match_score = 1.0
            elif distance < 100:
                location_match_score = 0.9 - (distance / 1000)
            elif distance < 500:
                location_match_score = 0.7 - (distance / 1250)
            elif distance < 1000:
                location_match_score = 0.5 - (distance / 2000)
            else:
                location_match_score = 0.0
                
            # Timezone comparison if available
            timezone_match = 0.0
            if persona_timezone:
                try:
                    # Get timezone for candidate location
                    candidate_tz_name = tf.timezone_at(
                        lat=candidate_geo.latitude, 
                        lng=candidate_geo.longitude
                    )
                    
                    if candidate_tz_name:
                        candidate_tz = pytz.timezone(candidate_tz_name)
                        persona_tz = pytz.timezone(persona_timezone)
                        
                        # Calculate time difference in hours
                        now = datetime.now()
                        candidate_offset = candidate_tz.utcoffset(now).total_seconds() / 3600
                        persona_offset = persona_tz.utcoffset(now).total_seconds() / 3600
                        
                        hour_diff = abs(candidate_offset - persona_offset)
                        
                        # Convert hour difference to similarity score
                        if hour_diff == 0:
                            timezone_match = 1.0
                        elif hour_diff <= 1:
                            timezone_match = 0.8
                        elif hour_diff <= 3:
                            timezone_match = 0.6
                        elif hour_diff <= 6:
                            timezone_match = 0.3
                        else:
                            timezone_match = 0.0
                except Exception as e:
                    logging.warning(f"Error computing timezone match: {e}")
            
            # Combine location and timezone scores
            if persona_timezone:
                location_match_score = (location_match_score * 0.7) + (timezone_match * 0.3)
    except Exception as e:
        logging.warning(f"Error computing precise location match: {e}")
    
    # Combine text similarity and geolocation score (if available)
    if location_match_score > 0:
        final_score = (text_similarity * 0.3) + (location_match_score * 0.7)
    else:
        final_score = text_similarity
    
    return final_score

def extract_username_from_url(url: str) -> Optional[str]:
    """
    Extract username from social media URL.
    
    Args:
        url: The social media URL
        
    Returns:
        str: The extracted username or None if not found
    """
    if not url:
        return None
    
    # GitHub username extraction
    github_match = re.search(r'github\.com/([^/]+)', url)
    if github_match:
        return github_match.group(1)
    
    # Twitter username extraction
    twitter_match = re.search(r'twitter\.com/([^/]+)', url)
    if twitter_match:
        return twitter_match.group(1)
    
    # LinkedIn username extraction
    linkedin_match = re.search(r'linkedin\.com/in/([^/]+)', url)
    if linkedin_match:
        return linkedin_match.group(1)
    
    return None

def compute_social_score(persona_socials: List[Dict], candidate_socials: List[Dict]) -> float:
    """
    Compute a similarity score based on matching social profiles.
    Uses social_scraper to get detailed profile information for richer comparison.
    
    Args:
        persona_socials: List of social profiles from the persona
        candidate_socials: List of social profiles from the LinkedIn candidate
        
    Returns:
        float: A score between 0 and 1 indicating social profile similarity
    """
    if not persona_socials or not candidate_socials:
        return 0.0
    
    # Extract URLs from social profiles
    persona_urls = [profile.get('url', '') for profile in persona_socials if profile.get('url')]
    candidate_urls = [profile.get('url', '') for profile in candidate_socials if profile.get('url')]
    
    # Scrape detailed profile information
    persona_profiles = scrape_social_profiles(persona_urls)
    candidate_profiles = scrape_social_profiles(candidate_urls)
    
    if not persona_profiles or not candidate_profiles:
        return 0.0
    
    match_count = 0
    total_socials = len(persona_profiles)
    
    for p_profile in persona_profiles:
        p_platform = p_profile.get('platform', '').lower()
        p_username = p_profile.get('username', '')
        p_display_name = p_profile.get('display_name', '')
        p_bio = p_profile.get('bio', '')
        p_location = p_profile.get('location', '')
        p_company = p_profile.get('company', '')
        
        if not p_platform or not p_username:
            continue
        
        for c_profile in candidate_profiles:
            c_platform = c_profile.get('platform', '').lower()
            c_username = c_profile.get('username', '')
            c_display_name = c_profile.get('display_name', '')
            c_bio = c_profile.get('bio', '')
            c_location = c_profile.get('location', '')
            c_company = c_profile.get('company', '')
            
            if p_platform == c_platform:
                # Score different aspects of the profiles
                scores = []
                
                # Username match (most important)
                username_match = fuzz.ratio(p_username.lower(), c_username.lower()) / 100
                scores.append(username_match * 0.4)  # 40% weight
                
                # Display name match
                if p_display_name and c_display_name:
                    display_name_match = fuzz.ratio(p_display_name.lower(), c_display_name.lower()) / 100
                    scores.append(display_name_match * 0.2)  # 20% weight
                
                # Bio similarity
                if p_bio and c_bio:
                    bio_match = fuzz.ratio(p_bio.lower(), c_bio.lower()) / 100
                    scores.append(bio_match * 0.2)  # 20% weight
                
                # Location match
                if p_location and c_location:
                    location_match = fuzz.ratio(p_location.lower(), c_location.lower()) / 100
                    scores.append(location_match * 0.1)  # 10% weight
                
                # Company match
                if p_company and c_company:
                    company_match = fuzz.ratio(p_company.lower(), c_company.lower()) / 100
                    scores.append(company_match * 0.1)  # 10% weight
                
                # Calculate weighted average of all available scores
                if scores:
                    profile_score = sum(scores)
                    match_count += profile_score
    
    # Normalize the score
    if total_socials > 0:
        score = match_count / total_socials
        return min(score, 1.0)
    else:
        return 0.0

def compute_image_score(persona_image_url: str, candidate_image_url: str) -> float:
    """
    Compute image similarity score (placeholder).
    In the main.py file, CLIP is used for this functionality.
    
    Args:
        persona_image_url: The image URL from the persona
        candidate_image_url: The image URL from the LinkedIn candidate
        
    Returns:
        float: A score between 0 and 1 indicating image similarity
    """
    # This is just a placeholder - actual implementation uses CLIP in main.py
    if not persona_image_url or not candidate_image_url:
        return 0.0
    
    return 0.0  # Will be replaced by CLIP similarity in main.py

def score_linkedin_candidate(persona: Dict, candidate: Dict) -> Dict:
    """
    Score a LinkedIn candidate against the persona using multiple scoring methods.
    
    Args:
        persona: The user persona dict
        candidate: The LinkedIn candidate dict
        
    Returns:
        Dict: A dictionary with individual scores and confidence score
    """
    # Extract relevant fields from persona and candidate
    persona_name = persona.get('name', '')
    candidate_name = candidate.get('title', '')  # LinkedIn search result title often has the name
    
    persona_intro = persona.get('intro', '')
    candidate_intro = candidate.get('snippet', '')  # LinkedIn search result snippet has description
    
    persona_industry = persona.get('company_industry', '')
    candidate_industry = ''  # Need to extract from snippet or other fields
    if candidate.get('snippet'):
        # Try to extract industry from snippet
        industry_patterns = [
            r'(?:in|at) the ([\w\s&]+) industry',
            r'(?:in|at) ([\w\s&]+) industry',
            r'working in ([\w\s&]+)',
        ]
        for pattern in industry_patterns:
            match = re.search(pattern, candidate.get('snippet', ''), re.IGNORECASE)
            if match:
                candidate_industry = match.group(1).strip()
                break
    
    persona_location = persona.get('location', '')
    candidate_location = ''
    # Try to extract location from snippet
    location_match = re.search(r'(?:in|from|at) ([^\.]+?)(?:\.|$)', candidate.get('snippet', ''), re.IGNORECASE)
    if location_match:
        candidate_location = location_match.group(1).strip()
    
    persona_timezone = persona.get('timezone', '')
    
    # Social profiles
    persona_socials = persona.get('social_profiles', [])
    candidate_socials = []  # LinkedIn search doesn't provide this directly
    
    # Image URLs
    persona_image_url = persona.get('image_url', '')
    candidate_image_url = candidate.get('image_url', '')
    
    # Compute individual scores
    name_score = compute_name_score(persona_name, candidate_name)
    semantic_score = compute_semantic_score(persona_intro, candidate_intro)
    industry_score = compute_industry_score(persona_industry, candidate_industry)
    location_score = compute_location_score(persona_location, candidate_location, persona_timezone)
    social_score = compute_social_score(persona_socials, candidate_socials)
    image_score = compute_image_score(persona_image_url, candidate_image_url)
    
    # Calculate the confidence score
    confidence_score = (
        (name_score * 0.35) +
        (semantic_score * 0.25) +
        (industry_score * 0.10) +
        (location_score * 0.15) +
        (social_score * 0.10) +
        (image_score * 0.05)
    )
    
    # Scale the confidence 0 to 1 range to 0 to 100 range
    confidence_percentage = round(confidence_score * 100, 1)
    
    # Prepare the result
    result = {
        'profile': candidate,
        'confidence': confidence_percentage,
        'scores': {
            'name_score': round(name_score * 100, 1),
            'semantic_score': round(semantic_score * 100, 1),
            'industry_score': round(industry_score * 100, 1),
            'location_score': round(location_score * 100, 1),
            'social_score': round(social_score * 100, 1),
            'image_score': round(image_score * 100, 1),
        },
        'explanation': {
            'name': f"Name match: {round(name_score * 100, 1)}% similarity between '{persona_name}' and '{candidate_name}'",
            'semantic': f"Semantic match: {round(semantic_score * 100, 1)}% contextual similarity in descriptions",
            'industry': f"Industry match: {round(industry_score * 100, 1)}% similarity between '{persona_industry}' and '{candidate_industry}'",
            'location': f"Location match: {round(location_score * 100, 1)}% proximity between '{persona_location}' and '{candidate_location}'",
            'social': f"Social match: {round(social_score * 100, 1)}% matching social profiles",
            'image': f"Image match: {round(image_score * 100, 1)}% visual similarity between profile images",
        }
    }
    
    return result

def rank_linkedin_candidates(persona: Dict, candidates: List[Dict]) -> List[Dict]:
    """
    Score and rank LinkedIn candidates based on similarity to a persona.
    
    Args:
        persona: Dictionary containing persona information
        candidates: List of LinkedIn candidate profiles to score
        
    Returns:
        List of scored and ranked candidates
    """
    # Score each candidate
    scored_candidates = []
    for candidate in candidates:
        scored_candidate = score_linkedin_candidate(persona, candidate)
        scored_candidates.append(scored_candidate)
    
    # Sort by confidence score in descending order
    ranked_candidates = sorted(
        scored_candidates, 
        key=lambda x: x['confidence'], 
        reverse=True
    )
    
    return ranked_candidates

# Example usage
if __name__ == "__main__":
    # Sample persona and candidate for testing
    sample_persona = {
        "name": "John Smith",
        "intro": "Software Engineer with expertise in Python and Machine Learning",
        "company_industry": "Technology",
        "location": "San Francisco, CA",
        "timezone": "America/Los_Angeles",
        "social_profiles": [
            {"platform": "github", "username": "johnsmith", "url": "https://github.com/johnsmith"},
            {"platform": "twitter", "username": "johnsmith", "url": "https://twitter.com/johnsmith"}
        ],
        "image_url": "https://example.com/john_smith.jpg"
    }
    
    sample_candidate = {
        "title": "John Smith - Software Engineer at TechCorp",
        "link": "https://www.linkedin.com/in/johnsmith/",
        "snippet": "Software Engineer with 5+ years of experience in Python and Machine Learning. Working in the Technology industry in San Francisco, CA.",
        "image_url": "https://example.com/linkedin_john_smith.jpg"
    }
    
    # Score the candidate
    score_result = score_linkedin_candidate(sample_persona, sample_candidate)
    
    # Print the results
    print(json.dumps(score_result, indent=2)) 