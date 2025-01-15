#####################################
# Initiate UI and handle user inputs.
#####################################

import pandas as pd
import geopandas as gpd
import datetime
import calendar

import streamlit as st
import pydeck as pdk

from logger import logger

@st.cache_data()
def load_data(path, geojson_data = False, columns=None):
    """Load in data from csv or geopandas files."""
    if columns:
        if not geojson_data:
            return pd.read_csv(path, usecols=columns)
        return gpd.read_file(path, columns = columns)
    if geojson_data:
        return gpd.read_file(path)
    return pd.read_csv(path)

def page_description():
    """Title, subheading, and other visual features."""
    st.header("PFAS Levels and Social Analysis")
    st.caption("An overview into average household income and PFAS chemical levels recorded in California.")

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
            pfas_path_input = st.file_uploader("Upload Geotracker PFAS File (CSV format)", type = "csv")

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
                    logger.info("All fields filled out successfully.")
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
