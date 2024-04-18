import pyspark
import os
from pyspark.sql import SparkSession

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


spark = SparkSession.builder \
    .master("spark://spark-master:7077") \
    .appName('OBIS') \
    .config("spark.executor.memory", "1g") \
    .config("spark.driver.memory", "4g") \
    .config("spark.sql.files.maxPartitionBytes", "128m") \
    .getOrCreate()


# @transformer
# def transform(data, *args, **kwargs):
#     print(os.path.exists("/home/data/obis.parquet"))
#     df = spark.read.parquet("/home/data/obis.parquet")
#     #obis_columns = ["marine", "class", "genus", "species", "variety", "individualCount", "eventDate", "eventTime", "year", "month", "day", "country", "locality", "decimalLongitude", "decimalLatitude"]

#     # obis_df = df.select(obis_columns)
#     obis_df = df.repartition(10)
#     obis_df.write.mode('overwrite').parquet("/home/data/obis_modified.parquet")
#     return "/home/data/obis_modified.parquet"



@transformer
def transform(data, *args, **kwargs):
    target_directory = "/home/data/obis_modified.parquet"
    print(os.path.exists("/home/data/obis.parquet"))
    df = spark.read.parquet("/home/data/obis.parquet")
    #obis_columns = ["marine", "class", "genus", "species", "variety", "individualCount", "eventDate", "eventTime", "year", "month", "day", "country", "locality", "decimalLongitude", "decimalLatitude"]
    #obis_df = df.select(obis_columns)
    obis_df = df.repartition(5)
    obis_df.write.mode('overwrite').parquet(target_directory)
    print(os.path.exists(target_directory))
    
    # df = spark.read.parquet(target_directory)
    return target_directory

@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
