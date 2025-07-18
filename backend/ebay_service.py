from typing import Dict, List, Any, Optional
import requests
import os
import time
from urllib.parse import quote_plus
import logging
from dotenv import load_dotenv
from pymongo.collection import Collection  # Import Collection type hint

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

class EBayService:
    """Service for interacting with eBay API"""

    # Accept preferences_collection in __init__
    def __init__(self, preferences_collection: Optional[Collection] = None):
        self.client_id = os.environ.get("EBAY_CLIENT_ID")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            logger.warning("eBay API credentials not found. Using mock data.")
            self.use_mock = True
        else:
            self.use_mock = False

        self.auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

        self.access_token = None
        self.token_expiry = 0

        # Store the MongoDB collection
        self.preferences_collection = preferences_collection

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

    # Modify search signature to accept user_id
    def search(self, intent: Dict, user_id: Optional[str] = None) -> List[Dict]:
        """Convert ML output to eBay API params, perform search, and personalize results."""
        query = intent.get('raw_query', '').strip()
        logging.info(f"eBay search intent: {intent}")
        if not query:
            logger.error("Empty query received for eBay search. Aborting API call.")
            return []

        # Fetch user preferences if user_id is provided
        user_prefs = self._get_user_preferences(user_id) if user_id else {}

        # Apply user preferences when not explicitly specified in the query
        if user_prefs:
            intent = self._enhance_with_user_preferences(intent, user_prefs)
            logging.info("Enhanced search with user preferences")

        # Build API parameters
        params = {
            "q": query,
            "limit": 20
        }

        filters = self._build_filters(intent)
        if filters:
            params["filter"] = ";".join(filters)

        # Add ML-powered sorting (can be overridden by personalization later)
        if intent.get('intent') == "buy_phone":
            params["sort"] = "newlyListed"
        elif intent.get('intent') == "bargain":
            params["sort"] = "price"

        category = self._get_category(intent)
        if category:
            category_id = self._get_category_id(category)
            if category_id != "0":
                params["category_ids"] = category_id

        if self.use_mock:
            logger.info("Using mock data for eBay search")
            mock_results = self._get_mock_results(
                intent.get('raw_query', ''),
                self._get_price_range(intent),
                category
            )
            # Pass user_prefs to rerank
            return self._rerank_results(mock_results, intent, user_prefs)

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

            # Pass user_prefs to rerank
            return self._rerank_results(items, intent, user_prefs)

        except Exception as e:
            logger.error(f"Error searching eBay API: {str(e)}")
            mock_results = self._get_mock_results(
                intent.get('raw_query', ''),
                self._get_price_range(intent),
                category
            )
            # Pass user_prefs to rerank
            return self._rerank_results(mock_results, intent, user_prefs)

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

    def _get_user_preferences(self, user_id: str) -> Dict:
        """Fetches user preferences from MongoDB."""
        if self.preferences_collection is None or not user_id:
            return {}
        try:
            prefs = self.preferences_collection.find_one({'user_id': user_id})
            return prefs if prefs else {}
        except Exception as e:
            logger.error(f"Error fetching preferences for user {user_id}: {e}", exc_info=True)
            return {}
    
    # Modify _rerank_results to accept and use user_prefs
    def _rerank_results(self, items: List, intent: Dict, user_prefs: Dict) -> List:
        """Personalize results using intent, user preferences, and add public eBay URLs."""
        if not items:
            return []

        scored_items = []
        for item in items:
            # Calculate base score based on current intent
            score = self._match_score(item, intent)

            # --- Apply User Preference Boosts ---
            title = item.get('title', '').lower()
            preferred_brands = user_prefs.get('preferred_brands', [])
            preferred_categories = user_prefs.get('preferred_categories', [])

            # Boost score if item matches preferred brands
            for brand in preferred_brands:
                if brand.lower() in title:
                    score += 1.5  # Add preference boost

            # Boost score if item matches preferred categories
            for category in preferred_categories:
                # Check against item title or potentially item category if available
                item_category_name = item.get('categories', [{}])[0].get('categoryName', '').lower()  # Example if category name is available
                if category.lower() in title or category.lower() in item_category_name:
                    score += 1.0  # Add preference boost

            # --- End Preference Boosts ---

            # Add public URL (simple transformation, might need adjustment based on actual API response)
            item_id = item.get('itemId', '').split('|')[1] if '|' in item.get('itemId', '') else item.get('itemId')
            if item_id:
                item['publicUrl'] = f"https://www.ebay.com/itm/{item_id}"
            else:
                item['publicUrl'] = item.get('itemHref', '#')  # Fallback

            scored_items.append({'item': item, 'score': score})

        # Sort items by score in descending order
        scored_items.sort(key=lambda x: x['score'], reverse=True)

        # Return only the top N items (e.g., top 10)
        return [scored['item'] for scored in scored_items[:10]]

    # Modify _match_score slightly for clarity
    def _match_score(self, item: Dict, intent: Dict) -> float:
        """Calculate similarity score between item and current search intent"""
        score = 0.0  # Use float for scores
        title = item.get('title', '').lower()

        # Check for brand matches from current intent
        current_brands = intent.get("BRAND", [])  # Use the key from NLP output
        if current_brands:
            for brand in current_brands:
                if brand.lower() in title:
                    score += 2.0

        # Check for category matches from current intent
        current_categories = intent.get("CATEGORY", [])  # Use the key from NLP output
        if current_categories:
            for category in current_categories:
                if category.lower() in title:
                    score += 1.0

        # Check for condition preferences from current intent
        current_condition = intent.get("CONDITION", [])  # Use the key from NLP output
        if current_condition:
            item_condition = item.get('condition', '').lower()
            if 'new' in current_condition and ('new' in item_condition or 'brand new' in item_condition):
                score += 1.0
            if 'used' in current_condition and 'used' in item_condition:
                score += 1.0

        # Check for specific features mentioned in the current intent
        current_features = intent.get("FEATURES", [])  # Assuming FEATURES is a possible key
        if current_features:
            for feature in current_features:
                if feature.lower() in title:
                    score += 1.5

        return score

    def _get_mock_results(self, query: str, price_range: Optional[str] = None,
                          category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate mock search results for development/testing"""
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

    def _enhance_with_user_preferences(self, intent: Dict, user_prefs: Dict) -> Dict:
        """Add user preferences to search criteria when not explicitly specified."""
        if not user_prefs:
            return intent

        enhanced_intent = intent.copy()

        # A helper function to check if a preference is already in the intent
        def is_preference_set(key):
            return key in enhanced_intent and enhanced_intent[key]

        # Apply size preference if not explicitly specified in current query
        if not is_preference_set('SIZE') and 'preferred_size' in user_prefs:
            # Add a specific check to ignore nonsensical or placeholder values
            if user_prefs['preferred_size'] and user_prefs['preferred_size'] != ['over']:
                enhanced_intent['SIZE'] = user_prefs['preferred_size']
                logging.info(f"Applied preferred size: {user_prefs['preferred_size']}")

        # Apply width preference if not explicitly specified
        if not is_preference_set('WIDTH') and 'preferred_width' in user_prefs:
            enhanced_intent['WIDTH'] = user_prefs['preferred_width']
            logging.info(f"Applied preferred width: {user_prefs['preferred_width']}")
            
        # Apply color preference if not explicitly specified
        if not is_preference_set('COLOR') and 'preferred_color' in user_prefs:
            enhanced_intent['COLOR'] = user_prefs['preferred_color']
            logging.info(f"Applied preferred color: {user_prefs['preferred_color']}")

        # Could add more preferences here (material, style, etc.)

        return enhanced_intent

    def update_user_preferences(self, user_id: str, preferences: Dict) -> bool:
        """Updates user preferences in MongoDB."""
        if self.preferences_collection is None or not user_id:
            return False
        try:
            self.preferences_collection.update_one(
                {'user_id': user_id},
                {'$set': preferences},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error updating preferences for user {user_id}: {e}")
            return False