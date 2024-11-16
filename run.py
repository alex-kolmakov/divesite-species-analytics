import streamlit as st
from google.cloud import bigquery
import pandas as pd
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)

def main():
    st.title("Species Search Application")

    # Input field for search term
    search_term = st.text_input("Search for species description")

    if search_term:
        with st.spinner("Searching for species..."):
            df = get_species(search_term)

        if not df.empty:
            # Display species list as a table
            display_species_table(df)
        else:
            st.write("No matching species found.")

    # Check if a species has been selected to show occurrences
    if 'selected_species' in st.session_state:
        species_name = st.session_state.selected_species
        display_species_occurrences(species_name)

def show_occurrences(species):
    """Function to update the selected species in session state."""
    st.session_state.selected_species = species

def display_species_table(df):
    """Display species list as a table with columns 'Name', 'Image', 'Description'."""
    st.subheader("Search Results")

    if not df.empty:
        # Create a container to hold the table
        table_container = st.container()
        # Create the header
        cols = table_container.columns([2, 2, 4, 2])  # Adjust column widths
        cols[0].write("**Name**")
        cols[1].write("**Image**")
        cols[2].write("**Description**")
        cols[3].write("")

        for idx, row in df.iterrows():
            cols = table_container.columns([2, 2, 4, 2])  # Adjust column widths
            cols[0].write(row['species'])
            cols[1].image(row['Image_URL'], width=100)
            cols[2].write(row['Common_name'])
            cols[3].button(
                "Show Occurrences",
                key=f"occurrences_{idx}",
                on_click=show_occurrences,
                args=(row['species'],)
            )
    else:
        st.write("No matching species found.")

def display_species_occurrences(species):
    """Display the full description, name, and occurrences of the selected species."""
    # Fetch species details again (you can optimize by storing this in session state)
    species_df = get_species_by_name(species)
    if not species_df.empty:
        species_row = species_df.iloc[0]
        st.header(species_row['species'])
        st.image(species_row['Image_URL'])
        st.write(species_row['Common_name'])

        # Fetch and display occurrences
        with st.spinner("Fetching occurrences..."):
            occurrence_df = get_occurrences(species)

        if not occurrence_df.empty:
            st.subheader("Occurrences")
            st.map(occurrence_df)
        else:
            st.write("No occurrences found.")

        # Back button to return to search results
        if st.button("Back to Search Results"):
            del st.session_state.selected_species
    else:
        st.error("Species details not found.")

@st.cache_data
def get_species(search_term):
    """Query BigQuery to get species matching the search term."""
    query = """
        SELECT species, Image_URL, Common_name
        FROM `gbif-412615.marine_data.species`
        WHERE Common_name LIKE @search_term
        LIMIT 10
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("search_term", "STRING", f"%{search_term}%")
        ]
    )
    try:
        query_job = client.query(query, job_config=job_config)
        df = query_job.to_dataframe()
    except Exception as e:
        st.error(f"An error occurred: {e}")
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
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("species", "STRING", species)
        ]
    )
    try:
        query_job = client.query(query, job_config=job_config)
        df = query_job.to_dataframe()
    except Exception as e:
        st.error(f"An error occurred: {e}")
        df = pd.DataFrame()
    return df

@st.cache_data
def get_occurrences(species):
    """Query BigQuery to get occurrences of a species."""
    occurrence_query = """
        SELECT
            ST_Y(geography) AS latitude,
            ST_X(geography) AS longitude
        FROM `gbif-412615.marine_data.occurences`
        WHERE species = @species
    """
    occurrence_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("species", "STRING", species)
        ]
    )
    try:
        occurrence_job = client.query(occurrence_query, job_config=occurrence_job_config)
        occurrence_df = occurrence_job.to_dataframe()
    except Exception as e:
        st.error(f"An error occurred: {e}")
        occurrence_df = pd.DataFrame()
    return occurrence_df

if __name__ == "__main__":
    main()