import jpype
import jpype.imports
from typing import List, Dict, Any
import logging
import tempfile
import os

class WriterSandbox:
    """Execute ItemWriter in sandbox"""
    
    def __init__(self, class_loader):
        self.class_loader = class_loader
        self.logger = logging.getLogger(__name__)
        self.temp_dir = tempfile.gettempdir()
    
    def test_writer(self, writer_class_name: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Actually execute a Spring Batch writer
        """
        try:
            self.logger.info(f"Testing writer: {writer_class_name}")
            
            # 1. Load writer class
            try:
                writer_class = jpype.JClass(writer_class_name)
                self.logger.info(f"✅ Loaded writer: {writer_class_name}")
            except Exception as e:
                return {
                    'success': False,
                    'itemsWritten': 0,
                    'outputFile': None,
                    'writerType': 'unknown',
                    'error': f"Could not load writer: {str(e)}"
                }
            
            # 2. Create writer instance
            try:
                writer = writer_class()
                self.logger.info(f"✅ Created writer instance")
            except Exception as e:
                self.logger.warning(f"Could not use no-arg constructor: {e}")
                # Writers often need configuration - skip for now
                return {
                    'success': False,
                    'itemsWritten': 0,
                    'outputFile': None,
                    'writerType': 'unknown',
                    'error': f"Writer requires configuration (constructor parameters)"
                }
            
            # 3. Convert Python items to Java Chunk
            java_chunk = self._create_chunk(items)
            
            # 4. Write items
            try:
                writer.write(java_chunk)
                self.logger.info(f"✅ Writer executed successfully")
                
                # Try to detect output location
                output_file = self._detect_output_file(writer_class_name)
                
                return {
                    'success': True,
                    'itemsWritten': len(items),
                    'outputFile': output_file,
                    'writerType': self._detect_writer_type(writer_class_name),
                    'error': None
                }
                
            except Exception as e:
                self.logger.error(f"Error during writing: {e}")
                import traceback
                traceback.print_exc()
                
                return {
                    'success': False,
                    'itemsWritten': 0,
                    'outputFile': None,
                    'writerType': 'unknown',
                    'error': f"Writing error: {str(e)}"
                }
            
        except Exception as e:
            self.logger.error(f"❌ Writer test failed: {e}")
            return {
                'success': False,
                'itemsWritten': 0,
                'outputFile': None,
                'writerType': 'unknown',
                'error': str(e)
            }
    
    def _create_chunk(self, items: List[Dict[str, Any]]):
        """Create Java Chunk from Python items"""
        try:
            # Create Chunk
            Chunk = jpype.JClass('org.springframework.batch.item.Chunk')
            chunk = Chunk()
            
            # Add items as HashMaps
            HashMap = jpype.JClass('java.util.HashMap')
            
            for item in items:
                java_map = HashMap()
                for key, value in item.items():
                    java_map.put(str(key), value)
                chunk.add(java_map)
            
            return chunk
            
        except Exception as e:
            self.logger.error(f"Could not create chunk: {e}")
            return None
    
    def _detect_output_file(self, writer_class_name: str) -> str:
        """Try to detect where the writer wrote files"""
        # For CSV/File writers, check temp directory
        if 'Csv' in writer_class_name or 'File' in writer_class_name:
            # List recent files in temp dir
            temp_files = [f for f in os.listdir(self.temp_dir) if f.endswith('.csv')]
            if temp_files:
                # Sort by modification time, return newest
                temp_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.temp_dir, x)), reverse=True)
                return os.path.join(self.temp_dir, temp_files[0])
        
        return None
    
    def _detect_writer_type(self, class_name: str) -> str:
        """Detect writer type from class name"""
        name_lower = class_name.lower()
        
        if 'csv' in name_lower:
            return 'CSV File Writer'
        elif 'jdbc' in name_lower or 'db' in name_lower:
            return 'JDBC Database Writer'
        elif 'jms' in name_lower:
            return 'JMS Writer'
        elif 'xml' in name_lower:
            return 'XML Writer'
        else:
            return 'Custom Writer'
