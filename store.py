"""
Daftyon App Store
A modern desktop application store for downloading and managing Daftyon applications
"""

import os
import shutil
import json
import threading
from pathlib import Path
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import hashlib
import requests
from urllib.parse import urljoin

# Set appearance mode and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AppCard(ctk.CTkFrame):
    """Custom widget for displaying an app in the store - Brofdi Store design"""
    
    def __init__(self, parent, app_data, download_callback, details_callback):
        super().__init__(parent, corner_radius=15, fg_color=("white", "gray20"), 
                         width=220, height=140, border_width=1, 
                         border_color=("gray80", "gray30"))
        
        self.app_data = app_data
        self.download_callback = download_callback
        self.details_callback = details_callback
        self.grid_propagate(False)
        
        # Main container with padding
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=12)
        
        # Top row: App name and info button
        top_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        top_frame.pack(fill="x")
        
        # App name - left aligned
        name_label = ctk.CTkLabel(
            top_frame,
            text=app_data['name'],
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
            text_color=("gray10", "white")
        )
        name_label.pack(side="left", fill="x", expand=True)
        
        # Info button - circular
        info_btn = ctk.CTkButton(
            top_frame,
            text="ⓘ",
            width=24,
            height=24,
            corner_radius=12,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=("gray85", "gray35"),
            border_width=1,
            border_color=("gray60", "gray50"),
            command=lambda: self.details_callback(app_data)
        )
        info_btn.pack(side="right")
        
        # Stars rating display
        stars_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        stars_frame.pack(pady=(8, 4))
        
        avg_rating = app_data.get('averageRating', 0)
        total_ratings = app_data.get('totalRatings', 0)
        
        # Display 5 stars
        stars_text = self._get_stars_display(avg_rating)
        stars_label = ctk.CTkLabel(
            stars_frame,
            text=stars_text,
            font=ctk.CTkFont(size=16),
            text_color="orange"
        )
        stars_label.pack()
        
        # Rating text (e.g., "4.0 (3)")
        rating_text = f"{avg_rating} ({total_ratings})"
        rating_label = ctk.CTkLabel(
            content_frame,
            text=rating_text,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        rating_label.pack(pady=(0, 8))
        
        # Download button with icon and count
        download_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        download_frame.pack()
        
        self.download_btn = ctk.CTkButton(
            download_frame,
            text=f"⬇ {app_data.get('downloadCount', 0)}",
            width=100,
            height=30,
            corner_radius=8,
            command=self.on_download,
            font=ctk.CTkFont(size=12),
            fg_color=("gray75", "gray40"),
            hover_color=("gray65", "gray35"),
            text_color=("gray10", "white")
        )
        self.download_btn.pack()
        
        # Progress bar (hidden by default)
        self.progress = ctk.CTkProgressBar(content_frame, width=100)
        self.progress.set(0)
    
    def _get_stars_display(self, rating):
        """Generate star display based on rating (0-5)"""
        full_stars = int(rating)
        half_star = 1 if (rating - full_stars) >= 0.5 else 0
        empty_stars = 5 - full_stars - half_star
        
        stars = "★" * full_stars
        if half_star:
            stars += "⯨"  # Half star
        stars += "☆" * empty_stars
        
        return stars
    
    def on_download(self):
        """Handle download button click"""
        self.download_callback(self.app_data, self)
    
    def show_progress(self):
        """Show progress bar and hide download button"""
        self.download_btn.pack_forget()
        self.progress.pack()
    
    def update_progress(self, value):
        """Update progress bar value (0.0 to 1.0)"""
        self.progress.set(value)
    
    def download_complete(self, success=True):
        """Show completion state"""
        self.progress.pack_forget()
        if success:
            self.download_btn.configure(
                text="✓ Done",
                fg_color="green",
                hover_color="darkgreen",
                state="disabled"
            )
        else:
            # Reset to original state
            count = self.app_data.get('downloadCount', 0)
            self.download_btn.configure(
                text=f"⬇ {count}",
                fg_color=("gray75", "gray40"),
                hover_color=("gray65", "gray35")
            )
        self.download_btn.pack()


class DaftyonAppStore(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Brofdi Store")
        self.geometry("1100x700")
        self.minsize(900, 600)
        
        # API configuration
        self.api_base_url = "http://172.20.120.78:4200"
        self.api_endpoint = f"{self.api_base_url}/api/templates"
        
        # Download directory
        self.download_dir = Path.home() / "Downloads" / "Daftyon Apps"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # App data storage
        self.apps = []
        
        self.create_widgets()
        self.fetch_apps()
    
    def create_widgets(self):
        """Create all UI widgets"""
        
        # Header
        header = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color=("gray85", "gray15"))
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)
        
        # Logo/Title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=30, pady=20)
        
        title = ctk.CTkLabel(
            title_frame,
            text="🏪 Brofdi",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=("gray10", "gray90")
        )
        title.pack(side="left")
        
        subtitle = ctk.CTkLabel(
            title_frame,
            text="Store",
            font=ctk.CTkFont(size=28),
            text_color=("gray40", "gray60")
        )
        subtitle.pack(side="left", padx=(5, 0))
        
        # Settings button
        settings_btn = ctk.CTkButton(
            header,
            text="⚙️ Settings",
            width=120,
            height=35,
            corner_radius=8,
            command=self.open_settings,
            fg_color="transparent",
            border_width=2
        )
        settings_btn.pack(side="right", padx=30, pady=20)
        
        # Search and filter bar
        control_frame = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="transparent")
        control_frame.pack(fill="x", padx=20, pady=(10, 0))
        control_frame.pack_propagate(False)
        
        # Search box
        self.search_var = ctk.StringVar()
        self.search_var.trace('w', self.filter_apps)
        
        search_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        search_frame.pack(side="left", fill="x", expand=True)
        
        search_label = ctk.CTkLabel(search_frame, text="🔍", font=ctk.CTkFont(size=18))
        search_label.pack(side="left", padx=(0, 10))
        
        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search apps...",
            height=40,
            textvariable=self.search_var,
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            control_frame,
            text="🔄 Refresh",
            width=100,
            height=40,
            corner_radius=8,
            command=self.fetch_apps
        )
        refresh_btn.pack(side="right", padx=(10, 0))
        
        # View mode selector
        view_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        view_frame.pack(side="right", padx=(10, 0))
        
        view_label = ctk.CTkLabel(view_frame, text="Grid:", font=ctk.CTkFont(size=12))
        view_label.pack(side="left", padx=(0, 5))
        
        self.columns_var = ctk.IntVar(value=5)
        columns_menu = ctk.CTkOptionMenu(
            view_frame,
            values=["3", "4", "5", "6"],
            variable=self.columns_var,
            width=70,
            height=40,
            command=lambda x: self.display_apps(self.current_apps)
        )
        columns_menu.pack(side="left")
        
        # Main content area with canvas and scrollbar for grid
        canvas_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        canvas_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Create canvas
        self.canvas = ctk.CTkCanvas(canvas_frame, bg=self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"]), 
                                    highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create scrollbar
        scrollbar = ctk.CTkScrollbar(canvas_frame, command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        
        # Configure canvas
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create frame inside canvas for grid
        self.grid_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        
        # Bind events for scrolling
        self.grid_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Bind mouse wheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Store current apps for re-rendering
        self.current_apps = []
        
        # Status bar
        self.status_bar = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color=("gray85", "gray15"))
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Ready",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.status_label.pack(side="left", padx=20, pady=10)
        
        self.app_count_label = ctk.CTkLabel(
            self.status_bar,
            text="0 apps available",
            font=ctk.CTkFont(size=12),
            anchor="e"
        )
        self.app_count_label.pack(side="right", padx=20, pady=10)
    
    def _on_frame_configure(self, event=None):
        """Reset the scroll region to encompass the inner frame"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        """Resize the inner frame to match the canvas width"""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
    
    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def fetch_apps(self):
        """Fetch apps from the API endpoint"""
        self.apps.clear()
        
        # Clear existing app cards
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        
        # Show loading message
        loading_label = ctk.CTkLabel(
            self.grid_frame,
            text="Loading apps from server...",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray50")
        )
        loading_label.grid(row=0, column=0, pady=50, padx=20, columnspan=5)
        self.update()
        
        try:
            # Fetch data from API
            self.status_label.configure(text="Fetching apps from server...")
            response = requests.get(self.api_endpoint, timeout=10)
            response.raise_for_status()
            
            api_apps = response.json()
            
            # Convert API response to app data format
            for api_app in api_apps:
                app_data = self.convert_api_app(api_app)
                self.apps.append(app_data)
            
            # Sort apps by name
            self.apps.sort(key=lambda x: x['name'].lower())
            
            # Display apps
            loading_label.destroy()
            self.display_apps(self.apps)
            
            self.app_count_label.configure(text=f"{len(self.apps)} apps available")
            self.status_label.configure(text="✓ Apps loaded successfully")
            
        except requests.exceptions.ConnectionError:
            loading_label.destroy()
            self.status_label.configure(text=f"✗ Connection error: Cannot reach {self.api_base_url}")
            error_label = ctk.CTkLabel(
                self.grid_frame,
                text=f"Connection Error\n\nCannot connect to:\n{self.api_base_url}\n\nPlease check:\n• Server is running\n• Network connection\n• Firewall settings",
                font=ctk.CTkFont(size=14),
                text_color="red",
                justify="center"
            )
            error_label.grid(row=0, column=0, pady=50, padx=20, columnspan=5)
            self.app_count_label.configure(text="0 apps available")
            
        except requests.exceptions.Timeout:
            loading_label.destroy()
            self.status_label.configure(text="✗ Request timeout")
            error_label = ctk.CTkLabel(
                self.grid_frame,
                text="Request Timeout\n\nThe server took too long to respond.\nPlease try again.",
                font=ctk.CTkFont(size=14),
                text_color="red",
                justify="center"
            )
            error_label.grid(row=0, column=0, pady=50, padx=20, columnspan=5)
            self.app_count_label.configure(text="0 apps available")
            
        except requests.exceptions.RequestException as e:
            loading_label.destroy()
            self.status_label.configure(text=f"✗ Error fetching apps")
            error_label = ctk.CTkLabel(
                self.grid_frame,
                text=f"Error Loading Apps\n\n{str(e)}\n\nPlease check Settings or try again.",
                font=ctk.CTkFont(size=14),
                text_color="red",
                justify="center"
            )
            error_label.grid(row=0, column=0, pady=50, padx=20, columnspan=5)
            self.app_count_label.configure(text="0 apps available")
        
        except Exception as e:
            loading_label.destroy()
            self.status_label.configure(text=f"✗ Unexpected error")
            error_label = ctk.CTkLabel(
                self.grid_frame,
                text=f"Unexpected Error\n\n{str(e)}",
                font=ctk.CTkFont(size=14),
                text_color="red",
                justify="center"
            )
            error_label.grid(row=0, column=0, pady=50, padx=20, columnspan=5)
            self.app_count_label.configure(text="0 apps available")
    
    def convert_api_app(self, api_app):
        """Convert API app data to internal format"""
        # Parse creation date
        try:
            date_str = api_app.get('createdAt', '')
            if date_str:
                # Parse ISO format with timezone
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime("%Y-%m-%d")
            else:
                formatted_date = "Unknown"
        except:
            formatted_date = "Unknown"
        
        # Extract version from name if possible
        name = api_app.get('name', 'Unknown App')
        version = "1.0.0"
        for part in name.split():
            if part[0].isdigit() and '.' in part:
                version = part
                break
        
        # Get file size (we'll estimate or fetch during download)
        # For now, show as "Available" since API doesn't provide size
        size = "Available"
        
        app_data = {
            'id': api_app.get('id'),
            'name': name,
            'version': version,
            'description': api_app.get('description', 'No description available'),
            'size': size,
            'date': formatted_date,
            'fileName': api_app.get('fileName', ''),
            'filePath': api_app.get('filePath', ''),
            'downloadCount': api_app.get('downloadCount', 0),
            'createdBy': api_app.get('createdBy', 'Unknown'),
            'type': 'api',
            'averageRating': 0,
            'totalRatings': 0
        }
        
        # Fetch ratings for this app
        try:
            ratings_url = f"{self.api_base_url}/api/ratings/template/{api_app.get('id')}"
            ratings_response = requests.get(ratings_url, timeout=5)
            if ratings_response.status_code == 200:
                ratings_data = ratings_response.json()
                app_data['averageRating'] = ratings_data.get('averageRating', 0)
                app_data['totalRatings'] = ratings_data.get('totalRatings', 0)
        except:
            # If ratings fetch fails, keep defaults (0, 0)
            pass
        
        return app_data
    
    def get_app_metadata(self, path):
        """Extract metadata from app file/folder (legacy method for local files)"""
        name = path.stem if path.is_file() else path.name
        size = self.get_size_string(path)
        date = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
        
        # Try to extract version from name
        version = "1.0.0"
        for part in name.split():
            if part[0].isdigit() and '.' in part:
                version = part
                break
        
        # Generate description
        description = f"Daftyon application: {name}"
        
        return {
            'name': name,
            'version': version,
            'description': description,
            'size': size,
            'date': date,
            'path': path,
            'type': 'file'
        }
    
    def get_size_string(self, path):
        """Get human-readable size string"""
        if path.is_file():
            size = path.stat().st_size
        else:
            size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def display_apps(self, apps):
        """Display app cards in a grid layout"""
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        
        self.current_apps = apps
        
        if not apps:
            no_apps_label = ctk.CTkLabel(
                self.grid_frame,
                text="No apps found matching your search",
                font=ctk.CTkFont(size=14),
                text_color=("gray50", "gray50")
            )
            no_apps_label.grid(row=0, column=0, pady=50, padx=20, columnspan=5)
            return
        
        # Get number of columns from selector (default to 5 for compact cards)
        num_columns = self.columns_var.get()
        
        # Create grid of app cards
        for index, app in enumerate(apps):
            row = index // num_columns
            col = index % num_columns
            
            card = AppCard(self.grid_frame, app, self.download_app, self.show_app_details)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        
        # Configure grid columns to expand evenly
        for i in range(num_columns):
            self.grid_frame.grid_columnconfigure(i, weight=1, uniform="column")
        
        # Update canvas scroll region
        self.grid_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def filter_apps(self, *args):
        """Filter apps based on search query"""
        query = self.search_var.get().lower()
        filtered = [app for app in self.apps if query in app['name'].lower() or query in app['description'].lower()]
        self.display_apps(filtered)
    
    def download_app(self, app_data, card):
        """Download/copy app to downloads directory"""
        def download_thread():
            try:
                if card:
                    card.show_progress()
                self.status_label.configure(text=f"Downloading {app_data['name']}...")
                
                if app_data['type'] == 'api':
                    # Download from API
                    file_name = app_data['fileName']
                    dest = self.download_dir / file_name
                    
                    # Construct download URL - Format: /api/templates/{id}/download
                    download_url = f"{self.api_base_url}/api/templates/{app_data['id']}/download"
                    
                    # Download file with progress
                    response = requests.get(download_url, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    # Get total size from headers
                    total_size = int(response.headers.get('content-length', 0))
                    
                    # Download with progress updates
                    downloaded = 0
                    chunk_size = 8192  # 8KB chunks
                    
                    with open(dest, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0 and card:
                                    progress = downloaded / total_size
                                    self.after(0, card.update_progress, progress)
                    
                    if card:
                        self.after(0, card.download_complete, True)
                    self.after(0, self.status_label.configure, {
                        "text": f"✓ {app_data['name']} downloaded to {dest}"
                    })
                    self.after(0, messagebox.showinfo, "Download Complete", 
                              f"{app_data['name']} has been downloaded to:\n{dest}\n\nYou can extract and use it now!")
                    
                else:
                    # Legacy: Copy from local path
                    source = app_data['path']
                    dest = self.download_dir / source.name
                    
                    if source.is_file():
                        # Copy file with progress
                        total_size = source.stat().st_size
                        chunk_size = 1024 * 1024  # 1MB chunks
                        
                        with open(source, 'rb') as src, open(dest, 'wb') as dst:
                            copied = 0
                            while True:
                                chunk = src.read(chunk_size)
                                if not chunk:
                                    break
                                dst.write(chunk)
                                copied += len(chunk)
                                progress = copied / total_size if total_size > 0 else 1
                                if card:
                                    self.after(0, card.update_progress, progress)
                    else:
                        # Copy directory
                        if dest.exists():
                            shutil.rmtree(dest)
                        
                        def copy_with_progress(src, dst):
                            files = list(src.rglob('*'))
                            total_files = len(files)
                            
                            for i, file in enumerate(files):
                                if file.is_file():
                                    rel_path = file.relative_to(src)
                                    dest_file = dst / rel_path
                                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(file, dest_file)
                                
                                progress = (i + 1) / total_files if total_files > 0 else 1
                                if card:
                                    self.after(0, card.update_progress, progress)
                        
                        dest.mkdir(parents=True, exist_ok=True)
                        copy_with_progress(source, dest)
                    
                    if card:
                        self.after(0, card.download_complete, True)
                    self.after(0, self.status_label.configure, {
                        "text": f"✓ {app_data['name']} downloaded to {dest}"
                    })
                    self.after(0, messagebox.showinfo, "Download Complete", 
                              f"{app_data['name']} has been downloaded to:\n{dest}")
                
            except requests.exceptions.RequestException as e:
                if card:
                    self.after(0, card.download_complete, False)
                self.after(0, self.status_label.configure, {
                    "text": f"✗ Error downloading {app_data['name']}"
                })
                self.after(0, messagebox.showerror, "Download Error", 
                          f"Error downloading {app_data['name']}:\n{str(e)}\n\nPlease check your connection and try again.")
            
            except Exception as e:
                if card:
                    self.after(0, card.download_complete, False)
                self.after(0, self.status_label.configure, {
                    "text": f"✗ Error downloading {app_data['name']}"
                })
                self.after(0, messagebox.showerror, "Download Error", 
                          f"Error downloading {app_data['name']}:\n{str(e)}")
        
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
    
    def show_app_details(self, app_data):
        """Show detailed app information in a dialog"""
        details_window = ctk.CTkToplevel(self)
        details_window.title(f"{app_data['name']} - Details")
        details_window.geometry("550x600")
        details_window.transient(self)
        details_window.grab_set()
        
        # Center window
        details_window.update_idletasks()
        x = (details_window.winfo_screenwidth() // 2) - (550 // 2)
        y = (details_window.winfo_screenheight() // 2) - (600 // 2)
        details_window.geometry(f"+{x}+{y}")
        
        # Main container with scrolling
        main_frame = ctk.CTkScrollableFrame(details_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # App name
        name_label = ctk.CTkLabel(
            main_frame,
            text=app_data['name'],
            font=ctk.CTkFont(size=24, weight="bold")
        )
        name_label.pack(pady=(0, 10))
        
        # Rating with stars
        rating_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        rating_frame.pack(pady=10)
        
        avg_rating = app_data.get('averageRating', 0)
        total_ratings = app_data.get('totalRatings', 0)
        
        # Stars
        stars_text = self._get_stars_display(avg_rating)
        stars_label = ctk.CTkLabel(
            rating_frame,
            text=stars_text,
            font=ctk.CTkFont(size=24),
            text_color="orange"
        )
        stars_label.pack()
        
        rating_text_label = ctk.CTkLabel(
            rating_frame,
            text=f"{avg_rating} out of 5 stars ({total_ratings} ratings)",
            font=ctk.CTkFont(size=13),
            text_color=("gray50", "gray60")
        )
        rating_text_label.pack(pady=(5, 0))
        
        # Separator
        separator1 = ctk.CTkFrame(main_frame, height=1, fg_color=("gray80", "gray30"))
        separator1.pack(fill="x", pady=15)
        
        # Description section
        desc_title = ctk.CTkLabel(
            main_frame,
            text="Description",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        desc_title.pack(fill="x", pady=(0, 10))
        
        desc_text = ctk.CTkTextbox(
            main_frame,
            height=150,
            wrap="word",
            font=ctk.CTkFont(size=13)
        )
        desc_text.insert("1.0", app_data['description'])
        desc_text.configure(state="disabled")
        desc_text.pack(fill="x", pady=(0, 15))
        
        # Separator
        separator2 = ctk.CTkFrame(main_frame, height=1, fg_color=("gray80", "gray30"))
        separator2.pack(fill="x", pady=15)
        
        # Information section
        info_title = ctk.CTkLabel(
            main_frame,
            text="Information",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        info_title.pack(fill="x", pady=(0, 10))
        
        # Info grid
        info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        info_frame.pack(fill="x")
        
        info_items = [
            ("Version:", app_data.get('version', 'N/A')),
            ("File:", app_data.get('fileName', 'N/A')),
            ("Created:", app_data.get('date', 'N/A')),
            ("Created By:", app_data.get('createdBy', 'N/A')),
            ("Downloads:", str(app_data.get('downloadCount', 0))),
        ]
        
        for i, (label_text, value_text) in enumerate(info_items):
            # Label
            label = ctk.CTkLabel(
                info_frame,
                text=label_text,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            )
            label.grid(row=i, column=0, sticky="w", pady=5, padx=(0, 10))
            
            # Value
            value = ctk.CTkLabel(
                info_frame,
                text=value_text,
                font=ctk.CTkFont(size=12),
                anchor="w",
                text_color=("gray50", "gray60")
            )
            value.grid(row=i, column=1, sticky="w", pady=5)
        
        # Button frame
        button_frame = ctk.CTkFrame(details_window, fg_color="transparent")
        button_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        
        # Close button
        close_btn = ctk.CTkButton(
            button_frame,
            text="Close",
            width=120,
            height=40,
            command=details_window.destroy,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        close_btn.pack(side="right")
        
        # Download button
        download_btn = ctk.CTkButton(
            button_frame,
            text="Download",
            width=120,
            height=40,
            command=lambda: [self.download_app(app_data, None), details_window.destroy()],
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="green",
            hover_color="darkgreen"
        )
        download_btn.pack(side="right", padx=(0, 10))
    
    def _get_stars_display(self, rating):
        """Generate star display based on rating (0-5)"""
        full_stars = int(rating)
        half_star = 1 if (rating - full_stars) >= 0.5 else 0
        empty_stars = 5 - full_stars - half_star
        
        stars = "★" * full_stars
        if half_star:
            stars += "⯨"  # Half star
        stars += "☆" * empty_stars
        
        return stars
    
    def open_settings(self):
        """Open settings dialog"""
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("600x450")
        settings_window.transient(self)
        settings_window.grab_set()
        
        # Center window
        settings_window.update_idletasks()
        x = (settings_window.winfo_screenwidth() // 2) - (600 // 2)
        y = (settings_window.winfo_screenheight() // 2) - (450 // 2)
        settings_window.geometry(f"+{x}+{y}")
        
        # Title
        title = ctk.CTkLabel(
            settings_window,
            text="Settings",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=20)
        
        # API Base URL
        api_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        api_frame.pack(fill="x", padx=30, pady=10)
        
        api_label = ctk.CTkLabel(
            api_frame,
            text="API Base URL:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        api_label.pack(anchor="w", pady=(0, 5))
        
        api_entry = ctk.CTkEntry(
            api_frame,
            height=35,
            font=ctk.CTkFont(size=12),
            placeholder_text="http://172.20.120.78:4200"
        )
        api_entry.insert(0, self.api_base_url)
        api_entry.pack(fill="x")
        
        api_hint = ctk.CTkLabel(
            api_frame,
            text="Example: http://172.20.120.78:4200 (without /api/templates)",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray50")
        )
        api_hint.pack(anchor="w", pady=(2, 0))
        
        # Download directory
        download_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        download_frame.pack(fill="x", padx=30, pady=10)
        
        download_label = ctk.CTkLabel(
            download_frame,
            text="Download Directory:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        download_label.pack(anchor="w", pady=(0, 5))
        
        download_entry_frame = ctk.CTkFrame(download_frame, fg_color="transparent")
        download_entry_frame.pack(fill="x")
        
        download_entry = ctk.CTkEntry(
            download_entry_frame,
            height=35,
            font=ctk.CTkFont(size=12)
        )
        download_entry.insert(0, str(self.download_dir))
        download_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        def browse_download():
            directory = filedialog.askdirectory(initialdir=self.download_dir)
            if directory:
                download_entry.delete(0, "end")
                download_entry.insert(0, directory)
        
        browse_btn = ctk.CTkButton(
            download_entry_frame,
            text="Browse",
            width=100,
            height=35,
            command=browse_download
        )
        browse_btn.pack(side="right")
        
        # Appearance mode
        appearance_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        appearance_frame.pack(fill="x", padx=30, pady=10)
        
        appearance_label = ctk.CTkLabel(
            appearance_frame,
            text="Appearance Mode:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        appearance_label.pack(anchor="w", pady=(0, 5))
        
        appearance_menu = ctk.CTkOptionMenu(
            appearance_frame,
            values=["Dark", "Light", "System"],
            command=lambda mode: ctk.set_appearance_mode(mode.lower()),
            height=35,
            font=ctk.CTkFont(size=12)
        )
        appearance_menu.set(ctk.get_appearance_mode().capitalize())
        appearance_menu.pack(fill="x")
        
        # Test connection button
        test_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        test_frame.pack(fill="x", padx=30, pady=10)
        
        test_result_label = ctk.CTkLabel(
            test_frame,
            text="",
            font=ctk.CTkFont(size=11)
        )
        test_result_label.pack(anchor="w", pady=(5, 0))
        
        def test_connection():
            test_url = api_entry.get().strip()
            if not test_url:
                test_result_label.configure(text="⚠️ Please enter an API URL", text_color="orange")
                return
            
            test_endpoint = f"{test_url}/api/templates"
            test_result_label.configure(text="Testing connection...", text_color=("gray50", "gray50"))
            settings_window.update()
            
            try:
                response = requests.get(test_endpoint, timeout=5)
                response.raise_for_status()
                apps = response.json()
                test_result_label.configure(
                    text=f"✓ Connection successful! Found {len(apps)} apps.", 
                    text_color="green"
                )
            except requests.exceptions.ConnectionError:
                test_result_label.configure(
                    text="✗ Connection failed. Check URL and network.", 
                    text_color="red"
                )
            except requests.exceptions.Timeout:
                test_result_label.configure(
                    text="✗ Connection timeout. Server not responding.", 
                    text_color="red"
                )
            except Exception as e:
                test_result_label.configure(
                    text=f"✗ Error: {str(e)[:50]}...", 
                    text_color="red"
                )
        
        test_btn = ctk.CTkButton(
            test_frame,
            text="Test Connection",
            width=150,
            height=35,
            command=test_connection,
            fg_color="transparent",
            border_width=2
        )
        test_btn.pack(anchor="w")
        
        # Buttons
        button_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        button_frame.pack(side="bottom", fill="x", padx=30, pady=20)
        
        def save_settings():
            api_url = api_entry.get().strip()
            if api_url:
                # Remove trailing slash if present
                api_url = api_url.rstrip('/')
                self.api_base_url = api_url
                self.api_endpoint = f"{api_url}/api/templates"
            
            self.download_dir = Path(download_entry.get())
            self.download_dir.mkdir(parents=True, exist_ok=True)
            settings_window.destroy()
            self.fetch_apps()
        
        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            width=120,
            height=40,
            command=save_settings,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        save_btn.pack(side="right", padx=(10, 0))
        
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=120,
            height=40,
            command=settings_window.destroy,
            fg_color="transparent",
            border_width=2,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        cancel_btn.pack(side="right")


if __name__ == "__main__":
    app = DaftyonAppStore()
    app.mainloop()
