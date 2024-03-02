import urllib.parse
import requests

def get_first_media_image(species_name):
    # Encode the species name to ensure it's correctly formatted for the URL
    encoded_species_name = urllib.parse.quote(species_name)
    
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
            media_url = data['results'][0]['media'][0]['identifier']
            return media_url
        else:
            return "No media image found for the given species."
    else:
        return "Failed to retrieve data from the GBIF API."

# Example usage
species_name = "Acanthaster planci"
print(get_first_media_image(species_name))


def get_google_custom_search_image(search_term):
    API_KEY = 'AIzaSyC5sfx3kFubedKrYuBrDTqNZSnPZFEVIv0'
    CX = '85e56ca4ec2f94e19'
    URL = 'https://www.googleapis.com/customsearch/v1'
    
    params = {
        'key': API_KEY,
        'cx': CX,
        'q': search_term,
        'searchType': 'image',
        'num': 1  # Number of images to return
    }
    
    response = requests.get(URL, params=params)
    response.raise_for_status()  # Raises stored HTTPError, if one occurred
    
    results = response.json()
    if 'items' in results and len(results['items']) > 0:
        first_image_url = results['items'][0]['link']
        return first_image_url
    else:
        return "No images found."

# Example usage
species_name = "Acanthaster planci"
print(get_google_custom_search_image(species_name))



