# General libraries
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
import branca

# Visualization libraries
import streamlit as st
import streamlit.components.v1 as components
import datetime
import calendar
import pydeck as pdk
from shapely.geometry import Point
from shapely.geometry import Polygon, MultiPolygon

demog_var_name = "Average_Household_Income"
day = 1 # Placeholder for entire month; DO NOT CHANGE

@st.cache_data()
def load_data(path, geojson_data = False, columns=None):
    if columns:
        if not geojson_data:
            return pd.read_csv(path, usecols=columns)
        return gpd.read_file(path, columns = columns)
    if geojson_data:
        return gpd.read_file(path)
    return pd.read_csv(path)

def initiate_map():
    """Initial blank map."""
    view_state = pdk.ViewState(
        longitude=-121.5,
        latitude=37.5,
        zoom=6,
        pitch=60,
        )
    return view_state
    
def initiate_form():
    """Creates the user form to submit."""
    if "visibility" not in st.session_state:
        st.session_state.visibility = "visible"
        st.session_state.disabled = False

    if 'form_data' not in st.session_state:
        st.session_state.form_data = {
            'pfas_path_input': '',
            'chem': '',
            'report_year': '',
            'report_month': '',
            'submitted': False
        }

    with st.sidebar:
        with st.form("My form"):
            st.write("Requirements")
            
            # User pfas dataset path input
            pfas_path_input = st.text_input(
                "Enter local path to Geotracker PFAS File (CSV format).",
                label_visibility=st.session_state.visibility,
                disabled=st.session_state.disabled
            )

            # User chemical input
            chem = st.selectbox(
                "What chemical would you like to select?",
                ("HFPO-DA", "PFHxS", "PFNA", "PFOA", "PFOS"),
                index=None,
                placeholder="Select chemical abbreviation..",
            )

            # User date input
            with st.expander('Select desired year and month.'):
                this_month = datetime.date.today().month
                min_year, max_year = "2018", str(datetime.date.today().year) # 2018 is hard coded. Max year is current year (not dataset year).
                min_date_obj = datetime.datetime.strptime(min_year, "%Y").year
                max_date_obj = datetime.datetime.strptime(max_year, "%Y").year

                report_year = st.selectbox('', range(max_date_obj, min_date_obj, -1))
                month_abbr = calendar.month_abbr[1:]
                report_month_str = st.radio('', month_abbr, index=this_month - 1, horizontal=True)
                report_month = month_abbr.index(report_month_str) + 1

            # Submit button
            submitted = st.form_submit_button(label = "Submit")

            # Make sure all fields filled out
            if submitted:
                validations = [validate_file_field(pfas_path_input),
                                validate_chem_field(chem),
                                validate_month_field(report_month),
                                validate_year_field(report_year),
                               ]
                # If all fields filled out, pass in variables to create final vis.
                if all(v[0] for v in validations):
                    st.success("All fields filled out!")
                    # Update session state
                    st.session_state.form_data.update({
                        'pfas_path_input': pfas_path_input,
                        'chem': chem,
                        'report_year': report_year,
                        'report_month': report_month,
                        'submitted': True
                    })
                    return pfas_path_input,chem, report_year, report_month

                else:
                    # Show all validation errors
                    for valid, message in validations:
                        if not valid:
                            st.error(message)

def validate_file_field(pfas_path_input):
    """Validate pfas file field filled out."""
    if not pfas_path_input:
        return False, "Please enter a file path for the PFAS dataset."
    return True, ""

def validate_chem_field(chem):
    """Validate chemical field selected."""
    if not chem:
        return False, "Please select a chemical."
    return True, ""

def validate_month_field(report_month):
    """Validate month field selected."""
    if not report_month:
        return False, "Please select a month."
    return True, ""

def validate_year_field(report_year):
    """Validate year field selected."""
    if not report_year:
        return False, "Please select a year."
    return True, ""

def clean_data(pfas_df, choropleth_df, date, chem):
    """Clean geotracker data and join with average household income data."""
    pfxx_df = pfas_df[pfas_df['Chemical Abbreviation'] == chem]
    pfxx_df = pfxx_df.reset_index(drop=True)

    ## Geospatial Data EDA
    geojson_counties_url = "https://gis-calema.opendata.arcgis.com/datasets/59d92c1bf84a438d83f78465dce02c61_0.geojson?outSR=%7B%22latestWkid%22%3A3857%2C%22wkid%22%3A102100%7D"
    gdf_counties = load_data(geojson_counties_url, True, ['CountyName','geometry'])

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

    ## Visualization
    def polygon_to_coordinates(geometry):
        if geometry.geom_type == "Polygon":
            return [list(geometry.exterior.coords)]
        elif geometry.geom_type == "MultiPolygon":
            return [list(p.exterior.coords) for p in geometry.geoms]
        else:
            raise ValueError("Geometry must be Polygon or MultiPolygon")
        
    # Map values to colors using the branca colormap
    def map_color(value):
        hex_color = color_scale(value)
        rgb = tuple(int(hex_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        return [rgb[0], rgb[1], rgb[2], 150]  # Alpha = 150

    mean_demog_date["coordinates"] = mean_demog_date["geometry"].apply(polygon_to_coordinates)

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
    st.markdown(legend_html, unsafe_allow_html=True)
    components.html(deck.to_html(as_string=True), height=820)


def main():
    st.header("PFAS Levels and Social Analysis")
    st.caption("An overview into average household income and PFAS chemical levels recorded in California.")

    # Initializes the blank map
    if 'df' not in st.session_state:
        view_state = initiate_map()
        st.session_state.df = st.pydeck_chart(
                            pdk.Deck(
                                initial_view_state=view_state,
                                map_style="light"
                                )
                            )

    pfas_path, chem, year, month = initiate_form()
    income_path = "https://raw.githubusercontent.com/jess-8/epa_saas/refs/heads/main/average_income_by_county.csv"
    date = datetime.date(year, month, day).strftime("%Y-%m-%d") 
    pfas_cols = ["Chemical Abbreviation", "Longitude", "Latitude", "Date", "Public Water System Name", "Site Name", "Value"]
    pfas_df = load_data(pfas_path, False, pfas_cols)
    choropleth_df = load_data(income_path)

    # Call visualizer
    visualizer(pfas_df, choropleth_df, date, chem)

try:
    main()
except TypeError:
    pass





