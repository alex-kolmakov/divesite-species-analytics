import pyspark
import os
from pyspark.sql import functions as F
from datetime import datetime
from pyspark.sql import SparkSession

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


spark = SparkSession.builder \
    .master("spark://spark-master:7077") \
    .appName('OBIS') \
    .config("spark.executor.memory", "1g") \
    .config("spark.driver.memory", "3g") \
    .config("spark.sql.files.maxPartitionBytes", "128m") \
    .getOrCreate()


@transformer
def transform(data, *args, **kwargs):
    df = spark.read.parquet("/home/data/obis.parquet")
    
    obis_columns = [
        "species", "individualCount", "eventDate", "eventTime",
        "year", "month", "day", "decimalLongitude", "decimalLatitude"
    ]
    obis_df = df.select(*obis_columns)

    # Filtering the DataFrame
    filtered_df = obis_df.filter(
        (F.col('species').isNotNull()) &
        (F.col('eventDate').isNotNull()) &
        (F.col('individualCount') > 0)
    )

    obis_df = filtered_df.toPandas()

    return obis_df

@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
