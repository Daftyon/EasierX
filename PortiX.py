#!/usr/bin/env python3
"""
Portix Pro v4.0 — Redesigned Edition

A clean, modern redesign of the Java Process & API Monitor.
Matches the HTML mockup: icon nav, colored monogram badges, status pills,
compact log footer, and a dense-but-scannable results table.

Dependencies:
    pip install requests paramiko
"""
from __future__ import annotations

import base64
import json
import queue
import re
import threading
import time
import tkinter as tk
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk

try:
    import requests
    import paramiko
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: pip install requests paramiko")

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass


# ── Config ────────────────────────────────────────────────────────────────────
APP_NAME    = "Portix Pro"
APP_VERSION = "4.0"
DEFAULT_POLL_SECONDS = 30
TIMEOUT_SECONDS      = 8
MAX_HISTORY_ENTRIES  = 1000
CONFIG_FILE = Path.home() / ".portix_pro_config.json"

SERVICES = [
    {"name": "Actuator Health",  "path": "/actuator/health",  "expect": "status",       "critical": True},
    {"name": "Actuator Info",    "path": "/actuator/info",    "expect": "",             "critical": False},
    {"name": "Actuator Metrics", "path": "/actuator/metrics", "expect": "names",        "critical": False},
    {"name": "Eureka Apps",      "path": "/eureka/apps",      "expect": "applications", "critical": True},
    {"name": "Jenkins API",      "path": "/api/json",         "expect": "",             "critical": False},
    {"name": "Basic Health",     "path": "/health",           "expect": "",             "critical": True},
    {"name": "Swagger UI",       "path": "/swagger-ui.html",  "expect": "",             "critical": False},
    {"name": "API Docs",         "path": "/v3/api-docs",      "expect": "",             "critical": False},
]

COMMON_PORTS = {8080: "Spring Boot", 8081: "Management", 9090: "Prometheus",
                8761: "Eureka", 8888: "Config Server", 8500: "Consul"}


# ── Palette ───────────────────────────────────────────────────────────────────
THEMES = {
    "light": {
        "name": "Light",
        # surfaces
        "bg":           "#f5f6f8",
        "surface":      "#ffffff",
        "surface2":     "#f0f2f5",
        "sidebar":      "#ffffff",
        "border":       "#e2e5ea",
        "divider":      "#edf0f3",
        # text
        "text":         "#111318",
        "text2":        "#6b7280",
        "text3":        "#9ca3af",
        # accent
        "accent":       "#378add",
        "accent2":      "#185fa5",
        "accent_bg":    "#e6f1fb",
        # semantic
        "success":      "#0f6e56",
        "success_bg":   "#e1f5ee",
        "danger":       "#a32d2d",
        "danger_bg":    "#fcebeb",
        "warning":      "#854f0b",
        "warning_bg":   "#faeeda",
        # treeview
        "tree_bg":      "#ffffff",
        "tree_alt":     "#f9fafb",
        "tree_sel":     "#e6f1fb",
        "tree_sel_fg":  "#111318",
        # inputs
        "input_bg":     "#ffffff",
        # terminal
        "term_bg":      "#0d1117",
        "term_fg":      "#c9d1d9",
        "term_accent":  "#58a6ff",
        # monogram badge colors: (bg, fg)
        "badge_blue":   ("#e6f1fb", "#185fa5"),
        "badge_green":  ("#eaf3de", "#3b6d11"),
        "badge_amber":  ("#faeeda", "#854f0b"),
        "badge_purple": ("#eeedfe", "#534ab7"),
        "badge_teal":   ("#e1f5ee", "#0f6e56"),
        "badge_coral":  ("#faece7", "#993c1d"),
    },
    "dark": {
        "name": "Dark",
        "bg":           "#0f1115",
        "surface":      "#171a21",
        "surface2":     "#1d2028",
        "sidebar":      "#13161c",
        "border":       "#262a33",
        "divider":      "#20242c",
        "text":         "#e6e8eb",
        "text2":        "#9aa1ad",
        "text3":        "#6b7280",
        "accent":       "#5b8dff",
        "accent2":      "#7ba3ff",
        "accent_bg":    "#1e2a44",
        "success":      "#4ade80",
        "success_bg":   "#14301f",
        "danger":       "#f87171",
        "danger_bg":    "#3a1717",
        "warning":      "#fbbf24",
        "warning_bg":   "#3a2a10",
        "tree_bg":      "#171a21",
        "tree_alt":     "#1b1e26",
        "tree_sel":     "#2a3a5c",
        "tree_sel_fg":  "#e6e8eb",
        "input_bg":     "#1d2028",
        "term_bg":      "#0a0d12",
        "term_fg":      "#d1d5db",
        "term_accent":  "#7ba3ff",
        "badge_blue":   ("#0c447c", "#85b7eb"),
        "badge_green":  ("#27500a", "#97c459"),
        "badge_amber":  ("#633806", "#ef9f27"),
        "badge_purple": ("#3c3489", "#afa9ec"),
        "badge_teal":   ("#085041", "#5dcaa5"),
        "badge_coral":  ("#711b13", "#f0997b"),
    },
}

# Cycle through badge colors for new app names
BADGE_KEYS = ["badge_blue", "badge_green", "badge_amber",
              "badge_purple", "badge_teal", "badge_coral"]


# ── Utilities ─────────────────────────────────────────────────────────────────
def build_auth_header(auth_type, username, password, token):
    headers = {}
    if auth_type == "Basic" and username:
        up = f"{username}:{password or ''}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(up).decode()
    elif auth_type == "Bearer" and token:
        headers["Authorization"] = "Bearer " + token
    return headers


def probe_url(base_url, service, timeout=TIMEOUT_SECONDS, headers=None):
    url = base_url.rstrip("/") + service["path"]
    t0 = time.time()
    try:
        r = requests.get(url, timeout=timeout, headers=headers or {}, verify=False)
        rt = (time.time() - t0) * 1000
        ok = 200 <= r.status_code < 300
        summary = ""
        try:
            j = r.json()
            if service["expect"]:
                found = service["expect"] in json.dumps(j)
                summary = f"{r.status_code}, has '{service['expect']}'={found}"
            else:
                keys = list(j.keys())[:5]
                summary = f"{r.status_code}, keys: {','.join(keys)}"
        except Exception:
            summary = f"{r.status_code} (non-json)"
        return {"ok": ok, "status_code": r.status_code, "summary": summary,
                "url": url, "response_time": rt,
                "timestamp": datetime.now().isoformat()}
    except requests.exceptions.Timeout:
        return {"ok": False, "status_code": None,
                "summary": f"Timeout after {timeout}s", "url": url,
                "response_time": timeout * 1000,
                "timestamp": datetime.now().isoformat()}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "status_code": None, "summary": "Connection error",
                "url": url, "response_time": None,
                "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"ok": False, "status_code": None, "summary": str(e)[:80],
                "url": url, "response_time": None,
                "timestamp": datetime.now().isoformat()}


JAVA_PORT_PATTERNS = [
    re.compile(r"--server\.port[=\s]+(\d+)"),
    re.compile(r"-Dserver\.port[=\s]+(\d+)"),
    re.compile(r"--port[=\s]+(\d+)"),
    re.compile(r"server\.port[=\s]+(\d+)"),
]


def parse_java_cmdline(cmdline: str):
    port = name = jar_name = main_class = None
    for p in JAVA_PORT_PATTERNS:
        m = p.search(cmdline)
        if m and 1024 <= int(m.group(1)) <= 65535:
            port = m.group(1)
            break
    if not port:
        for m in re.finditer(r"[\s:=](\d{4,5})\b", cmdline):
            v = int(m.group(1))
            if v in COMMON_PORTS or 8000 <= v <= 9999:
                port = str(v)
                break
    mjar = re.search(r"([\w\-\.]+)\.jar", cmdline)
    if mjar:
        jar_name = mjar.group(0)
        name = mjar.group(1)
    mc = re.search(r"\b([A-Za-z0-9_\.]*(?:Application|Main|Server|Bootstrap|Service))\b", cmdline)
    if mc:
        main_class = mc.group(1)
        if not name:
            name = main_class.split(".")[-1]
    if not name:
        name = "java-process"
    return {"port": port, "name": name, "jar": jar_name,
            "main_class": main_class, "cmdline": cmdline}


def ssh_run(host, username, password=None, pkey_path=None, port=22, timeout=10,
            cmd="ps -eo pid,args | grep java | grep -v grep"):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        kw = {"hostname": host, "port": port,
              "username": username, "timeout": timeout}
        if pkey_path and pkey_path.strip():
            for KeyClass in (paramiko.RSAKey, paramiko.Ed25519Key):
                try:
                    kw["pkey"] = KeyClass.from_private_key_file(pkey_path)
                    break
                except Exception:
                    pass
        if "pkey" not in kw and password:
            kw["password"] = password
        elif password and "pkey" not in kw:
            kw["password"] = password
        client.connect(**kw)
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        client.close()
        return out, err
    except Exception as e:
        try:
            client.close()
        except Exception:
            pass
        return "", str(e)


def parse_remote_ps(ps_output: str):
    items = []
    for line in ps_output.splitlines():
        line = line.strip()
        m = re.match(r"^(\d+)\s+(.*)$", line)
        if m:
            parsed = parse_java_cmdline(m.group(2))
            items.append({"pid": m.group(1), "cmd": m.group(2),
                          "port": parsed["port"],
                          "name": parsed["name"] or f"java-{m.group(1)}",
                          "jar": parsed.get("jar"),
                          "main_class": parsed.get("main_class")})
    return items


def get_listening_ports(host, username, password=None, pkey_path=None, port=22):
    cmd = "ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null"
    out, _ = ssh_run(host, username, password, pkey_path, port, cmd=cmd)
    pid_port_map = {}
    for line in (out or "").splitlines():
        pm = re.search(r"pid[=\s]+(\d+)|(\d+)/\w+", line)
        pt = re.search(r":(\d{4,5})\s", line)
        if pm and pt:
            pid = pm.group(1) or pm.group(2)
            p = pt.group(1)
            if 1024 <= int(p) <= 65535:
                pid_port_map[pid] = p
    return pid_port_map


def get_server_history(host, username, password=None, pkey_path=None, port=22, lines=100):
    for cmd in [f"cat ~/.bash_history | tail -n {lines}",
                f"cat ~/.zsh_history | tail -n {lines}"]:
        out, err = ssh_run(host, username, password, pkey_path, port, cmd=cmd)
        if out and not err:
            return out, None
    return None, "Could not retrieve history"


# ── Colored canvas pill helper ─────────────────────────────────────────────────
def make_pill_canvas(parent, text, bg, fg, width=80, height=22):
    c = tk.Canvas(parent, width=width, height=height,
                  bg=parent.cget("background"), highlightthickness=0, bd=0)
    r = height // 2
    # rounded rect
    c.create_arc(0, 0, r*2, height, start=90, extent=180, fill=bg, outline=bg)
    c.create_arc(width-r*2, 0, width, height, start=270, extent=180, fill=bg, outline=bg)
    c.create_rectangle(r, 0, width-r, height, fill=bg, outline=bg)
    # dot
    dot_x = r + 3
    dot_y = height // 2
    c.create_oval(dot_x-3, dot_y-3, dot_x+3, dot_y+3, fill=fg, outline=fg)
    # text
    c.create_text(dot_x + 9, dot_y, text=text, fill=fg,
                  font=("Segoe UI", 9, "bold"), anchor="w")
    return c


def make_monogram_canvas(parent, initials, bg, fg, size=28):
    c = tk.Canvas(parent, width=size, height=size,
                  bg=parent.cget("background"), highlightthickness=0, bd=0)
    r = 6
    c.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=bg, outline=bg)
    c.create_arc(size-r*2, 0, size, r*2, start=0, extent=90, fill=bg, outline=bg)
    c.create_arc(0, size-r*2, r*2, size, start=180, extent=90, fill=bg, outline=bg)
    c.create_arc(size-r*2, size-r*2, size, size, start=270, extent=90, fill=bg, outline=bg)
    c.create_rectangle(r, 0, size-r, size, fill=bg, outline=bg)
    c.create_rectangle(0, r, size, size-r, fill=bg, outline=bg)
    c.create_text(size//2, size//2, text=initials[:2].upper(),
                  fill=fg, font=("Segoe UI", 8, "bold"))
    return c


# ── Main Application ──────────────────────────────────────────────────────────
class PortixApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.master = master
        self.pack(fill="both", expand=True)
        master.title(f"{APP_NAME}  ·  Java Process & Service Monitor")
        master.geometry("1480x860")
        master.minsize(1100, 660)

        self.theme_name = "light"
        self.t = THEMES["light"]
        self.servers: list[dict] = []
        self.custom_services: list[dict] = []
        self.result_queue: queue.Queue = queue.Queue()
        self.history: defaultdict[str, list] = defaultdict(list)
        self.alert_state: dict = {}
        self.server_history: defaultdict[str, list] = defaultdict(list)
        self.stats = {"scans": 0, "probes": 0, "failed": 0}
        self._badge_idx: dict[str, int] = {}  # name -> badge color index
        self._polling = False
        self._poll_interval = DEFAULT_POLL_SECONDS
        self._poll_inflight = 0
        self._poll_next_in = 0
        self._sort_state: dict[str, bool] = {}

        self._setup_fonts()
        self._build_styles()
        self._build_menu()
        self._build_ui()
        self._apply_theme_to_widgets()
        self._start_queue_loop()
        self._load_config_auto()

    # ── fonts & styles ─────────────────────────────────────────────────────────
    def _setup_fonts(self):
        families = font.families()
        self.font_ui   = "Segoe UI" if "Segoe UI" in families else "Helvetica"
        self.font_mono = "Consolas" if "Consolas" in families else "Courier"
        try:
            font.nametofont("TkDefaultFont").configure(family=self.font_ui, size=10)
            font.nametofont("TkTextFont").configure(family=self.font_ui, size=10)
        except Exception:
            pass

    def _build_styles(self):
        t = self.t
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.master.configure(bg=t["bg"])
        style.configure(".", background=t["bg"], foreground=t["text"],
                        fieldbackground=t["input_bg"], bordercolor=t["border"],
                        lightcolor=t["border"], darkcolor=t["border"])

        style.configure("TFrame", background=t["bg"])
        style.configure("Sidebar.TFrame", background=t["sidebar"])
        style.configure("Surface.TFrame", background=t["surface"])
        style.configure("Surface2.TFrame", background=t["surface2"])
        style.configure("TLabel", background=t["bg"], foreground=t["text"])
        style.configure("Sidebar.TLabel", background=t["sidebar"], foreground=t["text"])
        style.configure("Muted.TLabel", background=t["bg"], foreground=t["text2"])
        style.configure("Subtle.TLabel", background=t["bg"], foreground=t["text3"])
        style.configure("Surface.TLabel", background=t["surface"], foreground=t["text"])
        style.configure("SurfaceMuted.TLabel", background=t["surface"], foreground=t["text2"])

        # Brand
        style.configure("Brand.TLabel", background=t["sidebar"],
                        foreground=t["accent"],
                        font=(self.font_ui, 15, "bold"))
        style.configure("BrandSub.TLabel", background=t["sidebar"],
                        foreground=t["text3"],
                        font=(self.font_ui, 9))
        style.configure("SidebarLabel.TLabel", background=t["sidebar"],
                        foreground=t["text3"],
                        font=(self.font_ui, 9, "bold"))
        style.configure("NavActive.TLabel", background=t["surface2"],
                        foreground=t["text"],
                        font=(self.font_ui, 11, "bold"))
        style.configure("Nav.TLabel", background=t["sidebar"],
                        foreground=t["text2"],
                        font=(self.font_ui, 11))
        style.configure("SectionTitle.TLabel", background=t["bg"],
                        foreground=t["text"],
                        font=(self.font_ui, 14, "bold"))
        style.configure("Meta.TLabel", background=t["bg"],
                        foreground=t["text3"],
                        font=(self.font_ui, 11))

        # Buttons
        style.configure("TButton", background=t["surface2"],
                        foreground=t["text"], bordercolor=t["border"],
                        lightcolor=t["border"], darkcolor=t["border"],
                        focusthickness=0, padding=(10, 6), relief="flat",
                        font=(self.font_ui, 10))
        style.map("TButton",
                  background=[("active", t["border"]),
                               ("pressed", t["border"])],
                  foreground=[("disabled", t["text3"])])

        style.configure("Primary.TButton", background=t["accent"],
                        foreground="#ffffff", bordercolor=t["accent"],
                        padding=(12, 7),
                        font=(self.font_ui + " Semibold" if "Segoe UI Semibold" in font.families()
                               else self.font_ui, 10, "bold"))
        style.map("Primary.TButton",
                  background=[("active", t["accent2"]), ("pressed", t["accent2"])],
                  foreground=[("disabled", "#ffffff")])

        style.configure("Danger.TButton", background=t["danger_bg"],
                        foreground=t["danger"], bordercolor=t["danger"],
                        padding=(10, 6))
        style.map("Danger.TButton",
                  background=[("active", t["danger"]), ("pressed", t["danger"])],
                  foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])

        style.configure("Sidebar.TButton", background=t["sidebar"],
                        foreground=t["text2"], bordercolor=t["border"],
                        focusthickness=0, padding=(8, 6), relief="flat",
                        font=(self.font_ui, 10))
        style.map("Sidebar.TButton",
                  background=[("active", t["surface2"]), ("pressed", t["surface2"])],
                  foreground=[("active", t["text"]), ("pressed", t["text"])])

        # Entries / combos
        style.configure("TEntry", fieldbackground=t["input_bg"],
                        foreground=t["text"], bordercolor=t["border"],
                        lightcolor=t["border"], darkcolor=t["border"], padding=6)
        style.map("TEntry", bordercolor=[("focus", t["accent"])])
        style.configure("TCombobox", fieldbackground=t["input_bg"],
                        background=t["input_bg"], foreground=t["text"],
                        bordercolor=t["border"], arrowcolor=t["text2"])
        style.map("TCombobox", fieldbackground=[("readonly", t["input_bg"])])

        style.configure("TCheckbutton", background=t["bg"],
                        foreground=t["text"], focuscolor=t["bg"])

        # Treeview
        style.configure("Treeview", background=t["tree_bg"],
                        fieldbackground=t["tree_bg"], foreground=t["text"],
                        bordercolor=t["border"], rowheight=36,
                        font=(self.font_ui, 10))
        style.map("Treeview",
                  background=[("selected", t["tree_sel"])],
                  foreground=[("selected", t["tree_sel_fg"])])
        style.configure("Treeview.Heading", background=t["surface2"],
                        foreground=t["text2"],
                        font=(self.font_ui, 9, "bold"),
                        relief="flat", padding=(8, 6))
        style.map("Treeview.Heading",
                  background=[("active", t["border"])])

        style.configure("TSeparator", background=t["divider"])
        style.configure("TPanedwindow", background=t["bg"])
        style.configure("TScrollbar", background=t["surface2"],
                        troughcolor=t["bg"], bordercolor=t["bg"],
                        arrowcolor=t["text2"])
        style.configure("TLabelframe", background=t["surface"],
                        bordercolor=t["border"],
                        lightcolor=t["border"], darkcolor=t["border"],
                        relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=t["surface"],
                        foreground=t["text"],
                        font=(self.font_ui, 10, "bold"))

    def _apply_theme_to_widgets(self):
        t = self.t
        if hasattr(self, "target_listbox"):
            self.target_listbox.configure(
                bg=t["sidebar"], fg=t["text"],
                selectbackground=t["accent_bg"],
                selectforeground=t["text"],
                highlightthickness=0, bd=0, activestyle="none")
        if hasattr(self, "log_text"):
            self.log_text.configure(bg=t["surface"], fg=t["text"],
                                    insertbackground=t["text"],
                                    selectbackground=t["accent_bg"],
                                    highlightthickness=0, bd=0)
            self.log_text.tag_configure("ok",   foreground=t["success"])
            self.log_text.tag_configure("err",  foreground=t["danger"])
            self.log_text.tag_configure("info", foreground=t["text2"])
            self.log_text.tag_configure("ts",   foreground=t["text3"])
        if hasattr(self, "tree"):
            self.tree.tag_configure("up",      background=t["success_bg"],
                                    foreground=t["success"])
            self.tree.tag_configure("down",    background=t["danger_bg"],
                                    foreground=t["danger"])
            self.tree.tag_configure("warning", background=t["warning_bg"],
                                    foreground=t["warning"])
            self.tree.tag_configure("idle",    foreground=t["text2"])

    def toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.t = THEMES[self.theme_name]
        self._build_styles()
        self._apply_theme_to_widgets()
        lbl = "☀  Light" if self.theme_name == "dark" else "🌙  Dark"
        if hasattr(self, "theme_btn"):
            self.theme_btn.configure(text=lbl)
        self.log("info", f"Switched to {self.t['name']} theme")

    # ── menu ───────────────────────────────────────────────────────────────────
    def _build_menu(self):
        mb = tk.Menu(self.master)
        self.master.config(menu=mb)
        fm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="Export Results…", command=self.export_results,  accelerator="Ctrl+E")
        fm.add_command(label="Export History…", command=self.export_history)
        fm.add_separator()
        fm.add_command(label="Save Config",     command=self.save_config,     accelerator="Ctrl+S")
        fm.add_command(label="Load Config…",    command=self.load_config)
        fm.add_separator()
        fm.add_command(label="Exit",            command=self.master.quit,     accelerator="Ctrl+Q")

        tm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Targets", menu=tm)
        tm.add_command(label="Add Remote Target…",  command=self.open_add_remote,        accelerator="Ctrl+N")
        tm.add_command(label="Edit Selected",        command=self.edit_selected_target)
        tm.add_command(label="Remove Selected",      command=self.remove_selected_target, accelerator="Delete")
        tm.add_separator()
        tm.add_command(label="Scan Selected",        command=self.scan_selected,          accelerator="F5")
        tm.add_command(label="Scan All Targets",     command=self.scan_all,               accelerator="Ctrl+F5")

        am = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Actions", menu=am)
        am.add_command(label="Start/Stop Polling",  command=self.toggle_polling, accelerator="Ctrl+Space")
        am.add_command(label="Probe Now",           command=self.probe_all)
        am.add_separator()
        am.add_command(label="Add Custom Service…", command=self.add_custom_service)
        am.add_command(label="Clear Results",       command=self.clear_results)

        vm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="View", menu=vm)
        vm.add_command(label="Toggle Theme",        command=self.toggle_theme,           accelerator="Ctrl+T")
        vm.add_separator()
        vm.add_command(label="Statistics",          command=self.show_statistics,        accelerator="Ctrl+I")
        vm.add_command(label="Service History",     command=self.show_history,           accelerator="Ctrl+H")
        vm.add_command(label="Server Event Log",    command=self.show_server_event_log,  accelerator="Ctrl+R")

        hm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Help", menu=hm)
        hm.add_command(label="Keyboard Shortcuts",  command=self.show_shortcuts, accelerator="F1")
        hm.add_command(label="About",               command=self.show_about)

    # ── UI scaffold ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.grid(row=0, column=0, sticky="nsew")
        paned.add(self._build_sidebar(paned), weight=0)
        paned.add(self._build_main(paned),    weight=1)

    # ── sidebar ────────────────────────────────────────────────────────────────
    def _build_sidebar(self, parent):
        t = self.t
        side = ttk.Frame(parent, style="Sidebar.TFrame", width=245)
        side.grid_propagate(False)
        side.grid_rowconfigure(5, weight=1)
        side.grid_columnconfigure(0, weight=1)

        # ── brand ──
        brand = ttk.Frame(side, style="Sidebar.TFrame", padding=(18, 18, 18, 14))
        brand.grid(row=0, column=0, sticky="we")
        brand.grid_columnconfigure(1, weight=1)

        dot_c = tk.Canvas(brand, width=26, height=26, bg=t["sidebar"],
                          highlightthickness=0, bd=0)
        dot_c.create_rectangle(0, 0, 26, 26, fill=t["accent"], outline=t["accent"])
        dot_c.create_oval(7, 7, 19, 19, fill="white", outline="white")
        dot_c.create_oval(10, 10, 16, 16, fill=t["accent"], outline=t["accent"])
        dot_c.grid(row=0, column=0, padx=(0, 8))
        self.brand_canvas = dot_c

        ttk.Label(brand, text=APP_NAME, style="Brand.TLabel").grid(
            row=0, column=1, sticky="w")

        self.theme_btn = ttk.Button(brand, text="🌙  Dark",
                                    style="Sidebar.TButton",
                                    command=self.toggle_theme, width=8)
        self.theme_btn.grid(row=0, column=2, sticky="e")

        ttk.Label(brand, text=f"Java monitor · v{APP_VERSION}",
                  style="BrandSub.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # ── border ──
        sep1 = tk.Frame(side, bg=t["border"], height=1)
        sep1.grid(row=1, column=0, sticky="we")
        self._sep_widgets = [sep1]

        # ── primary action ──
        action_frame = ttk.Frame(side, style="Sidebar.TFrame", padding=(14, 12, 14, 6))
        action_frame.grid(row=2, column=0, sticky="we")
        action_frame.grid_columnconfigure(0, weight=1)
        ttk.Button(action_frame, text="+ Add remote target",
                   style="Primary.TButton",
                   command=self.open_add_remote).grid(
            row=0, column=0, sticky="we", pady=(0, 8))

        # quick action row
        q = ttk.Frame(action_frame, style="Sidebar.TFrame")
        q.grid(row=1, column=0, sticky="we", pady=(0, 4))
        q.grid_columnconfigure(0, weight=1)
        q.grid_columnconfigure(1, weight=1)
        ttk.Button(q, text="Scan",     style="Sidebar.TButton",
                   command=self.scan_selected).grid(row=0, column=0, sticky="we", padx=(0, 3))
        ttk.Button(q, text="Scan all", style="Sidebar.TButton",
                   command=self.scan_all).grid(row=0, column=1, sticky="we", padx=(3, 0))

        # extra actions row
        e = ttk.Frame(action_frame, style="Sidebar.TFrame")
        e.grid(row=2, column=0, sticky="we")
        for i, (lbl, cmd) in enumerate([("Edit",   self.edit_selected_target),
                                         ("Remove", self.remove_selected_target),
                                         ("Shell",  self.show_server_history)]):
            e.grid_columnconfigure(i, weight=1)
            ttk.Button(e, text=lbl, style="Sidebar.TButton", command=cmd).grid(
                row=0, column=i, sticky="we", padx=(0 if i==0 else 2, 2 if i<2 else 0))

        sep2 = tk.Frame(side, bg=t["border"], height=1)
        sep2.grid(row=3, column=0, sticky="we", pady=(10, 0))
        self._sep_widgets.append(sep2)

        # ── targets label ──
        ttk.Label(side, text="TARGETS",
                  style="SidebarLabel.TLabel",
                  padding=(18, 8, 18, 4)).grid(row=4, column=0, sticky="we")

        # ── target list ──
        list_wrap = tk.Frame(side, bg=t["border"])
        list_wrap.grid(row=5, column=0, sticky="nswe", padx=14, pady=(0, 12))
        list_wrap.grid_rowconfigure(0, weight=1)
        list_wrap.grid_columnconfigure(0, weight=1)

        self.target_listbox = tk.Listbox(
            list_wrap, selectmode="extended",
            font=(self.font_ui, 10),
            relief="flat", bd=0, highlightthickness=0,
            activestyle="none")
        self.target_listbox.grid(row=0, column=0, sticky="nswe", padx=1, pady=1)
        tsb = ttk.Scrollbar(list_wrap, orient="vertical",
                             command=self.target_listbox.yview)
        tsb.grid(row=0, column=1, sticky="ns")
        self.target_listbox.configure(yscrollcommand=tsb.set)
        self.target_listbox.bind("<Double-Button-1>", lambda e: self.scan_selected())
        self.target_listbox.bind("<<ListboxSelect>>", self.on_target_select)

        # ── detail card ──
        info_card = ttk.LabelFrame(side, text="Details", padding=10,
                                   style="TLabelframe")
        info_card.grid(row=6, column=0, sticky="we", padx=14, pady=(0, 10))
        info_card.grid_columnconfigure(0, weight=1)
        self.target_detail_label = ttk.Label(info_card,
                                             text="Select a target.",
                                             style="SurfaceMuted.TLabel",
                                             wraplength=200, justify="left",
                                             font=(self.font_ui, 9))
        self.target_detail_label.grid(row=0, column=0, sticky="we")

        # ── overview card ──
        ov = ttk.LabelFrame(side, text="Overview", padding=10)
        ov.grid(row=7, column=0, sticky="we", padx=14, pady=(0, 14))
        ov.grid_columnconfigure(1, weight=1)
        for r, (lbl, attr) in enumerate([("Targets", "ov_targets_lbl"),
                                          ("Services", "ov_services_lbl")]):
            ttk.Label(ov, text=lbl, style="SurfaceMuted.TLabel").grid(
                row=r, column=0, sticky="w", pady=2)
            lbl_w = ttk.Label(ov, text="0", style="Surface.TLabel",
                              font=(self.font_ui, 11, "bold"))
            lbl_w.grid(row=r, column=1, sticky="e", pady=2)
            setattr(self, attr, lbl_w)

        self._refresh_targets()
        return side

    # ── main panel ─────────────────────────────────────────────────────────────
    def _build_main(self, parent):
        main = ttk.PanedWindow(parent, orient="vertical")
        main.add(self._build_results(main), weight=5)
        main.add(self._build_log(main),     weight=1)
        return main

    # ── results ────────────────────────────────────────────────────────────────
    def _build_results(self, parent):
        t = self.t
        wrap = ttk.Frame(parent, style="Surface.TFrame",
                         padding=(20, 16, 20, 10))
        wrap.grid_rowconfigure(2, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        # header row
        hdr = ttk.Frame(wrap, style="Surface.TFrame")
        hdr.grid(row=0, column=0, sticky="we", pady=(0, 12))
        hdr.grid_columnconfigure(1, weight=1)

        title_box = ttk.Frame(hdr, style="Surface.TFrame")
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(title_box, text="Services", style="SectionTitle.TLabel",
                  background=t["surface"]).pack(side="left")
        ttk.Label(title_box, text="  Discovered Java processes & probed endpoints",
                  style="Meta.TLabel",
                  background=t["surface"]).pack(side="left", padx=(4, 0))

        pills_frame = ttk.Frame(hdr, style="Surface.TFrame")
        pills_frame.grid(row=0, column=1, sticky="e")
        self.pill_up_var   = tk.StringVar(value="0 up")
        self.pill_down_var = tk.StringVar(value="0 down")
        self.pill_idle_var = tk.StringVar(value="0 idle")

        self.status_pills_frame = pills_frame  # kept for repaint
        self._draw_status_pills()

        # toolbar
        tb = ttk.Frame(wrap, style="Surface.TFrame")
        tb.grid(row=1, column=0, sticky="we", pady=(0, 10))
        tb.grid_columnconfigure(8, weight=1)

        self.poll_btn = ttk.Button(tb, text="▶  Start polling",
                                   style="Primary.TButton",
                                   command=self.toggle_polling)
        self.poll_btn.grid(row=0, column=0, padx=(0, 6))
        ttk.Button(tb, text="Probe now",
                   command=self.probe_all).grid(row=0, column=1, padx=(0, 10))

        tk.Frame(tb, bg=t["border"], width=1, height=20).grid(
            row=0, column=2, padx=6)

        ttk.Label(tb, text="Interval",
                  style="Muted.TLabel",
                  background=t["surface"]).grid(row=0, column=3, padx=(0, 4))
        self.poll_interval_var = tk.StringVar(value=str(DEFAULT_POLL_SECONDS))
        self.poll_interval_var.trace_add("write", lambda *a: self._on_interval_change())
        ttk.Combobox(tb, textvariable=self.poll_interval_var, width=5,
                     state="readonly",
                     values=["10", "30", "60", "120", "300"]).grid(
            row=0, column=4, padx=(0, 4))
        ttk.Label(tb, text="s",
                  style="Muted.TLabel",
                  background=t["surface"]).grid(row=0, column=5, padx=(0, 14))

        tk.Frame(tb, bg=t["border"], width=1, height=20).grid(
            row=0, column=6, padx=6)

        # search
        search_outer = ttk.Frame(tb, style="Surface.TFrame")
        search_outer.grid(row=0, column=7, padx=(0, 8))
        ttk.Label(search_outer, text="Filter",
                  style="Muted.TLabel",
                  background=t["surface"]).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._apply_filter())
        ttk.Entry(search_outer, textvariable=self.search_var,
                  width=22).pack(side="left")

        self.show_all_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(tb, text="Show all",
                        variable=self.show_all_var,
                        command=self._apply_filter,
                        style="TCheckbutton").grid(row=0, column=8, padx=(4, 0))

        self.poll_indicator = ttk.Label(tb, text="⏸  Idle",
                                        style="Muted.TLabel",
                                        background=t["surface"])
        self.poll_indicator.grid(row=0, column=9, padx=(20, 0))

        # results tree
        tree_container = tk.Frame(wrap, bg=t["border"], bd=0, highlightthickness=0)
        tree_container.grid(row=2, column=0, sticky="nswe")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        cols = ("target", "pid", "name", "port", "service",
                "status", "response_time", "last_check", "summary")
        self.tree = ttk.Treeview(tree_container, columns=cols,
                                 show="headings", selectmode="extended")
        col_cfg = {
            "target":        ("Target",      140, False),
            "pid":           ("PID",          60, False),
            "name":          ("Application", 190, True),
            "port":          ("Port",         72, False),
            "service":       ("Service",     150, True),
            "status":        ("Status",       90, False),
            "response_time": ("Response",     90, False),
            "last_check":    ("Checked",      80, False),
            "summary":       ("Details",     260, True),
        }
        for col, (label, width, stretch) in col_cfg.items():
            self.tree.heading(col, text=label,
                              command=lambda c=col: self._sort_tree(c))
            self.tree.column(col, anchor="w", width=width, stretch=stretch)

        self.tree.grid(row=0, column=0, sticky="nswe", padx=1, pady=1)
        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="we")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # context menu
        self.ctx = tk.Menu(self.tree, tearoff=0)
        self.ctx.add_command(label="Copy URL",          command=self._copy_url)
        self.ctx.add_command(label="Open in browser",   command=self._open_browser)
        self.ctx.add_separator()
        self.ctx.add_command(label="Probe now",         command=self._probe_selected)
        self.ctx.add_command(label="View details",      command=self._view_details)
        self.ctx.add_command(label="View history",      command=self._view_item_history)
        self.ctx.add_separator()
        self.ctx.add_command(label="Delete row",        command=self._delete_selected)

        self.tree.bind("<Button-3>",      self._show_ctx)
        self.tree.bind("<Double-Button-1>", lambda e: self._view_details())

        return wrap

    def _draw_status_pills(self):
        t = self.t
        for w in self.status_pills_frame.winfo_children():
            w.destroy()
        for text_var, bg, fg in [
            (self.pill_up_var,   t["success_bg"], t["success"]),
            (self.pill_down_var, t["danger_bg"],  t["danger"]),
            (self.pill_idle_var, t["surface2"],   t["text2"]),
        ]:
            lbl = tk.Label(self.status_pills_frame,
                           textvariable=text_var,
                           bg=bg, fg=fg,
                           font=(self.font_ui, 10, "bold"),
                           padx=10, pady=3,
                           relief="flat")
            lbl.pack(side="left", padx=4)

    # ── log footer ─────────────────────────────────────────────────────────────
    def _build_log(self, parent):
        t = self.t
        wrap = ttk.Frame(parent, style="Surface.TFrame")
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        # header strip
        bar = tk.Frame(wrap, bg=t["border"], height=1)
        bar.grid(row=0, column=0, sticky="we")

        hdr = ttk.Frame(wrap, style="Surface.TFrame", padding=(20, 6, 20, 0))
        hdr.grid(row=1, column=0, sticky="we")
        hdr.grid_columnconfigure(0, weight=1)
        ttk.Label(hdr, text="Activity log",
                  style="SurfaceMuted.TLabel",
                  font=(self.font_ui, 11, "bold")).grid(row=0, column=0, sticky="w")

        ctrl = ttk.Frame(hdr, style="Surface.TFrame")
        ctrl.grid(row=0, column=1, sticky="e")
        for lbl, cmd in [("Clear",   lambda: self.log_text.delete("1.0", "end")),
                          ("Save…",  self._save_log),
                          ("Export…",self.export_results)]:
            ttk.Button(ctrl, text=lbl, command=cmd,
                       padding=(8, 3)).pack(side="left", padx=3)

        self.stats_label = ttk.Label(hdr, text="Ready",
                                     style="SurfaceMuted.TLabel",
                                     font=(self.font_ui, 9))
        self.stats_label.grid(row=0, column=2, padx=(20, 0))

        # log text
        log_frame = ttk.Frame(wrap, style="Surface.TFrame",
                              padding=(20, 4, 20, 12))
        log_frame.grid(row=2, column=0, sticky="nswe")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=7, wrap="none",
                                font=(self.font_mono, 9),
                                relief="flat", bd=0,
                                highlightthickness=0, padx=4, pady=4)
        self.log_text.grid(row=0, column=0, sticky="nswe")
        lsb = ttk.Scrollbar(log_frame, orient="vertical",
                             command=self.log_text.yview)
        lsb.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=lsb.set)

        return wrap

    # ── targets management ─────────────────────────────────────────────────────
    def _refresh_targets(self):
        if not hasattr(self, "target_listbox"):
            return
        self.target_listbox.delete(0, tk.END)
        t = self.t
        for s in self.servers:
            ok = s.get("last_scan_success")
            dot = "●" if ok else ("○" if "last_scan" in s else "·")
            self.target_listbox.insert(
                tk.END, f"  {dot}  {s['host']}  ·  {s.get('username', '?')}")
            color = t["success"] if ok else (t["danger"] if "last_scan" in s else t["text2"])
            self.target_listbox.itemconfig(tk.END, fg=color)
        if hasattr(self, "ov_targets_lbl"):
            self.ov_targets_lbl.config(text=str(len(self.servers)))

    def on_target_select(self, _e):
        sel = self.target_listbox.curselection()
        if not sel:
            self.target_detail_label.config(text="Select a target.")
            return
        s = self.servers[sel[0]]
        auth = "Private key" if s.get("pkey") else "Password"
        info = f"Host:  {s['host']}\nPort:  {s.get('port', 22)}\nUser:  {s.get('username', '?')}\nAuth:  {auth}"
        if "last_scan" in s:
            info += f"\n\nLast scan: {s['last_scan']}"
            info += f"\nResult:    {'OK' if s.get('last_scan_success') else 'Failed'}"
        self.target_detail_label.config(text=info)

    def open_add_remote(self):
        dlg = RemoteDialog(self.master, theme=self.t)
        self.master.wait_window(dlg.top)
        if dlg.result:
            self.servers.append(dlg.result)
            self._refresh_targets()
            self.log("info", f"Added remote {dlg.result['host']}")
            self.save_config(silent=True)

    def edit_selected_target(self):
        sel = self.target_listbox.curselection()
        if not sel:
            messagebox.showinfo("Edit Target", "Select a target first.")
            return
        idx = sel[0]
        dlg = RemoteDialog(self.master, edit_data=self.servers[idx], theme=self.t)
        self.master.wait_window(dlg.top)
        if dlg.result:
            self.servers[idx] = dlg.result
            self._refresh_targets()
            self.log("info", f"Updated {dlg.result['host']}")
            self.save_config(silent=True)

    def remove_selected_target(self):
        sel = self.target_listbox.curselection()
        if not sel:
            messagebox.showinfo("Remove Target", "Select a target first.")
            return
        hosts = [self.servers[i]["host"] for i in sel]
        if messagebox.askyesno("Remove", f"Remove {len(sel)} target(s)?\n\n" + "\n".join(hosts)):
            for i in sorted(sel, reverse=True):
                self.servers.pop(i)
            self._refresh_targets()
            self.log("info", f"Removed {len(sel)} target(s)")
            self.save_config(silent=True)

    # ── scanning ───────────────────────────────────────────────────────────────
    def scan_selected(self):
        sel = self.target_listbox.curselection()
        if not sel:
            messagebox.showinfo("Scan", "Select a target first.")
            return
        for i in sel:
            self.log("info", f"Scanning {self.servers[i]['host']}…")
            threading.Thread(target=self._scan_worker,
                             args=(self.servers[i], i), daemon=True).start()

    def scan_all(self):
        if not self.servers:
            messagebox.showinfo("Scan All", "No targets configured.")
            return
        self.log("info", f"Scanning {len(self.servers)} target(s)…")
        for i, s in enumerate(self.servers):
            threading.Thread(target=self._scan_worker,
                             args=(s, i), daemon=True).start()

    def _scan_worker(self, conf, idx):
        try:
            out, err = ssh_run(conf["host"], conf["username"],
                               password=conf.get("password"),
                               pkey_path=conf.get("pkey"),
                               port=conf.get("port", 22))
            if err:
                self.result_queue.put(("scan_error",
                                       {"host": conf["host"], "error": err, "idx": idx}))
                return
            items = parse_remote_ps(out)
            try:
                pm = get_listening_ports(conf["host"], conf["username"],
                                         password=conf.get("password"),
                                         pkey_path=conf.get("pkey"),
                                         port=conf.get("port", 22))
                for it in items:
                    if not it.get("port") and it["pid"] in pm:
                        it["port"] = pm[it["pid"]]
            except Exception:
                pass
            self.result_queue.put(("scan_ok",
                                   {"host": conf["host"], "items": items, "idx": idx}))
            self.stats["scans"] += 1
        except Exception as e:
            self.result_queue.put(("error", f"Scan error {conf['host']}: {e}"))

    # ── probing ────────────────────────────────────────────────────────────────
    def _probe_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Probe", "Select services to probe.")
            return
        svcs = SERVICES + self.custom_services
        for iid in sel:
            try:
                vals = self.tree.item(iid)["values"]
            except tk.TclError:
                continue
            if len(vals) < 4:
                continue
            target, port = vals[0], vals[3]
            if not port or port == "N/A":
                continue
            base = f"http://{target}:{port}"
            for svc in svcs:
                threading.Thread(target=self._probe_worker,
                                 args=(iid, target, port, svc, base),
                                 daemon=True).start()

    def probe_all(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showinfo("Probe All", "No services discovered yet.")
            return
        svcs = SERVICES + self.custom_services
        count = 0
        for iid in items:
            try:
                vals = self.tree.item(iid)["values"]
            except tk.TclError:
                continue
            if len(vals) < 4:
                continue
            target, port = vals[0], vals[3]
            if not port or port == "N/A":
                continue
            count += 1
            base = f"http://{target}:{port}"
            for svc in svcs:
                threading.Thread(target=self._probe_worker,
                                 args=(iid, target, port, svc, base),
                                 daemon=True).start()
        if count == 0:
            self.log("info", "Probe all: no rows with a detected port.")
        else:
            self.log("info", f"Probing {count} × {len(svcs)} endpoints…")

    def _probe_worker(self, iid, target, port, svc, base):
        try:
            res = probe_url(base, svc)
            self.result_queue.put(("probe", {
                "iid": iid, "target": target, "port": port,
                "svc": svc["name"], "res": res,
                "critical": svc.get("critical", False),
            }))
            self.stats["probes"] += 1
            if not res["ok"]:
                self.stats["failed"] += 1
        except Exception as e:
            self.result_queue.put(("error", f"Probe error: {e}"))

    # ── polling ────────────────────────────────────────────────────────────────
    def toggle_polling(self):
        if self._polling:
            self._polling = False
            self.poll_btn.config(text="▶  Start polling")
            self.poll_indicator.config(text="⏸  Idle")
            self.log("info", "Polling stopped")
            return
        try:
            interval = int(self.poll_interval_var.get())
        except ValueError:
            messagebox.showerror("Polling", "Invalid interval.")
            return
        if interval < 5:
            messagebox.showwarning("Polling", "Minimum interval is 5 seconds.")
            return
        self._poll_interval = interval
        self._polling = True
        self.poll_btn.config(text="■  Stop polling", style="Danger.TButton")
        self.poll_indicator.config(text=f"● Polling every {interval}s")
        threading.Thread(target=self._poll_loop, daemon=True).start()
        self.log("info", f"Polling started every {interval}s")

    def _on_interval_change(self, *_):
        if not self._polling:
            return
        try:
            v = int(self.poll_interval_var.get())
        except ValueError:
            return
        if v >= 5 and v != self._poll_interval:
            self._poll_interval = v
            self.log("info", f"Poll interval updated to {v}s")

    def _poll_loop(self):
        next_at = time.time()
        while self._polling:
            now = time.time()
            if now >= next_at:
                self.result_queue.put(("poll_tick", None))
                next_at = now + max(5, self._poll_interval)
            remaining = max(0, int(next_at - now))
            self.result_queue.put(("poll_countdown", remaining))
            threading.Event().wait(0.5)

    def _run_poll_cycle(self):
        if not self._polling:
            return
        seen = set()
        targets = []
        for iid in self.tree.get_children():
            try:
                vals = self.tree.item(iid).get("values", [])
                if len(vals) < 4:
                    continue
                target, port = vals[0], vals[3]
                if not port or port in ("N/A", "—"):
                    continue
                key = (str(target), str(port))
                if key in seen:
                    continue
                seen.add(key)
                targets.append((iid, str(target), str(port)))
            except tk.TclError:
                continue
        if not targets:
            return
        svcs = SERVICES + self.custom_services
        self._poll_inflight = len(targets) * len(svcs)
        self.log("info", f"Poll: {len(targets)} × {len(svcs)} probes")
        for iid, target, port in targets:
            base = f"http://{target}:{port}"
            for svc in svcs:
                threading.Thread(target=self._poll_probe_worker,
                                 args=(iid, target, port, svc, base),
                                 daemon=True).start()

    def _poll_probe_worker(self, iid, target, port, svc, base):
        try:
            res = probe_url(base, svc)
        except Exception as e:
            res = {"ok": False, "status_code": None, "summary": str(e),
                   "url": base + svc["path"], "response_time": None,
                   "timestamp": datetime.now().isoformat()}
        self.result_queue.put(("probe_update", {
            "iid": iid, "target": target, "port": port,
            "svc": svc["name"], "res": res,
            "critical": svc.get("critical", False),
        }))
        self.result_queue.put(("poll_done", None))

    # ── queue processing ───────────────────────────────────────────────────────
    def _start_queue_loop(self):
        def poll():
            try:
                for _ in range(50):
                    try:
                        ev, payload = self.result_queue.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        if ev == "scan_ok":
                            self._handle_scan(payload)
                        elif ev == "scan_error":
                            self._handle_scan_error(payload)
                        elif ev in ("probe", "probe_update"):
                            self._handle_probe(payload, update=(ev == "probe_update"))
                        elif ev == "poll_tick":
                            self._run_poll_cycle()
                        elif ev == "poll_countdown":
                            self._poll_next_in = payload
                            self._update_poll_indicator()
                        elif ev == "poll_done":
                            if self._poll_inflight > 0:
                                self._poll_inflight -= 1
                        elif ev == "history_ok":
                            self._open_history_dialog(payload)
                        elif ev == "history_err":
                            self.log("err", f"{payload['host']}: {payload['error']}")
                        elif ev == "error":
                            self.log("err", payload)
                    except Exception as e:
                        self.log("err", f"Queue error: {e}")
            finally:
                self._update_status_counts()
                self._update_stats_label()
                self.after(200, poll)
        poll()

    def _update_poll_indicator(self):
        if not self._polling:
            return
        if self._poll_inflight > 0:
            txt = f"● Polling  ·  {self._poll_inflight} in flight"
        else:
            txt = f"● Polling  ·  next in {self._poll_next_in}s"
        self.poll_indicator.config(text=txt)

    def _handle_scan(self, payload):
        host, items, idx = payload["host"], payload["items"], payload.get("idx")
        if idx is not None and idx < len(self.servers):
            self.servers[idx]["last_scan"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.servers[idx]["last_scan_success"] = True
        self._clear_rows_for_target(host)
        for it in items:
            port = it.get("port", "")
            name = it.get("name", "java-process")
            status = "●  UP" if port else "○  IDLE"
            tag = "up" if port else "idle"
            summary = it.get("jar") or it.get("main_class") or "Java process"
            self.tree.insert("", "end", values=(
                host, it.get("pid", ""), name, port or "N/A",
                "", status, "", datetime.now().strftime("%H:%M:%S"), summary
            ), tags=(tag,))
        self.log("ok", f"{host}: {len(items)} process(es) found")
        self._refresh_targets()
        if hasattr(self, "ov_services_lbl"):
            self.ov_services_lbl.config(text=str(len(self.tree.get_children())))

    def _handle_scan_error(self, payload):
        host, err, idx = payload["host"], payload["error"], payload.get("idx")
        if idx is not None and idx < len(self.servers):
            self.servers[idx]["last_scan"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.servers[idx]["last_scan_success"] = False
        self.log("err", f"{host} scan failed: {err[:80]}")
        self._refresh_targets()

    def _handle_probe(self, payload, update=False):
        target = payload["target"]
        port   = payload["port"]
        svc    = payload["svc"]
        res    = payload["res"]
        critical = payload.get("critical", False)
        hint_iid = payload.get("iid")

        url = res["url"]
        self.history[url].append(res)
        if len(self.history[url]) > MAX_HISTORY_ENTRIES:
            self.history[url] = self.history[url][-MAX_HISTORY_ENTRIES:]

        prev = self.alert_state.get(url, {}).get("last_status")
        if prev is not None and prev != res["ok"]:
            label = "UP" if res["ok"] else "DOWN"
            self.log("info", f"State change: {svc} @ {target}:{port} → {label}")
            if not res["ok"] and critical:
                try:
                    self.master.bell()
                except Exception:
                    pass
        self.alert_state[url] = {"last_status": res["ok"],
                                  "timestamp": res["timestamp"]}

        # find row
        target_iid = None
        if hint_iid and self.tree.exists(hint_iid):
            target_iid = hint_iid
        else:
            for iid in self.tree.get_children():
                try:
                    vals = self.tree.item(iid)["values"]
                    if (len(vals) > 3 and str(vals[0]) == str(target)
                            and str(vals[3]) == str(port)):
                        target_iid = iid
                        break
                except tk.TclError:
                    continue

        if target_iid:
            try:
                rt_raw = res.get("response_time")
                rt = f"{rt_raw:.0f} ms" if rt_raw is not None else "—"
                status = "●  UP" if res["ok"] else "○  DOWN"
                self.tree.set(target_iid, "service",       svc)
                self.tree.set(target_iid, "status",        status)
                self.tree.set(target_iid, "response_time", rt)
                self.tree.set(target_iid, "last_check",    datetime.now().strftime("%H:%M:%S"))
                self.tree.set(target_iid, "summary",       res.get("summary", "")[:60])
                if res["ok"]:
                    tag = "up"
                elif rt_raw and rt_raw > 2000:
                    tag = "warning"
                else:
                    tag = "down"
                self.tree.item(target_iid, tags=(tag,))
            except tk.TclError:
                pass

        if not update:
            icon = "✓" if res["ok"] else "✗"
            rt = (f" ({res.get('response_time', 0):.0f}ms)"
                  if res.get("response_time") else "")
            tag = "ok" if res["ok"] else "err"
            self.log(tag, f"{icon} {svc} @ {target}:{port}{rt}")

    # ── filter / sort / display ────────────────────────────────────────────────
    def _apply_filter(self):
        search = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        show_all = self.show_all_var.get() if hasattr(self, "show_all_var") else True
        for iid in self.tree.get_children(""):
            try:
                vals = self.tree.item(iid)["values"]
                has_port = (len(vals) > 3
                            and str(vals[3]).strip()
                            and str(vals[3]) not in ("N/A", "—"))
                show = True
                if not show_all and not has_port:
                    show = False
                if show and search:
                    if search not in " ".join(str(v).lower() for v in vals):
                        show = False
                if show:
                    self.tree.reattach(iid, "", "end")
                else:
                    self.tree.detach(iid)
            except Exception:
                continue
        self._update_status_counts()

    def _sort_tree(self, col):
        items = [(self.tree.set(iid, col), iid)
                 for iid in self.tree.get_children("")]
        rev = self._sort_state.get(col, False)
        try:
            items.sort(
                key=lambda x: float(
                    re.sub(r"[^\d.]", "", str(x[0])) or "0"),
                reverse=rev)
        except Exception:
            items.sort(reverse=rev)
        for i, (_, iid) in enumerate(items):
            self.tree.move(iid, "", i)
        self._sort_state[col] = not rev

    def _update_status_counts(self):
        up = down = idle = 0
        for iid in self.tree.get_children(""):
            try:
                s = str(self.tree.set(iid, "status"))
                if "UP" in s:
                    up += 1
                elif "DOWN" in s:
                    down += 1
                else:
                    idle += 1
            except Exception:
                idle += 1
        self.pill_up_var.set(f"● {up} up")
        self.pill_down_var.set(f"● {down} down")
        self.pill_idle_var.set(f"● {idle} idle")

    def _update_stats_label(self):
        self.stats_label.config(
            text=(f"Scans: {self.stats['scans']}  ·  "
                  f"Probes: {self.stats['probes']}  ·  "
                  f"Failed: {self.stats['failed']}"))

    def _clear_rows_for_target(self, target):
        for iid in list(self.tree.get_children()):
            try:
                if self.tree.item(iid)["values"][0] == target:
                    self.tree.delete(iid)
            except Exception:
                pass

    def clear_results(self):
        if messagebox.askyesno("Clear", "Clear all discovered services?"):
            self.tree.delete(*self.tree.get_children())
            self.log("info", "Cleared all results")
            self._update_status_counts()

    # ── log ────────────────────────────────────────────────────────────────────
    def log(self, level: str, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}]  ", "ts")
        self.log_text.insert("end", f"{text}\n", level)
        self.log_text.see("end")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 600:
            self.log_text.delete("1.0", "100.0")

    # ── context menu helpers ───────────────────────────────────────────────────
    def _show_ctx(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.ctx.post(event.x_root, event.y_root)

    def _copy_url(self):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0])["values"]
            if vals[3] and vals[3] != "N/A":
                url = f"http://{vals[0]}:{vals[3]}"
                self.master.clipboard_clear()
                self.master.clipboard_append(url)
                self.log("info", f"Copied: {url}")

    def _open_browser(self):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0])["values"]
            if vals[3] and vals[3] != "N/A":
                url = f"http://{vals[0]}:{vals[3]}"
                webbrowser.open(url)

    def _delete_selected(self):
        sel = self.tree.selection()
        if sel and messagebox.askyesno("Delete", f"Delete {len(sel)} item(s)?"):
            for iid in sel:
                self.tree.delete(iid)
            self._update_status_counts()

    def _view_details(self):
        sel = self.tree.selection()
        if sel:
            DetailsDialog(self.master, self.tree.item(sel[0])["values"], theme=self.t)

    def _view_item_history(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])["values"]
        target, port = vals[0], vals[3]
        if not port or port == "N/A":
            messagebox.showinfo("History", "No port info available.")
            return
        base = f"http://{target}:{port}"
        entries = []
        for url, hist in self.history.items():
            if url.startswith(base):
                entries.extend(hist[-20:])
        if not entries:
            messagebox.showinfo("History", "No history available yet.")
            return
        HistoryDialog(self.master, f"{target}:{port}", entries, theme=self.t)

    # ── dialogs ────────────────────────────────────────────────────────────────
    def add_custom_service(self):
        dlg = CustomServiceDialog(self.master, theme=self.t)
        self.master.wait_window(dlg.top)
        if dlg.result:
            self.custom_services.append(dlg.result)
            self.log("info", f"Added custom service: {dlg.result['name']}")
            self.save_config(silent=True)

    def show_server_history(self):
        sel = self.target_listbox.curselection()
        if not sel:
            messagebox.showinfo("Shell", "Select a target first.")
            return
        server = self.servers[sel[0]]
        self.log("info", f"Fetching history from {server['host']}…")
        threading.Thread(target=self._fetch_history_worker,
                         args=(server,), daemon=True).start()

    def _fetch_history_worker(self, server):
        out, err = get_server_history(
            server["host"], server["username"],
            password=server.get("password"),
            pkey_path=server.get("pkey"),
            port=server.get("port", 22))
        if err:
            self.result_queue.put(("history_err",
                                   {"host": server["host"], "error": err}))
        else:
            self.result_queue.put(("history_ok",
                                   {"host": server["host"],
                                    "history": out,
                                    "server_config": server}))

    def _open_history_dialog(self, payload):
        UnixHistoryDialog(self.master,
                          payload["host"],
                          payload["history"],
                          payload.get("server_config"),
                          theme=self.t)

    def show_statistics(self):
        items = self.tree.get_children()
        total = len(items)
        up   = sum(1 for i in items if "UP"   in str(self.tree.set(i, "status")))
        down = sum(1 for i in items if "DOWN" in str(self.tree.set(i, "status")))
        rts  = []
        for i in items:
            v = self.tree.set(i, "response_time")
            if v and v not in ("—", "N/A"):
                try:
                    rts.append(float(re.sub(r"[^\d.]", "", v)))
                except Exception:
                    pass
        avg = sum(rts)/len(rts) if rts else 0
        uptime = up/total*100 if total else 0
        messagebox.showinfo("Statistics",
            f"Services:  {total}  (up: {up}, down: {down}, {uptime:.1f}% uptime)\n\n"
            f"Scans:   {self.stats['scans']}\n"
            f"Probes:  {self.stats['probes']}\n"
            f"Failed:  {self.stats['failed']}\n\n"
            f"Avg response: {avg:.0f} ms\n"
            f"Tracked URLs: {len(self.history)}")

    def show_history(self):
        if not self.history:
            messagebox.showinfo("History", "No history yet.")
            return
        entries = []
        for h in self.history.values():
            entries.extend(h[-50:])
        HistoryDialog(self.master, "All Services", entries, theme=self.t)

    def show_server_event_log(self):
        if not self.server_history:
            messagebox.showinfo("Event Log", "No events recorded yet.")
            return
        ServerEventsDialog(self.master, dict(self.server_history), theme=self.t)

    def show_about(self):
        messagebox.showinfo(f"About {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\nClean, modern Java process monitor.\n\n"
            "SSH scanning · Port detection · HTTP probing\n"
            "Light & dark themes · History & analytics")

    def show_shortcuts(self):
        messagebox.showinfo("Shortcuts",
            "Ctrl+N   Add remote target\n"
            "Ctrl+S   Save config\n"
            "Ctrl+E   Export results\n"
            "F5       Scan selected\n"
            "Ctrl+F5  Scan all\n"
            "Ctrl+Space  Toggle polling\n"
            "Ctrl+T   Toggle theme\n"
            "Ctrl+I   Statistics\n"
            "Ctrl+H   Service history\n"
            "F1       Shortcuts\n"
            "Ctrl+Q   Quit")

    # ── import/export ──────────────────────────────────────────────────────────
    def export_results(self):
        fn = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            initialfile=f'portix_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        if not fn:
            return
        data = [{"target": v[0], "pid": v[1], "name": v[2], "port": v[3],
                  "service": v[4], "status": v[5], "response_time": v[6],
                  "last_check": v[7], "summary": v[8]}
                for iid in self.tree.get_children()
                for v in [self.tree.item(iid)["values"]]]
        try:
            with open(fn, "w") as f:
                json.dump({"export_time": datetime.now().isoformat(),
                           "services": data}, f, indent=2)
            self.log("ok", f"Exported {len(data)} results")
            messagebox.showinfo("Export", f"Exported {len(data)} results to {fn}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def export_history(self):
        fn = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not fn:
            return
        try:
            with open(fn, "w") as f:
                json.dump({"export_time": datetime.now().isoformat(),
                           "history": dict(self.history)}, f, indent=2)
            total = sum(len(h) for h in self.history.values())
            self.log("ok", f"Exported {total} history entries")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _save_log(self):
        fn = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if not fn:
            return
        try:
            with open(fn, "w") as f:
                f.write(self.log_text.get("1.0", "end"))
            self.log("ok", f"Saved log to {fn}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ── config ─────────────────────────────────────────────────────────────────
    def save_config(self, silent=False):
        try:
            cfg = {"servers": self.servers,
                   "custom_services": self.custom_services,
                   "poll_interval": self._poll_interval,
                   "theme": self.theme_name}
            with open(CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
            if not silent:
                self.log("ok", "Config saved")
                messagebox.showinfo("Save Config", "Saved.")
        except Exception as e:
            if not silent:
                messagebox.showerror("Save Error", str(e))

    def load_config(self):
        fn = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not fn:
            return
        self._apply_config_file(fn)
        messagebox.showinfo("Load Config", "Configuration loaded.")

    def _load_config_auto(self):
        if CONFIG_FILE.exists():
            try:
                self._apply_config_file(str(CONFIG_FILE))
                self.log("info", f"Config loaded from {CONFIG_FILE.name}")
            except Exception as e:
                self.log("err", f"Config load failed: {e}")

    def _apply_config_file(self, path):
        with open(path) as f:
            cfg = json.load(f)
        self.servers = cfg.get("servers", [])
        self.custom_services = cfg.get("custom_services", [])
        self._poll_interval = cfg.get("poll_interval", DEFAULT_POLL_SECONDS)
        theme = cfg.get("theme", "light")
        if theme in THEMES and theme != self.theme_name:
            self.theme_name = theme
            self.t = THEMES[self.theme_name]
            self._build_styles()
            self._apply_theme_to_widgets()
            lbl = "☀  Light" if self.theme_name == "dark" else "🌙  Dark"
            if hasattr(self, "theme_btn"):
                self.theme_btn.configure(text=lbl)
        self._refresh_targets()


# ── Themed dialog base ────────────────────────────────────────────────────────
class _ThemedDialog:
    def _center(self, w=None, h=None):
        self.top.update_idletasks()
        w = w or self.top.winfo_width()
        h = h or self.top.winfo_height()
        x = (self.top.winfo_screenwidth()  - w) // 2
        y = (self.top.winfo_screenheight() - h) // 2
        self.top.geometry(f"{w}x{h}+{max(x,0)}+{max(y,0)}")


# ── Remote Dialog ─────────────────────────────────────────────────────────────
class RemoteDialog(_ThemedDialog):
    def __init__(self, master, edit_data=None, theme=None):
        self.theme = theme or THEMES["light"]
        self.top = tk.Toplevel(master)
        self.top.title("Remote Target")
        self.top.configure(bg=self.theme["bg"])
        self.result = None
        self.edit_data = edit_data
        self._build()
        self.top.transient(master)
        self.top.grab_set()
        self._center(w=480, h=490)

    def _build(self):
        t = self.theme
        wrap = ttk.Frame(self.top, padding=22)
        wrap.pack(fill="both", expand=True)
        wrap.grid_columnconfigure(0, weight=1)

        title = "Edit target" if self.edit_data else "Add remote target"
        ttk.Label(wrap, text=title, font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w")
        ttk.Label(wrap, text="SSH connection details",
                  style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 16))

        self.vars = {}
        ed = self.edit_data or {}

        def field(label, key, default="", show=None, row=0):
            ttk.Label(wrap, text=label).grid(row=row, column=0, sticky="w", pady=(6, 2))
            v = tk.StringVar(value=default)
            self.vars[key] = v
            ttk.Entry(wrap, textvariable=v, show=show).grid(
                row=row+1, column=0, sticky="we")

        field("Host *",                "host",     ed.get("host", ""),     row=2)
        field("Port",                  "port",     str(ed.get("port", 22)), row=4)
        field("Username *",            "username", ed.get("username", ""), row=6)
        field("Password",              "password", ed.get("password", ""), show="•", row=8)

        ttk.Label(wrap, text="Private key path").grid(
            row=10, column=0, sticky="w", pady=(6, 2))
        pkey_row = ttk.Frame(wrap)
        pkey_row.grid(row=11, column=0, sticky="we")
        pkey_row.grid_columnconfigure(0, weight=1)
        self.vars["pkey"] = tk.StringVar(value=ed.get("pkey", ""))
        ttk.Entry(pkey_row, textvariable=self.vars["pkey"]).grid(
            row=0, column=0, sticky="we", padx=(0, 6))
        ttk.Button(pkey_row, text="Browse…", command=self._browse).grid(row=0, column=1)

        btns = ttk.Frame(wrap)
        btns.grid(row=12, column=0, sticky="we", pady=(18, 0))
        ttk.Button(btns, text="Test", command=self.test).pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.top.destroy).pack(
            side="right", padx=(6, 0))
        ttk.Button(btns, text="Update" if self.edit_data else "Add",
                   style="Primary.TButton",
                   command=self.on_ok).pack(side="right")

    def _browse(self):
        fn = filedialog.askopenfilename(title="Select Private Key")
        if fn:
            self.vars["pkey"].set(fn)

    def _get_data(self):
        data = {k: v.get().strip() for k, v in self.vars.items() if v.get().strip()}
        if not data.get("host"):
            messagebox.showerror("Error", "Host is required.", parent=self.top)
            return None
        if not data.get("username"):
            messagebox.showerror("Error", "Username is required.", parent=self.top)
            return None
        try:
            data["port"] = int(data.get("port", 22))
        except Exception:
            messagebox.showerror("Error", "Port must be a number.", parent=self.top)
            return None
        return data

    def test(self):
        data = self._get_data()
        if not data:
            return
        try:
            self.top.config(cursor="watch")
            self.top.update()
            out, err = ssh_run(data["host"], data["username"],
                               password=data.get("password"),
                               pkey_path=data.get("pkey"),
                               port=data.get("port", 22),
                               timeout=5, cmd='echo "PORTIX_OK"')
            if "PORTIX_OK" in out:
                messagebox.showinfo("Test", "Connection successful!", parent=self.top)
            else:
                messagebox.showerror("Test", f"Failed:\n{err}", parent=self.top)
        except Exception as e:
            messagebox.showerror("Test", str(e), parent=self.top)
        finally:
            self.top.config(cursor="")

    def on_ok(self):
        data = self._get_data()
        if data:
            self.result = data
            self.top.destroy()


# ── Custom Service Dialog ─────────────────────────────────────────────────────
class CustomServiceDialog(_ThemedDialog):
    def __init__(self, master, theme=None):
        self.theme = theme or THEMES["light"]
        self.top = tk.Toplevel(master)
        self.top.title("Custom Service")
        self.top.configure(bg=self.theme["bg"])
        self.top.resizable(False, False)
        self.result = None
        self._build()
        self.top.transient(master)
        self.top.grab_set()
        self._center(w=440, h=320)

    def _build(self):
        wrap = ttk.Frame(self.top, padding=22)
        wrap.pack(fill="both", expand=True)
        wrap.grid_columnconfigure(0, weight=1)

        ttk.Label(wrap, text="Add custom service",
                  font=("Segoe UI", 14, "bold")).grid(row=0, sticky="w")
        ttk.Label(wrap, text="Custom HTTP endpoint to probe",
                  style="Muted.TLabel").grid(row=1, sticky="w", pady=(2, 14))

        for row, (lbl, attr, default) in enumerate([
            ("Name",                   "name_var",   ""),
            ("Path",                   "path_var",   "/"),
            ("Expected text (optional)", "expect_var", ""),
        ]):
            ttk.Label(wrap, text=lbl).grid(row=2+row*2, sticky="w", pady=(6, 2))
            v = tk.StringVar(value=default)
            setattr(self, attr, v)
            ttk.Entry(wrap, textvariable=v).grid(row=3+row*2, sticky="we")

        self.critical_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(wrap, text="Critical — alert on failure",
                        variable=self.critical_var).grid(row=9, sticky="w", pady=(10, 0))

        btns = ttk.Frame(wrap)
        btns.grid(row=10, sticky="we", pady=(18, 0))
        ttk.Button(btns, text="Cancel", command=self.top.destroy).pack(
            side="right", padx=(6, 0))
        ttk.Button(btns, text="Add", style="Primary.TButton",
                   command=self.on_ok).pack(side="right")

    def on_ok(self):
        name = self.name_var.get().strip()
        path = self.path_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Name required.", parent=self.top)
            return
        if not path:
            messagebox.showerror("Error", "Path required.", parent=self.top)
            return
        if not path.startswith("/"):
            path = "/" + path
        self.result = {"name": name, "path": path,
                       "expect": self.expect_var.get().strip(),
                       "critical": self.critical_var.get()}
        self.top.destroy()


# ── Details Dialog ────────────────────────────────────────────────────────────
class DetailsDialog(_ThemedDialog):
    def __init__(self, master, vals, theme=None):
        self.theme = theme or THEMES["light"]
        self.top = tk.Toplevel(master)
        self.top.title("Service Details")
        self.top.configure(bg=self.theme["surface"])
        self._build(vals)
        self.top.transient(master)
        self.top.grab_set()
        self._center(w=520, h=440)

    def _build(self, vals):
        wrap = ttk.Frame(self.top, padding=22)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="Service details",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(wrap, text=f"{vals[2]} on {vals[0]}:{vals[3]}",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 16))

        card = ttk.LabelFrame(wrap, text="Info", padding=12)
        card.pack(fill="both", expand=True)
        card.grid_columnconfigure(1, weight=1)

        pairs = [("Target", vals[0]), ("PID", vals[1]), ("Application", vals[2]),
                 ("Port", vals[3]), ("Service", vals[4] or "—"),
                 ("Status", vals[5] or "—"), ("Response Time", vals[6] or "—"),
                 ("Last Check", vals[7] or "—"), ("Details", vals[8] or "—")]
        for r, (k, v) in enumerate(pairs):
            ttk.Label(card, text=k, style="SurfaceMuted.TLabel").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=3)
            ttk.Label(card, text=str(v), style="Surface.TLabel",
                      wraplength=340, justify="left").grid(
                row=r, column=1, sticky="w", pady=3)

        ttk.Button(wrap, text="Close", command=self.top.destroy,
                   style="Primary.TButton").pack(pady=(16, 0), anchor="e")


# ── Unix History Dialog ───────────────────────────────────────────────────────
class UnixHistoryDialog(_ThemedDialog):
    def __init__(self, master, host, history_output, server_config=None, theme=None):
        self.theme = theme or THEMES["light"]
        self.top = tk.Toplevel(master)
        self.top.title(f"Remote Shell — {host}")
        self.top.geometry("1100x760")
        self.top.configure(bg=self.theme["bg"])
        self.host = host
        self.server_config = server_config
        self.cmd_queue: queue.Queue = queue.Queue()
        self.all_cmds: list[tuple[str, str]] = []
        self._build(history_output)
        self.top.transient(master)
        self._parse_history(history_output)
        self._start_cmd_processor()

    def _build(self, history_output):
        t = self.theme
        frm = ttk.Frame(self.top, padding=16)
        frm.pack(fill="both", expand=True)
        frm.grid_rowconfigure(1, weight=2)
        frm.grid_rowconfigure(2, weight=3)
        frm.grid_columnconfigure(0, weight=1)

        hdr = ttk.Frame(frm)
        hdr.grid(row=0, sticky="we", pady=(0, 10))
        hdr.grid_columnconfigure(1, weight=1)
        ttk.Label(hdr, text=f"Remote Shell — {self.host}",
                  font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.conn_label = ttk.Label(hdr, text="● Connected",
                                    foreground=t["success"],
                                    background=t["bg"])
        self.conn_label.grid(row=0, column=1, sticky="e")

        # history
        hist = ttk.LabelFrame(frm, text="Command history", padding=10)
        hist.grid(row=1, sticky="nswe", pady=(0, 8))
        hist.grid_rowconfigure(1, weight=1)
        hist.grid_columnconfigure(0, weight=1)

        sr = ttk.Frame(hist)
        sr.grid(row=0, sticky="we", pady=(0, 6))
        sr.grid_columnconfigure(1, weight=1)
        ttk.Label(sr, text="Filter").grid(row=0, column=0, padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._refresh_list())
        ttk.Entry(sr, textvariable=self.search_var).grid(row=0, column=1, sticky="we")
        ttk.Button(sr, text="Clear",
                   command=lambda: self.search_var.set("")).grid(row=0, column=2, padx=(6, 0))

        lw = tk.Frame(hist, bg=t["border"])
        lw.grid(row=1, sticky="nswe")
        lw.grid_rowconfigure(0, weight=1)
        lw.grid_columnconfigure(0, weight=1)
        self.hist_lb = tk.Listbox(lw, font=("Consolas", 10), selectmode="extended",
                                   activestyle="none", bg=t["surface2"], fg=t["text"],
                                   selectbackground=t["accent_bg"], selectforeground=t["text"],
                                   relief="flat", bd=0, highlightthickness=0)
        self.hist_lb.grid(row=0, column=0, sticky="nswe", padx=1, pady=1)
        vsb = ttk.Scrollbar(lw, orient="vertical", command=self.hist_lb.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.hist_lb.configure(yscrollcommand=vsb.set)
        self.hist_lb.bind("<Double-Button-1>", self._run_from_list)
        self.info_lbl = ttk.Label(hist, text="Double-click to run",
                                  style="Muted.TLabel", font=("Segoe UI", 9))
        self.info_lbl.grid(row=2, sticky="w", pady=(4, 0))

        # exec
        exec_frm = ttk.LabelFrame(frm, text="Execute on server", padding=10)
        exec_frm.grid(row=2, sticky="nswe")
        exec_frm.grid_rowconfigure(1, weight=1)
        exec_frm.grid_columnconfigure(0, weight=1)

        cmd_row = ttk.Frame(exec_frm)
        cmd_row.grid(row=0, sticky="we", pady=(0, 8))
        cmd_row.grid_columnconfigure(1, weight=1)
        ttk.Label(cmd_row, text="$", font=("Consolas", 13, "bold")).grid(
            row=0, column=0, padx=(0, 8))
        self.cmd_var = tk.StringVar()
        self.cmd_entry = ttk.Entry(cmd_row, textvariable=self.cmd_var,
                                    font=("Consolas", 11))
        self.cmd_entry.grid(row=0, column=1, sticky="we")
        self.cmd_entry.bind("<Return>", lambda e: self._execute())
        self.cmd_entry.focus()
        ttk.Button(cmd_row, text="Run", style="Primary.TButton",
                   command=self._execute).grid(row=0, column=2, padx=(8, 0))

        out_wrap = tk.Frame(exec_frm, bg=t["border"], bd=0, highlightthickness=0)
        out_wrap.grid(row=1, sticky="nswe")
        out_wrap.grid_rowconfigure(0, weight=1)
        out_wrap.grid_columnconfigure(0, weight=1)
        self.out_text = tk.Text(out_wrap, font=("Consolas", 10),
                                bg=t["term_bg"], fg=t["term_fg"],
                                insertbackground=t["term_fg"],
                                wrap="none", relief="flat", bd=0,
                                highlightthickness=0, padx=10, pady=10)
        self.out_text.grid(row=0, column=0, sticky="nswe", padx=1, pady=1)
        ovsb = ttk.Scrollbar(out_wrap, orient="vertical", command=self.out_text.yview)
        ovsb.grid(row=0, column=1, sticky="ns")
        ohsb = ttk.Scrollbar(out_wrap, orient="horizontal", command=self.out_text.xview)
        ohsb.grid(row=1, column=0, sticky="we")
        self.out_text.configure(yscrollcommand=ovsb.set, xscrollcommand=ohsb.set)

        self._log_out(f"Connected to {self.host}\n", t["term_accent"])
        self._log_out("Type a command and press Run.\n\n", t["term_fg"])

        footer = ttk.Frame(frm)
        footer.grid(row=3, sticky="we", pady=(8, 0))
        ttk.Button(footer, text="Close", command=self.top.destroy).pack(side="right")

    def _parse_history(self, text):
        if not text:
            return
        for i, line in enumerate(text.strip().split("\n"), 1):
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^\s*(\d+)\s+(.*)$", line)
            self.all_cmds.append(m.groups() if m else (str(i), line))
        self._refresh_list()

    def _refresh_list(self):
        t = self.theme
        self.hist_lb.delete(0, tk.END)
        q = self.search_var.get().lower()
        count = 0
        for num, cmd in self.all_cmds:
            if q and q not in cmd.lower():
                continue
            self.hist_lb.insert(tk.END, f"{num:>5}   {cmd}")
            low = cmd.lower()
            if any(k in low for k in ["rm -", "sudo rm", "kill", "shutdown"]):
                self.hist_lb.itemconfig(tk.END, fg=t["danger"])
            elif any(k in low for k in ["java", "mvn", "gradle"]):
                self.hist_lb.itemconfig(tk.END, fg=t["success"])
            count += 1
        self.info_lbl.config(text=f"{count} of {len(self.all_cmds)} commands")

    def _run_from_list(self, _e=None):
        sel = self.hist_lb.curselection()
        if not sel:
            return
        item = self.hist_lb.get(sel[0])
        m = re.match(r"^\s*\d*\s*(.*)$", item)
        if m:
            self.cmd_var.set(m.group(1).strip())
            self._execute()

    def _execute(self):
        cmd = self.cmd_var.get().strip()
        if not cmd or not self.server_config:
            return
        t = self.theme
        self._log_out(f"\n$ {cmd}\n", t["term_accent"])
        self.conn_label.config(text="● Running…", foreground=t["warning"])
        self.cmd_entry.config(state="disabled")
        threading.Thread(target=self._exec_worker, args=(cmd,), daemon=True).start()

    def _exec_worker(self, cmd):
        out, err = ssh_run(self.server_config["host"],
                           self.server_config["username"],
                           password=self.server_config.get("password"),
                           pkey_path=self.server_config.get("pkey"),
                           port=self.server_config.get("port", 22),
                           cmd=cmd, timeout=30)
        self.cmd_queue.put(("result", {"out": out, "err": err}))

    def _start_cmd_processor(self):
        def process():
            t = self.theme
            try:
                while True:
                    try:
                        ev, data = self.cmd_queue.get_nowait()
                        if ev == "result":
                            if data["out"]:
                                self._log_out(data["out"], t["term_fg"])
                            if data["err"]:
                                self._log_out(f"\n{data['err']}\n", t["danger"])
                            if not data["out"] and not data["err"]:
                                self._log_out("(no output)\n", t["text3"])
                            self.conn_label.config(text="● Connected",
                                                   foreground=t["success"])
                    except queue.Empty:
                        break
            finally:
                self.cmd_entry.config(state="normal")
                self.top.after(100, process)
        process()

    def _log_out(self, text, color):
        self.out_text.config(state="normal")
        tag = f"c_{color.replace('#', '')}"
        self.out_text.tag_configure(tag, foreground=color)
        self.out_text.insert("end", text, tag)
        self.out_text.see("end")
        self.out_text.config(state="disabled")


# ── Server Events Dialog ──────────────────────────────────────────────────────
class ServerEventsDialog(_ThemedDialog):
    def __init__(self, master, server_history, theme=None):
        self.theme = theme or THEMES["light"]
        self.top = tk.Toplevel(master)
        self.top.title("Server Event Log")
        self.top.geometry("1000x620")
        self.top.configure(bg=self.theme["bg"])
        self._build(server_history)
        self.top.transient(master)

    def _build(self, server_history):
        t = self.theme
        frm = ttk.Frame(self.top, padding=16)
        frm.pack(fill="both", expand=True)
        frm.grid_rowconfigure(1, weight=1)
        frm.grid_columnconfigure(0, weight=1)

        ttk.Label(frm, text="Server Event Log",
                  font=("Segoe UI", 14, "bold")).grid(row=0, sticky="w", pady=(0, 10))

        tw = tk.Frame(frm, bg=t["border"])
        tw.grid(row=1, sticky="nswe")
        tw.grid_rowconfigure(0, weight=1)
        tw.grid_columnconfigure(0, weight=1)
        cols = ("id", "timestamp", "server", "type", "message")
        tree = ttk.Treeview(tw, columns=cols, show="headings")
        for c, txt, w, s in [("#", "id", 50, False), ("Timestamp", "timestamp", 160, False),
                               ("Server", "server", 150, False), ("Type", "type", 100, False),
                               ("Event", "message", 480, True)]:
            tree.heading(txt, text=c)
            tree.column(txt, width=w, stretch=s)

        all_events = sorted(
            [(h, e) for h, evs in server_history.items() for e in evs],
            key=lambda x: x[1]["timestamp"], reverse=True)
        for idx, (host, ev) in enumerate(all_events, 1):
            et = ev["type"]
            tag = "scan" if et == "scan" else ("err" if et == "error" else ())
            tree.insert("", "end",
                        values=(idx, ev["timestamp"][:19], host,
                                et.upper(), ev["message"]),
                        tags=(tag,) if tag else ())
        tree.tag_configure("scan", foreground=t["accent"])
        tree.tag_configure("err",  foreground=t["danger"], background=t["danger_bg"])
        tree.grid(row=0, column=0, sticky="nswe", padx=1, pady=1)
        vsb = ttk.Scrollbar(tw, orient="vertical", command=tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=vsb.set)

        footer = ttk.Frame(frm)
        footer.grid(row=2, sticky="we", pady=(10, 0))
        ttk.Label(footer,
                  text=f"{len(all_events)} events across {len(server_history)} servers",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Close", command=self.top.destroy).pack(side="right")


# ── History Dialog ────────────────────────────────────────────────────────────
class HistoryDialog(_ThemedDialog):
    def __init__(self, master, title, history_entries, theme=None):
        self.theme = theme or THEMES["light"]
        self.top = tk.Toplevel(master)
        self.top.title(f"History — {title}")
        self.top.geometry("880x580")
        self.top.configure(bg=self.theme["bg"])
        self._build(title, history_entries)
        self.top.transient(master)

    def _build(self, title, entries):
        t = self.theme
        frm = ttk.Frame(self.top, padding=16)
        frm.pack(fill="both", expand=True)
        frm.grid_rowconfigure(1, weight=1)
        frm.grid_columnconfigure(0, weight=1)

        ttk.Label(frm, text=f"History — {title}",
                  font=("Segoe UI", 13, "bold")).grid(row=0, sticky="w", pady=(0, 10))

        tw = tk.Frame(frm, bg=t["border"])
        tw.grid(row=1, sticky="nswe")
        tw.grid_rowconfigure(0, weight=1)
        tw.grid_columnconfigure(0, weight=1)

        cols = ("timestamp", "status", "response_time", "code", "summary")
        tree = ttk.Treeview(tw, columns=cols, show="headings")
        for c, txt, w, s in [
            ("timestamp", "Timestamp", 160, False),
            ("status", "Status", 90, False),
            ("response_time", "Response", 100, False),
            ("code", "HTTP", 70, False),
            ("summary", "Details", 380, True),
        ]:
            tree.heading(c, text=txt)
            tree.column(c, width=w, stretch=s)

        for e in sorted(entries, key=lambda x: x["timestamp"], reverse=True):
            status = "● OK" if e["ok"] else "○ FAIL"
            rt = f"{e.get('response_time', 0):.0f} ms" if e.get("response_time") else "—"
            iid = tree.insert("", "end", values=(
                e["timestamp"][:19], status, rt,
                e.get("status_code", "—"), e.get("summary", "")))
            tree.item(iid, tags=("ok",) if e["ok"] else ("fail",))

        tree.tag_configure("ok",   background=t["success_bg"], foreground=t["success"])
        tree.tag_configure("fail", background=t["danger_bg"],  foreground=t["danger"])
        tree.grid(row=0, column=0, sticky="nswe", padx=1, pady=1)
        vsb = ttk.Scrollbar(tw, orient="vertical", command=tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=vsb.set)

        total   = len(entries)
        success = sum(1 for e in entries if e["ok"])
        footer = ttk.Frame(frm)
        footer.grid(row=2, sticky="we", pady=(10, 0))
        uptime = success/total*100 if total else 0
        ttk.Label(footer,
                  text=f"{total} checks · {success} ok · {uptime:.1f}% uptime",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Close", command=self.top.destroy).pack(side="right")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    app = PortixApp(root)

    binds = [
        ("<F5>",           lambda e: app.scan_selected()),
        ("<Control-F5>",   lambda e: app.scan_all()),
        ("<Control-n>",    lambda e: app.open_add_remote()),
        ("<Control-space>",lambda e: app.toggle_polling()),
        ("<Control-s>",    lambda e: app.save_config()),
        ("<Control-e>",    lambda e: app.export_results()),
        ("<Control-t>",    lambda e: app.toggle_theme()),
        ("<Control-i>",    lambda e: app.show_statistics()),
        ("<Control-h>",    lambda e: app.show_history()),
        ("<Control-r>",    lambda e: app.show_server_event_log()),
        ("<Control-q>",    lambda e: root.quit()),
        ("<Delete>",       lambda e: app._delete_selected()),
        ("<F1>",           lambda e: app.show_shortcuts()),
    ]
    for key, cmd in binds:
        root.bind(key, cmd)

    root.update()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"1480x860+{max((sw-1480)//2,0)}+{max((sh-860)//2,0)}")
    root.mainloop()


if __name__ == "__main__":
    main()
