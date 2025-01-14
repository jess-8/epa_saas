###############
# Run the app.
###############
import streamlit as st
import datetime

import pydeck as pdk

from handler import page_description, initiate_map, initiate_form, load_data
from visualizer import visualizer
from logger import logger


def main():
    # Variables
    income_path = "https://raw.githubusercontent.com/jess-8/epa_saas/refs/heads/main/average_income_by_county.csv"
    pfas_cols = ["Chemical Abbreviation", "Longitude", "Latitude", "Date", "Public Water System Name", "Site Name", "Value"]

    # Visuals
    page_description()
    logger.info("Created header and caption.")

    # Initializes the blank map
    if 'df' not in st.session_state:
        view_state = initiate_map()
        logger.info("Created initial map.")
        st.session_state.df = st.pydeck_chart(
                                    pdk.Deck(
                                        initial_view_state=view_state,
                                        map_style="light"
                                        )
                                    )

    # User inputs
    pfas_path, chem, year, month = initiate_form()
    date = datetime.date(year, month, 1).strftime("%Y-%m-%d") 
    try:
        pfas_df = load_data(pfas_path, False, pfas_cols)
        choropleth_df = load_data(income_path)
    except Exception as e:
        logger.debug(f"Failed to load data correctly {e}")

    # Call visualizer
    visualizer(pfas_df, choropleth_df, date, chem)

try:
    main()
except TypeError:
    pass
except Exception as e:
    logger.debug(f"Visualization failed to run. See error: {e}")





