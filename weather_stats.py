import argparse
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

WFS_URL = "https://opendata.meteo.be/geoserver/wfs"

def get_nearest_station(lat: float, lon: float) -> Tuple[Dict[str, Any], float]:
    """
    Find the nearest weather station to the given coordinates.

    Parameters
    ----------
    lat : float
        Latitude of the target location.
    lon : float
        Longitude of the target location.

    Returns
    -------
    station : dict
        Properties of the nearest weather station.
    distance : float
        Distance to the nearest station in kilometers.

    Raises
    ------
    requests.HTTPError
        If the WFS request fails.
    """
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "aws:aws_station",
        "outputFormat": "application/json"
    }
    try:
        response = requests.get(WFS_URL, params=params)
        response.raise_for_status()
    except requests.HTTPError as e:
        logger.error(f"Failed to fetch stations from WFS: {e}")
        sys.exit(1)

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

    if nearest_station is None:
        logger.error("No weather stations found in the dataset.")
        sys.exit(1)

    return nearest_station, min_dist

def fetch_weather_data(station_code: int, month: int, day: int) -> Dict[str, Any]:
    """
    Fetch hourly weather data for a specific station, across all available years for a given month and day.

    Parameters
    ----------
    station_code : int
        The code of the weather station.
    month : int
        The month of the year (1-12).
    day : int
        The day of the month (1-31).

    Returns
    -------
    data : dict
        The GeoJSON FeatureCollection containing the weather data.

    Raises
    ------
    requests.HTTPError
        If the WFS request fails.
    """
    all_features = []
    # Query year by year since month() and day() functions are not supported by the WFS
    current_year = datetime.now().year
    for year in range(2003, current_year + 1):
        start_time = f"{year}-{month:02d}-{day:02d}T00:00:00Z"
        end_time = f"{year}-{month:02d}-{day:02d}T23:59:59Z"

        cql_filter = f"code={station_code} AND timestamp DURING {start_time}/{end_time}"

        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": "aws:aws_1hour",
            "outputFormat": "application/json",
            "CQL_FILTER": cql_filter
        }

        try:
            response = requests.get(WFS_URL, params=params)
            response.raise_for_status()
            data = response.json()
            all_features.extend(data.get("features", []))
        except requests.HTTPError as e:
            logger.warning(f"Failed to fetch weather data for {year}-{month:02d}-{day:02d}: {e}")
            continue
        except Exception as e:
            logger.warning(f"An error occurred for {year}-{month:02d}-{day:02d}: {e}")
            continue

    return {"type": "FeatureCollection", "features": all_features}

def calculate_stats(data: Dict[str, Any], field_name: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculate the median and interquartile range (IQR) for a specific field in the weather data.

    Parameters
    ----------
    data : dict
        The GeoJSON FeatureCollection containing the weather data.
    field_name : str
        The name of the property to calculate statistics for.

    Returns
    -------
    median : float, optional
        The median value of the field, or None if no data points exist.
    iqr : float, optional
        The interquartile range of the field, or None if no data points exist.
    """
    values = [f["properties"][field_name] for f in data["features"] if f["properties"][field_name] is not None]
    if not values:
        return None, None

    median = np.median(values)
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1

    return float(median), float(iqr)

def main():
    parser = argparse.ArgumentParser(description="Query historical hourly weather data from RMI Belgium.")
    parser.add_argument("date", help="Date in YYYY-MM-DD or MM-DD format (year is ignored for stats)")
    parser.add_argument("place", help="Place name")

    args = parser.parse_args()

    # Parse month and day from input date
    try:
        if len(args.date.split('-')) == 3:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
        else:
            dt = datetime.strptime(args.date, "%m-%d")
        month, day = dt.month, dt.day
    except ValueError:
        logger.error("Invalid date format. Please use YYYY-MM-DD or MM-DD.")
        sys.exit(1)

    # 1. Geocode place
    geolocator = Nominatim(user_agent="weather_stats_script")
    location = geolocator.geocode(args.place)
    if not location:
        logger.error(f"Could not find location for '{args.place}'")
        sys.exit(1)

    logger.info(f"Location found: {location.address} ({location.latitude}, {location.longitude})")

    # 2. Find nearest station
    station, distance = get_nearest_station(location.latitude, location.longitude)

    logger.info(f"Nearest station: {station['name']} (Code: {station['code']}) at {distance:.2f} km")

    # 3. Fetch data for all years
    logger.info(f"Fetching data for month {month}, day {day} across all years (2003-{datetime.now().year})...")
    weather_data = fetch_weather_data(station['code'], month, day)

    if not weather_data["features"]:
        logger.error(f"No data found for station {station['name']} on {month:02d}-{day:02d}")
        return

    # 4. Calculate and display stats
    fields = {
        "temp_dry_shelter_avg": "Dry Shelter Temperature (°C)",
        "precip_quantity": "Precipitation Quantity (mm)",
        "sun_duration": "Sunshine Duration (min)"
    }

    print(f"\nStats for {month:02d}-{day:02d} (all years) at station {station['name']}:")
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
