import os

# Base project folder
base = "BatcherMan"

# Folder structure
folders = [
    "config",
    "ui/widgets",
    "core",
    "models",
    "utils",
    "resources/icons",
    "build"
]

# Files to create
files = [
    "main.py",
    "requirements.txt",
    "config/settings.py",
    "ui/__init__.py",
    "ui/main_window.py",
    "ui/reader_tester.py",
    "ui/processor_tester.py",
    "ui/writer_tester.py",
    "ui/step_runner.py",
    "ui/job_runner.py",
    "ui/pipeline_visualizer.py",
    "ui/widgets/data_table.py",
    "ui/widgets/log_viewer.py",
    "ui/widgets/diff_viewer.py",
    "core/__init__.py",
    "core/jvm_manager.py",
    "core/class_loader.py",
    "core/batch_analyzer.py",
    "core/reader_sandbox.py",
    "core/processor_sandbox.py",
    "core/writer_sandbox.py",
    "core/step_sandbox.py",
    "core/job_sandbox.py",
    "models/__init__.py",
    "models/batch_component.py",
    "models/execution_result.py",
    "models/pipeline_graph.py",
    "utils/__init__.py",
    "utils/jar_scanner.py",
    "utils/logger.py",
    "resources/styles.qss",
    "build/build.spec",
    "build/build.py"
]

# Create folders
for folder in folders:
    path = os.path.join(base, folder)
    os.makedirs(path, exist_ok=True)

# Create files
for file in files:
    path = os.path.join(base, file)
    # Ensure parent directories exist
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Create empty file if it doesn't exist
    if not os.path.exists(path):
        open(path, 'w').close()

print(f"Project '{base}' structure created successfully!")
