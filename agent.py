import os
import json
import re
from datetime import datetime
from openai import OpenAI, BadRequestError
import tools

MODEL = "llama-3.3-70b-versatile"

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)


def build_system_prompt():
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d (%A)")

    return f"""You are TripAgent, an autonomous travel planning assistant.

Today's real date is: {today_str}

IMPORTANT: Always resolve relative dates (e.g. "in August", "next month",
"this weekend") against TODAY'S REAL DATE above -- not against any date you
might otherwise assume. If the user doesn't give an exact date, pick the
nearest upcoming occurrence of that month/period relative to today.

Given a natural language travel request, you must:
1. Extract origin, destination, travel dates, number of travelers, and budget
   (if not given, make a reasonable assumption and state it clearly).
2. Convert city names to IATA codes yourself (e.g. Hyderabad -> HYD, Goa -> GOI,
   Delhi -> DEL, Mumbai -> BOM, Bangalore -> BLR, Chennai -> MAA, Kolkata -> CCU).
3. Call search_flights to find flight options.
4. Call search_hotels to find hotel options for the stay duration.
5. Call calculate_trip_budget using the CHEAPEST reasonable flight and hotel
   combination to check whether the trip fits the user's budget.
6. Produce a final, clearly structured itinerary as your answer:
   - Trip summary (route, dates, travelers)
   - Recommended flight (with price)
   - Recommended hotel (with price/night and total)
   - Day-by-day plan (brief, 1-2 activities per day is fine)
   - Budget breakdown and a clear verdict: within budget or over, by how much
   - If data came from a fallback/mock source, do not hide it -- just present
     it naturally as pricing information, no need to caveat every line.

Always call tools before answering -- never guess prices yourself. Be decisive:
pick ONE recommended flight and ONE recommended hotel rather than dumping all
options on the user, but you may briefly mention alternatives.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search for flight options between two cities on a given date. Returns a list of flights with airline, price in INR, duration, and stops.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "IATA code of origin city, e.g. HYD"},
                    "destination": {"type": "string", "description": "IATA code of destination city, e.g. GOI"},
                    "departure_date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                    "adults": {"type": "integer", "description": "Number of travelers", "default": 1},
                },
                "required": ["origin", "destination", "departure_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Search for hotel options in a city for a given date range. Returns hotel name, price per night, total price, and rating.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city_code": {"type": "string", "description": "IATA city code, e.g. GOI"},
                    "check_in": {"type": "string", "description": "Check-in date YYYY-MM-DD"},
                    "check_out": {"type": "string", "description": "Check-out date YYYY-MM-DD"},
                    "adults": {"type": "integer", "description": "Number of guests", "default": 1},
                },
                "required": ["city_code", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_trip_budget",
            "description": "Calculate total trip cost (flights + hotel + daily misc expenses) and compare against a budget if provided. This does real arithmetic -- always use this instead of estimating totals yourself.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_price_inr": {"type": "number", "description": "Price of ONE flight ticket in INR"},
                    "hotel_price_per_night_inr": {"type": "number", "description": "Hotel price per night in INR"},
                    "nights": {"type": "integer", "description": "Number of nights of stay"},
                    "travelers": {"type": "integer", "description": "Number of travelers", "default": 1},
                    "budget_inr": {"type": "number", "description": "User's stated total budget in INR, if any"},
                    "daily_misc_inr": {"type": "number", "description": "Estimated daily misc spend per traveler (food, local transport)", "default": 800},
                },
                "required": ["flight_price_inr", "hotel_price_per_night_inr", "nights"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "search_flights": tools.search_flights,
    "search_hotels": tools.search_hotels,
    "calculate_trip_budget": tools.calculate_trip_budget,
}


def execute_tool(name, tool_input):
    fn = TOOL_FUNCTIONS[name]
    return fn(**tool_input)


def _param_schema(tool_name):
    for t in TOOLS:
        if t["function"]["name"] == tool_name:
            return t["function"]["parameters"].get("properties", {})
    return {}


def _coerce_args(tool_name, args):
    schema = _param_schema(tool_name)
    fixed = {}
    for key, value in args.items():
        expected = schema.get(key, {}).get("type")
        if isinstance(value, str):
            if expected == "integer":
                try:
                    value = int(float(value))
                except ValueError:
                    pass
            elif expected == "number":
                try:
                    value = float(value)
                except ValueError:
                    pass
        fixed[key] = value
    return fixed


def _extract_failed_tool_call(error):
    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        try:
            body = json.loads(str(error.response.text))
        except Exception:
            body = {}


    if isinstance(body, dict) and "failed_generation" in body:
        err_obj = body
    elif isinstance(body, dict) and isinstance(body.get("error"), dict):
        err_obj = body["error"]
    else:
        err_obj = {}

    failed_generation = err_obj.get("failed_generation", "")
    if not failed_generation:
        return None, None


    name_match = re.search(r"<function=([\w_]+)", failed_generation)
    if not name_match:
        return None, None
    tool_name = name_match.group(1)

    json_match = re.search(r"\{.*\}(?=\s*</function>)", failed_generation, re.DOTALL)
    if not json_match:
        return None, None
    try:
        raw_args = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return None, None
    return tool_name, raw_args


def run_agent(user_query: str, verbose: bool = True, max_turns: int = 6):
   
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": user_query},
    ]

    for turn in range(max_turns):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=2000,
                tools=TOOLS,
                messages=messages,
            )
        except BadRequestError as e:
            tool_name, raw_args = _extract_failed_tool_call(e)
            if tool_name is None:
             
                return (f"⚠️ The model returned an unrecoverable error: {e}. "
                        f"Try rephrasing your request or running again.")

            fixed_args = _coerce_args(tool_name, raw_args)
            if verbose:
                print(f"⚠️  Model sent wrong argument types for {tool_name} "
                      f"({json.dumps(raw_args)}) -- auto-corrected to "
                      f"{json.dumps(fixed_args)} and continuing.")
            try:
                result = execute_tool(tool_name, fixed_args)
            except Exception as ex:
                result = {"error": str(ex)}
            if verbose:
                preview = json.dumps(result)[:300]
                print(f"   ↳ Result: {preview}{'...' if len(json.dumps(result)) > 300 else ''}")

            fake_call_id = f"call_autofix_{turn}"
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": fake_call_id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": json.dumps(fixed_args)},
                }],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": fake_call_id,
                "content": json.dumps(result),
            })
            continue  # ask the model to proceed now that it has this result

        msg = response.choices[0].message

        # Print any reasoning text the model produced before/alongside tool calls
        if verbose and msg.content and msg.content.strip():
            print(f"\n💭 Agent: {msg.content.strip()}\n")

        if not msg.tool_calls:
            # Final answer reached
            return msg.content or ""

        # Otherwise, the model wants to call one or more tools
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            if verbose:
                print(f"🔧 Calling tool: {name}({json.dumps(args)})")
            try:
                result = execute_tool(name, args)
            except Exception as e:
                result = {"error": str(e)}
            if verbose:
                preview = json.dumps(result)[:300]
                print(f"   ↳ Result: {preview}{'...' if len(json.dumps(result)) > 300 else ''}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    return "Agent reached max turns without a final answer."


if __name__ == "__main__":
    print("=" * 60)
    print(" TripAgent -- Autonomous Travel Planning Agent")
    print("=" * 60)
    query = input("\nEnter your travel request:\n> ")
    print("\n--- Agent reasoning trace ---")
    final = run_agent(query)
    print("\n--- Final Itinerary ---\n")
    print(final)
