import jpype
import jpype.imports
from typing import Dict, Any, Optional
import logging

class StepSandbox:
    """Execute a complete Step with chunk processing"""
    
    def __init__(self, class_loader, reader_sandbox, processor_sandbox, writer_sandbox):
        self.class_loader = class_loader
        self.reader_sandbox = reader_sandbox
        self.processor_sandbox = processor_sandbox
        self.writer_sandbox = writer_sandbox
        self.logger = logging.getLogger(__name__)
    
    def run_step(
        self,
        step_name: str,
        reader_class: str,
        processor_class: Optional[str],
        writer_class: str,
        chunk_size: int = 10
    ) -> Dict[str, Any]:
        """
        Execute a complete step with chunk-based processing
        
        Returns:
            {
                'success': bool,
                'metrics': {
                    'readCount': int,
                    'writeCount': int,
                    'filterCount': int,
                    'skipCount': int,
                    'duration': float
                },
                'error': Optional[str]
            }
        """
        import time
        start_time = time.time()
        
        metrics = {
            'readCount': 0,
            'writeCount': 0,
            'filterCount': 0,
            'skipCount': 0,
            'duration': 0.0
        }
        
        try:
            # Create reader
            reader = self.class_loader.create_instance(reader_class)
            
            # Create processor (optional)
            processor = None
            if processor_class:
                processor = self.class_loader.create_instance(processor_class)
            
            # Create writer
            writer = self.class_loader.create_instance(writer_class)
            
            # Create execution contexts
            execution_context = self._create_execution_context()
            
            # Open reader
            if self._is_item_stream(reader):
                reader.open(execution_context)
            
            # Open writer
            if self._is_item_stream(writer):
                writer.open(execution_context)
            
            # Process chunks
            chunk = []
            
            while True:
                # Read item
                item = reader.read()
                
                if item is None:
                    # End of data - write remaining chunk
                    if chunk:
                        self._write_chunk(writer, chunk)
                        metrics['writeCount'] += len(chunk)
                    break
                
                metrics['readCount'] += 1
                
                # Process item (if processor exists)
                if processor:
                    processed_item = processor.process(item)
                    
                    if processed_item is None:
                        # Item was filtered
                        metrics['filterCount'] += 1
                        continue
                    
                    item = processed_item
                
                # Add to chunk
                chunk.append(item)
                
                # Write chunk when full
                if len(chunk) >= chunk_size:
                    self._write_chunk(writer, chunk)
                    metrics['writeCount'] += len(chunk)
                    chunk = []
            
            # Close streams
            if self._is_item_stream(reader):
                reader.close()
            
            if self._is_item_stream(writer):
                writer.close()
            
            metrics['duration'] = time.time() - start_time
            
            self.logger.info(f"✅ Step completed: {metrics}")
            
            return {
                'success': True,
                'metrics': metrics,
                'error': None
            }
            
        except Exception as e:
            metrics['duration'] = time.time() - start_time
            self.logger.error(f"❌ Error running step: {e}")
            return {
                'success': False,
                'metrics': metrics,
                'error': str(e)
            }
    
    def _write_chunk(self, writer, chunk):
        """Write a chunk of items"""
        ArrayList = jpype.JClass('java.util.ArrayList')
        java_list = ArrayList()
        
        for item in chunk:
            java_list.add(item)
        
        writer.write(java_list)
    
    def _create_execution_context(self):
        """Create execution context"""
        try:
            ExecutionContext = jpype.JClass('org.springframework.batch.item.ExecutionContext')
            return ExecutionContext()
        except:
            return {}
    
    def _is_item_stream(self, obj) -> bool:
        """Check if implements ItemStream"""
        try:
            ItemStream = jpype.JClass('org.springframework.batch.item.ItemStream')
            return isinstance(obj, ItemStream)
        except:
            return False
