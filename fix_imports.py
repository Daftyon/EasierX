import os
from pathlib import Path

def replace_in_file(file_path):
    """Replace PySide6 with PySide6 in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'PySide6' in content:
            new_content = content.replace('PySide6', 'PySide6')
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ Updated: {file_path}")
            return True
    except Exception as e:
        print(f"❌ Error in {file_path}: {e}")
    
    return False

def main():
    # Find all Python files
    python_files = []
    
    for root, dirs, files in os.walk('.'):
        # Skip virtual environment
        if 'env' in root or 'venv' in root or '__pycache__' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"Found {len(python_files)} Python files")
    
    updated = 0
    for file_path in python_files:
        if replace_in_file(file_path):
            updated += 1
    
    print(f"\n✅ Updated {updated} files!")
    print("Run: python main.py")

if __name__ == '__main__':
    main()
