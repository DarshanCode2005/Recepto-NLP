import re
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter

# Common Indian surnames by region
COMMON_INDIAN_SURNAMES = {
    # Maharashtrian surnames
    "Maharashtra": ["Thakare", "Thakur", "Thakre", "Patil", "Deshmukh", "Kulkarni", "Deshpande", "Joshi"],
    # South Indian surnames
    "South": ["Iyer", "Iyengar", "Nair", "Menon", "Reddy", "Pillai", "Naidu", "Acharya"],
    # North Indian surnames
    "North": ["Sharma", "Singh", "Yadav", "Gupta", "Verma", "Kumar", "Shukla", "Tiwari"],
    # Bengali surnames
    "Bengal": ["Banerjee", "Chatterjee", "Mukherjee", "Sen", "Das", "Bose", "Ghosh", "Roy"],
    # Gujarati surnames
    "Gujarat": ["Patel", "Shah", "Modi", "Desai", "Mehta", "Gandhi", "Joshi", "Trivedi"]
}

# Common western surnames
COMMON_WESTERN_SURNAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", 
    "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson", "Taylor", 
    "Thomas", "Hernandez", "Moore", "Martin", "Jackson", "Thompson", "White"
]

def extract_initials(name: str) -> List[Tuple[str, str]]:
    """
    Extract first name and initial(s) from a name string.
    Returns a list of (first_name, initial) tuples.
    
    Examples:
    "Darshan T." -> [("Darshan", "T")]
    "D. T. Sharma" -> [("D", "T"), ("D", "T Sharma")]
    """
    # Regular expression to match names with initials
    patterns = [
        r'(\w+)\s+([A-Z])\.?$',                      # "Darshan T" or "Darshan T."
        r'(\w+)\s+([A-Z])\.?\s+(\w+)',               # "Darshan T Sharma"
        r'([A-Z])\.?\s+([A-Z])\.?\s+(\w+)',          # "D T Sharma"
        r'([A-Z])\.?\s+([A-Z])\.?$',                 # "D T" or "D. T."
        r'(\w+)\s+([A-Z])\.?\s+([A-Z])\.?\s+(\w+)'   # "Darshan T S Sharma"
    ]
    
    results = []
    for pattern in patterns:
        match = re.match(pattern, name)
        if match:
            groups = match.groups()
            if len(groups) == 2:  # "Darshan T"
                results.append((groups[0], groups[1]))
            elif len(groups) == 3 and groups[0].islower():  # "Darshan T Sharma"
                results.append((groups[0], groups[1]))
                # Also include the full name as a possible expansion
                results.append((groups[0], f"{groups[1]} {groups[2]}"))
            elif len(groups) == 3 and groups[0].isupper():  # "D T Sharma"
                results.append((groups[0], groups[1]))
                # Also include the full name with initials
                results.append((groups[0], f"{groups[1]} {groups[2]}"))
            elif len(groups) == 4:  # "Darshan T S Sharma"
                results.append((groups[0], groups[1]))
                results.append((groups[0], groups[2]))
                # Include combinations
                results.append((groups[0], f"{groups[1]} {groups[3]}"))
                results.append((groups[0], f"{groups[2]} {groups[3]}"))
                
    return results

def get_regional_surname_variants(initial: str, region: Optional[str] = None) -> List[str]:
    """
    Generate full surname variants based on an initial and optionally a region.
    If no region is specified, returns surnames from all regions.
    """
    variants = []
    
    # Filter surname dictionaries by the initial
    if region and region in COMMON_INDIAN_SURNAMES:
        surnames = [s for s in COMMON_INDIAN_SURNAMES[region] if s.startswith(initial)]
        variants.extend(surnames)
    else:
        # If no region or region not found, try all regions
        for region_surnames in COMMON_INDIAN_SURNAMES.values():
            surnames = [s for s in region_surnames if s.startswith(initial)]
            variants.extend(surnames)
        
        # Also try western surnames
        western_surnames = [s for s in COMMON_WESTERN_SURNAMES if s.startswith(initial)]
        variants.extend(western_surnames)
        
    return variants

def score_name_expansion(original_name: str, expanded_name: str) -> float:
    """
    Score the likelihood of an expanded name being correct.
    Higher scores indicate better matches.
    """
    score = 1.0
    
    # Favor expansions that preserve the original name components
    for part in original_name.split():
        if part.endswith('.'):
            # For initials, check if they match in the expanded name
            initial = part.rstrip('.')
            if not any(word.startswith(initial) for word in expanded_name.split()):
                score -= 0.3
        elif part not in expanded_name:
            score -= 0.2
            
    # Bonus for names with realistic length
    words = expanded_name.split()
    if len(words) <= 4:  # Most names have 1-4 parts
        score += 0.1
    else:
        score -= 0.2 * (len(words) - 4)  # Penalty for very long names
        
    # Bonus for names with recognized surnames
    surname = words[-1] if words else ""
    all_surnames = []
    for surnames in COMMON_INDIAN_SURNAMES.values():
        all_surnames.extend(surnames)
    all_surnames.extend(COMMON_WESTERN_SURNAMES)
    
    if surname in all_surnames:
        score += 0.2
        
    return score

def expand_name_from_initial(name: str) -> List[str]:
    """
    Expand a name with initials into possible full names.
    
    Args:
        name: A name string, potentially containing initials (e.g., "Darshan T.")
        
    Returns:
        A list of possible expanded names, ranked by likelihood
    """
    if not name:
        return []
    
    expanded_names = set()
    
    # Extract initial pattern
    initials_data = extract_initials(name)
    
    for first_name, initial in initials_data:
        # If the initial has a space, it might already have a surname
        if ' ' in initial:
            parts = initial.split()
            if len(parts) == 2:  # Initial + Surname
                expanded_names.add(f"{first_name} {parts[1]}")
                
                # Also try to expand the middle initial if this is a triple name
                if len(parts[0]) == 1:
                    middle_variants = get_regional_surname_variants(parts[0])
                    for middle in middle_variants:
                        expanded_names.add(f"{first_name} {middle} {parts[1]}")
            continue
            
        # Get surname variants for the initial
        surname_variants = get_regional_surname_variants(initial)
        
        # Create expanded names
        for surname in surname_variants:
            expanded_names.add(f"{first_name} {surname}")
    
    # Add original name (in case it's already complete)
    expanded_names.add(name)
    
    # Score and rank the expanded names
    scored_names = [(name_variant, score_name_expansion(name, name_variant)) 
                    for name_variant in expanded_names]
    
    # Sort by score in descending order
    scored_names.sort(key=lambda x: x[1], reverse=True)
    
    # Return only the names, not their scores
    return [name for name, _ in scored_names]

def extract_name_from_snippet(snippet: str, name_hint: str) -> List[str]:
    """
    Extract potential full names from search result snippets 
    using a partial name as a hint.
    
    Args:
        snippet: Text snippet from search results
        name_hint: Partial name to guide extraction
        
    Returns:
        List of potential full names found in the snippet
    """
    if not snippet or not name_hint:
        return []
    
    # Extract the first name from the hint
    first_name_match = re.search(r'^(\w+)', name_hint)
    if not first_name_match:
        return []
    
    first_name = first_name_match.group(1)
    
    # Look for patterns like "First_name [Middle_name] Last_name"
    # Account for different variations and formats
    patterns = [
        rf'{first_name}\s+\w+\s+\w+',  # First Middle Last
        rf'{first_name}\s+\w+',         # First Last
        rf'{first_name}\s+[A-Z]\.\s+\w+', # First I. Last
        rf'{first_name}\s+[A-Z]\s+\w+',   # First I Last
    ]
    
    found_names = []
    for pattern in patterns:
        matches = re.finditer(pattern, snippet, re.IGNORECASE)
        for match in matches:
            found_names.append(match.group(0))
    
    return found_names

# Example usage
if __name__ == "__main__":
    # Examples
    print(expand_name_from_initial("Darshan T."))
    print(expand_name_from_initial("S. Kumar"))
    
    # Example with snippet extraction
    snippet = "Darshan Thakare is a software engineer with expertise in AI and machine learning."
    print(extract_name_from_snippet(snippet, "Darshan T."))