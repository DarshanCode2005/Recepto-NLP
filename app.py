import os
import json
import streamlit as st
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import requests
import base64

from core.query_generator import generate_search_queries, search_linkedin_profiles
from core.name_expansion import expand_name_from_initial
from core.social_scraper import scrape_social_profiles, enrich_persona_with_social_data
from core.image_similarity import compare_image_similarity_clip, validate_persona_match
from core.profile_scoring import score_linkedin_candidate, rank_linkedin_candidates
from api.gemini_api import generate_enriched_persona
from api.people_api import enrich_persona_with_pdl

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="LinkedIn Profile Finder",
    page_icon="🔎",
    layout="wide"
)

def load_image_from_url(url):
    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        return img
    except:
        return None

def get_image_base64(image_path):
    if image_path.startswith('http'):
        response = requests.get(image_path)
        img_data = response.content
    else:
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
    return base64.b64encode(img_data).decode()

# Title and description
st.title("🔎 LinkedIn Profile Finder")
st.write("Find LinkedIn profiles based on a persona with advanced AI-powered scoring")

# Sidebar for API keys and configuration
with st.sidebar:
    st.header("API Keys")
    st.markdown("The app requires the following API keys to function:")
    
    if not os.environ.get("SERPAPI_API_KEY"):
        st.warning("⚠️ SERPAPI_API_KEY not set in .env file")
    else:
        st.success("✅ SERPAPI_API_KEY found")
    
    if not os.environ.get("GEMINI_API_KEY"):
        st.warning("⚠️ GEMINI_API_KEY not set in .env file")
    else:
        st.success("✅ GEMINI_API_KEY found")
    
    if not os.environ.get("SCRAPINGDOG_API_KEY"):
        st.warning("⚠️ SCRAPINGDOG_API_KEY not set in .env file")
    else:
        st.success("✅ SCRAPINGDOG_API_KEY found")
    
    if not os.environ.get("TWITTER_BEARER_TOKEN"):
        st.warning("⚠️ TWITTER_BEARER_TOKEN not set in .env file")
    else:
        st.success("✅ TWITTER_BEARER_TOKEN found")
        
    if not os.environ.get("PEOPLE_API_KEY"):
        st.warning("⚠️ PEOPLE_API_KEY not set in .env file")
    else:
        st.success("✅ PEOPLE_API_KEY found")
    
    st.divider()
    st.header("Configuration")
    max_results = st.slider("Max LinkedIn Results", min_value=1, max_value=10, value=5)
    image_threshold = st.slider("Image Similarity Threshold", min_value=0.0, max_value=1.0, value=0.65, step=0.05)

# Main content
tabs = st.tabs(["Input Persona", "Enriched Persona", "LinkedIn Matches"])

# Input Persona Tab
with tabs[0]:
    st.header("Enter Persona Information")
    
    # Option to input multiple personas in JSON format
    st.subheader("Input Multiple Personas (JSON Format)")
    multiple_personas_json = st.text_area(
        "Paste multiple personas in JSON format (as a list of objects):",
        height=200,
    )
    
    if st.button("Add Multiple Personas"):
        try:
            # Parse the JSON input
            multiple_personas = json.loads(multiple_personas_json)
            if isinstance(multiple_personas, list):
                # Store personas in session state
                if "personas" not in st.session_state:
                    st.session_state.personas = []
                st.session_state.personas.extend(multiple_personas)
                st.success(f"Added {len(multiple_personas)} personas successfully!")
            else:
                st.error("Invalid JSON format. Please provide a list of persona objects.")
        except json.JSONDecodeError:
            st.error("Invalid JSON. Please check your input.")
    
    # Display existing personas
    if "personas" in st.session_state and st.session_state.personas:
        st.subheader("Existing Personas")
        for i, persona in enumerate(st.session_state.personas):
            with st.expander(f"Persona #{i+1}"):
                st.json(persona)
                if st.button(f"Select Persona #{i+1} for Enrichment", key=f"select_{i}"):
                    st.session_state.selected_persona = persona
                    st.success(f"Selected Persona #{i+1} for enrichment.")
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        name = st.text_input("Name", "")
        intro = st.text_area("Professional Introduction", "")
        
        col1a, col1b = st.columns(2)
        with col1a:
            industry = st.text_input("Industry", "")
            company_size = st.text_input("Company Size", "")
        
        with col1b:
            location = st.text_input("Location", "")
            timezone = st.text_input("Timezone", "")
        
        social_twitter = st.text_input("Twitter URL", "")
        social_github = st.text_input("GitHub URL", "")
        social_other = st.text_area("Other Social Profiles (one per line)", "")
        
    with col2:
        st.subheader("Profile Image")
        image_url = st.text_input("Image URL", "")
        
        if image_url:
            img = load_image_from_url(image_url)
            if img:
                st.image(img, width=200)
            else:
                st.error("Could not load image from URL")
        
        st.markdown("### Or upload an image")
        uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            image_url = "uploaded_image"
            st.image(Image.open(uploaded_file), width=200)
        
        st.write("**Note:** Image is used for visual similarity matching")
    
    # Collect all inputs into a persona
    if st.button("Create Persona", type="primary"):
        social_profiles = []
        if social_twitter and "twitter.com" in social_twitter:
            social_profiles.append(social_twitter)
        if social_github and "github.com" in social_github:
            social_profiles.append(social_github)
        if social_other:
            for line in social_other.split("\n"):
                if line.strip():
                    social_profiles.append(line.strip())
        
        persona = {
            "name": name,
            "intro": intro,
            "company_industry": industry,
            "company_size": company_size,
            "location": location,
            "timezone": timezone,
            "social_profile": social_profiles
        }
        
        if image_url:
            if image_url == "uploaded_image" and uploaded_file is not None:
                # Save the uploaded image temporarily
                image_data = uploaded_file.getvalue()
                with open("temp_uploaded_image.jpg", "wb") as f:
                    f.write(image_data)
                persona["image"] = "temp_uploaded_image.jpg"
            else:
                persona["image"] = image_url
        
        st.session_state.persona = persona
        st.success("Persona created! Go to the 'Enriched Persona' tab to enrich it.")
        
        # Auto-expand name if it looks like it has an initial
        if " " in name and "." in name:
            expanded_names = expand_name_from_initial(name)
            if expanded_names:
                st.subheader("Name Expansion Suggestions")
                st.write("Your name appears to contain initials. Here are some possible expansions:")
                for i, expanded in enumerate(expanded_names[:5]):
                    st.write(f"{i+1}. {expanded}")

# Enriched Persona Tab
with tabs[1]:
    st.header("Enrich Persona with AI")
    
    if "selected_persona" not in st.session_state:
        st.info("Please select a persona in the 'Input Persona' tab first.")
    else:
        persona = st.session_state.selected_persona
        st.subheader("Selected Persona")
        st.json(persona)
        
        # Create a three-column layout for different enrichment options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Enrich with Social Data"):
                with st.spinner("Scraping social profiles..."):
                    social_urls = persona.get("social_profile", [])
                    if social_urls:
                        social_data = scrape_social_profiles(social_urls)
                        st.session_state.social_data = social_data
                        
                        st.subheader("Social Profiles Data")
                        st.json(social_data)
                        
                        enriched = enrich_persona_with_social_data(persona)
                        st.session_state.enriched_persona = enriched
                        
                        st.subheader("Enriched Persona")
                        st.json(enriched)
                    else:
                        st.warning("No social profiles provided. Add social URLs in the Input tab.")
        
        with col2:
            if st.button("Enrich with People Data Labs"):
                st.warning("People Data Labs API Key is missing. This feature is disabled.")
        
        with col3:
            if "social_data" in st.session_state and st.button("Enrich with Gemini AI"):
                if os.environ.get("GEMINI_API_KEY"):
                    with st.spinner("Generating AI-enhanced persona..."):
                        ai_persona = generate_enriched_persona(st.session_state.social_data)
                        st.session_state.ai_persona = ai_persona
                        
                        st.subheader("AI-Enhanced Persona")
                        st.json(ai_persona)
                else:
                    st.error("GEMINI_API_KEY not set in .env file. Cannot use AI enrichment.")
        
        # Option to use enriched personas for search
        st.divider()
        st.subheader("Select Persona for LinkedIn Search")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("Use Basic Persona"):
                st.session_state.search_persona = persona
                st.success("Basic Persona will be used for LinkedIn search.")
                
        with col2:
            if "enriched_persona" in st.session_state:
                if st.button("Use Social-Enriched"):
                    st.session_state.search_persona = st.session_state.enriched_persona
                    st.success("Social-Enriched Persona will be used for LinkedIn search.")
            else:
                st.button("Use Social-Enriched", disabled=True)
        
        with col3:
            if "pdl_enriched_persona" in st.session_state:
                if st.button("Use PDL-Enriched"):
                    st.session_state.search_persona = st.session_state.pdl_enriched_persona  
                    st.success("PDL-Enriched Persona will be used for LinkedIn search.")
            else:
                st.button("Use PDL-Enriched", disabled=True)
                
        with col4:
            if "ai_persona" in st.session_state:
                if st.button("Use AI-Enriched"):
                    st.session_state.search_persona = st.session_state.ai_persona
                    st.success("AI-Enriched Persona will be used for LinkedIn search.")
            else:
                st.button("Use AI-Enriched", disabled=True)
                
        # Display selected persona
        if "search_persona" in st.session_state:
            st.subheader("Selected Persona for Search")
            st.json(st.session_state.search_persona)
            st.write("👆 This persona will be used for LinkedIn search. Go to the 'LinkedIn Matches' tab to continue.")

# LinkedIn Matches Tab
with tabs[2]:
    st.header("Find LinkedIn Matches")
    
    if "search_persona" not in st.session_state and "persona" in st.session_state:
        st.session_state.search_persona = st.session_state.persona
    
    if "search_persona" not in st.session_state:
        st.info("Please create and select a persona for search first.")
    else:
        search_persona = st.session_state.search_persona
        
        st.subheader("Search Persona")
        st.json(search_persona)
        
        if st.button("Generate Search Queries"):
            with st.spinner("Generating optimized search queries..."):
                queries = generate_search_queries(search_persona)
                st.session_state.search_queries = queries
                
                st.subheader("Top Search Queries")
                for i, query in enumerate(queries[:10]):
                    st.write(f"{i+1}. `{query}`")
        
        if "search_queries" in st.session_state and st.button("Search LinkedIn Profiles"):
            if os.environ.get("SERPAPI_API_KEY"):
                with st.spinner("Searching for LinkedIn profiles..."):
                    try:
                        results = search_linkedin_profiles(search_persona, max_results=max_results)
                        st.session_state.search_results = results
                        
                        st.subheader(f"Found {len(results)} LinkedIn Profiles")
                        for i, result in enumerate(results):
                            with st.expander(f"{i+1}. {result['title']}"):
                                st.write(f"**Link:** {result['link']}")
                                st.write(f"**Snippet:** {result['snippet']}")
                    except Exception as e:
                        st.error(f"Error searching LinkedIn profiles: {e}")
            else:
                st.error("SERPAPI_API_KEY not set in .env file. Cannot search LinkedIn profiles.")

        if "search_results" in st.session_state and st.button("Score and Rank Profiles"):
            with st.spinner("Scoring and ranking LinkedIn profiles..."):
                scored_results = rank_linkedin_candidates(search_persona, st.session_state.search_results)
                st.session_state.scored_results = scored_results

                st.subheader("Ranked LinkedIn Profiles")
                for i, result in enumerate(scored_results):
                    confidence = result["confidence"]
                    with st.expander(f"{i+1}. {result['profile']['title']} (Confidence: {confidence}%)"):
                        st.write(f"**Link:** {result['profile']['link']}")
                        st.write(f"**Snippet:** {result['profile']['snippet']}")

                        st.subheader("Score Breakdown")
                        scores = result["scores"]
                        for score_type, score in scores.items():
                            st.progress(score/100, text=f"{score_type}: {score}%")

        # Image validation
        if "search_results" in st.session_state and "image" in search_persona and st.button("Validate with Image Similarity"):
            if os.environ.get("SCRAPINGDOG_API_KEY"):
                with st.spinner("Validating candidates using image similarity..."):
                    validated_results = validate_persona_match(
                        st.session_state.search_results, 
                        search_persona, 
                        threshold=image_threshold
                    )
                    st.session_state.validated_results = validated_results

                    st.subheader("Image-Validated LinkedIn Profiles")
                    for i, result in enumerate(validated_results):
                        match_icon = "✅" if result.get("image_match", False) else "❌"
                        similarity = result.get("image_similarity", 0)

                        with st.expander(f"{match_icon} {i+1}. {result['title']} (Similarity: {similarity:.2f})"):
                            st.write(f"**Link:** {result['link']}")
                            st.write(f"**Snippet:** {result['snippet']}")

                            # Show images side by side if available
                            if "profile_image" in result and result["profile_image"]:
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.subheader("Persona Image")
                                    if search_persona["image"].startswith(("http", "https")):
                                        st.image(search_persona["image"], width=150)
                                    else:
                                        try:
                                            st.image(Image.open(search_persona["image"]), width=150)
                                        except:
                                            st.write("Could not load persona image")

                                with col2:
                                    st.subheader("LinkedIn Image")
                                    st.image(result["profile_image"], width=150)
            else:
                st.error("SCRAPINGDOG_API_KEY not set in .env file. Cannot validate with image similarity.")

        # Combined results (hybrid scoring)
        if "scored_results" in st.session_state and "validated_results" in st.session_state:
            st.subheader("Final Combined Results")
            st.write("Top profiles based on both text scoring and image similarity")

            for result in st.session_state.scored_results[:3]:  # Show top 3 results
                profile_link = result["profile"]["link"]

                # Find the image similarity score for this profile
                img_similarity = 0.0
                img_match = False
                for v_result in st.session_state.validated_results:
                    if v_result["link"] == profile_link:
                        img_similarity = v_result.get("image_similarity", 0.0)
                        img_match = v_result.get("image_match", False)
                        profile_image = v_result.get("profile_image", None)
                        break

                confidence = result["confidence"]
                match_icon = "✅" if img_match else "❌"

                with st.expander(f"{match_icon} {result['profile']['title']}"):
                    st.write(f"**Confidence:** {confidence}% | **Image similarity:** {img_similarity:.2f}")
                    st.write(f"**Link:** {profile_link}")
                    st.write(f"**Snippet:** {result['profile']['snippet']}")

                    # Show scores
                    st.subheader("Score Breakdown")
                    scores = result["scores"]
                    for score_type, score in scores.items():
                        st.progress(score/100, text=f"{score_type}: {score}%")

# Footer
st.divider()
st.markdown("LinkedIn Profile Finder | Developed with ❤️ using Streamlit and Gemini AI")