from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QTextEdit, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFont, QPen, QBrush, QColor, QPainter

class PipelineVisualizerTab(QWidget):
    def __init__(self, api_client=None):
        super().__init__()
        self.api_client = api_client
        self.project_path = None
        self.analysis = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📊 Pipeline Visualizer")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Visual representation of your Spring Batch pipeline")
        desc.setStyleSheet("color: #888;")
        layout.addWidget(desc)
        
        # Graphics view for pipeline
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        
        # Fixed: Use correct PySide6 syntax
        self.view.setRenderHints(
            QPainter.RenderHint.Antialiasing | 
            QPainter.RenderHint.SmoothPixmapTransform
        )
        
        layout.addWidget(self.view)
        
        # Component summary
        summary_label = QLabel("Component Summary:")
        summary_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(summary_label)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.summary_text)
        
        self.setLayout(layout)
    
    def set_project(self, project_path: str, analysis: dict):
        """Update tab with project information"""
        self.project_path = project_path
        self.analysis = analysis
        
        # Draw pipeline
        self.draw_pipeline(analysis)
        
        # Update summary
        self.update_summary(analysis)
    
    def draw_pipeline(self, analysis: dict):
        """Draw the batch pipeline visually"""
        self.scene.clear()
        
        readers = analysis.get('readers', [])
        processors = analysis.get('processors', [])
        writers = analysis.get('writers', [])
        
        x = 50
        y = 50
        
        # Draw readers
        if readers:
            self._draw_section("READERS", readers, x, y, QColor(100, 150, 255))
            y += len(readers) * 60 + 100
        
        # Draw processors
        if processors:
            self._draw_section("PROCESSORS", processors, x, y, QColor(255, 200, 100))
            y += len(processors) * 60 + 100
        
        # Draw writers
        if writers:
            self._draw_section("WRITERS", writers, x, y, QColor(100, 255, 150))
    
    def _draw_section(self, title: str, components: list, x: int, y: int, color: QColor):
        """Draw a section of components"""
        # Title
        title_item = QGraphicsTextItem(title)
        title_item.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_item.setPos(x, y)
        title_item.setDefaultTextColor(color)
        self.scene.addItem(title_item)
        
        y += 40
        
        # Components
        for i, component in enumerate(components):
            # Box
            rect = QGraphicsRectItem(x, y + i * 60, 300, 50)
            rect.setBrush(QBrush(color.lighter(150)))
            rect.setPen(QPen(color, 2))
            self.scene.addItem(rect)
            
            # Text
            text = QGraphicsTextItem(component['name'])
            text.setFont(QFont("Arial", 11))
            text.setPos(x + 10, y + i * 60 + 15)
            self.scene.addItem(text)
    
    def update_summary(self, analysis: dict):
        """Update component summary text"""
        readers = analysis.get('readers', [])
        processors = analysis.get('processors', [])
        writers = analysis.get('writers', [])
        
        summary = f"""
📖 Readers: {len(readers)}
{chr(10).join(f"   • {r['name']}" for r in readers[:5])}
{f"   ... and {len(readers) - 5} more" if len(readers) > 5 else ""}

⚙️ Processors: {len(processors)}
{chr(10).join(f"   • {p['name']}" for p in processors[:5])}
{f"   ... and {len(processors) - 5} more" if len(processors) > 5 else ""}

✍️ Writers: {len(writers)}
{chr(10).join(f"   • {w['name']}" for w in writers[:5])}
{f"   ... and {len(writers) - 5} more" if len(writers) > 5 else ""}
        """.strip()
        
        self.summary_text.setPlainText(summary)
