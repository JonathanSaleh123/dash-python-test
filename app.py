import dash
from dash import dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import json
import requests
import pandas as pd
# extra libraries for geocoding
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import re
from dash.exceptions import PreventUpdate 
#Database import
import psycopg2
from shapely.wkb import loads

# Initialize Nominatim geolocator
# This is used for geocoding city names and addresses (Finding lat/lon for cities)
geolocator = Nominatim(user_agent="city_zip_explorer_app_v1.0")

DB_CONFIG = {
    "host": "localhost",
    "database": "your_database_name",
    "user": "your_username",
    "password": "your_password"
}
STATE_ABBREVIATIONS = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    # Reverse mapping for easy lookup (full name to abbr)
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"
}

# Function to get a database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None
    
# Function to load the US Zip Code GeoJSON data from DB
def load_zip_geojson_from_db(zip_code=None):
    conn = get_db_connection()
    if conn is None:
        return {"type": "FeatureCollection", "features": []}
    try:
        cur = conn.cursor()
        query = "SELECT zip_code, name, centroid_lat, centroid_lon, ST_AsGeoJSON(geometry) FROM us_zip_codes"
        params = []
        if zip_code:
            query += " WHERE zip_code = %s"
            params.append(zip_code)
        
        cur.execute(query, tuple(params))
        features = []
        for row in cur.fetchall():
            zip_code_db, name, lat, lon, geojson_str = row
            if geojson_str:
                feature = {
                    "type": "Feature",
                    "geometry": json.loads(geojson_str),
                    "properties": {
                        "ZCTA5CE10": zip_code_db,
                        "NAME10": name,
                        "INTPTLAT10": str(lat) if lat else None, # Store as string to match original structure
                        "INTPTLON10": str(lon) if lon else None
                    }
                }
                features.append(feature)
        
        return {"type": "FeatureCollection", "features": features}

    except psycopg2.Error as e:
        print(f"Error querying zip codes from DB: {e}")
        return {"type": "FeatureCollection", "features": []}
    finally:
        if conn:
            cur.close()
            conn.close()

# Function to load a specific city's GeoJSON data from DB
def load_specific_city_geojson_from_db(state_abbr, city_slug):
    conn = get_db_connection()
    if conn is None:
        return {"type": "FeatureCollection", "features": []}

    try:
        cur = conn.cursor()
        query = """
        SELECT city_name, state_abbr, city_slug, centroid_lat, centroid_lon, ST_AsGeoJSON(geometry)
        FROM us_cities
        WHERE state_abbr = %s AND city_slug = %s;
        """
        cur.execute(query, (state_abbr.upper(), city_slug))
        
        features = []
        row = cur.fetchone()
        if row:
            city_name_db, state_abbr_db, city_slug_db, lat, lon, geojson_str = row
            if geojson_str:
                feature = {
                    "type": "Feature",
                    "geometry": json.loads(geojson_str),
                    "properties": {
                        "NAME": city_name_db,
                        "STATE_ABBR": state_abbr_db,
                        "CITY_SLUG": city_slug_db,
                        "CENTROID_LAT": lat,
                        "CENTROID_LON": lon
                    }
                }
                features.append(feature)
        
        return {"type": "FeatureCollection", "features": features}

    except psycopg2.Error as e:
        print(f"Error querying city from DB: {e}")
        return {"type": "FeatureCollection", "features": []}
    finally:
        if conn:
            cur.close()
            conn.close()

# Initialize the Dash application
app = dash.Dash(__name__,
                 external_scripts=["https://unpkg.com/@tailwindcss/browser@4"])
app.layout = html.Div(
    className="min-h-screen bg-gray-100 p-4 font-inter antialiased flex flex-col items-center",
    children=[
        html.Link(href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap", rel="stylesheet"),
        html.H1(
            "City/Zip Code Map Explorer",
            className="text-4xl font-bold text-gray-800 mb-6 text-center"
        ),
        html.Div(
            className="flex flex-col lg:flex-row gap-6 w-full max-w-6xl bg-gray-100", 
            children=[
                # Input and Button section
                html.Div(
                    className="bg-white p-6 rounded-lg shadow-lg w-full lg:w-1/3 flex-shrink-0 flex flex-col space-y-4",
                    children=[
                        html.Div(
                            className="flex flex-col",
                            children=[
                                html.Label("Enter City or Zip Code:", className="text-gray-700 text-lg mb-2"),
                                dcc.Dropdown(
                                    id="location-dropdown",
                                    options=[], # Options will be populated by callback
                                    placeholder="Type to search for city or zip code...",
                                    className="p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                                    clearable=True,
                                    searchable=True,
                                    optionHeight=50
                                ),
                            ]
                        ),
                    ]
                ),
                # Map output section
                dcc.Loading(
                    id="loading-map",
                    type="circle",
                    className="w-full lg:flex-1",
                    children=html.Div(
                        id="map-output",
                        className="w-full h-[400px] lg:h-[600px] bg-gray-200 rounded-md overflow-hidden shadow-lg" 
                    )
                )
            ]
        )
    ]
)

# Callback to update dropdown options based on user input (autocomplete)
@app.callback(
    Output("location-dropdown", "options"),
    Input("location-dropdown", "search_value") 
)
def update_dropdown_options(search_value):
    if not search_value or len(search_value) < 3:
        raise PreventUpdate

    options = []
    
    # Try geocoding for city/address suggestions
    try:
        locations = geolocator.geocode(search_value, exactly_one=False, limit=3, timeout=5)
        if locations:
            for loc in locations:
                options.append({'label': loc.address, 'value': json.dumps({'address': loc.address, 'lat': loc.latitude, 'lon': loc.longitude})})
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding service error for suggestions: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during suggestion search: {e}")

    # Add zip code suggestion if it's a digit string
    if search_value.isdigit() and len(search_value) >= 3 and len(search_value) <= 5:
        if len(search_value) == 5:
            # Check if this zip exists in our DB (lighter query than full geojson)
            conn = get_db_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT zip_code FROM us_zip_codes WHERE zip_code = %s", (search_value,))
                    if cur.fetchone():
                        options.insert(0, {'label': f"Zip Code: {search_value}", 'value': json.dumps({'zip_code': search_value})})
                    else:
                        options.insert(0, {'label': f"Zip Code: {search_value} (No boundary data in DB)", 'value': json.dumps({'zip_code': search_value})})
                except Exception as e:
                    print(f"DB query error for zip suggestion: {e}")
                finally:
                    cur.close()
                    conn.close()
            else:
                options.insert(0, {'label': f"Zip Code: {search_value} (DB Error - No boundary data)", 'value': json.dumps({'zip_code': search_value})})
        else: # For partial zip codes
            options.insert(0, {'label': f"Zip Code: {search_value}", 'value': json.dumps({'zip_code': search_value})})

    return options


# Callback to load US Zip Code GeoJSON data and make map
@app.callback(
    Output("map-output", "children"),
    Input("location-dropdown", "value")
)
def update_map(selected_value_json):
    if not selected_value_json:
        return dcc.Graph(
            figure=px.scatter_mapbox(
                lat=[39.8283], lon=[-98.5795], zoom=3, height=600, width=800,
                mapbox_style="open-street-map",
                title="Enter a City or Zip Code to explore the map!"
            ).update_layout(margin={"r":0,"t":50,"l":0,"b":0})
        )

    selected_data = json.loads(selected_value_json)
    fig = None
    center_lat, center_lon, zoom_level = 39.8283, -98.5795, 3

    if 'zip_code' in selected_data:
        location_input = selected_data['zip_code']
        us_zip_geojson = load_zip_geojson_from_db(location_input) # Load only the specific zip's geojson

        filtered_features = us_zip_geojson["features"] if us_zip_geojson else []

        if filtered_features:
            filtered_geojson = {"type": "FeatureCollection", "features": filtered_features}
            
            # Prioritize centroids from DB if available
            first_feature_props = filtered_features[0]["properties"]
            if first_feature_props.get("INTPTLAT10") and first_feature_props.get("INTPTLON10"):
                center_lat = float(first_feature_props["INTPTLAT10"])
                center_lon = float(first_feature_props["INTPTLON10"])
                zoom_level = 10
            else: # Fallback to calculating centroid from geometry if not in properties
                coords = filtered_features[0]["geometry"]["coordinates"]
                if filtered_features[0]["geometry"]["type"] == "Polygon":
                    lons = [c[0] for c in coords[0]]
                    lats = [c[1] for c in coords[0]]
                elif filtered_features[0]["geometry"]["type"] == "MultiPolygon":
                    # For MultiPolygon, take the first polygon's exterior ring for centroid approximation
                    lons = [c[0] for c in coords[0][0]] 
                    lats = [c[1] for c in coords[0][0]]
                center_lon = sum(lons) / len(lons)
                center_lat = sum(lats) / len(lats)
                zoom_level = 10

            fig = px.choropleth_mapbox(
                geojson=filtered_geojson,
                locations=[location_input],
                featureidkey="properties.ZCTA5CE10",
                color_discrete_sequence=["blue"],
                mapbox_style="open-street-map",
                zoom=zoom_level,
                center={"lat": center_lat, "lon": center_lon},
                opacity=0.5,
                height=600,
                width=800,
                title=f"Area for Zip Code: {location_input}"
            )
            fig.update_traces(marker_line_width=2, marker_line_color="black")
        else:
            fig = px.scatter_mapbox(
                lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                mapbox_style="open-street-map",
                title=f"Zip Code '{location_input}' not found or no boundary data available."
            )
    elif 'address' in selected_data:
        full_address = selected_data['address']
        center_lat = selected_data['lat']
        center_lon = selected_data['lon']
        zoom_level = 9

        address_parts = full_address.split(', ')
        city_name_from_geocoded = address_parts[0].strip()

        state_abbr = None
        for part in address_parts:
            if part in STATE_ABBREVIATIONS:
                state_abbr = STATE_ABBREVIATIONS[part]
                break
            elif len(part) == 2 and re.match(r'^[A-Z]{2}$', part):
                if part in STATE_ABBREVIATIONS.values():
                    state_abbr = part
                    break
        
        city_slug = re.sub(r'[^a-z0-9]+', '_', city_name_from_geocoded.lower()).strip('_')
        
        city_geojson_data = {"type": "FeatureCollection", "features": []}

        if state_abbr:
            # Try original slug, then with _city suffix, then without _city suffix if present
            city_geojson_data = load_specific_city_geojson_from_db(state_abbr.upper(), city_slug)
            
            if not city_geojson_data["features"] and not city_slug.endswith("_city"):
                print(f"Retrying with '_city' suffix for {city_slug}")
                city_geojson_data = load_specific_city_geojson_from_db(state_abbr.upper(), city_slug + "_city")
            
            if not city_geojson_data["features"] and city_slug.endswith("_city"):
                print(f"Retrying by removing '_city' suffix for {city_slug}")
                city_geojson_data = load_specific_city_geojson_from_db(state_abbr.upper(), city_slug[:-len("_city")])

        if city_geojson_data and city_geojson_data["features"]:
            feature_name_in_geojson = city_geojson_data["features"][0]["properties"].get("NAME", city_slug)

            fig = px.choropleth_mapbox(
                data_frame=pd.DataFrame({'city': [feature_name_in_geojson], 'value': [1]}),
                geojson=city_geojson_data,
                locations='city',
                featureidkey="properties.NAME",
                color='value',
                color_discrete_sequence=["green"],
                mapbox_style="open-street-map",
                zoom=10,
                center={"lat": center_lat, "lon": center_lon},
                opacity=0.6,
                height=600,
                width=800,
                title=f"Boundary for City: {full_address}"
            )
            fig.update_traces(marker_line_width=2, marker_line_color="black")
            
            fig.add_trace(go.Scattermapbox(
                lat=[center_lat],
                lon=[center_lon],
                mode='markers',
                marker=go.scattermapbox.Marker(size=10, color='red'),
                name=f"Geocoded Point: {full_address}"
            ))

        else:
            fig = px.scatter_mapbox(
                lat=[center_lat],
                lon=[center_lon],
                zoom=zoom_level,
                mapbox_style="open-street-map",
                height=600,
                width=800,
                title=f"Location for City: {full_address} (Boundary data not found in DB or available)"
            )
            fig.update_traces(marker=dict(size=20, opacity=0.7, symbol="circle", color="red"))
    else:
        fig = px.scatter_mapbox(
            lat=[center_lat], lon=[center_lon], zoom=3, height=600,
            mapbox_style="open-street-map",
            title="Please select a valid location from the dropdown."
        )

    fig.update_layout(margin={"r":0,"t":50,"l":0,"b":0})
    return dcc.Graph(figure=fig)

if __name__ == "__main__":
    app.run(debug=True)