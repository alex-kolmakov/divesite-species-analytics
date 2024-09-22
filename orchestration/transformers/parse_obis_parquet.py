import pyarrow.parquet as pq
import pyarrow as pa
from tqdm import tqdm

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform(data, *args, **kwargs):
    """
    Efficiently process a large Parquet file by reading it in chunks,
    writing the result to a new Parquet file incrementally, and displaying
    progress using a customizable progress bar.
    """

    # List of columns to be read from the Parquet file
    obis_columns = [
        "species", "individualCount", "eventDate", "eventTime",
        "year", "month", "day", "decimalLongitude", "decimalLatitude"
    ]
    input_filename = f"/home/src/{kwargs.get('DOWNLOADED_FILENAME')}"  # Input file path
    output_filename = 'output_obis.parquet'  # Output file path

    # Get the progress bar step size from kwargs, or default to 1
    progress_step = kwargs.get('progress_step', 100)

    # Open the Parquet file
    parquet_file = pq.ParquetFile(input_filename)

    # Create a Parquet writer for writing output
    parquet_writer = None

    # Initialize tqdm progress bar
    num_row_groups = parquet_file.num_row_groups
    with tqdm(total=num_row_groups, desc="Processing Parquet file", unit="row group", miniters=progress_step) as pbar:
        # Iterate over the Parquet file in row groups (chunks)
        for i in range(num_row_groups):
            # Read each row group (this chunk) as a PyArrow table
            table = parquet_file.read_row_group(i, columns=obis_columns)

            # If the writer has not been initialized, set it up with the first table's schema
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(output_filename, table.schema)

            # Write the current chunk to the output Parquet file
            parquet_writer.write_table(table)

            # Update the progress bar
            pbar.update(1)

    # Close the writer after all chunks are processed
    if parquet_writer:
        parquet_writer.close()

    os.remove(input_filename)
    # Return the output file path as the result
    return output_filename


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
    assert isinstance(output, str), 'Output is not a file path'
    assert output.endswith('.parquet'), 'Output is not a Parquet file'