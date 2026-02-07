from geopy.geocoders import Nominatim
from typing import Optional, Tuple

def get_coordinates(address: str) -> Optional[Tuple[float, float, str]]:
    try:
        geolocator = Nominatim(user_agent="anty_test_bot_v1")
        location = geolocator.geocode(address)
        
        if location:
            return location.latitude, location.longitude, location.address
        return None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None
