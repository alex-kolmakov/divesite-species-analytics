# Species Analytics

Idea for the project was inspired by https://www.emiratesdiving.com/ article about local outbreak of Acanthaster planci(Crown of thorns starfish that can multiply quite fast and poses danger to local coral population). If you are interested in the subject - please consider checking out https://www.emiratesdiving.com/magazine/divers-for-the-environment-march-2024/.

For the first iteration I wanted to build a project that allows to view biodiversity data near local divesites that I frequent and understand yearly trends and overall state of what kind of data is offered as publicly available. 

This project uses 4 sources of data: 
- GBIF occurence data - https://www.gbif.org/
- OBIS data as additional source of occurence data - https://obis.org/
- Global invasive species database - https://www.gbif.org/dataset/b351a324-77c4-41c9-a909-f30f77268bc4
- IUCN Red list of species as a Darwin Core archive - https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3

Combining them will allow to explain how different underwater points of interest relate to occurence data.

<img width="1263" alt="Screenshot 2024-03-31 at 10 12 14 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/4c43e0f7-587e-44f4-86af-9da4d9b9e32c">


This project uses mage.ai to orchestrate data ingestion and dbt runs for a marine species analytics project. The data ingestion script fetches data from the web and stores it in Google Cloud Storage. The dbt models transform the raw data into a structured format that can be used for analysis.

## Prerequisites

- Docker & Docker compose
- Google Cloud SDK (for interacting with Google Cloud Storage through terraform)
- Terraform
- Jupyter Notebook & Spark (To be automated in the future)

## Setup

1. Clone the repository:

```sh
git clone https://github.com/yourusername/marine-species-analytics.git && cd marine-species-analytics
```


2. Create a `secret.json` file with your Google Cloud credentials from Service Account and put it in the root of the project.

3. Update variables inside `variables.tf` to match your project setup in Google Cloud.

4. Configure your Google Cloud SDK:

```sh
gcloud init
```

5. Run `terraform apply` to get all resources in the cloud up and running.


6. MANUAL STEP: run locally `obis_data.ipynb` to get the data from OBIS API and save it. For this you will need to have Jupyter Notebook installed in your local machine with access to local Spark Cluster(or any other of your choice). Once you have the data, you can upload it to Google Cloud Storage. This step is not automated in the pipeline and will be the focus of later improvements.

7. Before starting the project there is an ability to position desired place on the map and time window for analytics. You can find those variables in the `marine_data/dbt_project.yml`.
    -   `AGGREGATION_WINDOW_DAYS: 1095` - occurence data for the past 3 years will be used
    -   `PROXIMITY_METERS: 5000` - occurence points deemed "near" the divesites location when they are 5km or closer.
    -   `LATTITUDE_TOP: 26.5`
    -   `LATTITUDE_BOTTOM: 22.5`
    -   `LONGITUDE_LEFT: 51`
    -   `LONGITUDE_RIGHT: 56.5`  - all these variables allow you to pick a "square" on the map by pointing to top-right and bottom-left corners of the map. 


9. Run the compose file to start mage.ai:

```sh
docker-compose up --build -d
```

9. After this - proceed to port 6789 and launch the pipeline or setup a trigger.


## WARNING

Launching pipeline combines both GBIF and OBIS datasets and consumes around 130GiB in processed data from BigQuery. This happens because of the filtering over geographic coordinates in the `stg_occurences.sql` model.
<img width="1319" alt="Screenshot 2024-03-29 at 6 19 32 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/ac1fd75f-46dc-4ca1-a261-dd3197fc7eb0">

## Models preview

Orchestration tree
<img width="990" alt="Screenshot 2024-03-29 at 6 16 36 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/ae09b781-42a7-41cc-9ae5-75a4cdd08179">

DBT models
<img width="1419" alt="Screenshot 2024-03-29 at 6 14 34 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/d20bd13a-f887-4436-86d9-7d245a4cff8b">


Resulting looker dashboard: https://lookerstudio.google.com/s/vSQv3DXuGNQ



## Improvements

- OBIS data proved to be challenging as it is offered as single files weighing more than 15Gb. Due to time constraints processing of that wont be included in the orchestrated pipeline - but for convenience already provided as a Pyspark notebook that will produce required result locally and allow for upload to GCS. For the second iteration it will be beneficial to add this to overall pipeline or make it a standalone pipeline running on a PySpark kernel.

- DBT models require test and documentation coverage that was omitted for the first iteration.

- There is a way to enrich the data with adding images to species by either feeding them through gbif api or implementing custom search endpoints on google. But it will require to make mage node asynchronous since doing this normally takes much longer.

- Final improvement wil lbe adding ability to mix in community observed data either through common tables and forms or any other to make the data even more relatable.
