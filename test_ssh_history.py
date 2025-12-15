#!/usr/bin/env python3
"""
Diagnostic script to test SSH history retrieval from your server
This will help identify WHY the listbox is empty
"""

import paramiko
import sys

def test_ssh_history(host, username, password=None, port=22):
    """Test SSH connection and history retrieval"""
    
    print(f"\n{'='*70}")
    print(f"  Testing SSH History Retrieval")
    print(f"{'='*70}\n")
    
    print(f"📡 Connecting to: {username}@{host}:{port}")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Connect
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=10
        )
        
        print("✅ SSH connection successful!\n")
        
        # Try multiple history commands
        commands = [
            ("history 200", "Standard history command"),
            ("cat ~/.bash_history | tail -n 200", "Bash history file"),
            ("cat ~/.zsh_history | tail -n 200", "Zsh history file"),
            ("fc -l -200", "fc command (alternative)"),
            ("HISTFILE=~/.bash_history; history -r; history 200", "Force reload bash history"),
        ]
        
        print("🔍 Testing different history retrieval methods:\n")
        print("-" * 70)
        
        for cmd, description in commands:
            print(f"\n📝 Testing: {description}")
            print(f"   Command: {cmd}")
            
            try:
                stdin, stdout, stderr = client.exec_command(cmd)
                output = stdout.read().decode('utf-8', errors='ignore')
                error = stderr.read().decode('utf-8', errors='ignore')
                
                if output and not error:
                    lines = [l for l in output.strip().split('\n') if l.strip()]
                    print(f"   ✅ SUCCESS! Got {len(lines)} lines")
                    
                    # Show first 5 lines
                    print(f"\n   📋 First 5 commands:")
                    for line in lines[:5]:
                        print(f"      {line[:80]}")
                    
                    if len(lines) >= 5:
                        print(f"\n   💡 This method works! Total: {len(lines)} commands")
                        print(f"\n{'='*70}")
                        print("✅ SOLUTION FOUND!")
                        print("='*70}\n")
                        print(f"Use this command in your code:")
                        print(f'   cmd = "{cmd}"')
                        print(f"\nThe listbox was empty because:")
                        print(f"  • The history command may not be working")
                        print(f"  • Try using this working command instead")
                        return True
                        
                elif error and "command not found" not in error.lower():
                    print(f"   ⚠️  Got error: {error[:100]}")
                elif not output:
                    print(f"   ❌ No output (history might be empty)")
                else:
                    print(f"   ❌ Failed: {error[:100]}")
                    
            except Exception as e:
                print(f"   ❌ Exception: {str(e)[:100]}")
        
        print(f"\n{'='*70}")
        print("❌ NO WORKING METHOD FOUND")
        print(f"{'='*70}\n")
        print("Possible reasons:")
        print("  1. Shell history is disabled on server")
        print("  2. History file doesn't exist")
        print("  3. Permissions issue")
        print("  4. Different shell than expected")
        print("\nTo fix:")
        print("  • SSH into the server manually")
        print("  • Run: echo $SHELL")
        print("  • Run: echo $HISTFILE")
        print("  • Run: cat $HISTFILE | wc -l")
        print("  • Check if history exists")
        
        return False
        
    except paramiko.AuthenticationException:
        print("❌ Authentication failed! Check username/password")
        return False
    except paramiko.SSHException as e:
        print(f"❌ SSH error: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    finally:
        client.close()

def main():
    """Main entry point"""
    
    print("\n" + "="*70)
    print(" SSH History Diagnostic Tool")
    print("="*70)
    
    # Your server details
    host = input("\nEnter server host (e.g., 172.22.15.72): ").strip()
    username = input("Enter username: ").strip()
    password = input("Enter password (or press Enter for key auth): ").strip()
    port_str = input("Enter SSH port (default 22): ").strip()
    
    port = int(port_str) if port_str else 22
    
    if not host or not username:
        print("\n❌ Host and username are required!")
        sys.exit(1)
    
    password = password if password else None
    
    # Test
    success = test_ssh_history(host, username, password, port)
    
    if success:
        print("\n✅ Diagnosis complete - Working solution found!")
        sys.exit(0)
    else:
        print("\n⚠️ Diagnosis complete - No working solution found")
        print("   History might be disabled or unavailable on this server")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(1)
