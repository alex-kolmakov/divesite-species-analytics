import dlt
from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.paginators import PageNumberPaginator
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
load_dotenv()


@dlt.source
def padi():

    padi_client = RESTClient(
        base_url="https://travel.padi.com/api/v2",
        paginator=PageNumberPaginator(
            base_page=1,
            total_path="count"
        )
    )

    @dlt.resource(name="map_segments", parallelized=True)
    def map_segments(grid_cell_size=20) -> Tuple[str, Any]:
        for lat in range(-90, 90, grid_cell_size):
            for lon in range(-340, 340, grid_cell_size):
                yield (f"{lat+grid_cell_size},{lon+grid_cell_size}", f"{lat},{lon}")


    @dlt.transformer(parallelized=True)
    def coordinates(segments):

        @dlt.defer
        def _get_coordinates(geo_tuple: Tuple[str, str]) -> Dict[str, Any]:
            response = padi_client.get(
                "/travel/dsl/dive-sites/map/", 
                params={
                    "top_right": geo_tuple[0], 
                    "bottom_left": geo_tuple[1]
                }
            )
            return response.json()

        yield _get_coordinates(segments)

    def custom_response_handler(response, *args, **kwargs):
        if response.status_code == 404:
            pass

    @dlt.resource
    def metadata(parallelized=True):
        for page in padi_client.paginate("/travel/dive-guide/world/all/dive-sites", 
                                         params={"page_size": 1000},
                                         hooks={"response": [custom_response_handler]}):
            yield page

    @dlt.transformer()
    def merged_divesites(data, data2, *args, **kwargs):
        print("Data fetched:", len(data), "records")
        print("Map segments fetched:", len(data2), "segments")
        return data, data2


    return metadata | merged_divesites, map_segments | coordinates | merged_divesites

if __name__ == "__main__":

    pipeline = dlt.pipeline(
        pipeline_name="divesite", 
        destination="duckdb", 
        dataset_name="geo_padi_data",
        progress="log",
        refresh="drop_sources"
    )

    # the pokemon_list resource does not need to be loaded
    load_info = pipeline.run(padi())

    import duckdb
    con = duckdb.connect(database="divesite.duckdb")
    coordinates_df = con.execute("SELECT * FROM geo_padi_data.coordinates").fetch_df()
    print(coordinates_df)
    metadata_df = con.execute("SELECT * FROM geo_padi_data.metadata").fetch_df()
    print(metadata_df)

    merged_df = pd.merge(metadata_df, coordinates_df, on='id', how='inner')
    print(merged_df)
