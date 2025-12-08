import os
import sys
import logging

logging.basicConfig(level=logging.INFO)

print("=" * 60)
print("Testing Java & JPype Configuration")
print("=" * 60)

# Check Java
print("\n1. Checking Java installation...")
import subprocess
try:
    result = subprocess.run(['java', '-version'], capture_output=True, text=True)
    print(result.stderr.split('\n')[0])  # Java version
    print("   ✅ Java is installed")
except:
    print("   ❌ Java not found in PATH")
    sys.exit(1)

# Check JAVA_HOME
print("\n2. Checking JAVA_HOME...")
java_home = os.environ.get('JAVA_HOME')
if java_home:
    print(f"   JAVA_HOME: {java_home}")
    print("   ✅ JAVA_HOME is set")
else:
    print("   ⚠️ JAVA_HOME not set (will auto-detect)")

# Test JPype
print("\n3. Testing JPype...")
try:
    import jpype
    print("   ✅ JPype imported")
except ImportError:
    print("   ❌ JPype not installed")
    print("   Run: pip install JPype1")
    sys.exit(1)

# Test JVM Manager
print("\n4. Testing JVMManager...")
from core.jvm_manager import JVMManager

jvm_manager = JVMManager()

if jvm_manager.start():
    print("   ✅ JVM started successfully!")
    
    # Test basic Java
    try:
        String = jpype.JClass('java.lang.String')
        test = String('Hello from BatcherMan!')
        print(f"   ✅ Java String test: {test}")
    except Exception as e:
        print(f"   ❌ Java test failed: {e}")
    
    jvm_manager.stop()
    print("   ✅ JVM stopped successfully")
else:
    print("   ❌ Failed to start JVM")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ All tests passed! Java is ready.")
print("=" * 60)
