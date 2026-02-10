import os
import tempfile
import zipfile

import duckdb

if "transformer" not in globals():
    from mage_ai.data_preparation.decorators import transformer
if "test" not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform(data, *args, **kwargs):
    """
    Extracts a zip file containing partitioned Parquet data,
    processes it using DuckDB to select specific columns with low memory usage,
    and writes the result to a new single Parquet file.

    Optimization Notes:
    - DuckDB's `read_parquet` with `hive_partitioning=1` is generally memory-efficient
      as it can process partitions incrementally and leverages projection/predicate pushdown.
    - The `COPY (SELECT ... FROM read_parquet(...)) TO ...` pattern is designed for
      efficient, potentially out-of-core (disk-spilling) ETL operations, minimizing RAM.
    - Extracting the zip is necessary for DuckDB to see the file structure, but processing
      is done in a streaming fashion by DuckDB where possible.
    - Explicit memory limits can be set via PRAGMA if needed, but DuckDB's defaults
      are often effective.
    """
    input_zip_filename = kwargs.get("DOWNLOADED_FILENAME")  # Input zip file path
    output_filename = "output_obis.parquet"  # Output file path

    # List of columns to be selected
    obis_columns = [
        "species",
        "individualCount",
        "eventDate",
        "eventTime",
        "year",
        "month",
        "day",
        "decimalLongitude",
        "decimalLatitude",
    ]
    # Ensure columns with spaces/special chars are quoted for SQL
    columns_sql = ", ".join([f'"{col}"' for col in obis_columns])

    # Create a temporary directory to extract files
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Extracting {input_zip_filename} to {temp_dir}...")
        try:
            with zipfile.ZipFile(input_zip_filename, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            print("Extraction complete.")
        except zipfile.BadZipFile:
            print(f"Error: {input_zip_filename} is not a valid zip file or is corrupted.")
            raise
        except Exception as e:
            print(f"An error occurred during zip extraction: {e}")
            raise

        # Check if the zip file was empty or extraction failed
        extracted_items = os.listdir(temp_dir)
        if not extracted_items:
            raise ValueError("Zip file appears to be empty after extraction.")

        parquet_base_path = os.path.join(temp_dir, "occurrence")  # Default assumption: data is at the root

        print(f"Determined Parquet base path for reading: {parquet_base_path}")

        # Use DuckDB to read the partitioned Parquet files and write to a new file
        # Using '**/*.parquet' pattern for robust discovery within the base path
        # Ensure using forward slashes for DuckDB glob patterns
        read_path_pattern = os.path.join(parquet_base_path, "**", "*.parquet").replace("\\", "/")
        print(f"Reading Parquet files using pattern: {read_path_pattern}")
        print(f"Writing selected columns to: {output_filename}")

        # Connect to an in-memory database (can spill to disk if needed)
        con = duckdb.connect()
        # Optional: Set a memory limit (e.g., '4GB') if default behavior is insufficient
        con.sql("PRAGMA memory_limit = '2GB';")
        print("Set DuckDB memory limit to 2GB.")

        # Construct and execute the COPY statement
        # hive_partitioning=1 enables automatic partition detection and processing.
        # This is generally memory-efficient for large datasets.
        copy_query = f"""
        COPY (
            SELECT {columns_sql}
            FROM read_parquet('{read_path_pattern}', hive_partitioning=1)
        ) TO '{output_filename}' (FORMAT PARQUET, CODEC 'ZSTD');
        """
        # CODEC 'ZSTD' offers good compression ratio and speed. Default is SNAPPY.

        print("Executing DuckDB query...")
        con.sql(copy_query)
        print("DuckDB processing complete.")

    # Clean up the downloaded zip file *after* successful processing and temp dir closure
    print(f"Removing input zip file: {input_zip_filename}")
    # try:
    #     os.remove(input_zip_filename)
    # except OSError as e:
    #     print(f"Warning: Could not remove input zip file {input_zip_filename}: {e}")

    # Return the output file path for downstream tasks
    return output_filename


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, "The output is undefined"
    assert isinstance(output, str), "Output is not a file path string"
    assert output.endswith(".parquet"), "Output file is not a Parquet file"
    assert os.path.exists(output), f"Output file {output} does not exist"
    # Basic check: Ensure the output file is not empty
    assert os.path.getsize(output) > 0, f"Output file {output} is empty"
    print(f"Output file {output} exists and is not empty.")
    # Optional: Add more specific checks, e.g., read schema or row count
    try:
        con = duckdb.connect()
        row_count = con.sql(f"SELECT COUNT(*) FROM read_parquet('{output}')").fetchone()[0]
        print(f"Output file contains {row_count} rows.")
        con.close()
        assert row_count > 0, "Output parquet file has 0 rows."
    except Exception as e:
        print(f"Could not perform detailed check on output parquet file: {e}")
