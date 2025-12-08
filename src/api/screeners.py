from yahooquery.constants import SCREENERS

AVAILABLE_SCREENERS = [
    {"name": key, "description": value['desc']} 
    for key, value in SCREENERS.items()
]
