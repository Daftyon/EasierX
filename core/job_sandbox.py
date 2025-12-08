import jpype
import jpype.imports
from typing import Dict, Any, List
import logging
import time

class JobSandbox:
    """Execute a complete Job with multiple steps"""
    
    def __init__(self, class_loader, step_sandbox):
        self.class_loader = class_loader
        self.step_sandbox = step_sandbox
        self.logger = logging.getLogger(__name__)
    
    def run_job(
        self,
        job_name: str,
        steps_config: List[Dict[str, Any]],
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a complete job with multiple steps
        
        Args:
            job_name: Name of the job
            steps_config: List of step configurations
            parameters: Job parameters
            
        Returns:
            {
                'success': bool,
                'jobName': str,
                'status': str,
                'stepResults': List[Dict],
                'totalDuration': float,
                'error': Optional[str]
            }
        """
        start_time = time.time()
        step_results = []
        
        try:
            self.logger.info(f"▶ Starting job: {job_name}")
            
            # Execute each step
            for step_config in steps_config:
                step_name = step_config['name']
                self.logger.info(f"  ▶ Running step: {step_name}")
                
                step_result = self.step_sandbox.run_step(
                    step_name=step_name,
                    reader_class=step_config['reader'],
                    processor_class=step_config.get('processor'),
                    writer_class=step_config['writer'],
                    chunk_size=step_config.get('chunkSize', 10)
                )
                
                step_results.append({
                    'stepName': step_name,
                    'result': step_result
                })
                
                # If step failed, stop job
                if not step_result['success']:
                    raise Exception(f"Step {step_name} failed: {step_result['error']}")
            
            total_duration = time.time() - start_time
            
            self.logger.info(f"✅ Job completed: {job_name} in {total_duration:.2f}s")
            
            return {
                'success': True,
                'jobName': job_name,
                'status': 'COMPLETED',
                'stepResults': step_results,
                'totalDuration': total_duration,
                'error': None
            }
            
        except Exception as e:
            total_duration = time.time() - start_time
            self.logger.error(f"❌ Job failed: {e}")
            
            return {
                'success': False,
                'jobName': job_name,
                'status': 'FAILED',
                'stepResults': step_results,
                'totalDuration': total_duration,
                'error': str(e)
            }
