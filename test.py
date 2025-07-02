from dash import Dash, dcc, html, Input, Output, callback
import plotly.express as px
import json
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd # Although not directly used for data manipulation, it's a common dependency for geo-related tasks

# Initialize Nominatim geolocator for converting city names to coordinates
geolocator = Nominatim(user_agent="geo-dash-app")
us_zip_geojson = None
# URL for a comprehensive US zip code GeoJSON file (26MB resolution)
ZIP_GEOJSON_URL = "https://raw.githubusercontent.com/ndrezn/zip-code-geojson/master/usa_zip_codes_geo_26m.json"
# Function to load the GeoJSON data from the specified URL.
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
load_zip_geojson()


app = Dash()
app.title = "Boundary Highlighter"
app.layout = html.Div(
    className="min-h-screen bg-gray-100 p-4 font-inter antialiased flex flex-col items-center",
    children=[

    html.H1("Map with Boundary Highlighting"),
    html.Div([
        "Input: ",
        dcc.Input(id='my-input', type='text')
        # dcc.Dropdown(
        #     id='my-input',
        #     options=[
        #         {'label': 'New York City', 'value': 'New York City'},
        #         {'label': 'Montréal', 'value': 'Montréal'},
        #     ],
        #     className="w-1/4"
        # )
    ]),
    html.Button(
        "Show on Map",
        id="submit-button",
        n_clicks=0, 
        className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-md shadow-md transition duration-300 ease-in-out transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
    ),
    dcc.Loading(
        id="loading-map",
        type="circle", # Spinner type
        children=html.Div(id="my-output", className="w-full h-[600px] bg-gray-200 rounded-md overflow-hidden")
    )
    ]
)


@callback(
    Output(component_id='my-output', component_property='children'),
    Input(component_id='submit-button', component_property='n_clicks'),
    Input(component_id='my-input', component_property='value')
)
def update_output_div(n_clicks, input_value):
    if n_clicks == 0 or not input_value:
        # Default map
        return dcc.Graph(
            figure=px.scatter_mapbox(
                lat=[39.8283], lon=[-98.5795], zoom=3, height=600,
                mapbox_style="open-street-map",
                title="Enter a City or Zip Code to explore the map!"
            ).update_layout(margin={"r":0,"t":50,"l":0,"b":0})
        )

    # Make sure the GeoJSON is loaded
    global us_zip_geojson
    if us_zip_geojson is None or not us_zip_geojson["features"]:
        load_zip_geojson()
        if not us_zip_geojson["features"]:
            return html.Div("Error: Could not load ZIP boundary data.", className="text-red-500")

    # Handle ZIP code highlighting
    is_zip_code = input_value.isdigit() and len(input_value) == 5
    if is_zip_code:


    else:
        # If not a zip, you could implement city support later with geopy
        return html.Div("Please enter a 5-digit ZIP code.", className="text-yellow-600")





if __name__ == '__main__':
    app.run(debug=True)
