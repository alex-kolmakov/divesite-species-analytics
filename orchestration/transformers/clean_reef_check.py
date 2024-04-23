if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test
from datetime import datetime

REEF_CHECK_MAPPING = {
    "Dark Butterflyfish": "Chaetodon nigropunctatus",
    "Arabian Butterflyfish": "Chaetodon melapterus",
    "Longfin Bannerfish": "Heniochus acuminatus",
    "Butterflyfish": "Chaetodontidae",
    "Barramundi Cod": "Cromileptes altivelis",
    "Humphead Wrasse": "Cheilinus undulatus",
    "Grey Grunt": "Haemulon plumierii",
    "Black Spotted Grunt": "Haemulon maculicauda",
    "Spotted Grunt": "Haemulon maculicauda",
    "Haemulidae": "Haemulidae",
    "Bumphead Parrot": "Bolbometopon muricatum",
    "Parrotfish": "Scaridae",
    "Snapper": "Lutjanidae",
    "Moray Eel": "Muraenidae",
    "Grouper 30-40 cm": "Serranidae", 
    "Grouper 40-50 cm": "Serranidae",
    "Grouper 50-60 cm": "Serranidae",
    "Grouper > 60 cm": "Serranidae",
    "Grouper Total": "Serranidae",
    "Orange Spotted Grouper 30-40 cm": "Epinephelus coioides",
    "Orange Spotted Grouper 40-50 cm": "Epinephelus coioides",
    "Orange Spotted Grouper 50-60 cm": "Epinephelus coioides",
    "Orange Spotted Grouper > 60 cm": "Epinephelus coioides",
    "Orange Spotted Grouper Total": "Epinephelus coioides",
    "Banded Coral Shrimp": "Stenopus hispidus",
    "Diadema": "Diadema antillarum",
    "Black Urchin": "Diadema antillarum",
    "Short Spine Urchin": "Lytechinus variegatus",
    "Pencil Urchin": "Echinometra mathaei",
    "Tripneustes": "Tripneustes",
    "Edible Sea Cucumber": "Holothuria edulis",
    "COTS": "Ancanthaster planci",
    "Cowries": "Cowries",
    "Triton": "Charonia tritonis",
    "Lobster": "Diadema antillarum",
    "Giant Clam < 10 cm": "Tridacna gigas",
    "Giant Clam 10-20 cm": "Tridacna gigas",
    "Giant Clam 20-30 cm": "Tridacna gigas",
    "Giant Clam 30-40 cm": "Tridacna gigas",
    "Giant Clam 40-50 cm": "Tridacna gigas",
    "Giant Clam > 50 cm": "Tridacna gigas",
    "Giant Clam Total": "Tridacna gigas",
}

def sum_legs(*args):
    total = 0
    for arg in args:
        if isinstance(arg, (int, float)):
            total += arg
    return total



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
    # Specify your transformation logic here
    data['latitude'] = data.apply(lambda row: float(row['coordinates_in_decimal_degree_format'].split(", ")[0]), axis=1)
    data['longitude'] = data.apply(lambda row: float(row['coordinates_in_decimal_degree_format'].split(", ")[1]), axis=1)
    data['species'] = data.apply(lambda row: REEF_CHECK_MAPPING.get(row['organism_code']), axis=1)
    data['s1 (0-20m)'] = data['s1 (0-20m)'].fillna(0)
    data['s2 (25-45m)'] = data['s2 (25-45m)'].fillna(0)
    data['s3 (50-70m)'] = data['s3 (50-70m)'].fillna(0)
    data['s4 (75-95m)'] = data['s4 (75-95m)'].fillna(0)
    data['individualCount'] = data.apply(lambda row: sum_legs(
        row['s1 (0-20m)'],
        row['s2 (25-45m)'],
        row['s3 (50-70m)'],
        row['s4 (75-95m)'],
    ), axis=1)

    data['date'] = data.apply(lambda row: datetime.strptime(row['date'], "%d-%B-%y").isoformat(), axis=1)
    
    data = data.drop(columns=[
        "site_id", "survey_id",
        "longitude_degrees",
        "longitude_minutes",
        "longitude_seconds",
        "longitude_cardinal_direction",
        "latitude_degrees",
        "latitude_minutes",
        "latitude_seconds",
        "latitude_cardinal_direction",
        "static_descriptors_reef_id (archived field)",
    ])

    return data


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
