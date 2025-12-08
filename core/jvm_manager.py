import jpype
import jpype.imports
from pathlib import Path
from typing import List, Optional
import logging
import os
import sys

class JVMManager:
    """Manages JVM lifecycle and classpath"""
    
    def __init__(self):
        self.jvm_started = False
        self.classpath = []
        self.logger = logging.getLogger(__name__)
    
    def add_to_classpath(self, path: str):
        """Add JAR or directory to classpath"""
        path_obj = Path(path)
        if path_obj.exists():
            self.classpath.append(str(path_obj.absolute()))
            self.logger.info(f"Added to classpath: {path}")
        else:
            self.logger.warning(f"Path not found: {path}")
    
    def add_spring_batch_dependencies(self):
        """Add common Spring Batch JARs to classpath"""
        lib_dir = Path('lib')
        if lib_dir.exists():
            for jar in lib_dir.glob('*.jar'):
                self.add_to_classpath(str(jar))
            self.logger.info(f"Added {len(list(lib_dir.glob('*.jar')))} JARs from lib/")
        else:
            self.logger.warning("lib/ directory not found - create it and add Spring Batch JARs")
    
    def _find_jvm_path(self):
        """Find jvm.dll on Windows"""
        # Try JAVA_HOME first
        java_home = os.environ.get('JAVA_HOME')
        
        if java_home:
            possible_paths = [
                Path(java_home) / 'bin' / 'server' / 'jvm.dll',
                Path(java_home) / 'jre' / 'bin' / 'server' / 'jvm.dll',
                Path(java_home) / 'bin' / 'client' / 'jvm.dll',
            ]
            
            for path in possible_paths:
                if path.exists():
                    self.logger.info(f"Found JVM at: {path}")
                    return str(path)
        
        # Try jpype's default method
        try:
            default_jvm = jpype.getDefaultJVMPath()
            if default_jvm and Path(default_jvm).exists():
                self.logger.info(f"Using default JVM: {default_jvm}")
                return default_jvm
        except Exception as e:
            self.logger.warning(f"Could not get default JVM path: {e}")
        
        # Try common Java installation locations on Windows
        common_locations = [
            r'C:\Program Files\Java',
            r'C:\Program Files (x86)\Java',
        ]
        
        for base_path in common_locations:
            base = Path(base_path)
            if base.exists():
                for java_dir in base.glob('jdk*'):
                    jvm_path = java_dir / 'bin' / 'server' / 'jvm.dll'
                    if jvm_path.exists():
                        self.logger.info(f"Found JVM at: {jvm_path}")
                        return str(jvm_path)
        
        return None
    
    def start(self, max_heap: str = "2G") -> bool:
        """Start the JVM"""
        if self.jvm_started or jpype.isJVMStarted():
            self.logger.warning("JVM already started")
            self.jvm_started = True
            return True
        
        try:
            # Find JVM
            jvm_path = self._find_jvm_path()
            
            if not jvm_path:
                self.logger.error("❌ Could not find jvm.dll")
                self.logger.error("Please set JAVA_HOME environment variable")
                self.logger.error("Example: set JAVA_HOME=C:\\Program Files\\Java\\jdk-22")
                return False
            
            # Add classpaths
            for path in self.classpath:
                jpype.addClassPath(path)
            
            self.logger.info(f"Starting JVM with {len(self.classpath)} classpath entries")
            
            # Start JVM
            jpype.startJVM(
                jvm_path,
                f"-Xmx{max_heap}",
                convertStrings=False
            )
            
            self.jvm_started = True
            self.logger.info("✅ JVM started successfully")
            
            # Test Java
            String = jpype.JClass('java.lang.String')
            test = String('BatcherMan')
            self.logger.info(f"✅ Java test successful: {test}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start JVM: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def stop(self):
        """Stop the JVM"""
        if self.jvm_started and jpype.isJVMStarted():
            try:
                jpype.shutdownJVM()
                self.jvm_started = False
                self.logger.info("✅ JVM stopped")
            except Exception as e:
                self.logger.error(f"Error stopping JVM: {e}")
    
    def is_running(self) -> bool:
        """Check if JVM is running"""
        return jpype.isJVMStarted()
