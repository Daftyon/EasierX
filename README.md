#  BatcherMan Desktop

> **The ultimate desktop tool for Spring Batch developers**

BatcherMan transforms Spring Batch development by providing an interactive testing environment where you can test and debug batch components without the overhead of deploying complete jobs.

## 🎯 What Problem Does It Solve?

Traditional Spring Batch development requires:
- ❌ Running complete jobs to test a single reader
- ❌ Deploying to server to debug processors
- ❌ Processing thousands of records to validate writer logic
- ❌ Long feedback loops for simple component changes

**BatcherMan changes this:**
- ✅ Test readers with configurable item limits (test with 10 items, not 10,000)
- ✅ Debug processors with JSON input/output comparison
- ✅ Validate writers in sandbox mode without affecting production
- ✅ Instant feedback - no deployment needed

## 🚀 Features

### Component Testing
- **📖 Reader Tester**: Execute readers in isolation, preview data in table format
- **⚙️ Processor Tester**: Test transformations with before/after comparison
- **✍️ Writer Tester**: Validate output without full job execution
- **🔄 Step Runner**: Execute complete steps with visual flow (Reader → Processor → Writer)
- **🚀 Job Runner**: Run multi-step jobs with progress tracking

### Analysis & Visualization
- **Automatic Component Detection**: Analyzes JARs to find all batch components
- **XML + Java Support**: Detects components from both XML config and Java annotations
- **Pipeline Visualization**: Visual diagrams showing component relationships
- **Flow Diagrams**: Interactive step and job flow visualizations

### Developer Experience
- **No Configuration**: Point to your JAR and go
- **Real-time Logs**: See execution logs as components run
- **Debug Mode**: Deep inspection of JAR contents and XML parsing
- **Cross-platform**: Works on Windows, macOS, and Linux

## 🛠️ Technology Stack

- **UI**: Tkinter (Python) - lightweight, no dependencies
- **JVM Integration**: JPype - direct Java class execution
- **Analysis**: Bytecode inspection + XML parsing
- **Supported**: Spring Batch 4.x/5.x, Java 8+

## 📦 Installation
```bash
git clone https://github.com/yourusername/batcherman-desktop.git
cd batcherman-desktop
pip install -r requirements.txt
python main_tkinter.py
```

## 🎬 Quick Start

1. Launch BatcherMan
2. Click **Browse** and select your Spring Batch JAR
3. Click **Analyze** to discover all components
4. Switch to any tab (Reader/Processor/Writer/Step/Job)
5. Select a component and click **Run/Test**

## 📸 Screenshots

[Add screenshots here]

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md for details.

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Built for Spring Batch developers who need faster feedback loops and better debugging tools.

---

**Made with ❤️ by Synthos**
```

---

## ✅ **GitHub Topics (Tags)**

Add these topics to your GitHub repo:
```
spring-batch
java
python
batch-processing
testing-tools
debugging
desktop-application
tkinter
spring-framework
developer-tools
```

---

## ✅ **One-Liner for Social Media**
```
Just released BatcherMan 🚀 - a desktop app for testing Spring Batch components in isolation. 
No more running full jobs to debug a single reader! #SpringBatch #Java #DevTools
