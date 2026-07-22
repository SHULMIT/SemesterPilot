# SemesterPilot

A local-first academic planner for Open University students.

SemesterPilot helps students organize their academic life by importing their university calendar, synchronizing assignments and academic events, tracking progress, and planning their semester — all while keeping their data private on their own computer.

---

## ✨ Features

* 📅 Import Open University `.ics` calendars
* 🔄 Smart calendar synchronization
* 🚫 Duplicate detection
* 📝 Assignment management
* ✅ Personal progress tracking
* 📋 Subtask management
* 🔍 Search, filter, and sorting
* 📊 Dashboard with academic overview
* 💾 Local SQLite database
* 🔒 Privacy-first (all data stays on your computer)
* 🌐 RTL support
* 🏗️ Clean Architecture

---

## 🛠️ Tech Stack

* Python
* SQLite
* HTML / CSS / JavaScript
* Clean Architecture
* Dependency Injection
* Pytest
* Ruff
* Mypy

---

## 📸 Screenshots

> Screenshots will be added as the project evolves.

---

## 🚀 Running the project

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/SemesterPilot.git
cd SemesterPilot
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python prototype.py
```

Then open:

```
http://127.0.0.1:5050
```

---

## 🏛️ Architecture

SemesterPilot follows a layered Clean Architecture:

```
UI
│
▼
Application
│
▼
Domain
│
▼
Infrastructure
```

Business rules remain independent from the user interface and persistence layer.

---

## 🔒 Privacy

SemesterPilot is designed as a **local-first** application.

* No cloud storage
* No user accounts
* No telemetry
* No personal data leaves your computer

Every user imports their own calendar locally.

---

## 📅 Roadmap

### ✅ Completed

* Clean Architecture foundation
* SQLite persistence
* Calendar (.ics) parser
* Smart synchronization engine
* Dashboard
* Assignment management
* Subtask management
* RTL UI foundation

### 🚧 In Progress

* Weekly Planner

### 📌 Planned

* Calendar view
* Notifications
* Settings
* Packaging and installer

---

## 🧪 Quality

The project uses:

* Pytest
* Ruff
* Mypy

to maintain code quality and reliability.

---

## 📄 License

This project is licensed under the MIT License.
