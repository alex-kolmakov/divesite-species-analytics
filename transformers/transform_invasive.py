if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

import urllib
import requests

def get_first_media_image(species_name):
    # Encode the species name to ensure it's correctly formatted for the URL
    encoded_species_name = urllib.parse.quote(species_name)
    print(f"Fetching image for {species_name}")
    # Construct the query URL with the encoded species name
    url = f"https://api.gbif.org/v1/occurrence/search?q={encoded_species_name}&mediaType=StillImage&limit=1"
    
    # Make the request to the GBIF API
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        
        # Check if there are results and at least one media image
        if data['count'] > 0 and len(data['results']) > 0 and 'media' in data['results'][0]:
            # Extract the URL of the first media image
            try:
                media_url = data['results'][0]['media'][0]['identifier']
                return media_url
            except KeyError:
                return None
        else:
            return None
    else:
        return None




@transformer
def transform(data, *args, **kwargs):
    """
    Template code for a transformer block.

    Add more parameters to this function if this block has multiple parent blocks.
    There should be one parameter for each output variable from each parent block.

    Args:
        data: The output from the upstream parent block
        args: The output from any additional upstream blocks (if applicable)

    Returns:
        Anything (e.g. data frame, dictionary, array, int, str, etc.)
    """
    # data['imageUrl'] = data['scientificName'].apply(get_first_media_image)
    data = data.drop(columns=['source'])
    return data


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
    
