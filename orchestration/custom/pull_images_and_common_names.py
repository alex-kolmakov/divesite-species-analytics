import random
import time
import aiohttp
import asyncio
import pandas as pd
from bs4 import BeautifulSoup
import nest_asyncio
from tqdm.asyncio import tqdm

nest_asyncio.apply()

MAX_RETRIES = 2
INITIAL_BACKOFF = 1  # 1 second
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
}

# Asynchronous function to get Common_name and Image_URL from Wikipedia for a single species
async def get_species_info_from_wikipedia(scientific_name):
    retries = 0
    backoff = INITIAL_BACKOFF
    
    while retries < MAX_RETRIES:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                await asyncio.sleep(random.uniform(1, 2))  # Random delay to avoid API rate limit
                
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

                # Extract the Common_name from the first sentence of the extract
                extract_text = page_info.get('extract', '')
                image_url = page_info.get('thumbnail', {}).get('source', 'Image not available')

                common_name = None
                if extract_text:
                    # Use the first sentence of the extract as the Common_name
                    first_sentence = extract_text.split('.')[0]

                    # Remove HTML tags using BeautifulSoup
                    common_name = BeautifulSoup(first_sentence, "html.parser").get_text().strip()

                return common_name, image_url
        except aiohttp.ClientConnectionError as e:
            retries += 1
            await asyncio.sleep(backoff)
            backoff *= 2  # Exponential backoff
        except Exception as e:
            return None, None
    
    return None, None

# Asynchronous function to process only the missing rows
async def process_missing_species_info(df):
    # Filter rows where 'Common_name' or 'Image_URL' are missing (NaN)
    missing_df = df[df['Common_name'].isna() | df['Image_URL'].isna()]
    print(f"Full shape {df.shape} vs {missing_df.shape}")
    if missing_df.empty:
        print("All species already processed.")
        return df  # Return the original DataFrame if nothing is missing
    
    tasks = []
    for index, row in missing_df.iterrows():
        species_name = row['species']
        # Create tasks for only missing species info
        tasks.append(get_species_info_from_wikipedia(species_name))

    # Gather results with a progress bar
    results = await tqdm.gather(*tasks)

    # Update only the rows with missing data
    missing_df[['Common_name', 'Image_URL']] = pd.DataFrame(results, index=missing_df.index, columns=['Common_name', 'Image_URL'])

    # Update the original DataFrame with the new information
    df.update(missing_df)
    
    return df

# Function to run the async loop and process the DataFrame in Jupyter
async def apply_wikipedia_info_to_df(df):
    # Process the DataFrame asynchronously for missing rows
    return await process_missing_species_info(df)


@custom
def transform_custom(data, *args, **kwargs):
    """
    args: The output from any upstream parent blocks (if applicable)

    Returns:
        Anything (e.g. data frame, dictionary, array, int, str, etc.)
    """
    # Specify your custom logic here
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(apply_wikipedia_info_to_df(data))
    return result

@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'