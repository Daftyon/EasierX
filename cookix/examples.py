"""
Example Usage Scripts for VectorDB Laboratory
Demonstrates various distance metrics and database operations
"""

import numpy as np
import sys
sys.path.append('.')

from core.vector_db import VectorDB, DistanceMetric


def example_1_basic_usage():
    """Basic VectorDB usage example"""
    print("=" * 60)
    print("Example 1: Basic VectorDB Usage")
    print("=" * 60)
    
    # Create a 3D vector database
    db = VectorDB(dimension=3, metric=DistanceMetric.EUCLIDEAN)
    
    # Add some vectors
    vectors = [
        ("point_a", [1.0, 2.0, 3.0], {"label": "A", "category": "cluster1"}),
        ("point_b", [1.5, 2.1, 3.2], {"label": "B", "category": "cluster1"}),
        ("point_c", [5.0, 6.0, 7.0], {"label": "C", "category": "cluster2"}),
        ("point_d", [5.2, 6.1, 7.3], {"label": "D", "category": "cluster2"}),
        ("point_e", [0.0, 0.0, 0.0], {"label": "E", "category": "origin"}),
    ]
    
    for vector_id, vector, metadata in vectors:
        db.add_vector(vector_id, np.array(vector), metadata)
    
    print(f"\nDatabase created: {db}")
    print(f"Total vectors: {len(db)}")
    
    # Query for nearest neighbors
    query = np.array([1.2, 2.0, 3.1])
    results = db.query(query, k=3)
    
    print(f"\nQuery vector: {query}")
    print("\nTop 3 nearest neighbors:")
    for i, (entry, distance) in enumerate(results, 1):
        print(f"{i}. {entry.id}: distance={distance:.4f}, vector={entry.vector}, metadata={entry.metadata}")


def example_2_distance_metrics_comparison():
    """Compare different distance metrics on the same data"""
    print("\n" + "=" * 60)
    print("Example 2: Distance Metrics Comparison")
    print("=" * 60)
    
    # Sample vectors
    vectors = [
        ("vec1", [1, 2, 3]),
        ("vec2", [4, 5, 6]),
        ("vec3", [7, 8, 9]),
        ("vec4", [2, 3, 4]),
    ]
    
    query = np.array([3, 4, 5])
    
    # Test different metrics
    metrics = [
        DistanceMetric.EUCLIDEAN,
        DistanceMetric.COSINE,
        DistanceMetric.MANHATTAN,
        DistanceMetric.CHEBYSHEV,
    ]
    
    print(f"\nQuery vector: {query}")
    print("\nResults for each metric:")
    
    for metric in metrics:
        db = VectorDB(dimension=3, metric=metric)
        for vec_id, vec in vectors:
            db.add_vector(vec_id, np.array(vec))
        
        results = db.query(query, k=2)
        
        print(f"\n{metric.value.upper()}:")
        for i, (entry, distance) in enumerate(results, 1):
            print(f"  {i}. {entry.id}: distance={distance:.4f}")


def example_3_custom_metrics():
    """Demonstrate custom distance metrics"""
    print("\n" + "=" * 60)
    print("Example 3: Custom Distance Metrics")
    print("=" * 60)
    
    # Create databases with custom metrics
    db_adaptive = VectorDB(dimension=4, metric=DistanceMetric.CUSTOM_ADAPTIVE)
    db_weighted = VectorDB(dimension=4, metric=DistanceMetric.CUSTOM_WEIGHTED)
    
    # Add vectors
    vectors = [
        ("feature_a", [1.0, 2.0, 3.0, 4.0]),
        ("feature_b", [2.0, 3.0, 4.0, 5.0]),
        ("feature_c", [5.0, 6.0, 7.0, 8.0]),
        ("feature_d", [1.1, 2.1, 3.1, 4.1]),
    ]
    
    for vec_id, vec in vectors:
        db_adaptive.add_vector(vec_id, np.array(vec))
        db_weighted.add_vector(vec_id, np.array(vec))
    
    query = np.array([1.5, 2.5, 3.5, 4.5])
    
    # Custom Adaptive metric
    print("\nCUSTOM ADAPTIVE METRIC:")
    results_adaptive = db_adaptive.query(query, k=3)
    for i, (entry, distance) in enumerate(results_adaptive, 1):
        print(f"{i}. {entry.id}: distance={distance:.4f}")
    
    # Custom Weighted metric with emphasis on first dimensions
    print("\nCUSTOM WEIGHTED METRIC (emphasizing first 2 dimensions):")
    weights = np.array([2.0, 2.0, 0.5, 0.5])  # Weights for each dimension
    results_weighted = db_weighted.query(query, k=3, weights=weights)
    for i, (entry, distance) in enumerate(results_weighted, 1):
        print(f"{i}. {entry.id}: distance={distance:.4f}")


def example_4_filtering():
    """Demonstrate filtered queries"""
    print("\n" + "=" * 60)
    print("Example 4: Filtered Queries")
    print("=" * 60)
    
    db = VectorDB(dimension=3, metric=DistanceMetric.EUCLIDEAN)
    
    # Add vectors with different categories
    vectors = [
        ("cat_a_1", [1, 1, 1], {"category": "A", "priority": "high"}),
        ("cat_a_2", [1.5, 1.5, 1.5], {"category": "A", "priority": "low"}),
        ("cat_b_1", [2, 2, 2], {"category": "B", "priority": "high"}),
        ("cat_b_2", [2.5, 2.5, 2.5], {"category": "B", "priority": "low"}),
        ("cat_c_1", [3, 3, 3], {"category": "C", "priority": "high"}),
    ]
    
    for vec_id, vec, meta in vectors:
        db.add_vector(vec_id, np.array(vec), meta)
    
    query = np.array([2, 2, 2])
    
    # Query all vectors
    print(f"\nQuery: {query}")
    print("\nAll results:")
    results = db.query(query, k=5)
    for i, (entry, distance) in enumerate(results, 1):
        print(f"{i}. {entry.id}: distance={distance:.4f}, metadata={entry.metadata}")
    
    # Query only category A
    print("\nFiltered results (category='A' only):")
    results_filtered = db.query(
        query, 
        k=5, 
        filter_fn=lambda entry: entry.metadata.get('category') == 'A'
    )
    for i, (entry, distance) in enumerate(results_filtered, 1):
        print(f"{i}. {entry.id}: distance={distance:.4f}, metadata={entry.metadata}")
    
    # Query only high priority
    print("\nFiltered results (priority='high' only):")
    results_priority = db.query(
        query,
        k=5,
        filter_fn=lambda entry: entry.metadata.get('priority') == 'high'
    )
    for i, (entry, distance) in enumerate(results_priority, 1):
        print(f"{i}. {entry.id}: distance={distance:.4f}, metadata={entry.metadata}")


def example_5_batch_operations():
    """Demonstrate batch operations"""
    print("\n" + "=" * 60)
    print("Example 5: Batch Operations")
    print("=" * 60)
    
    db = VectorDB(dimension=5, metric=DistanceMetric.MANHATTAN)
    
    # Generate batch of random vectors
    batch_size = 100
    batch = []
    
    for i in range(batch_size):
        vector_id = f"batch_vec_{i}"
        vector = np.random.randn(5)
        metadata = {"batch": "batch_1", "index": i}
        batch.append((vector_id, vector, metadata))
    
    # Add batch
    count = db.add_batch(batch)
    print(f"\nAdded {count} vectors in batch")
    
    # Query performance
    query = np.random.randn(5)
    results = db.query(query, k=10)
    
    print(f"\nTop 10 results from {len(db)} vectors:")
    for i, (entry, distance) in enumerate(results, 1):
        print(f"{i}. {entry.id}: distance={distance:.4f}")
    
    # Database statistics
    stats = db.get_stats()
    print(f"\nDatabase statistics:")
    print(f"  Total vectors: {stats['total_vectors']}")
    print(f"  Total queries: {stats['total_queries']}")


def example_6_save_load():
    """Demonstrate saving and loading databases"""
    print("\n" + "=" * 60)
    print("Example 6: Save and Load Database")
    print("=" * 60)
    
    # Create and populate database
    db = VectorDB(dimension=3, metric=DistanceMetric.COSINE)
    
    for i in range(20):
        vector_id = f"saved_vec_{i}"
        vector = np.random.randn(3)
        metadata = {"index": i, "type": "saved"}
        db.add_vector(vector_id, vector, metadata)
    
    print(f"Created database with {len(db)} vectors")
    
    # Save to disk
    filepath = "example_db.pkl"  # Save in current directory
    db.save(filepath)
    print(f"\nDatabase saved to {filepath}")
    
    # Load from disk
    loaded_db = VectorDB.load(filepath)
    print(f"Database loaded: {loaded_db}")
    print(f"Vectors in loaded DB: {len(loaded_db)}")
    
    # Verify functionality
    query = np.random.randn(3)
    results = loaded_db.query(query, k=5)
    
    print(f"\nQuery on loaded database:")
    for i, (entry, distance) in enumerate(results, 1):
        print(f"{i}. {entry.id}: distance={distance:.4f}")


def example_7_high_dimensional():
    """Work with high-dimensional vectors"""
    print("\n" + "=" * 60)
    print("Example 7: High-Dimensional Vectors")
    print("=" * 60)
    
    # Create 128-dimensional database (similar to embeddings)
    dimension = 128
    db = VectorDB(dimension=dimension, metric=DistanceMetric.COSINE)
    
    print(f"Created {dimension}-dimensional vector database")
    
    # Add random vectors
    num_vectors = 1000
    for i in range(num_vectors):
        vector = np.random.randn(dimension)
        # Normalize for cosine similarity
        vector = vector / np.linalg.norm(vector)
        db.add_vector(f"embed_{i}", vector, {"type": "embedding"})
    
    print(f"Added {num_vectors} normalized vectors")
    
    # Query
    query = np.random.randn(dimension)
    query = query / np.linalg.norm(query)
    
    results = db.query(query, k=5)
    
    print(f"\nTop 5 similar vectors (cosine distance):")
    for i, (entry, distance) in enumerate(results, 1):
        similarity = 1 - distance  # Convert distance to similarity
        print(f"{i}. {entry.id}: similarity={similarity:.4f}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("VectorDB Laboratory - Example Usage Scripts")
    print("="*60)
    
    example_1_basic_usage()
    example_2_distance_metrics_comparison()
    example_3_custom_metrics()
    example_4_filtering()
    example_5_batch_operations()
    example_6_save_load()
    example_7_high_dimensional()
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60)
