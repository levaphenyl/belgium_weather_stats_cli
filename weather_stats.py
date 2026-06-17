import sys
import argparse
import json
import requests
import numpy as np
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

WFS_URL = "https://opendata.meteo.be/geoserver/wfs"

def get_nearest_station(lat, lon):
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "aws:aws_station",
        "outputFormat": "application/json"
    }
    response = requests.get(WFS_URL, params=params)
    response.raise_for_status()
    data = response.json()

    stations = data["features"]
    nearest_station = None
    min_dist = float("inf")

    target_coords = (lat, lon)

    for feature in stations:
        station_coords = (feature["geometry"]["coordinates"][1], feature["geometry"]["coordinates"][0])
        dist = geodesic(target_coords, station_coords).kilometers
        if dist < min_dist:
            min_dist = dist
            nearest_station = feature["properties"]

    return nearest_station, min_dist

def fetch_weather_data(station_code, date_str):
    # Parse date and create start/end timestamps
    start_time = f"{date_str}T00:00:00Z"
    end_time = f"{date_str}T23:59:59Z"

    cql_filter = f"code={station_code} AND timestamp >= '{start_time}' AND timestamp <= '{end_time}'"

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "aws:aws_1hour",
        "outputFormat": "application/json",
        "CQL_FILTER": cql_filter
    }

    response = requests.get(WFS_URL, params=params)
    response.raise_for_status()
    return response.json()

def calculate_stats(data, field_name):
    values = [f["properties"][field_name] for f in data["features"] if f["properties"][field_name] is not None]
    if not values:
        return None, None

    median = np.median(values)
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1

    return median, iqr

def main():
    parser = argparse.ArgumentParser(description="Query historical hourly weather data from RMI Belgium.")
    parser.add_argument("date", help="Date in YYYY-MM-DD format")
    parser.add_argument("place", help="Place name")

    args = parser.parse_args()

    # 1. Geocode place
    geolocator = Nominatim(user_agent="weather_stats_script")
    location = geolocator.geocode(args.place)
    if not location:
        print(f"Error: Could not find location for '{args.place}'")
        sys.exit(1)

    print(f"Location found: {location.address} ({location.latitude}, {location.longitude})")

    # 2. Find nearest station
    station, distance = get_nearest_station(location.latitude, location.longitude)
    if not station:
        print("Error: Could not find any weather stations.")
        sys.exit(1)

    print(f"Nearest station: {station['name']} (Code: {station['code']}) at {distance:.2f} km")

    # 3. Fetch data
    weather_data = fetch_weather_data(station['code'], args.date)

    if not weather_data["features"]:
        print(f"No data found for station {station['name']} on {args.date}")
        return

    # 4. Calculate and display stats
    fields = {
        "temp_dry_shelter_avg": "Dry Shelter Temperature (°C)",
        "precip_quantity": "Precipitation Quantity (mm)",
        "sun_duration": "Sunshine Duration (min)"
    }

    print(f"\nStats for {args.date} at station {station['name']}:")
    print("-" * 50)
    print(f"{'Parameter':<30} | {'Median':<10} | {'IQR':<10}")
    print("-" * 50)

    for field, label in fields.items():
        median, iqr = calculate_stats(weather_data, field)
        if median is not None:
            print(f"{label:<30} | {median:>10.2f} | {iqr:>10.2f}")
        else:
            print(f"{label:<30} | {'N/A':>10} | {'N/A':>10}")

if __name__ == "__main__":
    main()
