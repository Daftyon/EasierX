from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTextEdit, QSpinBox,
    QMessageBox, QProgressBar, QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

class StepRunThread(QThread):
    result_ready = Signal(dict)
    error_occurred = Signal(str)
    progress_update = Signal(str)
    
    def __init__(self, step_sandbox, step_name, reader, processor, writer, chunk_size):
        super().__init__()
        self.step_sandbox = step_sandbox
        self.step_name = step_name
        self.reader = reader
        self.processor = processor
        self.writer = writer
        self.chunk_size = chunk_size
    
    def run(self):
        try:
            self.progress_update.emit("Initializing step...")
            result = self.step_sandbox.run_step(
                self.step_name,
                self.reader,
                self.processor,
                self.writer,
                self.chunk_size
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

class StepRunnerTab(QWidget):
    def __init__(self, step_sandbox):
        super().__init__()
        self.step_sandbox = step_sandbox
        self.project_path = None
        self.analysis = None
        self.run_thread = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🔄 Step Runner")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Configuration
        config_group = self.create_config_section()
        layout.addWidget(config_group)
        
        # Metrics
        metrics_group = self.create_metrics_section()
        layout.addWidget(metrics_group)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Log
        log_label = QLabel("Execution Log:")
        log_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_output)
        
        self.setLayout(layout)
    
    def create_config_section(self):
        group = QGroupBox("Step Configuration")
        layout = QVBoxLayout()
        
        # Reader
        reader_layout = QHBoxLayout()
        reader_layout.addWidget(QLabel("Reader:"))
        self.reader_combo = QComboBox()
        self.reader_combo.setMinimumWidth(300)
        reader_layout.addWidget(self.reader_combo)
        reader_layout.addStretch()
        layout.addLayout(reader_layout)
        
        # Processor
        processor_layout = QHBoxLayout()
        processor_layout.addWidget(QLabel("Processor:"))
        self.processor_combo = QComboBox()
        self.processor_combo.setMinimumWidth(300)
        self.processor_combo.addItem("(None)", None)
        processor_layout.addWidget(self.processor_combo)
        processor_layout.addStretch()
        layout.addLayout(processor_layout)
        
        # Writer
        writer_layout = QHBoxLayout()
        writer_layout.addWidget(QLabel("Writer:"))
        self.writer_combo = QComboBox()
        self.writer_combo.setMinimumWidth(300)
        writer_layout.addWidget(self.writer_combo)
        writer_layout.addStretch()
        layout.addLayout(writer_layout)
        
        # Chunk size
        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(QLabel("Chunk Size:"))
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setMinimum(1)
        self.chunk_spin.setMaximum(1000)
        self.chunk_spin.setValue(10)
        chunk_layout.addWidget(self.chunk_spin)
        chunk_layout.addStretch()
        layout.addLayout(chunk_layout)
        
        # Run button
        self.run_button = QPushButton("▶ Run Step")
        self.run_button.clicked.connect(self.run_step)
        self.run_button.setEnabled(False)
        layout.addWidget(self.run_button)
        
        group.setLayout(layout)
        return group
    
    def create_metrics_section(self):
        group = QGroupBox("Metrics")
        layout = QHBoxLayout()
        
        self.read_count_label = QLabel("Read: 0")
        self.write_count_label = QLabel("Written: 0")
        self.filter_count_label = QLabel("Filtered: 0")
        self.skip_count_label = QLabel("Skipped: 0")
        self.duration_label = QLabel("Duration: 0.00s")
        
        for label in [self.read_count_label, self.write_count_label,
                      self.filter_count_label, self.skip_count_label,
                      self.duration_label]:
            label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            layout.addWidget(label)
        
        group.setLayout(layout)
        return group
    
    def set_project(self, project_path: str, analysis: dict):
        """Update tab with project information"""
        self.project_path = project_path
        self.analysis = analysis
        
        # Populate combos
        self.reader_combo.clear()
        for reader in analysis.get('readers', []):
            self.reader_combo.addItem(reader['name'], reader['fullName'])
        
        self.processor_combo.clear()
        self.processor_combo.addItem("(None)", None)
        for processor in analysis.get('processors', []):
            self.processor_combo.addItem(processor['name'], processor['fullName'])
        
        self.writer_combo.clear()
        for writer in analysis.get('writers', []):
            self.writer_combo.addItem(writer['name'], writer['fullName'])
        
        has_components = (len(analysis.get('readers', [])) > 0 and
                         len(analysis.get('writers', [])) > 0)
        self.run_button.setEnabled(has_components)
    
    def run_step(self):
        reader = self.reader_combo.currentData()
        processor = self.processor_combo.currentData()
        writer = self.writer_combo.currentData()
        chunk_size = self.chunk_spin.value()
        
        if not reader or not writer:
            QMessageBox.warning(self, "Error", "Please select reader and writer")
            return
        
        self.log_output.append(f"\n🔄 Running step with chunk size: {chunk_size}")
        self.log_output.append(f"   Reader: {self.reader_combo.currentText()}")
        if processor:
            self.log_output.append(f"   Processor: {self.processor_combo.currentText()}")
        self.log_output.append(f"   Writer: {self.writer_combo.currentText()}")
        
        self.run_button.setEnabled(False)
        self.run_button.setText("⏳ Running...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Run in background
        self.run_thread = StepRunThread(
            self.step_sandbox,
            "test-step",
            reader,
            processor,
            writer,
            chunk_size
        )
        self.run_thread.result_ready.connect(self.handle_result)
        self.run_thread.error_occurred.connect(self.handle_error)
        self.run_thread.progress_update.connect(self.log_output.append)
        self.run_thread.finished.connect(self.run_finished)
        self.run_thread.start()
    
    def handle_result(self, result: dict):
        if result['success']:
            metrics = result['metrics']
            
            self.read_count_label.setText(f"Read: {metrics['readCount']}")
            self.write_count_label.setText(f"Written: {metrics['writeCount']}")
            self.filter_count_label.setText(f"Filtered: {metrics['filterCount']}")
            self.skip_count_label.setText(f"Skipped: {metrics['skipCount']}")
            self.duration_label.setText(f"Duration: {metrics['duration']:.2f}s")
            
            self.log_output.append(f"✅ Step completed successfully!")
            self.log_output.append(f"   Total duration: {metrics['duration']:.2f}s")
        else:
            self.log_output.append(f"❌ Step failed: {result['error']}")
            QMessageBox.critical(self, "Error", result['error'])
    
    def handle_error(self, error: str):
        self.log_output.append(f"❌ Exception: {error}")
        QMessageBox.critical(self, "Error", f"Failed to run step:\n{error}")
    
    def run_finished(self):
        self.run_button.setEnabled(True)
        self.run_button.setText("▶ Run Step")
        self.progress_bar.setVisible(False)
