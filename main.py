import os
import json
from dotenv import load_dotenv
from core.query_generator import generate_search_queries, search_linkedin_profiles
from core.name_expansion import expand_name_from_initial, extract_name_from_snippet
from core.social_scraper import scrape_social_profiles, enrich_persona_with_social_data
from core.image_similarity import compare_image_similarity_clip, validate_persona_match
from core.profile_scoring import score_linkedin_candidate, rank_linkedin_candidates
from api.gemini_api import generate_enriched_persona
from api.people_api import enrich_persona_with_pdl

# Load environment variables from .env file
load_dotenv()

def main():
    # Example persona
    persona = {
        "name": "Samantha Carter",
        "intro": "Head of Product at Astrogate — building AI systems for enterprise automation",
        "company_industry": "Artificial Intelligence",
        "company_size": "51–200 Employees",
        "timezone": "America/New_York",
        "location": "Brooklyn, NY",
        "social_profile": [
            "https://twitter.com/samcarter_ai",
            "https://github.com/samcarter"
        ],
        "image": "https://images.generated.photos/samantha_carter.jpg"
    }
    
    # Generate search queries
    queries = generate_search_queries(persona)
    print("Generated search queries:")
    for i, query in enumerate(queries[:10], 1):
        print(f"{i}. {query}")
    
    # Example of name expansion
    print("\nName Expansion Examples:")
    abbreviated_name = "Darshan T."
    expanded_names = expand_name_from_initial(abbreviated_name)
    print(f"Original name: {abbreviated_name}")
    print("Expanded names:")
    for i, name in enumerate(expanded_names[:5], 1):
        print(f"{i}. {name}")
    
    # Example of snippet extraction
    print("\nSnippet Extraction Example:")
    snippet = "Darshan Thakare is a software engineer with expertise in AI and machine learning."
    extracted_names = extract_name_from_snippet(snippet, "Darshan T.")
    print(f"Snippet: {snippet}")
    print("Extracted names:")
    for i, name in enumerate(extracted_names, 1):
        print(f"{i}. {name}")
    
    # Example of social media profile scraping
    print("\nSocial Media Scraping Example:")
    # Define demo profiles to use since Twitter API may not be available
    demo_social_urls = []
    
    # Use GitHub profile which can be scraped without API key
    demo_social_urls.append("https://github.com/octocat")
    
    # Check if Twitter API is available before adding Twitter URLs
    if os.environ.get("TWITTER_BEARER_TOKEN"):
        demo_social_urls.append("https://twitter.com/github")
        print("Twitter API key is available - including Twitter profile in scraping")
    else:
        print("Twitter API key not available - using public GitHub profile only")
    
    print("Scraping social profiles...")
    social_profiles = scrape_social_profiles(demo_social_urls)
    
    for profile in social_profiles:
        print(f"\n{profile['platform'].upper()} profile for {profile['username']}:")
        for key, value in profile.items():
            if key not in ['platform', 'username'] and value is not None:
                print(f"  {key}: {value}")
    
    # Example of persona enrichment from social data
    print("\nPersona Enrichment Example:")
    minimal_persona = {
        "name": "",
        "social_profile": demo_social_urls
    }
    
    # Step 1: Enrich with social data
    print("\nStep 1: Enriching with social data...")
    social_enriched_persona = enrich_persona_with_social_data(minimal_persona)
    print(f"After social enrichment:")
    print(f"Name: '{social_enriched_persona.get('name', '')}'")
    print(f"Location: '{social_enriched_persona.get('location', '')}'")
    print(f"Intro: '{social_enriched_persona.get('intro', '')}'")
    
    # Step 2: Enrich with People Data Labs if available
    if os.environ.get("PEOPLE_API_KEY"):
        print("\nStep 2: Enriching with People Data Labs API...")
        pdl_enriched_persona = enrich_persona_with_pdl(social_enriched_persona)
        print(f"After PDL enrichment:")
        print(f"Name: '{pdl_enriched_persona.get('name', '')}'")
        print(f"Company: '{pdl_enriched_persona.get('company', '')}'")
        print(f"Industry: '{pdl_enriched_persona.get('company_industry', '')}'")
        print(f"Skills: {pdl_enriched_persona.get('skills', [])[:3]}...")
        
        # Use PDL enriched persona for further steps
        enriched_persona = pdl_enriched_persona
    else:
        print("\nStep 2: People Data Labs API key not set, skipping PDL enrichment")
        enriched_persona = social_enriched_persona
    
    # Step 3: Enrich with Gemini AI if available
    if os.environ.get("GEMINI_API_KEY"):
        print("\nStep 3: Enriching with Gemini AI...")
        ai_enriched_persona = generate_enriched_persona(social_profiles)
        
        print("\nAI-Enhanced Persona:")
        print(json.dumps(ai_enriched_persona, indent=2))
        
        # Generate search queries with AI-enhanced persona
        ai_queries = generate_search_queries(ai_enriched_persona)
        print("\nAI-Enhanced Search Queries:")
        for i, query in enumerate(ai_queries[:5], 1):
            print(f"{i}. {query}")
            
        # Use AI enriched persona for final step
        final_persona = ai_enriched_persona
    else:
        print("\nStep 3: Gemini API key not set, skipping AI enrichment")
        final_persona = enriched_persona
    
    # Example of image similarity comparison
    if os.environ.get("SCRAPINGDOG_API_KEY") and "image" in persona:
        print("\nImage Similarity Example:")
        # Using GitHub profile images for demonstration since they're publicly accessible
        image_url1 = "https://github.com/octocat.png"
        image_url2 = "https://avatars.githubusercontent.com/u/583231?v=4"
        
        print("Comparing two sample images...")
        similarity = compare_image_similarity_clip(image_url1, image_url2)
        print(f"Similarity score: {similarity:.4f}")
    
    # If SERPAPI_API_KEY is set, search for LinkedIn profiles
    if os.environ.get("SERPAPI_API_KEY"):
        print("\nSearching for LinkedIn profiles...")
        try:
            # Use the most enriched persona we have
            results = search_linkedin_profiles(final_persona, max_results=5)
            print(f"\nFound {len(results)} LinkedIn profiles:")
            for i, result in enumerate(results, 1):
                print(f"{i}. {result['title']}")
                print(f"   {result['link']}")
                print(f"   {result['snippet']}\n")
            
            # Score candidates using the profile_scoring module
            print("\nScoring LinkedIn profiles against persona...")
            scored_results = rank_linkedin_candidates(final_persona, results)
            
            print("\nRanked LinkedIn profiles:")
            for i, result in enumerate(scored_results, 1):
                confidence = result["confidence"]
                print(f"{i}. {result['profile']['title']} (Confidence: {confidence}%)")
                print(f"   {result['profile']['link']}")
                print(f"   {result['profile']['snippet']}")
                print("   Score breakdown:")
                for score_type, score in result["scores"].items():
                    print(f"     {score_type}: {score}%")
                print()
            
            # Validate candidates using image similarity if both API keys are available
            if os.environ.get("SCRAPINGDOG_API_KEY") and "image" in persona and results:
                print("\nValidating candidates using image similarity...")
                validated_results = validate_persona_match(results, persona, threshold=0.65)
                
                print("\nImage-validated LinkedIn profiles:")
                for i, result in enumerate(validated_results, 1):
                    match_indicator = "✓" if result.get("image_match", False) else "✗"
                    similarity = result.get("image_similarity", 0)
                    print(f"{i}. {match_indicator} {result['title']} (Image similarity: {similarity:.2f})")
                    print(f"   {result['link']}")
                    print(f"   {result['snippet']}\n")
                
                # Combine profile scoring and image validation for final results
                print("\nFinal combined scoring results:")
                for result in scored_results[:3]:  # Show top 3 results
                    profile_link = result["profile"]["link"]
                    # Find the image similarity score for this profile
                    img_similarity = 0.0
                    img_match = False
                    for v_result in validated_results:
                        if v_result["link"] == profile_link:
                            img_similarity = v_result.get("image_similarity", 0.0)
                            img_match = v_result.get("image_match", False)
                            break
                    
                    confidence = result["confidence"]
                    match_indicator = "✓" if img_match else "✗"
                    print(f"{match_indicator} {result['profile']['title']}")
                    print(f"   Confidence: {confidence}% | Image similarity: {img_similarity:.2f}")
                    print(f"   {profile_link}")
                    print(f"   {result['profile']['snippet']}\n")
        
        except Exception as e:
            print(f"Error searching LinkedIn profiles: {e}")
    else:
        print("\nSERPAPI_API_KEY not set. Skipping LinkedIn profile search.")
    
    print("\nDemonstration complete.")

if __name__ == "__main__":
    main()
