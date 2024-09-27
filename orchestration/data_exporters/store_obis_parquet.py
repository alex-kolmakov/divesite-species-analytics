import os
from google.cloud import storage

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

GC_PROJECT = os.getenv('GOOGLE_PROJECT_NAME', 'marine_data_412615')

@data_exporter
def export_data_to_google_cloud_storage(filename: str, **kwargs) -> None:
    """
    Export data to Google Cloud Storage with chunked uploads for large files.
    Specify your configuration settings in 'io_config.yaml'.
    """
    # Path to your service account key file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/src/secret.json"
    
    bucket_name = GC_PROJECT
    object_key = kwargs.get("DATASET_PARQUET_FILENAME")

    # Set chunk size to 5 MB (or customize as needed for your use case)
    chunk_size = 5 * 1024 * 1024

    # Initialize GCS client with chunk size for resumable uploads
    storage_client = storage.Client(project=GC_PROJECT)
    bucket = storage_client.bucket(bucket_name)

    # Create a blob object in GCS where the file will be stored
    blob = bucket.blob(object_key)

    # Configure blob for resumable upload with specified chunk size
    blob.chunk_size = chunk_size  # Set the chunk size for resumable uploads

    # Start a resumable upload session
    with open(filename, 'rb') as file_data:
        # Upload the file using the `upload_from_file` method for chunked upload
        blob.upload_from_file(file_data, rewind=True)

    print(f'File {filename} successfully uploaded to {bucket_name}/{object_key}.')