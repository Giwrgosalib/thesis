from typing import Dict, List, Any, Optional
import requests
from urllib.parse import quote_plus

class EBayService:
    """Service for interacting with eBay API"""
    
    def __init__(self):
        # eBay API credentials would typically be loaded from environment variables
        # or a secure configuration file in a production environment
        self.api_key = "YOUR_EBAY_API_KEY"  # Replace with actual API key or env variable
        self.base_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        
    def search(self, intent: Dict) -> List[Dict]:
        """Convert ML output to eBay API params"""
        params = {
            "q": intent['raw_query'],
            "filter": self._build_filters(intent)
        }
        # Add ML-powered sorting
        if intent['intent'] == "buy_phone":
            params["sort"] = "newlyListed" 
        elif intent['intent'] == "bargain":
            params["sort"] = "priceAsc"
        
        # In a real implementation, you would make the API call with proper headers:
        # headers = {"Authorization": f"Bearer {self.api_key}"}
        # response = requests.get(self.base_url, params=params, headers=headers)
        # return self._rerank_results(response.json().get("itemSummaries", []), intent)
        
        # For development/testing, use mock data
        mock_results = self._get_mock_results(intent['raw_query'], 
                                             self._get_price_range(intent),
                                             self._get_category(intent))
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
            }
            
            # Add price filter if provided
            if price_range:
                min_price, max_price = self._parse_price_range(price_range)
                if min_price:
                    params["price_min"] = min_price
                if max_price:
                    params["price_max"] = max_price
            
            # Add category filter if provided
            if category:
                params["category_ids"] = self._get_category_id(category)
            
            # In a real implementation, you would make the API call:
            # headers = {"Authorization": f"Bearer {self.api_key}"}
            # response = requests.get(self.base_url, params=params, headers=headers)
            # return response.json().get("itemSummaries", [])
            
            # For now, return mock data
            return self._get_mock_results(query, price_range, category)
        
        except Exception as e:
            print(f"Error searching eBay: {str(e)}")
            return []
    
    def _build_filters(self, intent: Dict) -> List[str]:
        """Build eBay API filter parameters from intent"""
        filters = []
        
        # Add price filters if available
        price_range = self._get_price_range(intent)
        if price_range:
            min_price, max_price = self._parse_price_range(price_range)
            if min_price:
                filters.append(f"price:[{min_price}..]")
            if max_price:
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
            "clothing": "11450",
            "home": "11700",
            "toys": "220",
            "books": "267",
            "sports": "888",
            # Add more mappings as needed
        }
        
        # Try to find a matching category
        for key, value in category_map.items():
            if key.lower() in category_name.lower():
                return value
        
        # Default to a general category if no match
        return "0"  # All Categories
    
    def _rerank_results(self, items: List, intent: Dict) -> List:
        """Personalize results using intent"""
        # Implement ML ranking model here
        return sorted(items, key=lambda x: (
            -self._match_score(x, intent),
            x['price']['value']
        ))

    def _match_score(self, item: Dict, intent: Dict) -> float:
        """Calculate ML similarity score"""
        # This would use a trained model in production
        score = 0
        if 'brands' in intent and intent['brands'] and any(b in item['title'].lower() for b in intent['brands']):
            score += 2
        if 'categories' in intent and intent['categories'] and any(c in item['title'].lower() for c in intent['categories']):
            score += 1
        return score
    
    def _get_mock_results(self, query: str, price_range: Optional[str] = None, 
                         category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate mock search results for development/testing"""
        # This would be replaced with actual API calls in production
        results = []
        
        # Generate a few mock items
        for i in range(1, 6):
            item = {
                "itemId": f"item{i}",
                "title": f"{query.title()} - Product {i}",
                "price": {
                    "value": 10.99 * i,
                    "currency": "USD"
                },
                "image": {
                    "imageUrl": f"https://picsum.photos/200/300?random={i}"
                },
                "seller": {
                    "username": f"seller{i}",
                    "feedbackPercentage": "98.5"
                },
                "condition": "New",
                "shippingCost": {
                    "value": 4.99,
                    "currency": "USD"
                },
                "url": f"https://www.ebay.com/itm/item{i}"
            }
            results.append(item)
        
        return results
