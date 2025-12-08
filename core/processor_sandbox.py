import jpype
import jpype.imports
from typing import Dict, Any
import logging

class ProcessorSandbox:
    """Execute ItemProcessor in isolation"""
    
    def __init__(self, class_loader):
        self.class_loader = class_loader
        self.logger = logging.getLogger(__name__)
    
    def test_processor(self, processor_class_name: str, input_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actually execute a Spring Batch processor
        """
        try:
            self.logger.info(f"Testing processor: {processor_class_name}")
            
            # 1. Load processor class
            try:
                processor_class = jpype.JClass(processor_class_name)
                self.logger.info(f"✅ Loaded processor: {processor_class_name}")
            except Exception as e:
                return {
                    'success': False,
                    'input': input_item,
                    'output': None,
                    'filtered': False,
                    'error': f"Could not load processor: {str(e)}"
                }
            
            # 2. Create processor instance
            try:
                processor = processor_class()
                self.logger.info(f"✅ Created processor instance")
            except Exception as e:
                return {
                    'success': False,
                    'input': input_item,
                    'output': None,
                    'filtered': False,
                    'error': f"Could not instantiate processor: {str(e)}"
                }
            
            # 3. Convert Python dict to Java object
            java_input = self._python_to_java(input_item)
            
            # 4. Process the item
            try:
                java_output = processor.process(java_input)
                
                # Check if filtered (null return)
                if java_output is None:
                    self.logger.info("⚠️ Item was filtered (processor returned null)")
                    return {
                        'success': True,
                        'input': input_item,
                        'output': None,
                        'filtered': True,
                        'error': None
                    }
                
                # Convert output back to Python
                output_item = self._java_to_python(java_output)
                
                self.logger.info(f"✅ Item processed successfully")
                
                return {
                    'success': True,
                    'input': input_item,
                    'output': output_item,
                    'filtered': False,
                    'error': None
                }
                
            except Exception as e:
                self.logger.error(f"Error during processing: {e}")
                import traceback
                traceback.print_exc()
                
                return {
                    'success': False,
                    'input': input_item,
                    'output': None,
                    'filtered': False,
                    'error': f"Processing error: {str(e)}"
                }
            
        except Exception as e:
            self.logger.error(f"❌ Processor test failed: {e}")
            return {
                'success': False,
                'input': input_item,
                'output': None,
                'filtered': False,
                'error': str(e)
            }
    
    def _python_to_java(self, python_dict: Dict[str, Any]):
        """
        Convert Python dict to Java HashMap
        (Processors usually accept generic objects, HashMap is safest)
        """
        try:
            HashMap = jpype.JClass('java.util.HashMap')
            java_map = HashMap()
            
            for key, value in python_dict.items():
                java_map.put(str(key), value)
            
            return java_map
            
        except Exception as e:
            self.logger.error(f"Could not convert to Java: {e}")
            return None
    
    def _java_to_python(self, java_obj) -> Dict[str, Any]:
        """Convert Java object to Python dict"""
        if java_obj is None:
            return None
        
        result = {}
        
        try:
            java_class = java_obj.getClass()
            fields = java_class.getDeclaredFields()
            
            for field in fields:
                try:
                    field.setAccessible(True)
                    field_name = str(field.getName())
                    field_value = field.get(java_obj)
                    
                    if field_value is None:
                        result[field_name] = None
                    elif isinstance(field_value, (jpype.JString, str)):
                        result[field_name] = str(field_value)
                    elif isinstance(field_value, (jpype.JInt, jpype.JLong, int)):
                        result[field_name] = int(field_value)
                    elif isinstance(field_value, (jpype.JDouble, jpype.JFloat, float)):
                        result[field_name] = float(field_value)
                    elif isinstance(field_value, jpype.JBoolean):
                        result[field_name] = bool(field_value)
                    else:
                        result[field_name] = str(field_value)
                        
                except Exception as e:
                    self.logger.debug(f"Could not read field {field_name}: {e}")
            
        except Exception as e:
            self.logger.warning(f"Could not introspect object: {e}")
            result = {'value': str(java_obj)}
        
        return result
