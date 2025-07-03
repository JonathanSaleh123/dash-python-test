import dash
from dash import dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go # Import graph_objects for more control
import json
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd
import re

# Initialize Nominatim geolocator
geolocator = Nominatim(user_agent="geo-dash-app")

# Global variable to store US zip code GeoJSON data
us_zip_geojson = None

# URLs for GeoJSON data
ZIP_GEOJSON_URL = "https://raw.githubusercontent.com/ndrezn/zip-code-geojson/master/usa_zip_codes_geo_100m.json"
CITY_GEOJSON_BASE_URL = "https://raw.githubusercontent.com/generalpiston/geojson-us-city-boundaries/master/cities/"

# State FIPS to abbreviation mapping (expanded for better geocoding results)
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
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "OH": "Ohio",
    "Oklahoma": "OK", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"
}

# Function to load the US Zip Code GeoJSON data
def load_zip_geojson():
    global us_zip_geojson
    if us_zip_geojson is None:
        try:
            print(f"Attempting to load US Zip GeoJSON from: {ZIP_GEOJSON_URL}")
            response = requests.get(ZIP_GEOJSON_URL)
            response.raise_for_status()
            us_zip_geojson = json.loads(response.text)
            print("US Zip GeoJSON loaded successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error loading US Zip GeoJSON: {e}")
            us_zip_geojson = {"type": "FeatureCollection", "features": []}
        except json.JSONDecodeError as e:
            print(f"Error decoding US Zip GeoJSON: {e}")
            us_zip_geojson = {"type": "FeatureCollection", "features": []}
    return us_zip_geojson

# Function to load a specific city's GeoJSON data
def load_specific_city_geojson(state_abbr, city_slug):
    city_geojson_url = f"{CITY_GEOJSON_BASE_URL}{state_abbr.lower()}/{city_slug}.json"
    try:
        print(f"Attempting to load City GeoJSON for {city_slug.replace('_', ' ').title()} in {state_abbr.upper()} from: {city_geojson_url}")
        response = requests.get(city_geojson_url)
        response.raise_for_status()
        city_data = json.loads(response.text)
        print(f"City GeoJSON for {city_slug.replace('_', ' ').title()} loaded successfully.")
        return city_data
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error loading city GeoJSON for {city_slug.replace('_', ' ').title()}: {e.response.status_code} - {e.response.reason}. URL: {city_geojson_url}")
        if e.response.status_code == 404:
            print(f"File not found for {city_slug.replace('_', ' ').title()} at {city_geojson_url}. It might not exist in the repository.")
        return {"type": "FeatureCollection", "features": []}
    except requests.exceptions.RequestException as e:
        print(f"Error loading City GeoJSON for {city_slug.replace('_', ' ').title()}: {e}")
        return {"type": "FeatureCollection", "features": []}
    except json.JSONDecodeError as e:
        print(f"Error decoding City GeoJSON for {city_slug.replace('_', ' ').title()}: {e}")
        return {"type": "FeatureCollection", "features": []}

# Initialize the Dash application
app = dash.Dash(__name__,
                 external_scripts=["https://unpkg.com/@tailwindcss/browser@4"])

# Define the layout
app.layout = html.Div(
    className="min-h-screen bg-gray-100 p-4 font-inter antialiased flex flex-col items-center",
    children=[
        # Tailwind CSS and Inter font import
        html.Script(src="https://cdn.tailwindcss.com"),
        html.Link(href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap", rel="stylesheet"),

        html.H1(
            "City/Zip Code Map Explorer",
            className="text-4xl font-bold text-gray-800 mb-6 text-center"
        ),
        # Main content area: Input/Button section and Map section side-by-side
        html.Div(
            className="flex flex-col lg:flex-row gap-6 w-full max-w-6xl bg-gray-100", # Responsive flex container
            children=[
                # Input and Button section
                html.Div(
                    className="bg-white p-6 rounded-lg shadow-lg w-full lg:w-1/3 flex-shrink-0 flex flex-col space-y-4",
                    children=[
                        html.Div(
                            className="flex flex-col",
                            children=[
                                html.Label("Enter City or Zip Code:", className="text-gray-700 text-lg mb-2"),
                                dcc.Input(
                                    id="location-input",
                                    type="text",
                                    placeholder="e.g., 90210 or San Francisco, CA",
                                    className="p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                ),
                            ]
                        ),
                        html.Button(
                            "Show on Map",
                            id="submit-button",
                            n_clicks=0,
                            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-md shadow-md transition duration-300 ease-in-out transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                        ),
                    ]
                ),

                # Map output section
                dcc.Loading(
                    id="loading-map",
                    type="circle",
                    className="w-full lg:flex-1", # Map container takes remaining space
                    children=html.Div(
                        id="map-output",
                        className="w-full h-[400px] lg:h-[600px] bg-gray-200 rounded-md overflow-hidden shadow-lg" # Adjusted height for smaller map
                    )
                )
            ]
        )
    ]
)

@app.callback(
    Output("map-output", "children"),
    Input("submit-button", "n_clicks"),
    State("location-input", "value")
)
def update_map(n_clicks, location_input):
    if n_clicks == 0 or not location_input:
        # Initial map view or no input
        return dcc.Graph(
            figure=px.scatter_mapbox(
                lat=[39.8283], lon=[-98.5795], zoom=3, height=600, width=800, # Adjusted height and width for initial view
                mapbox_style="open-street-map",
                title="Enter a City or Zip Code to explore the map!"
            ).update_layout(margin={"r":0,"t":50,"l":0,"b":0})
        )

    fig = None
    center_lat, center_lon, zoom_level = 39.8283, -98.5795, 3

    is_zip_code = False
    if location_input.isdigit() and len(location_input) == 5:
        is_zip_code = True

    if is_zip_code:
        global us_zip_geojson
        if us_zip_geojson is None:
            load_zip_geojson()
            if us_zip_geojson is None or not us_zip_geojson["features"]:
                return html.Div("Error: Could not load US zip code data. Please try again later.", className="text-red-500 text-center mt-4")

        filtered_features = [
            f for f in us_zip_geojson["features"]
            if f["properties"].get("ZCTA5CE10") == location_input
        ]

        if filtered_features:
            filtered_geojson = {"type": "FeatureCollection", "features": filtered_features}
            if filtered_features[0]["properties"].get("INTPTLAT10") and filtered_features[0]["properties"].get("INTPTLON10"):
                center_lat = float(filtered_features[0]["properties"]["INTPTLAT10"])
                center_lon = float(filtered_features[0]["properties"]["INTPTLON10"])
                zoom_level = 10
            else:
                # Fallback for calculating center if centroid properties are missing
                coords = filtered_features[0]["geometry"]["coordinates"]
                if filtered_features[0]["geometry"]["type"] == "Polygon":
                    lons = [c[0] for c in coords[0]]
                    lats = [c[1] for c in coords[0]]
                elif filtered_features[0]["geometry"]["type"] == "MultiPolygon":
                    # For MultiPolygon, take the first polygon's coordinates
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
                height=600, # Keep graph height consistent for the dcc.Graph component
                width=800, # Adjust width for better display
                title=f"Area for Zip Code: {location_input}"
            )
            fig.update_traces(marker_line_width=2, marker_line_color="black")
        else:
            fig = px.scatter_mapbox(
                lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                mapbox_style="open-street-map",
                title=f"Zip Code '{location_input}' not found or no boundary data available."
            )
    else:
        # Handle city input
        try:
            location = geolocator.geocode(location_input, timeout=5)
            if location:
                center_lat = location.latitude
                center_lon = location.longitude
                zoom_level = 9

                address_parts = location.address.split(', ')
                state_abbr = None
                for part in address_parts:
                    if part in STATE_ABBREVIATIONS:
                        state_abbr = STATE_ABBREVIATIONS[part]
                        break
                    elif len(part) == 2 and re.match(r'^[A-Z]{2}$', part):
                        # Ensure the 2-letter part is a valid state abbreviation
                        if part in STATE_ABBREVIATIONS.values(): # Check against values (abbrs)
                            state_abbr = part
                            break
                
                # Clean city name for slug creation
                city_name_from_input_raw = location_input.split(',')[0].strip()
                city_slug = re.sub(r'[^a-z0-9]+', '_', city_name_from_input_raw.lower()).strip('_')
                
                city_geojson_data = {"type": "FeatureCollection", "features": []} # Initialize as empty

                if state_abbr:
                    # Attempt to load with original slug
                    city_geojson_data = load_specific_city_geojson(state_abbr.upper(), city_slug)
                    
                    # If no features, try adding "_city" suffix
                    if not city_geojson_data["features"] and not city_slug.endswith("_city"):
                        print(f"Retrying with '_city' suffix for {city_slug}")
                        city_geojson_data = load_specific_city_geojson(state_abbr.upper(), city_slug + "_city")
                    
                    # If still no features, try removing "_city" suffix if present (e.g., for New York City)
                    if not city_geojson_data["features"] and city_slug.endswith("_city"):
                        print(f"Retrying by removing '_city' suffix for {city_slug}")
                        city_geojson_data = load_specific_city_geojson(state_abbr.upper(), city_slug[:-len("_city")])


                if city_geojson_data and city_geojson_data["features"]:
                    # Create a simple DataFrame with a dummy value to enable choropleth_mapbox
                    # We need one row of data that "matches" the single feature in our GeoJSON
                    city_data_df = pd.DataFrame({'id_col': [city_slug]})

                    # Let's extract the actual name from the GeoJSON's first feature's properties
                    # to use as the location identifier for Plotly Express
                    feature_name_in_geojson = city_geojson_data["features"][0]["properties"].get("NAME", city_slug)

                    fig = px.choropleth_mapbox(
                        data_frame=pd.DataFrame({'city': [feature_name_in_geojson], 'value': [1]}), # Dummy DataFrame
                        geojson=city_geojson_data,
                        locations='city', # This column holds the identifier
                        featureidkey="properties.NAME", # This tells Plotly to match 'city' column with properties.NAME
                        color='value', # Color based on the dummy value
                        color_discrete_sequence=["green"],
                        mapbox_style="open-street-map",
                        zoom=10, # A closer zoom for specific city boundaries
                        center={"lat": center_lat, "lon": center_lon},
                        opacity=0.6,
                        height=600, # Keep graph height consistent for the dcc.Graph component
                        width=800,
                        title=f"Boundary for City: {location.address}"
                    )
                    fig.update_traces(marker_line_width=2, marker_line_color="black")
                    
                    # Add the geocoded point as a marker for context, if desired
                    fig.add_trace(go.Scattermapbox(
                        lat=[center_lat],
                        lon=[center_lon],
                        mode='markers',
                        marker=go.scattermapbox.Marker(size=10, color='red'),
                        name=f"Geocoded Point: {location.address}"
                    ))

                else:
                    # City boundary not found in the repository, fall back to marker
                    fig = px.scatter_mapbox(
                        lat=[center_lat],
                        lon=[center_lon],
                        zoom=zoom_level,
                        mapbox_style="open-street-map",
                        height=600, # Keep graph height consistent for the dcc.Graph component,
                        width=800,
                        title=f"Location for City: {location.address} (Boundary data not found or available)"
                    )
                    fig.update_traces(marker=dict(size=20, opacity=0.7, symbol="circle", color="red"))
            else:
                fig = px.scatter_mapbox(
                    lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                    mapbox_style="open-street-map",
                    title=f"City '{location_input}' not found."
                )
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            fig = px.scatter_mapbox(
                lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                mapbox_style="open-street-map",
                title=f"Geocoding service error for '{location_input}': {e}. Please try again."
            )
        except Exception as e:
            fig = px.scatter_mapbox(
                lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                mapbox_style="open-street-map",
                title=f"An unexpected error occurred for '{location_input}': {e}"
            )

    fig.update_layout(margin={"r":0,"t":50,"l":0,"b":0})
    return dcc.Graph(figure=fig)

# Pre-load the Zip Code GeoJSON data when the script starts.
load_zip_geojson()

if __name__ == "__main__":
    app.run(debug=True)