from dash import Dash, html, dcc
from urllib.request import urlopen
import json
import pandas as pd
import plotly.express as px
import numpy as np

# Load NYC zip code GeoJSON
with urlopen('https://raw.githubusercontent.com/OpenDataDE/State-zip-code-GeoJSON/master/ny_new_york_zip_codes_geo.min.json') as response:
    zipcodes = json.load(response)

# Extract ZIP codes from GeoJSON
zip_list = [feature["properties"]["ZCTA5CE10"] for feature in zipcodes["features"]]

# Create mock DataFrame with ZIP codes and random "Cluster" values
zipcode_data = pd.DataFrame({
    "ZIP_Code": zip_list,
    "Cluster": np.random.randint(1, 6, size=len(zip_list))  # Clusters 1 through 5
})

# Plotly choropleth figure
fig = px.choropleth(
    zipcode_data,
    geojson=zipcodes,
    locations='ZIP_Code',
    color='Cluster',
    featureidkey="properties.ZCTA5CE10",
    color_continuous_scale="Viridis",
    range_color=(1, 5),
    scope="usa",
    labels={'Cluster': 'Cluster Category'}
)

fig.update_layout(
    mapbox_style="carto-positron",
    mapbox_zoom=9,
    mapbox_center={"lat": 40.7128, "lon": -74.0060},
    margin={"r": 0, "t": 0, "l": 0, "b": 0}
)

# Dash app layout
app = Dash()
app.layout = html.Div([
    html.H1("NYC Zip Code Clusters", style={'textAlign': 'center'}),
    dcc.Graph(figure=fig)
])

if __name__ == '__main__':
    app.run(debug=True)
