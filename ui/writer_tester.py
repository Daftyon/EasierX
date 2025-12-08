from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTextEdit, QTableWidget,
    QTableWidgetItem, QMessageBox, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import json

class WriterTestThread(QThread):
    result_ready = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, writer_sandbox, writer_class, items):
        super().__init__()
        self.writer_sandbox = writer_sandbox
        self.writer_class = writer_class
        self.items = items
    
    def run(self):
        try:
            result = self.writer_sandbox.test_writer(
                self.writer_class,
                self.items
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

class WriterTesterTab(QWidget):
    def __init__(self, writer_sandbox):
        super().__init__()
        self.writer_sandbox = writer_sandbox
        self.project_path = None
        self.analysis = None
        self.test_thread = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("✍️ Writer Tester")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Controls
        controls = self.create_controls()
        layout.addLayout(controls)
        
        # Items input
        items_label = QLabel("Items to Write (JSON Array):")
        items_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(items_label)
        
        self.items_editor = QTextEdit()
        self.items_editor.setFont(QFont("Consolas", 10))
        self.items_editor.setPlaceholderText('[\n  {"id": 1, "name": "Item 1"},\n  {"id": 2, "name": "Item 2"}\n]')
        self.items_editor.setMaximumHeight(200)
        layout.addWidget(self.items_editor)
        
        # Log output
        log_label = QLabel("Execution Log:")
        log_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_output)
        
        self.setLayout(layout)
    
    def create_controls(self):
        layout = QHBoxLayout()
        
        # Writer selection
        writer_label = QLabel("Select Writer:")
        self.writer_combo = QComboBox()
        self.writer_combo.setMinimumWidth(300)
        
        # Test button
        self.test_button = QPushButton("▶ Test Writer")
        self.test_button.clicked.connect(self.test_writer)
        self.test_button.setEnabled(False)
        
        layout.addWidget(writer_label)
        layout.addWidget(self.writer_combo)
        layout.addWidget(self.test_button)
        layout.addStretch()
        
        return layout
    
    def set_project(self, project_path: str, analysis: dict):
        """Update tab with project information"""
        self.project_path = project_path
        self.analysis = analysis
        
        # Populate writers
        self.writer_combo.clear()
        writers = analysis.get('writers', [])
        for writer in writers:
            self.writer_combo.addItem(
                writer['name'],
                writer['fullName']
            )
        
        self.test_button.setEnabled(len(writers) > 0)
        
        # Set sample items
        if writers:
            self.items_editor.setPlainText(json.dumps([
                {"id": 1, "name": "Item 1", "value": 100},
                {"id": 2, "name": "Item 2", "value": 200},
                {"id": 3, "name": "Item 3", "value": 300}
            ], indent=2))
    
    def test_writer(self):
        writer_class = self.writer_combo.currentData()
        
        if not writer_class:
            QMessageBox.warning(self, "Error", "Please select a writer")
            return
        
        # Parse items JSON
        try:
            items = json.loads(self.items_editor.toPlainText())
            if not isinstance(items, list):
                raise ValueError("Input must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            QMessageBox.warning(self, "Error", f"Invalid JSON input:\n{e}")
            return
        
        self.log_output.append(f"\n🔄 Testing writer: {self.writer_combo.currentText()}")
        self.log_output.append(f"   Items to write: {len(items)}")
        
        self.test_button.setEnabled(False)
        self.test_button.setText("⏳ Writing...")
        
        # Run in background
        self.test_thread = WriterTestThread(
            self.writer_sandbox,
            writer_class,
            items
        )
        self.test_thread.result_ready.connect(self.handle_result)
        self.test_thread.error_occurred.connect(self.handle_error)
        self.test_thread.finished.connect(self.test_finished)
        self.test_thread.start()
    
    def handle_result(self, result: dict):
        if result['success']:
            items_written = result['itemsWritten']
            writer_type = result['writerType']
            output_file = result.get('outputFile')
            sql = result.get('sqlStatements')
            
            self.log_output.append(f"✅ Successfully wrote {items_written} items")
            self.log_output.append(f"   Writer type: {writer_type}")
            
            if output_file:
                self.log_output.append(f"   Output file: {output_file}")
            
            if sql:
                self.log_output.append(f"   SQL statements executed:")
                for stmt in sql[:5]:  # Show first 5
                    self.log_output.append(f"     {stmt}")
        else:
            self.log_output.append(f"❌ Error: {result['error']}")
            QMessageBox.critical(self, "Error", result['error'])
    
    def handle_error(self, error: str):
        self.log_output.append(f"❌ Exception: {error}")
        QMessageBox.critical(self, "Error", f"Failed to test writer:\n{error}")
    
    def test_finished(self):
        self.test_button.setEnabled(True)
        self.test_button.setText("▶ Test Writer")
