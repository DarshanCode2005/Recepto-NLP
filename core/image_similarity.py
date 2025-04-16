import os
import requests
import imagehash
import numpy as np
from PIL import Image
from io import BytesIO
from typing import Optional, Tuple, Union
from dotenv import load_dotenv
import time

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
    Fetch a LinkedIn profile picture URL using Brightdata API.
    Returns None if the profile picture cannot be fetched.
    """
    if not linkedin_id:
        return None
    
    # Extract the username from the LinkedIn ID if it's a full URL
    if linkedin_id.startswith("http"):
        linkedin_id = linkedin_id.strip("/")
        linkedin_id = linkedin_id.split("/")[-1]
    
    # Get API key from environment variables
    api_key = os.environ.get("BRIGHTDATA_API_KEY")
    if not api_key:
        print("BRIGHTDATA_API_KEY not set in environment variables")
        return None
    
    try:
        BASE = "https://api.brightdata.com/datasets/v3"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        params = {
            "dataset_id": "gd_l1viktl72bvl7bjuj0",
            "include_errors": "true",
        }
        
        # Construct the LinkedIn URL
        linkedin_url = f"https://www.linkedin.com/in/{linkedin_id}"
        
        # Trigger the snapshot
        trigger = requests.post(
            f"{BASE}/trigger",
            headers=headers,
            params=params,
            json=[{"url": linkedin_url}],
        )
        trigger.raise_for_status()
        snap_resp = trigger.json()
        snapshot_id = snap_resp.get("snapshot_id")
        if not snapshot_id:
            print(f"No snapshot_id in trigger response: {snap_resp}")
            return None
        
        print(f"Triggered snapshot: {snapshot_id}")
        
        # Wait for the snapshot to be ready
        download_url = f"{BASE}/snapshot/{snapshot_id}"
        for attempt in range(60):  # ~5 minutes max
            r = requests.get(download_url, headers=headers)
            
            if r.status_code == 202:
                try:
                    status = r.json().get("status")
                except ValueError:
                    status = "unknown"
                print(f"[{attempt+1:02d}/60] task not completed status={status}")
                time.sleep(5)
                continue
            
            if r.status_code == 404:
                print(f"Snapshot not found: {snapshot_id}")
                return None
            
            r.raise_for_status()
            
            data = r.json()
            print("Snapshot ready, fetched results.")
            
            # Extract profile picture URL from the response
            if isinstance(data, list) and len(data) > 0:
                profile_data = data[0]
            else:
                profile_data = data
                
            # Try to get the profile picture URL using different possible keys
            profile_pic_url = None
            possible_keys = ["profile_pic_url", "profilePicture", "profile_picture", "picture", "image"]
            
            for key in possible_keys:
                if isinstance(profile_data, dict) and key in profile_data:
                    profile_pic_url = profile_data[key]
                    if profile_pic_url:
                        break
            
            return profile_pic_url
        
        print("Timed out waiting for snapshot to be ready")
        return None
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
    Currently disabled due to issues with image similarity.
    
    Args:
        linkedin_candidates: List of LinkedIn profile candidates
        persona: Person information including image URL
        threshold: Minimum similarity score to consider a match (0-1)
        
    Returns:
        List of candidates with default image similarity values
    """
    # Skip image similarity check for now
    print("Image similarity check is currently disabled")
    
    # Add default values to candidates
    for candidate in linkedin_candidates:
        candidate["image_similarity"] = 0.0
        candidate["profile_image"] = None
        candidate["image_match"] = False
    
    return linkedin_candidates


# Example usage
if __name__ == "__main__":
    print("Image similarity functionality is currently disabled.")
    print("To test other functionality, you can use the following code:")
    
    # Example of how to use the disabled functionality
    # linkedin_id = "https://www.linkedin.com/in/zhawtof/"
    # persona_image = "https://drive.google.com/file/d/1G4nkXOR_f-RGKdXw0HJctVmVVcSU6VS2/view?usp=drive_link"
    
    # if os.environ.get("BRIGHTDATA_API_KEY"):
    #     sim, linkedin_url = compare_linkedin_with_persona(linkedin_id, persona_image)
    #     print(f"LinkedIn profile similarity: {sim:.4f}")
    #     print(f"LinkedIn profile image URL: {linkedin_url}")
    # else:
    #     print("BRIGHTDATA_API_KEY not set in environment variables")