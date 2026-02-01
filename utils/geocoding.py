import aiohttp
import logging

async def geocode_address(address: str) -> tuple[float, float] | None:
    if not address:
        return None
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": "ru"
        }
        headers = {
            "User-Agent": "TelegramBot/1.0"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        lat = float(data[0]["lat"])
                        lon = float(data[0]["lon"])
                        return (lat, lon)
                else:
                    logging.warning(f"Geocoding API returned status {response.status}")
        return None
    except Exception as e:
        logging.error(f"Geocoding error for '{address}': {e}")
        return None
