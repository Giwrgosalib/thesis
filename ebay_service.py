from typing import Dict, List, Any, Optional
import requests
import os
import time
from urllib.parse import quote_plus
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

class EBayService:
    """Service for interacting with eBay API"""
    
    def __init__(self):
        # Load eBay API credentials from environment variables
        self.client_id = os.environ.get("EBAY_CLIENT_ID")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET")
        
        if not self.client_id or not self.client_secret:
            logger.warning("eBay API credentials not found in environment variables. Using mock data.")
            self.use_mock = True
        else:
            self.use_mock = False
            
        # eBay API endpoints
        self.auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        
        # Token management
        self.access_token = None
        self.token_expiry = 0
    
    def _get_access_token(self) -> str:
        """Get a valid OAuth access token for eBay API"""
        current_time = time.time()
        
        # Check if we have a valid token
        if self.access_token and current_time < self.token_expiry:
            return self.access_token
        
        # Request a new token
        try:
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {self._get_basic_auth_token()}'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'scope': 'https://api.ebay.com/oauth/api_scope'
            }
            
            response = requests.post(self.auth_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            # Set expiry time (subtract 5 minutes for safety margin)
            self.token_expiry = current_time + token_data['expires_in'] - 300
            
            return self.access_token
            
        except Exception as e:
            logger.error(f"Error obtaining eBay access token: {str(e)}")
            # Fall back to mock data if token acquisition fails
            self.use_mock = True
            return ""
    
    def _get_basic_auth_token(self) -> str:
        """Create the Basic Authorization token from client credentials"""
        import base64
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        return encoded_credentials
    
    def search(self, intent: Dict) -> List[Dict]:
        """Convert ML output to eBay API params and perform search"""
        params = {
            "q": intent['raw_query'],
            "limit": 10
        }

        # Add filters
        filters = self._build_filters(intent)
        if filters:
            # eBay expects filters as a single string, separated by ';'
            params["filter"] = ";".join(filters)

        # Add ML-powered sorting
        if intent.get('intent') == "buy_phone":
            params["sort"] = "newlyListed"
        elif intent.get('intent') == "bargain":
            params["sort"] = "price"

        # Add category if available
        category = self._get_category(intent)
        if category:
            category_id = self._get_category_id(category)
            if category_id != "0":
                params["category_ids"] = category_id

        # Use mock data if configured to do so
        if self.use_mock:
            logger.info("Using mock data for eBay search")
            mock_results = self._get_mock_results(
                intent['raw_query'],
                self._get_price_range(intent),
                category
            )
            return self._rerank_results(mock_results, intent)

        # Make the actual API call
        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
            }

            response = requests.get(self.search_url, params=params, headers=headers)
            response.raise_for_status()
            items = response.json().get("itemSummaries", [])

            # Optionally, map/normalize the results here if needed
            return self._rerank_results(items, intent)

        except Exception as e:
            logger.error(f"Error searching eBay API: {str(e)}")
            # Fall back to mock data on error
            mock_results = self._get_mock_results(
                intent['raw_query'],
                self._get_price_range(intent),
                category
            )
            return self._rerank_results(mock_results, intent)
    
    def search_ebay(self, query: str, price_range: Optional[str] = None, 
                   category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search eBay for items matching the query and filters
        
        Args:
            query: The search query string
            price_range: Optional price range filter (e.g. "10-50")
            category: Optional category filter
            
        Returns:
            List of item dictionaries with product details
        """
        try:
            # Build query parameters
            params = {
                "q": query,
                "limit": 10
            }
            
            # Add price filter if provided
            if price_range:
                min_price, max_price = self._parse_price_range(price_range)
                filters = []
                
                if min_price is not None:
                    filters.append(f"price:[{min_price}..]")
                if max_price is not None:
                    filters.append(f"price:[..{max_price}]")
                
                if filters:
                    params["filter"] = filters
            
            # Add category filter if provided
            if category:
                category_id = self._get_category_id(category)
                if category_id != "0":  # If we found a valid category
                    params["category_ids"] = category_id
            
            # Use mock data if configured to do so
            if self.use_mock:
                logger.info("Using mock data for eBay search")
                return self._get_mock_results(query, price_range, category)
            
            # Make the actual API call
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"  # Adjust for target marketplace
            }
            
            response = requests.get(self.search_url, params=params, headers=headers)
            response.raise_for_status()
            
            return response.json().get("itemSummaries", [])
            
        except Exception as e:
            logger.error(f"Error searching eBay: {str(e)}")
            # Fall back to mock data on error
            return self._get_mock_results(query, price_range, category)
    
    def _build_filters(self, intent: Dict) -> List[str]:
        """Build eBay API filter parameters from intent"""
        filters = []
        
        # Add price filters if available
        price_range = self._get_price_range(intent)
        if price_range:
            min_price, max_price = self._parse_price_range(price_range)
            if min_price is not None:
                filters.append(f"price:[{min_price}..]")
            if max_price is not None:
                filters.append(f"price:[..{max_price}]")
        
        # Add condition filters
        if 'condition' in intent and intent['condition']:
            conditions = []
            if 'new' in intent['condition']:
                conditions.append("NEW")
            if 'used' in intent['condition']:
                conditions.append("USED")
            if conditions:
                filters.append(f"conditionIds:{','.join(conditions)}")
        
        # Add brand filters
        if 'brands' in intent and intent['brands']:
            brand_filters = []
            for brand in intent['brands']:
                # Use exact brand match in eBay API format
                brand_filters.append(f"itemFilter.brand:{quote_plus(brand)}")
            if brand_filters:
                filters.extend(brand_filters)
        
        return filters
    
    def _get_price_range(self, intent: Dict) -> Optional[str]:
        """Extract price range from intent if available"""
        if 'price_range' in intent and intent['price_range']:
            return intent['price_range']
        return None
    
    def _get_category(self, intent: Dict) -> Optional[str]:
        """Extract category from intent if available"""
        if 'categories' in intent and intent['categories']:
            return intent['categories'][0]  # Use first category
        return None
    
    def _parse_price_range(self, price_range: str) -> tuple:
        """Parse a price range string into min and max values"""
        try:
            if "-" in price_range:
                parts = price_range.split("-")
                min_price = float(parts[0].strip().replace("$", ""))
                max_price = float(parts[1].strip().replace("$", ""))
                return min_price, max_price
            elif "under" in price_range.lower() or "less than" in price_range.lower():
                max_price = float(price_range.lower().replace("under", "").replace("less than", "").strip().replace("$", ""))
                return None, max_price
            elif "over" in price_range.lower() or "more than" in price_range.lower():
                min_price = float(price_range.lower().replace("over", "").replace("more than", "").strip().replace("$", ""))
                return min_price, None
            else:
                # Try to extract a single number
                price = float(price_range.strip().replace("$", ""))
                return price * 0.9, price * 1.1  # Give a 10% range
        except:
            return None, None
    
    def _get_category_id(self, category_name: str) -> str:
        """Convert a category name to eBay category ID"""
        # In a real implementation, this would use eBay's taxonomy API
        # or a local mapping of categories to IDs
        category_map = {
            "electronics": "293",
            "phones": "9355",
            "smartphones": "9355",
            "laptops": "175672",
            "computers": "58058",
            "clothing": "11450",
            "fashion": "11450",
            "shoes": "3034",
            "home": "11700",
            "furniture": "3197",
            "toys": "220",
            "books": "267",
            "sports": "888",
            "fitness": "15273",
            "automotive": "6000",
            "jewelry": "281",
            "watches": "14324",
            "cameras": "625",
            "video games": "1249",
            "music": "11233",
            "instruments": "619",
            "tools": "631",
            "garden": "2081",
            "beauty": "26395",
            "health": "26395",
            "collectibles": "1",
            "art": "550",
            "baby": "2984",
            "pet supplies": "1281",
            "business": "12576",
            "industrial": "12576",
        }
        
        # Try to find a matching category
        for key, value in category_map.items():
            if key.lower() in category_name.lower():
                return value
        
        # Default to a general category if no match
        return "0"  # All Categories
    
    def _rerank_results(self, items: List, intent: Dict) -> List:
        """Personalize results using intent and add public eBay URLs."""
        scored_items = []
        for item in items:
            score = self._match_score(item, intent)
            # Add public URL
            item_id = item.get('itemId')
            if item_id:
                # Remove any prefix like "v1|" if present
                if "|" in item_id:
                    ebay_id = item_id.split("|")[1]
                else:
                    ebay_id = item_id
                item["publicUrl"] = f"https://www.ebay.com/itm/{ebay_id}"
            scored_items.append((score, item))

        # Sort by score (descending) and then by price (ascending)
        scored_items.sort(key=lambda x: (-x[0], float(x[1].get('price', {}).get('value', 9999))))
        return [item for _, item in scored_items]

    def _match_score(self, item: Dict, intent: Dict) -> float:
        """Calculate similarity score between item and user intent"""
        score = 0
        title = item.get('title', '').lower()
        
        # Check for brand matches
        if 'brands' in intent and intent['brands']:
            for brand in intent['brands']:
                if brand.lower() in title:
                    score += 2
        
        # Check for category matches
        if 'categories' in intent and intent['categories']:
            for category in intent['categories']:
                if category.lower() in title:
                    score += 1
        
        # Check for condition preferences
        if 'condition' in intent and intent['condition']:
            item_condition = item.get('condition', '').lower()
            if 'new' in intent['condition'] and ('new' in item_condition or 'brand new' in item_condition):
                score += 1
            if 'used' in intent['condition'] and 'used' in item_condition:
                score += 1
        
        # Check for specific features mentioned in the intent
        if 'features' in intent and intent['features']:
            for feature in intent['features']:
                if feature.lower() in title:
                    score += 1.5
        
        return score
    
    def _get_mock_results(self, query: str, price_range: Optional[str] = None, 
                         category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate mock search results for development/testing"""
        # This would be replaced with actual API calls in production
        results = []
        
        # Parse price range to make mock data more realistic
        min_price, max_price = None, None
        if price_range:
            min_price, max_price = self._parse_price_range(price_range)
        
        if not min_price:
            min_price = 10
        if not max_price:
            max_price = 200
            
        # Generate a few mock items
        for i in range(1, 10):
            # Calculate a price within the range
            price_factor = i / 10
            price = min_price + (max_price - min_price) * price_factor
            
            # Create a more realistic title
            title_parts = [query.title()]
            
            # Add category to title if provided
            if category:
                title_parts.append(category.title())
                
            # Add some random attributes
            attributes = ["Premium", "Deluxe", "Standard", "Professional", "Basic"]
            colors = ["Black", "White", "Silver", "Red", "Blue"]
            
            title_parts.append(attributes[i % len(attributes)])
            title_parts.append(colors[(i + 2) % len(colors)])
            title_parts.append(f"Model {chr(65 + i)}")
            
            item = {
                "itemId": f"v1|{110000000000 + i}|0",
                "title": " ".join(title_parts),
                "price": {
                    "value": round(price, 2),
                    "currency": "USD"
                },
                "image": {
                    "imageUrl": f"https://picsum.photos/200/300?random={i}"
                },
                "seller": {
                    "username": f"top_seller_{i}",
                    "feedbackPercentage": f"{95 + (i % 5)}"
                },
                "condition": "New" if i % 3 != 0 else "Used",
                "shippingCost": {
                    "value": round(4.99 + (i % 3), 2),
                    "currency": "USD"
                },
                "itemHref": f"https://www.ebay.com/itm/v1|{110000000000 + i}|0",
                "itemLocation": {
                    "city": "New York",
                    "stateOrProvince": "NY",
                    "country": "US"
                },
                "categories": [
                    {"categoryId": self._get_category_id(category) if category else "0"}
                ]
            }
            results.append(item)
        
        return results