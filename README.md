
# Divesite Species Analytics Data Pipeline 

Project aims to combine several scientific occurence datasets to provide ability to analyze them through the species distribution and divesite proximity.


### Setup

For the setup please proceed to the [documentation](documentation/setup.md).


### Architecture Diagram
![diagram](https://github.com/alex-kolmakov/divesite-species-analytics/assets/3127175/4b385807-daf9-4270-b225-1dc366ce2d1f)


### Data modelling

Project mimics medallion architecture with the following layers:

- **Substrate** - contains raw external data from the sources.
- **Skeleton** - contains joined and cleaned data for individual dimensions and facts.
- **Coral** - final aggregated data for the analytics.


### Main Occurences model:
| Column Name    | Data Type   |   Description     |
|----------------|-------------|-------------------|
| species        | STRING      | String representation of the species name.              |
| individualcount| INTEGER     | Amount of individauls per  1 sighting (e.g. "I saw 5 ducks")              |
| eventdate      | TIMESTAMP   | Timestamp of the occurence               |
| geography      | GEOGRAPHY   | BigQuery type of geography marker: POINT()                |
| source         | STRING      | Source dataset from which occurence originated from                |
| is_invasive    | BOOLEAN     | Species considered invasive               |
| is_endangered  | BOOLEAN     | Species considered endangered            |

## [Dashboard](https://lookerstudio.google.com/s/vSQv3DXuGNQ)

- Divesites and observations distribution between used sources
- Invasive species near divesites
- Endangered species near divesites 
- Top 20 invasive species near divesites 
<img width="1265" alt="Screenshot 2024-05-04 at 2 50 13 PM" src="https://github.com/alex-kolmakov/divesite-species-analytics/assets/3127175/3e01401b-4dce-41f4-af46-ee03aae6be33">


## Acknowledgements & Credits & Support

If you're interested in contributing to this project, need to report issues or submit pull requests, please get in touch via 
- [GitHub](https://github.com/alex-kolmakov)
- [LinkedIn](https://linkedin.com/in/aleksandr-kolmakov)


### Acknowledgements
Acknowledgement to #DataTalksClub for mentoring us through the Data Engineering Zoom Camp over the last 10 weeks. It has been a privilege to take part in the Spring '24 Cohort, go and check them out!

![image](https://github.com/alex-kolmakov/divesite-species-analytics/assets/3127175/d6504180-31a9-4cb7-8cd0-26cd2d0a12ad)



