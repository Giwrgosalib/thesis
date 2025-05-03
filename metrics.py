import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import os
import json
import logging
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
import re
from collections import Counter

# Ensure the metrics directory exists
METRICS_DIR = os.path.join('data', 'metrics')
os.makedirs(METRICS_DIR, exist_ok=True)

def analyze_feedback_data():
    """Analyze feedback log data to generate metrics and visualizations."""
    try:
        # Load feedback data
        feedback_path = os.path.join('data', 'feedback_log.csv')
        if not os.path.exists(feedback_path):
            logging.error(f"Feedback log file not found at {feedback_path}")
            return {"error": "Feedback data not available"}
            
        df = pd.read_csv(feedback_path)
        
        # 1. Entity Distribution Analysis
        entity_counts = {}
        for idx, row in df.iterrows():
            if isinstance(row['entities'], str):
                try:
                    entities = eval(row['entities'])
                    for _, _, label in entities:
                        entity_counts[label] = entity_counts.get(label, 0) + 1
                except:
                    continue
        
        plt.figure(figsize=(12, 6))
        plt.bar(entity_counts.keys(), entity_counts.values())
        plt.xticks(rotation=45)
        plt.title('Entity Type Distribution in Dataset')
        plt.tight_layout()
        plt.savefig(os.path.join(METRICS_DIR, 'entity_distribution.png'))
        plt.close()
        
        # 2. Intent Distribution
        intent_counts = df['intent'].value_counts()
        plt.figure(figsize=(12, 6))
        plt.bar(intent_counts.index, intent_counts.values)
        plt.xticks(rotation=45)
        plt.title('Intent Distribution in Dataset')
        plt.tight_layout()
        plt.savefig(os.path.join(METRICS_DIR, 'intent_distribution.png'))
        plt.close()
        
        # 3. Query Complexity Analysis
        df['query_length'] = df['query'].apply(lambda x: len(str(x).split()))
        df['entity_count'] = df['entities'].apply(lambda x: len(eval(x)) if isinstance(x, str) and x.strip() else 0)
        
        plt.figure(figsize=(10, 6))
        plt.scatter(df['query_length'], df['entity_count'], alpha=0.5)
        plt.title('Query Length vs. Number of Entities')
        plt.xlabel('Number of Words in Query')
        plt.ylabel('Number of Entities')
        plt.savefig(os.path.join(METRICS_DIR, 'query_complexity.png'))
        plt.close()
        
        # 4. Price Range Analysis
        price_range_queries = df[df['entities'].apply(
            lambda x: isinstance(x, str) and 'PRICE_RANGE' in x
        )]
        
        # Count types of price range expressions
        price_patterns = {
            'under': r'(under|below|less than)\s*\$?(\d+)',
            'over': r'(over|above|more than)\s*\$?(\d+)',
            'between': r'between\s*\$?(\d+)\s*and\s*\$?(\d+)'
        }
        
        pattern_counts = {pattern: 0 for pattern in price_patterns}
        
        for query in price_range_queries['query']:
            for pattern, regex in price_patterns.items():
                if re.search(regex, query, re.IGNORECASE):
                    pattern_counts[pattern] += 1
                    break
        
        plt.figure(figsize=(10, 6))
        plt.bar(pattern_counts.keys(), pattern_counts.values())
        plt.title('Price Range Expression Patterns')
        plt.ylabel('Frequency')
        plt.savefig(os.path.join(METRICS_DIR, 'price_range_patterns.png'))
        plt.close()
        
        # Summary statistics
        metrics = {
            "total_queries": len(df),
            "unique_intents": len(intent_counts),
            "entity_distribution": entity_counts,
            "intent_distribution": intent_counts.to_dict(),
            "avg_query_length": df['query_length'].mean(),
            "avg_entities_per_query": df['entity_count'].mean(),
            "price_range_patterns": pattern_counts
        }
        
        # Save metrics as JSON
        with open(os.path.join(METRICS_DIR, 'metrics_summary.json'), 'w') as f:
            json.dump(metrics, f, indent=2)
            
        return {
            "metrics": metrics,
            "visualizations": {
                "entity_distribution": "/data/metrics/entity_distribution.png",
                "intent_distribution": "/data/metrics/intent_distribution.png",
                "query_complexity": "/data/metrics/query_complexity.png",
                "price_range_patterns": "/data/metrics/price_range_patterns.png"
            }
        }
    
    except Exception as e:
        logging.error(f"Error generating metrics: {e}", exc_info=True)
        return {"error": f"Failed to generate metrics: {str(e)}"}

def analyze_user_preferences(preferences_collection):
    """Analyze user preferences stored in MongoDB."""
    if preferences_collection is None:
        return {"error": "MongoDB collection not available"}
    
    try:
        # Fetch all user preferences
        all_prefs = list(preferences_collection.find({}))
        
        if not all_prefs:
            return {"error": "No user preference data available"}
        
        # Brand preferences analysis
        brand_counts = Counter()
        for user in all_prefs:
            if 'preferred_brands' in user:
                brand_counts.update(user['preferred_brands'])
        
        top_brands = brand_counts.most_common(10)
        brands, brand_frequencies = zip(*top_brands) if top_brands else ([], [])
        
        plt.figure(figsize=(12, 6))
        plt.bar(brands, brand_frequencies)
        plt.xticks(rotation=45)
        plt.title('Top 10 Preferred Brands')
        plt.tight_layout()
        plt.savefig(os.path.join(METRICS_DIR, 'top_brands.png'))
        plt.close()
        
        # Category preferences analysis
        category_counts = Counter()
        for user in all_prefs:
            if 'preferred_categories' in user:
                category_counts.update(user['preferred_categories'])
        
        top_categories = category_counts.most_common(10)
        categories, category_frequencies = zip(*top_categories) if top_categories else ([], [])
        
        plt.figure(figsize=(12, 6))
        plt.bar(categories, category_frequencies)
        plt.xticks(rotation=45)
        plt.title('Top 10 Preferred Categories')
        plt.tight_layout()
        plt.savefig(os.path.join(METRICS_DIR, 'top_categories.png'))
        plt.close()
        
        # User search history analysis
        queries_per_user = []
        for user in all_prefs:
            if 'search_history' in user:
                queries_per_user.append(len(user['search_history']))
        
        plt.figure(figsize=(10, 6))
        plt.hist(queries_per_user, bins=10)
        plt.title('Distribution of Queries per User')
        plt.xlabel('Number of Queries')
        plt.ylabel('Number of Users')
        plt.savefig(os.path.join(METRICS_DIR, 'queries_per_user.png'))
        plt.close()
        
        # Summary statistics
        metrics = {
            "total_users": len(all_prefs),
            "top_brands": dict(top_brands),
            "top_categories": dict(top_categories),
            "avg_queries_per_user": np.mean(queries_per_user) if queries_per_user else 0
        }
        
        # Save metrics as JSON
        with open(os.path.join(METRICS_DIR, 'user_metrics.json'), 'w') as f:
            json.dump(metrics, f, indent=2)
            
        return {
            "metrics": metrics,
            "visualizations": {
                "top_brands": "/data/metrics/top_brands.png",
                "top_categories": "/data/metrics/top_categories.png",
                "queries_per_user": "/data/metrics/queries_per_user.png"
            }
        }
    
    except Exception as e:
        logging.error(f"Error generating user preference metrics: {e}", exc_info=True)
        return {"error": f"Failed to generate user metrics: {str(e)}"}

def analyze_training_dataset():
    """Analyze the training dataset (dataset.csv) to generate metrics and visualizations."""
    try:
        # Load training data
        dataset_path = os.path.join('data', 'dataset.csv')
        if not os.path.exists(dataset_path):
            logging.error(f"Training dataset not found at {dataset_path}")
            return {"error": "Training dataset not available"}
            
        df = pd.read_csv(dataset_path)
        
        # 1. Dataset Size
        dataset_size = len(df)
        
        # 2. Intent Distribution Analysis
        intent_counts = df['intent'].value_counts()
        plt.figure(figsize=(12, 6))
        plt.bar(intent_counts.index, intent_counts.values)
        plt.xticks(rotation=45)
        plt.title('Intent Distribution in Training Dataset')
        plt.tight_layout()
        plt.savefig(os.path.join(METRICS_DIR, 'training_intent_distribution.png'))
        plt.close()
        
        # 3. Entity Distribution Analysis
        entity_counts = {}
        for idx, row in df.iterrows():
            if isinstance(row['entities'], str):
                try:
                    entities = eval(row['entities'])
                    for _, _, label in entities:
                        entity_counts[label] = entity_counts.get(label, 0) + 1
                except:
                    continue
        
        # Sort by frequency
        entity_counts = {k: v for k, v in sorted(entity_counts.items(), key=lambda item: item[1], reverse=True)}
        
        plt.figure(figsize=(15, 8))
        plt.bar(entity_counts.keys(), entity_counts.values())
        plt.xticks(rotation=90)
        plt.title('Entity Type Distribution in Training Dataset')
        plt.tight_layout()
        plt.savefig(os.path.join(METRICS_DIR, 'training_entity_distribution.png'))
        plt.close()
        
        # 4. Query Length and Entity Count Analysis
        df['query_length'] = df['query'].apply(lambda x: len(str(x).split()))
        df['entity_count'] = df['entities'].apply(lambda x: len(eval(x)) if isinstance(x, str) and x.strip() else 0)
        
        plt.figure(figsize=(10, 6))
        plt.hist(df['query_length'], bins=20)
        plt.title('Query Length Distribution')
        plt.xlabel('Number of Words in Query')
        plt.ylabel('Frequency')
        plt.savefig(os.path.join(METRICS_DIR, 'training_query_length.png'))
        plt.close()
        
        plt.figure(figsize=(10, 6))
        plt.hist(df['entity_count'], bins=10)
        plt.title('Entity Count Distribution')
        plt.xlabel('Number of Entities per Query')
        plt.ylabel('Frequency')
        plt.savefig(os.path.join(METRICS_DIR, 'training_entity_count.png'))
        plt.close()
        
        plt.figure(figsize=(10, 6))
        plt.scatter(df['query_length'], df['entity_count'], alpha=0.3)
        plt.title('Query Length vs. Number of Entities')
        plt.xlabel('Number of Words in Query')
        plt.ylabel('Number of Entities')
        plt.savefig(os.path.join(METRICS_DIR, 'training_query_complexity.png'))
        plt.close()
        
        # 5. Price Range Analysis
        price_range_queries = df[df['entities'].apply(
            lambda x: isinstance(x, str) and 'PRICE_RANGE' in x
        )]
        
        price_range_percent = (len(price_range_queries) / dataset_size) * 100
        
        # Count types of price range expressions
        price_patterns = {
            'under': r'(under|below|less than)\s*\$?(\d+)',
            'over': r'(over|above|more than)\s*\$?(\d+)',
            'between': r'between\s*\$?(\d+)\s*and\s*\$?(\d+)'
        }
        
        pattern_counts = {pattern: 0 for pattern in price_patterns}
        other_count = 0
        
        for query in price_range_queries['query']:
            matched = False
            for pattern, regex in price_patterns.items():
                if re.search(regex, query, re.IGNORECASE):
                    pattern_counts[pattern] += 1
                    matched = True
                    break
            if not matched:
                other_count += 1
                
        # Add "other" to pattern counts
        pattern_counts["other"] = other_count
        
        plt.figure(figsize=(10, 6))
        plt.bar(pattern_counts.keys(), pattern_counts.values())
        plt.title('Price Range Expression Patterns')
        plt.ylabel('Frequency')
        plt.savefig(os.path.join(METRICS_DIR, 'training_price_range_patterns.png'))
        plt.close()
        
        # 6. Most common entities by type
        top_entities_by_type = {}
        for idx, row in df.iterrows():
            if isinstance(row['entities'], str):
                try:
                    entities = eval(row['entities'])
                    for start, end, label in entities:
                        entity_text = row['query'][start:end]
                        if label not in top_entities_by_type:
                            top_entities_by_type[label] = Counter()
                        top_entities_by_type[label][entity_text.lower()] += 1
                except:
                    continue
        
        # Get top 10 most common entities for top entity types
        top_entity_types = ['BRAND', 'PRODUCT_TYPE', 'COLOR', 'MATERIAL', 'PRICE_RANGE']
        top_entities = {}
        
        for entity_type in top_entity_types:
            if entity_type in top_entities_by_type:
                top_entities[entity_type] = top_entities_by_type[entity_type].most_common(10)
        
        # Create visualizations for top entities
        for entity_type, entities in top_entities.items():
            if entities:
                labels, values = zip(*entities)
                plt.figure(figsize=(12, 6))
                plt.bar(labels, values)
                plt.xticks(rotation=90)
                plt.title(f'Top 10 Most Common {entity_type} Entities')
                plt.tight_layout()
                plt.savefig(os.path.join(METRICS_DIR, f'training_top_{entity_type.lower()}.png'))
                plt.close()
        
        # 7. Intent-Entity Co-occurrence Matrix for top intents and entities
        top_intents = intent_counts.index[:5].tolist()
        top_entity_labels = list(entity_counts.keys())[:10]
        
        # Create a co-occurrence matrix
        co_occurrence = np.zeros((len(top_intents), len(top_entity_labels)))
        
        for idx, row in df.iterrows():
            if row['intent'] in top_intents and isinstance(row['entities'], str):
                try:
                    entities = eval(row['entities'])
                    intent_idx = top_intents.index(row['intent'])
                    entity_types = [label for _, _, label in entities]
                    for entity_label in top_entity_labels:
                        if entity_label in entity_types:
                            entity_idx = top_entity_labels.index(entity_label)
                            co_occurrence[intent_idx, entity_idx] += 1
                except:
                    continue
        
        plt.figure(figsize=(12, 8))
        sns.heatmap(co_occurrence, annot=True, fmt="g", cmap="viridis", 
                    xticklabels=top_entity_labels, yticklabels=top_intents)
        plt.title('Intent-Entity Co-occurrence Matrix')
        plt.tight_layout()
        plt.savefig(os.path.join(METRICS_DIR, 'training_intent_entity_matrix.png'))
        plt.close()
        
        # Summary statistics
        metrics = {
            "dataset_size": dataset_size,
            "unique_intents": len(intent_counts),
            "unique_entity_types": len(entity_counts),
            "top_intents": intent_counts.head(10).to_dict(),
            "top_entity_types": {k: v for k, v in list(entity_counts.items())[:10]},
            "avg_query_length": float(df['query_length'].mean()),
            "avg_entities_per_query": float(df['entity_count'].mean()),
            "price_range_queries": len(price_range_queries),
            "price_range_percent": float(price_range_percent),
            "price_range_patterns": pattern_counts
        }
        
        # Save metrics as JSON
        with open(os.path.join(METRICS_DIR, 'training_dataset_metrics.json'), 'w') as f:
            json.dump(metrics, f, indent=2)
            
        return {
            "metrics": metrics,
            "visualizations": {
                "intent_distribution": "/data/metrics/training_intent_distribution.png",
                "entity_distribution": "/data/metrics/training_entity_distribution.png",
                "query_length": "/data/metrics/training_query_length.png",
                "entity_count": "/data/metrics/training_entity_count.png",
                "query_complexity": "/data/metrics/training_query_complexity.png",
                "price_range_patterns": "/data/metrics/training_price_range_patterns.png",
                "intent_entity_matrix": "/data/metrics/training_intent_entity_matrix.png",
                **{f"top_{entity_type.lower()}": f"/data/metrics/training_top_{entity_type.lower()}.png" for entity_type in top_entities.keys()}
            }
        }
    
    except Exception as e:
        logging.error(f"Error generating training dataset metrics: {e}", exc_info=True)
        return {"error": f"Failed to generate training dataset metrics: {str(e)}"}
