📦 PCTE Lost & Found Management System

A modern, intelligent, and feature-rich Lost & Found Management System built using Python, Tkinter/ttkbootstrap, SQLite, NLP (NLTK), and Machine Learning (TF‑IDF Similarity).

This application helps users submit lost/found items, upload images, and uses AI-powered matching to find possible matches. It also includes Admin login, Email/SMS notifications, Dark Mode, and PDF report generation.

🚀 Features
🖼️ Image Upload

Upload images of lost/found items for better identification.

🧠 NLP Description Matching

Uses NLTK + TF-IDF + Cosine Similarity to match descriptions smartly.

🎨 Modern UI (ttkbootstrap)

Beautiful UI with optional themes.

🌙 Dark Mode

Toggle dark/light themes via settings.

📩 Email Notifications (SMTP)

Send email alerts when a match is found.

📱 SMS Notifications (Twilio)

Optional Twilio integration to send SMS alerts.

🔍 Search Bar

Quickly filter and find items.

🔐 Admin Login System

Hashed admin credentials stored inside the database. Default:
username: admin
password: admin123

📄 PDF Report Generator

Generate a PDF summary of an item and its matches.

🗂️ Project Structure
📁 project-folder
├── lost.py
├── requirements.txt
├── README.md
├── items.db # Auto-created
├── images/ # Auto-created
└── settings.json # Auto-created

🛠️ Installation
1️⃣ Install Python 3.8+

Download from: https://www.python.org/downloads/

2️⃣ Install Dependencies
pip install -r requirements.txt

3️⃣ Run the App
python lost.py

🔧 Configuration
⚙️ SMTP (Email)

Go to Settings → SMTP and configure:

Host (example: smtp.gmail.com)

Port (587)

Username

Password

From Email

Gmail users must use an App Password.

⚙️ Twilio SMS (Optional)

Go to Settings → Twilio and enter:

Account SID

Auth Token

Twilio Phone Number

🧪 NLP Matching Logic

Descriptions are processed using:

Tokenization

Stopword removal

Stemming

TF‑IDF vectorization

Cosine similarity

Matches are shown with a similarity score (0–1).

🛡️ Admin System

Admin credentials stored hashed (SHA‑256)

Default admin auto-created on first run

Used for restricted features (future expansion possible)

📄 Generate PDF Report

App allows exporting:

Item details

Possible matches

Description

Similarity scores

Saved with ReportLab.

📦 Build EXE (Windows)

You can convert this app into a standalone EXE:
pyinstaller --onefile --windowed lost.py

After build, find your EXE in:
dist/lost.exe

❤️ Credits

Developed by: AashishCyberH4CKS

⚖️ License

This project is free to use and modify for personal or educational purposes.

⭐ If you use this in GitHub, consider giving the repo a star!