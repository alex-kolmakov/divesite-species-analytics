import requests
import duckdb
from mage_ai.io.file import FileIO
if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


def split_parquet_with_duckdb(input_file, columns, output_folder, chunk_size):
    conn = duckdb.connect("obis.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT {', '.join(columns)} FROM read_parquet('{input_file}')")

    i = 0
    while True:
        df = cursor.fetch_df_chunk(chunk_size)
        if df.empty:
            break
        output_file = f"{output_folder}/chunk_{i+1}.parquet"
        df.to_parquet(output_file, index=False)
        i += 1

    conn.close()


@transformer
def transform(data, *args, **kwargs):
    """
    Process and store data in chunks from a Parquet file, saving each chunk to a separate Parquet file.

    Args:
        data: The output from the upstream parent block
        args: The output from any additional upstream blocks (if applicable)

    Returns:
        List of filenames of the saved Parquet files.
    """
    obis_columns = ["species", "individualCount", "eventDate", "country", "decimalLongitude", "decimalLatitude"]
    input_filename = "obis.parquet"

    split_parquet_with_duckdb(input_filename, obis_columns, 'output_chunks', 50000)

@test
def test_output(output, *args) -> None:
    """
    Ensure that the output is a list of filenames and that the list is not empty.
    """
    assert isinstance(output, list), 'Output should be a list of filenames'
    assert len(output) > 0, 'The list of filenames should not be empty'
    for filename in output:
        assert os.path.exists(filename), f'File {filename} does not exist'
        assert filename.endswith('.parquet'), 'All files should be Parquet files'