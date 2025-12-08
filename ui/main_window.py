from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from ui.reader_tester import ReaderTesterTab
from ui.processor_tester import ProcessorTesterTab
from ui.writer_tester import WriterTesterTab
from ui.step_runner import StepRunnerTab
from ui.job_runner import JobRunnerTab
from ui.pipeline_visualizer import PipelineVisualizerTab

class AnalyzeThread(QThread):
    result_ready = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, batch_analyzer, project_path):
        super().__init__()
        self.batch_analyzer = batch_analyzer
        self.project_path = project_path
    
    def run(self):
        try:
            result = self.batch_analyzer.analyze_project(self.project_path)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self, batch_analyzer, reader_sandbox, processor_sandbox, 
                 writer_sandbox, step_sandbox, job_sandbox):
        super().__init__()
        self.batch_analyzer = batch_analyzer
        self.reader_sandbox = reader_sandbox
        self.processor_sandbox = processor_sandbox
        self.writer_sandbox = writer_sandbox
        self.step_sandbox = step_sandbox
        self.job_sandbox = job_sandbox
        
        self.project_path = None
        self.project_analysis = None
        self.analyze_thread = None
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("BatcherMan Desktop - Spring Batch Testing Tool")
        self.setGeometry(100, 100, 1400, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        
        # Header
        header = self.create_header()
        main_layout.addLayout(header)
        
        # Project selector
        project_layout = self.create_project_selector()
        main_layout.addLayout(project_layout)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setEnabled(False)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
                
        self.pipeline_tab = PipelineVisualizerTab()
        self.reader_tab = ReaderTesterTab(self.reader_sandbox)
        self.processor_tab = ProcessorTesterTab(self.processor_sandbox)
        self.writer_tab = WriterTesterTab(self.writer_sandbox)
        self.step_tab = StepRunnerTab(self.step_sandbox)
        self.job_tab = JobRunnerTab(self.job_sandbox)
        
        self.tabs.addTab(self.pipeline_tab, "📊 Pipeline")
        self.tabs.addTab(self.reader_tab, "📖 Reader")
        self.tabs.addTab(self.processor_tab, "⚙️ Processor")
        self.tabs.addTab(self.writer_tab, "✍️ Writer")
        self.tabs.addTab(self.step_tab, "🔄 Step")
        self.tabs.addTab(self.job_tab, "🚀 Job")
        # Set minimum tab height
        self.tabs.setStyleSheet("""
            QTabBar::tab { 
                min-height: 40px; 
                padding: 0 24px;
            }
        """)
        main_layout.addWidget(self.tabs)
        
        central_widget.setLayout(main_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Ready - Load a Spring Batch project to begin")
    
    def create_header(self):
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 20, 0, 20)
        
        # Title
        title = QLabel("🚀 BatcherMan Desktop")
        title.setObjectName("mainTitle")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #FFFFFF; padding: 10px;")
        
        # Subtitle
        subtitle = QLabel("Spring Batch Testing & Debugging Tool")
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #909090; padding-bottom: 10px;")
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        
        return layout

    def create_project_selector(self):
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 10, 20, 20)
        
        label = QLabel("Project:")
        label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        label.setMinimumWidth(60)
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select Spring Batch JAR file or project folder...")
        self.path_input.setFont(QFont("Segoe UI", 11))
        self.path_input.setMinimumHeight(36)
        
        browse_btn = QPushButton("📁 Browse")
        browse_btn.setFont(QFont("Segoe UI", 11))
        browse_btn.setMinimumWidth(100)
        browse_btn.setMinimumHeight(36)
        browse_btn.clicked.connect(self.browse_project)
        
        analyze_btn = QPushButton("🔍 Analyze Project")
        analyze_btn.setProperty("primary", True)
        analyze_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        analyze_btn.setMinimumWidth(140)
        analyze_btn.setMinimumHeight(36)
        analyze_btn.clicked.connect(self.analyze_project)
        
        layout.addWidget(label)
        layout.addWidget(self.path_input, stretch=1)
        layout.addWidget(browse_btn)
        layout.addWidget(analyze_btn)
        
        return layout
    def browse_project(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Spring Batch JAR",
            "",
            "JAR Files (*.jar);;All Files (*)"
        )
        
        if file_path:
            self.path_input.setText(file_path)
    
    def analyze_project(self):
        project_path = self.path_input.text().strip()
        
        if not project_path:
            QMessageBox.warning(self, "Error", "Please select a project")
            return
        
        self.update_status("Analyzing project...")
        
        # Run analysis in background
        self.analyze_thread = AnalyzeThread(self.batch_analyzer, project_path)
        self.analyze_thread.result_ready.connect(self.handle_analysis_result)
        self.analyze_thread.error_occurred.connect(self.handle_analysis_error)
        self.analyze_thread.start()
    
    def handle_analysis_result(self, result: dict):
        self.project_path = self.path_input.text()
        self.project_analysis = result
        
        # Update tabs
        self.pipeline_tab.set_project(self.project_path, result)
        self.reader_tab.set_project(self.project_path, result)
        self.processor_tab.set_project(self.project_path, result)
        self.writer_tab.set_project(self.project_path, result)
        self.step_tab.set_project(self.project_path, result)
        self.job_tab.set_project(self.project_path, result)
        
        self.tabs.setEnabled(True)
        
        reader_count = len(result.get('readers', []))
        processor_count = len(result.get('processors', []))
        writer_count = len(result.get('writers', []))
        
        self.update_status(
            f"✅ Project loaded: {reader_count} readers, "
            f"{processor_count} processors, {writer_count} writers"
        )
        
        QMessageBox.information(
            self,
            "Success",
            f"Project analyzed successfully!\n\n"
            f"Found:\n"
            f"  • {reader_count} Readers\n"
            f"  • {processor_count} Processors\n"
            f"  • {writer_count} Writers"
        )
    
    def handle_analysis_error(self, error: str):
        self.update_status("❌ Analysis failed")
        QMessageBox.critical(
            self,
            "Error",
            f"Failed to analyze project:\n\n{error}"
        )
    
    def update_status(self, message: str):
        self.status_bar.showMessage(message)
