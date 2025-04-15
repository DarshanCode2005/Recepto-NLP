"""
People Data Labs API Integration

This module provides functions to enrich persona data using the People Data Labs API.
"""

import os
import json
import requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
PDL_API_KEY = os.environ.get("PEOPLE_API_KEY")
PDL_API_URL = "https://api.peopledatalabs.com/v5/person/enrich"

def enrich_persona_with_pdl(persona: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich persona data using the People Data Labs API.
    
    Args:
        persona: Dictionary containing person information
        
    Returns:
        Enriched persona dictionary or original persona if enrichment fails
    """
    if not PDL_API_KEY:
        print("People Data Labs API key not set. Skipping PDL enrichment.")
        return persona
    
    # Extract data from persona to use as search parameters
    params = create_pdl_params(persona)
    
    if not params:
        print("Insufficient data for PDL enrichment.")
        return persona
    
    try:
        # Make the API request
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": PDL_API_KEY
        }
        
        response = requests.post(
            PDL_API_URL,
            json=params,
            headers=headers,
            timeout=15
        )
        
        if response.status_code != 200:
            print(f"PDL API error: {response.status_code} - {response.text}")
            return persona
        
        # Parse the response
        pdl_data = response.json()
        
        # Check if we got a valid match
        if not pdl_data.get("status") or pdl_data.get("status") != 200:
            print(f"PDL API returned no match: {pdl_data.get('status')}")
            return persona
        
        # Enhance the persona with PDL data
        enhanced_persona = enhance_persona_with_pdl_data(persona, pdl_data)
        return enhanced_persona
        
    except Exception as e:
        print(f"Error enriching with PDL: {e}")
        return persona

def create_pdl_params(persona: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create parameters for the PDL API request based on persona data.
    
    Args:
        persona: Dictionary containing person information
        
    Returns:
        Dictionary of parameters for the PDL API
    """
    params = {}
    
    # Add name if available
    if persona.get("name"):
        params["name"] = persona.get("name")
    
    # Add location if available
    if persona.get("location"):
        params["location"] = persona.get("location")
    
    # Add company information if available
    if persona.get("company_industry") or persona.get("company"):
        company = persona.get("company", "")
        industry = persona.get("company_industry", "")
        
        if company:
            params["company"] = company
        if industry and not company:
            # Use industry as company if no company name available
            params["company"] = industry
    
    # Add social profile URLs
    social_urls = {}
    for url in persona.get("social_profile", []):
        if "github.com" in url:
            social_urls["github"] = url
        elif "twitter.com" in url or "x.com" in url:
            social_urls["twitter"] = url
        elif "linkedin.com" in url:
            social_urls["linkedin"] = url
    
    if social_urls:
        params["profile"] = social_urls
    
    # Add email if available
    if persona.get("email"):
        params["email"] = persona.get("email")
    
    # Return empty dict if we don't have enough info
    if len(params) < 2:  # Need at least 2 identifiers for good results
        return {}
    
    # Set required parameters
    request_params = {
        "params": params,
        "min_likelihood": 0.6,  # Only return reasonably confident matches
        "required": ["full_name", "job_title", "work_email"]  # Require these fields
    }
    
    return request_params

def enhance_persona_with_pdl_data(persona: Dict[str, Any], pdl_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance persona with data from PDL API response.
    
    Args:
        persona: Original persona dictionary
        pdl_data: PDL API response data
        
    Returns:
        Enhanced persona dictionary
    """
    # Start with the original persona
    enhanced = persona.copy()
    
    # Only proceed if we have actual data
    if "data" not in pdl_data:
        return enhanced
    
    data = pdl_data["data"]
    
    # Update name if not already set
    if data.get("full_name") and not enhanced.get("name"):
        enhanced["name"] = data.get("full_name")
    
    # Update intro/professional headline
    if data.get("job_title") and not enhanced.get("intro"):
        company_name = data.get("job_company_name", "")
        job_title = data.get("job_title", "")
        
        if company_name:
            enhanced["intro"] = f"{job_title} at {company_name}"
        else:
            enhanced["intro"] = job_title
    
    # Update location
    if data.get("location_name") and not enhanced.get("location"):
        enhanced["location"] = data.get("location_name")
    
    # Update company industry
    if data.get("job_company_industry") and not enhanced.get("company_industry"):
        enhanced["company_industry"] = data.get("job_company_industry")
    
    # Update company size if available
    if data.get("job_company_size") and not enhanced.get("company_size"):
        enhanced["company_size"] = data.get("job_company_size")
    
    # Update company name
    if data.get("job_company_name") and not enhanced.get("company"):
        enhanced["company"] = data.get("job_company_name")
    
    # Add work email if available
    if data.get("work_email") and not enhanced.get("email"):
        enhanced["email"] = data.get("work_email")
    
    # Add skills
    if data.get("skills") and not enhanced.get("skills"):
        enhanced["skills"] = data.get("skills")
    
    # Add education
    if data.get("education") and not enhanced.get("education"):
        education_list = []
        for edu in data.get("education", []):
            school = edu.get("school", {})
            degree = edu.get("degree", {})
            
            education_entry = {
                "school": school.get("name", ""),
                "degree": degree.get("name", ""),
                "field": degree.get("fields", [""])[0] if degree.get("fields") else "",
                "start_date": edu.get("start_date", ""),
                "end_date": edu.get("end_date", ""),
            }
            education_list.append(education_entry)
        
        if education_list:
            enhanced["education"] = education_list
    
    # Add work history
    if data.get("experience") and not enhanced.get("work_history"):
        work_history = []
        for exp in data.get("experience", []):
            company = exp.get("company", {})
            
            experience_entry = {
                "company": company.get("name", ""),
                "title": exp.get("title", ""),
                "start_date": exp.get("start_date", ""),
                "end_date": exp.get("end_date", ""),
                "industry": company.get("industry", ""),
            }
            work_history.append(experience_entry)
        
        if work_history:
            enhanced["work_history"] = work_history
    
    # Add social profiles that might be missing
    if data.get("profiles"):
        existing_social_urls = set(enhanced.get("social_profile", []))
        for profile in data.get("profiles", []):
            url = profile.get("url", "")
            if url and url not in existing_social_urls:
                if "social_profile" not in enhanced:
                    enhanced["social_profile"] = []
                enhanced["social_profile"].append(url)
    
    # Add keywords based on skills
    if data.get("skills") and not enhanced.get("keywords"):
        enhanced["keywords"] = data.get("skills")[:10] if len(data.get("skills", [])) > 10 else data.get("skills", [])
    
    return enhanced

# Example usage
if __name__ == "__main__":
    sample_persona = {
        "name": "John Smith",
        "location": "San Francisco, CA",
        "social_profile": ["https://github.com/johnsmith", "https://twitter.com/johnsmith"]
    }
    
    enriched = enrich_persona_with_pdl(sample_persona)
    print(json.dumps(enriched, indent=2)) 