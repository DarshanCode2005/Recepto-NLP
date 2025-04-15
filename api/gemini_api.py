import os
import json
import time
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def construct_profile_description(profile_blocks: List[Dict]) -> str:
    """
    Construct a descriptive string from raw social profile data.
    
    Args:
        profile_blocks: List of dictionaries containing social profile data
        
    Returns:
        A descriptive string summarizing the profiles
    """
    # Check if we have any profile data
    if not profile_blocks:
        return "No profile data available."
    
    descriptions = []
    
    # Add a section for each platform's profile
    for profile in profile_blocks:
        platform = profile.get("platform", "Unknown").capitalize()
        username = profile.get("username", "unknown")
        
        # Start with platform and username
        profile_desc = f"\n## {platform} Profile (@{username})\n"
        
        # Add display name if available
        if profile.get("display_name"):
            profile_desc += f"Name: {profile.get('display_name')}\n"
        
        # Add bio/description if available
        if profile.get("bio"):
            # Clean up the bio text
            bio = profile.get("bio").replace("\n", " ").strip()
            profile_desc += f"Bio: {bio}\n"
        
        # Add location if available
        if profile.get("location"):
            profile_desc += f"Location: {profile.get('location')}\n"
        
        # Add company if available (mostly from GitHub)
        if profile.get("company"):
            company = profile.get("company")
            # Try to clean up HTML if present
            if "<" in company and ">" in company:
                # Very simple HTML removal - in production, use a proper HTML parser
                import re
                company = re.sub("<[^>]+>", "", company)
            profile_desc += f"Company/Organization: {company.strip()}\n"
        
        # Add metrics if available
        metrics = []
        if profile.get("followers_count") is not None:
            metrics.append(f"Followers: {profile.get('followers_count')}")
        if profile.get("following_count") is not None:
            metrics.append(f"Following: {profile.get('following_count')}")
        if profile.get("repo_count") is not None:
            metrics.append(f"Repositories: {profile.get('repo_count')}")
        if profile.get("tweet_count") is not None:
            metrics.append(f"Tweets: {profile.get('tweet_count')}")
        
        if metrics:
            profile_desc += "Metrics: " + ", ".join(metrics) + "\n"
        
        # Add URL for reference
        if profile.get("url"):
            profile_desc += f"URL: {profile.get('url')}\n"
        
        descriptions.append(profile_desc)
    
    # Create a full description
    full_description = "# Social Profile Information\n\n"
    full_description += "\n".join(descriptions)
    
    return full_description

def generate_enriched_persona_with_gemini(description: str) -> Optional[Dict]:
    """
    Use Gemini to generate an enriched persona based on the profile description.
    
    Args:
        description: A string describing the profiles
        
    Returns:
        Dictionary containing the enriched persona or None if unsuccessful
    """
    if not GEMINI_API_KEY:
        print("Gemini API key not set. Cannot use Gemini API.")
        return None
    
    try:
        # Create a generation config for structured output
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
        }
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # Prompt template for Gemini
        prompt = f"""
        I have collected social profile information about a person. I need you to analyze this information 
        and create a comprehensive persona JSON that can be used for LinkedIn profile finding.
        
        Here's the information I've gathered:
        
        {description}
        
        Based on this information, please create a JSON persona with the following fields:
        - name: The person's full name (if available) or most likely name
        - intro: A professional headline or introduction for the person
        - company_industry: The industry they likely work in
        - company_size: Estimated company size (if identifiable)
        - location: Geographic location
        - timezone: Likely timezone based on location (if determinable)
        - social_profile: Array of social profile URLs
        - keywords: Array of professional keywords that describe their expertise
        - interests: Array of professional interests
        - skills: Array of likely professional skills
        - education: Any education information found
        - work_history: Any work history information found
        
        Format your response as a valid JSON object. Feel free to infer reasonable values for fields 
        that aren't explicitly mentioned in the profiles but can be reasonably inferred.
        
        Return ONLY the JSON object without any additional text or explanation.
        """
        
        # Initialize Gemini model (use the free model)
        model = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Generate the response
        response = model.generate_content(prompt)
        
        # Extract and parse the JSON from the response
        try:
            # Try to extract JSON directly from the response
            response_text = response.text
            
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse the JSON
            enriched_persona = json.loads(response_text)
            return enriched_persona
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Error parsing Gemini response: {e}")
            print(f"Response text: {response.text}")
            return None
    
    except Exception as e:
        print(f"Error with Gemini API: {e}")
        return None

def generate_enriched_persona(profile_blocks: List[Dict]) -> Dict:
    """
    Generate an enriched persona from raw social profile data using AI.
    Uses Gemini API for enrichment.
    
    Args:
        profile_blocks: List of dictionaries containing social profile data
        
    Returns:
        An enriched persona dictionary
    """
    # Construct a descriptive string from the profile data
    description = construct_profile_description(profile_blocks)
    
    # Extract existing profile URLs to preserve them
    social_profile_urls = []
    for profile in profile_blocks:
        if profile.get("url"):
            social_profile_urls.append(profile.get("url"))
    
    # Try with Gemini
    result = None
    if GEMINI_API_KEY:
        result = generate_enriched_persona_with_gemini(description)
    
    # If Gemini failed, create a basic persona from the raw data
    if result is None:
        result = create_basic_persona(profile_blocks)
    
    # Ensure the social_profile field contains the original URLs
    if "social_profile" not in result:
        result["social_profile"] = social_profile_urls
    else:
        # Combine AI-generated and original URLs, removing duplicates
        combined_urls = set(result["social_profile"] + social_profile_urls)
        result["social_profile"] = list(combined_urls)
    
    return result

def create_basic_persona(profile_blocks: List[Dict]) -> Dict:
    """
    Create a basic persona from raw profile data when AI enrichment fails.
    
    Args:
        profile_blocks: List of dictionaries containing social profile data
        
    Returns:
        A basic persona dictionary
    """
    # Initialize an empty persona
    persona = {
        "name": "",
        "intro": "",
        "location": "",
        "social_profile": []
    }
    
    # Fill in fields from available profile data
    for profile in profile_blocks:
        # Add profile URL to social_profile array
        if profile.get("url"):
            persona["social_profile"].append(profile.get("url"))
        
        # Set name if available and not already set
        if profile.get("display_name") and not persona["name"]:
            persona["name"] = profile.get("display_name")
        
        # Set intro/bio if available and not already set
        if profile.get("bio") and not persona["intro"]:
            # Clean up the bio text
            bio = profile.get("bio").replace("\n", " ").strip()
            persona["intro"] = bio[:100]  # Truncate long bios
            
        # Set location if available and not already set
        if profile.get("location") and not persona["location"]:
            persona["location"] = profile.get("location")
    
    return persona

# Example usage
if __name__ == "__main__":
    # Example profile blocks
    sample_profiles = [
        {
            "platform": "twitter",
            "username": "johndoe",
            "display_name": "John Doe",
            "bio": "Software Engineer | AI Enthusiast | Building things at TechCorp",
            "location": "San Francisco, CA",
            "followers_count": 1500,
            "following_count": 500,
            "url": "https://twitter.com/johndoe"
        },
        {
            "platform": "github",
            "username": "jdoe",
            "display_name": "John Doe",
            "bio": "Backend developer. Python, Go, and distributed systems.",
            "location": "San Francisco Bay Area",
            "followers_count": 250,
            "repo_count": 45,
            "company": "TechCorp",
            "url": "https://github.com/jdoe"
        }
    ]
    
    # Generate enriched persona
    enriched_persona = generate_enriched_persona(sample_profiles)
    
    # Print the result
    print(json.dumps(enriched_persona, indent=2))