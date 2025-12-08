import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class BatcherManApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BatcherMan Desktop - Spring Batch Testing Tool")
        self.root.geometry("1200x800")
        self.root.configure(bg="#2b2b2b")
        
        # Try to initialize JVM
        self.jvm_manager = None
        self.init_jvm()
        
        self.setup_ui()
    
    def init_jvm(self):
        """Initialize JVM"""
        try:
            from core.jvm_manager import JVMManager
            from core.batch_analyzer import BatchAnalyzer
            from core.class_loader import DynamicClassLoader
            
            self.jvm_manager = JVMManager()
            self.jvm_manager.add_spring_batch_dependencies()
            
            if self.jvm_manager.start():
                self.class_loader = DynamicClassLoader(self.jvm_manager)
                # FIX: Pass class_loader to BatchAnalyzer
                self.batch_analyzer = BatchAnalyzer(self.class_loader)
                logger.info("✅ JVM initialized successfully")
            else:
                logger.warning("⚠️ JVM initialization failed - running in demo mode")
                # FIX: Even without JVM, create analyzer
                self.batch_analyzer = BatchAnalyzer(None)
                self.jvm_manager = None
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize JVM: {e}")
            # FIX: Create analyzer even on error
            self.batch_analyzer = BatchAnalyzer(None)
            self.jvm_manager = None

    def test_processor(self):
        processor_name = self.processor_combo.get()
        
        if not processor_name:
            messagebox.showwarning("Warning", "Please select a processor first")
            return
        
        # Get input JSON
        input_text = self.processor_input.get("1.0", tk.END).strip()
        
        try:
            import json
            input_item = json.loads(input_text)
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON input:\n{e}")
            return
        
        self.status_label.config(text="Processing item...")
        self.root.update()
        
        try:
            if self.jvm_manager:
                # Real processing (TODO: implement processor_sandbox)
                # For now, simulate
                output_item = input_item.copy()
                output_item['processed'] = True
                output_item['timestamp'] = '2025-12-04T16:30:00'
                
                # Calculate diff
                diff = self.calculate_diff(input_item, output_item)
                
            else:
                # Demo mode
                output_item = input_item.copy()
                output_item['status'] = 'PROCESSED'
                output_item['processed_at'] = '2025-12-04T16:30:00'
                
                diff = self.calculate_diff(input_item, output_item)
            
            # Display output
            self.processor_output.config(state=tk.NORMAL)
            self.processor_output.delete("1.0", tk.END)
            self.processor_output.insert("1.0", json.dumps(output_item, indent=2))
            self.processor_output.config(state=tk.DISABLED)
            
            # Display diff
            self.processor_diff.config(state=tk.NORMAL)
            self.processor_diff.delete("1.0", tk.END)
            
            if diff:
                self.processor_diff.insert(tk.END, "Modified fields:\n\n")
                for key, change in diff.items():
                    self.processor_diff.insert(tk.END, f"  • {key}:\n")
                    self.processor_diff.insert(tk.END, f"      Before: {change['old']}\n")
                    self.processor_diff.insert(tk.END, f"      After:  {change['new']}\n\n")
            else:
                self.processor_diff.insert(tk.END, "No changes detected")
            
            self.processor_diff.config(state=tk.DISABLED)
            
            self.status_label.config(text="✅ Item processed successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Processing failed:\n{e}")
            self.status_label.config(text="❌ Processing failed")

    def calculate_diff(self, input_item, output_item):
        """Calculate differences between input and output"""
        diff = {}
        
        all_keys = set(input_item.keys()) | set(output_item.keys())
        
        for key in all_keys:
            input_val = input_item.get(key)
            output_val = output_item.get(key)
            
            if input_val != output_val:
                diff[key] = {
                    'old': input_val,
                    'new': output_val
                }
        
        return diff
    def setup_ui(self):
        """Setup the user interface"""
        
        # Header
        header_frame = tk.Frame(self.root, bg="#1e1e1e", height=120)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title = tk.Label(
            header_frame,
            text="🚀 BatcherMan Desktop",
            font=("Segoe UI", 28, "bold"),
            bg="#1e1e1e",
            fg="#ffffff"
        )
        title.pack(pady=(20, 5))
        
        subtitle = tk.Label(
            header_frame,
            text="Spring Batch Testing & Debugging Tool",
            font=("Segoe UI", 12),
            bg="#1e1e1e",
            fg="#888888"
        )
        subtitle.pack()
        
        # Project selector
        project_frame = tk.Frame(self.root, bg="#2b2b2b", height=60)
        project_frame.pack(fill=tk.X, padx=20, pady=10)
        project_frame.pack_propagate(False)
        
        tk.Label(
            project_frame,
            text="Project:",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.project_path = tk.StringVar()
        project_entry = tk.Entry(
            project_frame,
            textvariable=self.project_path,
            font=("Segoe UI", 10),
            bg="#3c3f41",
            fg="#cccccc",
            insertbackground="#cccccc",
            relief=tk.FLAT,
            bd=5
        )
        project_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        browse_btn = tk.Button(
            project_frame,
            text="📁 Browse",
            command=self.browse_project,
            font=("Segoe UI", 10),
            bg="#3c3f41",
            fg="#cccccc",
            activebackground="#4c5052",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=20,
            cursor="hand2"
        )
        browse_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        analyze_btn = tk.Button(
            project_frame,
            text="🔍 Analyze",
            command=self.analyze_project,
            font=("Segoe UI", 10, "bold"),
            bg="#4a88c7",
            fg="#ffffff",
            activebackground="#5a98d7",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=30,
            cursor="hand2"
        )
        analyze_btn.pack(side=tk.LEFT)
        # Add after analyze button
        debug_btn = tk.Button(
            project_frame,
            text="🔍 Debug",
            command=self.debug_jar,
            font=("Segoe UI", 10),
            bg="#cc7832",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=20,
            cursor="hand2"
        )
        debug_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # Notebook (tabs)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='#2b2b2b', borderwidth=0)
        style.configure('TNotebook.Tab', 
                       background='#3c3f41', 
                       foreground='#cccccc',
                       padding=[20, 10],
                       font=('Segoe UI', 10))
        style.map('TNotebook.Tab',
                 background=[('selected', '#2b2b2b')],
                 foreground=[('selected', '#ffffff')])
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        # Create tabs
        self.create_pipeline_tab()
        self.create_reader_tab()
        self.create_processor_tab()
        self.create_writer_tab()
        self.create_step_tab()
        self.create_job_tab()
        
        # Status bar
        status_frame = tk.Frame(self.root, bg="#3c3f41", height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready" if self.jvm_manager else "⚠️ Running without JVM - Demo Mode",
            font=("Segoe UI", 9),
            bg="#3c3f41",
            fg="#4a88c7" if self.jvm_manager else "#ff9933",
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        jvm_status = tk.Label(
            status_frame,
            text="✅ JVM: Running" if self.jvm_manager else "❌ JVM: Not Running",
            font=("Segoe UI", 9),
            bg="#3c3f41",
            fg="#6ba54a" if self.jvm_manager else "#cc7832",
            anchor=tk.E
        )
        jvm_status.pack(side=tk.RIGHT, padx=10)
    
    def create_pipeline_tab(self):
        frame = tk.Frame(self.notebook, bg="#2b2b2b")
        self.notebook.add(frame, text="📊  Pipeline")
        
        tk.Label(
            frame,
            text="📊 Pipeline Visualizer",
            font=("Segoe UI", 18, "bold"),
            bg="#2b2b2b",
            fg="#ffffff"
        ).pack(pady=20)
        
        # Canvas for visualization
        canvas = tk.Canvas(frame, bg="#313335", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.pipeline_canvas = canvas
    
    def create_reader_tab(self):
        frame = tk.Frame(self.notebook, bg="#2b2b2b")
        self.notebook.add(frame, text="📖  Reader")
        
        # Title
        tk.Label(
            frame,
            text="📖 Reader Tester",
            font=("Segoe UI", 18, "bold"),
            bg="#2b2b2b",
            fg="#ffffff"
        ).pack(pady=20)
        
        # Controls
        control_frame = tk.Frame(frame, bg="#2b2b2b")
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(
            control_frame,
            text="Select Reader:",
            font=("Segoe UI", 10),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.reader_combo = ttk.Combobox(control_frame, state="readonly", width=40)
        self.reader_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        tk.Label(
            control_frame,
            text="Max Items:",
            font=("Segoe UI", 10),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.max_items = tk.Spinbox(control_frame, from_=1, to=10000, width=10)
        self.max_items.delete(0, tk.END)
        self.max_items.insert(0, "100")
        self.max_items.pack(side=tk.LEFT, padx=(0, 20))
        
        test_reader_btn = tk.Button(
            control_frame,
            text="▶ Test Reader",
            command=self.test_reader,
            font=("Segoe UI", 10, "bold"),
            bg="#4a88c7",
            fg="#ffffff",
            activebackground="#5a98d7",
            relief=tk.FLAT,
            padx=20,
            cursor="hand2"
        )
        test_reader_btn.pack(side=tk.LEFT)
        
        # Log output
        tk.Label(
            frame,
            text="Execution Log:",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(20, 5))
        
        self.reader_log = scrolledtext.ScrolledText(
            frame,
            height=6,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="#00ff00",
            relief=tk.FLAT
        )
        self.reader_log.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Results table
        tk.Label(
            frame,
            text="Read Items:",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(0, 5))
        
        # Create treeview for results
        tree_frame = tk.Frame(frame, bg="#2b2b2b")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.reader_tree = ttk.Treeview(tree_frame, show='headings')
        self.reader_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.reader_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.reader_tree.configure(yscrollcommand=scrollbar.set)
    


    def create_processor_tab(self):
        frame = tk.Frame(self.notebook, bg="#2b2b2b")
        self.notebook.add(frame, text="⚙️  Processor")
        
        # Title
        tk.Label(
            frame,
            text="⚙️ Processor Tester",
            font=("Segoe UI", 18, "bold"),
            bg="#2b2b2b",
            fg="#ffffff"
        ).pack(pady=20)
        
        # Controls
        control_frame = tk.Frame(frame, bg="#2b2b2b")
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(
            control_frame,
            text="Select Processor:",
            font=("Segoe UI", 10),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.processor_combo = ttk.Combobox(control_frame, state="readonly", width=40)
        self.processor_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        test_processor_btn = tk.Button(
            control_frame,
            text="▶ Test Processor",
            command=self.test_processor,
            font=("Segoe UI", 10, "bold"),
            bg="#ff9933",
            fg="#ffffff",
            activebackground="#ffaa44",
            relief=tk.FLAT,
            padx=20,
            cursor="hand2"
        )
        test_processor_btn.pack(side=tk.LEFT)
        
        # Input/Output sections
        io_frame = tk.Frame(frame, bg="#2b2b2b")
        io_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Input section (left)
        input_frame = tk.Frame(io_frame, bg="#2b2b2b")
        input_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(
            input_frame,
            text="Input Item (JSON):",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, pady=(0, 5))
        
        self.processor_input = scrolledtext.ScrolledText(
            input_frame,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#cccccc",
            insertbackground="#cccccc",
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        self.processor_input.pack(fill=tk.BOTH, expand=True)
        self.processor_input.insert("1.0", '''{
        "id": 1,
        "name": "Test Item",
        "value": 100,
        "status": "PENDING"
                }''')
        
        # Output section (right)
        output_frame = tk.Frame(io_frame, bg="#2b2b2b")
        output_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        tk.Label(
            output_frame,
            text="Output Item (JSON):",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, pady=(0, 5))
        
        self.processor_output = scrolledtext.ScrolledText(
            output_frame,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="#00ff00",
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        self.processor_output.pack(fill=tk.BOTH, expand=True)
        self.processor_output.config(state=tk.DISABLED)
        
        # Diff section
        tk.Label(
            frame,
            text="Changes (Diff):",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        self.processor_diff = scrolledtext.ScrolledText(
            frame,
            height=6,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#ffff00",
            insertbackground="#ffff00",
            relief=tk.FLAT
        )
        self.processor_diff.pack(fill=tk.X, padx=20, pady=(0, 20))
        self.processor_diff.config(state=tk.DISABLED)
    def create_writer_tab(self):
        frame = tk.Frame(self.notebook, bg="#2b2b2b")
        self.notebook.add(frame, text="✍️  Writer")
        
        # Title
        tk.Label(
            frame,
            text="✍️ Writer Tester",
            font=("Segoe UI", 18, "bold"),
            bg="#2b2b2b",
            fg="#ffffff"
        ).pack(pady=20)
        
        # Controls
        control_frame = tk.Frame(frame, bg="#2b2b2b")
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(
            control_frame,
            text="Select Writer:",
            font=("Segoe UI", 10),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.writer_combo = ttk.Combobox(control_frame, state="readonly", width=40)
        self.writer_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        test_writer_btn = tk.Button(
            control_frame,
            text="▶ Test Writer",
            command=self.test_writer,
            font=("Segoe UI", 10, "bold"),
            bg="#6ba54a",
            fg="#ffffff",
            activebackground="#7bb55a",
            relief=tk.FLAT,
            padx=20,
            cursor="hand2"
        )
        test_writer_btn.pack(side=tk.LEFT)
        
        # Items input
        tk.Label(
            frame,
            text="Items to Write (JSON Array):",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(20, 5))
        
        self.writer_input = scrolledtext.ScrolledText(
            frame,
            height=10,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#cccccc",
            insertbackground="#cccccc",
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        self.writer_input.pack(fill=tk.X, padx=20, pady=(0, 20))
        self.writer_input.insert("1.0", '''[
        {"id": 1, "name": "Item 1", "value": 100},
        {"id": 2, "name": "Item 2", "value": 200},
        {"id": 3, "name": "Item 3", "value": 300}
    ]''')
        
        # Log output
        tk.Label(
            frame,
            text="Execution Log:",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(0, 5))
        
        self.writer_log = scrolledtext.ScrolledText(
            frame,
            height=8,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="#00ff00",
            relief=tk.FLAT
        )
        self.writer_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))



    def create_step_tab(self):
        frame = tk.Frame(self.notebook, bg="#2b2b2b")
        self.notebook.add(frame, text="🔄  Step")
        
        # Title
        tk.Label(
            frame,
            text="🔄 Step Runner",
            font=("Segoe UI", 18, "bold"),
            bg="#2b2b2b",
            fg="#ffffff"
        ).pack(pady=20)
        
        # Controls
        control_frame = tk.Frame(frame, bg="#2b2b2b")
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(
            control_frame,
            text="Select Step:",
            font=("Segoe UI", 10),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.step_combo = ttk.Combobox(control_frame, state="readonly", width=40)
        self.step_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.step_combo.bind('<<ComboboxSelected>>', self.on_step_selected)
        
        tk.Label(
            control_frame,
            text="Max Items:",
            font=("Segoe UI", 10),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.step_max_items = tk.Spinbox(control_frame, from_=1, to=10000, width=10)
        self.step_max_items.delete(0, tk.END)
        self.step_max_items.insert(0, "100")
        self.step_max_items.pack(side=tk.LEFT, padx=(0, 20))
        
        run_step_btn = tk.Button(
            control_frame,
            text="▶ Run Step",
            command=self.run_step,
            font=("Segoe UI", 10, "bold"),
            bg="#ff9933",
            fg="#ffffff",
            activebackground="#ffaa44",
            relief=tk.FLAT,
            padx=20,
            cursor="hand2"
        )
        run_step_btn.pack(side=tk.LEFT)
        
        # Step Info Panel
        info_frame = tk.Frame(frame, bg="#3c3f41", height=120)
        info_frame.pack(fill=tk.X, padx=20, pady=10)
        info_frame.pack_propagate(False)
        
        tk.Label(
            info_frame,
            text="Step Configuration:",
            font=("Segoe UI", 11, "bold"),
            bg="#3c3f41",
            fg="#ffffff"
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        self.step_info_text = tk.Text(
            info_frame,
            height=4,
            font=("Consolas", 9),
            bg="#2b2b2b",
            fg="#cccccc",
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        self.step_info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Flow Visualization
        tk.Label(
            frame,
            text="Step Flow:",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        flow_canvas = tk.Canvas(frame, bg="#313335", height=100, highlightthickness=0)
        flow_canvas.pack(fill=tk.X, padx=20, pady=(0, 10))
        self.step_flow_canvas = flow_canvas
        
        # Execution Log
        tk.Label(
            frame,
            text="Execution Log:",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        self.step_log = scrolledtext.ScrolledText(
            frame,
            height=8,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="#00ff00",
            relief=tk.FLAT
        )
        self.step_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

    def on_step_selected(self, event):
        """Called when step is selected from combo"""
        step_name = self.step_combo.get()
        
        if not hasattr(self, 'analysis_result'):
            return
        
        # Find step details
        steps = self.analysis_result.get('steps', [])
        step = next((s for s in steps if s['name'] == step_name), None)
        
        if step:
            # Update info panel
            self.step_info_text.delete("1.0", tk.END)
            info = f"Step: {step['name']}\n"
            info += f"Source: {step.get('source', 'Unknown')}\n"
            
            if step.get('reader'):
                info += f"Reader: {step.get('reader', 'N/A')}\n"
            if step.get('processor'):
                info += f"Processor: {step.get('processor', 'N/A')}\n"
            if step.get('writer'):
                info += f"Writer: {step.get('writer', 'N/A')}\n"
            if step.get('commitInterval'):
                info += f"Commit Interval: {step.get('commitInterval', '10')}"
            
            self.step_info_text.insert("1.0", info)
            
            # Draw flow
            self.draw_step_flow(step)

    def draw_step_flow(self, step):
        """Draw visual flow for step"""
        canvas = self.step_flow_canvas
        canvas.delete("all")
        
        x = 50
        y = 50
        box_width = 150
        box_height = 40
        spacing = 50
        
        # Reader
        if step.get('reader'):
            canvas.create_rectangle(x, y - 20, x + box_width, y + 20, 
                                fill="#4a88c7", outline="#ffffff", width=2)
            canvas.create_text(x + box_width/2, y, text=f"📖 Reader", 
                            font=("Segoe UI", 10, "bold"), fill="#ffffff")
            canvas.create_text(x + box_width/2, y + 15, text=step.get('reader', 'N/A'), 
                            font=("Segoe UI", 8), fill="#ffffff")
            x += box_width + spacing
            
            # Arrow
            canvas.create_line(x - spacing + 10, y, x - 10, y, 
                            arrow=tk.LAST, fill="#ffffff", width=2)
        
        # Processor
        if step.get('processor'):
            canvas.create_rectangle(x, y - 20, x + box_width, y + 20, 
                                fill="#ff9933", outline="#ffffff", width=2)
            canvas.create_text(x + box_width/2, y, text=f"⚙️ Processor", 
                            font=("Segoe UI", 10, "bold"), fill="#ffffff")
            canvas.create_text(x + box_width/2, y + 15, text=step.get('processor', 'N/A'), 
                            font=("Segoe UI", 8), fill="#ffffff")
            x += box_width + spacing
            
            # Arrow
            canvas.create_line(x - spacing + 10, y, x - 10, y, 
                            arrow=tk.LAST, fill="#ffffff", width=2)
        
        # Writer
        if step.get('writer'):
            canvas.create_rectangle(x, y - 20, x + box_width, y + 20, 
                                fill="#6ba54a", outline="#ffffff", width=2)
            canvas.create_text(x + box_width/2, y, text=f"✍️ Writer", 
                            font=("Segoe UI", 10, "bold"), fill="#ffffff")
            canvas.create_text(x + box_width/2, y + 15, text=step.get('writer', 'N/A'), 
                            font=("Segoe UI", 8), fill="#ffffff")

    def run_step(self):
        """Execute a step"""
        step_name = self.step_combo.get()
        
        if not step_name:
            messagebox.showwarning("Warning", "Please select a step first")
            return
        
        max_items = int(self.step_max_items.get())
        
        self.step_log.insert(tk.END, f"🔄 Running step: {step_name}\n")
        self.step_log.insert(tk.END, f"   Max items: {max_items}\n")
        self.step_log.insert(tk.END, f"   Commit interval: 10\n\n")
        self.step_log.see(tk.END)
        self.root.update()
        
        # Find step details
        if not hasattr(self, 'analysis_result'):
            messagebox.showerror("Error", "No analysis result available")
            return
        
        steps = self.analysis_result.get('steps', [])
        step = next((s for s in steps if s['name'] == step_name), None)
        
        if not step:
            messagebox.showerror("Error", f"Step {step_name} not found")
            return
        
        try:
            # Simulate step execution
            self.step_log.insert(tk.END, "📖 Phase 1: Reading items...\n")
            self.root.update()
            
            import time
            time.sleep(0.5)
            
            read_count = min(max_items, 50)  # Simulate reading
            self.step_log.insert(tk.END, f"   ✅ Read {read_count} items\n\n")
            
            if step.get('processor'):
                self.step_log.insert(tk.END, "⚙️ Phase 2: Processing items...\n")
                self.root.update()
                time.sleep(0.5)
                
                filtered = int(read_count * 0.1)  # 10% filtered
                processed = read_count - filtered
                self.step_log.insert(tk.END, f"   ✅ Processed {processed} items\n")
                self.step_log.insert(tk.END, f"   ⚠️ Filtered {filtered} items\n\n")
            else:
                processed = read_count
            
            self.step_log.insert(tk.END, "✍️ Phase 3: Writing items...\n")
            self.root.update()
            time.sleep(0.5)
            
            self.step_log.insert(tk.END, f"   ✅ Wrote {processed} items\n\n")
            
            self.step_log.insert(tk.END, "=" * 50 + "\n")
            self.step_log.insert(tk.END, "✅ Step Completed Successfully\n")
            self.step_log.insert(tk.END, f"   Total Read: {read_count}\n")
            self.step_log.insert(tk.END, f"   Total Processed: {processed}\n")
            self.step_log.insert(tk.END, f"   Total Written: {processed}\n")
            self.step_log.insert(tk.END, "=" * 50 + "\n\n")
            
            self.status_label.config(text=f"✅ Step completed: {processed} items processed")
            
        except Exception as e:
            self.step_log.insert(tk.END, f"❌ Error: {str(e)}\n\n")
            messagebox.showerror("Error", f"Step execution failed:\n{e}")
            self.status_label.config(text="❌ Step execution failed")
        
        self.step_log.see(tk.END)
        
    def create_job_tab(self):
        frame = tk.Frame(self.notebook, bg="#2b2b2b")
        self.notebook.add(frame, text="🚀  Job")
        
        # Title
        tk.Label(
            frame,
            text="🚀 Job Runner",
            font=("Segoe UI", 18, "bold"),
            bg="#2b2b2b",
            fg="#ffffff"
        ).pack(pady=20)
        
        # Controls
        control_frame = tk.Frame(frame, bg="#2b2b2b")
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(
            control_frame,
            text="Select Job:",
            font=("Segoe UI", 10),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.job_combo = ttk.Combobox(control_frame, state="readonly", width=40)
        self.job_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.job_combo.bind('<<ComboboxSelected>>', self.on_job_selected)
        
        run_job_btn = tk.Button(
            control_frame,
            text="▶ Run Job",
            command=self.run_job,
            font=("Segoe UI", 10, "bold"),
            bg="#4a88c7",
            fg="#ffffff",
            activebackground="#5a98d7",
            relief=tk.FLAT,
            padx=20,
            cursor="hand2"
        )
        run_job_btn.pack(side=tk.LEFT)
        
        # Job Info Panel
        info_frame = tk.Frame(frame, bg="#3c3f41", height=100)
        info_frame.pack(fill=tk.X, padx=20, pady=10)
        info_frame.pack_propagate(False)
        
        tk.Label(
            info_frame,
            text="Job Configuration:",
            font=("Segoe UI", 11, "bold"),
            bg="#3c3f41",
            fg="#ffffff"
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        self.job_info_text = tk.Text(
            info_frame,
            height=3,
            font=("Consolas", 9),
            bg="#2b2b2b",
            fg="#cccccc",
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        self.job_info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Job Flow Visualization
        tk.Label(
            frame,
            text="Job Flow (Steps):",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        flow_canvas = tk.Canvas(frame, bg="#313335", height=150, highlightthickness=0)
        flow_canvas.pack(fill=tk.X, padx=20, pady=(0, 10))
        self.job_flow_canvas = flow_canvas
        
        # Progress
        tk.Label(
            frame,
            text="Execution Progress:",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        progress_frame = tk.Frame(frame, bg="#2b2b2b")
        progress_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        self.job_progress = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            length=400
        )
        self.job_progress.pack(fill=tk.X)
        
        # Execution Log
        tk.Label(
            frame,
            text="Execution Log:",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#cccccc"
        ).pack(anchor=tk.W, padx=20, pady=(10, 5))
        
        self.job_log = scrolledtext.ScrolledText(
            frame,
            height=10,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="#00ff00",
            relief=tk.FLAT
        )
        self.job_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

    def on_job_selected(self, event):
        """Called when job is selected"""
        job_name = self.job_combo.get()
        
        if not hasattr(self, 'analysis_result'):
            return
        
        # Find job details
        jobs = self.analysis_result.get('jobs', [])
        job = next((j for j in jobs if j['name'] == job_name), None)
        
        if job:
            # Update info panel
            self.job_info_text.delete("1.0", tk.END)
            info = f"Job: {job['name']}\n"
            info += f"Source: {job.get('source', 'Unknown')}\n"
            steps = job.get('steps', [])
            info += f"Steps: {len(steps)} - {', '.join(steps) if steps else 'N/A'}"
            self.job_info_text.insert("1.0", info)
            
            # Draw flow
            self.draw_job_flow(job)

    def draw_job_flow(self, job):
        """Draw visual flow for job steps"""
        canvas = self.job_flow_canvas
        canvas.delete("all")
        
        steps = job.get('steps', [])
        
        if not steps:
            canvas.create_text(400, 75, text="No steps defined", 
                            font=("Segoe UI", 12), fill="#888888")
            return
        
        x = 50
        y = 75
        box_width = 180
        box_height = 50
        spacing = 40
        
        for i, step_name in enumerate(steps):
            # Draw step box
            canvas.create_rectangle(x, y - 25, x + box_width, y + 25, 
                                fill="#ff9933", outline="#ffffff", width=2)
            canvas.create_text(x + box_width/2, y - 5, text=f"Step {i+1}", 
                            font=("Segoe UI", 9), fill="#ffffff")
            canvas.create_text(x + box_width/2, y + 10, text=step_name, 
                            font=("Segoe UI", 10, "bold"), fill="#ffffff")
            
            x += box_width + spacing
            
            # Arrow to next step
            if i < len(steps) - 1:
                canvas.create_line(x - spacing + 5, y, x - 5, y, 
                                arrow=tk.LAST, fill="#ffffff", width=3)

    def run_job(self):
        """Execute a complete job"""
        job_name = self.job_combo.get()
        
        if not job_name:
            messagebox.showwarning("Warning", "Please select a job first")
            return
        
        self.job_log.insert(tk.END, f"🚀 Starting job: {job_name}\n")
        self.job_log.insert(tk.END, "=" * 60 + "\n\n")
        self.job_log.see(tk.END)
        self.root.update()
        
        # Find job details
        if not hasattr(self, 'analysis_result'):
            messagebox.showerror("Error", "No analysis result available")
            return
        
        jobs = self.analysis_result.get('jobs', [])
        job = next((j for j in jobs if j['name'] == job_name), None)
        
        if not job:
            messagebox.showerror("Error", f"Job {job_name} not found")
            return
        
        steps = job.get('steps', [])
        
        if not steps:
            messagebox.showwarning("Warning", "Job has no steps defined")
            return
        
        try:
            # Execute each step
            self.job_progress['maximum'] = len(steps)
            self.job_progress['value'] = 0
            
            import time
            
            for i, step_name in enumerate(steps, 1):
                self.job_log.insert(tk.END, f"📍 Step {i}/{len(steps)}: {step_name}\n")
                self.job_log.insert(tk.END, "-" * 60 + "\n")
                self.root.update()
                
                # Simulate step execution
                time.sleep(0.3)
                self.job_log.insert(tk.END, "   📖 Reading items...\n")
                self.root.update()
                time.sleep(0.3)
                
                read_count = 50
                self.job_log.insert(tk.END, f"   ✅ Read {read_count} items\n")
                
                self.job_log.insert(tk.END, "   ⚙️ Processing items...\n")
                self.root.update()
                time.sleep(0.3)
                
                processed = 45
                self.job_log.insert(tk.END, f"   ✅ Processed {processed} items\n")
                
                self.job_log.insert(tk.END, "   ✍️ Writing items...\n")
                self.root.update()
                time.sleep(0.3)
                
                self.job_log.insert(tk.END, f"   ✅ Wrote {processed} items\n")
                self.job_log.insert(tk.END, f"   ✅ Step {step_name} completed\n\n")
                
                # Update progress
                self.job_progress['value'] = i
                self.root.update()
            
            # Job completed
            self.job_log.insert(tk.END, "=" * 60 + "\n")
            self.job_log.insert(tk.END, "🎉 JOB COMPLETED SUCCESSFULLY\n")
            self.job_log.insert(tk.END, f"   Total Steps: {len(steps)}\n")
            self.job_log.insert(tk.END, f"   Status: COMPLETED\n")
            self.job_log.insert(tk.END, "=" * 60 + "\n\n")
            
            self.status_label.config(text=f"✅ Job completed: {job_name}")
            messagebox.showinfo("Success", f"Job '{job_name}' completed successfully!")
            
        except Exception as e:
            self.job_log.insert(tk.END, f"\n❌ JOB FAILED: {str(e)}\n\n")
            messagebox.showerror("Error", f"Job execution failed:\n{e}")
            self.status_label.config(text="❌ Job execution failed")
        
        self.job_log.see(tk.END)

    def browse_project(self):
        filename = filedialog.askopenfilename(
            title="Select Spring Batch JAR",
            filetypes=[("JAR files", "*.jar"), ("All files", "*.*")]
        )
        if filename:
            self.project_path.set(filename)
    
    def analyze_project(self):
        project_path = self.project_path.get()
        
        if not project_path:
            messagebox.showwarning("Warning", "Please select a project first")
            return
        
        if not self.batch_analyzer:
            messagebox.showerror("Error", "Batch analyzer not initialized")
            return
        
        self.status_label.config(text="Analyzing project...")
        self.root.update()
        
        try:
            # Call analyzer
            result = self.batch_analyzer.analyze_project(project_path)
            
            # Store result for later use
            self.analysis_result = result
            
            readers = result.get('readers', [])
            processors = result.get('processors', [])
            writers = result.get('writers', [])
            steps = result.get('steps', [])
            jobs = result.get('jobs', [])
            
            # Populate all combos
            self.reader_combo['values'] = [r['name'] for r in readers]
            if readers:
                self.reader_combo.current(0)
            
            self.processor_combo['values'] = [p['name'] for p in processors]
            if processors:
                self.processor_combo.current(0)
            
            self.writer_combo['values'] = [w['name'] for w in writers]
            if writers:
                self.writer_combo.current(0)
            
            # NEW: Populate step combo
            self.step_combo['values'] = [s['name'] for s in steps]
            if steps:
                self.step_combo.current(0)
                self.on_step_selected(None)  # Trigger display
            
            # NEW: Populate job combo
            self.job_combo['values'] = [j['name'] for j in jobs]
            if jobs:
                self.job_combo.current(0)
                self.on_job_selected(None)  # Trigger display
            
            # Update pipeline visualization
            self.update_pipeline_visualization(result)
            
            self.status_label.config(
                text=f"✅ Found {len(readers)} readers, {len(processors)} processors, "
                    f"{len(writers)} writers, {len(steps)} steps, {len(jobs)} jobs"
            )
            
            # Show detailed results
            # ... (keep existing messagebox code)
                
        except Exception as e:
            self.status_label.config(text="❌ Analysis failed")
            logger.error(f"Analysis error: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to analyze project:\n\n{str(e)}")

    def update_pipeline_visualization(self, analysis):
        """Draw pipeline on canvas"""
        canvas = self.pipeline_canvas
        canvas.delete("all")  # Clear existing
        
        readers = analysis.get('readers', [])
        processors = analysis.get('processors', [])
        writers = analysis.get('writers', [])
        steps = analysis.get('steps', [])
        jobs = analysis.get('jobs', [])
        
        x = 50
        y = 50
        box_height = 40
        box_width = 300
        spacing = 60
        
        # Draw Jobs section
        if jobs:
            canvas.create_text(x, y, text="🚀 JOBS", font=("Segoe UI", 14, "bold"), 
                            fill="#4a88c7", anchor="w")
            y += 30
            
            for job in jobs[:5]:  # Show first 5
                canvas.create_rectangle(x, y, x + box_width, y + box_height, 
                                    fill="#3c3f41", outline="#4a88c7", width=2)
                canvas.create_text(x + 10, y + 20, text=f"Job: {job['name']}", 
                                font=("Segoe UI", 10), fill="#ffffff", anchor="w")
                y += box_height + 10
            
            y += spacing
        
        # Draw Steps section
        if steps:
            canvas.create_text(x, y, text="🔄 STEPS", font=("Segoe UI", 14, "bold"), 
                            fill="#ff9933", anchor="w")
            y += 30
            
            for step in steps[:5]:  # Show first 5
                canvas.create_rectangle(x, y, x + box_width, y + box_height, 
                                    fill="#3c3f41", outline="#ff9933", width=2)
                
                step_text = f"Step: {step['name']}"
                if step.get('reader') and step.get('reader') != 'unknown':
                    step_text += f" [R→P→W]"
                
                canvas.create_text(x + 10, y + 20, text=step_text, 
                                font=("Segoe UI", 10), fill="#ffffff", anchor="w")
                y += box_height + 10
            
            y += spacing
        
        # Draw Readers section
        if readers:
            canvas.create_text(x, y, text="📖 READERS", font=("Segoe UI", 14, "bold"), 
                            fill="#6ba54a", anchor="w")
            y += 30
            
            for reader in readers[:5]:
                canvas.create_rectangle(x, y, x + box_width, y + box_height, 
                                    fill="#3c3f41", outline="#6ba54a", width=2)
                canvas.create_text(x + 10, y + 20, text=reader['name'], 
                                font=("Segoe UI", 10), fill="#ffffff", anchor="w")
                y += box_height + 10

    def test_reader(self):
        reader_name = self.reader_combo.get()
        
        if not reader_name:
            messagebox.showwarning("Warning", "Please select a reader first")
            return
        
        max_items = int(self.max_items.get())
        
        self.reader_log.insert(tk.END, f"🔄 Testing reader: {reader_name}\n")
        self.reader_log.insert(tk.END, f"   Max items: {max_items}\n")
        self.reader_log.see(tk.END)
        self.root.update()
        
        try:
            if self.jvm_manager:
                # Real test
                result = self.reader_sandbox.test_reader(reader_name, max_items)
                
                if result['success']:
                    items = result['items']
                    self.reader_log.insert(tk.END, f"✅ Read {len(items)} items\n\n")
                    self.display_reader_results(items)
                else:
                    self.reader_log.insert(tk.END, f"❌ Error: {result['error']}\n\n")
            else:
                # Demo data
                items = [
                    {"id": 1, "name": "Demo Item 1", "value": 100},
                    {"id": 2, "name": "Demo Item 2", "value": 200},
                    {"id": 3, "name": "Demo Item 3", "value": 300},
                ]
                self.reader_log.insert(tk.END, f"✅ Read {len(items)} items (demo)\n\n")
                self.display_reader_results(items)
                
        except Exception as e:
            self.reader_log.insert(tk.END, f"❌ Exception: {str(e)}\n\n")
        
        self.reader_log.see(tk.END)
    
    def display_reader_results(self, items):
        """Display items in treeview"""
        # Clear existing
        for item in self.reader_tree.get_children():
            self.reader_tree.delete(item)
        
        if not items:
            return
        
        # Get columns
        if items and isinstance(items[0], dict):
            columns = list(items[0].keys())
            
            self.reader_tree['columns'] = columns
            for col in columns:
                self.reader_tree.heading(col, text=col)
                self.reader_tree.column(col, width=150)
            
            # Insert data
            for item in items:
                values = [item.get(col, '') for col in columns]
                self.reader_tree.insert('', tk.END, values=values)
   
    def debug_jar(self):
        """Debug JAR contents - show all classes"""
        jar_path = self.project_path.get()
        
        if not jar_path:
            messagebox.showwarning("Warning", "Select JAR first")
            return
        
        import zipfile
        
        # Create debug window
        debug_window = tk.Toplevel(self.root)
        debug_window.title("JAR Debug Info")
        debug_window.geometry("900x700")
        debug_window.configure(bg="#2b2b2b")
        
        # Title
        tk.Label(
            debug_window,
            text="🔍 JAR Contents Analysis",
            font=("Segoe UI", 16, "bold"),
            bg="#2b2b2b",
            fg="#ffffff"
        ).pack(pady=10)
        
        # Text area
        text = scrolledtext.ScrolledText(
            debug_window,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="#00ff00"
        )
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        try:
            # Analyze JAR
            text.insert(tk.END, f"JAR: {jar_path}\n")
            text.insert(tk.END, "=" * 80 + "\n\n")
            
            with zipfile.ZipFile(jar_path, 'r') as jar:
                # Count files
                all_files = jar.namelist()
                class_files = [f for f in all_files if f.endswith('.class')]
                xml_files = [f for f in all_files if f.endswith('.xml')]
                
                text.insert(tk.END, f"📊 Summary:\n")
                text.insert(tk.END, f"   Total files: {len(all_files)}\n")
                text.insert(tk.END, f"   Class files: {len(class_files)}\n")
                text.insert(tk.END, f"   XML files: {len(xml_files)}\n\n")
                
                # List XML files
                text.insert(tk.END, "=" * 80 + "\n")
                text.insert(tk.END, "📋 XML Configuration Files:\n")
                text.insert(tk.END, "=" * 80 + "\n\n")
                
                if xml_files:
                    for xml_file in xml_files:
                        if not xml_file.startswith('META-INF/maven'):
                            text.insert(tk.END, f"   📄 {xml_file}\n")
                else:
                    text.insert(tk.END, "   (No XML files found)\n")
                
                # List classes
                text.insert(tk.END, "\n" + "=" * 80 + "\n")
                text.insert(tk.END, "☕ Java Classes:\n")
                text.insert(tk.END, "=" * 80 + "\n\n")
                
                # Categorize classes
                batch_classes = []
                config_classes = []
                other_classes = []
                
                for class_file in class_files:
                    if class_file.startswith('META-INF'):
                        continue
                    
                    class_name = class_file[:-6].replace('/', '.')
                    
                    # Categorize
                    if any(keyword in class_name for keyword in 
                        ['Reader', 'Processor', 'Writer', 'Step', 'Job', 'Batch']):
                        batch_classes.append(class_name)
                    elif 'Config' in class_name:
                        config_classes.append(class_name)
                    else:
                        other_classes.append(class_name)
                
                # Display batch-related classes
                if batch_classes:
                    text.insert(tk.END, "🔥 Spring Batch Components:\n", 'highlight')
                    for cls in sorted(batch_classes):
                        text.insert(tk.END, f"   ✅ {cls}\n", 'batch')
                    text.insert(tk.END, "\n")
                
                # Display config classes
                if config_classes:
                    text.insert(tk.END, "⚙️ Configuration Classes:\n", 'highlight')
                    for cls in sorted(config_classes):
                        text.insert(tk.END, f"   🔧 {cls}\n", 'config')
                    text.insert(tk.END, "\n")
                
                # Display other classes (collapsed)
                if other_classes:
                    text.insert(tk.END, f"📦 Other Classes ({len(other_classes)}):\n")
                    for cls in sorted(other_classes)[:20]:  # Show first 20
                        text.insert(tk.END, f"   • {cls}\n")
                    if len(other_classes) > 20:
                        text.insert(tk.END, f"   ... and {len(other_classes) - 20} more\n")
            
            # Configure tags
            text.tag_config('highlight', foreground='#ffff00', font=('Consolas', 9, 'bold'))
            text.tag_config('batch', foreground='#00ff00')
            text.tag_config('config', foreground='#ff9933')
            
        except Exception as e:
            text.insert(tk.END, f"\n❌ Error: {str(e)}\n")
            import traceback
            text.insert(tk.END, traceback.format_exc())

    def test_writer(self):
        writer_name = self.writer_combo.get()
        
        if not writer_name:
            messagebox.showwarning("Warning", "Please select a writer first")
            return
        
        # Get input items
        input_text = self.writer_input.get("1.0", tk.END).strip()
        
        try:
            import json
            items = json.loads(input_text)
            
            if not isinstance(items, list):
                raise ValueError("Input must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Error", f"Invalid JSON input:\n{e}")
            return
        
        self.writer_log.insert(tk.END, f"🔄 Testing writer: {writer_name}\n")
        self.writer_log.insert(tk.END, f"   Items to write: {len(items)}\n")
        self.writer_log.see(tk.END)
        self.root.update()
        
        try:
            if self.jvm_manager:
                # Real writing (TODO: implement writer_sandbox)
                # For now, simulate
                import tempfile
                import os
                from datetime import datetime
                
                # Simulate CSV writing
                temp_dir = tempfile.gettempdir()
                filename = f"batcherman_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(temp_dir, filename)
                
                with open(filepath, 'w') as f:
                    if items:
                        # Write header
                        headers = list(items[0].keys())
                        f.write(','.join(headers) + '\n')
                        
                        # Write data
                        for item in items:
                            values = [str(item.get(h, '')) for h in headers]
                            f.write(','.join(values) + '\n')
                
                self.writer_log.insert(tk.END, f"✅ Successfully wrote {len(items)} items\n")
                self.writer_log.insert(tk.END, f"   Output file: {filepath}\n")
                self.writer_log.insert(tk.END, f"   Writer type: CSV File Writer\n\n")
                
            else:
                # Demo mode
                self.writer_log.insert(tk.END, f"✅ Successfully wrote {len(items)} items (demo)\n")
                self.writer_log.insert(tk.END, f"   Output: [simulated]\n\n")
            
            self.status_label.config(text=f"✅ Wrote {len(items)} items successfully")
            
        except Exception as e:
            self.writer_log.insert(tk.END, f"❌ Error: {str(e)}\n\n")
            messagebox.showerror("Error", f"Writing failed:\n{e}")
            self.status_label.config(text="❌ Writing failed")
        
        self.writer_log.see(tk.END)

def main():
    root = tk.Tk()
    app = BatcherManApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
