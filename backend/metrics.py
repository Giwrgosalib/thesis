"""
Metrics module for eBay AI Chatbot
Provides functions for analyzing feedback data, user preferences, and training datasets
"""

import os
import json
import pandas as pd
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

def analyze_feedback_data() -> Dict[str, Any]:
    """
    Analyze feedback data from the feedback log
    Returns metrics about user feedback and system performance
    """
    try:
        feedback_file = os.path.join('data', 'feedback_log.csv')
        
        if not os.path.exists(feedback_file):
            logger.warning("Feedback log file not found")
            return {
                "status": "no_data",
                "message": "No feedback data available",
                "total_feedback": 0,
                "metrics": {}
            }
        
        # Read feedback data
        df = pd.read_csv(feedback_file)
        
        if df.empty:
            return {
                "status": "empty",
                "message": "Feedback data is empty",
                "total_feedback": 0,
                "metrics": {}
            }
        
        # Basic metrics
        total_feedback = len(df)
        avg_rating = df['rating'].mean() if 'rating' in df.columns else 0
        positive_feedback = len(df[df['rating'] > 3]) if 'rating' in df.columns else 0
        
        return {
            "status": "success",
            "total_feedback": total_feedback,
            "average_rating": round(avg_rating, 2),
            "positive_feedback_count": positive_feedback,
            "positive_feedback_percentage": round((positive_feedback / total_feedback) * 100, 2) if total_feedback > 0 else 0,
            "metrics": {
                "total_entries": total_feedback,
                "avg_rating": avg_rating,
                "positive_count": positive_feedback
            }
        }
        
    except Exception as e:
        logger.error(f"Error analyzing feedback data: {e}")
        return {
            "status": "error",
            "message": f"Error analyzing feedback: {str(e)}",
            "total_feedback": 0,
            "metrics": {}
        }

def analyze_user_preferences(preferences_collection) -> Dict[str, Any]:
    """
    Analyze user preferences from MongoDB collection
    Returns metrics about user behavior and preferences
    """
    try:
        if not preferences_collection:
            return {
                "status": "no_collection",
                "message": "Preferences collection not available",
                "total_users": 0,
                "metrics": {}
            }
        
        # Get total users
        total_users = preferences_collection.count_documents({})
        
        if total_users == 0:
            return {
                "status": "empty",
                "message": "No user preferences found",
                "total_users": 0,
                "metrics": {}
            }
        
        # Get sample of preferences for analysis
        sample_prefs = list(preferences_collection.find().limit(100))
        
        # Analyze common preferences
        categories = {}
        brands = {}
        price_ranges = {}
        
        for pref in sample_prefs:
            # Count categories
            if 'preferred_categories' in pref:
                for cat in pref['preferred_categories']:
                    categories[cat] = categories.get(cat, 0) + 1
            
            # Count brands
            if 'preferred_brands' in pref:
                for brand in pref['preferred_brands']:
                    brands[brand] = brands.get(brand, 0) + 1
            
            # Count price ranges
            if 'price_range' in pref:
                price_range = pref['price_range']
                price_ranges[price_range] = price_ranges.get(price_range, 0) + 1
        
        return {
            "status": "success",
            "total_users": total_users,
            "sample_size": len(sample_prefs),
            "top_categories": dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]),
            "top_brands": dict(sorted(brands.items(), key=lambda x: x[1], reverse=True)[:5]),
            "price_distribution": price_ranges,
            "metrics": {
                "total_users": total_users,
                "categories_count": len(categories),
                "brands_count": len(brands)
            }
        }
        
    except Exception as e:
        logger.error(f"Error analyzing user preferences: {e}")
        return {
            "status": "error",
            "message": f"Error analyzing preferences: {str(e)}",
            "total_users": 0,
            "metrics": {}
        }

def analyze_training_dataset() -> Dict[str, Any]:
    """
    Analyze the training dataset
    Returns metrics about the dataset composition and quality
    """
    try:
        # Check for refined dataset first
        refined_file = os.path.join('data', 'refined_balanced_dataset.csv')
        train_file = os.path.join('data', 'refined_balanced_dataset_train.csv')
        val_file = os.path.join('data', 'refined_balanced_dataset_val.csv')
        
        dataset_files = []
        if os.path.exists(refined_file):
            dataset_files.append(('refined_balanced', refined_file))
        if os.path.exists(train_file):
            dataset_files.append(('train', train_file))
        if os.path.exists(val_file):
            dataset_files.append(('validation', val_file))
        
        if not dataset_files:
            # Fallback to original files
            original_files = [
                ('training', os.path.join('data', 'training.csv')),
                ('validation', os.path.join('data', 'validation.csv')),
                ('train', os.path.join('data', 'train.csv'))
            ]
            
            for name, path in original_files:
                if os.path.exists(path):
                    dataset_files.append((name, path))
        
        if not dataset_files:
            return {
                "status": "no_data",
                "message": "No training dataset files found",
                "total_samples": 0,
                "metrics": {}
            }
        
        # Analyze the main dataset
        main_dataset = dataset_files[0]  # Use the first available dataset
        df = pd.read_csv(main_dataset[1])
        
        total_samples = len(df)
        
        # Basic metrics
        metrics = {
            "dataset_name": main_dataset[0],
            "total_samples": total_samples,
            "columns": list(df.columns),
            "file_path": main_dataset[1]
        }
        
        # Analyze intents if available
        if 'intent' in df.columns:
            intent_counts = df['intent'].value_counts().to_dict()
            metrics['intent_distribution'] = intent_counts
            metrics['unique_intents'] = len(intent_counts)
        
        # Analyze entities if available
        if 'entities' in df.columns:
            # Count non-null entities
            non_null_entities = df['entities'].notna().sum()
            metrics['samples_with_entities'] = non_null_entities
            metrics['entity_coverage'] = round((non_null_entities / total_samples) * 100, 2)
        
        # Analyze queries if available
        if 'query' in df.columns:
            avg_query_length = df['query'].str.len().mean()
            metrics['average_query_length'] = round(avg_query_length, 2)
        
        return {
            "status": "success",
            "total_samples": total_samples,
            "dataset_files": [name for name, _ in dataset_files],
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"Error analyzing training dataset: {e}")
        return {
            "status": "error",
            "message": f"Error analyzing dataset: {str(e)}",
            "total_samples": 0,
            "metrics": {}
        }

def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a comprehensive summary of all metrics
    """
    try:
        feedback_metrics = analyze_feedback_data()
        dataset_metrics = analyze_training_dataset()
        
        return {
            "status": "success",
            "timestamp": pd.Timestamp.now().isoformat(),
            "feedback": feedback_metrics,
            "dataset": dataset_metrics,
            "summary": {
                "total_feedback": feedback_metrics.get("total_feedback", 0),
                "total_samples": dataset_metrics.get("total_samples", 0),
                "system_health": "operational" if feedback_metrics.get("status") == "success" else "limited_data"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        return {
            "status": "error",
            "message": f"Error generating summary: {str(e)}",
            "summary": {
                "system_health": "error"
            }
        }
