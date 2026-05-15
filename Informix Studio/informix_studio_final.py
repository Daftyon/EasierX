"""
Informix Database Studio - Multi-Connection + Database Comparator
Features:
- Multiple simultaneous database connections
- Database structure comparator (tables, columns, constraints, indexes)
- Side-by-side comparison with diff highlighting
- FK Relationship Visualizer (Graphical workflow view)
- Transaction Monitor (Show uncommitted/suspended transactions)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
from datetime import datetime
import threading
import glob
import webbrowser
import re

try:
    import jaydebeapi
    JAYDEBEAPI_AVAILABLE = True
except ImportError:
    JAYDEBEAPI_AVAILABLE = False

try:
    import jpype
    JPYPE_AVAILABLE = True
except ImportError:
    JPYPE_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def find_jvm_dll_anywhere():
    """Search for jvm.dll in all common locations"""
    print("Searching for jvm.dll...")
    
    search_paths = [
        r"C:\Programmes\Java",
        r"C:\Program Files\Java",
        r"C:\Program Files (x86)\Java",
        r"C:\Programmes (x86)\Java",
        r"C:\Program Files\Eclipse Adoptium",
        r"C:\Program Files\Microsoft\jdk",
        r"C:\Program Files\Zulu",
    ]
    
    for base_path in search_paths:
        if not os.path.exists(base_path):
            continue
        
        print(f"  Checking: {base_path}")
        
        pattern = os.path.join(base_path, "*", "bin", "server", "jvm.dll")
        matches = glob.glob(pattern)
        if matches:
            print(f"  ✓ Found: {matches[0]}")
            return matches[0]
        
        pattern = os.path.join(base_path, "*", "bin", "client", "jvm.dll")
        matches = glob.glob(pattern)
        if matches:
            print(f"  ✓ Found: {matches[0]}")
            return matches[0]
    
    print("  ✗ jvm.dll not found in any common location")
    return None


class InformixStudioJDBC:
    def __init__(self, root):
        self.root = root
        self.root.title("Informix Database Studio - Multi-Connection + Transaction Monitor")
        self.root.geometry("1400x900")
        
        # Multiple connections support
        self.connections = {}  # {connection_name: {connection, cursor, host, db, ...}}
        self.active_connection = None
        
        self.connections_file = "connections_jdbc.json"
        self.saved_connections = self.load_connections()
        
        self.jdbc_driver_path = self.load_jdbc_config()
        self.jvm_started = False
        
        # Auto-search for JVM
        print("\n" + "="*60)
        self.jvm_dll_path = find_jvm_dll_anywhere()
        print("="*60 + "\n")
        
        self.query_history = []
        self.max_history = 100
        self.fetch_limit = 1000
        self.current_offset = 0
        self.last_query = None
        
        # Comparison results storage
        self.last_comparison_result = None
        
        # FK Visualization storage
        self.fk_relationships = {}
        
        # Transaction monitoring
        self.transaction_monitor_running = False
        self.transaction_refresh_interval = 30  # seconds
        
        self.create_menu()
        self.create_toolbar()
        self.create_main_layout()
        self.create_statusbar()
        self.apply_theme()
        
        if self.jvm_dll_path:
            self.update_status(f"Ready - JVM: {self.jvm_dll_path}")
        else:
            self.update_status("ERROR: JVM not found - Java may not be installed")
        
    def load_jdbc_config(self):
        config_file = "jdbc_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f).get('jdbc_driver_path', '')
            except:
                pass
        return ''
        
    def start_jvm(self):
        if self.jvm_started:
            return True
        
        if not JPYPE_AVAILABLE:
            messagebox.showerror("Error", "JPype1 not installed.\n\nRun: pip install JPype1")
            return False
        
        if not self.jdbc_driver_path or not os.path.exists(self.jdbc_driver_path):
            messagebox.showerror("Error", 
                               "JDBC driver not configured.\n\n"
                               "Configure: Connection > Configure JDBC Driver")
            return False
        
        if not self.jvm_dll_path:
            messagebox.showerror("JVM Error", 
                               "Cannot find jvm.dll\n\nJava may not be installed")
            return False
        
        try:
            if not jpype.isJVMStarted():
                print(f"Starting JVM: {self.jvm_dll_path}")
                
                classpath = self.jdbc_driver_path
                
                # Add BSON library
                jdbc_path_normalized = self.jdbc_driver_path.replace('\\', '/')
                
                if '/.m2/repository/' in jdbc_path_normalized:
                    maven_repo = jdbc_path_normalized.split('/.m2/repository/')[0] + '/.m2/repository'
                elif '\\.m2\\repository\\' in self.jdbc_driver_path:
                    maven_repo = self.jdbc_driver_path.split('\\.m2\\repository\\')[0] + '\\.m2\\repository'
                else:
                    jdbc_dir = os.path.dirname(self.jdbc_driver_path)
                    maven_repo = jdbc_dir
                    for _ in range(5):
                        maven_repo = os.path.dirname(maven_repo)
                
                maven_repo = os.path.normpath(maven_repo)
                bson_jar = os.path.join(maven_repo, "org", "mongodb", "bson", "4.11.1", "bson-4.11.1.jar")
                
                if os.path.exists(bson_jar):
                    classpath += os.pathsep + bson_jar
                    print(f"✓ Added BSON library")
                
                jpype.startJVM(
                    self.jvm_dll_path,
                    "-ea",
                    f"-Djava.class.path={classpath}",
                    convertStrings=False
                )
                print("✓ JVM started successfully!")
            self.jvm_started = True
            return True
        except Exception as e:
            messagebox.showerror("JVM Error", f"Failed to start JVM:\n\n{str(e)}")
            return False
        
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Query", command=self.new_query_tab)
        file_menu.add_command(label="Open SQL", command=self.open_sql_file)
        file_menu.add_command(label="Save Query", command=self.save_query)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        conn_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Connection", menu=conn_menu)
        conn_menu.add_command(label="New Connection...", command=self.show_connection_dialog)
        conn_menu.add_command(label="Manage Connections...", command=self.show_connection_manager)
        conn_menu.add_separator()
        conn_menu.add_command(label="Disconnect Active", command=self.disconnect_active)
        conn_menu.add_command(label="Disconnect All", command=self.disconnect_all)
        conn_menu.add_separator()
        conn_menu.add_command(label="Configure JDBC Driver", command=self.configure_jdbc_driver)
        conn_menu.add_separator()
        conn_menu.add_command(label="Check Requirements", command=self.show_requirements)
        
        # Database Comparator Menu
        compare_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Compare", menu=compare_menu)
        compare_menu.add_command(label="🔍 Compare Databases...", command=self.show_database_comparator)
        compare_menu.add_command(label="📊 Compare Specific Tables...", command=self.show_table_comparator)
        compare_menu.add_separator()
        compare_menu.add_command(label="📋 View Last Comparison", command=self.show_last_comparison)
        compare_menu.add_command(label="💾 Export Comparison...", command=self.export_comparison)
        
        # FK Visualizer Menu
        visualizer_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="FK Visualizer", menu=visualizer_menu)
        visualizer_menu.add_command(label="🔗 Show All Relationships", command=self.show_all_fk_relationships)
        visualizer_menu.add_command(label="🎯 Show Table Relationships", command=self.show_table_fk_relationships)
        visualizer_menu.add_command(label="📊 Relationship Statistics", command=self.show_fk_statistics)
        visualizer_menu.add_separator()
        visualizer_menu.add_command(label="💾 Export Graph...", command=self.export_fk_graph)
        visualizer_menu.add_command(label="🖨️ Print Graph", command=self.print_fk_graph)
        
        # Transaction Monitor Menu
        transaction_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Transactions", menu=transaction_menu)
        transaction_menu.add_command(label="📊 Show Active Transactions", command=self.show_active_transactions)
        transaction_menu.add_command(label="⏱️ Show Long-Running Transactions", command=self.show_long_running_transactions)
        transaction_menu.add_command(label="⚠️ Show Suspended Transactions", command=self.show_suspended_transactions)
        transaction_menu.add_separator()
        transaction_menu.add_command(label="🔁 Start Auto-Refresh", command=self.start_transaction_monitor)
        transaction_menu.add_command(label="⏹️ Stop Auto-Refresh", command=self.stop_transaction_monitor)
        transaction_menu.add_separator()
        transaction_menu.add_command(label="⚙️ Configure Monitor...", command=self.configure_transaction_monitor)
        transaction_menu.add_command(label="💾 Export Transaction Log", command=self.export_transaction_log)
        
        query_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Query", menu=query_menu)
        query_menu.add_command(label="Execute (F5)", command=self.execute_query)
        query_menu.add_command(label="Execute with Limit", command=self.execute_with_limit)
        query_menu.add_command(label="Count Rows Only", command=self.count_rows)
        query_menu.add_separator()
        query_menu.add_command(label="Load More Rows", command=self.load_more_rows)
        query_menu.add_separator()
        query_menu.add_command(label="Clear Results", command=self.clear_results)
        query_menu.add_separator()
        query_menu.add_command(label="Set Fetch Limit...", command=self.set_fetch_limit)
        
        self.root.bind('<F5>', lambda e: self.execute_query())
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_toolbar(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        self.conn_btn = ttk.Button(toolbar, text="🔌 Connect", command=self.show_connection_dialog)
        self.conn_btn.pack(side=tk.LEFT, padx=2)
        
        self.disconn_btn = ttk.Button(toolbar, text="❌ Disconnect", command=self.disconnect_active, state=tk.DISABLED)
        self.disconn_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        self.exec_btn = ttk.Button(toolbar, text="▶ Execute", command=self.execute_query, state=tk.DISABLED)
        self.exec_btn.pack(side=tk.LEFT, padx=2)
        
        self.load_more_btn = ttk.Button(toolbar, text="⬇ Load More", command=self.load_more_rows, state=tk.DISABLED)
        self.load_more_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(toolbar, text="🗑 Clear", command=self.clear_results).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Label(toolbar, text="Limit:").pack(side=tk.LEFT, padx=(5,2))
        self.limit_var = tk.StringVar(value="1000")
        limit_combo = ttk.Combobox(toolbar, textvariable=self.limit_var, width=8, 
                                   values=["100", "500", "1000", "5000", "10000", "50000", "ALL"])
        limit_combo.pack(side=tk.LEFT, padx=2)
        limit_combo.bind('<<ComboboxSelected>>', self.on_limit_changed)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        self.export_btn = ttk.Button(toolbar, text="💾 Export", command=self.export_results, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(toolbar, text="🔍 Compare DBs", command=self.show_database_comparator).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔗 FK Graph", command=self.show_all_fk_relationships).pack(side=tk.LEFT, padx=2)
        
        # Transaction monitor indicator
        self.transaction_monitor_indicator = ttk.Label(toolbar, text="⏹️ TX Monitor: OFF", foreground="red")
        self.transaction_monitor_indicator.pack(side=tk.LEFT, padx=20)
        
        ttk.Button(toolbar, text="📊 TX Monitor", command=self.show_active_transactions).pack(side=tk.LEFT, padx=2)
        
        # Status indicators
        jvm_status = "JVM: " + ("Found" if self.jvm_dll_path else "NOT FOUND")
        jvm_color = "green" if self.jvm_dll_path else "red"
        ttk.Label(toolbar, text=jvm_status, foreground=jvm_color).pack(side=tk.RIGHT, padx=10)
        
        jdbc_ok = self.jdbc_driver_path and os.path.exists(self.jdbc_driver_path)
        ttk.Label(toolbar, text="JDBC: " + ("Ready" if jdbc_ok else "Not Set"), 
                 foreground="green" if jdbc_ok else "orange").pack(side=tk.RIGHT, padx=10)
        
        self.conn_count_label = ttk.Label(toolbar, text="Connections: 0", foreground="blue")
        self.conn_count_label.pack(side=tk.RIGHT, padx=10)
        
    def create_main_layout(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel with tabbed connections
        left_frame = ttk.Frame(main_paned, width=250)
        main_paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Database Connections", font=('Arial', 10, 'bold')).pack(pady=5)
        
        # Notebook for multiple database connections
        self.db_notebook = ttk.Notebook(left_frame)
        self.db_notebook.pack(fill=tk.BOTH, expand=True)
        self.db_notebook.bind('<<NotebookTabChanged>>', self.on_connection_tab_changed)
        
        # Add welcome tab
        welcome_tab = ttk.Frame(self.db_notebook)
        self.db_notebook.add(welcome_tab, text="Welcome")
        
        welcome_text = ttk.Label(welcome_tab, 
                                text="No connections\n\nClick 'Connect' to add\na database connection",
                                justify=tk.CENTER)
        welcome_text.pack(expand=True)
        
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=4)
        
        query_paned = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        query_paned.pack(fill=tk.BOTH, expand=True)
        
        editor_frame = ttk.Frame(query_paned, height=300)
        query_paned.add(editor_frame, weight=1)
        
        ttk.Label(editor_frame, text="SQL Editor", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        self.query_notebook = ttk.Notebook(editor_frame)
        self.query_notebook.pack(fill=tk.BOTH, expand=True)
        self.new_query_tab()
        
        results_frame = ttk.Frame(query_paned, height=400)
        query_paned.add(results_frame, weight=2)
        
        ttk.Label(results_frame, text="Query Results", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        self.results_notebook = ttk.Notebook(results_frame)
        self.results_notebook.pack(fill=tk.BOTH, expand=True)
        self.create_results_tab("Results")
        
    def create_statusbar(self):
        self.statusbar = ttk.Frame(self.root, relief=tk.SUNKEN)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ttk.Label(self.statusbar, text="Ready", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.active_conn_label = ttk.Label(self.statusbar, text="Active: None", anchor=tk.E, foreground="blue")
        self.active_conn_label.pack(side=tk.RIGHT, padx=10)
        
        self.rows_label = ttk.Label(self.statusbar, text="Rows: 0", anchor=tk.E)
        self.rows_label.pack(side=tk.RIGHT, padx=5)
        
        self.time_label = ttk.Label(self.statusbar, text="Time: 0.00s", anchor=tk.E)
        self.time_label.pack(side=tk.RIGHT, padx=5)
        
    def new_query_tab(self):
        tab_frame = ttk.Frame(self.query_notebook)
        self.query_notebook.add(tab_frame, text=f"Query {len(self.query_notebook.tabs())+1}")
        
        sql_editor = scrolledtext.ScrolledText(tab_frame, wrap=tk.NONE, font=('Consolas', 11))
        sql_editor.pack(fill=tk.BOTH, expand=True)
        tab_frame.sql_editor = sql_editor
        self.query_notebook.select(tab_frame)
        
    def create_results_tab(self, name):
        tab_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(tab_frame, text=name)
        
        tree_scroll_y = ttk.Scrollbar(tab_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree_scroll_x = ttk.Scrollbar(tab_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        results_tree = ttk.Treeview(tab_frame, yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tree_scroll_y.config(command=results_tree.yview)
        tree_scroll_x.config(command=results_tree.xview)
        
        tab_frame.results_tree = results_tree
        tab_frame.results_data = None
        return tab_frame
    
    def create_db_tree_tab(self, connection_name):
        """Create a new database tree tab for a connection"""
        tab_frame = ttk.Frame(self.db_notebook)
        self.db_notebook.add(tab_frame, text=connection_name)
        
        # Add connection info label
        conn_info = self.connections[connection_name]
        info_text = f"{conn_info['database']}@{conn_info['host']}:{conn_info['port']}"
        info_label = ttk.Label(tab_frame, text=info_text, font=('Arial', 8), foreground='blue')
        info_label.pack(pady=2)
        
        # Add tree view
        tree_scroll = ttk.Scrollbar(tab_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        db_tree = ttk.Treeview(tab_frame, yscrollcommand=tree_scroll.set)
        db_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=db_tree.yview)
        
        db_tree.bind('<Double-Button-1>', self.on_tree_double_click)
        db_tree.bind('<Button-3>', self.on_tree_right_click)
        db_tree.bind('<<TreeviewOpen>>', self.on_tree_expand)
        
        tab_frame.db_tree = db_tree
        tab_frame.connection_name = connection_name
        
        # Remove welcome tab if present
        if self.db_notebook.index("end") > 1:
            try:
                for i in range(self.db_notebook.index("end")):
                    if self.db_notebook.tab(i, "text") == "Welcome":
                        self.db_notebook.forget(i)
                        break
            except:
                pass
        
        self.db_notebook.select(tab_frame)
        return db_tree
    
    def on_connection_tab_changed(self, event):
        """Handle connection tab change"""
        try:
            current_tab = self.db_notebook.select()
            if current_tab:
                tab_frame = self.db_notebook.nametowidget(current_tab)
                if hasattr(tab_frame, 'connection_name'):
                    self.active_connection = tab_frame.connection_name
                    self.active_conn_label.config(text=f"Active: {self.active_connection}")
                    self.exec_btn.config(state=tk.NORMAL)
                    self.disconn_btn.config(state=tk.NORMAL)
                else:
                    self.active_connection = None
                    self.active_conn_label.config(text="Active: None")
                    self.exec_btn.config(state=tk.DISABLED)
                    self.disconn_btn.config(state=tk.DISABLED)
        except:
            pass
        
    def show_connection_dialog(self):
        """Show new connection dialog"""
        # Check requirements
        missing = []
        
        if not JAYDEBEAPI_AVAILABLE:
            missing.append("❌ JayDeBeApi not installed\n   Run: pip install JayDeBeApi")
        
        if not JPYPE_AVAILABLE:
            missing.append("❌ JPype1 not installed\n   Run: pip install JPype1")
        
        if not self.jdbc_driver_path:
            missing.append("❌ JDBC driver not configured\n   Go to: Connection > Configure JDBC Driver")
        elif not os.path.exists(self.jdbc_driver_path):
            missing.append(f"❌ JDBC driver file not found:\n   {self.jdbc_driver_path}")
        
        if not self.jvm_dll_path:
            missing.append("❌ JVM (jvm.dll) not found\n   Install Java from oracle.com")
        
        if missing:
            error_msg = "Missing Requirements:\n\n" + "\n\n".join(missing)
            error_msg += "\n\nFor detailed status, go to:\nConnection > Check Requirements"
            messagebox.showerror("Missing Requirements", error_msg)
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("New Database Connection")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        fields = [
            ("Connection Name:", "PROD"),
            ("Host:", "172.22.15.234"),
            ("Port:", "9027"),
            ("Database:", "ccp"),
            ("INFORMIXSERVER:", "BANK_CC_TRT"),
            ("Username:", "cctrtdev"),
            ("Password:", ""),
        ]
        
        entries = {}
        for i, (label, default) in enumerate(fields):
            ttk.Label(main_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            e = ttk.Entry(main_frame, width=40, show="*" if "Pass" in label else "")
            e.insert(0, default)
            e.grid(row=i, column=1, sticky=tk.EW, pady=5)
            entries[label.rstrip(":")] = e
        
        # Add color picker for connection
        ttk.Label(main_frame, text="Connection Color:").grid(row=len(fields), column=0, sticky=tk.W, pady=5)
        color_var = tk.StringVar(value="blue")
        color_combo = ttk.Combobox(main_frame, textvariable=color_var, width=37, 
                                   values=["blue", "green", "red", "orange", "purple", "brown"])
        color_combo.grid(row=len(fields), column=1, sticky=tk.EW, pady=5)
        
        def connect():
            conn_name = entries["Connection Name"].get().strip()
            host = entries["Host"].get()
            port = entries["Port"].get()
            database = entries["Database"].get()
            server = entries["INFORMIXSERVER"].get()
            username = entries["Username"].get()
            password = entries["Password"].get()
            color = color_var.get()
            
            if not conn_name:
                messagebox.showerror("Error", "Please enter a connection name")
                return
            
            if conn_name in self.connections:
                if not messagebox.askyesno("Confirm", f"Connection '{conn_name}' already exists.\n\nReplace it?"):
                    return
                # Close existing connection
                self.close_connection(conn_name)
            
            dialog.destroy()
            
            self.connect_to_database(conn_name, host, port, database, server, username, password, color)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=len(fields)+1, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Connect", command=connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
        
        main_frame.columnconfigure(1, weight=1)
        
    def connect_to_database(self, conn_name, host, port, db, server, user, pwd, color="blue"):
        """Connect to a database and add to connections"""
        try:
            self.update_status(f"Connecting to {conn_name}...")
            if not self.start_jvm():
                return
            
            url = f"jdbc:informix-sqli://{host}:{port}/{db}:INFORMIXSERVER={server};CLIENT_LOCALE=en_US.utf8"
            
            connection = jaydebeapi.connect("com.informix.jdbc.IfxDriver", url, [user, pwd], self.jdbc_driver_path)
            cursor = connection.cursor()
            
            # Store connection info
            self.connections[conn_name] = {
                'connection': connection,
                'cursor': cursor,
                'host': host,
                'port': port,
                'database': db,
                'server': server,
                'username': user,
                'color': color,
                'connected_at': datetime.now()
            }
            
            # Create database tree tab
            db_tree = self.create_db_tree_tab(conn_name)
            
            # Set as active connection
            self.active_connection = conn_name
            
            # Update UI
            self.update_connection_count()
            self.active_conn_label.config(text=f"Active: {conn_name}")
            self.exec_btn.config(state=tk.NORMAL)
            self.disconn_btn.config(state=tk.NORMAL)
            
            self.update_status(f"Connected to {conn_name}")
            
            # Load database tree
            self.refresh_database_tree_for_connection(conn_name, db_tree)
            
            messagebox.showinfo("Success", f"Connected to {conn_name}!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed:\n\n{str(e)}")
    
    def refresh_database_tree_for_connection(self, conn_name, db_tree):
        """Refresh database tree for a specific connection"""
        if conn_name not in self.connections:
            return
        
        try:
            conn_info = self.connections[conn_name]
            cursor = conn_info['cursor']
            
            self.update_status(f"Loading database objects for {conn_name}...")
            db_tree.delete(*db_tree.get_children())
            
            # Add Tables node
            tables_node = db_tree.insert('', tk.END, text='📁 Tables', open=True)
            
            # Get all user tables
            cursor.execute("""
                SELECT tabname, tabid 
                FROM systables 
                WHERE tabtype='T' AND tabid>99 
                ORDER BY tabname
            """)
            
            tables = cursor.fetchall()
            
            for table_name, tabid in tables:
                table_node = db_tree.insert(
                    tables_node, 
                    tk.END, 
                    text=f'📊 {table_name}',
                    values=('table', table_name, tabid, conn_name)
                )
                
                # Add placeholder
                db_tree.insert(table_node, tk.END, text='Loading...')
            
            self.update_status(f"Loaded {len(tables)} tables for {conn_name}")
            
        except Exception as e:
            print(f"Error loading database tree for {conn_name}: {e}")
            self.update_status(f"Error loading database objects for {conn_name}")
    
    # ==== TRANSACTION MONITOR ====
    
    def show_active_transactions(self):
        """Show all active transactions"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection.\n\nConnect to a database first.")
            return
        
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            self.update_status("Loading active transactions...")
            
            try:
                # Primary: syssessions (most reliable across Informix versions)
                cursor.execute("""
                    SELECT 
                        sid,
                        username,
                        connected,
                        'ACTIVE' as status,
                        '' as logged
                    FROM sysmaster:syssessions
                    WHERE connected IS NOT NULL
                    ORDER BY connected
                """)
                transactions = cursor.fetchall()
                columns = ['Session ID', 'Username', 'Connected', 'Status', 'Logged']
                
            except:
                try:
                    # Fallback: syslocks
                    cursor.execute("""
                        SELECT 
                            dbsname,
                            tabname,
                            rowidlk,
                            owner,
                            'LOCKED' as status
                        FROM sysmaster:syslocks
                        WHERE keynum > 0
                        ORDER BY dbsname, tabname
                    """)
                    transactions = cursor.fetchall()
                    columns = ['Database', 'Table', 'Row ID', 'Owner', 'Status']
                except Exception as inner_e:
                    messagebox.showerror("Error", 
                        f"Cannot access Informix SMI tables.\n\n"
                        f"Make sure the connected user has access to sysmaster database.\n\n"
                        f"Error: {str(inner_e)}")
                    return
            
            if not transactions:
                messagebox.showinfo("No Active Transactions", "No active transactions found.")
                return
            
            # Show transactions in a dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Active Transactions - {self.active_connection}")
            dialog.geometry("1000x600")
            dialog.transient(self.root)
            
            main_frame = ttk.Frame(dialog, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(main_frame, text=f"Active Transactions - {self.active_connection}", 
                     font=('Arial', 14, 'bold')).pack(pady=10)
            
            # Summary
            summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding=10)
            summary_frame.pack(fill=tk.X, pady=10)
            
            active_count = sum(1 for t in transactions if 'ACTIVE' in str(t[3]).upper())
            suspended_count = sum(1 for t in transactions if 'SUSPENDED' in str(t[3]).upper())
            locked_count = sum(1 for t in transactions if 'LOCKED' in str(t[3]).upper())
            
            summary_text = f"""
            Total Transactions: {len(transactions)}
            Active: {active_count}
            Suspended: {suspended_count}
            Locked: {locked_count}
            """
            
            ttk.Label(summary_frame, text=summary_text, justify=tk.LEFT).pack()
            
            # Transactions table
            table_frame = ttk.Frame(main_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            
            tree_scroll_y = ttk.Scrollbar(table_frame)
            tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
            
            tree_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
            tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
            
            tree = ttk.Treeview(table_frame, 
                              yscrollcommand=tree_scroll_y.set,
                              xscrollcommand=tree_scroll_x.set,
                              columns=columns,
                              show='headings')
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            tree_scroll_y.config(command=tree.yview)
            tree_scroll_x.config(command=tree.xview)
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)
            
            for i, transaction in enumerate(transactions):
                values = [str(v) if v is not None else '' for v in transaction]
                
                status = str(values[3]).upper() if len(values) > 3 else ''
                if 'SUSPENDED' in status:
                    tag = 'suspended'
                elif 'LOCKED' in status:
                    tag = 'locked'
                else:
                    tag = 'active'
                
                tree.insert('', tk.END, values=values, tags=(tag,))
            
            tree.tag_configure('active', background='lightgreen')
            tree.tag_configure('suspended', background='lightcoral')
            tree.tag_configure('locked', background='lightyellow')
            
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            
            def refresh():
                dialog.destroy()
                self.show_active_transactions()
            
            def kill_selected():
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select a transaction first.")
                    return
                
                item = tree.item(selection[0])
                tx_id = item['values'][0]
                
                if messagebox.askyesno("Confirm Kill", 
                                      f"Kill transaction/session: {tx_id}?\n\n"
                                      "WARNING: This may cause data inconsistency!"):
                    try:
                        cursor.execute(f"EXECUTE FUNCTION admin('kill_session', {tx_id})")
                        messagebox.showinfo("Success", f"Transaction {tx_id} killed.")
                        refresh()
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to kill transaction:\n\n{str(e)}")
            
            def show_details():
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select a transaction first.")
                    return
                
                item = tree.item(selection[0])
                self.show_transaction_details(item['values'])
            
            ttk.Button(button_frame, text="🔄 Refresh", command=refresh).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🔍 Details", command=show_details).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="💀 Kill Selected", command=kill_selected).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
            
            self.update_status(f"Found {len(transactions)} active transactions")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load transactions:\n\n{str(e)}")
    
    def show_transaction_details(self, transaction_info):
        """Show detailed information about a specific transaction"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Transaction Details")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Transaction Details", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Tab 1: Basic Info
        basic_tab = ttk.Frame(notebook)
        notebook.add(basic_tab, text="📋 Basic Info")
        
        basic_text = scrolledtext.ScrolledText(basic_tab, wrap=tk.WORD, font=('Consolas', 10))
        basic_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        content = []
        content.append("TRANSACTION INFORMATION")
        content.append("="*50)
        content.append("")
        
        for i, value in enumerate(transaction_info):
            label = f"Field {i+1}"
            if i == 0:
                label = "Transaction/Session ID"
            elif i == 1:
                label = "Owner/Username"
            elif i == 2:
                label = "Start/Connect Time"
            elif i == 3:
                label = "Status"
            elif i == 4:
                label = "Logged/Other Info"
            
            content.append(f"{label}: {value}")
        
        basic_text.insert('1.0', '\n'.join(content))
        basic_text.config(state=tk.DISABLED)
        
        # Tab 2: SQL to Investigate
        sql_tab = ttk.Frame(notebook)
        notebook.add(sql_tab, text="📝 Investigation SQL")
        
        sql_text = scrolledtext.ScrolledText(sql_tab, wrap=tk.WORD, font=('Consolas', 10))
        sql_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tx_id = transaction_info[0] if transaction_info else ''
        
        sql_queries = []
        sql_queries.append("-- SQL Queries to investigate this transaction:")
        sql_queries.append("="*60)
        sql_queries.append("")
        sql_queries.append("-- 1. Check for locks held by this transaction:")
        sql_queries.append("SELECT * FROM sysmaster:syslocks WHERE owner = <session_id>;")
        sql_queries.append("")
        sql_queries.append("-- 2. Check session details:")
        sql_queries.append("SELECT * FROM sysmaster:syssessions WHERE sid = <session_id>;")
        sql_queries.append("")
        sql_queries.append("-- 3. Check active statements:")
        sql_queries.append("SELECT * FROM sysmaster:syssqltrace WHERE sid = <session_id>;")
        sql_queries.append("")
        sql_queries.append("-- 4. Kill this transaction (CAUTION!):")
        sql_queries.append(f"EXECUTE FUNCTION admin('kill_session', {tx_id});")
        sql_queries.append("")
        sql_queries.append("-- 5. Check for long-running queries:")
        sql_queries.append("SELECT * FROM sysmaster:syssqltrace WHERE starttime < CURRENT - INTERVAL(5) MINUTE TO MINUTE;")
        
        sql_text.insert('1.0', '\n'.join(sql_queries))
        sql_text.config(state=tk.DISABLED)
        
        # Tab 3: Actions
        actions_tab = ttk.Frame(notebook)
        notebook.add(actions_tab, text="⚡ Actions")
        
        actions_frame = ttk.Frame(actions_tab, padding=20)
        actions_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(actions_frame, text="Available Actions:", 
                 font=('Arial', 11, 'bold')).pack(pady=10)
        
        def copy_sql_to_editor():
            tab = self.query_notebook.nametowidget(self.query_notebook.select())
            tab.sql_editor.delete('1.0', tk.END)
            
            investigation_sql = f"""
-- Investigate transaction {tx_id}
SELECT * FROM sysmaster:syslocks WHERE owner = {tx_id};

SELECT * FROM sysmaster:syssessions WHERE sid = {tx_id};

SELECT * FROM sysmaster:syssqltrace WHERE sid = {tx_id};
"""
            tab.sql_editor.insert('1.0', investigation_sql)
            dialog.destroy()
        
        def send_kill_command():
            if messagebox.askyesno("Confirm Kill", 
                                  f"Kill transaction {tx_id}?\n\n"
                                  "WARNING: This may cause data inconsistency!"):
                try:
                    conn_info = self.connections[self.active_connection]
                    cursor = conn_info['cursor']
                    cursor.execute(f"EXECUTE FUNCTION admin('kill_session', {tx_id})")
                    messagebox.showinfo("Success", f"Transaction {tx_id} killed.")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to kill transaction:\n\n{str(e)}")
        
        def monitor_transaction():
            self.start_transaction_monitor_for_tx(tx_id)
            dialog.destroy()
        
        ttk.Button(actions_frame, text="📋 Copy SQL to Editor", 
                  command=copy_sql_to_editor).pack(pady=10, fill=tk.X)
        ttk.Button(actions_frame, text="👁️ Monitor This Transaction", 
                  command=monitor_transaction).pack(pady=10, fill=tk.X)
        ttk.Button(actions_frame, text="💀 Kill Transaction", 
                  command=send_kill_command).pack(pady=10, fill=tk.X)
        
        ttk.Label(actions_frame, text="\nWarning: Killing transactions can cause\n"
                 "data inconsistency or application errors!", 
                 foreground="red", justify=tk.CENTER).pack(pady=20)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def show_long_running_transactions(self):
        """Show transactions running for a long time"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection.\n\nConnect to a database first.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Long-Running Transactions")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Long-Running Transaction Monitor", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        ttk.Label(main_frame, text="Show transactions running longer than:", 
                 font=('Arial', 10)).pack(pady=10)
        
        time_frame = ttk.Frame(main_frame)
        time_frame.pack(pady=10)
        
        time_var = tk.IntVar(value=5)
        ttk.Radiobutton(time_frame, text="5 minutes", variable=time_var, value=5).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(time_frame, text="15 minutes", variable=time_var, value=15).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(time_frame, text="30 minutes", variable=time_var, value=30).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(time_frame, text="1 hour", variable=time_var, value=60).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(time_frame, text="2 hours", variable=time_var, value=120).pack(side=tk.LEFT, padx=10)
        
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
        options_frame.pack(fill=tk.X, pady=10)
        
        include_active_var = tk.BooleanVar(value=True)
        include_suspended_var = tk.BooleanVar(value=True)
        include_idle_var = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(options_frame, text="Include Active Transactions", 
                       variable=include_active_var).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Include Suspended Transactions", 
                       variable=include_suspended_var).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Include Idle Sessions", 
                       variable=include_idle_var).pack(anchor=tk.W)
        
        def find_long_running():
            threshold = time_var.get()
            options = {
                'active': include_active_var.get(),
                'suspended': include_suspended_var.get(),
                'idle': include_idle_var.get()
            }
            
            dialog.destroy()
            self.find_long_running_transactions(threshold, options)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="🔍 Find Long-Running TX", 
                  command=find_long_running).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def find_long_running_transactions(self, threshold_minutes, options):
        """Find transactions running longer than threshold"""
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            self.update_status(f"Finding transactions running > {threshold_minutes} minutes...")
            
            try:
                cursor.execute(f"""
                    SELECT 
                        sid,
                        username,
                        connected,
                        'LONG_RUNNING' as status,
                        CURRENT - connected as duration
                    FROM sysmaster:syssessions
                    WHERE connected IS NOT NULL
                    AND (CURRENT - connected) > INTERVAL({threshold_minutes}) MINUTE TO MINUTE
                    ORDER BY connected
                """)
                transactions = cursor.fetchall()
            except:
                cursor.execute(f"""
                    SELECT 
                        sid,
                        username,
                        connected,
                        'LONG_RUNNING' as status,
                        '> {threshold_minutes} min' as duration
                    FROM sysmaster:syssessions
                    WHERE connected IS NOT NULL
                    ORDER BY connected
                """)
                transactions = cursor.fetchall()
            
            if not transactions:
                messagebox.showinfo("No Long-Running Transactions", 
                                  f"No transactions found running longer than {threshold_minutes} minutes.")
                return
            
            self.show_transaction_results(transactions, 
                                        f"Long-Running Transactions (> {threshold_minutes} min)",
                                        ['Session ID', 'Username', 'Connected', 'Status', 'Duration'])
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to find long-running transactions:\n\n{str(e)}")
    
    def show_suspended_transactions(self):
        """Show suspended/blocked transactions"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection.\n\nConnect to a database first.")
            return
        
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            self.update_status("Finding suspended transactions...")
            
            try:
                cursor.execute("""
                    SELECT 
                        l1.owner as blocked_sid,
                        u1.username as blocked_user,
                        l2.owner as blocking_sid,
                        u2.username as blocking_user,
                        l1.dbsname,
                        l1.tabname,
                        'BLOCKED' as status
                    FROM sysmaster:syslocks l1
                    JOIN sysmaster:syslocks l2 ON l1.dbsname = l2.dbsname 
                        AND l1.tabname = l2.tabname 
                        AND l1.rowidlk = l2.rowidlk
                        AND l1.owner != l2.owner
                    LEFT JOIN sysmaster:syssessions u1 ON l1.owner = u1.sid
                    LEFT JOIN sysmaster:syssessions u2 ON l2.owner = u2.sid
                    WHERE l1.keynum > 0 AND l2.keynum > 0
                    ORDER BY l1.dbsname, l1.tabname
                """)
                suspended = cursor.fetchall()
            except:
                cursor.execute("""
                    SELECT 
                        owner,
                        dbsname,
                        tabname,
                        rowidlk,
                        'LOCK_HELD' as status
                    FROM sysmaster:syslocks
                    WHERE keynum > 0
                    ORDER BY dbsname, tabname
                """)
                suspended = cursor.fetchall()
            
            if not suspended:
                messagebox.showinfo("No Suspended Transactions", 
                                  "No suspended or blocked transactions found.")
                return
            
            self.show_transaction_results(suspended, 
                                        "Suspended/Blocked Transactions",
                                        ['Blocked SID', 'Blocked User', 'Blocking SID', 
                                         'Blocking User', 'Database', 'Table', 'Status'])
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to find suspended transactions:\n\n{str(e)}")
    
    def show_transaction_results(self, transactions, title, columns):
        """Show transaction results in a table"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("1200x600")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=title, 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding=10)
        summary_frame.pack(fill=tk.X, pady=10)
        
        summary_text = f"Found {len(transactions)} transactions"
        ttk.Label(summary_frame, text=summary_text, justify=tk.LEFT).pack()
        
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        tree_scroll_y = ttk.Scrollbar(table_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        tree = ttk.Treeview(table_frame, 
                          yscrollcommand=tree_scroll_y.set,
                          xscrollcommand=tree_scroll_x.set,
                          columns=columns,
                          show='headings')
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tree_scroll_y.config(command=tree.yview)
        tree_scroll_x.config(command=tree.xview)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        
        for transaction in transactions:
            values = [str(v) if v is not None else '' for v in transaction]
            tree.insert('', tk.END, values=values)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        def export_results():
            f = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv"), ("Text", "*.txt"), ("All Files", "*.*")],
                initialfile=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
            if f:
                try:
                    import csv
                    with open(f, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(columns)
                        for transaction in transactions:
                            writer.writerow([str(v) if v is not None else '' for v in transaction])
                    messagebox.showinfo("Success", f"Exported to:\n{f}")
                except Exception as e:
                    messagebox.showerror("Error", f"Export failed:\n\n{str(e)}")
        
        ttk.Button(button_frame, text="💾 Export", command=export_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def start_transaction_monitor(self):
        """Start automatic transaction monitoring"""
        if not self.active_connection:
            messagebox.showwarning("Warning", "No active connection.")
            return
        
        if self.transaction_monitor_running:
            messagebox.showinfo("Info", "Transaction monitor is already running.")
            return
        
        self.transaction_monitor_running = True
        self.transaction_monitor_indicator.config(
            text="▶️ TX Monitor: ON", 
            foreground="green"
        )
        
        self.create_transaction_monitor_window()
        
        self.monitor_thread = threading.Thread(target=self.transaction_monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.update_status("Transaction monitor started")
    
    def start_transaction_monitor_for_tx(self, tx_id):
        """Start monitoring for a specific transaction"""
        if not self.active_connection:
            messagebox.showwarning("Warning", "No active connection.")
            return
        
        self.create_transaction_monitor_window(focus_tx_id=tx_id)
        
        if not self.transaction_monitor_running:
            self.transaction_monitor_running = True
            self.transaction_monitor_indicator.config(
                text="▶️ TX Monitor: ON", 
                foreground="green"
            )
            
            self.monitor_thread = threading.Thread(target=self.transaction_monitor_loop, daemon=True)
            self.monitor_thread.start()
        
        self.update_status(f"Monitoring transaction {tx_id}")
    
    def create_transaction_monitor_window(self, focus_tx_id=None):
        """Create transaction monitor window"""
        if hasattr(self, 'monitor_window') and self.monitor_window:
            try:
                self.monitor_window.deiconify()
                self.monitor_window.lift()
                return
            except:
                pass
        
        self.monitor_window = tk.Toplevel(self.root)
        self.monitor_window.title("Transaction Monitor - Live View")
        self.monitor_window.geometry("1200x700")
        
        self.monitor_window.focus_tx_id = focus_tx_id
        
        main_frame = ttk.Frame(self.monitor_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header_text = "🔴 Live Transaction Monitor"
        if focus_tx_id:
            header_text += f" - Focus: {focus_tx_id}"
        
        header = ttk.Label(main_frame, text=header_text, 
                          font=('Arial', 14, 'bold'))
        header.pack(pady=10)
        
        stats_frame = ttk.LabelFrame(main_frame, text="Live Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=10)
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack()
        
        self.stats_labels = {}
        stats = [
            ('Total TX:', 'total_tx', '0'),
            ('Active:', 'active_tx', '0'),
            ('Suspended:', 'suspended_tx', '0'),
            ('Long-Running:', 'long_tx', '0'),
            ('Blocked:', 'blocked_tx', '0'),
            ('Last Update:', 'last_update', 'Never')
        ]
        
        for i, (label, key, default) in enumerate(stats):
            row = i // 3
            col = i % 3
            
            frame = ttk.Frame(stats_grid)
            frame.grid(row=row, column=col, padx=20, pady=5, sticky=tk.W)
            
            ttk.Label(frame, text=label, font=('Arial', 9)).pack(side=tk.LEFT)
            value_label = ttk.Label(frame, text=default, font=('Arial', 9, 'bold'))
            value_label.pack(side=tk.LEFT, padx=5)
            self.stats_labels[key] = value_label
        
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        tree_scroll_y = ttk.Scrollbar(table_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.monitor_tree = ttk.Treeview(table_frame, 
                                       yscrollcommand=tree_scroll_y.set,
                                       xscrollcommand=tree_scroll_x.set,
                                       columns=('ID', 'User', 'Start', 'Status', 'Duration', 'Info'),
                                       show='headings')
        self.monitor_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tree_scroll_y.config(command=self.monitor_tree.yview)
        tree_scroll_x.config(command=self.monitor_tree.xview)
        
        columns = {
            'ID': 100,
            'User': 120,
            'Start': 150,
            'Status': 100,
            'Duration': 100,
            'Info': 400
        }
        
        for col, width in columns.items():
            self.monitor_tree.heading(col, text=col)
            self.monitor_tree.column(col, width=width)
        
        self.monitor_tree.tag_configure('active', background='lightgreen')
        self.monitor_tree.tag_configure('suspended', background='lightcoral')
        self.monitor_tree.tag_configure('blocked', background='lightyellow')
        self.monitor_tree.tag_configure('long', background='orange')
        self.monitor_tree.tag_configure('focus', background='lightblue', font=('Arial', 9, 'bold'))
        
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(pady=10)
        
        interval_frame = ttk.Frame(control_frame)
        interval_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(interval_frame, text="Refresh:").pack(side=tk.LEFT)
        self.refresh_interval_var = tk.StringVar(value="30")
        interval_combo = ttk.Combobox(interval_frame, 
                                     textvariable=self.refresh_interval_var,
                                     width=8,
                                     values=["5", "10", "30", "60", "300"],
                                     state='readonly')
        interval_combo.pack(side=tk.LEFT, padx=5)
        
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.LEFT, padx=20)
        
        def manual_refresh():
            self.refresh_transaction_monitor()
        
        def stop_monitor():
            self.stop_transaction_monitor()
        
        def clear_monitor():
            self.monitor_tree.delete(*self.monitor_tree.get_children())
        
        def export_monitor():
            self.export_transaction_log()
        
        ttk.Button(button_frame, text="🔄 Refresh Now", command=manual_refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑 Clear", command=clear_monitor).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="💾 Export", command=export_monitor).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="⏹️ Stop Monitor", command=stop_monitor).pack(side=tk.LEFT, padx=5)
        
        self.monitor_status = ttk.Label(main_frame, text="Monitoring started...", foreground="blue")
        self.monitor_status.pack(pady=5)
        
        self.monitor_window.protocol("WM_DELETE_WINDOW", self.on_monitor_window_close)
        
        self.refresh_transaction_monitor()
    
    def transaction_monitor_loop(self):
        """Main monitoring loop"""
        import time
        
        while self.transaction_monitor_running:
            try:
                self.root.after(0, self.refresh_transaction_monitor)
                
                interval = int(self.refresh_interval_var.get())
                for _ in range(interval * 2):
                    if not self.transaction_monitor_running:
                        break
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(5)
    
    def refresh_transaction_monitor(self):
        """Refresh transaction monitor data"""
        if not hasattr(self, 'monitor_window') or not self.monitor_window:
            return
        
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            self.monitor_tree.delete(*self.monitor_tree.get_children())
            
            try:
                cursor.execute("""
                    SELECT 
                        sid,
                        username,
                        connected,
                        'ACTIVE' as status,
                        CURRENT - connected as duration,
                        '' as info
                    FROM sysmaster:syssessions
                    WHERE connected IS NOT NULL
                    ORDER BY connected
                """)
                transactions = cursor.fetchall()
            except:
                cursor.execute("""
                    SELECT FIRST 10
                        sid,
                        username,
                        CURRENT as connected,
                        'ACTIVE' as status,
                        'N/A' as duration,
                        '' as info
                    FROM sysmaster:syssessions
                    WHERE 1=1
                """)
                transactions = cursor.fetchall()
            
            total = len(transactions)
            active = sum(1 for t in transactions if 'ACTIVE' in str(t[3]).upper())
            suspended = sum(1 for t in transactions if 'SUSPENDED' in str(t[3]).upper())
            
            self.stats_labels['total_tx'].config(text=str(total))
            self.stats_labels['active_tx'].config(text=str(active))
            self.stats_labels['suspended_tx'].config(text=str(suspended))
            self.stats_labels['last_update'].config(text=datetime.now().strftime('%H:%M:%S'))
            
            focus_tx_id = getattr(self.monitor_window, 'focus_tx_id', None)
            
            for tx in transactions:
                values = [str(v) if v is not None else '' for v in tx]
                
                status = str(values[3]).upper()
                if focus_tx_id and str(values[0]) == str(focus_tx_id):
                    tag = 'focus'
                elif 'SUSPENDED' in status:
                    tag = 'suspended'
                else:
                    tag = 'active'
                
                self.monitor_tree.insert('', tk.END, values=values, tags=(tag,))
            
            self.monitor_status.config(text=f"Last updated: {datetime.now().strftime('%H:%M:%S')} - {total} transactions")
            
        except Exception as e:
            self.monitor_status.config(text=f"Error: {str(e)}", foreground="red")
    
    def on_monitor_window_close(self):
        """Handle monitor window close"""
        self.monitor_window.destroy()
        self.monitor_window = None
    
    def stop_transaction_monitor(self):
        """Stop automatic transaction monitoring"""
        self.transaction_monitor_running = False
        self.transaction_monitor_indicator.config(
            text="⏹️ TX Monitor: OFF", 
            foreground="red"
        )
        
        if hasattr(self, 'monitor_window') and self.monitor_window:
            self.monitor_window.destroy()
            self.monitor_window = None
        
        self.update_status("Transaction monitor stopped")
    
    def configure_transaction_monitor(self):
        """Configure transaction monitor settings"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configure Transaction Monitor")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Transaction Monitor Configuration", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        interval_frame = ttk.LabelFrame(main_frame, text="Refresh Interval", padding=10)
        interval_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(interval_frame, text="Seconds between refreshes:").pack(anchor=tk.W)
        interval_var = tk.IntVar(value=self.transaction_refresh_interval)
        
        ttk.Radiobutton(interval_frame, text="5 seconds", variable=interval_var, value=5).pack(anchor=tk.W)
        ttk.Radiobutton(interval_frame, text="10 seconds", variable=interval_var, value=10).pack(anchor=tk.W)
        ttk.Radiobutton(interval_frame, text="30 seconds", variable=interval_var, value=30).pack(anchor=tk.W)
        ttk.Radiobutton(interval_frame, text="1 minute", variable=interval_var, value=60).pack(anchor=tk.W)
        ttk.Radiobutton(interval_frame, text="5 minutes", variable=interval_var, value=300).pack(anchor=tk.W)
        
        alert_frame = ttk.LabelFrame(main_frame, text="Alert Thresholds", padding=10)
        alert_frame.pack(fill=tk.X, pady=10)
        
        long_run_frame = ttk.Frame(alert_frame)
        long_run_frame.pack(fill=tk.X, pady=5)
        ttk.Label(long_run_frame, text="Long-running alert after:").pack(side=tk.LEFT)
        long_run_var = tk.StringVar(value="300")
        ttk.Entry(long_run_frame, textvariable=long_run_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(long_run_frame, text="seconds").pack(side=tk.LEFT)
        
        blocked_frame = ttk.Frame(alert_frame)
        blocked_frame.pack(fill=tk.X, pady=5)
        ttk.Label(blocked_frame, text="Blocked alert after:").pack(side=tk.LEFT)
        blocked_var = tk.StringVar(value="60")
        ttk.Entry(blocked_frame, textvariable=blocked_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(blocked_frame, text="seconds").pack(side=tk.LEFT)
        
        options_frame = ttk.LabelFrame(main_frame, text="Monitoring Options", padding=10)
        options_frame.pack(fill=tk.X, pady=10)
        
        monitor_all_var = tk.BooleanVar(value=True)
        monitor_suspended_var = tk.BooleanVar(value=True)
        monitor_long_var = tk.BooleanVar(value=True)
        alert_sound_var = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(options_frame, text="Monitor all transactions", 
                       variable=monitor_all_var).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Monitor suspended transactions", 
                       variable=monitor_suspended_var).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Monitor long-running transactions", 
                       variable=monitor_long_var).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Play alert sound", 
                       variable=alert_sound_var).pack(anchor=tk.W)
        
        def save_config():
            self.transaction_refresh_interval = interval_var.get()
            
            config = {
                'refresh_interval': interval_var.get(),
                'long_run_threshold': long_run_var.get(),
                'blocked_threshold': blocked_var.get(),
                'monitor_all': monitor_all_var.get(),
                'monitor_suspended': monitor_suspended_var.get(),
                'monitor_long': monitor_long_var.get(),
                'alert_sound': alert_sound_var.get()
            }
            
            with open('transaction_monitor_config.json', 'w') as f:
                json.dump(config, f)
            
            messagebox.showinfo("Success", "Configuration saved!")
            dialog.destroy()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Save", command=save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def export_transaction_log(self):
        """Export transaction log to file"""
        if not hasattr(self, 'monitor_tree') or not self.monitor_tree:
            messagebox.showwarning("Warning", "No transaction data to export.")
            return
        
        f = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt"), ("JSON", "*.json"), ("All Files", "*.*")],
            initialfile=f"transaction_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if not f:
            return
        
        try:
            transactions = []
            for item in self.monitor_tree.get_children():
                values = self.monitor_tree.item(item)['values']
                transactions.append(values)
            
            if f.endswith('.json'):
                data = {
                    'export_time': datetime.now().isoformat(),
                    'database': self.active_connection,
                    'transactions': transactions
                }
                with open(f, 'w', encoding='utf-8') as jsonfile:
                    json.dump(data, jsonfile, indent=2, default=str)
            
            else:
                import csv
                with open(f, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['ID', 'User', 'Start', 'Status', 'Duration', 'Info'])
                    writer.writerows(transactions)
            
            messagebox.showinfo("Success", f"Exported {len(transactions)} transactions to:\n{f}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n\n{str(e)}")
    
    # ==== CONNECTION MANAGEMENT ====
    
    def show_connection_manager(self):
        """Show connection manager dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Connection Manager")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Active Connections", font=('Arial', 12, 'bold')).pack(pady=10)
        
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        scroll_y = ttk.Scrollbar(tree_frame)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree = ttk.Treeview(tree_frame, yscrollcommand=scroll_y.set,
                           columns=('Database', 'Host', 'Port', 'User', 'Status'),
                           show='tree headings')
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.config(command=tree.yview)
        
        tree.column('#0', width=150)
        tree.heading('#0', text='Connection Name')
        tree.column('Database', width=100)
        tree.heading('Database', text='Database')
        tree.column('Host', width=120)
        tree.heading('Host', text='Host')
        tree.column('Port', width=60)
        tree.heading('Port', text='Port')
        tree.column('User', width=100)
        tree.heading('User', text='User')
        tree.column('Status', width=80)
        tree.heading('Status', text='Status')
        
        for conn_name, conn_info in self.connections.items():
            is_active = "🟢 Active" if conn_name == self.active_connection else "⚪ Inactive"
            tree.insert('', tk.END, text=conn_name,
                       values=(conn_info['database'], conn_info['host'], 
                              conn_info['port'], conn_info['username'], is_active))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        def activate_selected():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                conn_name = item['text']
                self.activate_connection(conn_name)
                dialog.destroy()
        
        def disconnect_selected():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                conn_name = item['text']
                if messagebox.askyesno("Confirm", f"Disconnect from {conn_name}?"):
                    self.close_connection(conn_name)
                    tree.delete(selection[0])
        
        ttk.Button(button_frame, text="Activate", command=activate_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Disconnect", command=disconnect_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def activate_connection(self, conn_name):
        """Activate a specific connection"""
        if conn_name in self.connections:
            for i in range(self.db_notebook.index("end")):
                tab_frame = self.db_notebook.nametowidget(self.db_notebook.tabs()[i])
                if hasattr(tab_frame, 'connection_name') and tab_frame.connection_name == conn_name:
                    self.db_notebook.select(i)
                    self.active_connection = conn_name
                    self.active_conn_label.config(text=f"Active: {conn_name}")
                    break
    
    def close_connection(self, conn_name):
        """Close a specific connection"""
        if conn_name in self.connections:
            try:
                conn_info = self.connections[conn_name]
                conn_info['cursor'].close()
                conn_info['connection'].close()
                del self.connections[conn_name]
                
                for i in range(self.db_notebook.index("end")):
                    tab_frame = self.db_notebook.nametowidget(self.db_notebook.tabs()[i])
                    if hasattr(tab_frame, 'connection_name') and tab_frame.connection_name == conn_name:
                        self.db_notebook.forget(i)
                        break
                
                if self.active_connection == conn_name:
                    self.active_connection = None
                    self.active_conn_label.config(text="Active: None")
                    if not self.connections:
                        self.exec_btn.config(state=tk.DISABLED)
                        self.disconn_btn.config(state=tk.DISABLED)
                
                self.update_connection_count()
                self.update_status(f"Disconnected from {conn_name}")
                
            except Exception as e:
                print(f"Error closing connection {conn_name}: {e}")
    
    def disconnect_active(self):
        """Disconnect the active connection"""
        if self.active_connection:
            if messagebox.askyesno("Confirm", f"Disconnect from {self.active_connection}?"):
                self.close_connection(self.active_connection)
        else:
            messagebox.showinfo("Info", "No active connection")
    
    def disconnect_all(self):
        """Disconnect all connections"""
        if not self.connections:
            messagebox.showinfo("Info", "No active connections")
            return
        
        if messagebox.askyesno("Confirm", f"Disconnect all {len(self.connections)} connections?"):
            conn_names = list(self.connections.keys())
            for conn_name in conn_names:
                self.close_connection(conn_name)
    
    def update_connection_count(self):
        """Update connection count display"""
        count = len(self.connections)
        self.conn_count_label.config(text=f"Connections: {count}")
        
        if count == 0 and self.db_notebook.index("end") == 0:
            welcome_tab = ttk.Frame(self.db_notebook)
            self.db_notebook.add(welcome_tab, text="Welcome")
            welcome_text = ttk.Label(welcome_tab, 
                                    text="No connections\n\nClick 'Connect' to add\na database connection",
                                    justify=tk.CENTER)
            welcome_text.pack(expand=True)
    
    # ==== DATABASE COMPARATOR ====
    
    def show_database_comparator(self):
        """Show database comparator dialog"""
        if len(self.connections) < 2:
            messagebox.showwarning("Warning", 
                "Database Comparator requires at least 2 connections.\n\n"
                f"Current connections: {len(self.connections)}\n\n"
                "Please connect to at least 2 databases.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Database Comparator")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Compare Database Structures", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        ttk.Label(main_frame, text="Select two databases to compare:",
                 font=('Arial', 10)).pack(pady=10)
        
        source_frame = ttk.Frame(main_frame)
        source_frame.pack(fill=tk.X, pady=10)
        ttk.Label(source_frame, text="Source Database:", width=20).pack(side=tk.LEFT)
        source_var = tk.StringVar()
        source_combo = ttk.Combobox(source_frame, textvariable=source_var, width=30,
                                    values=list(self.connections.keys()), state='readonly')
        source_combo.pack(side=tk.LEFT, padx=10)
        if self.connections:
            source_combo.current(0)
        
        target_frame = ttk.Frame(main_frame)
        target_frame.pack(fill=tk.X, pady=10)
        ttk.Label(target_frame, text="Target Database:", width=20).pack(side=tk.LEFT)
        target_var = tk.StringVar()
        target_combo = ttk.Combobox(target_frame, textvariable=target_var, width=30,
                                    values=list(self.connections.keys()), state='readonly')
        target_combo.pack(side=tk.LEFT, padx=10)
        if len(self.connections) > 1:
            target_combo.current(1)
        
        options_frame = ttk.LabelFrame(main_frame, text="Comparison Options", padding=10)
        options_frame.pack(fill=tk.X, pady=20)
        
        compare_tables_var = tk.BooleanVar(value=True)
        compare_columns_var = tk.BooleanVar(value=True)
        compare_constraints_var = tk.BooleanVar(value=True)
        compare_indexes_var = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(options_frame, text="Compare Tables", variable=compare_tables_var).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Compare Columns", variable=compare_columns_var).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Compare Constraints (PK, FK, Unique)", 
                       variable=compare_constraints_var).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Compare Indexes", variable=compare_indexes_var).pack(anchor=tk.W)
        
        progress_label = ttk.Label(main_frame, text="", foreground="blue")
        progress_label.pack(pady=10)
        
        def start_comparison():
            source_db = source_var.get()
            target_db = target_var.get()
            
            if not source_db or not target_db:
                messagebox.showerror("Error", "Please select both databases")
                return
            
            if source_db == target_db:
                messagebox.showerror("Error", "Please select different databases")
                return
            
            options = {
                'tables': compare_tables_var.get(),
                'columns': compare_columns_var.get(),
                'constraints': compare_constraints_var.get(),
                'indexes': compare_indexes_var.get()
            }
            
            dialog.destroy()
            self.run_database_comparison(source_db, target_db, options)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="▶ Start Comparison", command=start_comparison).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def show_table_comparator(self):
        """Compare specific tables between two connections"""
        if len(self.connections) < 2:
            messagebox.showwarning("Warning",
                "Table Comparator requires at least 2 connections.\n\n"
                f"Current connections: {len(self.connections)}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Compare Specific Tables")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Compare Specific Tables",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Source
        src_frame = ttk.Frame(main_frame)
        src_frame.pack(fill=tk.X, pady=5)
        ttk.Label(src_frame, text="Source Connection:", width=20).pack(side=tk.LEFT)
        source_var = tk.StringVar()
        source_combo = ttk.Combobox(src_frame, textvariable=source_var, width=30,
                                    values=list(self.connections.keys()), state='readonly')
        source_combo.pack(side=tk.LEFT, padx=10)
        if self.connections:
            source_combo.current(0)

        # Target
        tgt_frame = ttk.Frame(main_frame)
        tgt_frame.pack(fill=tk.X, pady=5)
        ttk.Label(tgt_frame, text="Target Connection:", width=20).pack(side=tk.LEFT)
        target_var = tk.StringVar()
        target_combo = ttk.Combobox(tgt_frame, textvariable=target_var, width=30,
                                    values=list(self.connections.keys()), state='readonly')
        target_combo.pack(side=tk.LEFT, padx=10)
        if len(self.connections) > 1:
            target_combo.current(1)

        # Table name
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.X, pady=10)
        ttk.Label(table_frame, text="Table Name:", width=20).pack(side=tk.LEFT)
        table_entry = ttk.Entry(table_frame, width=32)
        table_entry.pack(side=tk.LEFT, padx=10)

        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Compare", padding=10)
        options_frame.pack(fill=tk.X, pady=10)
        cmp_cols = tk.BooleanVar(value=True)
        cmp_const = tk.BooleanVar(value=True)
        cmp_idx = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Columns", variable=cmp_cols).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Constraints", variable=cmp_const).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Indexes", variable=cmp_idx).pack(anchor=tk.W)

        def run():
            src = source_var.get()
            tgt = target_var.get()
            tbl = table_entry.get().strip()
            if not src or not tgt:
                messagebox.showerror("Error", "Select both connections")
                return
            if src == tgt:
                messagebox.showerror("Error", "Select different connections")
                return
            if not tbl:
                messagebox.showerror("Error", "Enter a table name")
                return
            dialog.destroy()

            results = {
                'source': src, 'target': tgt,
                'timestamp': datetime.now(),
                'tables': {'missing_in_target': [], 'missing_in_source': [], 'common': [tbl]},
                'columns': {}, 'constraints': {}, 'indexes': {}
            }
            try:
                sc = self.connections[src]['cursor']
                tc = self.connections[tgt]['cursor']
                if cmp_cols.get():
                    results['columns'][tbl] = self.compare_table_columns(sc, tc, tbl)
                if cmp_const.get():
                    results['constraints'][tbl] = self.compare_table_constraints(sc, tc, tbl)
                if cmp_idx.get():
                    results['indexes'][tbl] = self.compare_table_indexes(sc, tc, tbl)
                self.last_comparison_result = results
                self.show_comparison_results(results)
            except Exception as e:
                messagebox.showerror("Error", f"Comparison failed:\n\n{str(e)}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="▶ Compare", command=run).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

    def show_last_comparison(self):
        """Show the last comparison result"""
        if not self.last_comparison_result:
            messagebox.showinfo("Info", "No previous comparison available.\n\nRun a comparison first.")
            return
        self.show_comparison_results(self.last_comparison_result)

    def export_comparison(self):
        """Export last comparison to file"""
        if not self.last_comparison_result:
            messagebox.showinfo("Info", "No comparison to export.\n\nRun a comparison first.")
            return
        self.export_comparison_report(self.last_comparison_result)

    def export_comparison_report(self, results):
        """Export comparison report to file"""
        f = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("JSON", "*.json"), ("All Files", "*.*")],
            initialfile=f"comparison_{results['source']}_vs_{results['target']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if not f:
            return
        try:
            if f.endswith('.json'):
                export = {
                    'source': results['source'],
                    'target': results['target'],
                    'timestamp': results['timestamp'].isoformat(),
                    'tables': results['tables'],
                    'columns': {k: v for k, v in results['columns'].items()},
                    'constraints': {k: v for k, v in results['constraints'].items()},
                    'indexes': {k: v for k, v in results['indexes'].items()}
                }
                with open(f, 'w', encoding='utf-8') as fp:
                    json.dump(export, fp, indent=2, default=str)
            else:
                lines = []
                lines.append(f"Database Comparison: {results['source']} vs {results['target']}")
                lines.append(f"Date: {results['timestamp']}")
                lines.append("=" * 60)
                lines.append(f"Missing in target: {results['tables']['missing_in_target']}")
                lines.append(f"Missing in source: {results['tables']['missing_in_source']}")
                lines.append(f"Common tables: {len(results['tables']['common'])}")
                for tbl, diff in results['columns'].items():
                    if any(v for v in diff.values()):
                        lines.append(f"\nTable {tbl}: {diff}")
                with open(f, 'w', encoding='utf-8') as fp:
                    fp.write('\n'.join(lines))
            messagebox.showinfo("Success", f"Report exported to:\n{f}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n\n{str(e)}")

    def generate_sync_script(self, results):
        """Generate SQL sync script from comparison"""
        f = filedialog.asksaveasfilename(
            defaultextension=".sql",
            filetypes=[("SQL", "*.sql"), ("All Files", "*.*")],
            initialfile=f"sync_{results['target']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        )
        if not f:
            return
        try:
            lines = []
            lines.append(f"-- Sync script: {results['source']} -> {results['target']}")
            lines.append(f"-- Generated: {datetime.now()}")
            lines.append("")
            for col_table, col_diff in results.get('columns', {}).items():
                for col in col_diff.get('missing_in_target', []):
                    lines.append(f"-- TODO: ALTER TABLE {col_table} ADD {col} <type>;")
            lines.append("")
            lines.append("-- Review and adjust types before executing.")
            with open(f, 'w', encoding='utf-8') as fp:
                fp.write('\n'.join(lines))
            messagebox.showinfo("Success", f"Sync script saved to:\n{f}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed:\n\n{str(e)}")

    def run_database_comparison(self, source_name, target_name, options):
        """Run database comparison and show results"""
        try:
            self.update_status(f"Comparing {source_name} vs {target_name}...")
            
            source_info = self.connections[source_name]
            target_info = self.connections[target_name]
            
            results = {
                'source': source_name,
                'target': target_name,
                'timestamp': datetime.now(),
                'tables': {'missing_in_target': [], 'missing_in_source': [], 'common': []},
                'columns': {},
                'constraints': {},
                'indexes': {}
            }
            
            if options['tables']:
                source_cursor = source_info['cursor']
                target_cursor = target_info['cursor']
                
                source_cursor.execute("SELECT tabname FROM systables WHERE tabtype='T' AND tabid>99 ORDER BY tabname")
                source_tables = set([row[0] for row in source_cursor.fetchall()])
                
                target_cursor.execute("SELECT tabname FROM systables WHERE tabtype='T' AND tabid>99 ORDER BY tabname")
                target_tables = set([row[0] for row in target_cursor.fetchall()])
                
                results['tables']['missing_in_target'] = sorted(source_tables - target_tables)
                results['tables']['missing_in_source'] = sorted(target_tables - source_tables)
                results['tables']['common'] = sorted(source_tables & target_tables)
                
                if options['columns']:
                    for table in results['tables']['common']:
                        results['columns'][table] = self.compare_table_columns(
                            source_cursor, target_cursor, table
                        )
                
                if options['constraints']:
                    for table in results['tables']['common']:
                        results['constraints'][table] = self.compare_table_constraints(
                            source_cursor, target_cursor, table
                        )
                
                if options['indexes']:
                    for table in results['tables']['common']:
                        results['indexes'][table] = self.compare_table_indexes(
                            source_cursor, target_cursor, table
                        )
            
            self.last_comparison_result = results
            self.show_comparison_results(results)
            self.update_status("Comparison complete")
            
        except Exception as e:
            messagebox.showerror("Error", f"Comparison failed:\n\n{str(e)}")
            self.update_status("Comparison failed")
    
    def compare_table_columns(self, source_cursor, target_cursor, table_name):
        """Compare columns between two tables"""
        result = {
            'missing_in_target': [],
            'missing_in_source': [],
            'type_mismatch': [],
            'nullable_mismatch': []
        }
        
        try:
            source_cursor.execute("SELECT tabid FROM systables WHERE tabname=?", [table_name])
            source_tabid = source_cursor.fetchone()
            if not source_tabid:
                return result
            source_tabid = source_tabid[0]
            
            target_cursor.execute("SELECT tabid FROM systables WHERE tabname=?", [table_name])
            target_tabid = target_cursor.fetchone()
            if not target_tabid:
                return result
            target_tabid = target_tabid[0]
            
            source_cursor.execute("""
                SELECT colname, coltype, collength
                FROM syscolumns
                WHERE tabid=?
                ORDER BY colno
            """, [source_tabid])
            source_cols = {row[0]: (row[1], row[2]) for row in source_cursor.fetchall()}
            
            target_cursor.execute("""
                SELECT colname, coltype, collength
                FROM syscolumns
                WHERE tabid=?
                ORDER BY colno
            """, [target_tabid])
            target_cols = {row[0]: (row[1], row[2]) for row in target_cursor.fetchall()}
            
            source_col_names = set(source_cols.keys())
            target_col_names = set(target_cols.keys())
            
            result['missing_in_target'] = sorted(source_col_names - target_col_names)
            result['missing_in_source'] = sorted(target_col_names - source_col_names)
            
            common_cols = source_col_names & target_col_names
            for col in common_cols:
                source_type, source_len = source_cols[col]
                target_type, target_len = target_cols[col]
                
                source_base_type = source_type % 256
                target_base_type = target_type % 256
                
                if source_base_type != target_base_type or source_len != target_len:
                    result['type_mismatch'].append({
                        'column': col,
                        'source_type': self.get_informix_type_name(source_type, source_len),
                        'target_type': self.get_informix_type_name(target_type, target_len)
                    })
                
                source_nullable = source_type < 256
                target_nullable = target_type < 256
                
                if source_nullable != target_nullable:
                    result['nullable_mismatch'].append({
                        'column': col,
                        'source_nullable': source_nullable,
                        'target_nullable': target_nullable
                    })
        
        except Exception as e:
            print(f"Error comparing columns for {table_name}: {e}")
        
        return result
    
    def compare_table_constraints(self, source_cursor, target_cursor, table_name):
        """Compare constraints between two tables"""
        result = {
            'pk_mismatch': False,
            'missing_fk_in_target': [],
            'missing_fk_in_source': [],
            'fk_differences': []
        }
        
        try:
            source_cursor.execute("SELECT tabid FROM systables WHERE tabname=?", [table_name])
            source_tabid_row = source_cursor.fetchone()
            if not source_tabid_row:
                return result
            source_tabid = source_tabid_row[0]
            
            target_cursor.execute("SELECT tabid FROM systables WHERE tabname=?", [table_name])
            target_tabid_row = target_cursor.fetchone()
            if not target_tabid_row:
                return result
            target_tabid = target_tabid_row[0]
            
            source_cursor.execute("""
                SELECT i.idxname, i.part1, i.part2, i.part3, i.part4
                FROM sysindexes i, sysconstraints sc
                WHERE i.tabid=? AND sc.tabid=i.tabid AND sc.idxname=i.idxname AND sc.constrtype='P'
            """, [source_tabid])
            source_pk = source_cursor.fetchall()
            
            target_cursor.execute("""
                SELECT i.idxname, i.part1, i.part2, i.part3, i.part4
                FROM sysindexes i, sysconstraints sc
                WHERE i.tabid=? AND sc.tabid=i.tabid AND sc.idxname=i.idxname AND sc.constrtype='P'
            """, [target_tabid])
            target_pk = target_cursor.fetchall()
            
            if source_pk != target_pk:
                result['pk_mismatch'] = True
            
            source_cursor.execute("""
                SELECT sc.constrname, pt.tabname
                FROM sysconstraints sc, sysreferences sr, systables pt
                WHERE sc.constrid = sr.constrid
                AND sr.ptabid = pt.tabid
                AND sc.tabid = ?
                AND sc.constrtype = 'R'
            """, [source_tabid])
            source_fks = {row[0]: row[1] for row in source_cursor.fetchall()}
            
            target_cursor.execute("""
                SELECT sc.constrname, pt.tabname
                FROM sysconstraints sc, sysreferences sr, systables pt
                WHERE sc.constrid = sr.constrid
                AND sr.ptabid = pt.tabid
                AND sc.tabid = ?
                AND sc.constrtype = 'R'
            """, [target_tabid])
            target_fks = {row[0]: row[1] for row in target_cursor.fetchall()}
            
            source_fk_names = set(source_fks.keys())
            target_fk_names = set(target_fks.keys())
            
            result['missing_fk_in_target'] = sorted(source_fk_names - target_fk_names)
            result['missing_fk_in_source'] = sorted(target_fk_names - source_fk_names)
            
            common_fks = source_fk_names & target_fk_names
            for fk in common_fks:
                if source_fks[fk] != target_fks[fk]:
                    result['fk_differences'].append({
                        'fk_name': fk,
                        'source_ref': source_fks[fk],
                        'target_ref': target_fks[fk]
                    })
        
        except Exception as e:
            print(f"Error comparing constraints for {table_name}: {e}")
        
        return result
    
    def compare_table_indexes(self, source_cursor, target_cursor, table_name):
        """Compare indexes between two tables"""
        result = {
            'missing_in_target': [],
            'missing_in_source': [],
            'type_mismatch': []
        }
        
        try:
            source_cursor.execute("SELECT tabid FROM systables WHERE tabname=?", [table_name])
            source_tabid_row = source_cursor.fetchone()
            if not source_tabid_row:
                return result
            source_tabid = source_tabid_row[0]
            
            target_cursor.execute("SELECT tabid FROM systables WHERE tabname=?", [table_name])
            target_tabid_row = target_cursor.fetchone()
            if not target_tabid_row:
                return result
            target_tabid = target_tabid_row[0]
            
            source_cursor.execute("""
                SELECT i.idxname, i.idxtype
                FROM sysindexes i
                WHERE i.tabid=?
                AND i.idxname NOT IN (SELECT idxname FROM sysconstraints WHERE tabid=?)
            """, [source_tabid, source_tabid])
            source_indexes = {row[0]: row[1] for row in source_cursor.fetchall()}
            
            target_cursor.execute("""
                SELECT i.idxname, i.idxtype
                FROM sysindexes i
                WHERE i.tabid=?
                AND i.idxname NOT IN (SELECT idxname FROM sysconstraints WHERE tabid=?)
            """, [target_tabid, target_tabid])
            target_indexes = {row[0]: row[1] for row in target_cursor.fetchall()}
            
            source_idx_names = set(source_indexes.keys())
            target_idx_names = set(target_indexes.keys())
            
            result['missing_in_target'] = sorted(source_idx_names - target_idx_names)
            result['missing_in_source'] = sorted(target_idx_names - source_idx_names)
            
            common_indexes = source_idx_names & target_idx_names
            for idx in common_indexes:
                if source_indexes[idx] != target_indexes[idx]:
                    result['type_mismatch'].append({
                        'index': idx,
                        'source_type': source_indexes[idx],
                        'target_type': target_indexes[idx]
                    })
        
        except Exception as e:
            print(f"Error comparing indexes for {table_name}: {e}")
        
        return result
    
    def show_comparison_results(self, results):
        """Show comparison results in a new window"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Comparison: {results['source']} vs {results['target']}")
        dialog.geometry("1200x800")
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header = f"Database Comparison Results\n{results['source']} ➔ {results['target']}\n{results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
        ttk.Label(main_frame, text=header, font=('Arial', 12, 'bold')).pack(pady=10)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.create_tables_comparison_tab(notebook, results)
        self.create_columns_comparison_tab(notebook, results)
        self.create_constraints_comparison_tab(notebook, results)
        self.create_indexes_comparison_tab(notebook, results)
        self.create_summary_report_tab(notebook, results)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="💾 Export Report", 
                  command=lambda: self.export_comparison_report(results)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📋 Generate Sync Script", 
                  command=lambda: self.generate_sync_script(results)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def create_tables_comparison_tab(self, notebook, results):
        """Create tables comparison tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="📊 Tables")
        
        text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=('Consolas', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        content = []
        content.append("="*80)
        content.append("TABLES COMPARISON")
        content.append("="*80)
        content.append("")
        
        content.append(f"Total tables in {results['source']}: {len(results['tables']['common']) + len(results['tables']['missing_in_target'])}")
        content.append(f"Total tables in {results['target']}: {len(results['tables']['common']) + len(results['tables']['missing_in_source'])}")
        content.append(f"Common tables: {len(results['tables']['common'])}")
        content.append("")
        
        if results['tables']['missing_in_target']:
            content.append(f"⚠️  MISSING IN {results['target']} ({len(results['tables']['missing_in_target'])} tables):")
            content.append("-"*80)
            for table in results['tables']['missing_in_target']:
                content.append(f"  ❌ {table}")
            content.append("")
        
        if results['tables']['missing_in_source']:
            content.append(f"⚠️  MISSING IN {results['source']} ({len(results['tables']['missing_in_source'])} tables):")
            content.append("-"*80)
            for table in results['tables']['missing_in_source']:
                content.append(f"  ❌ {table}")
            content.append("")
        
        if results['tables']['common']:
            content.append(f"✓ COMMON TABLES ({len(results['tables']['common'])} tables):")
            content.append("-"*80)
            for table in results['tables']['common']:
                content.append(f"  ✓ {table}")
            content.append("")
        
        text.insert('1.0', '\n'.join(content))
        text.config(state=tk.DISABLED)
    
    def create_columns_comparison_tab(self, notebook, results):
        """Create columns comparison tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="📋 Columns")
        
        text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=('Consolas', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        content = []
        content.append("="*80)
        content.append("COLUMNS COMPARISON")
        content.append("="*80)
        content.append("")
        
        has_differences = False
        
        for table, col_diff in results['columns'].items():
            table_has_diff = (col_diff['missing_in_target'] or col_diff['missing_in_source'] or 
                            col_diff['type_mismatch'] or col_diff['nullable_mismatch'])
            
            if table_has_diff:
                has_differences = True
                content.append(f"📊 TABLE: {table}")
                content.append("-"*80)
                
                if col_diff['missing_in_target']:
                    content.append(f"  ⚠️  Missing in {results['target']}:")
                    for col in col_diff['missing_in_target']:
                        content.append(f"    ❌ {col}")
                
                if col_diff['missing_in_source']:
                    content.append(f"  ⚠️  Missing in {results['source']}:")
                    for col in col_diff['missing_in_source']:
                        content.append(f"    ❌ {col}")
                
                if col_diff['type_mismatch']:
                    content.append(f"  ⚠️  Type mismatches:")
                    for mismatch in col_diff['type_mismatch']:
                        content.append(f"    🔄 {mismatch['column']}")
                        content.append(f"       {results['source']}: {mismatch['source_type']}")
                        content.append(f"       {results['target']}: {mismatch['target_type']}")
                
                if col_diff['nullable_mismatch']:
                    content.append(f"  ⚠️  Nullable mismatches:")
                    for mismatch in col_diff['nullable_mismatch']:
                        src_null = "NULL" if mismatch['source_nullable'] else "NOT NULL"
                        tgt_null = "NULL" if mismatch['target_nullable'] else "NOT NULL"
                        content.append(f"    🔄 {mismatch['column']}: {results['source']}={src_null}, {results['target']}={tgt_null}")
                
                content.append("")
        
        if not has_differences:
            content.append("✓ No column differences found in common tables")
        
        text.insert('1.0', '\n'.join(content))
        text.config(state=tk.DISABLED)
    
    def create_constraints_comparison_tab(self, notebook, results):
        """Create constraints comparison tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="🔒 Constraints")
        
        text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=('Consolas', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        content = []
        content.append("="*80)
        content.append("CONSTRAINTS COMPARISON")
        content.append("="*80)
        content.append("")
        
        has_differences = False
        
        for table, const_diff in results['constraints'].items():
            table_has_diff = (const_diff['pk_mismatch'] or const_diff['missing_fk_in_target'] or 
                            const_diff['missing_fk_in_source'] or const_diff['fk_differences'])
            
            if table_has_diff:
                has_differences = True
                content.append(f"📊 TABLE: {table}")
                content.append("-"*80)
                
                if const_diff['pk_mismatch']:
                    content.append(f"  ⚠️  PRIMARY KEY MISMATCH")
                
                if const_diff['missing_fk_in_target']:
                    content.append(f"  ⚠️  Foreign Keys missing in {results['target']}:")
                    for fk in const_diff['missing_fk_in_target']:
                        content.append(f"    ❌ {fk}")
                
                if const_diff['missing_fk_in_source']:
                    content.append(f"  ⚠️  Foreign Keys missing in {results['source']}:")
                    for fk in const_diff['missing_fk_in_source']:
                        content.append(f"    ❌ {fk}")
                
                if const_diff['fk_differences']:
                    content.append(f"  ⚠️  Foreign Key differences:")
                    for diff in const_diff['fk_differences']:
                        content.append(f"    🔄 {diff['fk_name']}")
                        content.append(f"       {results['source']} → {diff['source_ref']}")
                        content.append(f"       {results['target']} → {diff['target_ref']}")
                
                content.append("")
        
        if not has_differences:
            content.append("✓ No constraint differences found in common tables")
        
        text.insert('1.0', '\n'.join(content))
        text.config(state=tk.DISABLED)
    
    def create_indexes_comparison_tab(self, notebook, results):
        """Create indexes comparison tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="🔍 Indexes")
        
        text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=('Consolas', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        content = []
        content.append("="*80)
        content.append("INDEXES COMPARISON")
        content.append("="*80)
        content.append("")
        
        has_differences = False
        
        for table, idx_diff in results['indexes'].items():
            table_has_diff = (idx_diff['missing_in_target'] or idx_diff['missing_in_source'] or 
                            idx_diff['type_mismatch'])
            
            if table_has_diff:
                has_differences = True
                content.append(f"📊 TABLE: {table}")
                content.append("-"*80)
                
                if idx_diff['missing_in_target']:
                    content.append(f"  ⚠️  Indexes missing in {results['target']}:")
                    for idx in idx_diff['missing_in_target']:
                        content.append(f"    ❌ {idx}")
                
                if idx_diff['missing_in_source']:
                    content.append(f"  ⚠️  Indexes missing in {results['source']}:")
                    for idx in idx_diff['missing_in_source']:
                        content.append(f"    ❌ {idx}")
                
                if idx_diff['type_mismatch']:
                    content.append(f"  ⚠️  Index type mismatches:")
                    for mismatch in idx_diff['type_mismatch']:
                        content.append(f"    🔄 {mismatch['index']}")
                        content.append(f"       {results['source']}: {mismatch['source_type']}")
                        content.append(f"       {results['target']}: {mismatch['target_type']}")
                
                content.append("")
        
        if not has_differences:
            content.append("✓ No index differences found in common tables")
        
        text.insert('1.0', '\n'.join(content))
        text.config(state=tk.DISABLED)
    
    def create_summary_report_tab(self, notebook, results):
        """Create summary report tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="📈 Summary")
        
        text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=('Consolas', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        content = []
        content.append("="*80)
        content.append("DATABASE COMPARISON SUMMARY REPORT")
        content.append("="*80)
        content.append("")
        content.append(f"Source Database: {results['source']}")
        content.append(f"Target Database: {results['target']}")
        content.append(f"Comparison Date: {results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("")
        content.append("="*80)
        content.append("OVERALL STATISTICS")
        content.append("="*80)
        content.append("")
        
        total_issues = 0
        content.append("📊 TABLES:")
        tables_missing_target = len(results['tables']['missing_in_target'])
        tables_missing_source = len(results['tables']['missing_in_source'])
        content.append(f"  Tables missing in target: {tables_missing_target}")
        content.append(f"  Tables missing in source: {tables_missing_source}")
        content.append(f"  Common tables: {len(results['tables']['common'])}")
        total_issues += tables_missing_target + tables_missing_source
        content.append("")
        
        content.append("📋 COLUMNS:")
        cols_missing_target = sum(len(d['missing_in_target']) for d in results['columns'].values())
        cols_missing_source = sum(len(d['missing_in_source']) for d in results['columns'].values())
        type_mismatches = sum(len(d['type_mismatch']) for d in results['columns'].values())
        null_mismatches = sum(len(d['nullable_mismatch']) for d in results['columns'].values())
        content.append(f"  Columns missing in target: {cols_missing_target}")
        content.append(f"  Columns missing in source: {cols_missing_source}")
        content.append(f"  Type mismatches: {type_mismatches}")
        content.append(f"  Nullable mismatches: {null_mismatches}")
        total_issues += cols_missing_target + cols_missing_source + type_mismatches + null_mismatches
        content.append("")
        
        content.append("🔒 CONSTRAINTS:")
        pk_mismatches = sum(1 for d in results['constraints'].values() if d['pk_mismatch'])
        fk_missing_target = sum(len(d['missing_fk_in_target']) for d in results['constraints'].values())
        fk_missing_source = sum(len(d['missing_fk_in_source']) for d in results['constraints'].values())
        fk_differences = sum(len(d['fk_differences']) for d in results['constraints'].values())
        content.append(f"  Primary key mismatches: {pk_mismatches}")
        content.append(f"  Foreign keys missing in target: {fk_missing_target}")
        content.append(f"  Foreign keys missing in source: {fk_missing_source}")
        content.append(f"  Foreign key differences: {fk_differences}")
        total_issues += pk_mismatches + fk_missing_target + fk_missing_source + fk_differences
        content.append("")
        
        content.append("🔍 INDEXES:")
        idx_missing_target = sum(len(d['missing_in_target']) for d in results['indexes'].values())
        idx_missing_source = sum(len(d['missing_in_source']) for d in results['indexes'].values())
        idx_type_mismatch = sum(len(d['type_mismatch']) for d in results['indexes'].values())
        content.append(f"  Indexes missing in target: {idx_missing_target}")
        content.append(f"  Indexes missing in source: {idx_missing_source}")
        content.append(f"  Index type mismatches: {idx_type_mismatch}")
        total_issues += idx_missing_target + idx_missing_source + idx_type_mismatch
        content.append("")
        
        content.append("="*80)
        content.append(f"TOTAL ISSUES FOUND: {total_issues}")
        content.append("="*80)
        content.append("")
        
        if total_issues == 0:
            content.append("✅ DATABASES ARE IDENTICAL!")
        else:
            content.append("⚠️  DATABASES HAVE DIFFERENCES")
            content.append("")
            content.append("RECOMMENDATIONS:")
            if tables_missing_target > 0:
                content.append(f"  • Create {tables_missing_target} missing tables in {results['target']}")
            if cols_missing_target > 0:
                content.append(f"  • Add {cols_missing_target} missing columns in {results['target']}")
            if fk_missing_target > 0:
                content.append(f"  • Create {fk_missing_target} missing foreign keys in {results['target']}")
            if idx_missing_target > 0:
                content.append(f"  • Create {idx_missing_target} missing indexes in {results['target']}")
            if type_mismatches > 0:
                content.append(f"  • Review and fix {type_mismatches} column type mismatches")
        
        text.insert('1.0', '\n'.join(content))
        text.config(state=tk.DISABLED)
    
    # ==== FK RELATIONSHIP VISUALIZER ====
    
    def show_all_fk_relationships(self):
        """Show all FK relationships in a graphical workflow view"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection.\n\nConnect to a database first.")
            return
        
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            self.update_status("Loading FK relationships...")
            
            cursor.execute("""
                SELECT 
                    t1.tabname as child_table,
                    t2.tabname as parent_table,
                    sc.constrname as fk_name
                FROM sysconstraints sc
                JOIN sysreferences sr ON sc.constrid = sr.constrid
                JOIN systables t1 ON sc.tabid = t1.tabid
                JOIN systables t2 ON sr.ptabid = t2.tabid
                WHERE sc.constrtype = 'R'
                ORDER BY t1.tabname, t2.tabname
            """)
            
            relationships = cursor.fetchall()
            
            if not relationships:
                messagebox.showinfo("No FK Relationships", "No foreign key relationships found.")
                return
            
            # Show in a dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"FK Relationships - {self.active_connection}")
            dialog.geometry("1000x700")
            
            main_frame = ttk.Frame(dialog, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(main_frame, text=f"Foreign Key Relationships - {self.active_connection}", 
                     font=('Arial', 14, 'bold')).pack(pady=10)
            
            # Canvas for drawing
            canvas_frame = ttk.Frame(main_frame)
            canvas_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            
            canvas_scroll_y = ttk.Scrollbar(canvas_frame)
            canvas_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
            
            canvas_scroll_x = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
            canvas_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
            
            canvas = tk.Canvas(canvas_frame, bg='white',
                             yscrollcommand=canvas_scroll_y.set,
                             xscrollcommand=canvas_scroll_x.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            canvas_scroll_y.config(command=canvas.yview)
            canvas_scroll_x.config(command=canvas.xview)
            
            # Build graph data
            tables = set()
            edges = []
            for child, parent, fk_name in relationships:
                tables.add(child)
                tables.add(parent)
                edges.append((child, parent, fk_name))
            
            tables = sorted(tables)
            
            # Simple grid layout
            cols = 4
            cell_w = 200
            cell_h = 80
            pad = 50
            
            positions = {}
            for i, table in enumerate(tables):
                row = i // cols
                col = i % cols
                x = pad + col * cell_w
                y = pad + row * cell_h
                positions[table] = (x + cell_w // 2, y + cell_h // 2)
                
                # Draw table box
                canvas.create_rectangle(x + 10, y + 10, x + cell_w - 10, y + cell_h - 10,
                                       fill='lightblue', outline='navy', width=2)
                canvas.create_text(x + cell_w // 2, y + cell_h // 2, 
                                  text=table, font=('Arial', 8, 'bold'))
            
            # Draw edges
            for child, parent, fk_name in edges:
                if child in positions and parent in positions:
                    x1, y1 = positions[child]
                    x2, y2 = positions[parent]
                    canvas.create_line(x1, y1, x2, y2, fill='red', width=1, arrow=tk.LAST)
            
            # Set scroll region
            max_row = (len(tables) - 1) // cols
            canvas.config(scrollregion=(0, 0, pad * 2 + cols * cell_w, pad * 2 + (max_row + 1) * cell_h))
            
            # Info
            ttk.Label(main_frame, text=f"Tables: {len(tables)} | Relationships: {len(edges)}", 
                     foreground="blue").pack(pady=5)
            
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
            
            self.update_status(f"Loaded {len(edges)} FK relationships for {len(tables)} tables")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load FK relationships:\n\n{str(e)}")
    
    def show_table_fk_relationships(self):
        """Show FK relationships for a specific table"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection.\n\nConnect to a database first.")
            return
        
        table_name = tk.simpledialog.askstring("Table FK Relationships", "Enter table name:") if hasattr(tk, 'simpledialog') else None
        if not table_name:
            # Fallback dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Enter Table Name")
            dialog.geometry("300x120")
            dialog.transient(self.root)
            dialog.grab_set()
            
            frame = ttk.Frame(dialog, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(frame, text="Table name:").pack(pady=5)
            entry = ttk.Entry(frame, width=30)
            entry.pack(pady=5)
            entry.focus()
            
            result = [None]
            
            def ok():
                result[0] = entry.get().strip()
                dialog.destroy()
            
            ttk.Button(frame, text="OK", command=ok).pack(pady=5)
            entry.bind('<Return>', lambda e: ok())
            
            dialog.wait_window()
            table_name = result[0]
        
        if not table_name:
            return
        
        messagebox.showinfo("Info", f"FK relationships for '{table_name}' - use 'Show All Relationships' and look for this table.")
    
    def show_fk_statistics(self):
        """Show FK relationship statistics"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection.")
            return
        
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            cursor.execute("""
                SELECT COUNT(*) FROM sysconstraints WHERE constrtype = 'R'
            """)
            fk_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM sysconstraints WHERE constrtype = 'P'
            """)
            pk_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM sysconstraints WHERE constrtype = 'U'
            """)
            unique_count = cursor.fetchone()[0]
            
            messagebox.showinfo("FK Statistics", 
                              f"Database: {self.active_connection}\n\n"
                              f"Primary Keys: {pk_count}\n"
                              f"Foreign Keys: {fk_count}\n"
                              f"Unique Constraints: {unique_count}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get statistics:\n\n{str(e)}")
    
    def export_fk_graph(self):
        """Export FK graph"""
        messagebox.showinfo("Info", "Use 'Show All Relationships' to view the graph, then take a screenshot or export data.")
    
    def print_fk_graph(self):
        """Print FK graph"""
        messagebox.showinfo("Info", "Use 'Show All Relationships' to view the graph, then use system print screen.")
    
    # ==== TREE NAVIGATION ====
    
    def on_tree_expand(self, event):
        """Load table details when node is expanded"""
        tree = None
        try:
            current_tab = self.db_notebook.select()
            if current_tab:
                tab_frame = self.db_notebook.nametowidget(current_tab)
                if hasattr(tab_frame, 'db_tree'):
                    tree = tab_frame.db_tree
                    conn_name = tab_frame.connection_name
                else:
                    return
            else:
                return
        except:
            return
        
        item = tree.focus()
        if not item:
            return
        
        vals = tree.item(item, 'values')
        if not vals or vals[0] != 'table':
            return
        
        # Check if already loaded (first child is "Loading...")
        children = tree.get_children(item)
        if children and tree.item(children[0], 'text') == 'Loading...':
            # Remove placeholder
            tree.delete(children[0])
            
            table_name = vals[1]
            tabid = vals[2]
            
            try:
                conn_info = self.connections[conn_name]
                cursor = conn_info['cursor']
                
                # Load columns
                columns_node = tree.insert(item, tk.END, text='📋 Columns')
                self.load_table_columns(cursor, tree, columns_node, table_name, tabid)
                
                # Load constraints
                constraints_node = tree.insert(item, tk.END, text='🔒 Constraints')
                self.load_table_constraints(cursor, tree, constraints_node, table_name, tabid)
                
                # Load indexes
                indexes_node = tree.insert(item, tk.END, text='🔍 Indexes')
                self.load_table_indexes(cursor, tree, indexes_node, table_name, tabid)
                
            except Exception as e:
                print(f"Error loading table details: {e}")
    
    def load_table_columns(self, cursor, tree, parent_node, table_name, tabid):
        """Load columns for a table"""
        try:
            cursor.execute("""
                SELECT colname, coltype, collength, colno
                FROM syscolumns
                WHERE tabid=?
                ORDER BY colno
            """, [tabid])
            
            columns = cursor.fetchall()
            
            for col_name, col_type, col_length, col_no in columns:
                type_name = self.get_informix_type_name(col_type, col_length)
                nullable = "NULL" if col_type < 256 else "NOT NULL"
                
                tree.insert(parent_node, tk.END, 
                          text=f'  {col_name} ({type_name}) {nullable}',
                          values=('column', col_name, table_name))
                
        except Exception as e:
            print(f"Error loading columns for {table_name}: {e}")
    
    def load_table_constraints(self, cursor, tree, parent_node, table_name, tabid):
        """Load constraints for a table"""
        try:
            cursor.execute("""
                SELECT constrname, constrtype
                FROM sysconstraints
                WHERE tabid=?
                ORDER BY constrtype, constrname
            """, [tabid])
            
            constraints = cursor.fetchall()
            
            type_map = {'P': 'PK', 'R': 'FK', 'U': 'UNIQUE', 'C': 'CHECK'}
            
            for const_name, const_type in constraints:
                type_label = type_map.get(const_type, const_type)
                tree.insert(parent_node, tk.END, 
                          text=f'  [{type_label}] {const_name}',
                          values=('constraint', const_name, table_name))
                
        except Exception as e:
            print(f"Error loading constraints for {table_name}: {e}")
    
    def load_table_indexes(self, cursor, tree, parent_node, table_name, tabid):
        """Load indexes for a table"""
        try:
            cursor.execute("""
                SELECT idxname, idxtype
                FROM sysindexes
                WHERE tabid=?
                ORDER BY idxname
            """, [tabid])
            
            indexes = cursor.fetchall()
            
            for idx_name, idx_type in indexes:
                type_label = "UNIQUE" if idx_type == 'U' else "INDEX"
                tree.insert(parent_node, tk.END, 
                          text=f'  [{type_label}] {idx_name}',
                          values=('index', idx_name, table_name))
                
        except Exception as e:
            print(f"Error loading indexes for {table_name}: {e}")
    
    def on_tree_double_click(self, e):
        """Handle double-click on tree items"""
        tree = None
        try:
            current_tab = self.db_notebook.select()
            if current_tab:
                tab_frame = self.db_notebook.nametowidget(current_tab)
                if hasattr(tab_frame, 'db_tree'):
                    tree = tab_frame.db_tree
                    self.current_connection_name = tab_frame.connection_name
                else:
                    return
            else:
                return
        except:
            return
        
        item = tree.selection()
        if not item:
            return
        
        vals = tree.item(item[0], 'values')
        if not vals:
            return
        
        if vals[0] == 'table':
            table_name = vals[1]
            limit = self.limit_var.get()
            
            tab = self.query_notebook.nametowidget(self.query_notebook.select())
            tab.sql_editor.delete('1.0', tk.END)
            
            if limit == "ALL":
                query = f"SELECT * FROM {table_name};"
            else:
                query = f"SELECT FIRST {limit} * FROM {table_name};"
            
            tab.sql_editor.insert('1.0', query)
        
        elif vals[0] == 'column':
            col_name = vals[1]
            table_name = vals[2]
            
            tab = self.query_notebook.nametowidget(self.query_notebook.select())
            tab.sql_editor.delete('1.0', tk.END)
            
            query = f"SELECT {col_name} FROM {table_name};"
            tab.sql_editor.insert('1.0', query)
    
    def on_tree_right_click(self, event):
        """Show context menu on right-click"""
        tree = None
        try:
            current_tab = self.db_notebook.select()
            if current_tab:
                tab_frame = self.db_notebook.nametowidget(current_tab)
                if hasattr(tab_frame, 'db_tree'):
                    tree = tab_frame.db_tree
                    self.current_connection_name = tab_frame.connection_name
                else:
                    return
            else:
                return
        except:
            return
        
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            vals = tree.item(item, 'values')
            
            menu = tk.Menu(self.root, tearoff=0)
            
            if vals and vals[0] == 'table':
                table_name = vals[1]
                menu.add_command(label=f"📊 Query Table", 
                               command=lambda: self.query_table(table_name, tree))
                menu.add_command(label=f"🔢 Count Rows", 
                               command=lambda: self.count_table_rows(table_name))
                menu.add_separator()
                menu.add_command(label=f"📋 Copy Table Name", 
                               command=lambda: self.copy_to_clipboard(table_name))
                menu.add_command(label=f"🔄 Refresh", 
                               command=lambda: self.refresh_current_tree())
            
            elif vals and vals[0] == 'column':
                col_name = vals[1]
                table_name = vals[2]
                menu.add_command(label=f"📊 Query Column", 
                               command=lambda: self.query_column(col_name, table_name))
                menu.add_command(label=f"📋 Copy Column Name", 
                               command=lambda: self.copy_to_clipboard(col_name))
            
            else:
                menu.add_command(label="🔄 Refresh", 
                               command=lambda: self.refresh_current_tree())
            
            menu.post(event.x_root, event.y_root)
    
    # ==== QUERY EXECUTION ====
    
    def execute_query(self):
        """Execute SQL query on active connection"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection.\n\nConnect to a database first.")
            return
        
        conn_info = self.connections[self.active_connection]
        cursor = conn_info['cursor']
        connection = conn_info['connection']
        
        tab = self.query_notebook.nametowidget(self.query_notebook.select())
        sql = tab.sql_editor.get('1.0', tk.END).strip()
        
        if not sql:
            return
        
        self.current_offset = 0
        self.last_query = sql
        
        try:
            start = datetime.now()
            
            if sql.strip().upper().startswith('SELECT'):
                limit_str = self.limit_var.get()
                if limit_str == "ALL":
                    modified_sql = sql
                else:
                    fetch_limit = int(limit_str)
                    if 'FIRST' not in sql.upper():
                        modified_sql = sql[:6] + f' FIRST {fetch_limit}' + sql[6:]
                    else:
                        modified_sql = sql
                
                self.update_status(f"Executing on {self.active_connection}...")
                cursor.execute(modified_sql)
                
                rows = cursor.fetchall()
                cols = [d[0] for d in cursor.description] if cursor.description else []
                
                self.display_results(cols, rows, append=False)
                
                elapsed = (datetime.now() - start).total_seconds()
                self.update_status(f"Query OK - {len(rows)} rows - {elapsed:.2f}s")
                self.rows_label.config(text=f"Rows: {len(rows)}")
                self.time_label.config(text=f"Time: {elapsed:.2f}s")
                self.export_btn.config(state=tk.NORMAL)
            else:
                cursor.execute(sql)
                connection.commit()
                elapsed = (datetime.now() - start).total_seconds()
                self.update_status(f"Query executed - {elapsed:.2f}s")
                self.time_label.config(text=f"Time: {elapsed:.2f}s")
                
        except Exception as e:
            self.update_status("Query failed")
            messagebox.showerror("Error", f"Query failed:\n\n{str(e)}")
    
    def display_results(self, cols, rows, append=False):
        """Display query results"""
        tab = self.results_notebook.nametowidget(self.results_notebook.tabs()[0])
        tree = tab.results_tree
        
        if not append:
            tree.delete(*tree.get_children())
            tree['columns'] = cols
            tree.column('#0', width=0, stretch=tk.NO)
            
            for col in cols:
                tree.column(col, width=150)
                tree.heading(col, text=col)
        
        for row in rows:
            tree.insert('', tk.END, values=[str(v) if v is not None else 'NULL' for v in row])
        
        if PANDAS_AVAILABLE:
            if append and hasattr(tab, 'results_data') and tab.results_data is not None:
                new_df = pd.DataFrame(rows, columns=cols)
                tab.results_data = pd.concat([tab.results_data, new_df], ignore_index=True)
            else:
                tab.results_data = pd.DataFrame(rows, columns=cols)
    
    def get_informix_type_name(self, col_type, col_length):
        """Convert Informix type code to type name"""
        base_type = col_type % 256 if col_type >= 256 else col_type
        
        type_map = {
            0: 'CHAR', 1: 'SMALLINT', 2: 'INTEGER', 3: 'FLOAT',
            4: 'SMALLFLOAT', 5: 'DECIMAL', 6: 'SERIAL', 7: 'DATE',
            8: 'MONEY', 9: 'NULL', 10: 'DATETIME', 11: 'BYTE',
            12: 'TEXT', 13: 'VARCHAR', 14: 'INTERVAL', 15: 'NCHAR',
            16: 'NVARCHAR', 17: 'INT8', 18: 'SERIAL8', 40: 'LVARCHAR',
            41: 'BLOB', 43: 'CLOB', 45: 'BOOLEAN', 52: 'BIGINT', 53: 'BIGSERIAL'
        }
        
        type_name = type_map.get(base_type, f'TYPE({base_type})')
        
        if base_type in [0, 13, 15, 16, 40]:
            return f'{type_name}({col_length})'
        
        return type_name
    
    # ==== UTILITY METHODS ====
    
    def query_table(self, table_name, tree=None):
        """Generate SELECT query for table"""
        limit = self.limit_var.get()
        tab = self.query_notebook.nametowidget(self.query_notebook.select())
        tab.sql_editor.delete('1.0', tk.END)
        
        if limit == "ALL":
            query = f"SELECT * FROM {table_name};"
        else:
            query = f"SELECT FIRST {limit} * FROM {table_name};"
        
        tab.sql_editor.insert('1.0', query)
    
    def query_column(self, col_name, table_name):
        """Generate SELECT query for specific column"""
        tab = self.query_notebook.nametowidget(self.query_notebook.select())
        tab.sql_editor.delete('1.0', tk.END)
        query = f"SELECT {col_name} FROM {table_name};"
        tab.sql_editor.insert('1.0', query)
    
    def count_table_rows(self, table_name):
        """Count rows in a table"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection")
            return
        
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            start = datetime.now()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            elapsed = (datetime.now() - start).total_seconds()
            
            messagebox.showinfo("Row Count", 
                              f"Table: {table_name}\n\nTotal rows: {count:,}\n\nTime: {elapsed:.2f}s")
        except Exception as e:
            messagebox.showerror("Error", f"Count failed:\n\n{str(e)}")
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.update_status(f"Copied to clipboard: {text}")
    
    def refresh_current_tree(self):
        """Refresh the currently active database tree"""
        if self.active_connection and self.active_connection in self.connections:
            try:
                current_tab = self.db_notebook.select()
                if current_tab:
                    tab_frame = self.db_notebook.nametowidget(current_tab)
                    if hasattr(tab_frame, 'db_tree'):
                        self.refresh_database_tree_for_connection(
                            self.active_connection, 
                            tab_frame.db_tree
                        )
            except Exception as e:
                print(f"Error refreshing tree: {e}")
    
    def load_more_rows(self):
        """Load the next batch of rows"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection")
            return
        
        if not self.last_query:
            return
        
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            limit_str = self.limit_var.get()
            if limit_str == "ALL":
                fetch_limit = None
            else:
                fetch_limit = int(limit_str)
            
            if not fetch_limit:
                messagebox.showinfo("Info", "Already loading all rows")
                return
            
            self.update_status(f"Loading more rows (offset: {self.current_offset})...")
            
            sql = self.last_query
            if 'SKIP' in sql.upper():
                messagebox.showwarning("Warning", "Query already contains SKIP clause")
                return
            
            if 'FIRST' not in sql.upper():
                modified_sql = sql[:6] + f' SKIP {self.current_offset} FIRST {fetch_limit}' + sql[6:]
            else:
                modified_sql = re.sub(r'FIRST\s+\d+', f'SKIP {self.current_offset} FIRST {fetch_limit}', 
                                    sql, count=1, flags=re.IGNORECASE)
            
            start = datetime.now()
            cursor.execute(modified_sql)
            rows = cursor.fetchall()
            
            if rows:
                cols = [d[0] for d in cursor.description]
                self.display_results(cols, rows, append=True)
                
                self.current_offset += len(rows)
                elapsed = (datetime.now() - start).total_seconds()
                
                tab = self.results_notebook.nametowidget(self.results_notebook.tabs()[0])
                total_rows = len(tab.results_tree.get_children())
                
                if len(rows) < fetch_limit:
                    self.update_status(f"Loaded all rows - Total: {total_rows} - {elapsed:.2f}s")
                    self.load_more_btn.config(state=tk.DISABLED)
                else:
                    self.update_status(f"Loaded {len(rows)} more rows - Total: {total_rows} - {elapsed:.2f}s")
                
                self.rows_label.config(text=f"Rows: {total_rows}")
            else:
                self.update_status("No more rows")
                self.load_more_btn.config(state=tk.DISABLED)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load more rows:\n\n{str(e)}")
    
    def execute_with_limit(self):
        """Show dialog to execute with custom limit"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Execute with Limit")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Fetch Limit:").pack(pady=5)
        
        limit_entry = ttk.Entry(frame, width=20)
        limit_entry.insert(0, self.limit_var.get())
        limit_entry.pack(pady=5)
        limit_entry.focus()
        
        def execute():
            self.limit_var.set(limit_entry.get())
            dialog.destroy()
            self.execute_query()
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Execute", command=execute).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
        
        limit_entry.bind('<Return>', lambda e: execute())
    
    def count_rows(self):
        """Count rows without fetching data"""
        if not self.active_connection or self.active_connection not in self.connections:
            messagebox.showwarning("Warning", "No active connection")
            return
        
        tab = self.query_notebook.nametowidget(self.query_notebook.select())
        sql = tab.sql_editor.get('1.0', tk.END).strip()
        
        if not sql or not sql.strip().upper().startswith('SELECT'):
            messagebox.showwarning("Warning", "Please enter a SELECT query")
            return
        
        try:
            conn_info = self.connections[self.active_connection]
            cursor = conn_info['cursor']
            
            count_sql = f"SELECT COUNT(*) FROM ({sql})"
            
            start = datetime.now()
            cursor.execute(count_sql)
            count = cursor.fetchone()[0]
            elapsed = (datetime.now() - start).total_seconds()
            
            messagebox.showinfo("Row Count", 
                              f"Total rows: {count:,}\n\nTime: {elapsed:.2f}s")
            self.update_status(f"Row count: {count:,} - {elapsed:.2f}s")
            
        except Exception as e:
            messagebox.showerror("Error", f"Count failed:\n\n{str(e)}")
    
    def set_fetch_limit(self):
        """Set default fetch limit"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Fetch Limit")
        dialog.geometry("350x180")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Default Fetch Limit:", font=('Arial', 10, 'bold')).pack(pady=5)
        ttk.Label(frame, text="(Applies to all new queries)").pack(pady=2)
        
        limit_entry = ttk.Entry(frame, width=20)
        limit_entry.insert(0, self.limit_var.get())
        limit_entry.pack(pady=10)
        limit_entry.focus()
        
        def save():
            try:
                value = limit_entry.get()
                if value == "ALL" or int(value) > 0:
                    self.limit_var.set(value)
                    self.fetch_limit = None if value == "ALL" else int(value)
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", "Please enter a positive number or 'ALL'")
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number or 'ALL'")
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
        
        limit_entry.bind('<Return>', lambda e: save())
    
    def on_limit_changed(self, event=None):
        """Handle limit combobox change"""
        value = self.limit_var.get()
        if value == "ALL":
            self.fetch_limit = None
        else:
            try:
                self.fetch_limit = int(value)
            except:
                pass
        
    def clear_results(self):
        """Clear query results"""
        tab = self.results_notebook.nametowidget(self.results_notebook.tabs()[0])
        tab.results_tree.delete(*tab.results_tree.get_children())
        self.rows_label.config(text="Rows: 0")
        self.export_btn.config(state=tk.DISABLED)
        
    def export_results(self):
        """Export results to CSV - handles large datasets efficiently"""
        if not self.active_connection or self.active_connection not in self.connections:
            return
        
        tab = self.results_notebook.nametowidget(self.results_notebook.tabs()[0])
        
        if not hasattr(tab, 'results_data') or tab.results_data is None:
            if not tab.results_tree.get_children():
                messagebox.showwarning("Warning", "No results to export")
                return
        
        f = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"), ("All Files", "*.*")]
        )
        
        if not f:
            return
        
        try:
            row_count = len(tab.results_tree.get_children())
            
            if row_count > 10000:
                if not messagebox.askyesno("Large Export", 
                    f"Exporting {row_count:,} rows may take time.\n\nContinue?"):
                    return
            
            self.update_status(f"Exporting {row_count:,} rows...")
            
            if PANDAS_AVAILABLE and hasattr(tab, 'results_data') and tab.results_data is not None:
                if f.endswith('.xlsx'):
                    tab.results_data.to_excel(f, index=False, engine='openpyxl')
                else:
                    tab.results_data.to_csv(f, index=False)
            else:
                import csv
                with open(f, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    cols = tab.results_tree['columns']
                    writer.writerow(cols)
                    
                    for item in tab.results_tree.get_children():
                        values = tab.results_tree.item(item)['values']
                        writer.writerow(values)
            
            self.update_status(f"Exported {row_count:,} rows successfully")
            messagebox.showinfo("Success", f"Exported {row_count:,} rows to:\n{f}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n\n{str(e)}")
                
    def open_sql_file(self):
        """Open SQL file"""
        f = filedialog.askopenfilename(filetypes=[("SQL", "*.sql"), ("All Files", "*.*")])
        if f:
            with open(f, 'r', encoding='utf-8') as file:
                tab = self.query_notebook.nametowidget(self.query_notebook.select())
                tab.sql_editor.delete('1.0', tk.END)
                tab.sql_editor.insert('1.0', file.read())
                
    def save_query(self):
        """Save query to file"""
        f = filedialog.asksaveasfilename(defaultextension=".sql", 
                                        filetypes=[("SQL", "*.sql"), ("All Files", "*.*")])
        if f:
            tab = self.query_notebook.nametowidget(self.query_notebook.select())
            with open(f, 'w', encoding='utf-8') as file:
                file.write(tab.sql_editor.get('1.0', tk.END))
                
    def load_connections(self):
        """Load saved connections"""
        if os.path.exists(self.connections_file):
            try:
                with open(self.connections_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def apply_theme(self):
        """Apply theme"""
        ttk.Style().theme_use('clam')
    
    def show_requirements(self):
        """Show detailed requirements status"""
        status_lines = []
        status_lines.append("=" * 50)
        status_lines.append("REQUIREMENTS CHECK")
        status_lines.append("=" * 50)
        status_lines.append("")
        
        status_lines.append("Python Packages:")
        status_lines.append(f"  JPype1:      {'✓ Installed' if JPYPE_AVAILABLE else '✗ NOT INSTALLED'}")
        if not JPYPE_AVAILABLE:
            status_lines.append("               Fix: pip install JPype1")
        
        status_lines.append(f"  JayDeBeApi:  {'✓ Installed' if JAYDEBEAPI_AVAILABLE else '✗ NOT INSTALLED'}")
        if not JAYDEBEAPI_AVAILABLE:
            status_lines.append("               Fix: pip install JayDeBeApi")
        
        status_lines.append(f"  Pandas:      {'✓ Installed' if PANDAS_AVAILABLE else '✗ NOT INSTALLED (optional)'}")
        status_lines.append("")
        
        status_lines.append("JDBC Driver:")
        jdbc_ok = self.jdbc_driver_path and os.path.exists(self.jdbc_driver_path)
        status_lines.append(f"  Status:      {'✓ Found' if jdbc_ok else '✗ NOT FOUND'}")
        if self.jdbc_driver_path:
            status_lines.append(f"  Path:        {self.jdbc_driver_path}")
        status_lines.append("")
        
        status_lines.append("Java Virtual Machine:")
        status_lines.append(f"  Status:      {'✓ Found' if self.jvm_dll_path else '✗ NOT FOUND'}")
        if self.jvm_dll_path:
            status_lines.append(f"  Path:        {self.jvm_dll_path}")
        status_lines.append("")
        
        status_lines.append("=" * 50)
        all_ok = all([JAYDEBEAPI_AVAILABLE, JPYPE_AVAILABLE, jdbc_ok, self.jvm_dll_path])
        status_lines.append(f"Overall: {'✓ Ready to Connect' if all_ok else '✗ Missing Requirements'}")
        status_lines.append("=" * 50)
        
        msg = "\n".join(status_lines)
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Requirements Check")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        
        text_widget = scrolledtext.ScrolledText(dialog, wrap=tk.NONE, font=('Consolas', 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert('1.0', msg)
        text_widget.config(state=tk.DISABLED)
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def configure_jdbc_driver(self):
        """Configure JDBC driver path"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configure JDBC Driver")
        dialog.geometry("700x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="JDBC Driver JAR:", font=('Arial', 10, 'bold')).pack(pady=10)
        
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=5)
        
        path_entry = ttk.Entry(path_frame, width=70)
        path_entry.insert(0, self.jdbc_driver_path or "")
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        
        def browse():
            f = filedialog.askopenfilename(filetypes=[("JAR", "*.jar"), ("All Files", "*.*")])
            if f:
                path_entry.delete(0, tk.END)
                path_entry.insert(0, f)
        
        ttk.Button(path_frame, text="Browse", command=browse).pack(side=tk.LEFT)
        
        def save():
            p = path_entry.get().strip()
            if p and os.path.exists(p):
                self.jdbc_driver_path = p
                with open("jdbc_config.json", 'w') as f:
                    json.dump({"jdbc_driver_path": p}, f)
                messagebox.showinfo("Success", "JDBC driver path saved!\n\nPlease restart the application.")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "File not found")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
    
    def update_status(self, msg): 
        self.status_label.config(text=msg)
        self.root.update_idletasks()
        
    def on_closing(self):
        try:
            self.transaction_monitor_running = False
            
            for conn_name in list(self.connections.keys()):
                self.close_connection(conn_name)
            
            if JPYPE_AVAILABLE and jpype.isJVMStarted():
                jpype.shutdownJVM()
                
        except:
            pass
        self.root.destroy()


def main():
    print("="*60)
    print("Informix Database Studio - Multi-Connection + Comparator + FK Visualizer + Transaction Monitor")
    print("="*60)
    print()
    
    root = tk.Tk()
    app = InformixStudioJDBC(root)
    root.mainloop()


if __name__ == "__main__":
    main()
