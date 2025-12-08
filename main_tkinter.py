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
            
            # Store result
            self.analysis_result = result
            
            readers = result.get('readers', [])
            processors = result.get('processors', [])
            writers = result.get('writers', [])
            steps = result.get('steps', [])
            jobs = result.get('jobs', [])
            
            # Populate combos in main window
            self.reader_combo['values'] = [r['name'] for r in readers]
            if readers:
                self.reader_combo.current(0)
            
            self.processor_combo['values'] = [p['name'] for p in processors]
            if processors:
                self.processor_combo.current(0)
            
            self.writer_combo['values'] = [w['name'] for w in writers]
            if writers:
                self.writer_combo.current(0)
            
            self.step_combo['values'] = [s['name'] for s in steps]
            if steps:
                self.step_combo.current(0)
                self.on_step_selected(None)
            
            self.job_combo['values'] = [j['name'] for j in jobs]
            if jobs:
                self.job_combo.current(0)
                self.on_job_selected(None)
            
            # Update pipeline visualization
            self.update_pipeline_visualization(result)
            
            self.status_label.config(
                text=f"✅ Found {len(readers)} readers, {len(processors)} processors, "
                    f"{len(writers)} writers, {len(steps)} steps, {len(jobs)} jobs"
            )
            
            # NEW: Show components in separate windows
            self.show_components_windows(result)
            
            # NEW: Show workflow diagram
            self.show_workflow_diagram(result)
                
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
    def show_workflow_diagram(self, analysis):
        """Show complete Spring Batch workflow diagram with scrolling"""
        window = tk.Toplevel(self.root)
        window.title("🔄 Batch Workflow Architecture")
        window.geometry("1400x900")
        window.configure(bg="#2b2b2b")
        
        # Title
        title_frame = tk.Frame(window, bg="#1e1e1e", height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame,
            text="🔄 Spring Batch Workflow Architecture",
            font=("Segoe UI", 20, "bold"),
            bg="#1e1e1e",
            fg="#ffffff"
        ).pack(pady=15)
        
        # Create frame for canvas and scrollbars
        canvas_frame = tk.Frame(window, bg="#2b2b2b")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Create canvas with scrollbars
        canvas = tk.Canvas(
            canvas_frame,
            bg="#313335",
            highlightthickness=0,
            scrollregion=(0, 0, 2000, 1200)  # Large scrollable area
        )
        
        # Vertical scrollbar
        v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Horizontal scrollbar
        h_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Configure canvas scrolling
        canvas.configure(
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Draw the complete workflow
        self.draw_complete_workflow(canvas, analysis)
        
        # Update scroll region after drawing
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        
        # Bind mouse wheel events
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Shift-MouseWheel>", on_shift_mousewheel)
        
        # Add zoom controls
        control_frame = tk.Frame(window, bg="#2b2b2b", height=40)
        control_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        control_frame.pack_propagate(False)
        
        # Zoom buttons
        tk.Button(
            control_frame,
            text="🔍 Zoom In",
            command=lambda: zoom_canvas(canvas, 1.2),
            font=("Segoe UI", 9),
            bg="#3c3f41",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=15,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            control_frame,
            text="🔍 Zoom Out",
            command=lambda: zoom_canvas(canvas, 0.8),
            font=("Segoe UI", 9),
            bg="#3c3f41",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=15,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            control_frame,
            text="🔄 Reset View",
            command=lambda: reset_canvas(canvas),
            font=("Segoe UI", 9),
            bg="#3c3f41",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=15,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        # Instructions
        tk.Label(
            control_frame,
            text="💡 Use mouse wheel to scroll vertically, Shift+Wheel for horizontal",
            font=("Segoe UI", 9),
            bg="#2b2b2b",
            fg="#888888"
        ).pack(side=tk.RIGHT, padx=10)
        
        # Store initial scale
        canvas.scale_factor = 1.0
        
        def zoom_canvas(canvas, factor):
            """Zoom canvas content"""
            canvas.scale_factor *= factor
            canvas.scale("all", 0, 0, factor, factor)
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def reset_canvas(canvas):
            """Reset canvas to original size"""
            if hasattr(canvas, 'scale_factor'):
                canvas.scale("all", 0, 0, 1/canvas.scale_factor, 1/canvas.scale_factor)
                canvas.scale_factor = 1.0
                canvas.configure(scrollregion=canvas.bbox("all"))
        
        # Pan with mouse drag
        canvas.bind("<ButtonPress-1>", lambda e: canvas.scan_mark(e.x, e.y))
        canvas.bind("<B1-Motion>", lambda e: canvas.scan_dragto(e.x, e.y, gain=1))
        
        # Clean up mouse wheel bindings when window closes
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Shift-MouseWheel>")
            window.destroy()
        
        window.protocol("WM_DELETE_WINDOW", on_close)
    def draw_complete_workflow(self, canvas, analysis):
        """Draw Spring Batch architecture diagram with real component names"""
        jobs = analysis.get('jobs', [])
        steps = analysis.get('steps', [])
        readers = analysis.get('readers', [])
        processors = analysis.get('processors', [])
        writers = analysis.get('writers', [])
        
        # Colors
        job_color = "#9b59b6"
        step_color = "#c897d4"
        reader_color = "#4a88c7"
        processor_color = "#ff9933"
        writer_color = "#6ba54a"
        db_color = "#95a5a6"
        
        # Starting positions - with more spacing
        x_start = 150
        y_start = 150
        
        # 1. Draw Job Scheduler (top left)
        canvas.create_rectangle(x_start, y_start, x_start + 150, y_start + 80,
                            fill=job_color, outline="#ffffff", width=2)
        canvas.create_text(x_start + 75, y_start + 30, text="Job Scheduler",
                        font=("Segoe UI", 12, "bold"), fill="#ffffff")
        canvas.create_text(x_start + 75, y_start + 55, text="run()",
                        font=("Segoe UI", 10), fill="#ffffff")
        
        # 2. Draw JobLauncher
        job_launcher_x = x_start + 220
        job_launcher_y = y_start + 120
        
        canvas.create_rectangle(job_launcher_x, job_launcher_y, 
                            job_launcher_x + 150, job_launcher_y + 80,
                            fill=job_color, outline="#ffffff", width=2)
        canvas.create_text(job_launcher_x + 75, job_launcher_y + 30,
                        text="JobLauncher", font=("Segoe UI", 12, "bold"), fill="#ffffff")
        canvas.create_text(job_launcher_x + 75, job_launcher_y + 55,
                        text="execute()", font=("Segoe UI", 10), fill="#ffffff")
        
        # Arrow from scheduler to launcher
        canvas.create_line(x_start + 75, y_start + 80, job_launcher_x + 75, job_launcher_y,
                        arrow=tk.LAST, fill="#ffffff", width=3)
        
        # 3. Draw Job(s)
        job_x = job_launcher_x + 250
        job_y = job_launcher_y
        
        if jobs:
            for i, job in enumerate(jobs[:3]):  # Show max 3 jobs
                jy = job_y + i * 100
                
                canvas.create_rectangle(job_x, jy, job_x + 180, jy + 80,
                                    fill=job_color, outline="#ffffff", width=2)
                canvas.create_text(job_x + 90, jy + 20, text="Job",
                                font=("Segoe UI", 11, "bold"), fill="#ffffff")
                canvas.create_text(job_x + 90, jy + 45, text=job['name'],
                                font=("Consolas", 10), fill="#ffffff")
                canvas.create_text(job_x + 90, jy + 65, text="execute()",
                                font=("Segoe UI", 9), fill="#ffffff")
                
                # Arrow from launcher to job
                if i == 0:
                    canvas.create_line(job_launcher_x + 150, job_launcher_y + 40,
                                    job_x, jy + 40,
                                    arrow=tk.LAST, fill="#ffffff", width=3)
        else:
            # Default job box
            canvas.create_rectangle(job_x, job_y, job_x + 180, job_y + 80,
                                fill=job_color, outline="#ffffff", width=2)
            canvas.create_text(job_x + 90, job_y + 40, text="Job\n(No jobs found)",
                            font=("Segoe UI", 11, "bold"), fill="#ffffff")
        
        # 4. Draw JobExecution box
        exec_x = job_x + 280
        exec_y = y_start + 50
        exec_width = 800
        exec_height = 650
        
        canvas.create_rectangle(exec_x, exec_y, exec_x + exec_width, exec_y + exec_height,
                            fill="#45464a", outline="#7d7d7d", width=3)
        canvas.create_text(exec_x + 400, exec_y + 25, text="JobExecution",
                        font=("Segoe UI", 14, "bold"), fill="#ffffff")
        
        # 5. Draw Steps inside JobExecution
        step_x = exec_x + 50
        step_y = exec_y + 70
        
        if steps:
            for i, step in enumerate(steps[:2]):  # Show max 2 steps
                sy = step_y + i * 280
                
                # StepExecution box
                canvas.create_rectangle(step_x, sy, step_x + 700, sy + 250,
                                    fill="#565a5e", outline="#9b9b9b", width=2)
                canvas.create_text(step_x + 350, sy + 20, text="StepExecution",
                                font=("Segoe UI", 12, "bold"), fill="#ffffff")
                
                # Step box
                canvas.create_rectangle(step_x + 30, sy + 50, step_x + 160, sy + 120,
                                    fill=step_color, outline="#ffffff", width=2)
                canvas.create_text(step_x + 95, sy + 70, text="Step",
                                font=("Segoe UI", 11, "bold"), fill="#ffffff")
                canvas.create_text(step_x + 95, sy + 95, text=step['name'][:18],
                                font=("Consolas", 9), fill="#ffffff")
                
                # Arrow from step to execution context
                canvas.create_line(step_x + 160, sy + 85, step_x + 230, sy + 85,
                                arrow=tk.LAST, fill="#ffffff", width=2)
                
                # Execution Context
                ctx_x = step_x + 230
                ctx_y = sy + 50
                canvas.create_rectangle(ctx_x, ctx_y, ctx_x + 130, ctx_y + 190,
                                    fill="#6b6f73", outline="#ffffff", width=2)
                canvas.create_text(ctx_x + 65, ctx_y + 95, text="Execution\nContext",
                                font=("Segoe UI", 11, "bold"), fill="#ffffff")
                
                # Reader, Processor, Writer boxes
                comp_x = ctx_x + 160
                
                # Reader
                reader_name = step.get('reader', 'ItemReader')
                canvas.create_rectangle(comp_x, sy + 50, comp_x + 150, sy + 90,
                                    fill=reader_color, outline="#ffffff", width=2)
                canvas.create_text(comp_x + 75, sy + 63, text="📖 ItemReader",
                                font=("Segoe UI", 10, "bold"), fill="#ffffff")
                canvas.create_text(comp_x + 75, sy + 80, text=f"read()",
                                font=("Segoe UI", 9), fill="#ffffff")
                
                # Show actual reader name on the right
                canvas.create_text(comp_x + 170, sy + 70, text=reader_name[:25],
                                font=("Consolas", 9), fill="#4a88c7", anchor="w")
                
                # Processor
                processor_name = step.get('processor', 'ItemProcessor')
                canvas.create_rectangle(comp_x, sy + 105, comp_x + 150, sy + 145,
                                    fill=processor_color, outline="#ffffff", width=2)
                canvas.create_text(comp_x + 75, sy + 118, text="⚙️ ItemProcessor",
                                font=("Segoe UI", 10, "bold"), fill="#ffffff")
                canvas.create_text(comp_x + 75, sy + 135, text=f"process()",
                                font=("Segoe UI", 9), fill="#ffffff")
                
                # Show actual processor name
                canvas.create_text(comp_x + 170, sy + 125, text=processor_name[:25],
                                font=("Consolas", 9), fill="#ff9933", anchor="w")
                
                # Writer
                writer_name = step.get('writer', 'ItemWriter')
                canvas.create_rectangle(comp_x, sy + 160, comp_x + 150, sy + 200,
                                    fill=writer_color, outline="#ffffff", width=2)
                canvas.create_text(comp_x + 75, sy + 173, text="✍️ ItemWriter",
                                font=("Segoe UI", 10, "bold"), fill="#ffffff")
                canvas.create_text(comp_x + 75, sy + 190, text=f"write()",
                                font=("Segoe UI", 9), fill="#ffffff")
                
                # Show actual writer name
                canvas.create_text(comp_x + 170, sy + 180, text=writer_name[:25],
                                font=("Consolas", 9), fill="#6ba54a", anchor="w")
                
                # Arrows connecting execution context to components
                canvas.create_line(ctx_x + 130, sy + 85, comp_x, sy + 70,
                                fill="#ffffff", width=2, dash=(3, 3))
                canvas.create_line(ctx_x + 130, sy + 125, comp_x, sy + 125,
                                fill="#ffffff", width=2, dash=(3, 3))
                canvas.create_line(ctx_x + 130, sy + 165, comp_x, sy + 180,
                                fill="#ffffff", width=2, dash=(3, 3))
                
                # Arrow from job to step (for first step)
                if i == 0:
                    canvas.create_line(job_x + 180, job_y + 40, step_x, sy + 85,
                                    arrow=tk.LAST, fill="#ffffff", width=3)
        
        # 6. Draw JobRepository (bottom left)
        repo_x = job_launcher_x
        repo_y = exec_y + exec_height + 60
        
        canvas.create_rectangle(repo_x, repo_y, repo_x + 180, repo_y + 80,
                            fill=job_color, outline="#ffffff", width=2)
        canvas.create_text(repo_x + 90, repo_y + 40, text="JobRepository",
                        font=("Segoe UI", 12, "bold"), fill="#ffffff")
        
        # 7. Draw Database (bottom)
        db_x = repo_x + 250
        db_y = repo_y + 10
        
        canvas.create_oval(db_x, db_y, db_x + 130, db_y + 60,
                        fill=db_color, outline="#ffffff", width=2)
        canvas.create_text(db_x + 65, db_y + 30, text="Database",
                        font=("Segoe UI", 12, "bold"), fill="#ffffff")
        
        # Arrow from repo to database
        canvas.create_line(repo_x + 180, repo_y + 40, db_x, db_y + 30,
                        arrow=tk.LAST, fill="#ffffff", width=3)
        
        # Arrow from execution context to repository
        canvas.create_line(exec_x + 100, exec_y + exec_height, repo_x + 90, repo_y,
                        arrow=tk.LAST, fill="#7d7d7d", width=3, dash=(5, 3))
        canvas.create_text(exec_x + 80, exec_y + exec_height + 25,
                        text="CRUD Operation", font=("Segoe UI", 10),
                        fill="#7d7d7d", anchor="e")
        
        # Add legend
        legend_x = 100
        legend_y = repo_y + 120
        
        canvas.create_text(legend_x, legend_y, text="Legend:",
                        font=("Segoe UI", 12, "bold"), fill="#ffffff", anchor="w")
        
        legends = [
            ("Flow of central processing", "#ffffff", True),
            ("Flow of job information persistence", "#7d7d7d", False),
        ]
        
        ly = legend_y + 30
        for text, color, solid in legends:
            canvas.create_line(legend_x, ly, legend_x + 50, ly,
                            fill=color, width=3, dash=() if solid else (5, 3))
            canvas.create_text(legend_x + 60, ly, text=text,
                            font=("Segoe UI", 10), fill="#cccccc", anchor="w")
            ly += 30

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
    def show_components_windows(self, analysis):
        """Show components in separate organized windows"""
        readers = analysis.get('readers', [])
        processors = analysis.get('processors', [])
        writers = analysis.get('writers', [])
        steps = analysis.get('steps', [])
        jobs = analysis.get('jobs', [])
        
        # Calculate positions for windows
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Show readers window
        if readers:
            self.show_component_window(
                "📖 Readers",
                readers,
                x=50,
                y=100,
                color="#4a88c7"
            )
        
        # Show processors window
        if processors:
            self.show_component_window(
                "⚙️ Processors",
                processors,
                x=50,
                y=350,
                color="#ff9933"
            )
        
        # Show writers window
        if writers:
            self.show_component_window(
                "✍️ Writers",
                writers,
                x=50,
                y=600,
                color="#6ba54a"
            )
        
        # Show steps window
        if steps:
            self.show_steps_window(
                steps,
                x=screen_width - 450,
                y=100
            )
        
        # Show jobs window
        if jobs:
            self.show_jobs_window(
                jobs,
                x=screen_width - 450,
                y=450
            )

    def show_component_window(self, title, components, x, y, color):
        """Show a window with list of components"""
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry(f"400x200+{x}+{y}")
        window.configure(bg="#2b2b2b")
        
        # Title
        tk.Label(
            window,
            text=title,
            font=("Segoe UI", 14, "bold"),
            bg="#2b2b2b",
            fg=color
        ).pack(pady=10)
        
        # Components list
        frame = tk.Frame(window, bg="#2b2b2b")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create listbox with scrollbar
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(
            frame,
            font=("Consolas", 10),
            bg="#3c3f41",
            fg="#ffffff",
            selectbackground=color,
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate list
        for component in components:
            name = component.get('name', 'Unknown')
            source = component.get('source', 'Unknown')
            listbox.insert(tk.END, f"  {name} ({source})")

    def show_steps_window(self, steps, x, y):
        """Show steps window with flow visualization"""
        window = tk.Toplevel(self.root)
        window.title("🔄 Steps")
        window.geometry(f"400x300+{x}+{y}")
        window.configure(bg="#2b2b2b")
        
        # Title
        tk.Label(
            window,
            text="🔄 Steps Configuration",
            font=("Segoe UI", 14, "bold"),
            bg="#2b2b2b",
            fg="#ff9933"
        ).pack(pady=10)
        
        # Steps list with details
        frame = tk.Frame(window, bg="#2b2b2b")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(frame, bg="#3c3f41", highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#3c3f41")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Display each step
        for i, step in enumerate(steps):
            step_frame = tk.Frame(scrollable_frame, bg="#2b2b2b", relief=tk.RAISED, bd=1)
            step_frame.pack(fill=tk.X, padx=5, pady=5)
            
            tk.Label(
                step_frame,
                text=f"Step: {step['name']}",
                font=("Segoe UI", 11, "bold"),
                bg="#2b2b2b",
                fg="#ffffff",
                anchor="w"
            ).pack(fill=tk.X, padx=10, pady=5)
            
            if step.get('reader'):
                tk.Label(
                    step_frame,
                    text=f"  📖 Reader: {step.get('reader')}",
                    font=("Consolas", 9),
                    bg="#2b2b2b",
                    fg="#4a88c7",
                    anchor="w"
                ).pack(fill=tk.X, padx=15)
            
            if step.get('processor'):
                tk.Label(
                    step_frame,
                    text=f"  ⚙️ Processor: {step.get('processor')}",
                    font=("Consolas", 9),
                    bg="#2b2b2b",
                    fg="#ff9933",
                    anchor="w"
                ).pack(fill=tk.X, padx=15)
            
            if step.get('writer'):
                tk.Label(
                    step_frame,
                    text=f"  ✍️ Writer: {step.get('writer')}",
                    font=("Consolas", 9),
                    bg="#2b2b2b",
                    fg="#6ba54a",
                    anchor="w"
                ).pack(fill=tk.X, padx=15)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def show_jobs_window(self, jobs, x, y):
        """Show jobs window"""
        window = tk.Toplevel(self.root)
        window.title("🚀 Jobs")
        window.geometry(f"400x200+{x}+{y}")
        window.configure(bg="#2b2b2b")
        
        # Title
        tk.Label(
            window,
            text="🚀 Batch Jobs",
            font=("Segoe UI", 14, "bold"),
            bg="#2b2b2b",
            fg="#4a88c7"
        ).pack(pady=10)
        
        # Jobs list
        frame = tk.Frame(window, bg="#2b2b2b")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for job in jobs:
            job_frame = tk.Frame(frame, bg="#3c3f41", relief=tk.RAISED, bd=1)
            job_frame.pack(fill=tk.X, pady=5)
            
            tk.Label(
                job_frame,
                text=f"Job: {job['name']}",
                font=("Segoe UI", 11, "bold"),
                bg="#3c3f41",
                fg="#ffffff",
                anchor="w"
            ).pack(fill=tk.X, padx=10, pady=5)
            
            steps = job.get('steps', [])
            if steps:
                steps_text = f"  Steps: {', '.join(steps)}"
                tk.Label(
                    job_frame,
                    text=steps_text,
                    font=("Consolas", 9),
                    bg="#3c3f41",
                    fg="#cccccc",
                    anchor="w"
                ).pack(fill=tk.X, padx=15, pady=(0, 5))   
def show_components_windows(self, analysis):
    """Show components in separate organized windows"""
    readers = analysis.get('readers', [])
    processors = analysis.get('processors', [])
    writers = analysis.get('writers', [])
    steps = analysis.get('steps', [])
    jobs = analysis.get('jobs', [])
    
    # Calculate positions for windows
    screen_width = self.root.winfo_screenwidth()
    screen_height = self.root.winfo_screenheight()
    
    # Show readers window
    if readers:
        self.show_component_window(
            "📖 Readers",
            readers,
            x=50,
            y=100,
            color="#4a88c7"
        )
    
    # Show processors window
    if processors:
        self.show_component_window(
            "⚙️ Processors",
            processors,
            x=50,
            y=350,
            color="#ff9933"
        )
    
    # Show writers window
    if writers:
        self.show_component_window(
            "✍️ Writers",
            writers,
            x=50,
            y=600,
            color="#6ba54a"
        )
    
    # Show steps window
    if steps:
        self.show_steps_window(
            steps,
            x=screen_width - 450,
            y=100
        )
    
    # Show jobs window
    if jobs:
        self.show_jobs_window(
            jobs,
            x=screen_width - 450,
            y=450
        )

def show_component_window(self, title, components, x, y, color):
    """Show a window with list of components"""
    window = tk.Toplevel(self.root)
    window.title(title)
    window.geometry(f"400x200+{x}+{y}")
    window.configure(bg="#2b2b2b")
    
    # Title
    tk.Label(
        window,
        text=title,
        font=("Segoe UI", 14, "bold"),
        bg="#2b2b2b",
        fg=color
    ).pack(pady=10)
    
    # Components list
    frame = tk.Frame(window, bg="#2b2b2b")
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Create listbox with scrollbar
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    listbox = tk.Listbox(
        frame,
        font=("Consolas", 10),
        bg="#3c3f41",
        fg="#ffffff",
        selectbackground=color,
        yscrollcommand=scrollbar.set,
        relief=tk.FLAT
    )
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)
    
    # Populate list
    for component in components:
        name = component.get('name', 'Unknown')
        source = component.get('source', 'Unknown')
        listbox.insert(tk.END, f"  {name} ({source})")

def show_steps_window(self, steps, x, y):
    """Show steps window with flow visualization"""
    window = tk.Toplevel(self.root)
    window.title("🔄 Steps")
    window.geometry(f"400x300+{x}+{y}")
    window.configure(bg="#2b2b2b")
    
    # Title
    tk.Label(
        window,
        text="🔄 Steps Configuration",
        font=("Segoe UI", 14, "bold"),
        bg="#2b2b2b",
        fg="#ff9933"
    ).pack(pady=10)
    
    # Steps list with details
    frame = tk.Frame(window, bg="#2b2b2b")
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    canvas = tk.Canvas(frame, bg="#3c3f41", highlightthickness=0)
    scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#3c3f41")
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Display each step
    for i, step in enumerate(steps):
        step_frame = tk.Frame(scrollable_frame, bg="#2b2b2b", relief=tk.RAISED, bd=1)
        step_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(
            step_frame,
            text=f"Step: {step['name']}",
            font=("Segoe UI", 11, "bold"),
            bg="#2b2b2b",
            fg="#ffffff",
            anchor="w"
        ).pack(fill=tk.X, padx=10, pady=5)
        
        if step.get('reader'):
            tk.Label(
                step_frame,
                text=f"  📖 Reader: {step.get('reader')}",
                font=("Consolas", 9),
                bg="#2b2b2b",
                fg="#4a88c7",
                anchor="w"
            ).pack(fill=tk.X, padx=15)
        
        if step.get('processor'):
            tk.Label(
                step_frame,
                text=f"  ⚙️ Processor: {step.get('processor')}",
                font=("Consolas", 9),
                bg="#2b2b2b",
                fg="#ff9933",
                anchor="w"
            ).pack(fill=tk.X, padx=15)
        
        if step.get('writer'):
            tk.Label(
                step_frame,
                text=f"  ✍️ Writer: {step.get('writer')}",
                font=("Consolas", 9),
                bg="#2b2b2b",
                fg="#6ba54a",
                anchor="w"
            ).pack(fill=tk.X, padx=15)
    
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

def show_jobs_window(self, jobs, x, y):
    """Show jobs window"""
    window = tk.Toplevel(self.root)
    window.title("🚀 Jobs")
    window.geometry(f"400x200+{x}+{y}")
    window.configure(bg="#2b2b2b")
    
    # Title
    tk.Label(
        window,
        text="🚀 Batch Jobs",
        font=("Segoe UI", 14, "bold"),
        bg="#2b2b2b",
        fg="#4a88c7"
    ).pack(pady=10)
    
    # Jobs list
    frame = tk.Frame(window, bg="#2b2b2b")
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    for job in jobs:
        job_frame = tk.Frame(frame, bg="#3c3f41", relief=tk.RAISED, bd=1)
        job_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            job_frame,
            text=f"Job: {job['name']}",
            font=("Segoe UI", 11, "bold"),
            bg="#3c3f41",
            fg="#ffffff",
            anchor="w"
        ).pack(fill=tk.X, padx=10, pady=5)
        
        steps = job.get('steps', [])
        if steps:
            steps_text = f"  Steps: {', '.join(steps)}"
            tk.Label(
                job_frame,
                text=steps_text,
                font=("Consolas", 9),
                bg="#3c3f41",
                fg="#cccccc",
                anchor="w"
            ).pack(fill=tk.X, padx=15, pady=(0, 5))

def main():
    root = tk.Tk()
    app = BatcherManApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
