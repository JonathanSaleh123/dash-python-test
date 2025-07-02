import dash
from dash import dcc, html, Input, Output, State
import plotly.express as px
import json
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd # Although not directly used for data manipulation, it's a common dependency for geo-related tasks

# Initialize Nominatim geolocator for converting city names to coordinates
geolocator = Nominatim(user_agent="geo-dash-app")

# Global variable to store GeoJSON data for US zip codes.
# This large dataset will be loaded once when the application starts
# to avoid repeated network requests and improve performance.
us_zip_geojson = None
# URL for a comprehensive US zip code GeoJSON file (26MB resolution)
ZIP_GEOJSON_URL = "https://raw.githubusercontent.com/ndrezn/zip-code-geojson/master/usa_zip_codes_geo_100m.json"
US_CITY_GEOJSON_URL = "https://github.com/generalpiston/geojson-us-city-boundaries/master/"
# Function to load the GeoJSON data from the specified URL.
# This function is called once at the application's startup.
def load_zip_geojson():
    global us_zip_geojson
    if us_zip_geojson is None:
        try:
            print(f"Attempting to load GeoJSON from: {ZIP_GEOJSON_URL}")
            response = requests.get(ZIP_GEOJSON_URL)
            response.raise_for_status()  # Raise an exception for HTTP errors (e.g., 404, 500)
            us_zip_geojson = json.loads(response.text)
            print("GeoJSON loaded successfully.")
        except requests.exceptions.RequestException as e:
            # Handle network or request-related errors
            print(f"Error loading GeoJSON: {e}")
            # Set to an empty GeoJSON FeatureCollection to prevent further errors
            us_zip_geojson = {"type": "FeatureCollection", "features": []}
        except json.JSONDecodeError as e:
            # Handle JSON parsing errors if the response is not valid JSON
            print(f"Error decoding GeoJSON: {e}")
            us_zip_geojson = {"type": "FeatureCollection", "features": []}
    return us_zip_geojson

# Initialize the Dash application
app = dash.Dash(__name__)

# Define the layout of the Dash application using HTML components and Tailwind CSS classes.
# The layout includes an input field, a button, and a graph component for the map.
app.layout = html.Div(
    className="min-h-screen bg-gray-100 p-4 font-inter antialiased flex flex-col items-center",
    children=[
        # Load Tailwind CSS for styling
        html.Script(src="https://cdn.tailwindcss.com"),
        # Load Inter font from Google Fonts
        html.Link(href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap", rel="stylesheet"),

        # Main application title
        html.H1(
            "City/Zip Code Map Explorer",
            className="text-4xl font-bold text-gray-800 mb-6 text-center"
        ),

        # Container for input and button
        html.Div(
            className="bg-white p-6 rounded-lg shadow-lg w-full max-w-md flex flex-col space-y-4",
            children=[
                html.Div(
                    className="flex flex-col",
                    children=[
                        html.Label("Enter City or Zip Code:", className="text-gray-700 text-lg mb-2"),
                        dcc.Input(
                            id="location-input",
                            type="text",
                            placeholder="e.g., 90210 or New York",
                            className="p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        ),
                    ]
                ),
                html.Button(
                    "Show on Map",
                    id="submit-button",
                    n_clicks=0, # Initialize click count
                    className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-md shadow-md transition duration-300 ease-in-out transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                ),
                # Loading component to show a spinner while the map is being updated
                dcc.Loading(
                    id="loading-map",
                    type="circle", # Spinner type
                    children=html.Div(id="map-output", className="w-full h-[600px] bg-gray-200 rounded-md overflow-hidden")
                )
            ]
        )
    ]
)

# Define the callback function that updates the map based on user input.
# It listens for clicks on the submit button and uses the value from the input field.
@app.callback(
    Output("map-output", "children"), # Output: the content of the 'map-output' div
    Input("submit-button", "n_clicks"), # Input: number of clicks on the submit button
    State("location-input", "value") # State: the current value of the input field
)
def update_map(n_clicks, location_input):
    # Initial state or if no input is provided
    if n_clicks == 0 or not location_input:
        # Display a default map of the US with a welcome message
        return dcc.Graph(
            figure=px.scatter_mapbox(
                lat=[39.8283], lon=[-98.5795], zoom=3, height=600, # Centered on the US
                mapbox_style="open-street-map", # Use OpenStreetMap tiles
                title="Enter a City or Zip Code to explore the map!"
            ).update_layout(margin={"r":0,"t":50,"l":0,"b":0}) # Adjust margins for better display
        )

    # Ensure GeoJSON data is loaded before proceeding
    global us_zip_geojson
    if us_zip_geojson is None:
        load_zip_geojson() # Attempt to load if not already loaded
        if us_zip_geojson is None or not us_zip_geojson["features"]: # Check if loading failed or returned empty
            return html.Div("Error: Could not load geographical data. Please try again later.", className="text-red-500 text-center mt-4")

    fig = None
    # Default map center and zoom for the US, used as fallback
    center_lat, center_lon, zoom_level = 39.8283, -98.5795, 3

    # Determine if the input is likely a 5-digit US zip code
    is_zip_code = False
    if location_input.isdigit() and len(location_input) == 5:
        is_zip_code = True

    if is_zip_code:
        # Filter the pre-loaded GeoJSON data to find the feature corresponding to the input zip code.
        # 'ZCTA5CE10' is the property key for 5-digit ZCTA (Zip Code Tabulation Area) codes in this GeoJSON.
        filtered_features = [
            f for f in us_zip_geojson["features"]
            if f["properties"].get("ZCTA5CE10") == location_input
        ]

        if filtered_features:
            # Create a new GeoJSON object containing only the matched zip code feature(s).
            filtered_geojson = {"type": "FeatureCollection", "features": filtered_features}

            # Attempt to get the centroid (internal point) for centering the map from GeoJSON properties.
            # 'INTPTLAT10' and 'INTPTLON10' provide the latitude and longitude of the internal point.
            if filtered_features[0]["properties"].get("INTPTLAT10") and filtered_features[0]["properties"].get("INTPTLON10"):
                center_lat = float(filtered_features[0]["properties"]["INTPTLAT10"])
                center_lon = float(filtered_features[0]["properties"]["INTPTLON10"])
                zoom_level = 10 # Zoom in for a specific zip code for better detail
            else:
                # Fallback: If internal point properties are missing, calculate a rough centroid.
                # This is a simplified approach and might not be accurate for complex multipolygons.
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

            # Create a choropleth map using Plotly Express.
            # `geojson` provides the boundaries, `locations` links data to features,
            # `featureidkey` specifies how to match `locations` with `geojson` features.
            fig = px.choropleth_mapbox(
                geojson=filtered_geojson,
                locations=[location_input], # The zip code itself acts as the location identifier
                featureidkey="properties.ZCTA5CE10", # Key in GeoJSON properties to match `locations`
                color_discrete_sequence=["blue"], # Color to highlight the selected area
                mapbox_style="open-street-map",
                zoom=zoom_level,
                center={"lat": center_lat, "lon": center_lon},
                opacity=0.5, # Make the highlighted area semi-transparent
                height=600,
                title=f"Area for Zip Code: {location_input}"
            )
            # Add a black border to the highlighted area for better visibility
            fig.update_traces(marker_line_width=2, marker_line_color="black")
        else:
            # If the zip code is not found in the GeoJSON data
            fig = px.scatter_mapbox(
                lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                mapbox_style="open-street-map",
                title=f"Zip Code '{location_input}' not found or no boundary data available."
            )
    else:
        # If the input is not a 5-digit number, assume it's a city name.
        # Use Nominatim to geocode the city name to latitude and longitude.
        try:
            location = geolocator.geocode(location_input, timeout=5) # 5-second timeout for geocoding
            if location:
                center_lat = location.latitude
                center_lon = location.longitude
                zoom_level = 9 # A good zoom level for city views

                # For cities, precise GeoJSON boundaries for all cities are not easily
                # available via a single public URL without an API key.
                # Therefore, we'll center the map and place a prominent marker to indicate the city.
                fig = px.scatter_mapbox(
                    lat=[center_lat],
                    lon=[center_lon],
                    zoom=zoom_level,
                    mapbox_style="open-street-map",
                    height=600,
                    title=f"Location for City: {location.address}",
                    size_max=20, # Max size for markers
                    color_discrete_sequence=["red"], # Color of the marker
                    size=[50] # Arbitrary size to make the marker clearly visible
                )
                # Customize the marker appearance
                fig.update_traces(marker=dict(size=20, opacity=0.7, symbol="circle"))
            else:
                # If the city name cannot be geocoded
                fig = px.scatter_mapbox(
                    lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                    mapbox_style="open-street-map",
                    title=f"City '{location_input}' not found."
                )
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            # Handle errors from the geocoding service (e.g., network issues, service unavailability)
            fig = px.scatter_mapbox(
                lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                mapbox_style="open-street-map",
                title=f"Geocoding service error for '{location_input}': {e}. Please try again."
            )
        except Exception as e:
            # Catch any other unexpected errors during processing
            fig = px.scatter_mapbox(
                lat=[center_lat], lon=[center_lon], zoom=3, height=600,
                mapbox_style="open-street-map",
                title=f"An unexpected error occurred for '{location_input}': {e}"
            )

    # Update layout margins for the generated figure
    fig.update_layout(margin={"r":0,"t":50,"l":0,"b":0})
    return dcc.Graph(figure=fig)

# Pre-load the GeoJSON data when the script starts.
# This ensures the data is available when the first request comes in.
load_zip_geojson()

# To run this Dash app, you would typically use:
if __name__ == "__main__":
    app.run(debug=True)
# In this environment, the `app` object itself is what gets executed.