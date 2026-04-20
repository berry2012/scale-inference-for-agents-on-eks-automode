from fastapi import FastAPI
from pydantic import BaseModel
from strands import tool, Agent
from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
import requests
import os

# Use AWS Bedrock for the Weather Agent
# Bedrock is the default model provider in Strands, so we just specify the model ID
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "us.anthropic.claude-sonnet-4-20250514-v1:0")

app = FastAPI(title="Time and Weather Agent")

geolocator = Nominatim(user_agent="time-weather-agent", timeout=10)
tf = TimezoneFinder()

@tool
def current_time(location: str) -> str:
    """Get the current time for a location.
    
    Args:
        location: The city or location name to get the time for
    """
    try:
        location_data = geolocator.geocode(location)
        if location_data:
            timezone = tf.timezone_at(lng=location_data.longitude, lat=location_data.latitude) or "UTC"
            dt = datetime.now(pytz.timezone(timezone))
            return dt.strftime("%Y-%m-%d %I:%M %p %Z")
    except Exception as e:
        print(f"Time error: {e}")
    return datetime.now().strftime("%Y-%m-%d %I:%M %p")

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle",
    53: "Moderate drizzle", 55: "Dense drizzle", 61: "Light rain",
    63: "Moderate rain", 65: "Heavy rain", 71: "Light snow",
    73: "Moderate snow", 75: "Heavy snow", 95: "Thunderstorm"
}

def _geocode(location: str):
    loc = geolocator.geocode(location)
    if not loc:
        return None, None
    return loc.latitude, loc.longitude

@tool
def current_weather(location: str) -> str:
    """Get the current weather for a location.
    
    Args:
        location: The city or location name to get the weather for
    """
    try:
        lat, lon = _geocode(location)
        if lat is None:
            return "Location not found"

        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto"
        resp = requests.get(url)
        if resp.status_code == 200:
            cur = resp.json().get("current", {})
            desc = WEATHER_CODES.get(cur.get("weather_code"), "Unknown")
            return f"{desc}, {cur.get('temperature_2m', 'N/A')}°C"
        return "Weather data currently unavailable"
    except Exception as e:
        print(f"Weather error: {e}")
        return "Weather service is currently unavailable"

@tool
def weather_forecast(location: str, days: int = 7) -> str:
    """Get a multi-day weather forecast for a location.
    
    Args:
        location: The city or location name to get the forecast for
        days: Number of forecast days (1-16, default 7)
    """
    try:
        lat, lon = _geocode(location)
        if lat is None:
            return "Location not found"

        days = max(1, min(days, 16))
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,weather_code"
            f"&forecast_days={days}&timezone=auto"
        )
        resp = requests.get(url)
        if resp.status_code == 200:
            daily = resp.json().get("daily", {})
            dates = daily.get("time", [])
            highs = daily.get("temperature_2m_max", [])
            lows = daily.get("temperature_2m_min", [])
            codes = daily.get("weather_code", [])

            lines = []
            for i, date in enumerate(dates):
                desc = WEATHER_CODES.get(codes[i], "Unknown")
                lines.append(f"{date}: {desc}, High {highs[i]}°C / Low {lows[i]}°C")
            return "\n".join(lines)
        return "Forecast data currently unavailable"
    except Exception as e:
        print(f"Forecast error: {e}")
        return "Forecast service is currently unavailable"

class QueryRequest(BaseModel):
    query: str

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/agent")
async def agent_endpoint(request: QueryRequest):
    """Endpoint that uses time and weather agent with AWS Bedrock"""
    agent = Agent(
        model=BEDROCK_MODEL,
        name="WeatherAgent",
        description="AI agent for time and weather information",
        tools=[current_time, current_weather, weather_forecast],
        system_prompt="""You are WeatherAgent, an AI assistant that provides time and weather information.

You have access to three tools:
1. current_time: Get the current time for any location
2. current_weather: Get the current weather for any location
3. weather_forecast: Get a multi-day weather forecast (up to 16 days) for any location

Use current_weather for "what's the weather now" questions.
Use weather_forecast for questions about future weather, tomorrow, this week, etc.
Always provide accurate, helpful information about time and weather when asked."""
    )
    response = agent(request.query)
    
    return {
        "status": "success",
        "response": str(response)
    }