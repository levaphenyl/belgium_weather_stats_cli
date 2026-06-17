# Weather Stats

Query historical weather data from the Royal Meteorological Institute (RMI) of Belgium and calculate statistics (median, interquartile range, and probability of rainfall/sunshine) for a specific day of the year over the last 10 years.

## Contribution

This project was developed with the assistance of **Jules**, an AI software engineer.

## Data Source

The data is provided by the Royal Meteorological Institute (RMI) of Belgium.
More information can be found here: [RMI Open Data - Automatic Weather Stations (AWS) - 1 Day](https://opendata.meteo.be/geonetwork/srv/eng/catalog.search#/metadata/RMI_DATASET_AWS_1DAY)

## Installation

To install the package and its dependencies, run:

```bash
pip install .
```

## Usage

You can use the `weather-stats` command to query statistics for a specific date and location.

```bash
weather-stats <date> <location>
```

- `<date>`: Date in `YYYY-MM-DD` or `MM-DD` format (the year is ignored for historical statistics).
- `<location>`: Name of the place in Belgium (e.g., "Brussels", "Antwerp", "Ghent").

### Example

```bash
weather-stats 06-15 Brussels
```

Output:

```text
Stats for 06-15 (all years) at station UCCLE:
---------------------------------------------------------------------------
Parameter                         | Median     | IQR        | P(x > 0)
---------------------------------------------------------------------------
Dry Shelter Min Temperature (°C)  |       12.8 |        4.0 |       100%
Dry Shelter Max Temperature (°C)  |       23.6 |        5.2 |       100%
Precipitation Quantity (mm)       |        0.0 |        1.6 |        36%
Sunshine Duration (min)           |      600.6 |      425.2 |       100%
```

In this example, rainfall probability at any time on June 15th is 36%.
