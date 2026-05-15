#!/usr/bin/env python3
"""
Custom Formula Tester - Interactive Console
Test your custom distance formulas before using them in the visualizer
"""

import numpy as np
from core.formula_editor import FormulaParser, CustomFormulaLibrary
from core.vector_db import VectorDB, DistanceMetric


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def show_templates():
    """Show all available formula templates"""
    print_header("Available Formula Templates")
    
    library = CustomFormulaLibrary()
    
    print("\n📚 STANDARD METRICS:")
    for name, info in library.TEMPLATES.items():
        print(f"\n  {info['name']}")
        print(f"    Formula: {info['formula']}")
        print(f"    Description: {info['description']}")
    
    print("\n🎨 CREATIVE EXAMPLES:")
    for name, info in library.CREATIVE_EXAMPLES.items():
        print(f"\n  {info['name']}")
        print(f"    Formula: {info['formula']}")
        print(f"    Description: {info['description']}")


def test_formula_interactive():
    """Interactive formula testing"""
    print_header("Interactive Formula Tester")
    
    parser = FormulaParser()
    
    print("\nEnter your custom formula (or 'help' for syntax guide):")
    print("Example: sqrt(sum((v1 - v2) ** 2))")
    print()
    
    formula = input("Formula: ").strip()
    
    if formula.lower() == 'help':
        print(CustomFormulaLibrary.get_help_text())
        return
    
    if not formula:
        print("❌ No formula entered")
        return
    
    # Validate
    print("\n🔍 Validating formula...")
    is_valid, message = parser.validate_formula(formula)
    
    if not is_valid:
        print(f"❌ Invalid: {message}")
        return
    
    print(f"✅ {message}")
    
    # Create function
    func = parser.create_distance_function(formula, "custom")
    
    # Test with sample vectors
    print("\n🧪 Testing with sample vectors:")
    print("-" * 70)
    
    test_cases = [
        ("Identical vectors", [1, 2, 3], [1, 2, 3]),
        ("Slightly different", [1, 2, 3], [1.1, 2.1, 3.1]),
        ("Very different", [1, 2, 3], [10, 20, 30]),
        ("Origin and unit", [0, 0, 0], [1, 1, 1]),
        ("Perpendicular", [1, 0, 0], [0, 1, 0]),
        ("Opposite direction", [1, 2, 3], [-1, -2, -3]),
    ]
    
    for name, v1, v2 in test_cases:
        v1_arr = np.array(v1)
        v2_arr = np.array(v2)
        
        try:
            result = func(v1_arr, v2_arr)
            print(f"\n  {name}:")
            print(f"    v1 = {v1}")
            print(f"    v2 = {v2}")
            print(f"    distance = {result:.6f}")
        except Exception as e:
            print(f"\n  {name}: ❌ Error - {e}")
    
    print("\n" + "-" * 70)
    
    # Compare with standard metrics
    print("\n📊 Comparison with Standard Metrics:")
    print("-" * 70)
    
    v1 = np.array([1, 2, 3])
    v2 = np.array([4, 5, 6])
    
    print(f"\nTest vectors: v1={v1}, v2={v2}")
    print(f"\nYour formula:     {func(v1, v2):.6f}")
    
    # Compare with standards
    db = VectorDB(dimension=3)
    db.add_vector("v1", v1)
    db.add_vector("v2", v2)
    
    for metric in [DistanceMetric.EUCLIDEAN, DistanceMetric.MANHATTAN, 
                   DistanceMetric.COSINE, DistanceMetric.CHEBYSHEV]:
        db.metric = metric
        results = db.query(v1, k=1)
        if results:
            dist = results[0][1]
            print(f"{metric.value:15s}: {dist:.6f}")


def compare_formulas():
    """Compare multiple formulas side by side"""
    print_header("Formula Comparison Tool")
    
    parser = FormulaParser()
    library = CustomFormulaLibrary()
    
    # Get formulas to compare
    print("\nAvailable formulas:")
    templates = list(library.TEMPLATES.keys())[:5]  # First 5
    for i, name in enumerate(templates, 1):
        info = library.TEMPLATES[name]
        print(f"  {i}. {info['name']}")
    
    print(f"  6. Enter custom formula")
    
    print("\nSelect formulas to compare (comma-separated, e.g., 1,2,3):")
    selection = input("Selection: ").strip()
    
    # Parse selection
    try:
        indices = [int(x.strip()) for x in selection.split(',')]
    except:
        print("❌ Invalid selection")
        return
    
    # Collect formulas
    formulas_to_test = []
    
    for idx in indices:
        if 1 <= idx <= 5:
            template_name = templates[idx - 1]
            info = library.TEMPLATES[template_name]
            formulas_to_test.append((info['name'], info['formula']))
        elif idx == 6:
            custom = input("Enter custom formula: ").strip()
            if custom:
                formulas_to_test.append(("Custom", custom))
    
    if not formulas_to_test:
        print("❌ No valid formulas selected")
        return
    
    # Test vectors
    test_cases = [
        ("Close vectors", [1, 2, 3], [1.1, 2.1, 3.1]),
        ("Far vectors", [1, 2, 3], [10, 20, 30]),
        ("Perpendicular", [1, 0, 0], [0, 1, 0]),
    ]
    
    # Compare
    print("\n" + "=" * 70)
    print("  Comparison Results")
    print("=" * 70)
    
    for test_name, v1, v2 in test_cases:
        print(f"\n📍 {test_name}: {v1} <-> {v2}")
        print("-" * 70)
        
        v1_arr = np.array(v1)
        v2_arr = np.array(v2)
        
        results = []
        for name, formula in formulas_to_test:
            is_valid, msg = parser.validate_formula(formula)
            if is_valid:
                func = parser.create_distance_function(formula, name)
                try:
                    dist = func(v1_arr, v2_arr)
                    results.append((name, dist))
                except Exception as e:
                    results.append((name, f"Error: {e}"))
            else:
                results.append((name, f"Invalid: {msg}"))
        
        # Print sorted by distance
        valid_results = [(n, d) for n, d in results if isinstance(d, (int, float))]
        invalid_results = [(n, d) for n, d in results if not isinstance(d, (int, float))]
        
        valid_results.sort(key=lambda x: x[1])
        
        for name, dist in valid_results:
            print(f"  {name:30s}: {dist:.6f}")
        
        for name, error in invalid_results:
            print(f"  {name:30s}: {error}")


def batch_test_formula():
    """Test a formula with random vectors"""
    print_header("Batch Formula Tester")
    
    parser = FormulaParser()
    
    formula = input("\nEnter formula to test: ").strip()
    
    if not formula:
        print("❌ No formula entered")
        return
    
    is_valid, message = parser.validate_formula(formula)
    if not is_valid:
        print(f"❌ Invalid: {message}")
        return
    
    print(f"✅ Formula valid!")
    
    func = parser.create_distance_function(formula, "batch_test")
    
    # Generate random vectors
    num_tests = int(input("Number of test pairs (default 10): ").strip() or "10")
    dimension = int(input("Vector dimension (default 3): ").strip() or "3")
    
    print(f"\n🧪 Testing {num_tests} random {dimension}D vector pairs...")
    print("-" * 70)
    
    for i in range(num_tests):
        v1 = np.random.randn(dimension)
        v2 = np.random.randn(dimension)
        
        try:
            dist = func(v1, v2)
            print(f"  Test {i+1:2d}: distance = {dist:10.6f}")
        except Exception as e:
            print(f"  Test {i+1:2d}: ❌ Error - {e}")
            break
    
    print("-" * 70)
    print("✅ Batch test complete!")


def main_menu():
    """Main interactive menu"""
    while True:
        print("\n" + "=" * 70)
        print("  VectorDB Laboratory - Custom Formula Tester")
        print("=" * 70)
        print("\n1. View formula templates")
        print("2. Test a custom formula (interactive)")
        print("3. Compare multiple formulas")
        print("4. Batch test a formula")
        print("5. Show syntax help")
        print("6. Exit")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            show_templates()
        elif choice == '2':
            test_formula_interactive()
        elif choice == '3':
            compare_formulas()
        elif choice == '4':
            batch_test_formula()
        elif choice == '5':
            print(CustomFormulaLibrary.get_help_text())
        elif choice == '6':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid option")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Custom Formula Tester" + " " * 32 + "║")
    print("╚" + "=" * 68 + "╝")
    
    main_menu()
