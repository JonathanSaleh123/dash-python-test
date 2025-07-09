import psycopg2
import json
import requests
from shapely.geometry import shape # For converting GeoJSON to WKB for PostGIS

# Database connection details
DB_HOST = "localhost"
DB_NAME = "your_database_name"
DB_USER = "your_username"
DB_PASSWORD = "your_password"

ZIP_GEOJSON_URL = "https://raw.githubusercontent.com/ndrezn/zip-code-geojson/master/usa_zip_codes_geo_100m.json"
CITY_GEOJSON_BASE_URL = "https://raw.githubusercontent.com/generalpiston/geojson-us-city-boundaries/master/cities/"
ALL_STATE_ABBREVIATIONS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY"
]

def get_db_connection():
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None

def load_zip_data_to_db():
    conn = get_db_connection()
    if conn is None:
        return
    try:
        cur = conn.cursor()

        print("Fetching US Zip GeoJSON...")
        response = requests.get(ZIP_GEOJSON_URL)
        response.raise_for_status()
        zip_geojson = json.loads(response.text)
        print("US Zip GeoJSON fetched.")

        insert_query = """
        INSERT INTO us_zip_codes (zip_code, name, aland, awater, centroid_lat, centroid_lon, geometry)
        VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromEWKB(%s))
        ON CONFLICT (zip_code) DO UPDATE SET
            name = EXCLUDED.name,
            aland = EXCLUDED.aland,
            awater = EXCLUDED.awater,
            centroid_lat = EXCLUDED.centroid_lat,
            centroid_lon = EXCLUDED.centroid_lon,
            geometry = EXCLUDED.geometry;
        """

        for feature in zip_geojson["features"]:
            props = feature["properties"]
            geometry = feature["geometry"]

            zip_code = props.get("ZCTA5CE10")
            name = props.get("NAME10")
            aland = props.get("ALAND10")
            awater = props.get("AWATER10")
            
            centroid_lat = float(props.get("INTPTLAT10")) if props.get("INTPTLAT10") else None
            centroid_lon = float(props.get("INTPTLON10")) if props.get("INTPTLON10") else None
            
            # Convert GeoJSON geometry to WKB (Well-Known Binary) for PostGIS
            # You might need to install shapely: pip install shapely
            # This step is crucial for efficient storage and querying in PostGIS
            if geometry:
                # Ensure geometry is valid and handle potential errors during conversion
                try:
                    shapely_geometry = shape(geometry)
                    if shapely_geometry.is_valid:
                        wkb_geometry = shapely_geometry.wkb_hex # Get hex representation
                    else:
                        print(f"Invalid geometry for zip code {zip_code}, attempting to fix...")
                        shapely_geometry = shapely_geometry.buffer(0) # Attempt to fix invalid geometry
                        if shapely_geometry.is_valid:
                            wkb_geometry = shapely_geometry.wkb_hex
                        else:
                            print(f"Could not fix geometry for zip code {zip_code}. Skipping.")
                            wkb_geometry = None
                except Exception as e:
                    print(f"Error converting geometry for zip code {zip_code}: {e}")
                    wkb_geometry = None
            else:
                wkb_geometry = None

            if wkb_geometry:
                cur.execute(insert_query, (zip_code, name, aland, awater, centroid_lat, centroid_lon, wkb_geometry))
        
        conn.commit()
        print("US Zip GeoJSON data loaded into database successfully.")

    except (Exception, psycopg2.Error) as error:
        print(f"Error while connecting to PostgreSQL or inserting data: {error}")
    finally:
        if conn:
            cur.close()
            conn.close()
            print("PostgreSQL connection closed.")


# def load_city_data_to_db():
#     conn = get_db_connection()
#     if conn is None:
#         print("Could not establish database connection. Aborting city data load.")
#         return

#     cur = conn.cursor()

#     # SQL query for inserting/updating city data
#     insert_query = """
#     INSERT INTO us_cities (city_name, state_abbr, city_slug, centroid_lat, centroid_lon, geometry)
#     VALUES (%s, %s, %s, %s, %s, ST_GeomFromEWKB(%s))
#     ON CONFLICT (city_slug) DO UPDATE SET
#         city_name = EXCLUDED.city_name,
#         state_abbr = EXCLUDED.state_abbr,
#         centroid_lat = EXCLUDED.centroid_lat,
#         centroid_lon = EXCLUDED.centroid_lon,
#         geometry = EXCLUDED.geometry;
#     """

#     for state_abbr in ALL_STATE_ABBREVIATIONS:
#         state_folder_url = f"{CITY_GEOJSON_BASE_URL}{state_abbr.lower()}/"
#         print(f"\nProcessing state: {state_abbr.upper()}")

#         try:
#             # A common way to list files in a GitHub repo directory via API or by guessing common slugs
#             # For simplicity here, we will *try to infer* potential city slugs
#             # A more robust solution would involve fetching the directory listing from GitHub API
#             # For now, let's assume we have a list of slugs or infer them.
#             # This part is the most challenging due to the directory structure.
#             # Ideal scenario: A manifest file or direct API access to list files.
            
#             # --- For demonstration, let's hardcode a few common city slugs per state
#             # --- In a real application, you might fetch all filenames from the repo.
#             # --- Example: Fetching file list via GitHub API (more complex, requires token for rate limits)
#             # --- Or, if you download the repo locally, you can os.listdir()
            
#             # Since directly listing contents of a GitHub folder via raw.githubusercontent.com is not possible,
#             # we either need to know the city slugs beforehand, or modify the source to provide a manifest,
#             # or rely on scraping/GitHub API.
#             # For this example, let's try to simulate by assuming some common slugs or
#             # if you had a local copy, you'd iterate `os.listdir(local_path_to_state_folder)`
            
#             # This is a placeholder for how you'd get city slugs.
#             # In practice, you might pre-process the entire repo to get a list of all city slugs.
            
#             # This repository has an index.json in each state folder that lists cities.
#             # Let's try to use that.
#             index_url = f"{state_folder_url}index.json"
#             print(f"Fetching index for {state_abbr.upper()} from: {index_url}")
#             index_response = requests.get(index_url)
#             index_response.raise_for_status()
#             city_index = json.loads(index_response.text)
            
#             city_slugs_to_process = [item['slug'] for item in city_index] # Assuming 'slug' key
            
#         except requests.exceptions.RequestException as e:
#             print(f"Could not fetch index for {state_abbr.upper()}: {e}. Skipping state.")
#             continue
#         except json.JSONDecodeError as e:
#             print(f"Error decoding index for {state_abbr.upper()}: {e}. Skipping state.")
#             continue
#         except KeyError: # If 'slug' key is missing
#             print(f"Index for {state_abbr.upper()} does not contain expected 'slug' key. Skipping state.")
#             continue


#         for city_slug in city_slugs_to_process:
#             city_file_url = f"{state_folder_url}{city_slug}.json"
#             try:
#                 print(f"  Fetching city: {city_slug}...")
#                 city_response = requests.get(city_file_url, timeout=10) # Add timeout
#                 city_response.raise_for_status()
#                 city_data = json.loads(city_response.text)

#                 if not city_data["features"]:
#                     print(f"    No features found in {city_slug}.json. Skipping.")
#                     continue

#                 # The city GeoJSON files usually contain a single Feature
#                 feature = city_data["features"][0]
#                 props = feature["properties"]
#                 geometry = feature["geometry"]

#                 city_name = props.get("NAME") # Common property for city name
#                 # If NAME is not consistent, you might derive it from city_slug
#                 if not city_name:
#                     city_name = city_slug.replace('_', ' ').title()

#                 centroid_lat = props.get("CENTROID_LAT") # The repo provides these
#                 centroid_lon = props.get("CENTROID_LON")
                
#                 if geometry:
#                     try:
#                         shapely_geometry = shape(geometry)
#                         # Fix invalid geometries if any
#                         if not shapely_geometry.is_valid:
#                             print(f"    Invalid geometry for {city_slug}, attempting to fix...")
#                             shapely_geometry = shapely_geometry.buffer(0) # Attempt to fix
#                             if not shapely_geometry.is_valid:
#                                 print(f"    Could not fix geometry for {city_slug}. Skipping.")
#                                 wkb_geometry = None
#                             else:
#                                 wkb_geometry = dumps(shapely_geometry, hex=True, srid=4326) # Add SRID
#                         else:
#                             wkb_geometry = dumps(shapely_geometry, hex=True, srid=4326) # Add SRID
#                     except Exception as e:
#                         print(f"    Error converting geometry for {city_slug}: {e}. Skipping.")
#                         wkb_geometry = None
#                 else:
#                     wkb_geometry = None

#                 if wkb_geometry:
#                     cur.execute(insert_query, (city_name, state_abbr.upper(), city_slug,
#                                                centroid_lat, centroid_lon, wkb_geometry))
#                     conn.commit() # Commit after each city or in batches
#                     # print(f"    Inserted/Updated: {city_name} ({state_abbr.upper()})")
#                 else:
#                     print(f"    Skipping {city_slug} due to missing or invalid geometry.")

#             except requests.exceptions.RequestException as e:
#                 print(f"  Error fetching {city_slug}.json: {e}. Skipping.")
#                 continue
#             except json.JSONDecodeError as e:
#                 print(f"  Error decoding {city_slug}.json: {e}. Skipping.")
#                 continue
#             except Exception as e:
#                 print(f"  An unexpected error occurred for {city_slug}: {e}. Skipping.")
#                 conn.rollback() # Rollback on error if committing in batch
#                 continue
    
#     cur.close()
#     conn.close()
#     print("\nFinished loading city data.")

if __name__ == "__main__":
    load_zip_data_to_db()
    # You'd call a similar function for cities