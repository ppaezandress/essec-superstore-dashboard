"""Phase 5 - External data: population (datausa.io), economy (US Census ACS) and weather (open-meteo.com).

Every call is saved in external_cache/, so the app still works without internet (it says so when it does).
Run it alone to collect everything and print the completeness check:  python3 external_data.py

Economic indicators:
- Median household income and poverty rate come from the US Census Bureau's ACS 5-year tables
  (B19013 and B17001), served by the datausa.io API (no key needed).
- Unemployment rate comes straight from api.census.gov (table B23025). census.gov now requires a free key:
  get one at https://api.census.gov/data/key_signup.html and put it in .streamlit/secrets.toml as
  CENSUS_API_KEY = "..."  (or in the CENSUS_API_KEY environment variable).
"""
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).parent
CACHE = HERE / "external_cache"
DATAUSA = "https://api.datausa.io/tesseract/data.jsonrecords"
METEO = "https://archive-api.open-meteo.com/v1/archive"
CENSUS = "https://api.census.gov/data/{year}/acs/acs5"
MAP_YEAR = 2017  # last year of the Superstore data


def _get(url, params, label):
    """GET JSON; save it to the cache, or fall back to the cache when the network fails.
    Returns (data, origin) where origin is "live" or "cache"."""
    key = hashlib.md5((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:12]
    path = CACHE / f"{label}_{key}.json"
    try:
        query = "&".join(f"{k}={v}" for k, v in params.items())  # datausa needs raw ":" and ";" in include=
        r = requests.get(f"{url}?{query}", timeout=40)
        r.raise_for_status()
        data = r.json()
        CACHE.mkdir(exist_ok=True)
        path.write_text(json.dumps(data))
        return data, "live"
    except Exception:
        if path.exists():
            return json.loads(path.read_text()), "cache"
        raise


def _datausa(cube, drilldowns, measure, include="", label="datausa"):
    params = {"cube": cube, "drilldowns": drilldowns.replace(" ", "+"), "measures": measure.replace(" ", "+")}
    if include:
        params["include"] = include.replace(" ", "+")
    data, origin = _get(DATAUSA, params, label)
    return pd.DataFrame(data["data"]), origin


# ---------- Population ----------
def places_population(year=MAP_YEAR):
    """Population of every US place (city, town...) for one year: Place ID, Place ('Houston, TX'), Population."""
    return _datausa("acs_yg_total_population_5", "Place", "Population", f"Year:{year}", "places_population")


def states_population(year=MAP_YEAR):
    df, origin = _datausa("acs_yg_total_population_5", "State", "Population", f"Year:{year}", "states_population")
    return df[["State", "Population"]], origin


def match_cities(cities, places):
    """Attach a Census place to each Superstore (City, state code). Adds Place ID, Population, Match."""
    exact = dict(zip(places.Place.str.lower(), places.index))
    rows = []
    for city, code in zip(cities.City, cities.code):
        name = {"New York City": "New York"}.get(city, city).replace("Saint ", "St. ")
        idx, how = exact.get(f"{name}, {code}".lower()), "exact"
        if idx is None:  # e.g. "Indianapolis city (balance), IN", "Boise City, ID", "Franklin Town, MA"
            cand = places[places.Place.str.endswith(f", {code}") &
                          places.Place.str.match(re.escape(name) + r"[ \-/]")]
            idx, how = (cand.Population.idxmax(), "approximate") if len(cand) else (None, "not found")
        rows.append({"Place ID": places.at[idx, "Place ID"] if idx is not None else None,
                     "Population": places.at[idx, "Population"] if idx is not None else None, "Match": how})
    return pd.concat([cities.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


# ---------- City evolution: population, income, poverty ----------
def city_series(place_id):
    """Year-by-year population, median household income and poverty rate of one place."""
    pop, o1 = _datausa("acs_yg_total_population_5", "Year", "Population", f"Place:{place_id}", "pop_series")
    inc, o2 = _datausa("acs_ygr_median_household_income_race_5", "Year", "Household Income by Race",
                       f"Place:{place_id};Race:0", "income_series")
    pov, o3 = _datausa("acs_ygpsar_poverty_by_gender_age_race_5", "Year,Poverty Status", "Poverty Population",
                       f"Place:{place_id};Race:0", "poverty_series")
    pov = pov.pivot_table(index="Year", columns="Poverty Status ID", values="Poverty Population", aggfunc="sum")
    pov = (pov[0] / (pov[0] + pov[1])).rename("Poverty rate").reset_index()
    out = (pop[["Year", "Population"]]
           .merge(inc[["Year", "Household Income by Race"]].rename(columns={"Household Income by Race":
                                                                              "Median income"}), on="Year",
                  how="outer")
           .merge(pov, on="Year", how="outer").sort_values("Year").reset_index(drop=True))
    origin = "cache" if "cache" in (o1, o2, o3) else "live"
    return out, origin


def census_unemployment(place_id, key, years=range(2013, 2023)):
    """Unemployment rate from api.census.gov (ACS table B23025). Needs a free API key."""
    state, place = place_id[-7:-5], place_id[-5:]
    rows, origin = [], "live"
    for y in years:
        data, o = _get(CENSUS.format(year=y), {"get": "B23025_003E,B23025_005E", "for": f"place:{place}",
                                               "in": f"state:{state}", "key": key}, f"census_unemp_{y}")
        origin = "cache" if o == "cache" else origin
        labour, unemployed = float(data[1][0]), float(data[1][1])
        rows.append({"Year": y, "Unemployment rate": unemployed / labour})
    return pd.DataFrame(rows), origin


# ---------- Weather ----------
def weather_monthly(lat, lon, start="2014-01-01", end="2019-12-31"):
    """Monthly mean temperature (°C) and total rain (mm) from open-meteo's historical archive."""
    data, origin = _get(METEO, {"latitude": round(lat, 3), "longitude": round(lon, 3), "start_date": start,
                                "end_date": end, "daily": "temperature_2m_mean,precipitation_sum",
                                "timezone": "auto"}, "weather")
    d = pd.DataFrame(data["daily"])
    d["time"] = pd.to_datetime(d.time)
    missing_days = int(d[["temperature_2m_mean", "precipitation_sum"]].isna().any(axis=1).sum())
    m = (d.set_index("time").resample("MS")
         .agg({"temperature_2m_mean": "mean", "precipitation_sum": "sum"})
         .rename(columns={"temperature_2m_mean": "Temperature (°C)", "precipitation_sum": "Rain (mm)"})
         .reset_index().rename(columns={"time": "Month"}))
    return m, origin, len(d), missing_days


# ---------- Completeness check ----------
def check(source, what, df, expected_years=None, year_col="Year", origin="live", extra=""):
    years = sorted(df[year_col].dropna().unique()) if year_col in df else []
    missing_years = sorted(set(expected_years or []) - set(int(y) for y in years))
    missing_values = int(df.drop(columns=[year_col], errors="ignore").isna().sum().sum())
    ok = not missing_years and missing_values == 0
    return {"Source": source, "Data": what, "Rows": len(df),
            "Covers": f"{int(min(years))}-{int(max(years))}" if years else "-",
            "Missing years": ", ".join(map(str, missing_years)) or "none",
            "Missing values": missing_values,
            "Status": ("Complete" if ok else "Incomplete") + (" (offline copy)" if origin == "cache" else ""),
            "Notes": extra}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE))
    focus = {"New York City": "16000US3651000", "Houston": "16000US4835000", "Seattle": "16000US5363000",
             "Chicago": "16000US1714000"}
    places, _ = places_population()
    print(f"Places with population ({MAP_YEAR}): {len(places):,}")
    for name, pid in focus.items():
        s, o = city_series(pid)
        print(f"\n{name}  [{o}]")
        print(s.to_string(index=False))
        print(check("datausa.io", "population/income/poverty", s, range(2014, 2018), origin=o))
    coords = pd.read_csv(HERE / "city_coords.csv").set_index("City")
    for name in focus:
        lat, lon = coords.loc[name, ["lat", "lon"]].iloc[0] if coords.loc[[name]].shape[0] > 1 \
            else coords.loc[name, ["lat", "lon"]]
        w, o, days, miss = weather_monthly(lat, lon)
        print(f"\nWeather {name} [{o}]: {days} days, {miss} days with missing values, {len(w)} months")
