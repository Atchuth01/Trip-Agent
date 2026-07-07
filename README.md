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
export $(cat .env | xargs)   # or use python-dotenv / your shell's method
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

## 1-week build plan (if you're building this from scratch)

- **Day 1:** Get a free Groq API key + Amadeus free test keys. Read Groq's
  tool-use docs (OpenAI-compatible format). Get a bare "hello world" tool call
  working (one fake tool).
- **Day 2:** Build `tools.py` — mock data first (get this rock solid), then
  wire in real Amadeus calls with fallback.
- **Day 3:** Build `agent.py` — the tool-use loop, system prompt, tool
  schemas. Test with 5-10 different queries, fix edge cases (missing dates,
  vague budgets, unknown cities).
- **Day 4:** Polish the terminal output / build the Streamlit version.
  Handle errors gracefully (never let it crash on stage).
- **Day 5:** Dry-run the demo 5+ times. Time it. Trim the query examples
  down to ones that produce clean, fast, impressive output.
- **Day 6:** Record the actual demo (see script below). Do 3-4 takes.
- **Day 7:** Buffer day — fix anything, write your application, submit early.

## 90–120 second demo script

**Don't use slides. Screen-record your terminal or Streamlit app live.**

| Time | What's on screen | What you say |
|---|---|---|
| 0:00–0:12 | Terminal/UI, empty, about to type | "This is TripAgent — an agent that plans a trip end-to-end by autonomously calling real tools. No hardcoded logic deciding what happens next, Claude decides." |
| 0:12–0:20 | Type the query and hit enter | "I'll ask it to plan a 3-day trip from Hyderabad to Goa under ₹20,000." |
| 0:20–0:55 | Reasoning trace scrolling: tool calls appearing live | "Watch — it's calling search_flights on its own, then search_hotels, then it runs a real budget calculation to check if this fits ₹20,000 — I'm not scripting this order, the model is deciding it." |
| 0:55–1:35 | Final itinerary rendering | "And here's the output: flight, hotel, day-by-day plan, and a clear budget verdict — over or under, by how much. This hit a live flight/hotel API [or: falls back gracefully to consistent pricing if the API's unavailable, so it never breaks live]. The whole agent runs on a free, open-source model served by Groq — zero API cost." |
| 1:35–1:50 | Quick cut to code (agent.py tool loop or tools.py) | "Under the hood it's an open-source model's tool-calling API, served free via Groq, orchestrating three tools I built in Python, with a real Amadeus integration for live data." |
| 1:50–2:00 | Back to final output | "That's the full loop — input to autonomous tool use to structured output, in under 30 seconds." |

**Tips:**
- Pick a query in advance that you know produces a clean result (test it 3x
  beforehand) — don't improvise the query live.
- Keep your voiceover confident and technical — say "tool calling",
  "autonomous", "orchestration" naturally, don't over-explain basics.
- If you show code, show it for 5-8 seconds max, don't read it line by line.
- Record in a quiet room, 1080p, and do a final playback check before
  submitting.

## Why this satisfies the brief

- ✅ Takes natural language input
- ✅ Calls tools autonomously (Claude decides which/when, not a hardcoded script)
- ✅ Real output: structured itinerary with real numbers
- ✅ Not a classifier / not a static Streamlit ML app — it acts (searches,
  calculates, decides) rather than just predicting a label
- ✅ Built entirely in Python, free APIs, in well under a week
