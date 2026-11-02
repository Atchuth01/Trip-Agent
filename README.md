# TripAgent — Autonomous Travel Planning Agent

TripAgent accepts a natural-language travel request, calls flight and hotel search tools, calculates an estimated budget, and returns a structured itinerary.

## Architecture

```text
User request
    |
    v
Llama 3.3 70B through Groq API
    |
    +--> search_flights (Amadeus API or clearly labelled mock fallback)
    +--> search_hotels (Amadeus API or clearly labelled mock fallback)
    +--> calculate_trip_budget
    |
    v
Structured itinerary
```

The model provider is **Groq** (OpenAI-compatible API), not Claude. Flight and hotel results may be live Amadeus test-environment data or deterministic mock data. Mock results are not real availability or quotes.

## Requirements

- Python 3.10+
- Groq API key (required for the language model)
- Amadeus API credentials (optional; without them, flight/hotel tools use mock fallback data)

## Setup (Windows PowerShell)

1. Clone the repository and open its folder:

   ```powershell
   git clone https://github.com/Atchuth01/Trip-Agent.git
   cd Trip-Agent
   ```

2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies and create your private environment file:

   ```powershell
   pip install -r requirements.txt
   Copy-Item .env.example .env
   notepad .env
   ```

4. Add your own credentials to the local `.env` file:

   ```dotenv
   GROQ_API_KEY=your_new_groq_api_key
   AMADEUS_CLIENT_ID=your_amadeus_client_id
   AMADEUS_CLIENT_SECRET=your_amadeus_client_secret
   ```

   The Groq key is required. Amadeus credentials are optional. Never commit `.env`, paste credentials into source code, or share them in screenshots/issues. The repository's `.gitignore` excludes `.env`.

## Run

Terminal agent:

```powershell
python agent.py
```

Streamlit interface:

```powershell
streamlit run streamlit_app.py
```

## Data-source transparency

- `amadeus_live`: response from the Amadeus test API.
- `mock_fallback`: deterministic demo data generated locally; not a live fare, hotel offer, or booking confirmation.

Always check the returned source before treating prices as real-world quotes.

## Security

- Keep API keys in local environment variables or a secrets manager.
- Do not commit `.env`, credentials, tokens, or private configuration.
- If a key is ever exposed, revoke it immediately and issue a replacement.
- Removing a secret from the latest commit does not remove it from earlier Git history. Follow the GitHub sensitive-data removal guidance if credentials were committed.
