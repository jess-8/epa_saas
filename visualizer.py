#############################################
# Clean data, and create the interactive map.
#############################################

import pandas as pd
import geopandas as gpd

import branca
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components

from handler import load_data
from logger import logger
import sys

def clean_data(pfas_df: pd.DataFrame, choropleth_df: pd.DataFrame, date: str, chem: str) -> pd.DataFrame:
    """
    Clean and create geotracker and income dataset.
    """
    date_check = pd.to_datetime(date)
    received_date = (date_check.year, date_check.month)
    all_dates = pd.to_datetime(pfas_df['Date'])
    all_combos = list(all_dates.apply(lambda x: (x.year, x.month)).unique())

    if received_date not in all_combos:
        st.text("This combination of year and month is not in the Geotracker data. Please enter valid combination.")
        logger.info("User has entered invalid combination of year and month.")
        sys.exit()

    pfxx_df = pfas_df[pfas_df['Chemical Abbreviation'] == chem]
    pfxx_df = pfxx_df.reset_index(drop=True)

    ## Geospatial Data EDA
    geojson_counties_url = "https://gis-calema.opendata.arcgis.com/datasets/59d92c1bf84a438d83f78465dce02c61_0.geojson?outSR=%7B%22latestWkid%22%3A3857%2C%22wkid%22%3A102100%7D"
    try:
        gdf_counties = load_data(geojson_counties_url, True, ['CountyName','geometry'])
    except Exception as e:
        logger.debug(f"Failed to load in geojson data for counties: {e}")

    # Ensure 'Longitude' is numeric for spatial operations
    pfxx_df['Longitude'] = pd.to_numeric(pfxx_df['Longitude'], errors='coerce')
    pfxx_df['Latitude'] = pd.to_numeric(pfxx_df['Latitude'], errors='coerce')

    # Create a geometry column for the points in pfxx_df
    pfxx_df = gpd.GeoDataFrame(
        pfxx_df, geometry=gpd.points_from_xy(pfxx_df.Longitude, pfxx_df.Latitude), crs="EPSG:4326"
    )

    # Ensure both GeoDataFrames use the same CRS
    gdf_counties = gdf_counties.to_crs("EPSG:4326")

    pfxx_df = gpd.sjoin(pfxx_df, gdf_counties, how="left", predicate="within")

    pfxx_df['County'] = pfxx_df['CountyName']
    pfxx_df = pfxx_df.reset_index(drop=True)
    pfxx_df['Date'] = pd.to_datetime(pfxx_df['Date'])
    pfxx_df['UniqueID'] = pfxx_df['Public Water System Name'] + '_' + pfxx_df['Site Name']
    pfxx_cleaner = pfxx_df[['UniqueID','Value','Date']]

    min_date, max_date = pfxx_df['Date'].min(), pfxx_df['Date'].max()

    # Convert to monthly data
    pfxx_monthly = (
      pfxx_cleaner.groupby([pfxx_cleaner['UniqueID'], pfxx_cleaner['Date'].dt.to_period('M')])['Value']
      .mean()
      .reset_index()
    )

    pfxx_pivot = pfxx_monthly.pivot(index='Date', columns='UniqueID', values='Value')
    pfxx_pivot.index = pfxx_pivot.index.to_timestamp()

    full_date_range = pd.date_range(start=min_date, end=max_date, freq="MS")
    pfxx_pivot = pfxx_pivot.reindex(full_date_range)
    pfxx_pivot.index.name = "Date"

    pfxx_pivot = pfxx_pivot.reset_index()
    pfxx_pivot_ffill = pfxx_pivot.fillna(method='ffill')
    pfxx_pivot_filled = pfxx_pivot_ffill.fillna(method='bfill')
    pfxx_filled = pfxx_pivot_filled.melt(id_vars=['Date'], var_name='UniqueID', value_name='Value')

    # Map each row to corresponding county
    county_mapping = (
        pfxx_df.groupby('County')['UniqueID']
        .apply(list)
        .to_dict()
    )

    uniqueid_to_county = {
        uniqueid: county
        for county, uniqueids in county_mapping.items()
        for uniqueid in uniqueids
    }

    pfxx_filled['County'] = pfxx_filled['UniqueID'].map(uniqueid_to_county)
    pfxx_grouped_cty = pfxx_filled.groupby(['County', 'Date']).agg({'Value': 'mean'})
    pfxx_grouped_clean = pfxx_grouped_cty.sort_values(by=['County', 'Date'],ascending=True)
    pfxx_grouped_clean = pfxx_grouped_clean.reset_index()

    pfxx_geom = pfxx_grouped_clean.merge(gdf_counties, left_on='County', right_on='CountyName', how='left')\
                                    .drop(columns=['CountyName'])
    mean_demog = pd.merge(pfxx_geom, choropleth_df, on='County', how='left')
    
    mean_demog_date = mean_demog[mean_demog['Date'] == date].reset_index(drop = True)
    if mean_demog_date.empty:
        st.text("This combination of chemical, year, and month is not in the Geotracker data. Please enter valid combination.")
        logger.info("User has entered invalid combination of chemical, year, and month.")
        sys.exit()

    mean_demog_date = gpd.GeoDataFrame(mean_demog_date, geometry="geometry")
    mean_demog_date['Centroid_Lat'] = mean_demog_date.geometry.centroid.y
    mean_demog_date['Centroid_Lon'] = mean_demog_date.geometry.centroid.x

    # Ensure the geometry column is properly formatted
    mean_demog_date = gpd.GeoDataFrame(mean_demog_date, geometry="geometry")

    mean_demog_date["Value"] = round(mean_demog_date["Value"], 2)
    mean_demog_date["Average_Household_Income"] = round(mean_demog_date["Average_Household_Income"], 2)
    return mean_demog_date

def visualizer(pfas_df, choropleth_df, date, chem):
    """
    Create the interactive income and chemical concentration on county visualization.
    """
    mean_demog_date = clean_data(pfas_df, choropleth_df, date, chem)
    demog_var_name = "Average_Household_Income"

    ## Visualization
    def polygon_to_coordinates(geometry):
        """Convert polygon to coordinates."""
        if geometry.geom_type == "Polygon":
            return [list(geometry.exterior.coords)]
        elif geometry.geom_type == "MultiPolygon":
            return [list(p.exterior.coords) for p in geometry.geoms]
        else:
            raise ValueError("Geometry must be Polygon or MultiPolygon")
        
    def map_color(value):
        """Map values to colors using previously created colormap."""
        hex_color = color_scale(value)
        rgb = tuple(int(hex_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        return [rgb[0], rgb[1], rgb[2], 150]  # Alpha = 150

    try:
        mean_demog_date["coordinates"] = mean_demog_date["geometry"].apply(polygon_to_coordinates)
    except Exception as e:
        logger.debug(f"Failed to convert polygons to coordinates: {e}")

    color_scale = branca.colormap.LinearColormap(colors=["#FF0000", "#FFA500", "#FFFF00", "#ADFF2F", "#008000"], vmin=mean_demog_date[demog_var_name].min(), vmax=mean_demog_date[demog_var_name].max() )

    mean_demog_date["color"] = mean_demog_date[demog_var_name].apply(map_color)

    # Create the PyDeck PolygonLayer
    polygon_layer = pdk.Layer(
        "PolygonLayer",
        mean_demog_date,
        get_polygon="coordinates",
        get_fill_color="color",
        auto_highlight=True,
        pickable=True
    )

    # Create the PyDeck ColumnLayer
    column_layer = pdk.Layer(
        'ColumnLayer',
        data=mean_demog_date,
        get_position=['Centroid_Lon', 'Centroid_Lat'],
        get_elevation='Value',
        elevation_scale=10000,
        radius=10000,
        get_fill_color=[255, 0, 0, 180],
        pickable=True,
        auto_highlight=True,
    )

    # Define the view state
    view_state = pdk.ViewState(
        longitude=-121.5,
        latitude=37.5,
        zoom=6,
        pitch=60,
    )

    tooltip={"text": f"County: {{County}}\nAverage Household Income: ${{{demog_var_name}}}\
             \nConcentration Reading of {chem}: {{Value}} ng/L \nDate: {date}"}

    deck = pdk.Deck(
            layers=[polygon_layer, column_layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style="light"
            )

    # Create legend
    div_beg = '<div style="display: inline-block; margin-bottom: 20px; margin-left: 10px;"><h6 style="margin:0; padding:0; font-size: 12px; font-family: Arial;">Color Legend (Average Household Income - Dollars)</h6>'
    div_end = '</div>'
    legend_html = color_scale._repr_html_().replace("font:Arial; fill:black", "font:Arial; fill:white")
    legend_html = "".join([div_beg, legend_html])
    legend_html = "".join([legend_html, div_end])

    # Create final Pydeck visualization in Streamlit.
    try:
        st.markdown(legend_html, unsafe_allow_html=True)
    except Exception as e:
        logger.debug(f"Failed to create the legend: {e}")
    
    components.html(deck.to_html(as_string=True), height=820)
