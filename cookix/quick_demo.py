#!/usr/bin/env python3
"""
Quick Start Demo for VectorDB Laboratory
Run this to see all features in action
"""

import numpy as np
from core.vector_db import VectorDB, DistanceMetric


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def demo_basic_operations():
    """Demonstrate basic VectorDB operations"""
    print_section("BASIC OPERATIONS")
    
    # Create database
    db = VectorDB(dimension=3, metric=DistanceMetric.EUCLIDEAN)
    print(f"✓ Created VectorDB: {db}")
    
    # Add vectors
    vectors = [
        ("home", [0, 0, 0], {"type": "origin"}),
        ("work", [5, 2, 1], {"type": "destination"}),
        ("gym", [2, 5, 3], {"type": "destination"}),
        ("cafe", [1, 1, 0], {"type": "destination"}),
    ]
    
    for vid, vec, meta in vectors:
        db.add_vector(vid, np.array(vec), meta)
    
    print(f"✓ Added {len(db)} vectors")
    
    # Query
    query_point = np.array([1, 1, 1])
    results = db.query(query_point, k=3)
    
    print(f"\n📍 Query point: {query_point}")
    print("🎯 Nearest neighbors:")
    for i, (entry, dist) in enumerate(results, 1):
        print(f"   {i}. {entry.id:8s} | distance: {dist:6.3f} | vector: {entry.vector}")


def demo_distance_metrics():
    """Compare different distance metrics"""
    print_section("DISTANCE METRICS COMPARISON")
    
    # Test vectors
    point_a = np.array([1, 2, 3])
    point_b = np.array([4, 5, 6])
    
    print(f"Vector A: {point_a}")
    print(f"Vector B: {point_b}\n")
    
    metrics_to_test = [
        DistanceMetric.EUCLIDEAN,
        DistanceMetric.MANHATTAN,
        DistanceMetric.COSINE,
        DistanceMetric.CHEBYSHEV,
        DistanceMetric.CANBERRA,
    ]
    
    for metric in metrics_to_test:
        db = VectorDB(dimension=3, metric=metric)
        db.add_vector("A", point_a)
        db.add_vector("B", point_b)
        
        results = db.query(point_a, k=2)
        distance_to_b = results[1][1]  # Second result is B
        
        print(f"{metric.value:15s}: {distance_to_b:.6f}")


def demo_custom_metric():
    """Demonstrate custom weighted distance"""
    print_section("CUSTOM WEIGHTED METRIC")
    
    db = VectorDB(dimension=4, metric=DistanceMetric.CUSTOM_WEIGHTED)
    
    # Add vectors
    vectors = {
        "balanced": [1, 1, 1, 1],
        "high_x": [5, 1, 1, 1],
        "high_y": [1, 5, 1, 1],
        "high_z": [1, 1, 5, 1],
        "high_w": [1, 1, 1, 5],
    }
    
    for name, vec in vectors.items():
        db.add_vector(name, np.array(vec))
    
    query = np.array([2, 2, 2, 2])
    
    # Query with equal weights
    print(f"\n📍 Query: {query}")
    print("\n1️⃣  Equal weights:")
    results = db.query(query, k=3, weights=np.array([1, 1, 1, 1]))
    for i, (entry, dist) in enumerate(results, 1):
        print(f"   {i}. {entry.id:12s}: {dist:.4f}")
    
    # Query with emphasis on first dimension
    print("\n2️⃣  Emphasize X dimension (weights=[5, 1, 1, 1]):")
    results = db.query(query, k=3, weights=np.array([5, 1, 1, 1]))
    for i, (entry, dist) in enumerate(results, 1):
        print(f"   {i}. {entry.id:12s}: {dist:.4f}")


def demo_filtering():
    """Demonstrate filtered queries"""
    print_section("FILTERED QUERIES")
    
    db = VectorDB(dimension=3, metric=DistanceMetric.EUCLIDEAN)
    
    # Add vectors with categories
    vectors = [
        ("restaurant_a", [1, 2, 0], {"category": "food", "rating": 4.5}),
        ("restaurant_b", [2, 3, 0], {"category": "food", "rating": 3.8}),
        ("gym_a", [3, 1, 0], {"category": "fitness", "rating": 4.2}),
        ("gym_b", [3, 2, 0], {"category": "fitness", "rating": 4.7}),
        ("cafe_a", [1, 1, 0], {"category": "food", "rating": 4.9}),
    ]
    
    for vid, vec, meta in vectors:
        db.add_vector(vid, np.array(vec), meta)
    
    query = np.array([2, 2, 0])
    
    print(f"📍 Query: {query}\n")
    
    # All results
    print("🔍 All results:")
    results = db.query(query, k=5)
    for i, (entry, dist) in enumerate(results, 1):
        cat = entry.metadata['category']
        rating = entry.metadata['rating']
        print(f"   {i}. {entry.id:15s} | {dist:.3f} | {cat:8s} | ★{rating}")
    
    # Filter by category
    print("\n🍽️  Food only:")
    results = db.query(query, k=5, filter_fn=lambda e: e.metadata['category'] == 'food')
    for i, (entry, dist) in enumerate(results, 1):
        rating = entry.metadata['rating']
        print(f"   {i}. {entry.id:15s} | {dist:.3f} | ★{rating}")
    
    # Filter by rating
    print("\n⭐ High rated (≥4.5) only:")
    results = db.query(query, k=5, filter_fn=lambda e: e.metadata['rating'] >= 4.5)
    for i, (entry, dist) in enumerate(results, 1):
        cat = entry.metadata['category']
        rating = entry.metadata['rating']
        print(f"   {i}. {entry.id:15s} | {dist:.3f} | {cat:8s} | ★{rating}")


def demo_batch_and_stats():
    """Demonstrate batch operations and statistics"""
    print_section("BATCH OPERATIONS & STATISTICS")
    
    db = VectorDB(dimension=10, metric=DistanceMetric.COSINE)
    
    # Generate batch
    batch_size = 500
    batch = []
    for i in range(batch_size):
        vec = np.random.randn(10)
        vec = vec / np.linalg.norm(vec)  # Normalize for cosine
        batch.append((f"vec_{i}", vec, {"batch": 1}))
    
    # Add batch
    count = db.add_batch(batch)
    print(f"✓ Added {count} vectors in batch\n")
    
    # Perform queries
    for _ in range(10):
        query = np.random.randn(10)
        query = query / np.linalg.norm(query)
        db.query(query, k=5)
    
    # Show statistics
    stats = db.get_stats()
    print("📊 Database Statistics:")
    print(f"   Total vectors: {stats['total_vectors']}")
    print(f"   Total queries: {stats['total_queries']}")
    print(f"   Dimension: {db.dimension}")
    print(f"   Metric: {db.metric.value}")


def demo_save_load():
    """Demonstrate persistence"""
    print_section("SAVE & LOAD DATABASE")
    
    # Create and populate
    db = VectorDB(dimension=5, metric=DistanceMetric.MANHATTAN)
    for i in range(20):
        vec = np.random.randn(5)
        db.add_vector(f"saved_{i}", vec, {"saved": True})
    
    print(f"✓ Created database with {len(db)} vectors")
    
    # Save
    filepath = "/home/claude/vectordb_lab/demo_db.pkl"
    db.save(filepath)
    print(f"✓ Saved to: {filepath}")
    
    # Load
    loaded = VectorDB.load(filepath)
    print(f"✓ Loaded: {loaded}")
    
    # Verify
    query = np.random.randn(5)
    results = loaded.query(query, k=3)
    print(f"\n✓ Query successful on loaded database:")
    for i, (entry, dist) in enumerate(results, 1):
        print(f"   {i}. {entry.id}: {dist:.4f}")


def main():
    """Run all demonstrations"""
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "VectorDB Laboratory - Quick Demo" + " "*20 + "║")
    print("╚" + "="*68 + "╝")
    
    try:
        demo_basic_operations()
        demo_distance_metrics()
        demo_custom_metric()
        demo_filtering()
        demo_batch_and_stats()
        demo_save_load()
        
        print("\n" + "="*70)
        print("✅ All demonstrations completed successfully!")
        print("="*70)
        
        print("\n💡 Next steps:")
        print("   • Run 'python examples.py' for more detailed examples")
        print("   • Run 'python gui/visualizer_app.py' to launch the 3D visualizer")
        print("   • Check README.md for full documentation")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
