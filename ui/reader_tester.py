from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

class ReaderTestThread(QThread):
    result_ready = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, reader_sandbox, project_path, reader_name, max_items):
        super().__init__()
        self.reader_sandbox = reader_sandbox
        self.project_path = project_path
        self.reader_name = reader_name
        self.max_items = max_items
    
    def run(self):
        try:
            result = self.reader_sandbox.test_reader(
                self.reader_name,
                self.max_items
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

class ReaderTesterTab(QWidget):
    def __init__(self, reader_sandbox):
        super().__init__()
        self.reader_sandbox = reader_sandbox
        self.project_path = None
        self.analysis = None
        self.test_thread = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📖 Reader Tester")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Controls
        controls = self.create_controls()
        layout.addLayout(controls)
        
        # Log output
        log_label = QLabel("Execution Log:")
        log_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        self.log_output.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_output)
        
        # Results table
        results_label = QLabel("Read Items:")
        results_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(results_label)
        
        self.results_table = QTableWidget()
        layout.addWidget(self.results_table)
        
        self.setLayout(layout)
    
    def create_controls(self):
        layout = QHBoxLayout()
        
        # Reader selection
        reader_label = QLabel("Select Reader:")
        self.reader_combo = QComboBox()
        self.reader_combo.setMinimumWidth(300)
        
        # Max items
        max_items_label = QLabel("Max Items:")
        self.max_items_spin = QSpinBox()
        self.max_items_spin.setMinimum(1)
        self.max_items_spin.setMaximum(10000)
        self.max_items_spin.setValue(100)
        
        # Test button
        self.test_button = QPushButton("▶ Test Reader")
        self.test_button.clicked.connect(self.test_reader)
        self.test_button.setEnabled(False)
        
        layout.addWidget(reader_label)
        layout.addWidget(self.reader_combo)
        layout.addWidget(max_items_label)
        layout.addWidget(self.max_items_spin)
        layout.addWidget(self.test_button)
        layout.addStretch()
        
        return layout
    
    def set_project(self, project_path: str, analysis: dict):
        """Update tab with project information"""
        self.project_path = project_path
        self.analysis = analysis
        
        # Populate readers combo
        self.reader_combo.clear()
        readers = analysis.get('readers', [])
        for reader in readers:
            self.reader_combo.addItem(reader.get('name', 'Unknown'))
        
        self.test_button.setEnabled(len(readers) > 0)
        
        if len(readers) > 0:
            self.log_output.append(f"✅ Found {len(readers)} readers")
        else:
            self.log_output.append("⚠️ No readers found in project")
    
    def test_reader(self):
        reader_name = self.reader_combo.currentText()
        max_items = self.max_items_spin.value()
        
        if not reader_name:
            QMessageBox.warning(self, "Error", "Please select a reader")
            return
        
        self.log_output.append(f"\n🔄 Testing reader: {reader_name}")
        self.log_output.append(f"   Max items: {max_items}")
        
        self.test_button.setEnabled(False)
        self.test_button.setText("⏳ Testing...")
        
        # Run in background thread
        self.test_thread = ReaderTestThread(
            self.reader_sandbox,
            self.project_path,
            reader_name,
            max_items
        )
        self.test_thread.result_ready.connect(self.handle_result)
        self.test_thread.error_occurred.connect(self.handle_error)
        self.test_thread.finished.connect(self.test_finished)
        self.test_thread.start()
    
    def handle_result(self, result: dict):
        if result.get('success'):
            data = result.get('data', {})
            items = data.get('items', [])
            item_count = data.get('itemCount', 0)
            
            self.log_output.append(f"✅ Successfully read {item_count} items")
            
            # Display in table
            self.display_items(items)
        else:
            error = result.get('error', 'Unknown error')
            self.log_output.append(f"❌ Error: {error}")
            QMessageBox.critical(self, "Error", error)
    
    def handle_error(self, error: str):
        self.log_output.append(f"❌ Exception: {error}")
        QMessageBox.critical(self, "Error", f"Failed to test reader:\n{error}")
    
    def test_finished(self):
        self.test_button.setEnabled(True)
        self.test_button.setText("▶ Test Reader")
    
    def display_items(self, items: list):
        """Display items in table"""
        if not items:
            self.results_table.setRowCount(0)
            self.results_table.setColumnCount(0)
            return
        
        # Get all unique keys from items
        all_keys = set()
        for item in items:
            if isinstance(item, dict):
                all_keys.update(item.keys())
        
        columns = sorted(list(all_keys))
        
        # Setup table
        self.results_table.setRowCount(len(items))
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        
        # Fill table
        for row, item in enumerate(items):
            if isinstance(item, dict):
                for col, key in enumerate(columns):
                    value = str(item.get(key, ''))
                    self.results_table.setItem(row, col, QTableWidgetItem(value))
        
        self.results_table.resizeColumnsToContents()
