# 🚀 **PCTE Lost & Found Management System**

A modern, feature-rich, AI-powered **Lost & Found Management System** built using **Python**, **Tkinter/ttkbootstrap**, **SQLite**, **NLTK**, **ML (TF-IDF Similarity)**, and more.

This project is ideal for **college submissions, GitHub portfolios, academic demos, and real-world deployment**.

---

## ✨ **Key Features**

### 🖼️ **Image Upload System**

<img width="1142" height="695" alt="image 2" src="https://github.com/user-attachments/assets/fd3581bc-bc76-4170-929a-27b94cd086da" />


### 🧠 **AI-Powered NLP Matching**

Uses **NLTK** + **TF-IDF** + **Cosine Similarity** to match items smartly.

### 🎨 **Modern UI (ttkbootstrap)**

A sleek, professional interface with smooth styling.

### 🌙 **Dark Mode Support**

Toggle dark/light themes in the settings panel.

### 📩 **Email Notifications (SMTP)**

Automatically send match alerts directly to user email.

### 📱 **SMS Notifications (Twilio)**

Optional—send SMS alerts using Twilio API.

### 🔍 **Search System**

Instantly search items by name, description, or place.

### 🔐 **Admin Login System**

Secure admin access with **hashed credentials**.
Default credentials:

```
username: admin
password: admin123
```

### 📄 **PDF Report Generator (ReportLab)**

Generate a professional PDF summary of an item + potential matches.

---

## 📂 **Project Structure**

```bash
📁 your-project-folder/
│── lost.py
│── requirements.txt
│── README.md
│── items.db          # Auto-generated
│── settings.json     # Auto-generated
└── 📁 images/        # Auto-created for uploaded files
```

---

## 🛠️ **Installation Guide**

### **1️⃣ Install Python 3.8+**

Download from: [https://www.python.org/downloads/](https://www.python.org/downloads/)

---

### **2️⃣ Install Required Packages**

```bash
pip install -r requirements.txt
```

---

### **3️⃣ Run the Application**

```bash
python lost.py
```

---

## ⚙️ **Configuration**

### **📧 SMTP Email Setup**

Go to: **Settings → SMTP** and enter:

* SMTP Host (e.g., smtp.gmail.com)
* Port: 587
* Username
* Password
* From Email

> ⚠️ **Gmail Users:** Must use an **App Password**.

---

### **📱 Twilio SMS Setup (Optional)**

Go to: **Settings → Twilio**

* Account SID
* Auth Token
* Phone Number (Twilio verified)

---

## 🧠 **How NLP Matching Works**

The system processes text using:

* Tokenization
* Stopword removal
* Stemming
* TF-IDF Vectorization
* Cosine similarity

Matches are displayed with a **similarity score (0–1)**.

---

## 🔐 **Admin System**

* Admin passwords stored using **SHA-256 hashing**.
* Only admins can view/manage certain features.
* Default admin is auto-created.

---

## 📄 **PDF Report Generation**

Automatically export:

* Item details
* Description
* Submission info
* All matched items + similarity scores

Useful for: **records, printing, verification**, etc.

---

## 🖥️ **Build Windows EXE (Standalone)**

You can package the project into an EXE:

```bash
pyinstaller --onefile --windowed lost.py
```

Output file will appear in:

```
dist/lost.exe
```

---


---

## ❤️ **Credits**

* Developed by **AashishCyberH4CKS**

---

## 📜 **License**

This project is free for personal, academic, and educational use.

> ⭐ If this project helped you, consider giving it a **star on GitHub**!
