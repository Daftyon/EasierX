import jpype
import jpype.imports
from typing import List, Dict, Any, Optional
import logging

class ReaderSandbox:
    """Execute ItemReader in isolated sandbox"""
    
    def __init__(self, class_loader):
        self.class_loader = class_loader
        self.logger = logging.getLogger(__name__)
    
    def test_reader(self, reader_class_name: str, max_items: int = 100) -> Dict[str, Any]:
        """
        Actually execute a Spring Batch reader and return real data
        """
        try:
            self.logger.info(f"Testing reader: {reader_class_name}")
            
            # 1. Load the reader class
            try:
                reader_class = jpype.JClass(reader_class_name)
                self.logger.info(f"✅ Loaded class: {reader_class_name}")
            except Exception as e:
                return {
                    'success': False,
                    'items': [],
                    'itemCount': 0,
                    'error': f"Could not load class {reader_class_name}: {str(e)}"
                }
            
            # 2. Try to instantiate the reader
            # This is tricky - readers often need constructor parameters
            reader = self._create_reader_instance(reader_class, reader_class_name)
            
            if reader is None:
                return {
                    'success': False,
                    'items': [],
                    'itemCount': 0,
                    'error': f"Could not instantiate {reader_class_name} - requires specific constructor parameters"
                }
            
            # 3. Initialize reader if it's an ItemStream
            try:
                ItemStream = jpype.JClass('org.springframework.batch.item.ItemStream')
                if isinstance(reader, ItemStream):
                    ExecutionContext = jpype.JClass('org.springframework.batch.item.ExecutionContext')
                    execution_context = ExecutionContext()
                    reader.open(execution_context)
                    self.logger.info("✅ Reader opened (ItemStream)")
            except Exception as e:
                self.logger.warning(f"Could not open reader as ItemStream: {e}")
            
            # 4. Read items
            items = []
            count = 0
            
            try:
                while count < max_items:
                    item = reader.read()
                    
                    if item is None:
                        break
                    
                    # Convert Java object to Python dict
                    item_dict = self._java_to_python(item)
                    items.append(item_dict)
                    count += 1
                    
                    self.logger.debug(f"Read item {count}: {item_dict}")
                
                self.logger.info(f"✅ Successfully read {count} items")
                
            except Exception as e:
                self.logger.error(f"Error during reading: {e}")
                return {
                    'success': False,
                    'items': items,
                    'itemCount': count,
                    'error': f"Error reading items: {str(e)}"
                }
            
            # 5. Close reader
            try:
                if isinstance(reader, ItemStream):
                    reader.close()
                    self.logger.info("✅ Reader closed")
            except:
                pass
            
            return {
                'success': True,
                'items': items,
                'itemCount': count,
                'error': None
            }
            
        except Exception as e:
            self.logger.error(f"❌ Reader test failed: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'items': [],
                'itemCount': 0,
                'error': str(e)
            }
    
    def _create_reader_instance(self, reader_class, class_name: str):
        """
        Try multiple strategies to instantiate the reader
        """
        # Strategy 1: No-arg constructor
        try:
            reader = reader_class()
            self.logger.info(f"✅ Created reader with no-arg constructor")
            return reader
        except:
            pass
        
        # Strategy 2: Try with mock DataSource for JDBC readers
        if 'Jdbc' in class_name or 'Db' in class_name:
            try:
                # Create a mock/null DataSource
                datasource = self._create_mock_datasource()
                reader = reader_class(datasource)
                self.logger.info(f"✅ Created JDBC reader with mock DataSource")
                return reader
            except Exception as e:
                self.logger.debug(f"Could not create with DataSource: {e}")
        
        # Strategy 3: Return None - cannot instantiate
        self.logger.warning(f"⚠️ Could not instantiate {class_name}")
        return None
    
    def _create_mock_datasource(self):
        """Create a mock DataSource for testing"""
        try:
            # Try to create H2 in-memory datasource
            DriverManagerDataSource = jpype.JClass('org.springframework.jdbc.datasource.DriverManagerDataSource')
            ds = DriverManagerDataSource()
            ds.setDriverClassName("org.h2.Driver")
            ds.setUrl("jdbc:h2:mem:testdb")
            return ds
        except:
            return None
    
    def _java_to_python(self, java_obj) -> Dict[str, Any]:
        """
        Convert Java object to Python dictionary
        """
        if java_obj is None:
            return None
        
        result = {}
        
        try:
            # Get the Java class
            java_class = java_obj.getClass()
            
            # Get all fields
            fields = java_class.getDeclaredFields()
            
            for field in fields:
                try:
                    field.setAccessible(True)
                    field_name = str(field.getName())
                    field_value = field.get(java_obj)
                    
                    # Convert to Python types
                    result[field_name] = self._convert_value(field_value)
                    
                except Exception as e:
                    self.logger.debug(f"Could not read field {field_name}: {e}")
            
        except Exception as e:
            self.logger.warning(f"Could not introspect object: {e}")
            # Fallback: just convert to string
            result = {'value': str(java_obj)}
        
        return result
    
    def _convert_value(self, value):
        """Convert Java value to Python type"""
        if value is None:
            return None
        
        # Check type and convert
        value_type = type(value).__name__
        
        if 'String' in value_type or 'str' in value_type:
            return str(value)
        elif 'Integer' in value_type or 'Long' in value_type:
            return int(value)
        elif 'Double' in value_type or 'Float' in value_type:
            return float(value)
        elif 'Boolean' in value_type:
            return bool(value)
        elif 'Date' in value_type or 'Timestamp' in value_type:
            return str(value)
        else:
            return str(value)
