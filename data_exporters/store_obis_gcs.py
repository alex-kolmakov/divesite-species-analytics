import os
import pyarrow as pa
import pyarrow.parquet as pq
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.google_cloud_storage import GoogleCloudStorage
from pandas import DataFrame
from os import path

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "/home/src/secret.json"

bucket_name = 'marine_data_412615'
project_id = 'gbif-412615'
table_name = "obis_data"

root_path = f"{bucket_name}/{table_name}"

@data_exporter
def export_data_to_google_cloud_storage(obis_filename: str, **kwargs) -> None:

   table = pq.read_table(obis_filename)

   gcs = pa.fs.GcsFileSystem()

   pq.write_to_dataset(
    table,
    root_path,
    partition_cols=["eventDate"],
    filesystem=gcs
   )
