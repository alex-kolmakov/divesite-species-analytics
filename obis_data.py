#!/usr/bin/env python
# coding: utf-8

# In[23]:


import pandas as pd
import pyspark
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .master("local[*]") \
    .appName('test') \
    .config("spark.executor.memory", "10g") \
    .config("spark.driver.memory", "10g") \
    .config("spark.memory.offHeap.enabled", "true") \
    .config("spark.memory.offHeap.size","16g") \
    .getOrCreate()

pd.set_option('display.max_columns', 500)


# In[24]:


#!wget "https://obis-datasets.ams3.digitaloceanspaces.com/exports/obis_20231025.parquet"
#!wget "https://hosted-datasets.gbif.org/datasets/gisd_2011-11-20.zip"
#!wget "https://hosted-datasets.gbif.org/datasets/iucn/iucn-2022-1.zip"


df = spark.read \
    .parquet('/Users/helloworld/Downloads/obis_20231025.parquet')


# In[25]:


from dwca.read import DwCAReader

with DwCAReader('/Users/helloworld/Downloads/gisd_2011-11-20.zip') as dwca:
   print("Core data file is: {}".format(dwca.descriptor.core.file_location)) # => 'taxon.txt'

   invasive_df = dwca.pd_read(dwca_red.descriptor.core.file_location, parse_dates=True)


with DwCAReader('/Users/helloworld/Downloads/iucn-2022-1.zip') as dwca_red:
   print("Core data file is: {}".format(dwca_red.descriptor.core.file_location)) # => 'taxon.txt'

   redlist_df = dwca_red.pd_read(dwca_red.descriptor.core.file_location, parse_dates=True)

redlist_df = redlist_df.dropna(subset=["scientificNameAuthorship"])
redlist_df['scientificName'] = redlist_df.apply(lambda row: row['scientificName'].replace(row['scientificNameAuthorship'], '').strip(), axis=1)
redlist_df.tail(20)


# In[27]:


# Assuming 'df' is your original Spark DataFrame and 'core_df' contains your invasive species data
obis_columns = ["marine", "class", "genus", "species", "variety", "individualCount", "eventDate", "eventTime", "year", "month", "day", "country", "locality", "decimalLongitude", "decimalLatitude"]

# Select the relevant columns and repartition
newdf = df.select(obis_columns).repartition(300)
newdf.registerTempTable('obis_data')

# Register the invasive species DataFrame as a temporary table
# Assuming 'core_df' is a Pandas DataFrame with a column 'scientificName' for invasive species
invasive_species = spark.createDataFrame(invasive_df).withColumnRenamed('scientificName', 'species')
invasive_species.registerTempTable('invasive_species')

redlist_species = spark.createDataFrame(redlist_df).withColumnRenamed('scientificName', 'species')
redlist_species.registerTempTable('redlist_species')

# Use SQL to filter 'obis_data', join with 'invasive_species', and sum 'individualCount'
aggregated_invasive_counts = spark.sql("""
    SELECT obis.species, sum(obis.individualCount) as total_individualCount
    FROM obis_data obis
    INNER JOIN invasive_species inv ON obis.species = inv.species
    WHERE obis.individualCount > 0 AND country = "Mexico"
    GROUP BY obis.species
    ORDER BY total_individualCount DESC
""")

aggregated_redlist_counts = spark.sql("""
    SELECT obis.species, sum(obis.individualCount) as total_individualCount
    FROM obis_data obis
    INNER JOIN redlist_species red ON obis.species = red.species
    WHERE obis.individualCount > 0 AND country = "Mexico"
    GROUP BY obis.species
    ORDER BY total_individualCount DESC
""")

# Show the result
aggregated_invasive_df = aggregated_invasive_counts.toPandas()
aggregated_redlist_df = aggregated_redlist_counts.toPandas()


# In[29]:


aggregated_invasive_df


# In[30]:


aggregated_redlist_df


# In[ ]:




