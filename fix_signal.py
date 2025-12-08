import os

def replace_signal_in_file(file_path):
    """Replace Signal with Signal in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'Signal' in content:
            # Replace import statement
            content = content.replace(
                'from PySide6.QtCore import Qt, QThread, Signal',
                'from PySide6.QtCore import Qt, QThread, Signal'
            )
            
            # Replace any standalone Signal usage
            content = content.replace('Signal', 'Signal')
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Fixed: {file_path}")
            return True
    except Exception as e:
        print(f"❌ Error in {file_path}: {e}")
    
    return False

def main():
    # Find all Python files in ui/ and root
    python_files = []
    
    for root, dirs, files in os.walk('.'):
        if 'env' in root or 'venv' in root or '__pycache__' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"Scanning {len(python_files)} files...")
    
    fixed = 0
    for file_path in python_files:
        if replace_signal_in_file(file_path):
            fixed += 1
    
    print(f"\n✅ Fixed {fixed} files!")
    print("Run: python main.py")

if __name__ == '__main__':
    main()
