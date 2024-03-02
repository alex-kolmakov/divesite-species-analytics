import pandas as pd
import requests
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType
from pyspark.sql.functions import udf
from io import StringIO

# Define Spark session
spark = SparkSession.builder.getOrCreate()

# Define URL
url = "http://example.com/data.csv"

# Download CSV from URL
response = requests.get(url)
assert response.status_code == 200, 'Failed to download data'

# Use pandas to infer schema from first few lines
data = pd.read_csv(StringIO(response.text), nrows=5)
schema = StructType.from_pandas(data)

# Create Spark DataFrame with inferred schema
data = pd.read_csv(StringIO(response.text))
df = spark.createDataFrame(data, schema=schema)

# Partition DataFrame
df = df.repartition(10)

# Define user-defined function
def my_func(x):
    return x * 2  # Replace with your function

udf_my_func = udf(my_func)

# Apply user-defined function
df = df.withColumn('column_name', udf_my_func('column_name'))  # Replace 'column_name' with your column name

# Write DataFrame to Parquet file
df.coalesce(1).write.parquet('output.parquet')