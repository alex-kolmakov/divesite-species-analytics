import random
import time
import aiohttp
import asyncio
import pandas as pd
from bs4 import BeautifulSoup
import nest_asyncio
from tqdm.asyncio import tqdm

nest_asyncio.apply()

MAX_RETRIES = 5
INITIAL_BACKOFF = 5  # 1 second
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
}

# Asynchronous function to get common name and image URL from Wikipedia for a single species
async def get_species_info_from_wikipedia(scientific_name):
    retries = 0
    backoff = INITIAL_BACKOFF
    
    while retries < MAX_RETRIES:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                await asyncio.sleep(random.uniform(5, 20))  # Random delay to avoid API rate limit
                
                # Search Wikipedia for the species page
                search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={scientific_name}&format=json"
                async with session.get(search_url) as search_response:
                    if search_response.status != 200:
                        return None, None
                    search_data = await search_response.json()

                # Check if any page is found
                if not search_data['query']['search']:
                    return None, None

                # Get the page title from the first search result
                page_title = search_data['query']['search'][0]['title']

                # Wikipedia API endpoint for fetching page info including image and extract
                page_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={page_title}&prop=pageimages|extracts&format=json&pithumbsize=1024&exintro"
                async with session.get(page_url) as page_response:
                    if page_response.status != 200:
                        return None, None
                    page_data = await page_response.json()

                pages = page_data.get('query', {}).get('pages', {})

                if not pages:
                    return None, None

                # Extract the page details
                page_info = next(iter(pages.values()))

                # Extract the common name from the first sentence of the extract
                extract_text = page_info.get('extract', '')
                image_url = page_info.get('thumbnail', {}).get('source', 'Image not available')

                common_name = None
                if extract_text:
                    # Use the first sentence of the extract as the common name
                    first_sentence = extract_text.split('.')[0]

                    # Remove HTML tags using BeautifulSoup
                    common_name = BeautifulSoup(first_sentence, "html.parser").get_text().strip()

                return common_name, image_url
        except aiohttp.ClientConnectionError as e:
            retries += 1
            await asyncio.sleep(backoff)
            backoff *= 2  # Exponential backoff
        except Exception as e:
            print(f"Error for {scientific_name}: {e}")
            return None, None
    
    # If all retries fail, return None
    print(f"Failed to fetch data for {scientific_name} after {MAX_RETRIES} retries.")
    return None, None

# Asynchronous function to process a DataFrame row and apply the Wikipedia info extraction
async def process_species_list(df, column_name):
    tasks = []
    for name in df[column_name]:
        # Create tasks for each species name
        tasks.append(get_species_info_from_wikipedia(name))

    # Gather all tasks (concurrent execution) with tqdm progress bar
    results = await tqdm.gather(*tasks)  # Add progress bar to async task execution

    # Assign the results to new columns in the DataFrame
    df[['Common Name', 'Image URL']] = pd.DataFrame(results, columns=['Common Name', 'Image URL'])
    return df

# Function to run the async loop and process the DataFrame in Jupyter
async def apply_wikipedia_info_to_df(df, column_name):
    # Process the DataFrame asynchronously
    return await process_species_list(df, column_name)

@custom
def transform_custom(data, *args, **kwargs):
    """
    args: The output from any upstream parent blocks (if applicable)

    Returns:
        Anything (e.g. data frame, dictionary, array, int, str, etc.)
    """
    # Specify your custom logic here
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(apply_wikipedia_info_to_df(data, 'species'))
    return result

@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'