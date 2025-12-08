import zipfile
import logging
from typing import List, Dict, Any
import xml.etree.ElementTree as ET
import re

class BatchAnalyzer:
    """Analyze Spring Batch components from both Java classes and XML configuration"""
    
    def __init__(self, class_loader=None):
        self.class_loader = class_loader
        self.logger = logging.getLogger(__name__)
    
    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """
        Comprehensive analysis of Spring Batch project
        Analyzes: Java classes, XML configs, annotations
        """
        self.logger.info(f"🔍 Analyzing project: {project_path}")
        self.logger.info("=" * 80)
        
        # Analyze Java classes
        self.logger.info("📦 Analyzing Java classes...")
        java_readers = self.find_readers(project_path)
        java_processors = self.find_processors(project_path)
        java_writers = self.find_writers(project_path)
        java_steps = self.find_steps(project_path)
        java_jobs = self.find_jobs(project_path)
        
        # Analyze XML configuration
        self.logger.info("📋 Analyzing XML configuration...")
        xml_components = self._analyze_xml_config(project_path)
        
        # Merge results
        result = {
            'readers': self._merge_components(
                java_readers,
                xml_components.get('readers', [])
            ),
            'processors': self._merge_components(
                java_processors,
                xml_components.get('processors', [])
            ),
            'writers': self._merge_components(
                java_writers,
                xml_components.get('writers', [])
            ),
            'steps': self._merge_components(
                java_steps,
                xml_components.get('steps', [])
            ),
            'jobs': self._merge_components(
                java_jobs,
                xml_components.get('jobs', [])
            )
        }
        
        self.logger.info("=" * 80)
        self.logger.info("✅ Analysis Complete:")
        self.logger.info(f"   📖 Readers: {len(result['readers'])}")
        self.logger.info(f"   ⚙️ Processors: {len(result['processors'])}")
        self.logger.info(f"   ✍️ Writers: {len(result['writers'])}")
        self.logger.info(f"   🔄 Steps: {len(result['steps'])}")
        self.logger.info(f"   🚀 Jobs: {len(result['jobs'])}")
        self.logger.info("=" * 80)
        
        return result
    
    def _analyze_xml_config(self, jar_path: str) -> Dict[str, List]:
        """
        Analyze XML configuration files for Spring Batch beans
        Supports both Spring beans XML and Spring Batch namespace
        """
        self.logger.info("🔍 Scanning for XML configuration files...")
        
        readers = []
        processors = []
        writers = []
        steps = []
        jobs = []
        
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                # Find all XML files (excluding Maven metadata)
                xml_files = [f for f in jar.namelist() 
                            if f.endswith('.xml') and not f.startswith('META-INF/maven')]
                
                self.logger.info(f"Found {len(xml_files)} XML files")
                
                for xml_file in xml_files:
                    self.logger.info(f"📄 Parsing: {xml_file}")
                    
                    try:
                        xml_content = jar.read(xml_file)
                        xml_data = self._parse_spring_xml(xml_content, xml_file)
                        
                        readers.extend(xml_data.get('readers', []))
                        processors.extend(xml_data.get('processors', []))
                        writers.extend(xml_data.get('writers', []))
                        steps.extend(xml_data.get('steps', []))
                        jobs.extend(xml_data.get('jobs', []))
                        
                    except Exception as e:
                        self.logger.warning(f"⚠️ Could not parse {xml_file}: {e}")
        
        except Exception as e:
            self.logger.error(f"❌ Error reading XML files: {e}")
        
        return {
            'readers': readers,
            'processors': processors,
            'writers': writers,
            'steps': steps,
            'jobs': jobs
        }
    
    def _parse_spring_xml(self, xml_content: bytes, filename: str) -> Dict[str, List]:
        """
        Parse Spring XML configuration to extract batch components
        Handles both <bean> declarations and <batch:job>/<batch:step> namespace
        """
        readers = []
        processors = []
        writers = []
        steps = []
        jobs = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Define namespaces (handle multiple namespace variations)
            namespaces = {
                'beans': 'http://www.springframework.org/schema/beans',
                'batch': 'http://www.springframework.org/schema/batch',
                'context': 'http://www.springframework.org/schema/context',
                'p': 'http://www.springframework.org/schema/p'
            }
            
            # Also try without namespace (for files without proper xmlns)
            no_ns = {'beans': '', 'batch': '', 'context': '', 'p': ''}
            
            # === Parse <bean> Elements ===
            for ns in [namespaces, no_ns]:
                # Find all <bean> elements
                for bean in root.findall('.//bean', ns) + root.findall('.//beans:bean', ns):
                    bean_id = bean.get('id', bean.get('name', 'unknown'))
                    bean_class = bean.get('class', '')
                    
                    if not bean_class:
                        continue
                    
                    component_info = {
                        'name': bean_id,
                        'fullName': bean_class,
                        'source': f'XML: {filename}',
                        'beanId': bean_id,
                        'xmlFile': filename
                    }
                    
                    # Classify by class name or bean ID
                    if self._is_reader_bean(bean_id, bean_class):
                        component_info['type'] = 'ItemReader'
                        component_info['description'] = self._get_reader_type(bean_class)
                        readers.append(component_info)
                        self.logger.info(f"  ✅ Found XML reader: {bean_id} ({bean_class})")
                    
                    elif self._is_processor_bean(bean_id, bean_class):
                        component_info['type'] = 'ItemProcessor'
                        processors.append(component_info)
                        self.logger.info(f"  ✅ Found XML processor: {bean_id} ({bean_class})")
                    
                    elif self._is_writer_bean(bean_id, bean_class):
                        component_info['type'] = 'ItemWriter'
                        component_info['description'] = self._get_writer_type(bean_class)
                        writers.append(component_info)
                        self.logger.info(f"  ✅ Found XML writer: {bean_id} ({bean_class})")
            
            # === Parse Spring Batch Namespace Elements ===
            
            # Parse <batch:job> elements
            for ns in [namespaces, no_ns]:
                for job in root.findall('.//job', ns) + root.findall('.//batch:job', ns):
                    job_id = job.get('id', 'unknown')
                    job_steps = []
                    
                    # Find all steps in this job
                    for step in job.findall('.//step', ns) + job.findall('.//batch:step', ns):
                        step_id = step.get('id', 'unknown')
                        job_steps.append(step_id)
                    
                    # Also check for <step> references via "next" attribute
                    for step in job.findall('.//step', ns) + job.findall('.//batch:step', ns):
                        next_step = step.get('next', '')
                        if next_step and next_step not in job_steps:
                            job_steps.append(next_step)
                    
                    job_info = {
                        'name': job_id,
                        'type': 'Job',
                        'steps': job_steps,
                        'source': f'XML: {filename}',
                        'xmlFile': filename
                    }
                    jobs.append(job_info)
                    self.logger.info(f"  ✅ Found XML job: {job_id} with {len(job_steps)} steps")
            
            # Parse <batch:step> elements (standalone or in jobs)
            for ns in [namespaces, no_ns]:
                for step_elem in root.findall('.//step', ns) + root.findall('.//batch:step', ns):
                    step_id = step_elem.get('id', 'unknown')
                    
                    step_info = {
                        'name': step_id,
                        'type': 'Step',
                        'source': f'XML: {filename}',
                        'xmlFile': filename,
                        'reader': '',
                        'processor': '',
                        'writer': '',
                        'commitInterval': '10'
                    }
                    
                    # Find tasklet
                    tasklet = step_elem.find('.//tasklet', ns) or step_elem.find('.//batch:tasklet', ns)
                    
                    if tasklet is not None:
                        # Find chunk configuration
                        chunk = tasklet.find('.//chunk', ns) or tasklet.find('.//batch:chunk', ns)
                        
                        if chunk is not None:
                            step_info['reader'] = chunk.get('reader', '')
                            step_info['processor'] = chunk.get('processor', '')
                            step_info['writer'] = chunk.get('writer', '')
                            step_info['commitInterval'] = chunk.get('commit-interval', '10')
                            
                            self.logger.info(f"  ✅ Found XML step: {step_id} "
                                          f"[reader={step_info['reader']}, "
                                          f"processor={step_info['processor']}, "
                                          f"writer={step_info['writer']}]")
                        else:
                            # Tasklet without chunk (custom tasklet)
                            tasklet_ref = tasklet.get('ref', '')
                            if tasklet_ref:
                                step_info['tasklet'] = tasklet_ref
                                self.logger.info(f"  ✅ Found XML tasklet step: {step_id} [tasklet={tasklet_ref}]")
                    
                    steps.append(step_info)
        
        except ET.ParseError as e:
            self.logger.warning(f"⚠️ XML parse error in {filename}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Error parsing XML {filename}: {e}")
            import traceback
            traceback.print_exc()
        
        return {
            'readers': readers,
            'processors': processors,
            'writers': writers,
            'steps': steps,
            'jobs': jobs
        }
    
    def find_steps(self, jar_path: str) -> List[Dict[str, Any]]:
        """
        Find Step definitions from Java @Bean methods
        """
        steps = []
        
        try:
            classes = self._get_class_info(jar_path)
            
            for class_info in classes:
                class_name = class_info['name']
                
                # Skip test and inner classes
                if 'Test' in class_name or '$' in class_name:
                    continue
                
                # Look for configuration classes
                if 'Config' in class_name or 'Configuration' in class_name:
                    step_beans = self._find_step_beans_in_class(jar_path, class_name)
                    steps.extend(step_beans)
        
        except Exception as e:
            self.logger.error(f"❌ Error finding Java steps: {e}")
        
        return steps
    
    def find_jobs(self, jar_path: str) -> List[Dict[str, Any]]:
        """
        Find Job definitions from Java @Bean methods
        """
        jobs = []
        
        try:
            classes = self._get_class_info(jar_path)
            
            for class_info in classes:
                class_name = class_info['name']
                
                if 'Test' in class_name or '$' in class_name:
                    continue
                
                # Look for configuration classes
                if 'Config' in class_name or 'Configuration' in class_name:
                    job_beans = self._find_job_beans_in_class(jar_path, class_name)
                    jobs.extend(job_beans)
        
        except Exception as e:
            self.logger.error(f"❌ Error finding Java jobs: {e}")
        
        return jobs
    
    def _find_step_beans_in_class(self, jar_path: str, class_name: str) -> List[Dict[str, Any]]:
        """
        Find @Bean methods that return Step by analyzing bytecode
        """
        steps = []
        
        try:
            class_file = class_name.replace('.', '/') + '.class'
            
            with zipfile.ZipFile(jar_path, 'r') as jar:
                if class_file in jar.namelist():
                    bytecode = jar.read(class_file)
                    text = bytecode.decode('latin1', errors='ignore')
                    
                    # Look for Step bean methods
                    # Pattern: public Step xxxStep() or xxxStep(
                    step_patterns = [
                        r'(\w*[Ss]tep\w*)\s*\([^)]*\)\s*\{',  # xxxStep() {
                        r'Step\s+(\w+[Ss]tep\w*)\s*\(',       # Step xxxStep(
                    ]
                    
                    found_steps = set()
                    
                    for pattern in step_patterns:
                        matches = re.findall(pattern, text)
                        for match in matches:
                            if match and 'step' in match.lower():
                                found_steps.add(match)
                    
                    for step_name in found_steps:
                        steps.append({
                            'name': step_name,
                            'type': 'Step',
                            'configClass': class_name,
                            'source': 'Java @Bean',
                            'reader': 'unknown',
                            'processor': 'unknown',
                            'writer': 'unknown'
                        })
                        self.logger.info(f"  ✅ Found Java step: {step_name} in {class_name}")
        
        except Exception as e:
            self.logger.debug(f"Could not parse class {class_name}: {e}")
        
        return steps
    
    def _find_job_beans_in_class(self, jar_path: str, class_name: str) -> List[Dict[str, Any]]:
        """
        Find @Bean methods that return Job by analyzing bytecode
        """
        jobs = []
        
        try:
            class_file = class_name.replace('.', '/') + '.class'
            
            with zipfile.ZipFile(jar_path, 'r') as jar:
                if class_file in jar.namelist():
                    bytecode = jar.read(class_file)
                    text = bytecode.decode('latin1', errors='ignore')
                    
                    # Look for Job bean methods
                    job_patterns = [
                        r'(\w*[Jj]ob\w*)\s*\([^)]*\)\s*\{',  # xxxJob() {
                        r'Job\s+(\w+[Jj]ob\w*)\s*\(',        # Job xxxJob(
                    ]
                    
                    found_jobs = set()
                    
                    for pattern in job_patterns:
                        matches = re.findall(pattern, text)
                        for match in matches:
                            if match and 'job' in match.lower():
                                found_jobs.add(match)
                    
                    for job_name in found_jobs:
                        jobs.append({
                            'name': job_name,
                            'type': 'Job',
                            'configClass': class_name,
                            'source': 'Java @Bean',
                            'steps': []
                        })
                        self.logger.info(f"  ✅ Found Java job: {job_name} in {class_name}")
        
        except Exception as e:
            self.logger.debug(f"Could not parse class {class_name}: {e}")
        
        return jobs
    
    def _is_reader_bean(self, bean_id: str, bean_class: str) -> bool:
        """Check if bean is a reader"""
        # Check by ID
        if any(keyword in bean_id.lower() for keyword in ['reader', 'read']):
            return True
        
        # Check by class name
        if any(keyword in bean_class for keyword in [
            'ItemReader', 'Reader',
            'JdbcCursorItemReader', 'JdbcPagingItemReader',
            'FlatFileItemReader', 'StaxEventItemReader'
        ]):
            return True
        
        return False
    
    def _is_processor_bean(self, bean_id: str, bean_class: str) -> bool:
        """Check if bean is a processor"""
        if any(keyword in bean_id.lower() for keyword in ['processor', 'process']):
            return True
        
        if 'ItemProcessor' in bean_class or 'Processor' in bean_class:
            return True
        
        return False
    
    def _is_writer_bean(self, bean_id: str, bean_class: str) -> bool:
        """Check if bean is a writer"""
        if any(keyword in bean_id.lower() for keyword in ['writer', 'write']):
            return True
        
        if any(keyword in bean_class for keyword in [
            'ItemWriter', 'Writer',
            'JdbcBatchItemWriter', 'FlatFileItemWriter',
            'StaxEventItemWriter', 'JmsItemWriter'
        ]):
            return True
        
        return False
    
    def _merge_components(self, java_list: List, xml_list: List) -> List:
        """Merge components from Java and XML, removing duplicates"""
        merged = {}
        
        # Add Java components
        for component in java_list:
            key = component.get('fullName') or component.get('name')
            merged[key] = component
        
        # Add XML components (prefer XML if duplicate)
        for component in xml_list:
            key = component.get('fullName') or component.get('name')
            if key not in merged:
                merged[key] = component
            else:
                # Enhance with XML info
                merged[key]['beanId'] = component.get('beanId')
                merged[key]['xmlSource'] = component.get('source')
        
        return list(merged.values())
    
    # Keep existing reader/processor/writer finding methods
    def find_readers(self, jar_path: str) -> List[Dict[str, Any]]:
        """Find ItemReader implementations by analyzing bytecode"""
        readers = []
        
        try:
            classes = self._get_class_info(jar_path)
            
            for class_info in classes:
                class_name = class_info['name']
                
                if 'Test' in class_name or '$' in class_name:
                    continue
                
                is_reader = (
                    'Reader' in class_name or
                    'ItemReader' in class_info.get('interfaces', '') or
                    'JdbcCursorItemReader' in class_info.get('superclass', '') or
                    'JdbcPagingItemReader' in class_info.get('superclass', '') or
                    'FlatFileItemReader' in class_info.get('superclass', '')
                )
                
                if is_reader:
                    simple_name = class_name.split('.')[-1]
                    
                    readers.append({
                        'name': simple_name,
                        'fullName': class_name,
                        'type': 'ItemReader',
                        'description': self._get_reader_type(class_name),
                        'superclass': class_info.get('superclass', 'Unknown'),
                        'source': 'Java Class'
                    })
                    
                    self.logger.info(f"  ✅ Found Java reader: {simple_name}")
        
        except Exception as e:
            self.logger.error(f"❌ Error finding readers: {e}")
        
        return readers
    
    def find_processors(self, jar_path: str) -> List[Dict[str, Any]]:
        """Find ItemProcessor implementations"""
        processors = []
        
        try:
            classes = self._get_class_info(jar_path)
            
            for class_info in classes:
                class_name = class_info['name']
                
                if 'Test' in class_name or '$' in class_name:
                    continue
                
                is_processor = (
                    'Processor' in class_name or
                    'ItemProcessor' in class_info.get('interfaces', '')
                )
                
                if is_processor:
                    simple_name = class_name.split('.')[-1]
                    
                    processors.append({
                        'name': simple_name,
                        'fullName': class_name,
                        'type': 'ItemProcessor',
                        'source': 'Java Class'
                    })
                    
                    self.logger.info(f"  ✅ Found Java processor: {simple_name}")
        
        except Exception as e:
            self.logger.error(f"❌ Error finding processors: {e}")
        
        return processors
    
    def find_writers(self, jar_path: str) -> List[Dict[str, Any]]:
        """Find ItemWriter implementations"""
        writers = []
        
        try:
            classes = self._get_class_info(jar_path)
            
            for class_info in classes:
                class_name = class_info['name']
                
                if 'Test' in class_name or '$' in class_name:
                    continue
                
                is_writer = (
                    'Writer' in class_name or
                    'ItemWriter' in class_info.get('interfaces', '')
                )
                
                if is_writer:
                    simple_name = class_name.split('.')[-1]
                    
                    writers.append({
                        'name': simple_name,
                        'fullName': class_name,
                        'type': 'ItemWriter',
                        'description': self._get_writer_type(class_name),
                        'source': 'Java Class'
                    })
                    
                    self.logger.info(f"  ✅ Found Java writer: {simple_name}")
        
        except Exception as e:
            self.logger.error(f"❌ Error finding writers: {e}")
        
        return writers
    
    def _get_class_info(self, jar_path: str) -> List[Dict[str, Any]]:
        """Extract class information from JAR"""
        classes = []
        
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                for entry in jar.namelist():
                    if entry.endswith('.class') and not entry.startswith('META-INF'):
                        class_name = entry[:-6].replace('/', '.')
                        bytecode = jar.read(entry)
                        class_info = self._parse_class_bytecode(class_name, bytecode)
                        classes.append(class_info)
        
        except Exception as e:
            self.logger.error(f"❌ Error reading JAR: {e}")
        
        return classes
    
    def _parse_class_bytecode(self, class_name: str, bytecode: bytes) -> Dict[str, Any]:
        """Parse Java class bytecode to extract superclass and interfaces"""
        try:
            text = bytecode.decode('latin1', errors='ignore')
            
            superclass = 'Unknown'
            interfaces = []
            
            # Check for common Spring Batch classes
            if 'JdbcCursorItemReader' in text:
                superclass = 'JdbcCursorItemReader'
            elif 'JdbcPagingItemReader' in text:
                superclass = 'JdbcPagingItemReader'
            elif 'FlatFileItemReader' in text:
                superclass = 'FlatFileItemReader'
            
            if 'ItemReader' in text:
                interfaces.append('ItemReader')
            if 'ItemProcessor' in text:
                interfaces.append('ItemProcessor')
            if 'ItemWriter' in text:
                interfaces.append('ItemWriter')
            
            return {
                'name': class_name,
                'superclass': superclass,
                'interfaces': ', '.join(interfaces) if interfaces else ''
            }
            
        except Exception as e:
            return {
                'name': class_name,
                'superclass': 'Unknown',
                'interfaces': ''
            }
    
    def _get_reader_type(self, class_name: str) -> str:
        """Determine reader type"""
        name_lower = class_name.lower()
        
        if 'jdbc' in name_lower or 'db' in name_lower:
            return '🗄️ JDBC Database Reader'
        elif 'csv' in name_lower or 'flat' in name_lower:
            return '📄 CSV/Flat File Reader'
        elif 'xml' in name_lower or 'stax' in name_lower:
            return '📋 XML Reader'
        elif 'json' in name_lower:
            return '📝 JSON Reader'
        elif 'jms' in name_lower:
            return '📨 JMS Reader'
        else:
            return '🔧 Custom Reader'
    
    def _get_writer_type(self, class_name: str) -> str:
        """Determine writer type"""
        name_lower = class_name.lower()
        
        if 'jdbc' in name_lower or 'db' in name_lower:
            return '🗄️ JDBC Database Writer'
        elif 'csv' in name_lower or 'flat' in name_lower:
            return '📄 CSV/Flat File Writer'
        elif 'xml' in name_lower or 'stax' in name_lower:
            return '📋 XML Writer'
        elif 'json' in name_lower:
            return '📝 JSON Writer'
        elif 'jms' in name_lower:
            return '📨 JMS Writer'
        else:
            return '🔧 Custom Writer'


    def debug_jar_analysis(self, jar_path: str) -> Dict[str, Any]:
        """
        Comprehensive debug analysis - shows everything found
        """
        debug_info = {
            'jar_path': jar_path,
            'xml_files': [],
            'class_files': [],
            'xml_parse_results': [],
            'errors': []
        }
        
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                all_files = jar.namelist()
                
                # List all files
                debug_info['total_files'] = len(all_files)
                debug_info['xml_files'] = [f for f in all_files if f.endswith('.xml')]
                debug_info['class_files'] = [f for f in all_files if f.endswith('.class')]
                
                self.logger.info(f"📊 JAR Analysis:")
                self.logger.info(f"   Total files: {len(all_files)}")
                self.logger.info(f"   XML files: {len(debug_info['xml_files'])}")
                self.logger.info(f"   Class files: {len(debug_info['class_files'])}")
                
                # Try to parse each XML file
                for xml_file in debug_info['xml_files']:
                    if xml_file.startswith('META-INF/maven'):
                        continue
                    
                    self.logger.info(f"\n📄 Parsing XML: {xml_file}")
                    
                    try:
                        xml_content = jar.read(xml_file)
                        
                        # Show first 500 chars
                        preview = xml_content.decode('utf-8', errors='ignore')[:500]
                        self.logger.info(f"   Content preview: {preview}...")
                        
                        # Try to parse
                        root = ET.fromstring(xml_content)
                        
                        # Show root element
                        self.logger.info(f"   Root element: {root.tag}")
                        self.logger.info(f"   Root attributes: {root.attrib}")
                        
                        # Find all elements
                        all_elements = list(root.iter())
                        self.logger.info(f"   Total elements: {len(all_elements)}")
                        
                        # Show element types
                        element_types = {}
                        for elem in all_elements:
                            # Remove namespace
                            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                            element_types[tag] = element_types.get(tag, 0) + 1
                        
                        self.logger.info(f"   Element types: {element_types}")
                        
                        # Look for batch-specific elements
                        jobs_found = len([e for e in all_elements if 'job' in e.tag.lower()])
                        steps_found = len([e for e in all_elements if 'step' in e.tag.lower()])
                        beans_found = len([e for e in all_elements if 'bean' in e.tag.lower()])
                        
                        self.logger.info(f"   🚀 Jobs: {jobs_found}")
                        self.logger.info(f"   🔄 Steps: {steps_found}")
                        self.logger.info(f"   🫘 Beans: {beans_found}")
                        
                        debug_info['xml_parse_results'].append({
                            'file': xml_file,
                            'parsed': True,
                            'elements': len(all_elements),
                            'jobs': jobs_found,
                            'steps': steps_found,
                            'beans': beans_found
                        })
                        
                    except Exception as e:
                        self.logger.error(f"   ❌ Parse error: {e}")
                        debug_info['errors'].append(f"{xml_file}: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"❌ Error reading JAR: {e}")
            debug_info['errors'].append(str(e))
        
        return debug_info
