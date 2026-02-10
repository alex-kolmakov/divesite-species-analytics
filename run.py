import pandas as pd
import pydeck as pdk
import streamlit as st
import validators
from google.cloud import bigquery
from google.oauth2 import service_account

# Initialize BigQuery client
credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])
client = bigquery.Client(credentials=credentials)
st.set_page_config(page_title="Marine species")


def main():
    st.title("Species search")

    # Initialize session state variables
    if "show_species_list" not in st.session_state:
        st.session_state.show_species_list = False
    if "selected_species" not in st.session_state:
        st.session_state.selected_species = None

    # Use st.form to align text input and button
    with st.form("search_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input(
                "",
                value=st.session_state.get("search_term", ""),
                placeholder="Name or description",
                label_visibility="collapsed",
                key="search_term_input",
            )
        with col2:
            search_button = st.form_submit_button("Search", use_container_width=True)

        if search_button and search_term:
            st.session_state.search_term = search_term
            st.session_state.show_species_list = True
            st.session_state.selected_species = None
            st.rerun()
        elif search_button and not search_term:
            st.warning("Please enter a search term.")

    # Display species occurrences if selected_species is not None
    if st.session_state.selected_species:
        display_species_occurrences(st.session_state.selected_species)
    elif st.session_state.show_species_list:
        if "search_term" in st.session_state:
            with st.spinner("Searching for species..."):
                df = get_species(st.session_state.search_term)
            if not df.empty:
                # Display species list as a mobile-friendly list
                display_species_list(df)
            else:
                st.write("No matching species found.")


def show_occurrences(species):
    """Function to update the selected species in session state."""
    st.session_state.selected_species = species
    st.session_state.show_species_list = False


COLOR_BREWER_BLUE_SCALE = [
    [240, 249, 232],
    [204, 235, 197],
    [168, 221, 181],
    [123, 204, 196],
    [67, 162, 202],
    [8, 104, 172],
]


def display_species_list(df):
    """Display species list as a mobile-friendly list."""
    if not df.empty:
        for idx, row in df.iterrows():
            with st.container():
                st.write(f"### {row['species']}")
                # Display trimmed Common_name with 'Read more' option
                if pd.notnull(row["Common_name"]):
                    common_name = str(row["Common_name"])
                    if len(common_name) > 1000:
                        st.write(common_name[:1000] + "...")
                        if st.button("Read more", key=f"read_more_{idx}"):
                            st.write(common_name)
                    else:
                        st.write(common_name)
                # Check if Image_URL is a valid URL
                if is_valid_image_url(row["Image_URL"]):
                    st.image(row["Image_URL"], use_column_width=True)
                # 'Show Occurrences' button
                st.button(
                    "Show Occurrences", key=f"occurrences_{idx}", on_click=show_occurrences, args=(row["species"],)
                )
    else:
        st.write("No matching species found.")


def display_species_occurrences(species):
    """Display the full description, name, and occurrences of the selected species."""
    species_df = get_species_by_name(species)
    if not species_df.empty:
        species_row = species_df.iloc[0]
        st.header(species_row["species"])
        # Display trimmed Common_name with 'Read more' option
        if pd.notnull(species_row["Common_name"]):
            common_name = str(species_row["Common_name"])
            if len(common_name) > 1000:
                st.write(common_name[:1000] + "...")
                if st.button("Read more", key="read_more_full"):
                    st.write(common_name)
            else:
                st.write(common_name)
        # Check if Image_URL is a valid URL
        if is_valid_image_url(species_row["Image_URL"]):
            st.image(species_row["Image_URL"])
        # Fetch and display occurrences
        with st.spinner("Fetching occurrences..."):
            occurrence_df = get_occurrences(species)
        if not occurrence_df.empty:
            st.subheader("Occurrences")

            # Define a Pydeck HeatmapLayer with tooltips
            heatmap_layer = pdk.Layer(
                "HeatmapLayer",
                data=occurrence_df,
                get_position=["longitude", "latitude"],
                get_weight="individual_count",
                color_range=COLOR_BREWER_BLUE_SCALE,
                opacity=0.9,
                threshold=0.2,
            )

            # Define the Pydeck view
            view_state = pdk.ViewState(
                latitude=occurrence_df["latitude"].mean(),
                longitude=occurrence_df["longitude"].mean(),
                zoom=3,
                pitch=40.5,
            )

            # Render the map with HeatmapLayer
            st.pydeck_chart(pdk.Deck(layers=[heatmap_layer], initial_view_state=view_state))
        else:
            st.write("No occurrences found.")

        # Back button to return to search results
        if st.button("Back to Search Results"):
            st.session_state.selected_species = None
            st.session_state.show_species_list = True
            st.rerun()
    else:
        st.error("Species details not found.")


def is_valid_image_url(url):
    """Check if the URL is valid and points to an image."""
    if pd.notnull(url) and url.strip() != "":
        url = url.strip()
        # Check if URL is valid
        if validators.url(url):
            # Optional: Check if URL ends with common image extensions
            if any(url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".svg"]):
                return True
    return False


@st.cache_data
def get_species(search_term):
    """Query BigQuery to get species matching the search term."""
    query = """
        SELECT species, Image_URL, Common_name
        FROM `gbif-412615.marine_data.species`
        WHERE SEARCH(Common_name, @search_term)
        LIMIT 20
    """
    search_term = search_term.lower()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("search_term", "STRING", f"{search_term}")]
    )
    try:
        query_job = client.query(query, job_config=job_config)
        df = query_job.to_dataframe()
    except Exception as e:
        st.error(f"An error occurred while fetching species: {e}")
        df = pd.DataFrame()
    return df


@st.cache_data
def get_species_by_name(species):
    """Query BigQuery to get species details by name."""
    query = """
        SELECT species, Image_URL, Common_name
        FROM `gbif-412615.marine_data.species`
        WHERE species = @species
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("species", "STRING", species)])
    try:
        query_job = client.query(query, job_config=job_config)
        df = query_job.to_dataframe()
    except Exception as e:
        st.error(f"An error occurred while fetching species details: {e}")
        df = pd.DataFrame()
    return df


@st.cache_data
def get_occurrences(species):
    """Query BigQuery to get occurrences of a species."""
    occurrence_query = """
        SELECT
            ST_Y(geography) AS latitude,
            ST_X(geography) AS longitude,
            individual_count
        FROM `gbif-412615.marine_data.clustered_occurrences`
        WHERE species = @species
    """
    occurrence_job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("species", "STRING", species)]
    )
    try:
        occurrence_job = client.query(occurrence_query, job_config=occurrence_job_config)
        occurrence_df = occurrence_job.to_dataframe()
    except Exception as e:
        st.error(f"An error occurred while fetching occurrences: {e}")
        occurrence_df = pd.DataFrame()
    return occurrence_df


if __name__ == "__main__":
    main()
