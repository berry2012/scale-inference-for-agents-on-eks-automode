#!/usr/bin/env python3
"""Weather MCP Server for weather and geolocation services.

This server provides a REST API for weather information and geolocation
using Open-Meteo API and Nominatim geocoding service.
"""

import os
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
import requests
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "component": "%(name)s", "message": "%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S%z"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Weather MCP Server",
    description="MCP server for weather and geolocation services",
    version="1.0.0"
)

# Configuration
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "SummitAssistant-weather-mcp")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))

# Initialize services
geolocator = Nominatim(user_agent=NOMINATIM_USER_AGENT, timeout=REQUEST_TIMEOUT)
tf = TimezoneFinder()

# Weather code mappings
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    95: "Thunderstorm"
}


class WeatherRequest(BaseModel):
    """Weather information request."""
    location: str = Field(..., description="City or location name")


class WeatherResponse(BaseModel):
    """Weather information response."""
    status: str = Field(..., description="Response status (success or error)")
    location: str = Field(..., description="Location name")
    temperature: Optional[float] = Field(None, description="Temperature in Celsius")
    weather_description: Optional[str] = Field(None, description="Weather description")
    weather_code: Optional[int] = Field(None, description="Weather code")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    error: Optional[str] = Field(None, description="Error message if status=error")


class TimeRequest(BaseModel):
    """Time information request."""
    location: str = Field(..., description="City or location name")


class TimeResponse(BaseModel):
    """Time information response."""
    status: str = Field(..., description="Response status (success or error)")
    location: str = Field(..., description="Location name")
    current_time: Optional[str] = Field(None, description="Current time in location")
    timezone: Optional[str] = Field(None, description="Timezone name")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    error: Optional[str] = Field(None, description="Error message if status=error")


class GeocodeRequest(BaseModel):
    """Geocoding request."""
    location: str = Field(..., description="City or location name to geocode")


class GeocodeResponse(BaseModel):
    """Geocoding response."""
    status: str = Field(..., description="Response status (success or error)")
    location: str = Field(..., description="Location name")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    display_name: Optional[str] = Field(None, description="Full location name")
    error: Optional[str] = Field(None, description="Error message if status=error")


def geocode_location(location: str) -> Optional[dict]:
    """Geocode a location string to coordinates.
    
    Args:
        location: Location name to geocode
        
    Returns:
        Dictionary with latitude, longitude, and display_name, or None if not found
    """
    try:
        location_data = geolocator.geocode(location)
        if location_data:
            return {
                "latitude": location_data.latitude,
                "longitude": location_data.longitude,
                "display_name": location_data.address
            }
        return None
    except Exception as e:
        logger.error(f"Geocoding error for {location}: {e}")
        return None


@app.get("/health")
def health_check():
    """Health check endpoint with external API connectivity checks."""
    health = {
        "status": "healthy",
        "service": "weather-mcp-server",
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check Open-Meteo API
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current=temperature_2m",
            timeout=5
        )
        health["checks"]["open_meteo"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        logger.warning(f"Open-Meteo health check failed: {e}")
        health["checks"]["open_meteo"] = "unhealthy"
        health["status"] = "degraded"
    
    # Check Nominatim geocoding
    try:
        test_location = geolocator.geocode("London", timeout=5)
        health["checks"]["nominatim"] = "healthy" if test_location else "unhealthy"
    except Exception as e:
        logger.warning(f"Nominatim health check failed: {e}")
        health["checks"]["nominatim"] = "unhealthy"
        health["status"] = "degraded"
    
    return health


@app.post("/weather", response_model=WeatherResponse)
async def get_weather(request: WeatherRequest):
    """Get current weather for a location.
    
    Args:
        request: Weather request with location
        
    Returns:
        Weather information including temperature and description
    """
    logger.info(f"Weather request for location: {request.location}")
    
    # Geocode location
    location_data = geocode_location(request.location)
    if not location_data:
        logger.warning(f"Location not found: {request.location}")
        return WeatherResponse(
            status="error",
            location=request.location,
            error="Location not found"
        )
    
    lat = location_data["latitude"]
    lon = location_data["longitude"]
    
    # Get weather data from Open-Meteo
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code != 200:
            logger.error(f"Open-Meteo API error: {response.status_code}")
            return WeatherResponse(
                status="error",
                location=request.location,
                latitude=lat,
                longitude=lon,
                error="Weather data currently unavailable"
            )
        
        data = response.json()
        current = data.get("current", {})
        temperature = current.get("temperature_2m")
        weather_code = current.get("weather_code")
        weather_description = WEATHER_CODES.get(weather_code, f"Unknown (code {weather_code})")
        
        logger.info(f"Weather retrieved for {request.location}: {temperature}°C, {weather_description}")
        
        return WeatherResponse(
            status="success",
            location=request.location,
            temperature=temperature,
            weather_description=weather_description,
            weather_code=weather_code,
            latitude=lat,
            longitude=lon
        )
        
    except requests.Timeout:
        logger.error(f"Timeout getting weather for {request.location}")
        return WeatherResponse(
            status="error",
            location=request.location,
            latitude=lat,
            longitude=lon,
            error="Weather service timeout"
        )
    except Exception as e:
        logger.error(f"Error getting weather for {request.location}: {e}")
        return WeatherResponse(
            status="error",
            location=request.location,
            latitude=lat,
            longitude=lon,
            error=f"Weather service error: {str(e)}"
        )


@app.post("/time", response_model=TimeResponse)
async def get_time(request: TimeRequest):
    """Get current time for a location.
    
    Args:
        request: Time request with location
        
    Returns:
        Current time in the location's timezone
    """
    logger.info(f"Time request for location: {request.location}")
    
    # Geocode location
    location_data = geocode_location(request.location)
    if not location_data:
        logger.warning(f"Location not found: {request.location}")
        return TimeResponse(
            status="error",
            location=request.location,
            error="Location not found"
        )
    
    lat = location_data["latitude"]
    lon = location_data["longitude"]
    
    # Get timezone
    try:
        timezone_str = tf.timezone_at(lng=lon, lat=lat)
        if not timezone_str:
            timezone_str = "UTC"
            logger.warning(f"Timezone not found for {request.location}, using UTC")
        
        # Get current time in timezone
        tz = pytz.timezone(timezone_str)
        current_time = datetime.now(tz)
        time_formatted = current_time.strftime("%Y-%m-%d %I:%M %p %Z")
        
        logger.info(f"Time retrieved for {request.location}: {time_formatted}")
        
        return TimeResponse(
            status="success",
            location=request.location,
            current_time=time_formatted,
            timezone=timezone_str,
            latitude=lat,
            longitude=lon
        )
        
    except Exception as e:
        logger.error(f"Error getting time for {request.location}: {e}")
        return TimeResponse(
            status="error",
            location=request.location,
            latitude=lat,
            longitude=lon,
            error=f"Time service error: {str(e)}"
        )


@app.post("/geocode", response_model=GeocodeResponse)
async def geocode(request: GeocodeRequest):
    """Geocode a location to coordinates.
    
    Args:
        request: Geocode request with location
        
    Returns:
        Coordinates and full location name
    """
    logger.info(f"Geocode request for location: {request.location}")
    
    location_data = geocode_location(request.location)
    if not location_data:
        logger.warning(f"Location not found: {request.location}")
        return GeocodeResponse(
            status="error",
            location=request.location,
            error="Location not found"
        )
    
    logger.info(f"Geocoded {request.location}: {location_data['latitude']}, {location_data['longitude']}")
    
    return GeocodeResponse(
        status="success",
        location=request.location,
        latitude=location_data["latitude"],
        longitude=location_data["longitude"],
        display_name=location_data["display_name"]
    )


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "service": "Weather MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "weather": "/weather (POST)",
            "time": "/time (POST)",
            "geocode": "/geocode (POST)",
            "docs": "/docs"
        }
    }


def main():
    """Main entry point."""
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Weather MCP Server on {host}:{port}")
    logger.info(f"Nominatim user agent: {NOMINATIM_USER_AGENT}")
    logger.info(f"Request timeout: {REQUEST_TIMEOUT}s")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
