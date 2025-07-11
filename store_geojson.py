import json
import requests
from shapely.geometry import shape
from shapely.wkb import dumps # For converting GeoJSON to WKB for PostGIS
from supabase_config import get_supabase_client
import time

# Database connection details are no longer needed here as we use Supabase client

ZIP_GEOJSON_URL = "https://raw.githubusercontent.com/ndrezn/zip-code-geojson/master/usa_zip_codes_geo_100m.json"
CITY_GEOJSON_BASE_URL = "https://raw.githubusercontent.com/generalpiston/geojson-us-city-boundaries/master/cities/"
ALL_STATE_ABBREVIATIONS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY"
]

def load_zip_data_to_db():
    supabase = get_supabase_client()
    if supabase is None:
        print("Could not get Supabase client. Aborting zip data load.")
        return

    print("Fetching US Zip GeoJSON...")
    try:
        response = requests.get(ZIP_GEOJSON_URL)
        response.raise_for_status()
        zip_geojson = json.loads(response.text)
        print("US Zip GeoJSON fetched.")
        for feature in zip_geojson["features"]:
            props = feature["properties"]
            geometry = feature["geometry"]
            zip_code = props.get("ZCTA5CE10")
            name = props.get("NAME10")
            aland = props.get("ALAND10")
            awater = props.get("AWATER10")
            
            centroid_lat = float(props.get("INTPTLAT10")) if props.get("INTPTLAT10") else None
            centroid_lon = float(props.get("INTPTLON10")) if props.get("INTPTLON10") else None
            
            wkb_geometry = None
            if geometry:
                try:
                    shapely_geometry = shape(geometry)
                    if not shapely_geometry.is_valid:
                        print(f"Invalid geometry for zip code {zip_code}, attempting to fix...")
                        shapely_geometry = shapely_geometry.buffer(0)
                        if not shapely_geometry.is_valid:
                            print(f"Could not fix geometry for zip code {zip_code}. Skipping.")
                            continue
                    
                    # Convert to WKB hex and ensure SRID 4326
                    wkb_geometry = dumps(shapely_geometry, hex=True, srid=4326)
                except Exception as e:
                    print(f"Error converting geometry for zip code {zip_code}: {e}. Skipping.")
                    continue
            
            if wkb_geometry:
                data, count = supabase.table('us_zip_codes').upsert({
                    "zip_code": zip_code,
                    "name": name,
                    "aland": aland,
                    "awater": awater,
                    "centroid_lat": centroid_lat,
                    "centroid_lon": centroid_lon,
                    "geometry": wkb_geometry 
                }).execute()
                if not data:
                    print(f"Error inserting/updating zip code {zip_code}.")
            else:
                print(f"Skipping zip code {zip_code} due to missing or invalid geometry.")
        print("US Zip GeoJSON data loaded into database successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching zip code GeoJSON: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during zip data load: {e}")

def load_city_data_to_db():
    supabase = get_supabase_client()
    if supabase is None:
        print("Could not get Supabase client. Aborting city data load.")
        return

    for state_abbr in ALL_STATE_ABBREVIATIONS:
        state_folder_url = f"{CITY_GEOJSON_BASE_URL}{state_abbr.lower()}/"
        print(f"\nProcessing state: {state_abbr.upper()}")

        try:
            index_url = f"{state_folder_url}index.json"
            print(f"Fetching index for {state_abbr.upper()} from: {index_url}")
            index_response = requests.get(index_url)
            index_response.raise_for_status()
            city_index = json.loads(index_response.text)
            
            city_slugs_to_process = [item['slug'] for item in city_index]
            
        except requests.exceptions.RequestException as e:
            print(f"Could not fetch index for {state_abbr.upper()}: {e}. Skipping state.")
            continue
        except json.JSONDecodeError as e:
            print(f"Error decoding index for {state_abbr.upper()}: {e}. Skipping state.")
            continue
        except KeyError:
            print(f"Index for {state_abbr.upper()} does not contain expected 'slug' key. Skipping state.")
            continue

        for city_slug in city_slugs_to_process:
            city_file_url = f"{state_folder_url}{city_slug}.json"
            try:
                print(f"  Fetching city: {city_slug}...")
                city_response = requests.get(city_file_url, timeout=10)
                city_response.raise_for_status()
                city_data = json.loads(city_response.text)

                if not city_data["features"]:
                    print(f"    No features found in {city_slug}.json. Skipping.")
                    continue

                feature = city_data["features"][0]
                props = feature["properties"]
                geometry = feature["geometry"]

                city_name = props.get("NAME")
                if not city_name:
                    city_name = city_slug.replace('_', ' ').title()

                centroid_lat = props.get("CENTROID_LAT")
                centroid_lon = props.get("CENTROID_LON")
                
                wkb_geometry = None
                if geometry:
                    try:
                        shapely_geometry = shape(geometry)
                        if not shapely_geometry.is_valid:
                            print(f"    Invalid geometry for {city_slug}, attempting to fix...")
                            shapely_geometry = shapely_geometry.buffer(0)
                            if not shapely_geometry.is_valid:
                                print(f"    Could not fix geometry for {city_slug}. Skipping.")
                                continue
                        wkb_geometry = dumps(shapely_geometry, hex=True, srid=4326)
                    except Exception as e:
                        print(f"    Error converting geometry for {city_slug}: {e}. Skipping.")
                        continue
                
                if wkb_geometry:
                    data, count = supabase.table('us_cities').upsert({
                        "city_name": city_name,
                        "state_abbr": state_abbr.upper(),
                        "city_slug": city_slug,
                        "centroid_lat": centroid_lat,
                        "centroid_lon": centroid_lon,
                        "geometry": wkb_geometry
                    }).execute()
                    if not data:
                        print(f"    Error inserting/updating: {city_name} ({state_abbr.upper()}).")
                        # print(data) # uncomment for debugging
                else:
                    print(f"    Skipping {city_slug} due to missing or invalid geometry.")
                
                # Add a small delay to avoid hitting rate limits on external API
                time.sleep(0.1)

            except requests.exceptions.RequestException as e:
                print(f"  Error fetching {city_slug}.json: {e}. Skipping.")
                continue
            except json.JSONDecodeError as e:
                print(f"  Error decoding {city_slug}.json: {e}. Skipping.")
                continue
            except Exception as e:
                print(f"  An unexpected error occurred for {city_slug}: {e}. Skipping.")
                continue
    
    print("\nFinished loading city data.")

if __name__ == "__main__":
    load_zip_data_to_db()
    # load_city_data_to_db()