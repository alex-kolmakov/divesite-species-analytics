
# Divesite Species Analytics Data Pipeline 

>This project started as my attempt to apply gathered knowledge to undestand how can I spot in advance the invasive and endangered species near the local divesites that frequent.


## Articles 

Project is described in depth on the following articles:
  - [Part 1: Aiming for the stars (Problem statement)](https://www.linkedin.com/pulse/data-engineering-zoom-camp-capstone-project-aleksandr-kolmakov/)
  - [Part 2: Ingesting data with Mage](https://www.linkedin.com/pulse/data-engineering-zoom-camp-capstone-project-aleksandr-kolmakov/)
  - Part 3: Clean, Enrich, Transform
  - Part 4: Data modelling
  - Part 5: Deployment and cost optimisation with GCP
  - Part 6: Final thoughts, lessons learnt and B-rolls of the development.


## Articles 

Project is described in depth on the following articles:
  - [Data Engineering Zoom Camp | Capstone Project](https://www.linkedin.com/pulse/data-engineering-zoom-camp-capstone-project-aleksandr-kolmakov/)


## Project overview

>Project aims to combine several scientific occurence datasets to provide ability to analyze them through the lens of specific occurence marker - like "invasive" or "endangered"


### Architecture Diagram


### Applied Tools & Technologies
<div align="center">
  <a href="https://www.docker.com/">Docker</a> • <a href="https://www.mage.ai/">Mage</a> • <a href="https://spark.apache.org/">Spark</a> • <a href="https://cloud.google.com/products/compute?hl=en">Google Cloud Virtual Machine</a> • <a href="https://cloud.google.com/storage/?hl=en">Google Cloud Storage</a> • <a href="https://cloud.google.com/bigquery?hl=en">Google BigQuery</a> • <a href="https://www.terraform.io/">Terraform</a> • <a href="https://lookerstudio.google.com/">Looker Studio</a>
</div>


### Pipelines


### Data modelling

Project mimics medallion architecture with the following layers:

- **Seabed** - contains raw external data from the sources.
- **Coral** - contains joined and cleaned data for individual dimensions and facts.
- **Reef** - final aggregated data for the analytics.


### Main Occurences model:
| Column Name    | Data Type   |   Description     |
|----------------|-------------|-------------------|
| species        | STRING      | String representation of the species name.              |
| individualcount| INTEGER     | Amount of individauls per  1 sighting (e.g. "I saw 5 ducks")              |
| eventdate      | TIMESTAMP   | Timestamp of the occurence               |
| geography      | GEOGRAPHY   | BigQuery type of geography marker: POINT()                |
| source         | STRING      | Source dataset from which occurence originated from                |
| is_invasive    | BOOLEAN     | Species considered invasive               |
| is_endangered  | BOOLEAN     | Species considered endangere             |

## [Dashboard](https://lookerstudio.google.com/s/vSQv3DXuGNQ)

- Divesites and observations distribution between used sources
- Invasive species near divesites
- Endangered species near divesites 
- Top 20 invasive species near divesites 

<img width="1253" alt="Screenshot 2024-04-23 at 2 15 41 PM" src="https://github.com/Feanaur/divesite-species-analytics/assets/3127175/7bcb7d82-53bc-4dbc-8da4-b08fb1ec846a">


## Setup

For the setup please proceed to the [SETUP.md](documentation/SETUP.md) file.





