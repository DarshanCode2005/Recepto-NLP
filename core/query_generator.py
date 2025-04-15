import os
import re
from typing import Dict, List, Any, Set, Tuple
from nameparser import HumanName
from serpapi import GoogleSearch

# Import our name expansion module if available
try:
    from core.name_expansion import expand_name_from_initial
except ImportError:
    # Fallback function if the module isn't available
    def expand_name_from_initial(name: str) -> List[str]:
        return [name]

def generate_name_variants(name: str) -> List[str]:
    """Generate multiple name format variants from a full name."""
    if not name:
        return []

    variants = set()
    parsed = HumanName(name)

    # Add first name
    if parsed.first:
        variants.add(parsed.first)

        # Add first + last name combinations
        if parsed.last:
            variants.add(f"{parsed.first} {parsed.last}")
            variants.add(f"{parsed.first[0]}. {parsed.last}")

            # Add middle initial variants if available
            if parsed.middle:
                variants.add(f"{parsed.first} {parsed.middle[0]}. {parsed.last}")
                variants.add(f"{parsed.first} {parsed.middle} {parsed.last}")

    # Add full name and nickname variants
    variants.add(name)
    if parsed.nickname:
        variants.add(parsed.nickname)
        if parsed.last:
            variants.add(f"{parsed.nickname} {parsed.last}")
    
    # Check if the name has any initials that we could expand
    if re.search(r'\b[A-Z]\.\s', name) or re.search(r'\s[A-Z]\b', name):
        # Try to expand initials
        expanded_variants = expand_name_from_initial(name)
        variants.update(expanded_variants)

    return list(variants)

def infer_role_from_size_and_intro(company_size: str, intro: str = "") -> str:
    if intro:
        intro_lower = intro.lower()
        if any(word in intro_lower for word in ["founder", "co-founder", "ceo", "started", "my company", "built", "entrepreneur"]):
            return "Founder"
        elif any(word in intro_lower for word in ["manager", "director", "vp", "team lead"]):
            return "Manager"
        elif "consultant" in intro_lower:
            return "Consultant"
        elif "engineer" in intro_lower:
            return "Engineer"

    # Only fallback to company_size if intro gave no signal
    if not company_size:
        return ""

    size = company_size.lower()
    if "1" in size or "0" in size:
        return "Founder"
    elif "11" in size:
        return "Co-founder"
    elif "50" in size:
        return "Team Lead"
    elif "200" in size or "500" in size:
        return "Manager"
    elif "1000" in size or "+" in size:
        return "Staff"  # generic, neutral
    return ""

def extract_social_usernames(social_profiles: List[str]) -> Dict[str, List[str]]:
    usernames_dict = {}

    # Patterns for different social media platforms
    patterns = {
        'twitter': r'(?:twitter\.com|x\.com)/(@?[\w\d\-_]+)',
        'github': r'github\.com/([\w\d\-_]+)',
        'bluesky': r'(?:bsky\.app|bsky\.social)/profile/([\w\d\-_\.]+)',
        'instagram': r'instagram\.com/(?!p/)(@?[\w\d\._]+)',
        'facebook': r'facebook\.com/(?!(?:pages|groups|events)/)([^/\?]+)',
        'linkedin': r'linkedin\.com/in/([\w\d\-_]+)',
        'youtube': r'youtube\.com/(?:c/|channel/|user/|@)([\w\d\-_]+)',
        'tiktok': r'tiktok\.com/(@[\w\d\._]+)',
        'mastodon': r'([\w\d\-_\.]+)@([\w\d\-_\.]+)',  # username@instance.domain
        'threads': r'threads\.net/(@?[\w\d\._]+)'
    }

    for url in social_profiles:
        url = url.strip()

        for platform, pattern in patterns.items():
            match = re.search(pattern, url)
            if match:
                username = match.group(1)

                # Format usernames properly
                if platform == 'twitter' and not username.startswith('@'):
                    username = f'@{username}'
                elif platform == 'tiktok' and not username.startswith('@'):
                    username = f'@{username}'
                elif platform == 'instagram' and not username.startswith('@'):
                    username = f'@{username}'
                elif platform == 'bluesky' and not username.startswith('@'):
                    username = f'@{username}'

                # Add to results dictionary
                if platform not in usernames_dict:
                    usernames_dict[platform] = []
                usernames_dict[platform].append(username)
                break

    return usernames_dict

def enrich_persona_with_api(persona: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optional: Try enriching the persona using PeopleDataLabs or Clearbit
    if name-only data is available.
    Returns the enriched persona or the same if not enriched.
    """
    # Defensive programming
    if not persona or not isinstance(persona, dict):
        return persona

    name = persona.get("name", "")
    if not name or len(name.split()) < 1:
        return persona  # not enough info to enrich

    # Example enrichment - This is a placeholder for actual API integration
    # result = people_data_labs_enrich(name=name)
    # if result:
    #     persona["company_industry"] = result.get("industry")
    #     persona["intro"] = result.get("job_title")
    #     persona["location"] = result.get("location")

    return persona

def score_query(query: str, weights: Dict[str, float]) -> float:
    """
    Score a search query based on the weights of its components.
    Applies some penalties and bonuses based on query structure.
    """
    score = sum(weights.values())

    # Bonus for queries with multiple high-value components
    if len(weights) >= 3:
        score *= 1.2

    # Penalty for very long queries
    if len(query.split()) > 10:
        score *= 0.9

    return score

def generate_search_queries(persona: Dict[str, Any]) -> List[str]:
    """
    Generate ranked search queries based on a person's information.
    Returns a list of search queries ordered by relevance.
    
    Args:
        persona: Dictionary containing the person's information with keys such as:
            - name: Full name (required)
            - intro: Brief professional introduction or job title
            - company_industry: Industry the person works in
            - company_size: Size of company (used to infer role)
            - social_profile: List of social media profile URLs
            - location: Geographic location
    
    Returns:
        List of search queries ranked by relevance
    """
    # Input validation
    if not persona or not isinstance(persona, dict):
        return []

    # Enrich and extract persona data
    persona = enrich_persona_with_api(persona)
    name = persona.get("name", "")
    intro = persona.get("intro", "")
    company = persona.get("company_industry", "")
    company_size = persona.get("company_size", "")
    social_profiles = persona.get("social_profile", [])
    location = persona.get("location", "")

    if not name:  # Name is required
        return []

    queries = []

    # Build base name variants
    name_variants = generate_name_variants(name)
    
    # Check if the name might have initials that need expanding
    if any(re.search(r'\b[A-Z]\.\s', variant) or re.search(r'\s[A-Z]\b', variant) for variant in name_variants):
        # Add expanded variants for names with initials
        expanded_variants = []
        for variant in name_variants:
            if re.search(r'\b[A-Z]\.\s', variant) or re.search(r'\s[A-Z]\b', variant):
                expanded_variants.extend(expand_name_from_initial(variant))
        
        # Add the expanded variants to our name_variants list
        name_variants.extend(expanded_variants)
        
        # Remove duplicates while preserving order
        seen = set()
        name_variants = [x for x in name_variants if not (x in seen or seen.add(x))]

    # Get social usernames
    social_data = extract_social_usernames(social_profiles)
    social_usernames = []
    for platform_usernames in social_data.values():
        social_usernames.extend(platform_usernames)

    # Infer likely role based on company size
    inferred_role = infer_role_from_size_and_intro(company_size, intro)

    # Generate queries with various combinations
    for variant in name_variants:
        # Basic name-only query
        base = f'"{variant}" site:linkedin.com/in'
        queries.append((base, {"name": 1.0}))

        # Name + job title/intro
        if intro:
            queries.append((f'"{variant}" "{intro}" site:linkedin.com/in',
                           {"name": 1.0, "intro": 0.8}))

        # Name + company/industry
        if company:
            queries.append((f'"{variant}" "{company}" site:linkedin.com/in',
                           {"name": 1.0, "company": 0.7}))
            # Name + company + intro for higher specificity
            if intro:
                queries.append((f'"{variant}" "{company}" "{intro}" site:linkedin.com/in',
                               {"name": 1.0, "company": 0.7, "intro": 0.8}))

        # Name + inferred role
        if inferred_role:
            queries.append((f'"{variant}" "{inferred_role}" site:linkedin.com/in',
                           {"name": 1.0, "role": 0.6}))
            # Name + inferred role + company
            if company:
                queries.append((f'"{variant}" "{inferred_role}" "{company}" site:linkedin.com/in',
                               {"name": 1.0, "role": 0.6, "company": 0.7}))

        # Name + location for local professionals
        if location:
            queries.append((f'"{variant}" "{location}" site:linkedin.com/in',
                           {"name": 1.0, "location": 0.5}))

        # Fallback generic role queries
        common_roles = ["Founder", "CEO", "CTO", "Director", "Manager", "Lead"]
        if not intro and not inferred_role:
            for role in common_roles:
                queries.append((f'"{variant}" "{role}" site:linkedin.com/in',
                               {"name": 1.0, "fallback": 0.4}))

    # Social handle-based queries
    for handle in social_usernames:
        queries.append((f'"{handle}" site:linkedin.com/in', {"social": 0.9}))

        # Try to combine social handles with name for better matches
        if name_variants:
            primary_name = name_variants[0]
            queries.append((f'"{handle}" "{primary_name}" site:linkedin.com/in',
                           {"social": 0.9, "name": 1.0}))

    # Deduplicate and rank queries
    seen = set()
    ranked_queries = []

    for query, weights in queries:
        if query not in seen:
            ranked_queries.append((query, score_query(query, weights)))
            seen.add(query)

    # Sort by score in descending order
    ranked_queries.sort(key=lambda x: x[1], reverse=True)

    # Return only the query strings, not their scores
    return [query for query, _ in ranked_queries]

def search_linkedin_profiles(persona, max_results=5):
    """
    Search for LinkedIn profiles using generated queries.
    This is a helper function to demonstrate usage of the query generator.
    
    Args:
        persona: Dictionary containing person information
        max_results: Maximum number of results to return
        
    Returns:
        List of dictionaries containing LinkedIn profile information
    """
    queries = generate_search_queries(persona)
    seen = set()
    candidates = []
    
    # Get SERPAPI API key from environment variables
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        raise ValueError("SERPAPI_API_KEY environment variable is not set")

    for query in queries:
        params = {
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "num": max_results
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        for result in results.get("organic_results", []):
            link = result.get("link", "")
            snippet = result.get("snippet", "")
            if "linkedin.com/in/" in link and link not in seen:
                candidates.append({
                    "link": link,
                    "title": result.get("title"),
                    "snippet": snippet
                })
                seen.add(link)

            if len(candidates) >= max_results:
                break

        if len(candidates) >= max_results:
            break

    return candidates