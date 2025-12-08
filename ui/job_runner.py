from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QProgressBar, QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

class JobRunThread(QThread):
    result_ready = Signal(dict)
    error_occurred = Signal(str)
    step_started = Signal(str)
    step_completed = Signal(str, dict)
    
    def __init__(self, job_sandbox, job_name, steps_config):
        super().__init__()
        self.job_sandbox = job_sandbox
        self.job_name = job_name
        self.steps_config = steps_config
    
    def run(self):
        try:
            result = self.job_sandbox.run_job(
                self.job_name,
                self.steps_config
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

class JobRunnerTab(QWidget):
    def __init__(self, job_sandbox):
        super().__init__()
        self.job_sandbox = job_sandbox
        self.project_path = None
        self.analysis = None
        self.run_thread = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🚀 Job Runner")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Job configuration
        config_group = self.create_config_section()
        layout.addWidget(config_group)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Step execution tree
        steps_label = QLabel("Step Execution Status:")
        steps_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(steps_label)
        
        self.steps_tree = QTreeWidget()
        self.steps_tree.setHeaderLabels(["Step", "Status", "Read", "Written", "Duration"])
        self.steps_tree.setMaximumHeight(200)
        layout.addWidget(self.steps_tree)
        
        # Log output
        log_label = QLabel("Execution Log:")
        log_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_output)
        
        self.setLayout(layout)
    
    def create_config_section(self):
        group = QGroupBox("Job Configuration")
        layout = QVBoxLayout()
        
        # Job selection
        job_layout = QHBoxLayout()
        job_layout.addWidget(QLabel("Select Job:"))
        self.job_combo = QComboBox()
        self.job_combo.setMinimumWidth(400)
        job_layout.addWidget(self.job_combo)
        job_layout.addStretch()
        layout.addLayout(job_layout)
        
        # Job description
        self.job_description = QLabel("No job selected")
        self.job_description.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.job_description)
        
        # Run button
        button_layout = QHBoxLayout()
        self.run_button = QPushButton("▶ Run Job")
        self.run_button.clicked.connect(self.run_job)
        self.run_button.setEnabled(False)
        self.run_button.setMinimumHeight(40)
        
        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(40)
        
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group
    
    def set_project(self, project_path: str, analysis: dict):
        """Update tab with project information"""
        self.project_path = project_path
        self.analysis = analysis
        
        # Populate jobs
        self.job_combo.clear()
        jobs = analysis.get('jobs', [])
        
        if not jobs:
            # Create a mock job from available components
            self.job_combo.addItem("Test Job (Auto-generated)", self.create_test_job())
        else:
            for job in jobs:
                self.job_combo.addItem(job['name'], job)
        
        self.run_button.setEnabled(True)
        self.update_job_description()
        
        self.job_combo.currentIndexChanged.connect(self.update_job_description)
    
    def create_test_job(self):
        """Create a test job configuration from available components"""
        readers = self.analysis.get('readers', [])
        processors = self.analysis.get('processors', [])
        writers = self.analysis.get('writers', [])
        
        if not readers or not writers:
            return None
        
        return {
            'name': 'test-job',
            'steps': [
                {
                    'name': 'test-step-1',
                    'reader': readers[0]['fullName'],
                    'processor': processors[0]['fullName'] if processors else None,
                    'writer': writers[0]['fullName'],
                    'chunkSize': 10
                }
            ]
        }
    
    def update_job_description(self):
        """Update job description label"""
        job_config = self.job_combo.currentData()
        
        if not job_config:
            self.job_description.setText("No job available")
            return
        
        steps = job_config.get('steps', [])
        desc = f"Job contains {len(steps)} step(s)"
        self.job_description.setText(desc)
    
    def run_job(self):
        job_config = self.job_combo.currentData()
        
        if not job_config:
            QMessageBox.warning(self, "Error", "Please select a job")
            return
        
        job_name = job_config['name']
        steps_config = job_config['steps']
        
        self.log_output.append(f"\n🚀 Starting job: {job_name}")
        self.log_output.append(f"   Steps: {len(steps_config)}")
        
        # Setup tree
        self.steps_tree.clear()
        for step in steps_config:
            item = QTreeWidgetItem([step['name'], "⏳ Pending", "0", "0", "0.00s"])
            item.setData(0, Qt.ItemDataRole.UserRole, step['name'])
            self.steps_tree.addTopLevelItem(item)
        
        self.run_button.setEnabled(False)
        self.run_button.setText("⏳ Running...")
        self.stop_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(steps_config))
        self.progress_bar.setValue(0)
        
        # Run in background
        self.run_thread = JobRunThread(
            self.job_sandbox,
            job_name,
            steps_config
        )
        self.run_thread.result_ready.connect(self.handle_result)
        self.run_thread.error_occurred.connect(self.handle_error)
        self.run_thread.finished.connect(self.run_finished)
        self.run_thread.start()
    
    def handle_result(self, result: dict):
        if result['success']:
            job_name = result['jobName']
            duration = result['totalDuration']
            step_results = result['stepResults']
            
            self.log_output.append(f"✅ Job completed: {job_name}")
            self.log_output.append(f"   Total duration: {duration:.2f}s")
            
            # Update tree
            for i, step_result in enumerate(step_results):
                item = self.steps_tree.topLevelItem(i)
                metrics = step_result['result']['metrics']
                
                item.setText(1, "✅ Completed")
                item.setText(2, str(metrics['readCount']))
                item.setText(3, str(metrics['writeCount']))
                item.setText(4, f"{metrics['duration']:.2f}s")
                item.setForeground(1, QColor(0, 200, 0))
            
            self.progress_bar.setValue(len(step_results))
            
        else:
            self.log_output.append(f"❌ Job failed: {result['error']}")
            QMessageBox.critical(self, "Error", result['error'])
    
    def handle_error(self, error: str):
        self.log_output.append(f"❌ Exception: {error}")
        QMessageBox.critical(self, "Error", f"Failed to run job:\n{error}")
    
    def run_finished(self):
        self.run_button.setEnabled(True)
        self.run_button.setText("▶ Run Job")
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
