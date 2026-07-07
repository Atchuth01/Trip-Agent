

import os
import time
import hashlib
import requests
from datetime import datetime

AMADEUS_CLIENT_ID = os.environ.get("AMADEUS_CLIENT_ID", "")
AMADEUS_CLIENT_SECRET = os.environ.get("AMADEUS_CLIENT_SECRET", "")
AMADEUS_BASE_URL = "https://test.api.amadeus.com"

_token_cache = {"token": None, "expires_at": 0}



def _get_amadeus_token():
    
    if not AMADEUS_CLIENT_ID or not AMADEUS_CLIENT_SECRET:
        raise RuntimeError("Amadeus credentials not configured")

    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 30:
        return _token_cache["token"]

    resp = requests.post(
        f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": AMADEUS_CLIENT_ID,
            "client_secret": AMADEUS_CLIENT_SECRET,
        },
        timeout=8,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 1800)
    return _token_cache["token"]



def _seeded_number(seed_str, low, high):

    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return low + (h % (high - low))


_AIRLINES = ["IndiGo", "Air India", "SpiceJet", "Vistara", "Akasa Air"]
_HOTEL_NAMES = [
    "Sea Breeze Residency", "The Grand Palm", "Coastal Comfort Inn",
    "Sunset Bay Hotel", "Urban Nest Suites", "Lakeview Regency",
]


def _mock_flights(origin, destination, departure_date, adults):
    flights = []
    for i in range(3):
        seed = f"{origin}-{destination}-{departure_date}-{i}"
        price = _seeded_number(seed, 2800, 7200) * adults
        duration_min = _seeded_number(seed + "d", 75, 220)
        flights.append({
            "airline": _AIRLINES[_seeded_number(seed + "a", 0, len(_AIRLINES))],
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "price_inr": price,
            "duration_minutes": duration_min,
            "stops": 0 if i == 0 else 1,
            "source": "mock_fallback",
        })
    return sorted(flights, key=lambda f: f["price_inr"])


def _mock_hotels(city_code, check_in, check_out, adults):
    nights = max(1, (_parse_date(check_out) - _parse_date(check_in)).days)
    hotels = []
    for i in range(3):
        seed = f"{city_code}-{check_in}-{i}"
        price_per_night = _seeded_number(seed, 1200, 5500)
        rating = round(3.4 + _seeded_number(seed + "r", 0, 16) / 10, 1)
        hotels.append({
            "name": _HOTEL_NAMES[_seeded_number(seed + "n", 0, len(_HOTEL_NAMES))],
            "city_code": city_code,
            "price_per_night_inr": price_per_night,
            "nights": nights,
            "total_price_inr": price_per_night * nights,
            "rating": min(rating, 5.0),
            "source": "mock_fallback",
        })
    return sorted(hotels, key=lambda h: h["total_price_inr"])


def _parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d")



def search_flights(origin: str, destination: str, departure_date: str, adults: int = 1):
   
    try:
        token = _get_amadeus_token()
        resp = requests.get(
            f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "adults": adults,
                "max": 3,
                "currencyCode": "INR",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            raise ValueError("No live results returned")

        results = []
        for offer in data[:3]:
            itinerary = offer["itineraries"][0]
            segments = itinerary["segments"]
            duration_iso = itinerary["duration"]  # e.g. "PT2H10M"
            results.append({
                "airline": segments[0]["carrierCode"],
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "price_inr": float(offer["price"]["total"]),
                "duration_iso": duration_iso,
                "stops": len(segments) - 1,
                "source": "amadeus_live",
            })
        return {"status": "ok", "flights": results}

    except Exception as e:
        return {
            "status": "fallback",
            "reason": str(e),
            "flights": _mock_flights(origin, destination, departure_date, adults),
        }


def search_hotels(city_code: str, check_in: str, check_out: str, adults: int = 1):
 
    try:
        token = _get_amadeus_token()
        # Step 1: get hotel IDs in the city
        list_resp = requests.get(
            f"{AMADEUS_BASE_URL}/v1/reference-data/locations/hotels/by-city",
            headers={"Authorization": f"Bearer {token}"},
            params={"cityCode": city_code},
            timeout=8,
        )
        list_resp.raise_for_status()
        hotel_ids = [h["hotelId"] for h in list_resp.json().get("data", [])[:5]]
        if not hotel_ids:
            raise ValueError("No hotels found for city code")

        offers_resp = requests.get(
            f"{AMADEUS_BASE_URL}/v3/shopping/hotel-offers",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "hotelIds": ",".join(hotel_ids),
                "checkInDate": check_in,
                "checkOutDate": check_out,
                "adults": adults,
            },
            timeout=8,
        )
        offers_resp.raise_for_status()
        data = offers_resp.json().get("data", [])
        if not data:
            raise ValueError("No live hotel offers returned")

        nights = max(1, (_parse_date(check_out) - _parse_date(check_in)).days)
        results = []
        for item in data[:3]:
            hotel = item["hotel"]
            offer = item["offers"][0]
            total = float(offer["price"]["total"])
            results.append({
                "name": hotel.get("name", "Unknown Hotel"),
                "city_code": city_code,
                "total_price_inr": total,
                "price_per_night_inr": round(total / nights, 2),
                "nights": nights,
                "source": "amadeus_live",
            })
        return {"status": "ok", "hotels": results}

    except Exception as e:
        return {
            "status": "fallback",
            "reason": str(e),
            "hotels": _mock_hotels(city_code, check_in, check_out, adults),
        }


def calculate_trip_budget(flight_price_inr: float, hotel_price_per_night_inr: float,
                           nights: int, travelers: int = 1, budget_inr: float = None,
                           daily_misc_inr: float = 800):

    flight_total = flight_price_inr * travelers
    hotel_total = hotel_price_per_night_inr * nights
    misc_total = daily_misc_inr * nights * travelers
    grand_total = flight_total + hotel_total + misc_total

    result = {
        "flight_total_inr": round(flight_total, 2),
        "hotel_total_inr": round(hotel_total, 2),
        "misc_total_inr": round(misc_total, 2),
        "grand_total_inr": round(grand_total, 2),
        "travelers": travelers,
        "nights": nights,
    }

    if budget_inr is not None:
        result["budget_inr"] = budget_inr
        result["within_budget"] = grand_total <= budget_inr
        result["difference_inr"] = round(budget_inr - grand_total, 2)

    return result
