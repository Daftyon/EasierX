"""
Informix Database Studio - JDBC Version (Manual JVM Path)
Works with Java 22 by constructing jvm.dll path manually
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
from datetime import datetime
import threading

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


def find_jvm_dll():
    """Find jvm.dll using JAVA_HOME"""
    java_home = os.environ.get('JAVA_HOME')
    
    if not java_home:
        return None
    
    # Try server JVM first (64-bit)
    jvm_path = os.path.join(java_home, 'bin', 'server', 'jvm.dll')
    if os.path.exists(jvm_path):
        return jvm_path
    
    # Try client JVM
    jvm_path = os.path.join(java_home, 'bin', 'client', 'jvm.dll')
    if os.path.exists(jvm_path):
        return jvm_path
    
    return None


class InformixStudioJDBC:
    def __init__(self, root):
        self.root = root
        self.root.title("Informix Database Studio (JDBC)")
        self.root.geometry("1400x900")
        
        self.connection = None
        self.cursor = None
        self.connections_file = "connections_jdbc.json"
        self.saved_connections = self.load_connections()
        
        self.jdbc_driver_path = self.load_jdbc_config()
        self.jvm_started = False
        self.jvm_dll_path = find_jvm_dll()
        
        self.query_history = []
        self.max_history = 100
        
        self.create_menu()
        self.create_toolbar()
        self.create_main_layout()
        self.create_statusbar()
        self.apply_theme()
        
        # Show JVM status
        if self.jvm_dll_path:
            self.update_status(f"JVM found: {self.jvm_dll_path}")
        else:
            self.update_status("JVM not found - check JAVA_HOME")
        
    def load_jdbc_config(self):
        """Load JDBC configuration"""
        config_file = "jdbc_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('jdbc_driver_path', '')
            except:
                pass
        return ''
        
    def start_jvm(self):
        """Start JVM with manual jvm.dll path"""
        if self.jvm_started:
            return True
        
        if not JPYPE_AVAILABLE:
            messagebox.showerror("Error", "JPype1 not installed.\n\nInstall: pip install JPype1")
            return False
        
        if not self.jdbc_driver_path or not os.path.exists(self.jdbc_driver_path):
            messagebox.showerror("Error", "JDBC driver not configured.\n\nConfigure in: Connection > Configure JDBC Driver")
            return False
        
        if not self.jvm_dll_path:
            messagebox.showerror("JVM Error", 
                               f"Cannot find jvm.dll\n\n"
                               f"JAVA_HOME = {os.environ.get('JAVA_HOME', 'NOT SET')}\n\n"
                               f"Expected location:\n"
                               f"C:\\Program Files\\Java\\jdk-22\\bin\\server\\jvm.dll\n\n"
                               f"Solution: Verify Java is installed in JAVA_HOME path")
            return False
        
        try:
            if not jpype.isJVMStarted():
                print(f"Starting JVM with: {self.jvm_dll_path}")
                jpype.startJVM(
                    self.jvm_dll_path,
                    "-ea",
                    f"-Djava.class.path={self.jdbc_driver_path}",
                    convertStrings=False
                )
            self.jvm_started = True
            self.update_status("JVM started successfully")
            return True
        except Exception as e:
            messagebox.showerror("JVM Error", 
                               f"Failed to start JVM:\n\n{str(e)}\n\n"
                               f"JVM path: {self.jvm_dll_path}\n"
                               f"JDBC JAR: {self.jdbc_driver_path}")
            return False
        
    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Query", command=self.new_query_tab)
        file_menu.add_command(label="Open SQL File", command=self.open_sql_file)
        file_menu.add_command(label="Save Query", command=self.save_query)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        conn_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Connection", menu=conn_menu)
        conn_menu.add_command(label="New Connection", command=self.show_connection_dialog)
        conn_menu.add_command(label="Disconnect", command=self.disconnect)
        conn_menu.add_command(label="Configure JDBC Driver", command=self.configure_jdbc_driver)
        
        query_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Query", menu=query_menu)
        query_menu.add_command(label="Execute (F5)", command=self.execute_query)
        query_menu.add_command(label="Clear Results", command=self.clear_results)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Database Browser", command=self.refresh_database_tree)
        tools_menu.add_command(label="Export Results", command=self.export_results)
        
        self.root.bind('<F5>', lambda e: self.execute_query())
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_toolbar(self):
        """Create toolbar"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        self.conn_btn = ttk.Button(toolbar, text="🔌 Connect", command=self.show_connection_dialog)
        self.conn_btn.pack(side=tk.LEFT, padx=2)
        
        self.disconn_btn = ttk.Button(toolbar, text="❌ Disconnect", command=self.disconnect, state=tk.DISABLED)
        self.disconn_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        self.exec_btn = ttk.Button(toolbar, text="▶ Execute (F5)", command=self.execute_query, state=tk.DISABLED)
        self.exec_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(toolbar, text="🗑 Clear", command=self.clear_results).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        self.export_btn = ttk.Button(toolbar, text="💾 Export", command=self.export_results, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=2)
        
        # Status indicators
        jvm_status = "JVM: " + ("Found" if self.jvm_dll_path else "NOT FOUND")
        jvm_color = "green" if self.jvm_dll_path else "red"
        ttk.Label(toolbar, text=jvm_status, foreground=jvm_color).pack(side=tk.RIGHT, padx=10)
        
        driver_ok = self.jdbc_driver_path and os.path.exists(self.jdbc_driver_path)
        jdbc_status = "JDBC: " + ("Ready" if driver_ok else "Not Configured")
        jdbc_color = "green" if driver_ok else "orange"
        ttk.Label(toolbar, text=jdbc_status, foreground=jdbc_color).pack(side=tk.RIGHT, padx=10)
        
        self.conn_indicator = ttk.Label(toolbar, text="● Not Connected", foreground="red")
        self.conn_indicator.pack(side=tk.RIGHT, padx=10)
        
    def create_main_layout(self):
        """Create main layout"""
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(main_paned, width=250)
        main_paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Database Objects", font=('Arial', 10, 'bold')).pack(pady=5)
        
        tree_scroll = ttk.Scrollbar(left_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.db_tree = ttk.Treeview(left_frame, yscrollcommand=tree_scroll.set)
        self.db_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.db_tree.yview)
        
        self.db_tree.bind('<Double-Button-1>', self.on_tree_double_click)
        
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
        """Create status bar"""
        self.statusbar = ttk.Frame(self.root, relief=tk.SUNKEN)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ttk.Label(self.statusbar, text="Ready", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.rows_label = ttk.Label(self.statusbar, text="Rows: 0", anchor=tk.E)
        self.rows_label.pack(side=tk.RIGHT, padx=5)
        
        self.time_label = ttk.Label(self.statusbar, text="Time: 0.00s", anchor=tk.E)
        self.time_label.pack(side=tk.RIGHT, padx=5)
        
    def new_query_tab(self):
        """Create new query tab"""
        tab_frame = ttk.Frame(self.query_notebook)
        tab_count = len(self.query_notebook.tabs()) + 1
        self.query_notebook.add(tab_frame, text=f"Query {tab_count}")
        
        sql_editor = scrolledtext.ScrolledText(tab_frame, wrap=tk.NONE, font=('Consolas', 11), undo=True)
        sql_editor.pack(fill=tk.BOTH, expand=True)
        
        tab_frame.sql_editor = sql_editor
        self.query_notebook.select(tab_frame)
        
        return tab_frame
        
    def create_results_tab(self, tab_name):
        """Create results tab"""
        tab_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(tab_frame, text=tab_name)
        
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
        
    def configure_jdbc_driver(self):
        """Configure JDBC driver"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configure JDBC Driver")
        dialog.geometry("700x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="JDBC Driver JAR Path:", font=('Arial', 10, 'bold')).pack(pady=10)
        
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=5)
        
        path_entry = ttk.Entry(path_frame, width=70)
        path_entry.insert(0, self.jdbc_driver_path or "")
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def browse_jar():
            filename = filedialog.askopenfilename(
                title="Select Informix JDBC Driver",
                filetypes=[("JAR files", "*.jar"), ("All files", "*.*")],
                initialdir=r"C:\Users\018801\.m2\repository\com\ibm\informix\jdbc"
            )
            if filename:
                path_entry.delete(0, tk.END)
                path_entry.insert(0, filename)
        
        ttk.Button(path_frame, text="Browse...", command=browse_jar).pack(side=tk.LEFT)
        
        ttk.Label(main_frame, 
                 text="Your JAR:\nC:\\Users\\018801\\.m2\\repository\\com\\ibm\\informix\\jdbc\\4.50.3\\jdbc-4.50.3.jar",
                 foreground="blue").pack(pady=10)
        
        def save_path():
            new_path = path_entry.get().strip()
            if new_path and os.path.exists(new_path):
                self.jdbc_driver_path = new_path
                try:
                    with open("jdbc_config.json", 'w') as f:
                        json.dump({"jdbc_driver_path": new_path}, f)
                except:
                    pass
                messagebox.showinfo("Success", "JDBC driver configured!")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "File not found")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Save", command=save_path).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def show_connection_dialog(self):
        """Show connection dialog"""
        if not JAYDEBEAPI_AVAILABLE or not JPYPE_AVAILABLE:
            messagebox.showerror("Error", "Missing libraries.\n\nInstall: pip install jaydebeapi JPype1")
            return
        
        if not self.jdbc_driver_path or not os.path.exists(self.jdbc_driver_path):
            messagebox.showerror("Error", "JDBC driver not configured.\n\nConfigure in: Connection > Configure JDBC Driver")
            return
        
        if not self.jvm_dll_path:
            messagebox.showerror("Error", 
                               f"Cannot find jvm.dll\n\n"
                               f"JAVA_HOME = {os.environ.get('JAVA_HOME', 'NOT SET')}\n\n"
                               f"Expected:\nC:\\Program Files\\Java\\jdk-22\\bin\\server\\jvm.dll")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Connect to Informix Database")
        dialog.geometry("550x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        fields = [
            ("Connection Name:", "name", ""),
            ("Host:", "host", "172.22.15.234"),
            ("Port:", "port", "9027"),
            ("Database:", "database", "ccp"),
            ("INFORMIXSERVER:", "informixserver", "BANK_CC_TRT"),
            ("Username:", "username", "cctrtdev"),
            ("Password:", "password", ""),
        ]
        
        entries = {}
        row = 0
        
        for label_text, field_name, default in fields:
            ttk.Label(main_frame, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=5)
            
            if field_name == "password":
                entry = ttk.Entry(main_frame, show="*", width=45)
            else:
                entry = ttk.Entry(main_frame, width=45)
                if default:
                    entry.insert(0, default)
            
            entry.grid(row=row, column=1, sticky=tk.EW, pady=5)
            entries[field_name] = entry
            row += 1
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        def connect():
            conn_params = {k: v.get() for k, v in entries.items()}
            dialog.destroy()
            self.connect_to_database(
                conn_params["host"],
                conn_params["port"],
                conn_params["database"],
                conn_params["informixserver"],
                conn_params["username"],
                conn_params["password"]
            )
        
        ttk.Button(button_frame, text="Connect", command=connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
    def connect_to_database(self, host, port, database, informixserver, username, password):
        """Connect to database"""
        try:
            self.update_status("Starting JVM...")
            
            if not self.start_jvm():
                return
            
            self.update_status("Connecting to database...")
            
            jdbc_url = f"jdbc:informix-sqli://{host}:{port}/{database}:INFORMIXSERVER={informixserver};CLIENT_LOCALE=en_US.utf8;DB_LOCALE=en_US.utf8"
            
            self.connection = jaydebeapi.connect(
                "com.informix.jdbc.IfxDriver",
                jdbc_url,
                [username, password],
                self.jdbc_driver_path
            )
            self.cursor = self.connection.cursor()
            
            self.conn_indicator.config(text=f"● Connected: {database}@{host}", foreground="green")
            self.exec_btn.config(state=tk.NORMAL)
            self.disconn_btn.config(state=tk.NORMAL)
            self.conn_btn.config(state=tk.DISABLED)
            
            self.update_status(f"Connected to {database}")
            self.refresh_database_tree()
            
            messagebox.showinfo("Success", f"Connected to {database}!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed:\n\n{str(e)}")
            self.update_status("Connection failed")
            
    def disconnect(self):
        """Disconnect"""
        if self.connection:
            try:
                if self.cursor:
                    self.cursor.close()
                self.connection.close()
                self.connection = None
                self.cursor = None
                
                self.conn_indicator.config(text="● Not Connected", foreground="red")
                self.exec_btn.config(state=tk.DISABLED)
                self.disconn_btn.config(state=tk.DISABLED)
                self.conn_btn.config(state=tk.NORMAL)
                self.export_btn.config(state=tk.DISABLED)
                
                self.db_tree.delete(*self.db_tree.get_children())
                self.update_status("Disconnected")
            except:
                pass
                
    def execute_query(self):
        """Execute query"""
        if not self.connection:
            messagebox.showwarning("Warning", "Connect to database first")
            return
        
        current_tab = self.query_notebook.nametowidget(self.query_notebook.select())
        sql_query = current_tab.sql_editor.get('1.0', tk.END).strip()
        
        if not sql_query:
            messagebox.showwarning("Warning", "Enter a SQL query")
            return
        
        try:
            start_time = datetime.now()
            self.update_status("Executing query...")
            
            self.cursor.execute(sql_query)
            
            if sql_query.strip().upper().startswith('SELECT'):
                rows = self.cursor.fetchall()
                columns = [desc[0] for desc in self.cursor.description] if self.cursor.description else []
                
                self.display_results(columns, rows)
                
                elapsed = (datetime.now() - start_time).total_seconds()
                self.update_status(f"Query executed - {len(rows)} rows")
                self.rows_label.config(text=f"Rows: {len(rows)}")
                self.time_label.config(text=f"Time: {elapsed:.2f}s")
                self.export_btn.config(state=tk.NORMAL)
            else:
                self.connection.commit()
                elapsed = (datetime.now() - start_time).total_seconds()
                self.update_status("Query executed")
                self.time_label.config(text=f"Time: {elapsed:.2f}s")
                self.show_message_in_results("Query executed successfully")
                
        except Exception as e:
            messagebox.showerror("Error", f"Query failed:\n\n{str(e)}")
            self.update_status("Query failed")
            
    def display_results(self, columns, rows):
        """Display results"""
        if self.results_notebook.index('end') > 0:
            results_tab = self.results_notebook.nametowidget(self.results_notebook.tabs()[0])
        else:
            results_tab = self.create_results_tab("Results")
        
        results_tree = results_tab.results_tree
        
        results_tree.delete(*results_tree.get_children())
        results_tree['columns'] = columns
        results_tree.column('#0', width=0, stretch=tk.NO)
        
        for col in columns:
            results_tree.column(col, anchor=tk.W, width=150)
            results_tree.heading(col, text=col, anchor=tk.W)
        
        for row in rows:
            display_row = [str(val) if val is not None else 'NULL' for val in row]
            results_tree.insert('', tk.END, values=display_row)
        
        if PANDAS_AVAILABLE:
            results_tab.results_data = pd.DataFrame(rows, columns=columns)
        else:
            results_tab.results_data = {'columns': columns, 'rows': rows}
        
        self.results_notebook.select(results_tab)
        
    def show_message_in_results(self, message):
        """Show message"""
        if self.results_notebook.index('end') > 0:
            results_tab = self.results_notebook.nametowidget(self.results_notebook.tabs()[0])
        else:
            results_tab = self.create_results_tab("Results")
        
        results_tree = results_tab.results_tree
        results_tree.delete(*results_tree.get_children())
        results_tree['columns'] = ('Message',)
        results_tree.column('#0', width=0, stretch=tk.NO)
        results_tree.column('Message', anchor=tk.W, width=800)
        results_tree.heading('Message', text='Message', anchor=tk.W)
        
        for line in message.split('\n'):
            results_tree.insert('', tk.END, values=(line,))
        
    def refresh_database_tree(self):
        """Refresh database tree"""
        if not self.connection:
            return
        
        try:
            self.update_status("Loading database objects...")
            self.db_tree.delete(*self.db_tree.get_children())
            
            tables_node = self.db_tree.insert('', tk.END, text='Tables')
            try:
                self.cursor.execute("SELECT tabname FROM systables WHERE tabtype = 'T' AND tabid > 99 ORDER BY tabname")
                for table in self.cursor.fetchall():
                    self.db_tree.insert(tables_node, tk.END, text=table[0], values=('table', table[0]))
            except:
                pass
            
            self.update_status("Database objects loaded")
        except:
            pass
            
    def on_tree_double_click(self, event):
        """Handle tree double-click"""
        item = self.db_tree.selection()
        if item:
            values = self.db_tree.item(item[0], 'values')
            if values and len(values) >= 2:
                table_name = values[1]
                query = f"SELECT FIRST 100 * FROM {table_name};"
                current_tab = self.query_notebook.nametowidget(self.query_notebook.select())
                current_tab.sql_editor.delete('1.0', tk.END)
                current_tab.sql_editor.insert('1.0', query)
        
    def clear_results(self):
        """Clear results"""
        if self.results_notebook.index('end') > 0:
            results_tab = self.results_notebook.nametowidget(self.results_notebook.tabs()[0])
            results_tab.results_tree.delete(*results_tab.results_tree.get_children())
            results_tab.results_data = None
        self.rows_label.config(text="Rows: 0")
        self.time_label.config(text="Time: 0.00s")
        self.export_btn.config(state=tk.DISABLED)
        
    def export_results(self):
        """Export results"""
        if self.results_notebook.index('end') == 0:
            return
        
        results_tab = self.results_notebook.nametowidget(self.results_notebook.tabs()[0])
        if not results_tab.results_data:
            return
        
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not filename:
            return
        
        try:
            if PANDAS_AVAILABLE and isinstance(results_tab.results_data, pd.DataFrame):
                results_tab.results_data.to_csv(filename, index=False)
            else:
                import csv
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(results_tab.results_data['columns'])
                    writer.writerows(results_tab.results_data['rows'])
            messagebox.showinfo("Success", f"Exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{str(e)}")
            
    def open_sql_file(self):
        """Open SQL file"""
        filename = filedialog.askopenfilename(filetypes=[("SQL files", "*.sql")])
        if filename:
            try:
                with open(filename, 'r') as f:
                    current_tab = self.query_notebook.nametowidget(self.query_notebook.select())
                    current_tab.sql_editor.delete('1.0', tk.END)
                    current_tab.sql_editor.insert('1.0', f.read())
            except:
                pass
            
    def save_query(self):
        """Save query"""
        filename = filedialog.asksaveasfilename(defaultextension=".sql", filetypes=[("SQL files", "*.sql")])
        if filename:
            try:
                current_tab = self.query_notebook.nametowidget(self.query_notebook.select())
                with open(filename, 'w') as f:
                    f.write(current_tab.sql_editor.get('1.0', tk.END))
                messagebox.showinfo("Success", "Query saved")
            except:
                pass
        
    def load_connections(self):
        """Load connections"""
        if os.path.exists(self.connections_file):
            try:
                with open(self.connections_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
        
    def apply_theme(self):
        """Apply theme"""
        style = ttk.Style()
        style.theme_use('clam')
        
    def update_status(self, message):
        """Update status"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def on_closing(self):
        """Handle closing"""
        try:
            if self.connection:
                self.disconnect()
            if JPYPE_AVAILABLE and jpype.isJVMStarted():
                jpype.shutdownJVM()
        except:
            pass
        self.root.destroy()


def main():
    """Main"""
    print("="*60)
    print("Informix Database Studio (JDBC)")
    print("="*60)
    
    java_home = os.environ.get('JAVA_HOME')
    print(f"\nJAVA_HOME = {java_home or 'NOT SET'}")
    
    jvm_path = find_jvm_dll()
    if jvm_path:
        print(f"✓ JVM found: {jvm_path}")
    else:
        print(f"✗ JVM NOT FOUND")
        if java_home:
            print(f"  Expected: {java_home}\\bin\\server\\jvm.dll")
    
    print("="*60)
    print()
    
    root = tk.Tk()
    app = InformixStudioJDBC(root)
    root.mainloop()


if __name__ == "__main__":
    main()
