from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import os
import logging

class EBayRecommender:
    """Recommendation system for eBay products"""
    
    def __init__(self, data_path: str = "data/product_data.csv", model_path: str = "models/recommender.pkl"):
        """
        Initialize the recommender system
        
        Args:
            data_path: Path to the product data CSV
            model_path: Path to save/load the trained model
        """
        self.data_path = data_path
        self.model_path = model_path
        self.product_data = None
        self.content_similarity = None
        self.user_item_matrix = None
        self.item_features = None
        self.logger = logging.getLogger(__name__)
        
        # Load model if it exists
        if os.path.exists(model_path):
            self._load_model()
        else:
            self.logger.warning(f"No recommender model found at {model_path}. Use train() to create one.")
    
    def train(self, product_data_path: Optional[str] = None, user_interactions_path: Optional[str] = "data/user_interactions.csv"):
        """
        Train the recommendation models
        
        Args:
            product_data_path: Path to product data CSV (optional, uses self.data_path if None)
            user_interactions_path: Path to user interaction data (views, purchases, etc.)
        """
        try:
            # Load product data
            data_path = product_data_path or self.data_path
            self.product_data = pd.read_csv(data_path)
            self.logger.info(f"Loaded product data with {len(self.product_data)} items")
            
            # Train content-based model
            self._train_content_based()
            
            # Train collaborative filtering model if user data exists
            if os.path.exists(user_interactions_path):
                self._train_collaborative(user_interactions_path)
            
            # Save the trained model
            self._save_model()
            self.logger.info("Recommender model trained and saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error training recommender model: {str(e)}")
            raise
    
    def _train_content_based(self):
        """Train content-based recommendation model using product features"""
        # Create a text representation of each product
        self.product_data['features'] = self.product_data.apply(
            lambda row: f"{row['title']} {row.get('brand', '')} {row.get('category', '')} {row.get('description', '')}", 
            axis=1
        )
        
        # Create TF-IDF vectors
        tfidf = TfidfVectorizer(stop_words='english')
        self.item_features = tfidf.fit_transform(self.product_data['features'])
        
        # Calculate similarity matrix
        self.content_similarity = cosine_similarity(self.item_features)
    
    def _train_collaborative(self, user_interactions_path: str):
        """Train collaborative filtering model using user interaction data"""
        # Load user interaction data
        interactions = pd.read_csv(user_interactions_path)
        
        # Create user-item matrix (users as rows, items as columns)
        self.user_item_matrix = interactions.pivot_table(
            index='user_id', 
            columns='item_id', 
            values='interaction_value',
            fill_value=0
        )
    
    def get_similar_items(self, item_id: str, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get similar items based on content similarity
        
        Args:
            item_id: ID of the reference item
            n: Number of recommendations to return
            
        Returns:
            List of similar item dictionaries
        """
        if self.content_similarity is None:
            self.logger.warning("Content similarity matrix not available. Train the model first.")
            return []
        
        try:
            # Find the index of the item
            item_idx = self.product_data[self.product_data['item_id'] == item_id].index[0]
            
            # Get similarity scores
            similarity_scores = list(enumerate(self.content_similarity[item_idx]))
            
            # Sort by similarity (excluding the item itself)
            similarity_scores = sorted(
                [i for i in similarity_scores if i[0] != item_idx],
                key=lambda x: x[1], 
                reverse=True
            )
            
            # Get top N similar items
            similar_items_indices = [i[0] for i in similarity_scores[:n]]
            
            # Convert to list of dictionaries
            recommendations = self.product_data.iloc[similar_items_indices].to_dict('records')
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error getting similar items: {str(e)}")
            return []
    
    def get_user_recommendations(self, user_id: str, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations for a user
        
        Args:
            user_id: ID of the user
            n: Number of recommendations to return
            
        Returns:
            List of recommended item dictionaries
        """
        if self.user_item_matrix is None:
            self.logger.warning("User-item matrix not available. Using content-based only.")
            # Fall back to popular items if no user data
            return self.get_popular_items(n)
        
        try:
            if user_id not in self.user_item_matrix.index:
                self.logger.info(f"User {user_id} not found in user-item matrix. Using popular items.")
                return self.get_popular_items(n)
            
            # Get user's interaction vector
            user_vector = self.user_item_matrix.loc[user_id].values
            
            # Calculate similarity with all other users
            user_similarities = []
            for other_user in self.user_item_matrix.index:
                if other_user != user_id:
                    other_vector = self.user_item_matrix.loc[other_user].values
                    similarity = cosine_similarity([user_vector], [other_vector])[0][0]
                    user_similarities.append((other_user, similarity))
            
            # Sort by similarity
            user_similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Get top similar users
            similar_users = [u[0] for u in user_similarities[:10]]
            
            # Find items that similar users interacted with but the user hasn't
            user_items = set(self.user_item_matrix.columns[user_vector > 0])
            candidate_items = {}
            
            for similar_user in similar_users:
                similar_user_vector = self.user_item_matrix.loc[similar_user].values
                similar_user_items = set(self.user_item_matrix.columns[similar_user_vector > 0])
                
                # Items the similar user liked but our user hasn't interacted with
                new_items = similar_user_items - user_items
                
                for item in new_items:
                    if item in candidate_items:
                        candidate_items[item] += self.user_item_matrix.loc[similar_user, item]
                    else:
                        candidate_items[item] = self.user_item_matrix.loc[similar_user, item]
            
            # Sort candidate items by score
            recommended_items = sorted(candidate_items.items(), key=lambda x: x[1], reverse=True)[:n]
            
            # Get item details
            item_ids = [i[0] for i in recommended_items]
            recommendations = self.product_data[self.product_data['item_id'].isin(item_ids)].to_dict('records')
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error getting user recommendations: {str(e)}")
            return self.get_popular_items(n)  # Fall back to popular items
    
    def get_popular_items(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get most popular items based on interaction count"""
        if self.product_data is None:
            self.logger.warning("Product data not available. Train the model first.")
            return []
        
        try:
            # If we have popularity data, use it
            if 'popularity' in self.product_data.columns:
                popular_items = self.product_data.sort_values('popularity', ascending=False).head(n)
            else:
                # Otherwise just return the first N items
                popular_items = self.product_data.head(n)
            
            return popular_items.to_dict('records')
            
        except Exception as e:
            self.logger.error(f"Error getting popular items: {str(e)}")
            return []
    
    def get_recommendations_for_query(self, query: str, filters: Dict[str, Any] = None, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get recommendations based on a search query and filters
        
        Args:
            query: Search query string
            filters: Dictionary of filters (price_range, category, etc.)
            n: Number of recommendations to return
            
        Returns:
            List of recommended item dictionaries
        """
        if self.product_data is None or self.item_features is None:
            self.logger.warning("Product data or item features not available. Train the model first.")
            return []
        
        try:
            # Create a query vector
            tfidf = TfidfVectorizer(stop_words='english')
            tfidf.fit(self.product_data['features'])
            query_vector = tfidf.transform([query])
            
            # Calculate similarity with all items
            similarities = cosine_similarity(query_vector, self.item_features)[0]
            
            # Create a DataFrame with similarities
            results = self.product_data.copy()
            results['similarity'] = similarities
            
            # Apply filters if provided
            if filters:
                if 'price_range' in filters and filters['price_range']:
                    min_price, max_price = self._parse_price_range(filters['price_range'])
                    if min_price:
                        results = results[results['price'] >= min_price]
                    if max_price:
                        results = results[results['price'] <= max_price]
                
                if 'category' in filters and filters['category']:
                    results = results[results['category'] == filters['category']]
            
            # Sort by similarity and return top N
            recommendations = results.sort_values('similarity', ascending=False).head(n)
            return recommendations.to_dict('records')
            
        except Exception as e:
            self.logger.error(f"Error getting query recommendations: {str(e)}")
            return []
    
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
    
    def _save_model(self):
        """Save the trained model to disk"""
        model_data = {
            'product_data': self.product_data,
            'content_similarity': self.content_similarity,
            'user_item_matrix': self.user_item_matrix,
            'item_features': self.item_features
        }
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        # Save the model
        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)
    
    def _load_model(self):
        """Load the trained model from disk"""
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.product_data = model_data['product_data']
            self.content_similarity = model_data['content_similarity']
            self.user_item_matrix = model_data['user_item_matrix']
            self.item_features = model_data['item_features']
            
            self.logger.info(f"Loaded recommender model with {len(self.product_data)} products")
            
        except Exception as e:
            self.logger.error(f"Error loading recommender model: {str(e)}")