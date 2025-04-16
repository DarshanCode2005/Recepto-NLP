# LinkedIn Profile Finder

An AI-powered tool to find and validate LinkedIn profiles based on a persona with hybrid scoring approach.

## 🌟 Features

- Generate a persona from social media profiles (GitHub, Twitter)
- Enrich persona data with People Data Labs API for comprehensive professional details
- Further enhance persona with AI using Google's Gemini model
- Generate optimized LinkedIn search queries based on persona details
- Find and score potential LinkedIn profile matches
- Validate matches with image similarity using CLIP
- Complete profile scoring with weighted matching (name, semantic, location, etc.)
- Streamlit UI for easy interaction

## 🛠️ How It Works

1. **Persona Creation**: Start with basic information about the person you're looking for (name, social media profiles, professional details)
2. **Profile Enrichment**: Scrape social profiles to gather more details about the person
3. **Professional Data Enrichment**: Use People Data Labs API to fill in professional details, skills, and background
4. **AI Enhancement**: Use Gemini AI to infer additional professional details, skills, and other attributes
5. **Search Query Generation**: Create optimized search queries for LinkedIn
6. **LinkedIn Search**: Find potential matching profiles using SerpAPI
7. **Profile Scoring**: Score each candidate with a hybrid approach:
   - Name similarity using fuzzy matching
   - Semantic similarity of professional descriptions using BERT
   - Industry and location matching
   - Social profile validation
   - Image similarity using CLIP (optional)
8. **Final Ranking**: Combine all scores for a final confidence score

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Required API keys:
  - SERPAPI_API_KEY: For LinkedIn searches
  - PEOPLE_API_KEY: For professional data enrichment (People Data Labs)
  - GEMINI_API_KEY: For AI enrichment (Google Gemini)
  - SCRAPINGDOG_API_KEY: For LinkedIn profile image extraction (optional)
  - TWITTER_BEARER_TOKEN: For Twitter profile scraping (optional)

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/linkedin-profile-finder.git
cd linkedin-profile-finder
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your API keys
```
SERPAPI_API_KEY=your_serpapi_api_key_here
PEOPLE_API_KEY=your_people_data_labs_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
SCRAPINGDOG_API_KEY=your_scrapingdog_api_key_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
```

### Running the App

Launch the Streamlit UI:
```bash
streamlit run app.py
```

Or run the command-line demo:
```bash
python main.py
```

## 📊 Scoring System

The profile scoring system uses a hybrid approach that considers:

| Score Type | Weight | Description |
|------------|--------|-------------|
| Name Score | 35% | Fuzzy matching of names, accounting for variations |
| Semantic Score | 25% | BERT-based similarity of professional introductions |
| Industry Score | 10% | Matching of industry and professional domain |
| Location Score | 15% | Geographic proximity and timezone alignment |
| Social Score | 10% | Validation through social media profiles |
| Image Score | 5% | Visual similarity of profile photos (using CLIP) |

## 💡 Use Cases

- Recruiting: Find potential candidates matching a specific profile
- Business Development: Locate decision-makers at target companies
- Research: Find professionals in specific domains
- Networking: Locate colleagues or contacts with limited information

## 📋 Core Modules

- `main.py`: Entry-point for command-line usage
- `app.py`: Streamlit web app
- `core/profile_scraper.py`: Social media profile scraping
- `api/people_api.py`: Professional data enrichment with People Data Labs
- `api/gemini_api.py`: AI enrichment with Gemini
- `core/image_similarity.py`: Handles lightweight perceptual hash-based image comparison
- `core/name_utils.py`: Name parsing and expansion
- `core/search.py`: LinkedIn search query generation
- `core/profile_scoring.py`: Candidate matching and scoring functions

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Always respect LinkedIn's terms of service and privacy policies when using this tool. The creators are not responsible for any misuse of this tool. 