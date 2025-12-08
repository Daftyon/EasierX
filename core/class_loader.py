import jpype
import jpype.imports
from pathlib import Path
from typing import List, Dict, Any
import logging

class DynamicClassLoader:
    """Load classes from user's Spring Batch project"""
    
    def __init__(self, jvm_manager):
        self.jvm_manager = jvm_manager
        self.logger = logging.getLogger(__name__)
        self.loaded_classes = {}
    
    def load_project(self, project_path: str):
        """Load a JAR or directory into the JVM"""
        path = Path(project_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Project path not found: {project_path}")
        
        if path.is_file() and path.suffix == '.jar':
            self.jvm_manager.add_to_classpath(str(path))
            self.logger.info(f"Loaded JAR: {project_path}")
        elif path.is_dir():
            self.jvm_manager.add_to_classpath(str(path))
            self.logger.info(f"Loaded directory: {project_path}")
        else:
            raise ValueError(f"Invalid project path: {project_path}")
    
    def get_class(self, class_name: str):
        """Get a Java class by name"""
        if class_name in self.loaded_classes:
            return self.loaded_classes[class_name]
        
        try:
            java_class = jpype.JClass(class_name)
            self.loaded_classes[class_name] = java_class
            return java_class
        except Exception as e:
            self.logger.error(f"Failed to load class {class_name}: {e}")
            raise
    
    def create_instance(self, class_name: str, *args):
        """Create an instance of a Java class"""
        java_class = self.get_class(class_name)
        return java_class(*args)
    
    def list_classes_in_jar(self, jar_path: str) -> List[str]:
        """List all classes in a JAR file"""
        import zipfile
        
        classes = []
        with zipfile.ZipFile(jar_path, 'r') as jar:
            for file in jar.namelist():
                if file.endswith('.class'):
                    # Convert path to class name
                    class_name = file[:-6].replace('/', '.')
                    classes.append(class_name)
        
        return classes
