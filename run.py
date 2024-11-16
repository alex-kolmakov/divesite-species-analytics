import streamlit as st
from google.cloud import bigquery
import pandas as pd
from google.oauth2 import service_account
import validators

# Set up BigQuery client with credentials
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)

def main():
    st.title("Species Search")

    # Input field for search term
    search_term = st.text_input("Name or a known common part of description:")

    if search_term:
        with st.spinner("Searching for species..."):
            df = get_species(search_term)

        if not df.empty:
            # Display species list as a mobile-friendly list
            display_species_list(df)
        else:
            st.write("No matching species found.")

    # Check if a species has been selected to show occurrences
    if 'selected_species' in st.session_state:
        species_name = st.session_state.selected_species
        display_species_occurrences(species_name)

def show_occurrences(species):
    """Function to update the selected species in session state."""
    st.session_state.selected_species = species

def display_species_list(df):
    """Display species list as a mobile-friendly list."""

    if not df.empty:
        for idx, row in df.iterrows():
            with st.container():
                st.write(f"### {row['species']}")
                # Display trimmed Common_name with 'Read more' option
                if pd.notnull(row['Common_name']):
                    common_name = str(row['Common_name'])
                    if len(common_name) > 1000:
                        st.write(common_name[:1000] + "...")
                        if st.button("Read more", key=f"read_more_{idx}"):
                            st.write(common_name)
                    else:
                        st.write(common_name)
                # Check if Image_URL is a valid URL
                if is_valid_image_url(row['Image_URL']):
                    st.image(row['Image_URL'], use_column_width=True)
                # 'Show Occurrences' button
                st.button(
                    "Show Occurrences",
                    key=f"occurrences_{idx}",
                    on_click=show_occurrences,
                    args=(row['species'],)
                )
                st.markdown("---")
    else:
        st.write("No matching species found.")

def display_species_occurrences(species):
    """Display the full description, name, and occurrences of the selected species."""
    # Fetch species details again (you can optimize by storing this in session state)
    species_df = get_species_by_name(species)
    if not species_df.empty:
        species_row = species_df.iloc[0]
        st.header(species_row['species'])
        # Display trimmed Common_name with 'Read more' option
        if pd.notnull(species_row['Common_name']):
            common_name = str(species_row['Common_name'])
            if len(common_name) > 1000:
                st.write(common_name[:1000] + "...")
                if st.button("Read more", key="read_more_full"):
                    st.write(common_name)
            else:
                st.write(common_name)
        # Check if Image_URL is a valid URL
        if is_valid_image_url(species_row['Image_URL']):
            st.image(species_row['Image_URL'])
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

def is_valid_image_url(url):
    """Check if the URL is valid and points to an image."""
    if pd.notnull(url) and url.strip() != '':
        url = url.strip()
        # Check if URL is valid
        if validators.url(url):
            # Optional: Check if URL ends with common image extensions
            if any(url.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg']):
                return True
    return False

@st.cache_data
def get_species(search_term):
    """Query BigQuery to get species matching the search term."""
    query = """
        SELECT species, Image_URL, Common_name
        FROM `gbif-412615.marine_data.species`
        WHERE Common_name LIKE @search_term
        LIMIT 5
    """
    search_term = search_term.lower()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("search_term", "STRING", f"%{search_term}%")
        ]
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
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("species", "STRING", species)
        ]
    )
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
            ST_X(geography) AS longitude
        FROM `gbif-412615.marine_data.occurrences`
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
        st.error(f"An error occurred while fetching occurrences: {e}")
        occurrence_df = pd.DataFrame()
    return occurrence_df

if __name__ == "__main__":
    main()