#!/usr/bin/env python3
"""
Enhanced Java Process & API Monitor - Remote-Only Production Desktop App

Features:
 - Remote java process scanning via SSH
 - Advanced port detection with multiple heuristics
 - Multi-endpoint health monitoring (Actuator, Eureka, Jenkins, Custom)
 - Real-time status tracking with visual alerts
 - Response time monitoring & trending
 - Historical data tracking & analytics
 - Auto-save/restore configurations
 - Batch operations on multiple targets
 - Custom API endpoint configuration
 - Advanced filtering & search
 - Responsive, modern UI design
 
Dependencies:
    pip install requests paramiko pillow
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
from datetime import datetime, timedelta
import threading
import queue
import json
import base64
import re
import time
import os
from pathlib import Path
from collections import defaultdict
import urllib.parse

try:
    import requests
    import paramiko
except ImportError as e:
    raise SystemExit(f"Missing dependency {e}. Install with: pip install requests paramiko")

# ============== Configuration ==============
DEFAULT_POLL_SECONDS = 30
TIMEOUT_SECONDS = 8
MAX_HISTORY_ENTRIES = 1000
CONFIG_FILE = Path.home() / '.java_monitor_config.json'

# Predefined service endpoints
SERVICES = [
    {"name": "Spring Actuator Health", "path": "/actuator/health", "expect": "status", "critical": True},
    {"name": "Spring Actuator Info", "path": "/actuator/info", "expect": "", "critical": False},
    {"name": "Spring Actuator Metrics", "path": "/actuator/metrics", "expect": "names", "critical": False},
    {"name": "Eureka Apps", "path": "/eureka/apps", "expect": "applications", "critical": True},
    {"name": "Eureka Status", "path": "/eureka/status", "expect": "", "critical": False},
    {"name": "Jenkins API", "path": "/api/json", "expect": "", "critical": False},
    {"name": "Basic Health", "path": "/health", "expect": "", "critical": True},
    {"name": "Swagger UI", "path": "/swagger-ui.html", "expect": "", "critical": False},
    {"name": "API Docs", "path": "/v3/api-docs", "expect": "", "critical": False},
]

# Common Java application ports
COMMON_PORTS = {
    8080: "Tomcat/Spring Boot",
    8081: "Management",
    9090: "Prometheus",
    8761: "Eureka",
    8888: "Config Server",
    8500: "Consul",
}

# Color scheme - Modern professional theme
COLORS = {
    'bg_dark': '#1e1e1e',
    'bg_light': '#ffffff',
    'primary': '#0078d4',
    'primary_dark': '#005a9e',
    'success': '#28a745',
    'success_light': '#d4edda',
    'success_dark': '#155724',
    'error': '#dc3545',
    'error_light': '#f8d7da',
    'error_dark': '#721c24',
    'warning': '#ffc107',
    'warning_light': '#fff3cd',
    'warning_dark': '#856404',
    'text_dark': '#ffffff',
    'text_light': '#212529',
    'border': '#dee2e6',
    'hover': '#e7f3ff',
    'gray_light': '#f8f9fa',
    'gray_medium': '#6c757d',
}

# ============== Utilities ==============
def build_auth_header(auth_type, username, password, token):
    """Build authentication headers for HTTP requests"""
    headers = {}
    if auth_type == 'Basic' and username:
        userpass = f"{username}:{password or ''}".encode('utf-8')
        headers['Authorization'] = 'Basic ' + base64.b64encode(userpass).decode('ascii')
    elif auth_type == 'Bearer' and token:
        headers['Authorization'] = 'Bearer ' + token
    return headers

def probe_url(base_url, service, timeout=TIMEOUT_SECONDS, headers=None):
    """Probe a service endpoint and return detailed status"""
    url = base_url.rstrip('/') + service['path']
    start_time = time.time()
    
    try:
        r = requests.get(url, timeout=timeout, headers=headers or {}, verify=False)
        response_time = (time.time() - start_time) * 1000  # ms
        
        ok = (200 <= r.status_code < 300)
        summary = ''
        data = None
        
        try:
            j = r.json()
            data = j
            if service['expect']:
                found = service['expect'] in json.dumps(j)
                summary = f"{r.status_code}, has '{service['expect']}'={found}"
            else:
                keys = list(j.keys())[:5]
                summary = f"{r.status_code}, keys: {','.join(keys)}"
        except Exception:
            summary = f"{r.status_code} (non-json)"
            
        return {
            'ok': ok, 
            'status_code': r.status_code, 
            'summary': summary, 
            'url': url,
            'response_time': response_time,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
    except requests.exceptions.Timeout:
        return {
            'ok': False, 
            'status_code': None, 
            'summary': f'Timeout after {timeout}s', 
            'url': url,
            'response_time': timeout * 1000,
            'timestamp': datetime.now().isoformat()
        }
    except requests.exceptions.ConnectionError as e:
        return {
            'ok': False, 
            'status_code': None, 
            'summary': f'Connection Error', 
            'url': url,
            'response_time': None,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'ok': False, 
            'status_code': None, 
            'summary': str(e)[:80], 
            'url': url,
            'response_time': None,
            'timestamp': datetime.now().isoformat()
        }

# Enhanced port detection patterns
JAVA_PORT_PATTERNS = [
    re.compile(r'--server\.port[=\s]+(\d+)'),
    re.compile(r'-Dserver\.port[=\s]+(\d+)'),
    re.compile(r'--port[=\s]+(\d+)'),
    re.compile(r'-Dport[=\s]+(\d+)'),
    re.compile(r'--server\.address[=\s]+[\w\.\:]*:(\d+)'),
    re.compile(r'-Dtomcat\.port[=\s]+(\d+)'),
    re.compile(r'--management\.port[=\s]+(\d+)'),
    re.compile(r'-Dhttp\.port[=\s]+(\d+)'),
    re.compile(r'--http\.port[=\s]+(\d+)'),
    re.compile(r'--listen[=\s]+[\w\.\:]*:(\d+)'),
    re.compile(r'-Dlisten\.port[=\s]+(\d+)'),
    re.compile(r'--address[=\s]+[\w\.\:]*:(\d+)'),
    re.compile(r'-javaagent.*:(\d{4,5})\b'),  # Java agents often have ports
    re.compile(r'application\.port[=\s]+(\d+)'),
    re.compile(r'server\.port[=\s]+(\d+)'),
]

def parse_java_cmdline(cmdline: str):
    """Extract port, name, and metadata from Java command line"""
    port = None
    name = None
    jar_name = None
    main_class = None
    
    # Try explicit port patterns first
    for p in JAVA_PORT_PATTERNS:
        m = p.search(cmdline)
        if m:
            potential_port = m.group(1)
            if 1024 <= int(potential_port) <= 65535:
                port = potential_port
                break
    
    # If no explicit port, look for numeric values in valid port range
    if not port:
        # Look for patterns like :8080 or =8080 or " 8080"
        for m in re.finditer(r'[\s:=](\d{4,5})\b', cmdline):
            potential_port = int(m.group(1))
            if 1024 <= potential_port <= 65535:
                # Common Java ports are more likely
                if potential_port in COMMON_PORTS or potential_port in [8080, 8081, 8082, 8083, 8088, 8090, 9090, 8761, 8888]:
                    port = str(potential_port)
                    break
                # Any port in 8000-9999 range is likely
                elif 8000 <= potential_port <= 9999:
                    port = str(potential_port)
                    break
    
    # Extract JAR name
    mjar = re.search(r'([\w\-\.]+)\.jar', cmdline)
    if mjar:
        jar_name = mjar.group(0)
        name = mjar.group(1)
    
    # Extract main class
    mc = re.search(r'\b([A-Za-z0-9_\.]*(?:Application|Main|Server|Bootstrap|Service))\b', cmdline)
    if mc:
        main_class = mc.group(1)
        if not name:
            name = main_class.split('.')[-1]
    
    # Try to extract application name from jar path
    if not name:
        jar_path = re.search(r'/([\w\-]+)\.jar', cmdline)
        if jar_path:
            name = jar_path.group(1)
    
    # Fallback name
    if not name:
        if jar_name:
            name = jar_name.replace('.jar', '')
        elif main_class:
            name = main_class
        else:
            # Try to extract from classpath
            cp_match = re.search(r'-cp\s+.*/([\w\-]+)\.jar', cmdline)
            if cp_match:
                name = cp_match.group(1)
            else:
                name = 'java-process'
    
    return {
        'port': port, 
        'name': name,
        'jar': jar_name,
        'main_class': main_class,
        'cmdline': cmdline
    }

# ============== SSH Operations ==============
def ssh_run(host, username, password=None, pkey_path=None, port=22, timeout=10,
            cmd='ps -eo pid,args | grep java | grep -v grep'):
    """Execute command on remote host via SSH"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        connect_kwargs = {
            'hostname': host,
            'port': port,
            'username': username,
            'timeout': timeout
        }
        
        if pkey_path and pkey_path.strip():
            try:
                key = paramiko.RSAKey.from_private_key_file(pkey_path)
                connect_kwargs['pkey'] = key
            except:
                try:
                    key = paramiko.Ed25519Key.from_private_key_file(pkey_path)
                    connect_kwargs['pkey'] = key
                except:
                    if password:
                        connect_kwargs['password'] = password
        elif password:
            connect_kwargs['password'] = password
        
        client.connect(**connect_kwargs)
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        client.close()
        return out, err
    except Exception as e:
        try:
            client.close()
        except:
            pass
        return '', str(e)

def get_server_history(host, username, password=None, pkey_path=None, port=22, lines=100):
    """Get Unix command history from remote server"""
    # Try multiple methods to get history
    commands = [
        f"cat ~/.bash_history | tail -n {lines}",  # ← MOVE THIS TO FIRST
        f"history {lines}",  # Standard history command
        f"cat ~/.zsh_history | tail -n {lines}",  # Zsh history file
    ]
    
    for cmd in commands:
        out, err = ssh_run(host, username, password, pkey_path, port, cmd=cmd)
        if out and not err:
            return out, None
    
    return None, "Could not retrieve history from server"

def get_listening_ports(host, username, password=None, pkey_path=None, port=22):
    """Get listening ports mapped to PIDs"""
    # Try to get listening ports with PIDs
    cmd = "ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null || lsof -i -n -P 2>/dev/null | grep LISTEN"
    out, err = ssh_run(host, username, password, pkey_path, port, cmd=cmd)
    
    pid_port_map = {}
    if out:
        # Parse ss/netstat output
        for line in out.splitlines():
            # Look for PID and port patterns
            # ss format: ... users:(("java",pid=12345,fd=89)) ... :8080
            # netstat format: ... :8080 ... 12345/java
            
            pid_match = re.search(r'pid[=\s]+(\d+)|(\d+)/\w+', line)
            port_match = re.search(r':(\d{4,5})\s', line)
            
            if pid_match and port_match:
                pid = pid_match.group(1) or pid_match.group(2)
                listening_port = port_match.group(1)
                if 1024 <= int(listening_port) <= 65535:
                    pid_port_map[pid] = listening_port
    
    return pid_port_map

def parse_remote_ps_output(ps_output: str):
    """Parse ps command output to extract Java process information"""
    lines = [l.strip() for l in ps_output.splitlines() if l.strip()]
    items = []
    
    for line in lines:
        m = re.match(r'^(\d+)\s+(.*)$', line)
        if m:
            pid = m.group(1)
            cmd = m.group(2)
            parsed = parse_java_cmdline(cmd)
            items.append({
                'pid': pid,
                'cmd': cmd,
                'port': parsed['port'],
                'name': parsed['name'] or f'java-{pid}',
                'jar': parsed.get('jar'),
                'main_class': parsed.get('main_class'),
            })
    return items

# ============== Main Application ==============
class MonitorApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill='both', expand=True)
        
        master.title('PortiX - Java Process & Service Monitor')
        master.geometry('1600x900')
        master.minsize(1200, 700)
        
        # Set app icon if available
        try:
            # You can add an icon file here
            # master.iconbitmap('portix.ico')
            pass
        except:
            pass
        
        # State
        self.servers = []
        self.custom_services = []
        self.result_queue = queue.Queue()
        self._polling = False
        self._poll_interval = DEFAULT_POLL_SECONDS
        
        # History tracking
        self.history = defaultdict(list)
        self.alert_state = {}
        
        # Server history - track all events per server
        self.server_history = defaultdict(list)  # {server_host: [events]}
        self.max_server_history = 100  # Keep last 100 events per server
        
        # Statistics
        self.stats = {
            'total_scans': 0,
            'total_probes': 0,
            'failed_probes': 0,
            'servers_down': 0
        }
        
        # Current filter
        self.filter_text = ''
        
        self._setup_styles()
        self._create_menu()
        self._create_widgets()
        self._start_queue_poller()
        self._load_config()
        
        # Bind resize event
        master.bind('<Configure>', self._on_resize)

    def _setup_styles(self):
        """Configure modern UI styles"""
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass
        
        # Configure main styles with professional colors
        style.configure('Header.TLabel', 
                       font=('Segoe UI', 16, 'bold'), 
                       foreground=COLORS['primary'])
        style.configure('Subheader.TLabel', 
                       font=('Segoe UI', 11, 'bold'),
                       foreground=COLORS['text_light'])
        style.configure('Status.TLabel', 
                       font=('Segoe UI', 10))
        style.configure('Success.TLabel', 
                       foreground=COLORS['success'], 
                       font=('Segoe UI', 10, 'bold'))
        style.configure('Error.TLabel', 
                       foreground=COLORS['error'], 
                       font=('Segoe UI', 10, 'bold'))
        style.configure('Warning.TLabel', 
                       foreground=COLORS['warning'], 
                       font=('Segoe UI', 10, 'bold'))
        
        # Button styles
        style.configure('Primary.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       background=COLORS['primary'])
        style.map('Primary.TButton',
                 background=[('active', COLORS['primary_dark'])])
        
        style.configure('Success.TButton', 
                       background=COLORS['success'])
        style.configure('Danger.TButton', 
                       background=COLORS['error'])
        
        # Frame styles
        style.configure('Card.TFrame', 
                       relief='raised', 
                       borderwidth=1,
                       background=COLORS['bg_light'])
        style.configure('TLabelframe', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground=COLORS['primary'])
        style.configure('TLabelframe.Label',
                       font=('Segoe UI', 10, 'bold'),
                       foreground=COLORS['primary'])
        
        # Configure default fonts
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=10)

    def _create_menu(self):
        """Create application menu bar"""
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Results...", command=self.export_results, 
                             accelerator="Ctrl+E")
        file_menu.add_command(label="Export History...", command=self.export_history)
        file_menu.add_separator()
        file_menu.add_command(label="Save Config", command=self.save_config, 
                             accelerator="Ctrl+S")
        file_menu.add_command(label="Load Config...", command=self.load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.master.quit, 
                             accelerator="Ctrl+Q")
        
        # Targets menu
        targets_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Targets", menu=targets_menu)
        targets_menu.add_command(label="Add Remote Target...", command=self.open_add_remote, 
                                accelerator="Ctrl+N")
        targets_menu.add_command(label="Edit Selected", command=self.edit_selected_target)
        targets_menu.add_command(label="Remove Selected", command=self.remove_selected_target, 
                                accelerator="Delete")
        targets_menu.add_separator()
        targets_menu.add_command(label="Scan Selected", command=self.scan_selected_remote, 
                                accelerator="F5")
        targets_menu.add_command(label="Scan All Targets", command=self.scan_all_targets, 
                                accelerator="Ctrl+F5")
        
        # Actions menu
        actions_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Actions", menu=actions_menu)
        actions_menu.add_command(label="Start/Stop Polling", command=self.toggle_polling, 
                                accelerator="Ctrl+Space")
        actions_menu.add_separator()
        actions_menu.add_command(label="Add Custom Service...", command=self.add_custom_service)
        actions_menu.add_command(label="Clear Results", command=self.clear_results)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Show Statistics", command=self.show_statistics, 
                             accelerator="Ctrl+I")
        view_menu.add_command(label="Show History", command=self.show_history, 
                             accelerator="Ctrl+H")
        view_menu.add_command(label="Server History", command=self.show_server_history,
                             accelerator="Ctrl+R")
        view_menu.add_command(label="Refresh Display", command=self.refresh_display, 
                             accelerator="F5")
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Auto-scroll Log", command=self.toggle_autoscroll)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts, 
                             accelerator="F1")
        help_menu.add_command(label="About", command=self.show_about)

    def _create_widgets(self):
        """Create responsive main UI widgets"""
        # Configure grid weights for responsiveness
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Main container with paned window
        self.main_paned = ttk.PanedWindow(self, orient='horizontal')
        self.main_paned.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)
        
        # Left panel - Targets (20% width)
        left = self._create_left_panel(self.main_paned)
        self.main_paned.add(left, weight=1)
        
        # Right container - vertical paned for results and details
        right_paned = ttk.PanedWindow(self.main_paned, orient='vertical')
        self.main_paned.add(right_paned, weight=4)
        
        # Top right - Results (70% height)
        results = self._create_results_panel(right_paned)
        right_paned.add(results, weight=7)
        
        # Bottom right - Log and Status (30% height)
        bottom = self._create_bottom_panel(right_paned)
        right_paned.add(bottom, weight=3)

    def _create_left_panel(self, parent):
        """Create responsive left panel with target management"""
        left = ttk.Frame(parent, padding=10)
        left.grid_rowconfigure(8, weight=1)
        left.grid_columnconfigure(0, weight=1)
        
        # Header with PortiX branding
        header_frame = ttk.Frame(left)
        header_frame.grid(row=0, column=0, sticky='we', pady=(0, 15))
        header_frame.grid_columnconfigure(0, weight=1)
        
        # App logo/title
        title_label = ttk.Label(header_frame, text='🌐 PortiX', 
                               font=('Segoe UI', 18, 'bold'),
                               foreground=COLORS['primary'])
        title_label.grid(row=0, column=0, sticky='w')
        
        subtitle_label = ttk.Label(header_frame, text='Remote Targets', 
                                   font=('Segoe UI', 10),
                                   foreground=COLORS['gray_medium'])
        subtitle_label.grid(row=1, column=0, sticky='w', pady=(2, 0))
        
        # Action buttons
        btn_frame = ttk.Frame(left)
        btn_frame.grid(row=1, column=0, sticky='we', pady=(0, 10))
        btn_frame.grid_columnconfigure(0, weight=1)
        
        ttk.Button(btn_frame, text='➕ Add Remote', 
                  command=self.open_add_remote, 
                  style='Primary.TButton').grid(row=0, column=0, sticky='we', pady=2)
        
        ttk.Button(btn_frame, text='🔍 Scan Selected', 
                  command=self.scan_selected_remote).grid(row=1, column=0, sticky='we', pady=2)
        
        ttk.Button(btn_frame, text='🔄 Scan All', 
                  command=self.scan_all_targets).grid(row=2, column=0, sticky='we', pady=2)
        
        ttk.Button(btn_frame, text='📜 Server History', 
                  command=self.show_server_history).grid(row=3, column=0, sticky='we', pady=2)
        
        ttk.Button(btn_frame, text='✏️ Edit', 
                  command=self.edit_selected_target).grid(row=4, column=0, sticky='we', pady=2)
        
        ttk.Button(btn_frame, text='🗑️ Remove', 
                  command=self.remove_selected_target).grid(row=5, column=0, sticky='we', pady=2)
        
        ttk.Separator(left, orient='horizontal').grid(
            row=2, column=0, sticky='we', pady=10
        )
        
        # Target listbox with scrollbar
        list_label = ttk.Label(left, text='Configured Targets:', style='Subheader.TLabel')
        list_label.grid(row=3, column=0, sticky='w', pady=(0, 5))
        
        list_frame = ttk.Frame(left, style='Card.TFrame', relief='sunken', borderwidth=1)
        list_frame.grid(row=4, column=0, sticky='nswe', pady=(0, 10))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        self.target_listbox = tk.Listbox(list_frame, selectmode='extended', 
                                         font=('Segoe UI', 10),
                                         relief='flat', borderwidth=0,
                                         highlightthickness=0)
        self.target_listbox.grid(row=0, column=0, sticky='nswe')
        
        target_scroll = ttk.Scrollbar(list_frame, orient='vertical', 
                                      command=self.target_listbox.yview)
        target_scroll.grid(row=0, column=1, sticky='ns')
        self.target_listbox.configure(yscrollcommand=target_scroll.set)
        
        # Bind events
        self.target_listbox.bind('<Double-Button-1>', 
                                lambda e: self.scan_selected_remote())
        self.target_listbox.bind('<<ListboxSelect>>', self.on_target_select)
        
        # Target info card
        info_frame = ttk.LabelFrame(left, text='Target Information', padding=10)
        info_frame.grid(row=5, column=0, sticky='we', pady=(0, 10))
        info_frame.grid_columnconfigure(0, weight=1)
        
        self.target_info_label = ttk.Label(info_frame, text='Select a target to view details', 
                                          wraplength=250, justify='left')
        self.target_info_label.grid(row=0, column=0, sticky='we')
        
        # Quick stats
        stats_frame = ttk.LabelFrame(left, text='Quick Stats', padding=10)
        stats_frame.grid(row=6, column=0, sticky='we')
        stats_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(stats_frame, text='Targets:').grid(row=0, column=0, sticky='w', pady=2)
        self.target_count_label = ttk.Label(stats_frame, text='0', 
                                           font=('Segoe UI', 10, 'bold'))
        self.target_count_label.grid(row=0, column=1, sticky='e', pady=2)
        
        ttk.Label(stats_frame, text='Services:').grid(row=1, column=0, sticky='w', pady=2)
        self.service_count_label = ttk.Label(stats_frame, text='0', 
                                            font=('Segoe UI', 10, 'bold'))
        self.service_count_label.grid(row=1, column=1, sticky='e', pady=2)
        
        # Now refresh targets after all widgets are created
        self.refresh_targets()
        
        return left
    
    def _create_results_panel(self, parent):
        """Create responsive results panel"""
        results = ttk.Frame(parent, padding=10)
        results.grid_rowconfigure(3, weight=1)
        results.grid_columnconfigure(0, weight=1)
        
        # Header with status indicators
        header_frame = ttk.Frame(results)
        header_frame.grid(row=0, column=0, sticky='we', pady=(0, 15))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Title with icon
        title_container = ttk.Frame(header_frame)
        title_container.grid(row=0, column=0, sticky='w')
        
        ttk.Label(title_container, text='📊', 
                 font=('Segoe UI', 18)).pack(side='left', padx=(0, 5))
        ttk.Label(title_container, text='Discovered Services', 
                 font=('Segoe UI', 16, 'bold'),
                 foreground=COLORS['primary']).pack(side='left')
        
        # Status indicators with better styling
        status_frame = ttk.Frame(header_frame)
        status_frame.grid(row=0, column=1, sticky='e')
        
        self.status_up_label = ttk.Label(status_frame, text='🟢 0', 
                                        font=('Segoe UI', 11, 'bold'),
                                        foreground=COLORS['success'])
        self.status_up_label.pack(side='left', padx=10)
        
        self.status_down_label = ttk.Label(status_frame, text='🔴 0',
                                          font=('Segoe UI', 11, 'bold'),
                                          foreground=COLORS['error'])
        self.status_down_label.pack(side='left', padx=10)
        
        self.status_unknown_label = ttk.Label(status_frame, text='⚪ 0',
                                             font=('Segoe UI', 11),
                                             foreground=COLORS['gray_medium'])
        self.status_unknown_label.pack(side='left', padx=10)
        
        # Control toolbar
        toolbar = ttk.Frame(results)
        toolbar.grid(row=1, column=0, sticky='we', pady=(0, 5))
        toolbar.grid_columnconfigure(3, weight=1)
        
        # Polling control
        self.poll_button = ttk.Button(toolbar, text='▶️ Start Polling', 
                                      command=self.toggle_polling)
        self.poll_button.grid(row=0, column=0, padx=2)
        
        # Polling interval
        ttk.Label(toolbar, text='Interval:').grid(row=0, column=1, padx=(15, 2))
        self.poll_interval_var = tk.StringVar(value=str(DEFAULT_POLL_SECONDS))
        interval_combo = ttk.Combobox(toolbar, textvariable=self.poll_interval_var, 
                                     width=6, values=['10', '30', '60', '120', '300'],
                                     state='readonly')
        interval_combo.grid(row=0, column=2, sticky='w', padx=2)
        ttk.Label(toolbar, text='sec').grid(row=0, column=3, sticky='w', padx=2)
        
        # Search/Filter bar
        search_frame = ttk.Frame(results)
        search_frame.grid(row=2, column=0, sticky='we', pady=(0, 5))
        search_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(search_frame, text='🔎').grid(row=0, column=0, padx=(0, 5))
        
        # Initialize show_all_var BEFORE search_var - DEFAULT TO TRUE (CHECKED)
        self.show_all_var = tk.BooleanVar(value=True)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.apply_filter())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky='we', padx=2)
        
        ttk.Button(search_frame, text='✖', width=3, 
                  command=lambda: self.search_var.set('')).grid(row=0, column=2, padx=2)
        
        # Show all checkbox - CHECKED by default
        ttk.Checkbutton(search_frame, text='Show all', 
                       variable=self.show_all_var,
                       command=self.apply_filter).grid(row=0, column=3, padx=5)
        
        ttk.Button(search_frame, text='⟳ Refresh', 
                  command=self.refresh_display).grid(row=0, column=4, padx=2)
        
        # Results tree with modern styling
        tree_frame = ttk.Frame(results, relief='sunken', borderwidth=1)
        tree_frame.grid(row=3, column=0, sticky='nswe')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        cols = ('target', 'pid', 'name', 'port', 'service', 
                'status', 'response_time', 'last_check', 'summary')
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', 
                                selectmode='extended')
        
        # Configure columns with proper widths
        col_config = {
            'target': {'text': 'Target', 'width': 150, 'stretch': False},
            'pid': {'text': 'PID', 'width': 70, 'stretch': False},
            'name': {'text': 'Application', 'width': 180, 'stretch': True},
            'port': {'text': 'Port', 'width': 70, 'stretch': False},
            'service': {'text': 'Service', 'width': 150, 'stretch': True},
            'status': {'text': 'Status', 'width': 90, 'stretch': False},
            'response_time': {'text': 'Response', 'width': 90, 'stretch': False},
            'last_check': {'text': 'Last Check', 'width': 90, 'stretch': False},
            'summary': {'text': 'Details', 'width': 250, 'stretch': True}
        }
        
        for col, config in col_config.items():
            self.tree.heading(col, text=config['text'], 
                            command=lambda c=col: self.sort_tree(c))
            self.tree.column(col, anchor='w', width=config['width'], 
                           stretch=config['stretch'])
        
        self.tree.grid(row=0, column=0, sticky='nswe')
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky='we')
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Tags for row colors with professional styling
        self.tree.tag_configure('up', 
                               background=COLORS['success_light'], 
                               foreground=COLORS['success_dark'])
        self.tree.tag_configure('down', 
                               background=COLORS['error_light'], 
                               foreground=COLORS['error_dark'])
        self.tree.tag_configure('warning', 
                               background=COLORS['warning_light'], 
                               foreground=COLORS['warning_dark'])
        self.tree.tag_configure('selected', 
                               background=COLORS['primary'], 
                               foreground='white')
        
        # Context menu
        self.tree_menu = tk.Menu(self.tree, tearoff=0)
        self.tree_menu.add_command(label="📋 Copy URL", command=self.copy_url)
        self.tree_menu.add_command(label="🌐 Open in Browser", command=self.open_in_browser)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="ℹ️ View Details", command=self.view_details)
        self.tree_menu.add_command(label="📈 View History", command=self.view_item_history)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="🗑️ Delete", command=self.delete_selected)
        
        self.tree.bind('<Button-3>', self.show_tree_menu)
        
        return results
    
    def _create_bottom_panel(self, parent):
        """Create responsive bottom panel with log and statistics"""
        bottom = ttk.Frame(parent, padding=10)
        bottom.grid_rowconfigure(1, weight=1)
        bottom.grid_columnconfigure(0, weight=1)
        
        # Statistics bar with PortiX branding
        stats_frame = ttk.Frame(bottom)
        stats_frame.grid(row=0, column=0, sticky='we', pady=(0, 8))
        stats_frame.grid_columnconfigure(1, weight=1)
        
        # PortiX logo in stats bar
        ttk.Label(stats_frame, text='📊 PortiX', 
                 font=('Segoe UI', 11, 'bold'),
                 foreground=COLORS['primary']).grid(row=0, column=0, padx=(0, 10))
        
        self.stats_label = ttk.Label(stats_frame, text='Ready', 
                                     font=('Segoe UI', 10))
        self.stats_label.grid(row=0, column=1, sticky='w')
        
        # Polling status indicator with better styling
        self.polling_indicator = ttk.Label(stats_frame, text='⏸️ Idle', 
                                          font=('Segoe UI', 10),
                                          foreground=COLORS['gray_medium'])
        self.polling_indicator.grid(row=0, column=2, sticky='e', padx=15)
        
        # Log section
        log_frame = ttk.LabelFrame(bottom, text='Activity Log', padding=5)
        log_frame.grid(row=1, column=0, sticky='nswe')
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        log_container = ttk.Frame(log_frame)
        log_container.grid(row=0, column=0, sticky='nswe')
        log_container.grid_rowconfigure(0, weight=1)
        log_container.grid_columnconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_container, height=6, wrap='word',
                               font=('Consolas', 9), relief='flat',
                               borderwidth=0, highlightthickness=0)
        self.log_text.grid(row=0, column=0, sticky='nswe')
        
        log_scroll = ttk.Scrollbar(log_container, orient='vertical', 
                                   command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky='ns')
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
        # Log controls
        log_ctrl = ttk.Frame(log_frame)
        log_ctrl.grid(row=1, column=0, sticky='we', pady=(5, 0))
        
        ttk.Button(log_ctrl, text='Clear Log', 
                  command=lambda: self.log_text.delete('1.0', 'end')).pack(side='left', padx=2)
        ttk.Button(log_ctrl, text='Save Log...', 
                  command=self.save_log).pack(side='left', padx=2)
        ttk.Button(log_ctrl, text='Export Results...', 
                  command=self.export_results).pack(side='left', padx=2)
        
        return bottom

    def _on_resize(self, event):
        """Handle window resize for responsive layout"""
        # Adjust column widths based on window width
        if event.widget == self.master:
            width = event.width
            if hasattr(self, 'tree'):
                # Proportional column widths
                if width > 1400:
                    self.tree.column('summary', width=350)
                    self.tree.column('name', width=200)
                elif width > 1200:
                    self.tree.column('summary', width=250)
                    self.tree.column('name', width=180)
                else:
                    self.tree.column('summary', width=200)
                    self.tree.column('name', width=150)

    # ============== Target Management ==============
    def refresh_targets(self):
        """Refresh target listbox"""
        if not hasattr(self, 'target_listbox'):
            return
            
        self.target_listbox.delete(0, tk.END)
        for i, s in enumerate(self.servers):
            icon = '🟢' if s.get('last_scan_success', False) else '🔴'
            label = f"{icon} {s['host']}:{s.get('port', 22)} - {s.get('username', 'N/A')}"
            self.target_listbox.insert(tk.END, label)
        
        # Update count (safely check if widget exists)
        if hasattr(self, 'target_count_label'):
            self.target_count_label.config(text=str(len(self.servers)))

    def on_target_select(self, event):
        """Handle target selection"""
        sel = self.target_listbox.curselection()
        if not sel:
            self.target_info_label.config(text='Select a target to view details')
            return
        
        idx = sel[0]
        server = self.servers[idx]
        
        info = f"Host: {server['host']}\n"
        info += f"Port: {server.get('port', 22)}\n"
        info += f"Username: {server.get('username', 'N/A')}\n"
        info += f"Auth: {'Private Key' if server.get('pkey') else 'Password'}\n"
        
        if 'last_scan' in server:
            info += f"\nLast Scan: {server['last_scan']}\n"
            info += f"Status: {'✅ Success' if server.get('last_scan_success') else '❌ Failed'}"
        
        self.target_info_label.config(text=info)

    def open_add_remote(self):
        """Open dialog to add remote target"""
        dlg = RemoteDialog(self.master)
        self.master.wait_window(dlg.top)
        if dlg.result:
            self.servers.append(dlg.result)
            self.refresh_targets()
            self.log(f"✅ Added remote {dlg.result['host']}")
            self.save_config()

    def edit_selected_target(self):
        """Edit selected remote target"""
        sel = self.target_listbox.curselection()
        if not sel:
            messagebox.showinfo('Edit Target', 'Select a target to edit')
            return
        
        idx = sel[0]
        server = self.servers[idx]
        
        dlg = RemoteDialog(self.master, edit_data=server)
        self.master.wait_window(dlg.top)
        if dlg.result:
            self.servers[idx] = dlg.result
            self.refresh_targets()
            self.log(f"✅ Updated remote {dlg.result['host']}")
            self.save_config()

    def remove_selected_target(self):
        """Remove selected remote target"""
        sel = self.target_listbox.curselection()
        if not sel:
            messagebox.showinfo('Remove Target', 'Select a target to remove')
            return
        
        indices = sorted(sel, reverse=True)
        hosts = [self.servers[i]['host'] for i in indices]
        
        if messagebox.askyesno('Confirm', f"Remove {len(indices)} target(s)?\n\n" + '\n'.join(hosts)):
            for idx in indices:
                self.servers.pop(idx)
            self.refresh_targets()
            self.log(f"🗑️ Removed {len(indices)} target(s)")
            self.save_config()

    # ============== Scanning ==============
    def scan_selected_remote(self):
        """Scan selected remote target"""
        sel = self.target_listbox.curselection()
        if not sel:
            messagebox.showinfo('Scan Remote', 'Select a target to scan')
            return
        
        for idx in sel:
            conf = self.servers[idx]
            self.log(f"🔍 Scanning remote {conf['host']}...")
            threading.Thread(target=self._scan_remote_worker, args=(conf, idx), 
                           daemon=True).start()

    def scan_all_targets(self):
        """Scan all configured targets"""
        if not self.servers:
            messagebox.showinfo('Scan All', 'No targets configured')
            return
        
        self.log(f"🔍 Scanning all {len(self.servers)} target(s)...")
        for idx, server in enumerate(self.servers):
            threading.Thread(target=self._scan_remote_worker, args=(server, idx), 
                           daemon=True).start()

    def _scan_remote_worker(self, conf, idx):
        """Worker thread for remote scanning"""
        try:
            # First get Java processes
            out, err = ssh_run(conf['host'], conf['username'], 
                             password=conf.get('password'), 
                             pkey_path=conf.get('pkey'),
                             port=conf.get('port', 22))
            
            if err:
                self.result_queue.put(('scan_remote_error', 
                                      {'host': conf['host'], 'error': err, 'idx': idx}))
                return
            
            items = parse_remote_ps_output(out)
            
            # Try to get listening ports for better detection
            try:
                pid_port_map = get_listening_ports(
                    conf['host'], conf['username'],
                    password=conf.get('password'),
                    pkey_path=conf.get('pkey'),
                    port=conf.get('port', 22)
                )
                
                # Enhance items with listening ports
                for item in items:
                    if not item.get('port') and item['pid'] in pid_port_map:
                        item['port'] = pid_port_map[item['pid']]
                        self.log(f"🔍 Detected port {item['port']} for PID {item['pid']} via netstat")
            except Exception as e:
                self.log(f"⚠️ Could not detect listening ports: {str(e)[:50]}")
            
            self.result_queue.put(('scan_remote', 
                                  {'host': conf['host'], 'items': items, 'idx': idx}))
            self.stats['total_scans'] += 1
        except Exception as e:
            self.result_queue.put(('error', f"Remote scan error for {conf['host']}: {e}"))

    # ============== Probing ==============
    def probe_selected(self):
        """Probe selected items"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Probe', 'Select services to probe')
            return
        
        rows = [self.tree.item(iid)['values'] for iid in sel]
        self.log(f"🔍 Probing {len(rows)} selected service(s)...")
        
        probed_count = 0
        for row in rows:
            target, pid, name, port = row[0], row[1], row[2], row[3]
            
            if not port:
                self.log(f"⚠️ Skipping {name} (PID {pid}) - no port detected")
                continue
            
            self.log(f"🔍 Probing {name} on {target}:{port}...")
            base = f"http://{target}:{port}"
            services = SERVICES + self.custom_services
            
            for svc in services:
                threading.Thread(target=self._probe_worker, 
                               args=(target, port, svc, base), 
                               daemon=True).start()
                probed_count += 1
        
        self.log(f"✅ Started {probed_count} probe(s)")

    def probe_all(self):
        """Probe all discovered services"""
        all_items = self.tree.get_children()
        if not all_items:
            messagebox.showinfo('Probe All', 'No services discovered yet')
            return
        
        self.log(f"🔍 Probing all {len(all_items)} discovered service(s)...")
        
        probed_count = 0
        for iid in all_items:
            vals = self.tree.item(iid)['values']
            target, port = vals[0], vals[3]
            
            if not port:
                continue
            
            base = f"http://{target}:{port}"
            services = SERVICES + self.custom_services
            
            for svc in services:
                threading.Thread(target=self._probe_worker, 
                               args=(target, port, svc, base), 
                               daemon=True).start()
                probed_count += 1
        
        self.log(f"✅ Started {probed_count} probe(s) for {len([v for v in [self.tree.item(i)['values'] for i in all_items] if v[3]])} services with ports")

    def _probe_worker(self, target, port, svc, base):
        """Worker thread for probing"""
        try:
            res = probe_url(base, svc)
            self.result_queue.put(('probe', {
                'target': target,
                'port': port,
                'svc': svc['name'],
                'res': res,
                'critical': svc.get('critical', False)
            }))
            self.stats['total_probes'] += 1
            if not res['ok']:
                self.stats['failed_probes'] += 1
        except Exception as e:
            self.result_queue.put(('error', f"Probe error: {e}"))

    # ============== Polling ==============
    def toggle_polling(self):
        """Toggle automatic polling"""
        if self._polling:
            self._polling = False
            self.poll_button.config(text='▶️ Start Polling')
            self.polling_indicator.config(text='⏸️ Idle', style='Status.TLabel')
            self.log("⏸️ Stopped polling")
        else:
            try:
                interval = int(self.poll_interval_var.get())
                if interval < 5:
                    messagebox.showwarning('Polling', 'Minimum interval is 5 seconds')
                    return
                self._poll_interval = interval
            except ValueError:
                messagebox.showerror('Polling', 'Invalid interval value')
                return
            
            self._polling = True
            self.poll_button.config(text='⏸️ Stop Polling')
            self.polling_indicator.config(text=f'▶️ Active ({self._poll_interval}s)', 
                                         style='Success.TLabel')
            threading.Thread(target=self._poll_loop, daemon=True).start()
            self.log(f"▶️ Started polling (every {self._poll_interval}s)")

    def _poll_loop(self):
        """Main polling loop"""
        while self._polling:
            all_items = self.tree.get_children()
            if all_items:
                for iid in all_items:
                    if not self._polling:
                        break
                    
                    vals = self.tree.item(iid)['values']
                    target, port = vals[0], vals[3]
                    
                    if port:
                        base = f"http://{target}:{port}"
                        services = SERVICES + self.custom_services
                        
                        for svc in services:
                            if not self._polling:
                                break
                            res = probe_url(base, svc)
                            self.result_queue.put(('probe_update', {
                                'iid': iid,
                                'target': target,
                                'port': port,
                                'svc': svc['name'],
                                'res': res,
                                'critical': svc.get('critical', False)
                            }))
            
            # Sleep in small intervals
            for _ in range(self._poll_interval * 2):
                if not self._polling:
                    break
                threading.Event().wait(0.5)

    # ============== Queue Processing ==============
    def _start_queue_poller(self):
        """Start processing result queue"""
        def poll():
            try:
                processed = 0
                while processed < 50:  # Batch process
                    try:
                        ev, payload = self.result_queue.get_nowait()
                        processed += 1
                    except queue.Empty:
                        break
                    
                    try:
                        if ev == 'scan_remote':
                            self._handle_remote_scan(payload)
                        elif ev == 'scan_remote_error':
                            self._handle_scan_error(payload)
                        elif ev == 'probe':
                            self._handle_probe_result(payload)
                        elif ev == 'probe_update':
                            self._handle_probe_result(payload, update=True)
                        elif ev == 'history_success':
                            self._handle_history_success(payload)
                        elif ev == 'history_error':
                            self._handle_history_error(payload)
                        elif ev == 'error':
                            self.log(f"❌ Error: {payload}")
                    except Exception as e:
                        self.log(f"❌ Queue processing error: {e}")
            finally:
                self.update_status_counts()
                self.update_stats()
                self.after(200, poll)
        
        poll()

    def show_alert(self, url, result):
        """Show alert for critical service down"""
        try:
            self.master.bell()
            # Flash the window
            self.master.attributes('-topmost', True)
            self.after(2000, lambda: self.master.attributes('-topmost', False))
        except:
            pass

    def _handle_remote_scan(self, payload):
        """Handle remote scan results"""
        host = payload['host']
        items = payload['items']
        idx = payload.get('idx')
        
        # Update server status
        if idx is not None and idx < len(self.servers):
            self.servers[idx]['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.servers[idx]['last_scan_success'] = True
        
        # Log to server history
        self._add_server_history(host, 'scan', f'Scan completed: {len(items)} processes found')
        
        # Clear old entries for this host
        self._clear_rows_for_target(host)
        
        ports_found = 0
        up_count = 0
        down_count = 0
        
        # Add items directly to tree
        for it in items:
            port = it.get('port', '')
            name = it.get('name', 'java-process')
            pid = it.get('pid', '')
            
            # Build summary
            summary = it.get('jar', '') or it.get('main_class', '') or 'Java Process'
            
            # STATUS BASED ON PORT DETECTION
            if port:
                status = '🟢 UP'
                ports_found += 1
                up_count += 1
                tags = ('up',)
                # Log service up
                self._add_server_history(host, 'status_change', 
                                        f'Service UP: {name} on port {port}',
                                        {'pid': pid, 'port': port, 'name': name})
            else:
                status = '🔴 DOWN'
                down_count += 1
                tags = ('down',)
                # Log service down
                self._add_server_history(host, 'status_change', 
                                        f'Service DOWN: {name} (no port detected)',
                                        {'pid': pid, 'name': name})
            
            # INSERT with status
            self.tree.insert('', 'end', values=(
                host,           # Target
                pid,            # PID
                name,           # Application
                port or 'N/A',  # Port
                '',             # Service
                status,         # Status - UP if port found, DOWN if not
                '',             # Response Time
                datetime.now().strftime('%H:%M:%S'),  # Last Check
                summary         # Details
            ), tags=tags)
        
        # Configure tag colors with professional scheme
        self.tree.tag_configure('up', 
                               background=COLORS['success_light'], 
                               foreground=COLORS['success_dark'])
        self.tree.tag_configure('down', 
                               background=COLORS['error_light'], 
                               foreground=COLORS['error_dark'])
        
        # Log
        total = len(items)
        self.log(f"✅ {host}: {total} processes - {up_count} UP (port detected), {down_count} DOWN (no port)")
        
        # Update counts
        self.refresh_targets()
        if hasattr(self, 'service_count_label'):
            self.service_count_label.config(text=str(len(self.tree.get_children())))
        
        self.update_status_counts()

    def _handle_scan_error(self, payload):
        """Handle scan errors"""
        host = payload['host']
        error = payload['error']
        idx = payload.get('idx')
        
        if idx is not None and idx < len(self.servers):
            self.servers[idx]['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.servers[idx]['last_scan_success'] = False
        
        # Log to server history
        self._add_server_history(host, 'error', f'Scan failed: {error[:100]}', 
                                {'error': error})
        
        self.log(f"❌ {host} scan failed: {error[:100]}")
        self.refresh_targets()
    
    def _handle_history_success(self, payload):
        """Handle successful history fetch"""
        host = payload['host']
        history = payload['history']
        server_config = payload.get('server_config')  # ← ADD THIS LINE
        
        self.log(f"✅ {host} command history retrieved")
        
        # Show in dialog
        UnixHistoryDialog(self.master, host, history, server_config)  # ← ADD server_config
        
    def _handle_history_error(self, payload):
        """Handle history fetch error"""
        host = payload['host']
        error = payload['error']
        
        self.log(f"❌ {host} history fetch failed: {error}")
        messagebox.showerror('History Error', 
                           f'Could not retrieve command history from {host}:\n\n{error}')

    def _handle_probe_result(self, payload, update=False):
        """Handle probe results"""
        target = payload['target']
        port = payload['port']
        svc = payload['svc']
        res = payload['res']
        critical = payload.get('critical', False)
        
        # Store in history
        url = res['url']
        self.history[url].append(res)
        if len(self.history[url]) > MAX_HISTORY_ENTRIES:
            self.history[url] = self.history[url][-MAX_HISTORY_ENTRIES:]
        
        # Check for state change
        prev_state = self.alert_state.get(url, {}).get('last_status')
        if prev_state is not None and prev_state != res['ok']:
            status_text = "UP ✅" if res['ok'] else "DOWN ⚠️"
            self.log(f"🚨 ALERT: {svc} @ {target}:{port} is now {status_text}!")
            if not res['ok'] and critical:
                self.show_alert(url, res)
        
        self.alert_state[url] = {
            'last_status': res['ok'],
            'timestamp': res['timestamp']
        }
        
        # Update tree
        for iid in self.tree.get_children():
            vals = self.tree.item(iid)['values']
            if str(vals[0]) == str(target) and str(vals[3]) == str(port):
                status = '🟢 UP' if res['ok'] else '🔴 DOWN'
                response_time = f"{res.get('response_time', 0):.0f}ms" if res.get('response_time') else 'N/A'
                last_check = datetime.now().strftime('%H:%M:%S')
                
                self.tree.set(iid, 'service', svc)
                self.tree.set(iid, 'status', status)
                self.tree.set(iid, 'response_time', response_time)
                self.tree.set(iid, 'last_check', last_check)
                self.tree.set(iid, 'summary', res.get('summary', '')[:60])
                
                # Apply tags
                if res['ok']:
                    self.tree.item(iid, tags=('up',))
                elif res.get('response_time') and res['response_time'] > 2000:
                    self.tree.item(iid, tags=('warning',))
                else:
                    self.tree.item(iid, tags=('down',))
                
                break
        
        if not update:
            status_icon = "✅" if res['ok'] else "❌"
            rt = f" ({res.get('response_time', 0):.0f}ms)" if res.get('response_time') else ""
            self.log(f"{status_icon} {svc} @ {target}:{port}{rt}")

    def _add_server_history(self, host, event_type, message, details=None):
        """Add event to server history"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,  # 'scan', 'connect', 'error', 'status_change'
            'message': message,
            'details': details
        }
        
        self.server_history[host].append(event)
        
        # Keep only last N events
        if len(self.server_history[host]) > self.max_server_history:
            self.server_history[host] = self.server_history[host][-self.max_server_history:]
        """Show alert for critical service down"""
        try:
            self.master.bell()
            # Flash the window
            self.master.attributes('-topmost', True)
            self.after(2000, lambda: self.master.attributes('-topmost', False))
        except:
            pass

    # ============== UI Helpers ==============
    def _clear_rows_for_target(self, target):
        """Clear tree rows for specific target"""
        for iid in list(self.tree.get_children()):
            vals = self.tree.item(iid)['values']
            if vals[0] == target:
                self.tree.delete(iid)

    def clear_results(self):
        """Clear all results"""
        if messagebox.askyesno('Clear Results', 'Clear all discovered services?'):
            self.tree.delete(*self.tree.get_children())
            self.log("🗑️ Cleared all results")
            self.update_status_counts()

    def apply_filter(self):
        """Apply search filter to tree"""
        search_text = self.search_var.get().lower() if hasattr(self, 'search_var') else ''
        show_all = self.show_all_var.get() if hasattr(self, 'show_all_var') else True
        
        visible_count = 0
        
        # Get ALL children including detached
        all_iids = self.tree.get_children('')
        
        for iid in all_iids:
            try:
                vals = self.tree.item(iid)['values']
                if not vals:
                    continue
                
                # Port is column index 3
                has_port = bool(str(vals[3]).strip()) if len(vals) > 3 else False
                
                should_show = True
                
                # Filter by show_all checkbox
                if not show_all and not has_port:
                    should_show = False
                
                # Filter by search text
                if should_show and search_text:
                    text = ' '.join(str(v).lower() for v in vals)
                    if search_text not in text:
                        should_show = False
                
                # Apply visibility
                if should_show:
                    # Reattach to make visible
                    try:
                        self.tree.reattach(iid, '', 'end')
                        visible_count += 1
                    except tk.TclError:
                        # Already attached, just count it
                        visible_count += 1
                else:
                    # Detach to hide
                    try:
                        self.tree.detach(iid)
                    except tk.TclError:
                        pass
                        
            except Exception as e:
                continue
        
        # Update counts
        self.update_status_counts()
        
        return visible_count

    def refresh_display(self):
        """Refresh the display"""
        self.apply_filter()
        self.update_status_counts()
        self.update_stats()
        self.log("🔄 Display refreshed")

    def sort_tree(self, col):
        """Sort tree by column"""
        items = [(self.tree.set(iid, col), iid) for iid in self.tree.get_children('')]
        
        # Try numeric sort first
        try:
            items.sort(key=lambda x: float(x[0].replace('ms', '').replace('🟢', '').replace('🔴', '').strip()))
        except (ValueError, AttributeError):
            items.sort()
        
        for index, (val, iid) in enumerate(items):
            self.tree.move(iid, '', index)

    def update_status_counts(self):
        """Update status count labels"""
        up_count = 0
        down_count = 0
        unknown_count = 0
        
        # Only count visible items
        for iid in self.tree.get_children(''):
            try:
                status = self.tree.set(iid, 'status')
                if '🟢' in str(status):
                    up_count += 1
                elif '🔴' in str(status):
                    down_count += 1
                else:
                    unknown_count += 1
            except:
                unknown_count += 1
        
        if hasattr(self, 'status_up_label'):
            self.status_up_label.config(text=f'🟢 {up_count}')
        if hasattr(self, 'status_down_label'):
            self.status_down_label.config(text=f'🔴 {down_count}')
        if hasattr(self, 'status_unknown_label'):
            self.status_unknown_label.config(text=f'⚪ {unknown_count}')

    def update_stats(self):
        """Update statistics display"""
        stats_text = (f"Scans: {self.stats['total_scans']} | "
                     f"Probes: {self.stats['total_probes']} | "
                     f"Failed: {self.stats['failed_probes']}")
        self.stats_label.config(text=stats_text)

    def log(self, text):
        """Add message to log with timestamp"""
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f'[{ts}] {text}\n')
        self.log_text.see('end')
        
        # Keep log size manageable
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 500:
            self.log_text.delete('1.0', '100.0')

    # ============== Context Menu ==============
    def show_tree_menu(self, event):
        """Show context menu for tree"""
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.tree_menu.post(event.x_root, event.y_root)

    def copy_url(self):
        """Copy URL to clipboard"""
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0])['values']
            target, port = vals[0], vals[3]
            if port:
                url = f"http://{target}:{port}"
                self.master.clipboard_clear()
                self.master.clipboard_append(url)
                self.log(f"📋 Copied: {url}")

    def open_in_browser(self):
        """Open URL in browser"""
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0])['values']
            target, port = vals[0], vals[3]
            if port:
                url = f"http://{target}:{port}"
                import webbrowser
                webbrowser.open(url)
                self.log(f"🌐 Opened: {url}")

    def delete_selected(self):
        """Delete selected tree items"""
        sel = self.tree.selection()
        if sel and messagebox.askyesno('Delete', f'Delete {len(sel)} item(s)?'):
            for iid in sel:
                self.tree.delete(iid)
            self.update_status_counts()

    def view_details(self):
        """View detailed information for selected item"""
        sel = self.tree.selection()
        if not sel:
            return
        
        vals = self.tree.item(sel[0])['values']
        details = f"""Target: {vals[0]}
PID: {vals[1]}
Application: {vals[2]}
Port: {vals[3]}
Service: {vals[4]}
Status: {vals[5]}
Response Time: {vals[6]}
Last Check: {vals[7]}

Details: {vals[8]}"""
        
        messagebox.showinfo('Service Details', details)

    def view_item_history(self):
        """View history for selected item"""
        sel = self.tree.selection()
        if not sel:
            return
        
        vals = self.tree.item(sel[0])['values']
        target, port = vals[0], vals[3]
        
        if not port:
            messagebox.showinfo('History', 'No port information available')
            return
        
        # Find matching history
        base_url = f"http://{target}:{port}"
        matching_history = []
        
        for url, entries in self.history.items():
            if url.startswith(base_url):
                matching_history.extend(entries[-20:])
        
        if not matching_history:
            messagebox.showinfo('History', 'No history available')
            return
        
        HistoryDialog(self.master, f"{target}:{port}", matching_history)

    # ============== Dialogs ==============
    def add_custom_service(self):
        """Add custom service endpoint"""
        dlg = CustomServiceDialog(self.master)
        self.master.wait_window(dlg.top)
        if dlg.result:
            self.custom_services.append(dlg.result)
            self.log(f"✅ Added custom service: {dlg.result['name']}")
            self.save_config()

    def show_server_history(self):
        """Show real Unix command history from remote server"""
        sel = self.target_listbox.curselection()
        
        if not sel:
            messagebox.showinfo('Server History', 
                              'Please select a server to view its command history.')
            return
        
        idx = sel[0]
        server = self.servers[idx]
        host = server['host']
        
        self.log(f"📜 Fetching command history from {host}...")
        
        # Get history in background thread
        threading.Thread(target=self._fetch_server_history_worker, 
                        args=(server,), daemon=True).start()
    
    def _fetch_server_history_worker(self, server):
        """Worker thread to fetch Unix history from server"""
        try:
            host = server['host']
            history_output, err = get_server_history(
                host, 
                server['username'],
                password=server.get('password'),
                pkey_path=server.get('pkey'),
                port=server.get('port', 22),
                lines=200  # Get last 200 commands
            )
            
            if err:
                self.result_queue.put(('history_error', {
                    'host': host,
                    'error': err
                }))
            else:
                self.result_queue.put(('history_success', {
                    'host': host,
                    'history': history_output,
                    'server_config': server  # ← ADD THIS LINE
                }))
                
        except Exception as e:
            self.result_queue.put(('history_error', {
                'host': server['host'],
                'error': str(e)
            }))
    
    def show_statistics(self):
        """Show detailed statistics"""
        total_services = len(self.tree.get_children())
        up_services = sum(1 for iid in self.tree.get_children() 
                         if '🟢' in self.tree.set(iid, 'status'))
        down_services = sum(1 for iid in self.tree.get_children() 
                           if '🔴' in self.tree.set(iid, 'status'))
        
        avg_response = 0
        response_times = []
        for iid in self.tree.get_children():
            rt = self.tree.set(iid, 'response_time')
            if rt and rt != 'N/A':
                try:
                    response_times.append(float(rt.replace('ms', '')))
                except:
                    pass
        
        if response_times:
            avg_response = sum(response_times) / len(response_times)
            min_response = min(response_times)
            max_response = max(response_times)
        else:
            min_response = max_response = 0
        
        uptime_pct = (up_services / total_services * 100) if total_services > 0 else 0
        
        stats_text = f"""=== System Statistics ===

Targets
  • Configured: {len(self.servers)}
  • Total Services: {total_services}

Service Status
  • Up: {up_services} ({uptime_pct:.1f}%)
  • Down: {down_services}
  • Unknown: {total_services - up_services - down_services}

Operations
  • Total Scans: {self.stats['total_scans']}
  • Total Probes: {self.stats['total_probes']}
  • Failed Probes: {self.stats['failed_probes']}

Performance
  • Avg Response: {avg_response:.1f}ms
  • Min Response: {min_response:.1f}ms
  • Max Response: {max_response:.1f}ms

History
  • Tracked URLs: {len(self.history)}
  • Total Entries: {sum(len(h) for h in self.history.values())}
"""
        messagebox.showinfo('Statistics', stats_text)

    def show_history(self):
        """Show complete history"""
        if not self.history:
            messagebox.showinfo('History', 'No history available')
            return
        
        all_entries = []
        for entries in self.history.values():
            all_entries.extend(entries[-50:])
        
        HistoryDialog(self.master, "All Services", all_entries)

    def show_about(self):
        """Show about dialog"""
        about_text = """PortiX
Java Process & Service Monitor
Version 2.0

A comprehensive monitoring tool for remote Java 
applications and services with real-time status 
tracking and port detection.

Features:
  • Remote process scanning via SSH
  • Automatic port detection
  • Real-time UP/DOWN status
  • Multi-target management
  • Service health monitoring
  • History tracking & analytics
  • Modern, responsive UI

Designed for production monitoring of 
Java microservices and applications.

© 2025 PortiX"""
        
        messagebox.showinfo('About PortiX', about_text)

    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """=== Keyboard Shortcuts ===

File Operations
  Ctrl+N - Add Remote Target
  Ctrl+S - Save Configuration
  Ctrl+E - Export Results
  Ctrl+Q - Exit Application

Scanning
  F5 - Scan Selected Target
  Ctrl+F5 - Scan All Targets
  Ctrl+Space - Toggle Auto Polling

View & Navigation
  Ctrl+I - Show Statistics
  Ctrl+H - Show History
  Ctrl+L - Clear Log
  Delete - Remove Selected
  F1 - Show This Help

Context Menu
  Right-click on services for more options
  Double-click target to scan
"""
        messagebox.showinfo('Keyboard Shortcuts', shortcuts)

    def toggle_autoscroll(self):
        """Toggle auto-scroll for log"""
        # This is a placeholder - implement if needed
        pass

    # ============== Import/Export ==============
    def export_results(self):
        """Export current results to JSON"""
        filename = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
            initialfile=f'monitor_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        
        if not filename:
            return
        
        data = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid)['values']
            data.append({
                'target': vals[0],
                'pid': vals[1],
                'name': vals[2],
                'port': vals[3],
                'service': vals[4],
                'status': vals[5],
                'response_time': vals[6],
                'last_check': vals[7],
                'summary': vals[8]
            })
        
        try:
            with open(filename, 'w') as f:
                json.dump({
                    'export_time': datetime.now().isoformat(),
                    'total_services': len(data),
                    'services': data
                }, f, indent=2)
            self.log(f"✅ Exported {len(data)} results to {filename}")
            messagebox.showinfo('Export', f'Exported {len(data)} results successfully')
        except Exception as e:
            messagebox.showerror('Export Error', str(e))

    def export_history(self):
        """Export history to JSON"""
        filename = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
            initialfile=f'monitor_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w') as f:
                json.dump({
                    'export_time': datetime.now().isoformat(),
                    'history': dict(self.history)
                }, f, indent=2)
            
            total_entries = sum(len(h) for h in self.history.values())
            self.log(f"✅ Exported {total_entries} history entries")
            messagebox.showinfo('Export', f'Exported {total_entries} entries successfully')
        except Exception as e:
            messagebox.showerror('Export Error', str(e))

    def save_log(self):
        """Save log to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialfile=f'monitor_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w') as f:
                f.write(self.log_text.get('1.0', 'end'))
            self.log(f"✅ Saved log to {filename}")
        except Exception as e:
            messagebox.showerror('Save Error', str(e))

    # ============== Configuration ==============
    def save_config(self):
        """Save configuration to file"""
        try:
            config = {
                'servers': self.servers,
                'custom_services': self.custom_services,
                'poll_interval': self._poll_interval
            }
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.log(f"✅ Configuration saved")
            messagebox.showinfo('Save Config', 'Configuration saved successfully')
        except Exception as e:
            messagebox.showerror('Save Error', str(e))

    def load_config(self):
        """Load configuration from file"""
        filename = filedialog.askopenfilename(
            defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
            initialfile=CONFIG_FILE.name
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'r') as f:
                config = json.load(f)
            
            self.servers = config.get('servers', [])
            self.custom_services = config.get('custom_services', [])
            self._poll_interval = config.get('poll_interval', DEFAULT_POLL_SECONDS)
            
            self.refresh_targets()
            self.log(f"✅ Configuration loaded")
            messagebox.showinfo('Load Config', 'Configuration loaded successfully')
        except Exception as e:
            messagebox.showerror('Load Error', str(e))

    def _load_config(self):
        """Auto-load configuration on startup"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                
                self.servers = config.get('servers', [])
                self.custom_services = config.get('custom_services', [])
                self._poll_interval = config.get('poll_interval', DEFAULT_POLL_SECONDS)
                
                self.refresh_targets()
                self.log(f"✅ Configuration loaded from {CONFIG_FILE.name}")
            except Exception as e:
                self.log(f"⚠️ Could not load config: {e}")

# ============== Dialogs ==============
class RemoteDialog:
    """Dialog for adding/editing remote SSH targets"""
    def __init__(self, master, edit_data=None):
        self.top = tk.Toplevel(master)
        self.top.title("Remote Target Configuration")
        self.top.geometry('500x450')
        self.result = None
        self.edit_data = edit_data
        self._build()
        
        # Center dialog
        self.top.transient(master)
        self.top.grab_set()
        
        # Center on screen
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f'500x450+{x}+{y}')

    def _build(self):
        # Title
        title_frame = ttk.Frame(self.top, padding=20)
        title_frame.pack(fill='x')
        
        title_text = "Edit Target" if self.edit_data else "Add Remote Target"
        ttk.Label(title_frame, text=title_text, font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        
        # Fields
        fields_frame = ttk.Frame(self.top, padding=(20, 0, 20, 0))
        fields_frame.pack(fill='both', expand=True)
        
        self.vars = {}
        
        # Host
        ttk.Label(fields_frame, text='Host *').pack(anchor='w', pady=(5, 2))
        self.vars['host'] = tk.StringVar(value=self.edit_data.get('host', '') if self.edit_data else '')
        ttk.Entry(fields_frame, textvariable=self.vars['host']).pack(fill='x', pady=(0, 10))
        
        # Port
        ttk.Label(fields_frame, text='Port').pack(anchor='w', pady=(5, 2))
        self.vars['port'] = tk.StringVar(value=str(self.edit_data.get('port', 22)) if self.edit_data else '22')
        ttk.Entry(fields_frame, textvariable=self.vars['port']).pack(fill='x', pady=(0, 10))
        
        # Username
        ttk.Label(fields_frame, text='Username *').pack(anchor='w', pady=(5, 2))
        self.vars['username'] = tk.StringVar(value=self.edit_data.get('username', '') if self.edit_data else '')
        ttk.Entry(fields_frame, textvariable=self.vars['username']).pack(fill='x', pady=(0, 10))
        
        # Password
        ttk.Label(fields_frame, text='Password').pack(anchor='w', pady=(5, 2))
        self.vars['password'] = tk.StringVar(value=self.edit_data.get('password', '') if self.edit_data else '')
        ttk.Entry(fields_frame, textvariable=self.vars['password'], show='•').pack(fill='x', pady=(0, 10))
        
        # Private Key
        ttk.Label(fields_frame, text='Private Key Path').pack(anchor='w', pady=(5, 2))
        key_frame = ttk.Frame(fields_frame)
        key_frame.pack(fill='x', pady=(0, 10))
        
        self.vars['pkey'] = tk.StringVar(value=self.edit_data.get('pkey', '') if self.edit_data else '')
        ttk.Entry(key_frame, textvariable=self.vars['pkey']).pack(side='left', fill='x', expand=True)
        ttk.Button(key_frame, text='Browse', command=self._browse_key).pack(side='right', padx=(5, 0))
        
        # Info
        info_frame = ttk.LabelFrame(fields_frame, text='Info', padding=10)
        info_frame.pack(fill='x', pady=(10, 0))
        ttk.Label(info_frame, text='Use password OR private key\nPrivate key recommended for security', 
                 font=('Segoe UI', 9)).pack(anchor='w')
        
        # Buttons at bottom
        btn_frame = ttk.Frame(self.top, padding=20)
        btn_frame.pack(fill='x', side='bottom')
        
        save_text = 'Update' if self.edit_data else 'Add Target'
        ttk.Button(btn_frame, text=save_text, command=self.on_ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.top.destroy).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Test', command=self.test_connection).pack(side='left', padx=5)

    def _browse_key(self):
        filename = filedialog.askopenfilename(title='Select Private Key')
        if filename:
            self.vars['pkey'].set(filename)

    def test_connection(self):
        """Test SSH connection"""
        data = self._get_data()
        if not data:
            return
        
        try:
            self.top.config(cursor='watch')
            self.top.update()
            
            out, err = ssh_run(data['host'], data['username'],
                             password=data.get('password'),
                             pkey_path=data.get('pkey'),
                             port=data.get('port', 22),
                             timeout=5,
                             cmd='echo "OK"')
            
            if 'OK' in out:
                messagebox.showinfo('Test', 'Connection successful!', parent=self.top)
            else:
                messagebox.showerror('Test', f'Failed:\n{err}', parent=self.top)
        except Exception as e:
            messagebox.showerror('Test', f'Error:\n{str(e)}', parent=self.top)
        finally:
            self.top.config(cursor='')

    def _get_data(self):
        """Get and validate data"""
        data = {}
        for k, v in self.vars.items():
            val = v.get().strip()
            if val:
                data[k] = val
        
        if not data.get('host'):
            messagebox.showerror('Error', 'Host is required', parent=self.top)
            return None
        
        if not data.get('username'):
            messagebox.showerror('Error', 'Username is required', parent=self.top)
            return None
        
        # Set default port
        if 'port' not in data:
            data['port'] = 22
        else:
            try:
                data['port'] = int(data['port'])
            except:
                messagebox.showerror('Error', 'Port must be a number', parent=self.top)
                return None
        
        return data

    def on_ok(self):
        data = self._get_data()
        if data:
            self.result = data
            self.top.destroy()

class CustomServiceDialog:
    """Dialog for adding custom service endpoints"""
    def __init__(self, master):
        self.top = tk.Toplevel(master)
        self.top.title("Add Custom Service")
        self.top.geometry('450x280')
        self.top.resizable(False, False)
        self.result = None
        self._build()
        
        self.top.transient(master)
        self.top.grab_set()
        
        # Center on screen
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (self.top.winfo_width() // 2)
        y = (self.top.winfo_screenheight() // 2) - (self.top.winfo_height() // 2)
        self.top.geometry(f'+{x}+{y}')

    def _build(self):
        frm = ttk.Frame(self.top, padding=20)
        frm.pack(fill='both', expand=True)
        frm.grid_columnconfigure(1, weight=1)
        
        ttk.Label(frm, text='Custom Service Endpoint', 
                 font=('Segoe UI', 14, 'bold')).grid(
            row=0, column=0, columnspan=2, pady=(0, 15), sticky='w')
        
        ttk.Label(frm, text='Service Name:').grid(row=1, column=0, sticky='w', pady=8)
        self.name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.name_var, width=35).grid(
            row=1, column=1, sticky='we', pady=8)
        
        ttk.Label(frm, text='Path:').grid(row=2, column=0, sticky='w', pady=8)
        self.path_var = tk.StringVar(value='/')
        ttk.Entry(frm, textvariable=self.path_var, width=35).grid(
            row=2, column=1, sticky='we', pady=8)
        
        ttk.Label(frm, text='Expected Text:').grid(row=3, column=0, sticky='w', pady=8)
        self.expect_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.expect_var, width=35).grid(
            row=3, column=1, sticky='we', pady=8)
        
        self.critical_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text='Critical (trigger alerts on failure)', 
                       variable=self.critical_var).grid(
                           row=4, column=0, columnspan=2, sticky='w', pady=10)
        
        # Example
        example_frame = ttk.Frame(frm, relief='solid', borderwidth=1, padding=8)
        example_frame.grid(row=5, column=0, columnspan=2, sticky='we', pady=(5, 0))
        
        ttk.Label(example_frame, text='Example:', 
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        ttk.Label(example_frame, 
                 text='Name: My API Health\n'
                      'Path: /api/health\n'
                      'Expected: "healthy"',
                 font=('Segoe UI', 9),
                 foreground='gray').pack(anchor='w', pady=(3, 0))
        
        # Buttons
        btnf = ttk.Frame(frm)
        btnf.grid(row=6, column=0, columnspan=2, pady=(15, 0))
        
        ttk.Button(btnf, text='Add Service', command=self.on_ok, 
                  width=15, style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(btnf, text='Cancel', command=self.top.destroy, 
                  width=15).pack(side='left', padx=5)

    def on_ok(self):
        name = self.name_var.get().strip()
        path = self.path_var.get().strip()
        
        if not name:
            messagebox.showerror('Validation', 'Service name is required')
            return
        
        if not path:
            messagebox.showerror('Validation', 'Path is required')
            return
        
        if not path.startswith('/'):
            path = '/' + path
        
        self.result = {
            'name': name,
            'path': path,
            'expect': self.expect_var.get().strip(),
            'critical': self.critical_var.get()
        }
        self.top.destroy()

# Add this enhanced UnixHistoryDialog class to replace the existing one in the script

class UnixHistoryDialog:
    """Enhanced dialog for viewing Unix command history and running commands on remote server"""
    def __init__(self, master, host, history_output, server_config=None):
        self.top = tk.Toplevel(master)
        self.top.title(f"Server Terminal - {host}")
        self.top.geometry('1200x900')        
        self.host = host
        self.server_config = server_config
        self.command_queue = queue.Queue()
        
        frm = ttk.Frame(self.top, padding=15)
        frm.pack(fill='both', expand=True)
        frm.grid_rowconfigure(1, weight=1)
        frm.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ttk.Frame(frm)
        header.grid(row=0, column=0, sticky='we', pady=(0, 10))
        header.grid_columnconfigure(1, weight=1)
        
        ttk.Label(header, text=f'🖥️  Server Terminal: {host}', 
                 font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, sticky='w')
        
        # Status indicator
        self.status_label = ttk.Label(header, text='● Connected', 
                                     font=('Segoe UI', 10, 'bold'),
                                     foreground='#28a745')
        self.status_label.grid(row=0, column=1, sticky='e')
        
        # Export button
        ttk.Button(header, text='💾 Export', 
                  command=lambda: self.export_history(host, history_output)).grid(
                      row=0, column=2, padx=5)
        
        # Command history list
        history_frame = ttk.LabelFrame(frm, text='📜 Command History (Recent 200 Commands)', 
                                      padding=10)
        history_frame.grid(row=1, column=0, sticky='nswe', pady=(0, 10))
        history_frame.grid_rowconfigure(1, weight=1)
        history_frame.grid_columnconfigure(0, weight=1)
        
        # Search bar - MOVED TO TOP OF HISTORY FRAME
        search_frame = ttk.Frame(history_frame)
        search_frame.grid(row=0, column=0, sticky='we', pady=(0, 10))
        search_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(search_frame, text='🔎 Search:').grid(row=0, column=0, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.filter_history())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky='we', padx=2)
        
        ttk.Button(search_frame, text='✖ Clear', 
                  command=lambda: self.search_var.set('')).grid(row=0, column=2, padx=2)
        
        # Info label
        self.info_label = ttk.Label(search_frame, text='Tip: Double-click to run command', 
                                    foreground='#6c757d', font=('Segoe UI', 9))
        self.info_label.grid(row=0, column=3, padx=15)
        
        # Listbox for command history
        list_container = ttk.Frame(history_frame, relief='sunken', borderwidth=1)
        list_container.grid(row=1, column=0, sticky='nswe')
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        self.history_listbox = tk.Listbox(list_container, 
                                         font=('Consolas', 10),
                                         selectmode='extended',
                                         activestyle='none',
                                         bg='#f8f9fa',
                                         relief='flat',
                                         height=20)  # Reduced height since we have more space
        self.history_listbox.grid(row=0, column=0, sticky='nswe')
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_container, orient='vertical', 
                           command=self.history_listbox.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        self.history_listbox.configure(yscrollcommand=vsb.set)
        
        # Parse and populate history
        self.parse_and_populate(history_output)
        
        # Double-click to run command
        self.history_listbox.bind('<Double-Button-1>', self.run_selected_command)
        
        # Context menu for listbox
        self.list_menu = tk.Menu(self.history_listbox, tearoff=0)
        self.list_menu.add_command(label="▶ Run Command", command=self.run_selected_command)
        self.list_menu.add_command(label="📋 Copy Command", command=self.copy_selected_command)
        self.list_menu.add_separator()
        self.list_menu.add_command(label="🔍 Filter Similar", command=self.filter_similar)
        
        self.history_listbox.bind('<Button-3>', self.show_list_menu)
        
        # Command execution section - SIMPLIFIED WITHOUT QUICK COMMANDS
        exec_frame = ttk.LabelFrame(frm, text='⚡ Execute Commands on Server', padding=10)
        exec_frame.grid(row=2, column=0, sticky='nswe')
        exec_frame.grid_rowconfigure(1, weight=1)
        exec_frame.grid_columnconfigure(0, weight=1)
        
        # Command input
        cmd_input_frame = ttk.Frame(exec_frame)
        cmd_input_frame.grid(row=0, column=0, sticky='we', pady=(0, 10))
        cmd_input_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(cmd_input_frame, text='Command:', 
                 font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=(0, 5))
        
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(cmd_input_frame, 
                                      textvariable=self.command_var,
                                      font=('Consolas', 11))
        self.command_entry.grid(row=0, column=1, sticky='we', padx=5)
        self.command_entry.bind('<Return>', lambda e: self.execute_command())
        self.command_entry.focus()
        
        ttk.Button(cmd_input_frame, text='▶ Execute', 
                  command=self.execute_command,
                  style='Primary.TButton').grid(row=0, column=2, padx=5)
        
        ttk.Button(cmd_input_frame, text='📋 Paste', 
                  command=self.paste_from_clipboard).grid(row=0, column=3, padx=2)
        
        # Output area
        output_container = ttk.Frame(exec_frame)
        output_container.grid(row=1, column=0, sticky='nswe', pady=(10, 0))
        output_container.grid_rowconfigure(0, weight=1)
        output_container.grid_columnconfigure(0, weight=1)
        
        self.output_text = tk.Text(output_container, 
                                   font=('Consolas', 10),
                                   bg='#0d1b2a',
                                   fg='#00ff41',
                                   wrap='none',
                                   relief='sunken',
                                   borderwidth=2,
                                   height=12)  # Increased height since we removed quick commands
        self.output_text.grid(row=0, column=0, sticky='nswe')
        
        # Scrollbars for output
        out_vsb = ttk.Scrollbar(output_container, orient='vertical', 
                               command=self.output_text.yview)
        out_vsb.grid(row=0, column=1, sticky='ns')
        out_hsb = ttk.Scrollbar(output_container, orient='horizontal',
                               command=self.output_text.xview)
        out_hsb.grid(row=1, column=0, sticky='we')
        self.output_text.configure(yscrollcommand=out_vsb.set, 
                                  xscrollcommand=out_hsb.set)
        
        # Initial message
        self.log_output(f"╔{'═'*58}╗\n", '#00d4ff')
        self.log_output(f"║  Connected to {host:48} ║\n", '#00d4ff')
        self.log_output(f"║  Type commands to execute on remote server{' '*15}║\n", '#00d4ff')
        self.log_output(f"╚{'═'*58}╝\n\n", '#00d4ff')
        
        # Output controls
        output_ctrl = ttk.Frame(exec_frame)
        output_ctrl.grid(row=2, column=0, sticky='we', pady=(5, 0))
        
        ttk.Button(output_ctrl, text='🗑️ Clear Output', 
                  command=lambda: self.output_text.delete('1.0', 'end')).pack(side='left', padx=2)
        ttk.Button(output_ctrl, text='💾 Save Output', 
                  command=self.save_output).pack(side='left', padx=2)
        ttk.Button(output_ctrl, text='📋 Copy Output', 
                  command=self.copy_output).pack(side='left', padx=2)
        
        # Stats
        stats_frame = ttk.Frame(frm)
        stats_frame.grid(row=3, column=0, sticky='we', pady=(10, 0))
        
        lines = history_output.strip().split('\n') if history_output else []
        self.stats_label = ttk.Label(stats_frame, 
                                     text=f"Total Commands in History: {len(lines)}  |  Server: {host}",
                                     font=('Segoe UI', 10))
        self.stats_label.pack(side='left')
        
        # Close button
        ttk.Button(stats_frame, text='Close', 
                  command=self.top.destroy, width=15).pack(side='right')
        
        self.top.transient(master)
        self.history_output = history_output
        self.all_commands = []
        
        # Start queue processor
        self.start_queue_processor()
    
    def parse_and_populate(self, history_output):
        """Parse history and populate listbox"""
        if not history_output:
            self.info_label.config(text='❌ No history data received from server!')
            return
        
        lines = history_output.strip().split('\n')
        
        self.all_commands = []
        
        for idx, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            # Try to parse numbered format: "  123  command"
            match = re.match(r'^\s*(\d+)\s+(.*)$', line)
            if match:
                line_num = match.group(1)
                command = match.group(2)
                self.all_commands.append((line_num, command))
            else:
                # Plain command without number - ADD OUR OWN NUMBER
                self.all_commands.append((str(idx), line))
        
        # Populate listbox
        self.update_listbox_display()
        
        # Update info with count
        if self.all_commands:
            self.info_label.config(text=f'✅ Loaded {len(self.all_commands)} commands from history')
        else:
            self.info_label.config(text='⚠️ History data received but no valid commands found')
    
    def update_listbox_display(self):
        """Update listbox with filtered commands"""
        self.history_listbox.delete(0, tk.END)
        
        # SAFETY CHECK - search_var might not exist yet
        try:
            search_text = self.search_var.get().lower()
        except AttributeError:
            search_text = ''
        
        count = 0
        
        for line_num, command in self.all_commands:
            if not search_text or search_text in command.lower():
                display = f"{line_num:>6}  {command}" if line_num else f"        {command}"
                self.history_listbox.insert(tk.END, display)
                count += 1
                
                # Color code important commands
                if any(keyword in command.lower() for keyword in ['sudo', 'rm -', 'kill ']):
                    self.history_listbox.itemconfig(tk.END, fg='#dc3545')
                elif any(keyword in command.lower() for keyword in ['java', 'mvn', 'gradle', 'jar']):
                    self.history_listbox.itemconfig(tk.END, fg='#28a745')
                elif any(keyword in command.lower() for keyword in ['docker', 'kubectl', 'systemctl', 'service']):
                    self.history_listbox.itemconfig(tk.END, fg='#0078d4')
        
        # Update info label
        if search_text:
            self.info_label.config(text=f'Found {count} matching commands')
        else:
            self.info_label.config(text='Tip: Double-click to run command')
    
    def filter_history(self):
        """Filter history based on search"""
        self.update_listbox_display()
    
    def show_list_menu(self, event):
        """Show context menu for listbox"""
        # Select the item under cursor
        index = self.history_listbox.nearest(event.y)
        self.history_listbox.selection_clear(0, tk.END)
        self.history_listbox.selection_set(index)
        self.history_listbox.activate(index)
        
        self.list_menu.post(event.x_root, event.y_root)
    
    def copy_selected_command(self):
        """Copy selected command to clipboard"""
        selection = self.history_listbox.curselection()
        if not selection:
            return
        
        item = self.history_listbox.get(selection[0])
        match = re.match(r'^\s*\d*\s*(.*)$', item)
        if match:
            command = match.group(1).strip()
            self.top.clipboard_clear()
            self.top.clipboard_append(command)
            self.info_label.config(text='Command copied to clipboard')
    
    def filter_similar(self):
        """Filter commands similar to selected"""
        selection = self.history_listbox.curselection()
        if not selection:
            return
        
        item = self.history_listbox.get(selection[0])
        match = re.match(r'^\s*\d*\s*(.*)$', item)
        if match:
            command = match.group(1).strip()
            # Get first word as filter
            first_word = command.split()[0] if command.split() else ''
            if first_word:
                self.search_var.set(first_word)
    
    def run_selected_command(self, event=None):
        """Run selected command from history"""
        selection = self.history_listbox.curselection()
        if not selection:
            return
        
        # Get selected command
        item = self.history_listbox.get(selection[0])
        # Extract command (remove line number if present)
        match = re.match(r'^\s*\d*\s*(.*)$', item)
        if match:
            command = match.group(1).strip()
            self.command_var.set(command)
            self.execute_command()
    
    def execute_command(self):
        """Execute command on remote server"""
        command = self.command_var.get().strip()
        
        if not command:
            messagebox.showwarning('Execute', 'Please enter a command', parent=self.top)
            return
        
        if not self.server_config:
            messagebox.showerror('Execute', 'No server configuration available', parent=self.top)
            return
        
        # Confirm dangerous commands
        dangerous_keywords = ['rm -rf', 'dd if=', 'mkfs', ':(){:|:&};:', 'shutdown', 'reboot', 'init 0', 'halt']
        if any(keyword in command for keyword in dangerous_keywords):
            if not messagebox.askyesno('⚠️  Dangerous Command', 
                                      f'This command may be DANGEROUS:\n\n{command}\n\n'
                                      f'It could cause data loss or system shutdown.\n\n'
                                      f'Are you SURE you want to continue?',
                                      parent=self.top):
                return
        
        self.log_output(f"\n╭─ $ ", '#00d4ff')
        self.log_output(f"{command}\n", '#ffffff')
        self.log_output(f"╰─{'─'*60}\n", '#00d4ff')
        
        self.status_label.config(text='⏳ Executing...', foreground='#ffc107')
        self.command_entry.config(state='disabled')
        
        # Execute in background thread
        threading.Thread(target=self._execute_worker, args=(command,), daemon=True).start()
    
    def _execute_worker(self, command):
        """Worker thread to execute command"""
        try:
            out, err = ssh_run(
                self.server_config['host'],
                self.server_config['username'],
                password=self.server_config.get('password'),
                pkey_path=self.server_config.get('pkey'),
                port=self.server_config.get('port', 22),
                cmd=command,
                timeout=30
            )
            
            self.command_queue.put(('success', {'output': out, 'error': err}))
            
        except Exception as e:
            self.command_queue.put(('error', str(e)))
    
    def start_queue_processor(self):
        """Process command execution results"""
        def process():
            try:
                while True:
                    try:
                        event_type, data = self.command_queue.get_nowait()
                        
                        if event_type == 'success':
                            output = data['output']
                            error = data['error']
                            
                            if output:
                                self.log_output(output, '#00ff41')
                            
                            if error:
                                self.log_output(f"\n⚠️  Error:\n", '#ffc107')
                                self.log_output(f"{error}\n", '#ef4444')
                            
                            if not output and not error:
                                self.log_output("(no output)\n", '#8892b0')
                            
                            self.log_output(f"\n{'─'*60}\n", '#00d4ff')
                            
                            self.status_label.config(text='✓ Connected', 
                                                   foreground='#28a745')
                            
                        elif event_type == 'error':
                            self.log_output(f"\n❌ Execution Error:\n", '#ef4444')
                            self.log_output(f"{data}\n", '#ef4444')
                            self.log_output(f"\n{'─'*60}\n", '#00d4ff')
                            
                            self.status_label.config(text='✗ Error', 
                                                   foreground='#dc3545')
                        
                    except queue.Empty:
                        break
            finally:
                self.command_entry.config(state='normal')
                self.top.after(100, process)
        
        process()
    
    def log_output(self, text, color='#00ff41'):
        """Log output to text widget with color"""
        self.output_text.config(state='normal')
        
        tag_name = f'color_{color.replace("#", "")}'
        self.output_text.tag_configure(tag_name, foreground=color)
        
        self.output_text.insert('end', text, tag_name)
        self.output_text.see('end')
        
        self.output_text.config(state='disabled')
    
    def paste_from_clipboard(self):
        """Paste from clipboard to command entry"""
        try:
            clipboard_text = self.top.clipboard_get()
            self.command_var.set(clipboard_text)
        except:
            pass
    
    def save_output(self):
        """Save output to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialfile=f'{self.host}_output_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
            parent=self.top
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w') as f:
                f.write(self.output_text.get('1.0', 'end'))
            
            messagebox.showinfo('Save', f'Output saved to:\n{filename}', parent=self.top)
        except Exception as e:
            messagebox.showerror('Save Error', str(e), parent=self.top)
    
    def copy_output(self):
        """Copy output to clipboard"""
        output = self.output_text.get('1.0', 'end')
        self.top.clipboard_clear()
        self.top.clipboard_append(output)
        self.info_label.config(text='Output copied to clipboard')
    
    def export_history(self, host, history_output):
        """Export history to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialfile=f'{host}_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
            parent=self.top
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w') as f:
                f.write(f"Unix Command History - {host}\n")
                f.write(f"Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                f.write(history_output)
            
            messagebox.showinfo('Export', f'History exported to:\n{filename}', parent=self.top)
        except Exception as e:
            messagebox.showerror('Export Error', str(e), parent=self.top)
class ServerHistoryDialog:
    """Dialog for viewing server history like Unix history command"""
    def __init__(self, master, title, server_history):
        self.top = tk.Toplevel(master)
        self.top.title(f"Server History - {title}")
        self.top.geometry('1000x700')
        
        frm = ttk.Frame(self.top, padding=15)
        frm.pack(fill='both', expand=True)
        frm.grid_rowconfigure(1, weight=1)
        frm.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ttk.Frame(frm)
        header.grid(row=0, column=0, sticky='we', pady=(0, 10))
        
        ttk.Label(header, text=f'📜 Server History: {title}', 
                 font=('Segoe UI', 14, 'bold')).pack(side='left')
        
        # Export button
        ttk.Button(header, text='💾 Export', 
                  command=lambda: self.export_history(server_history)).pack(side='right', padx=5)
        ttk.Button(header, text='🔄 Refresh', 
                  command=lambda: self.refresh_history(server_history)).pack(side='right', padx=5)
        
        # Tree with history
        tree_frame = ttk.Frame(frm, relief='sunken', borderwidth=1)
        tree_frame.grid(row=1, column=0, sticky='nswe')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        cols = ('id', 'timestamp', 'server', 'type', 'message')
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        
        self.tree.heading('id', text='#')
        self.tree.heading('timestamp', text='Timestamp')
        self.tree.heading('server', text='Server')
        self.tree.heading('type', text='Type')
        self.tree.heading('message', text='Event')
        
        self.tree.column('id', width=50, stretch=False)
        self.tree.column('timestamp', width=150, stretch=False)
        self.tree.column('server', width=150, stretch=False)
        self.tree.column('type', width=100, stretch=False)
        self.tree.column('message', width=500, stretch=True)
        
        # Add data - sorted by timestamp
        all_events = []
        for host, events in server_history.items():
            for event in events:
                all_events.append((host, event))
        
        # Sort by timestamp (newest first)
        all_events.sort(key=lambda x: x[1]['timestamp'], reverse=True)
        
        # Add to tree with colors
        for idx, (host, event) in enumerate(all_events, 1):
            event_type = event['type']
            timestamp = event['timestamp'][:19]  # Remove microseconds
            message = event['message']
            
            # Color code by type
            if event_type == 'scan':
                tags = ('scan',)
            elif event_type == 'error':
                tags = ('error',)
            elif event_type == 'status_change':
                if '🟢' in message or 'UP' in message:
                    tags = ('up',)
                else:
                    tags = ('down',)
            else:
                tags = ()
            
            self.tree.insert('', 'end', values=(
                idx, timestamp, host, event_type.upper(), message
            ), tags=tags)
        
        # Configure tags
        self.tree.tag_configure('scan', foreground='#0078d4')
        self.tree.tag_configure('up', foreground='#28a745', font=('Segoe UI', 9, 'bold'))
        self.tree.tag_configure('down', foreground='#dc3545', font=('Segoe UI', 9, 'bold'))
        self.tree.tag_configure('error', foreground='#dc3545', background='#f8d7da')
        
        self.tree.grid(row=0, column=0, sticky='nswe')
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky='we')
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Stats
        stats_frame = ttk.Frame(frm)
        stats_frame.grid(row=2, column=0, sticky='we', pady=(10, 0))
        
        total_events = len(all_events)
        servers_count = len(server_history)
        scan_count = sum(1 for _, e in all_events if e['type'] == 'scan')
        error_count = sum(1 for _, e in all_events if e['type'] == 'error')
        
        
        stats_text = f"Total Events: {total_events}  |  Servers: {servers_count}  |  Scans: {scan_count}  |  Errors: {error_count}"
        ttk.Label(stats_frame, text=stats_text, font=('Segoe UI', 10)).pack(side='left')
        
        # Close button
        ttk.Button(frm, text='Close', command=self.top.destroy, 
                  width=15).grid(row=3, column=0, pady=(10, 0))
        
        self.top.transient(master)
        self.server_history = server_history
    
    def refresh_history(self, server_history):
        """Refresh the history display"""
        # Clear and reload
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Reload data
        all_events = []
        for host, events in server_history.items():
            for event in events:
                all_events.append((host, event))
        
        all_events.sort(key=lambda x: x[1]['timestamp'], reverse=True)
        
        for idx, (host, event) in enumerate(all_events, 1):
            event_type = event['type']
            timestamp = event['timestamp'][:19]
            message = event['message']
            
            if event_type == 'scan':
                tags = ('scan',)
            elif event_type == 'error':
                tags = ('error',)
            elif event_type == 'status_change':
                tags = ('up',) if 'UP' in message else ('down',)
            else:
                tags = ()
            
            self.tree.insert('', 'end', values=(
                idx, timestamp, host, event_type.upper(), message
            ), tags=tags)
    
    def export_history(self, server_history):
        """Export history to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('JSON files', '*.json'), ('All files', '*.*')],
            initialfile=f'server_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )
        
        if not filename:
            return
        
        try:
            all_events = []
            for host, events in server_history.items():
                for event in events:
                    all_events.append((host, event))
            
            all_events.sort(key=lambda x: x[1]['timestamp'], reverse=True)
            
            if filename.endswith('.json'):
                # Export as JSON
                import json
                export_data = {
                    'export_time': datetime.now().isoformat(),
                    'servers': dict(server_history)
                }
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2)
            else:
                # Export as text (like Unix history)
                with open(filename, 'w') as f:
                    f.write(f"PortiX Server History\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    for idx, (host, event) in enumerate(all_events, 1):
                        f.write(f"{idx:4d}  {event['timestamp'][:19]}  [{host}]  {event['type'].upper()}\n")
                        f.write(f"      {event['message']}\n")
                        if event.get('details'):
                            f.write(f"      Details: {event['details']}\n")
                        f.write("\n")
            
            messagebox.showinfo('Export', f'History exported to:\n{filename}')
        except Exception as e:
            messagebox.showerror('Export Error', str(e))

class HistoryDialog:
    """Dialog for viewing service history"""
    def __init__(self, master, title, history_entries):
        self.top = tk.Toplevel(master)
        self.top.title(f"History - {title}")
        self.top.geometry('900x600')
        
        frm = ttk.Frame(self.top, padding=15)
        frm.pack(fill='both', expand=True)
        frm.grid_rowconfigure(1, weight=1)
        frm.grid_columnconfigure(0, weight=1)
        
        # Header
        ttk.Label(frm, text=f'📈 Service History: {title}', 
                 font=('Segoe UI', 14, 'bold')).grid(
            row=0, column=0, sticky='w', pady=(0, 10))
        
        # Tree
        tree_frame = ttk.Frame(frm, relief='sunken', borderwidth=1)
        tree_frame.grid(row=1, column=0, sticky='nswe')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        cols = ('timestamp', 'status', 'response_time', 'status_code', 'summary')
        tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        
        tree.heading('timestamp', text='Timestamp')
        tree.heading('status', text='Status')
        tree.heading('response_time', text='Response Time')
        tree.heading('status_code', text='HTTP Code')
        tree.heading('summary', text='Details')
        
        tree.column('timestamp', width=150, stretch=False)
        tree.column('status', width=80, stretch=False)
        tree.column('response_time', width=100, stretch=False)
        tree.column('status_code', width=80, stretch=False)
        tree.column('summary', width=400, stretch=True)
        
        # Add data
        for entry in sorted(history_entries, key=lambda x: x['timestamp'], reverse=True):
            status = '🟢 OK' if entry['ok'] else '🔴 FAIL'
            rt = f"{entry.get('response_time', 0):.0f}ms" if entry.get('response_time') else 'N/A'
            ts = entry['timestamp'][:19]
            code = entry.get('status_code', 'N/A')
            
            iid = tree.insert('', 'end', values=(
                ts, status, rt, code, entry.get('summary', '')
            ))
            
            # Color code
            if entry['ok']:
                tree.item(iid, tags=('ok',))
            else:
                tree.item(iid, tags=('fail',))
        
        tree.tag_configure('ok', background='#d4edda')
        tree.tag_configure('fail', background='#f8d7da')
        
        tree.grid(row=0, column=0, sticky='nswe')
        
        # Scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        tree.configure(yscrollcommand=vsb.set)
        
        # Stats
        total = len(history_entries)
        success = sum(1 for e in history_entries if e['ok'])
        fail = total - success
        uptime_pct = (success / total * 100) if total > 0 else 0
        
        stats_frame = ttk.Frame(frm)
        stats_frame.grid(row=2, column=0, sticky='we', pady=(10, 0))
        
        stats_text = f"Total Checks: {total}  |  Success: {success}  |  Failed: {fail}  |  Uptime: {uptime_pct:.1f}%"
        ttk.Label(stats_frame, text=stats_text, font=('Segoe UI', 10)).pack(side='left')
        
        # Close button
        ttk.Button(frm, text='Close', command=self.top.destroy, 
                  width=15).grid(row=3, column=0, pady=(10, 0))
        
        self.top.transient(master)

# ============== Main ==============
def main():
    """Main entry point"""
    root = tk.Tk()
    app = MonitorApp(root)
    
    # Keyboard shortcuts
    root.bind('<F5>', lambda e: app.scan_selected_remote())
    root.bind('<Control-F5>', lambda e: app.scan_all_targets())
    root.bind('<Control-n>', lambda e: app.open_add_remote())
    root.bind('<Control-space>', lambda e: app.toggle_polling())
    root.bind('<Control-s>', lambda e: app.save_config())
    root.bind('<Control-e>', lambda e: app.export_results())
    root.bind('<Control-i>', lambda e: app.show_statistics())
    root.bind('<Control-h>', lambda e: app.show_history())
    root.bind('<Control-l>', lambda e: app.log_text.delete('1.0', 'end'))
    root.bind('<Control-q>', lambda e: root.quit())
    root.bind('<Delete>', lambda e: app.delete_selected())
    root.bind('<F1>', lambda e: app.show_shortcuts())
    
    # Set minimum window size
    root.update()
    root.minsize(root.winfo_width(), root.winfo_height())
    
    # Center on screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 1600) // 2
    y = (screen_height - 900) // 2
    root.geometry(f'1600x900+{x}+{y}')
    
    root.mainloop()

if __name__ == '__main__':
    main()
