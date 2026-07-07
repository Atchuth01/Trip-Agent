# TripAgent — Autonomous Travel Planning Agent

Built for the Tabhi / Mondee Agentic AI Intern application.

An agent that takes a natural-language travel request, autonomously decides
which tools to call (flight search → hotel search → budget calculator), and
returns a structured itinerary — not a classifier, not a static form, an
actual multi-step tool-using agent.

## How it works

```
User query
   │
   ▼
Llama 3.3 70B (via Groq's free API) reasons about what's needed
   │
   ├─► search_flights(origin, destination, date)      [tool call 1]
   ├─► search_hotels(city, check_in, check_out)        [tool call 2]
   ├─► calculate_trip_budget(flight, hotel, nights...)  [tool call 3]
   │
   ▼
Claude synthesizes all tool results into a final itinerary
```

The model decides autonomously *which* tools to call, *in what order*, and
*with what arguments* — this repo just provides the tools and the loop that
feeds results back to the model. That autonomy is what makes it "agentic"
rather than a scripted pipeline.

Flight/hotel search hits the **real Amadeus Self-Service API** (free test
tier) when credentials are configured, and transparently falls back to
deterministic mock pricing if the API is unavailable — so a demo recording
never fails mid-take due to a flaky third-party API or rate limit.

## Setup

```bash
cd travel_agent
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}   # or use python-dotenv / your shell's method
```

**Required:** `GROQ_API_KEY` — completely free, no credit card. Get one at
https://console.groq.com → API Keys → Create Key. Takes under 2 minutes.

**Optional (recommended for extra credibility):** `AMADEUS_CLIENT_ID` /
`AMADEUS_CLIENT_SECRET` — free, no credit card, from
https://developers.amadeus.com → "Self-Service" → Create App. Takes 5 minutes.
If you skip this, the agent still works perfectly using mock data.

## Run it

Terminal (best for a clean recording — shows the reasoning trace live):
```bash
python agent.py
```

Streamlit UI (nicer visuals if you'd rather show a UI):
```bash
streamlit run streamlit_app.py
```

Try queries like:
- "Plan a 3-day trip from Hyderabad to Goa in August under ₹20,000"
- "I want to go from Delhi to Mumbai for 2 nights next month, budget 15000, just me"
- "Weekend trip Bangalore to Chennai for 2 people, keep it under 10k"


- ✅ Takes natural language input
- ✅ Calls tools autonomously (Claude decides which/when, not a hardcoded script)
- ✅ Real output: structured itinerary with real numbers
- ✅ Not a classifier / not a static Streamlit ML app — it acts (searches,
  calculates, decides) rather than just predicting a label
- ✅ Built entirely in Python, free APIs, in well under a week
