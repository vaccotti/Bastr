
import requests
import logging

logger = logging.getLogger(__name__)

def get_city_bbox(city_name):
    """
    Geocode a city name to get its bounding box using Nominatim.
    Returns: (min_lat, max_lat, min_lon, max_lon) or None
    Note: Nominatim returns [min_lat, max_lat, min_lon, max_lon] in boundingbox
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "BarstrBot/1.0"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            logger.warning(f"No results found for city: {city_name}")
            return None
            
        # expected structure: data[0]['boundingbox'] -> [min_lat, max_lat, min_lon, max_lon]
        # Wait, Nominatim usually returns strings
        bbox = data[0].get('boundingbox')
        if bbox and len(bbox) == 4:
            # Convert to float
            return [float(x) for x in bbox]
            
        return None
        
    except Exception as e:
        logger.error(f"Error geocoding {city_name}: {e}")
        return None

def get_bitcoin_bars(bbox):
    """
    Fetch functionality from BTCmap within a bounding box.
    bbox: [min_lat, max_lat, min_lon, max_lon]
    Returns list of dicts with name, and details.
    """
    if not bbox:
        return []

    # BTCmap API v2 expects bounding_box=min_lon,min_lat,max_lon,max_lat
    # Nominatim gives: min_lat, max_lat, min_lon, max_lon
    
    min_lat, max_lat, min_lon, max_lon = bbox
    
    # Construct API param
    # Correct order for BTC Map: west, south, east, north (min_lon, min_lat, max_lon, max_lat)
    bbox_str = f"{min_lon},{min_lat},{max_lon},{max_lat}"
    
    url = "https://api.btcmap.org/v2/elements"
    params = {
        "bounding_box": bbox_str,
        "limit": 50 # Limit to avoid huge messages
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        elements = response.json()
        
        bars = []
        for el in elements:
            # We filter for bars/pubs
            # Check tags
            tags = el.get('osm_json', {}).get('tags', {})
            amenity = tags.get('amenity')
            
            # Categories we care about
            if amenity in ['bar', 'pub', 'nightclub', 'biergarten', 'cafe', 'restaurant']:
                # The user specifically asked for "bars bitcoin friendly".
                # Sometimes restaurants are bars. But let's verify "bitcoin friendly".
                # BTC Map returns things that accept BTC usually. But let's check tags.
                accepts_lightning = tags.get('payment:lightning') == 'yes'
                accepts_onchain = tags.get('payment:onchain') == 'yes'
                
                if accepts_lightning or accepts_onchain:
                    name = tags.get('name') or "Unknown Place"
                    # Create a nice link or info
                    osm_id = el.get('id', '').replace('node:', '').replace('way:', '')
                    # We can link to btcmap.org/map using coords eventually or just list names
                    
                    bar_info = {
                        "name": name,
                        "amenity": amenity,
                        "lightning": accepts_lightning,
                        "onchain": accepts_onchain,
                        "city": tags.get('addr:city', '')
                    }
                    bars.append(bar_info)
        
        return bars

    except Exception as e:
        logger.error(f"Error fetching from BTCmap: {e}")
        return []
