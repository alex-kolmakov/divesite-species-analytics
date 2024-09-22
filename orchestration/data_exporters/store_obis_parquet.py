import os
from google.cloud import storage
from tqdm import tqdm

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


GC_PROJECT = os.getenv('GOOGLE_PROJECT_NAME', 'marine_data_412615')

@data_exporter
def export_data_to_google_cloud_storage(filename: str, **kwargs) -> None:
    """
    Export data to Google Cloud Storage with chunked uploads for large files.
    Specify your configuration settings in 'io_config.yaml' and include tqdm for adjustable progress.
    """
    # Path to your service account key file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/src/secret.json"

    bucket_name = GC_PROJECT
    object_key = kwargs.get("DATASET_PARQUET_FILENAME")

    # Set chunk size to 5 MB (or customize as needed for your use case)
    chunk_size = 128 * 1024 * 1024

    # Initialize GCS client with chunk size for resumable uploads
    storage_client = storage.Client(project=GC_PROJECT)
    bucket = storage_client.bucket(bucket_name)

    # Create a blob object in GCS where the file will be stored
    blob = bucket.blob(object_key)

    # Get the file size to track progress
    file_size = os.path.getsize(filename)

    # Initialize progress bar with tqdm
    with tqdm(total=file_size, unit='B', unit_scale=True, desc="Uploading to GCS") as pbar:
        # Open the file and manually read it in chunks
        with open(filename, 'rb') as file_data:
            while True:
                # Read the next chunk
                chunk = file_data.read(chunk_size)
                if not chunk:
                    break  # Exit loop if we reach the end of the file

                # Upload the current chunk
                blob.upload_from_string(chunk, content_type='application/octet-stream')

                # Update the progress bar
                pbar.update(len(chunk))

    print(f'File {filename} successfully uploaded to {bucket_name}/{object_key}.')
    return f"{bucket_name}/{object_key}"