#!/usr/bin/env python3
"""
Prerequisite Checker for Informix Database Studio
Verifies all required components are installed and configured
"""

import sys
import subprocess
import platform

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_status(check_name, status, message=""):
    """Print check status"""
    status_icon = "✓" if status else "✗"
    status_text = "PASS" if status else "FAIL"
    color = "\033[92m" if status else "\033[91m"
    reset = "\033[0m"
    
    print(f"{color}{status_icon} {check_name}: {status_text}{reset}")
    if message:
        print(f"  → {message}")

def check_python_version():
    """Check Python version"""
    print_header("Python Version Check")
    
    version = sys.version_info
    required = (3, 8)
    
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print(f"  Detected: Python {version_str}")
    print(f"  Required: Python {required[0]}.{required[1]}+")
    
    if version >= required:
        print_status("Python Version", True, "Version is compatible")
        return True
    else:
        print_status("Python Version", False, "Please upgrade to Python 3.8 or higher")
        return False

def check_pip():
    """Check if pip is installed"""
    print_header("Pip Package Manager Check")
    
    try:
        result = subprocess.run(['pip', '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        
        if result.returncode == 0:
            print(f"  {result.stdout.strip()}")
            print_status("Pip", True, "Pip is installed and working")
            return True
        else:
            print_status("Pip", False, "Pip command failed")
            return False
            
    except FileNotFoundError:
        print_status("Pip", False, "Pip is not installed or not in PATH")
        return False
    except Exception as e:
        print_status("Pip", False, f"Error checking pip: {str(e)}")
        return False

def check_python_package(package_name):
    """Check if a Python package is installed"""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

def check_python_packages():
    """Check required Python packages"""
    print_header("Python Packages Check")
    
    packages = {
        'tkinter': 'Tkinter (GUI library)',
        'pyodbc': 'pyodbc (Database connectivity)',
        'pandas': 'pandas (Data manipulation)',
        'openpyxl': 'openpyxl (Excel export)'
    }
    
    all_installed = True
    missing_packages = []
    
    for package, description in packages.items():
        installed = check_python_package(package)
        print_status(description, installed)
        
        if not installed:
            all_installed = False
            missing_packages.append(package)
    
    if not all_installed:
        print("\n  To install missing packages:")
        if 'tkinter' in missing_packages:
            print("  - Tkinter: Install via system package manager")
            if platform.system() == "Linux":
                print("    Ubuntu/Debian: sudo apt-get install python3-tk")
                print("    Fedora/RHEL: sudo dnf install python3-tkinter")
            missing_packages.remove('tkinter')
        
        if missing_packages:
            print(f"  - pip install {' '.join(missing_packages)}")
    
    return all_installed

def check_odbc_driver():
    """Check if Informix ODBC driver is installed"""
    print_header("Informix ODBC Driver Check")
    
    system = platform.system()
    
    if system == "Linux":
        try:
            # Check using odbcinst
            result = subprocess.run(['odbcinst', '-q', '-d'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            
            if result.returncode == 0:
                drivers = result.stdout.lower()
                if 'informix' in drivers:
                    print("  Detected Informix ODBC driver:")
                    for line in result.stdout.split('\n'):
                        if 'informix' in line.lower():
                            print(f"    {line}")
                    print_status("Informix ODBC Driver", True, "Driver is installed")
                    return True
                else:
                    print("  Available drivers:")
                    print(result.stdout)
                    print_status("Informix ODBC Driver", False, 
                               "Informix driver not found in ODBC configuration")
                    return False
            else:
                print_status("ODBC Configuration", False, 
                           "Unable to query ODBC drivers")
                return False
                
        except FileNotFoundError:
            print_status("odbcinst", False, 
                       "odbcinst not found. Install unixODBC: sudo apt-get install unixodbc")
            return False
        except Exception as e:
            print_status("ODBC Driver Check", False, f"Error: {str(e)}")
            return False
            
    elif system == "Windows":
        try:
            # Try to import pyodbc and list drivers
            import pyodbc
            drivers = pyodbc.drivers()
            
            print("  Available ODBC drivers:")
            informix_found = False
            for driver in drivers:
                print(f"    - {driver}")
                if 'informix' in driver.lower():
                    informix_found = True
            
            if informix_found:
                print_status("Informix ODBC Driver", True, "Driver is installed")
                return True
            else:
                print_status("Informix ODBC Driver", False, 
                           "Informix driver not found. Install IBM Informix Client SDK")
                return False
                
        except ImportError:
            print_status("ODBC Driver Check", False, 
                       "pyodbc not installed. Cannot check drivers.")
            return False
        except Exception as e:
            print_status("ODBC Driver Check", False, f"Error: {str(e)}")
            return False
            
    else:
        print(f"  Unsupported platform: {system}")
        print_status("ODBC Driver Check", False, 
                   "Manual verification required for this platform")
        return False

def check_network_connectivity(host="8.8.8.8", port=53, timeout=3):
    """Check basic network connectivity"""
    print_header("Network Connectivity Check")
    
    import socket
    
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        print_status("Network", True, "Network connectivity is available")
        return True
    except socket.error:
        print_status("Network", False, 
                   "No network connectivity. Check your internet connection")
        return False

def print_recommendations(checks_passed):
    """Print final recommendations"""
    print_header("Summary and Recommendations")
    
    total_checks = len(checks_passed)
    passed_checks = sum(checks_passed.values())
    
    print(f"\n  Checks Passed: {passed_checks}/{total_checks}")
    
    if passed_checks == total_checks:
        print("\n  ✓ All checks passed! You're ready to use Informix Database Studio.")
        print("\n  Next steps:")
        print("    1. Run: python informix_studio.py")
        print("    2. Click 'Connect' and enter your database details")
        print("    3. Start querying!")
    else:
        print("\n  ✗ Some checks failed. Please address the issues above.")
        print("\n  Common solutions:")
        
        if not checks_passed.get('python_packages', False):
            print("    - Install missing Python packages:")
            print("      pip install pyodbc pandas openpyxl")
        
        if not checks_passed.get('odbc_driver', False):
            print("    - Install Informix ODBC driver:")
            print("      Download from: https://www.ibm.com/products/informix")
            if platform.system() == "Linux":
                print("      Also install unixODBC: sudo apt-get install unixodbc")
        
        if not checks_passed.get('python_version', False):
            print("    - Upgrade Python to version 3.8 or higher")
    
    print()

def main():
    """Main function"""
    print("\n" + "="*60)
    print("  Informix Database Studio - Prerequisite Checker")
    print("="*60)
    print(f"\n  Platform: {platform.system()} {platform.release()}")
    print(f"  Architecture: {platform.machine()}")
    
    checks = {}
    
    # Run all checks
    checks['python_version'] = check_python_version()
    checks['pip'] = check_pip()
    checks['python_packages'] = check_python_packages()
    checks['odbc_driver'] = check_odbc_driver()
    checks['network'] = check_network_connectivity()
    
    # Print summary
    print_recommendations(checks)
    
    # Exit code
    if all(checks.values()):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCheck cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        sys.exit(1)
