from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTextEdit, QTableWidget,
    QTableWidgetItem, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import json

class ProcessorTestThread(QThread):
    result_ready = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, processor_sandbox, processor_class, input_item):
        super().__init__()
        self.processor_sandbox = processor_sandbox
        self.processor_class = processor_class
        self.input_item = input_item
    
    def run(self):
        try:
            result = self.processor_sandbox.test_processor(
                self.processor_class,
                self.input_item
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

class ProcessorTesterTab(QWidget):
    def __init__(self, processor_sandbox):
        super().__init__()
        self.processor_sandbox = processor_sandbox
        self.project_path = None
        self.analysis = None
        self.test_thread = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("⚙️ Processor Tester")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Controls
        controls = self.create_controls()
        layout.addLayout(controls)
        
        # Splitter for input/output
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Input section
        input_widget = self.create_input_section()
        splitter.addWidget(input_widget)
        
        # Output section
        output_widget = self.create_output_section()
        splitter.addWidget(output_widget)
        
        layout.addWidget(splitter)
        
        # Diff viewer
        diff_label = QLabel("Changes (Diff):")
        diff_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(diff_label)
        
        self.diff_table = QTableWidget()
        self.diff_table.setColumnCount(3)
        self.diff_table.setHorizontalHeaderLabels(["Field", "Before", "After"])
        layout.addWidget(self.diff_table)
        
        self.setLayout(layout)
    
    def create_controls(self):
        layout = QHBoxLayout()
        
        # Processor selection
        processor_label = QLabel("Select Processor:")
        self.processor_combo = QComboBox()
        self.processor_combo.setMinimumWidth(300)
        
        # Test button
        self.test_button = QPushButton("▶ Test Processor")
        self.test_button.clicked.connect(self.test_processor)
        self.test_button.setEnabled(False)
        
        layout.addWidget(processor_label)
        layout.addWidget(self.processor_combo)
        layout.addWidget(self.test_button)
        layout.addStretch()
        
        return layout
    
    def create_input_section(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Input Item (JSON):")
        label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(label)
        
        self.input_editor = QTextEdit()
        self.input_editor.setFont(QFont("Consolas", 10))
        self.input_editor.setPlaceholderText('{\n  "id": 1,\n  "name": "Test Item",\n  "value": 100\n}')
        layout.addWidget(self.input_editor)
        
        widget.setLayout(layout)
        return widget
    
    def create_output_section(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Output Item (JSON):")
        label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(label)
        
        self.output_viewer = QTextEdit()
        self.output_viewer.setFont(QFont("Consolas", 10))
        self.output_viewer.setReadOnly(True)
        layout.addWidget(self.output_viewer)
        
        widget.setLayout(layout)
        return widget
    
    def set_project(self, project_path: str, analysis: dict):
        """Update tab with project information"""
        self.project_path = project_path
        self.analysis = analysis
        
        # Populate processors
        self.processor_combo.clear()
        processors = analysis.get('processors', [])
        for processor in processors:
            self.processor_combo.addItem(
                processor['name'],
                processor['fullName']
            )
        
        self.test_button.setEnabled(len(processors) > 0)
        
        # Set sample input
        if processors:
            self.input_editor.setPlainText(json.dumps({
                "id": 1,
                "name": "Sample Item",
                "value": 100,
                "status": "PENDING"
            }, indent=2))
    
    def test_processor(self):
        processor_class = self.processor_combo.currentData()
        
        if not processor_class:
            QMessageBox.warning(self, "Error", "Please select a processor")
            return
        
        # Parse input JSON
        try:
            input_item = json.loads(self.input_editor.toPlainText())
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Error", f"Invalid JSON input:\n{e}")
            return
        
        self.test_button.setEnabled(False)
        self.test_button.setText("⏳ Processing...")
        
        # Run in background
        self.test_thread = ProcessorTestThread(
            self.processor_sandbox,
            processor_class,
            input_item
        )
        self.test_thread.result_ready.connect(self.handle_result)
        self.test_thread.error_occurred.connect(self.handle_error)
        self.test_thread.finished.connect(self.test_finished)
        self.test_thread.start()
    
    def handle_result(self, result: dict):
        if result['success']:
            output = result['output']
            diff = result['diff']
            filtered = result['filtered']
            
            if filtered:
                self.output_viewer.setPlainText("⚠️ Item was FILTERED (returned null)")
            else:
                self.output_viewer.setPlainText(json.dumps(output, indent=2))
            
            # Display diff
            self.display_diff(diff)
        else:
            QMessageBox.critical(self, "Error", result['error'])
    
    def handle_error(self, error: str):
        QMessageBox.critical(self, "Error", f"Failed to test processor:\n{error}")
    
    def test_finished(self):
        self.test_button.setEnabled(True)
        self.test_button.setText("▶ Test Processor")
    
    def display_diff(self, diff: dict):
        """Display differences in table"""
        self.diff_table.setRowCount(len(diff))
        
        for row, (field, changes) in enumerate(diff.items()):
            if field == 'filtered':
                continue
            
            self.diff_table.setItem(row, 0, QTableWidgetItem(field))
            self.diff_table.setItem(row, 1, QTableWidgetItem(str(changes.get('old', ''))))
            self.diff_table.setItem(row, 2, QTableWidgetItem(str(changes.get('new', ''))))
        
        self.diff_table.resizeColumnsToContents()
