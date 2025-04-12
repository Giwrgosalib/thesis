import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class Config:
    # eBay API Configuration
    EBAY_API_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    EBAY_API_KEY = os.getenv("EBAY_API_KEY")  # From environment variables
    
    # Application Settings
    MAX_RECOMMENDATIONS = 2
    DEFAULT_PRICE_RANGE = "0..2000"