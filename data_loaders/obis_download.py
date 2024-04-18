import requests
from zlib import crc32

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

@data_loader
def load_data_from_file(*args, **kwargs):
    url = "https://obis-datasets.ams3.digitaloceanspaces.com/exports/obis_20231025.parquet"
    download_path = "/home/data/obis.parquet"
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    downloaded_size = 0

    with open(download_path, "wb") as f:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            downloaded_size += size
            if downloaded_size % (1024*1024*512) == 0:
                print(f"Downloading: {downloaded_size * 100 / total_size:.2f}%")
    print(compute_file_crc(download_path))

    return download_path


def compute_file_crc(filename):
    """
    Compute the CRC32 of a file.

    Args:
    filename (str): Path to the file.

    Returns:
    int: The CRC32 checksum of the file.
    """
    prev_crc = 0  # Initial CRC value
    try:
        with open(filename, 'rb') as f:
            while True:
                data = f.read(1024 * 1024)  # Read in chunks of 1 MB
                if not data:
                    break
                prev_crc = crc32(data, prev_crc)
        return prev_crc
    except IOError as e:
        print(f"Error opening or reading the file: {e}")
        return None


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """

    assert output is not None, 'The output is undefined'

    crc = compute_file_crc(output)
    print(crc)
    assert crc == 1007414139, 'The file is corrupted'
