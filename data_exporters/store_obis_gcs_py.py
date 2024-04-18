from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from google.cloud import storage
from os import path, walk
import yaml

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

def upload_directory_to_gcs(bucket_name, directory_path, gcs_path_prefix):
    """
    Uploads a file to Google Cloud Storage.
    """
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    with open(config_path, 'r') as file:
        config_data = yaml.load(file, Loader=yaml.FullLoader)
    client = storage.Client.from_service_account_json(config_data['default']['GOOGLE_SERVICE_ACC_KEY_FILEPATH'])
    bucket = client.bucket(bucket_name)
    
    for dirpath, dirnames, filenames in walk(directory_path):
        for filename in filenames:
            local_file_path = path.join(dirpath, filename)
            relative_path = path.relpath(local_file_path, directory_path)
            gcs_object_name = path.join(gcs_path_prefix, relative_path)
            blob = bucket.blob(gcs_object_name)
            blob.upload_from_filename(local_file_path)
            print(f"Uploaded {local_file_path} to {gcs_object_name}")

@data_exporter
def export_data_to_google_cloud_storage(directory_path: str, **kwargs) -> None:
    """
    Template for exporting data to a Google Cloud Storage bucket.
    """
    bucket_name = 'marine_data_412615'
    gcs_path_prefix = 'obis'
    upload_directory_to_gcs(bucket_name, directory_path, gcs_path_prefix)

