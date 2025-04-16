import os
import requests
import imagehash
import numpy as np
from PIL import Image
from io import BytesIO
from typing import Optional, Tuple, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def load_image_from_url(url: str) -> Optional[Image.Image]:
    """
    Load an image from a URL and return it as a PIL Image.
    Returns None if the image cannot be loaded.
    """
    if not url:
        return None
    
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        
        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        return img
    except Exception as e:
        print(f"Error loading image from {url}: {e}")
        return None


def get_linkedin_profile_image(linkedin_id: str) -> Optional[str]:
    """
    Fetch a LinkedIn profile picture URL using ScrapingDog API.
    Returns None if the profile picture cannot be fetched.
    """
    if not linkedin_id:
        return None
    
    # Extract the username from the LinkedIn ID if it's a full URL
    if linkedin_id.startswith("http"):
        linkedin_id = linkedin_id.strip("/")
        linkedin_id = linkedin_id.split("/")[-1]
    
    # Get API key from environment variables
    api_key = os.environ.get("SCRAPINGDOG_API_KEY")
    if not api_key:
        print("SCRAPINGDOG_API_KEY not set in environment variables")
        return None
    
    try:
        url = f"https://api.scrapingdog.com/linkedin"
        params = {
            "api_key": api_key,
            "type": "profile",
            "linkId": linkedin_id
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        profile_pic_url = data.get("profile_pic_url")
        
        return profile_pic_url
    except Exception as e:
        print(f"Error fetching LinkedIn profile picture for {linkedin_id}: {e}")
        return None


def get_image_hash(image: Union[str, Image.Image]) -> Optional[imagehash.ImageHash]:
    """
    Calculate perceptual hash for an image URL or PIL Image.
    """
    try:
        # Load image if URL is provided
        if isinstance(image, str):
            img = load_image_from_url(image)
            if img is None:
                return None
        else:
            img = image
        
        # Calculate perceptual hash (using phash for better accuracy)
        img_hash = imagehash.phash(img)
        return img_hash
    except Exception as e:
        print(f"Error generating image hash: {e}")
        return None


def compute_similarity(hash1: imagehash.ImageHash, hash2: imagehash.ImageHash) -> float:
    """
    Compute similarity between two image hashes.
    Returns a float between 0 and 1.
    """
    try:
        # Calculate hash distance
        hash_distance = hash1 - hash2
        # Convert to similarity score (0-1)
        # Maximum hash distance depends on hash size, typically 64-bit hash has max distance of 64
        max_distance = 64.0  # For standard phash
        similarity = 1.0 - (hash_distance / max_distance)
        return max(0.0, min(1.0, similarity))
    except Exception as e:
        print(f"Error computing similarity: {e}")
        return 0.0


def compare_image_similarity_clip(url1: str, url2: str) -> float:
    """
    Compare two images using perceptual hashing and return a similarity score.
    Note: Function name kept the same for backward compatibility.
    
    Args:
        url1: URL of the first image
        url2: URL of the second image
        
    Returns:
        Similarity score between 0 and 1
    """
    # Get image hashes
    hash1 = get_image_hash(url1)
    hash2 = get_image_hash(url2)
    
    # Check if we have valid hashes
    if hash1 is None or hash2 is None:
        print("Could not generate valid hashes for both images")
        return 0.0
    
    # Compute similarity
    return compute_similarity(hash1, hash2)


def compare_linkedin_with_persona(linkedin_id: str, persona_image_url: str) -> Tuple[float, Optional[str]]:
    """
    Compare a LinkedIn profile picture with a persona image.
    
    Args:
        linkedin_id: LinkedIn ID or profile URL
        persona_image_url: URL of the persona image
        
    Returns:
        Tuple of (similarity_score, linkedin_image_url)
    """
    # Get LinkedIn profile picture
    linkedin_image_url = get_linkedin_profile_image(linkedin_id)
    
    if not linkedin_image_url:
        print(f"Could not fetch LinkedIn profile picture for {linkedin_id}")
        return 0.0, None
    
    # Compare images
    similarity = compare_image_similarity_clip(linkedin_image_url, persona_image_url)
    
    return similarity, linkedin_image_url


def validate_persona_match(linkedin_candidates: list, persona: dict, threshold: float = 0.7) -> list:
    """
    Validate LinkedIn profile candidates against a persona image.
    
    Args:
        linkedin_candidates: List of LinkedIn profile candidates
        persona: Person information including image URL
        threshold: Minimum similarity score to consider a match (0-1)
        
    Returns:
        List of validated candidates with similarity scores
    """
    if not persona.get("image"):
        # If no image, return original candidates
        return linkedin_candidates
    
    persona_image_url = persona.get("image")
    validated_candidates = []
    
    for candidate in linkedin_candidates:
        linkedin_id = candidate.get("link", "")
        
        # Skip if no valid LinkedIn ID
        if not linkedin_id or "linkedin.com/in/" not in linkedin_id:
            continue
        
        # Compare images
        similarity, linkedin_image_url = compare_linkedin_with_persona(linkedin_id, persona_image_url)
        
        # Add similarity info to candidate
        candidate["image_similarity"] = similarity
        candidate["profile_image"] = linkedin_image_url
        
        # Check if similarity is above threshold
        if similarity >= threshold:
            candidate["image_match"] = True
        else:
            candidate["image_match"] = False
        
        validated_candidates.append(candidate)
    
    # Sort by similarity score (highest first)
    validated_candidates.sort(key=lambda x: x.get("image_similarity", 0), reverse=True)
    
    return validated_candidates


# Example usage
if __name__ == "__main__":
    # Test with sample images
    image_url1 = "https://github.com/octocat.png"
    image_url2 = "https://avatars.githubusercontent.com/u/583231?v=4"
    
    similarity = compare_image_similarity_clip(image_url1, image_url2)
    print(f"Similarity between images: {similarity:.4f}")
    
    # Example LinkedIn validation
    linkedin_id = "some-linkedin-id"
    persona_image = "https://example.com/image.jpg"
    
    # Ensure we have the API key before attempting to call
    if os.environ.get("SCRAPINGDOG_API_KEY"):
        sim, linkedin_url = compare_linkedin_with_persona(linkedin_id, persona_image)
        print(f"LinkedIn profile similarity: {sim:.4f}")
        print(f"LinkedIn profile image URL: {linkedin_url}")