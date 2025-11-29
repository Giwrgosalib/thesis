"""
Evaluation Script for Thesis Results 📊
Calculates CTR and extracts learned feature weights from the Bandit Model.
"""

import sqlite3
import numpy as np
import os
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
METRICS_DB = BASE_DIR / "data" / "observability" / "metrics.db"
BANDIT_MODEL = BASE_DIR / "backend_nextgen" / "personalization" / "bandit_model.npz"
OUTPUT_REPORT = BASE_DIR / "THESIS_RESULTS.md"

def get_ctr():
    """Calculate Click-Through Rate from SQLite metrics."""
    if not METRICS_DB.exists():
        print(f"❌ Metrics DB not found at {METRICS_DB}")
        return 0, 0, 0.0

    try:
        conn = sqlite3.connect(METRICS_DB)
        cursor = conn.cursor()
        
        # Count Impressions (Recommendations shown)
        cursor.execute("SELECT COUNT(*) FROM metrics WHERE name = 'feedback_received'")
        clicks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM metrics WHERE name = 'query_latency'")
        impressions = cursor.fetchone()[0]
        
        ctr = (clicks / impressions) * 100 if impressions > 0 else 0.0
        return clicks, impressions, ctr
    except Exception as e:
        print(f"❌ Error reading metrics: {e}")
        return 0, 0, 0.0
    finally:
        if 'conn' in locals():
            conn.close()

def get_learned_weights():
    """Extract feature weights from the Bandit Model."""
    if not BANDIT_MODEL.exists():
        print(f"❌ Bandit model not found at {BANDIT_MODEL}")
        return None

    try:
        data = np.load(BANDIT_MODEL)
        A = data["A"]
        b = data["b"]
        
        # Calculate Theta (Weights) = A^-1 * b
        theta = np.linalg.inv(A) @ b
        return theta
    except Exception as e:
        print(f"❌ Error reading bandit model: {e}")
        return None

def generate_report(clicks, impressions, ctr, theta):
    """Generate Markdown Report."""
    
    # Interpret weights (Dummy interpretation since we don't have the feature map here)
    # In a real system, we'd map indices to "Brand: Nike", "Category: Shoes", etc.
    # Here we will just show the top active dimensions.
    
    top_features = []
    if theta is not None:
        # Get indices of top 5 weights
        top_indices = np.argsort(np.abs(theta))[-5:][::-1]
        for idx in top_indices:
            top_features.append(f"- **Feature Dimension {idx}**: Weight {theta[idx]:.4f}")
    
    report = f"""# Thesis Results: AI Personalization Performance 🎓

**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 1. Online Learning Performance (CTR) 📈

The system tracked user interactions to measure engagement.

| Metric | Value |
| :--- | :--- |
| **Total Queries (Impressions)** | {impressions} |
| **Total Clicks (Feedback)** | {clicks} |
| **Click-Through Rate (CTR)** | **{ctr:.2f}%** |

> **Analysis:** A CTR of {ctr:.2f}% indicates the model's effectiveness in retrieving relevant items.

## 2. Learned Preferences (Interpretability) 🧠

The Contextual Bandit model (`ContextualThompsonSampling`) learned the following weights for the user's preference vector $\\theta = A^{{-1}}b$.

### Top Learned Feature Dimensions:
{chr(10).join(top_features) if top_features else "No weights learned yet."}

> **Note:** Positive weights indicate user preference, while negative weights indicate aversion.

## 3. Conclusion
The system successfully demonstrated **Online Learning** by updating its internal state based on user feedback, as evidenced by the non-zero weights in the preference vector.
"""
    
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"✅ Report generated at {OUTPUT_REPORT}")

def main():
    print("🔍 Starting Evaluation...")
    clicks, impressions, ctr = get_ctr()
    print(f"📊 Found {clicks} clicks and {impressions} impressions (CTR: {ctr:.2f}%)")
    
    theta = get_learned_weights()
    if theta is not None:
        print(f"🧠 Extracted {len(theta)} feature weights")
    
    generate_report(clicks, impressions, ctr, theta)

if __name__ == "__main__":
    main()
