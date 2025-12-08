import sys
import os
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import core components
from core.jvm_manager import JVMManager
from core.class_loader import DynamicClassLoader
from core.batch_analyzer import BatchAnalyzer
from core.reader_sandbox import ReaderSandbox
from core.processor_sandbox import ProcessorSandbox
from core.writer_sandbox import WriterSandbox
from core.step_sandbox import StepSandbox
from core.job_sandbox import JobSandbox

# Import UI
from ui.main_window import MainWindow

class BatcherManApp:
    """Main application class"""
    
    def __init__(self):
        self.jvm_manager = None
        self.class_loader = None
        self.batch_analyzer = None
        self.reader_sandbox = None
        self.processor_sandbox = None
        self.writer_sandbox = None
        self.step_sandbox = None
        self.job_sandbox = None
    
    def initialize_core(self):
        """Initialize core components"""
        try:
            # Start JVM
            self.jvm_manager = JVMManager()
            
            # Add Spring Batch dependencies
            self.jvm_manager.add_spring_batch_dependencies()
            
            # Start JVM
            if not self.jvm_manager.start():
                raise Exception("Failed to start JVM")
            
            # Create core components
            self.class_loader = DynamicClassLoader(self.jvm_manager)
            self.batch_analyzer = BatchAnalyzer(self.class_loader)
            self.reader_sandbox = ReaderSandbox(self.class_loader)
            self.processor_sandbox = ProcessorSandbox(self.class_loader)
            self.writer_sandbox = WriterSandbox(self.class_loader)
            self.step_sandbox = StepSandbox(
                self.class_loader,
                self.reader_sandbox,
                self.processor_sandbox,
                self.writer_sandbox
            )
            self.job_sandbox = JobSandbox(self.class_loader, self.step_sandbox)
            
            logging.info("✅ Core components initialized")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize core: {e}")
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        if self.jvm_manager:
            self.jvm_manager.stop()

def main():
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("BatcherMan Desktop")
    app.setOrganizationName("Synthos")
    
    # Load dark theme
    style_path = Path(__file__).parent / 'resources' / 'styles.qss'
    if style_path.exists():
        with open(style_path, 'r') as f:
            app.setStyleSheet(f.read())
    
    # Initialize BatcherMan
    batcherman = BatcherManApp()
    
    if not batcherman.initialize_core():
        QMessageBox.critical(
            None,
            "Initialization Error",
            "Failed to initialize BatcherMan core components.\n"
            "Please ensure Java is installed and Spring Batch JARs are in the 'lib' folder."
        )
        sys.exit(1)
    
    # Create main window
    window = MainWindow(
        batcherman.batch_analyzer,
        batcherman.reader_sandbox,
        batcherman.processor_sandbox,
        batcherman.writer_sandbox,
        batcherman.step_sandbox,
        batcherman.job_sandbox
    )
    window.show()
    
    # Run application
    exit_code = app.exec()
    
    # Cleanup
    batcherman.cleanup()
    
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
