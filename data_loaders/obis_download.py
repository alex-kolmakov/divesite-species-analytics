import requests
import duckdb
from mage_ai.io.file import FileIO
if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

@data_loader
def load_data_from_file(*args, **kwargs):
    #url = "https://obis-datasets.ams3.digitaloceanspaces.com/exports/obis_20231025.parquet"
    url = "https://filesampleshub.com/download/code/parquet/sample3.parquet"
    download_path = "/home/data/obis.parquet"
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    downloaded_size = 0

    with open(download_path, "wb") as f:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            downloaded_size += size
            if downloaded_size % (1024*1024*1024) == 0:
                print(f"Downloading: {downloaded_size * 100 / total_size:.2f}%")

    return download_path

@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
