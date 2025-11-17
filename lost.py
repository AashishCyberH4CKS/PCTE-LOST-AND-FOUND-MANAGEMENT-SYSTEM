"""
PCTE Lost & Found Management System - Final Python Code
Single-file Python app using Tkinter/ttkbootstrap (optional), SQLite, NLTK, scikit-learn, Pillow.
Enhanced features:
- Modern UI using ttkbootstrap (falls back to ttk)
- Dark Mode toggle (via settings)
- Email notifications via SMTP
- SMS notifications via Twilio (optional)
- Search bar
- Admin login system (default admin/admin123)
- PDF report generator (reportlab; optional)

Install required packages (recommended):
pip install nltk scikit-learn pillow reportlab ttkbootstrap twilio

Run:
python PCTE_Lost_and_Found_System.py
"""

import os
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import shutil
import uuid
import datetime
import hashlib
import json

from PIL import Image, ImageTk

# NLP
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Optional: reportlab for PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# Optional modern UI
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    UI_BOOTSTRAP = True
except Exception:
    UI_BOOTSTRAP = False

# Optional Twilio
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except Exception:
    TWILIO_AVAILABLE = False

# Ensure NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

STOPWORDS = set(stopwords.words('english'))
STEMMER = PorterStemmer()

# Paths & constants
DB_PATH = 'items.db'
IMAGES_DIR = 'images'
SETTINGS_FILE = 'settings.json'
os.makedirs(IMAGES_DIR, exist_ok=True)


class DB:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self._create()

    def _create(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                type TEXT,
                name TEXT,
                description TEXT,
                place TEXT,
                date TEXT,
                contact TEXT,
                image_path TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT
            )
        ''')
        self.conn.commit()
        cur.execute('SELECT COUNT(*) FROM admin')
        if cur.fetchone()[0] == 0:
            self.add_admin('admin', 'admin123')

    def add_admin(self, username, password):
        cur = self.conn.cursor()
        ph = self.hash_password(password)
        try:
            cur.execute('INSERT INTO admin (username, password_hash) VALUES (?,?)', (username, ph))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def verify_admin(self, username, password):
        cur = self.conn.cursor()
        cur.execute('SELECT password_hash FROM admin WHERE username=?', (username,))
        row = cur.fetchone()
        if not row:
            return False
        return self.verify_hash(password, row[0])

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_hash(self, password, hashval):
        return hashlib.sha256(password.encode()).hexdigest() == hashval

    def add_item(self, item):
        cur = self.conn.cursor()
        cur.execute('''INSERT INTO items (id,type,name,description,place,date,contact,image_path) VALUES (?,?,?,?,?,?,?,?)''', (
            item['id'], item['type'], item['name'], item['description'], item['place'], item['date'], item['contact'], item['image_path']
        ))
        self.conn.commit()

    def get_items(self, type=None, search=None):
        cur = self.conn.cursor()
        if type and search:
            cur.execute('SELECT * FROM items WHERE type=? AND (name LIKE ? OR description LIKE ? OR place LIKE ?)', (type, f'%{search}%', f'%{search}%', f'%{search}%'))
        elif type:
            cur.execute('SELECT * FROM items WHERE type=?', (type,))
        elif search:
            cur.execute('SELECT * FROM items WHERE name LIKE ? OR description LIKE ? OR place LIKE ?', (f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            cur.execute('SELECT * FROM items')
        rows = cur.fetchall()
        cols = ['id','type','name','description','place','date','contact','image_path']
        return [dict(zip(cols,row)) for row in rows]

    def close(self):
        self.conn.close()


def preprocess(text):
    if not text:
        return ''
    text = text.lower()
    tokens = word_tokenize(text)
    tokens = [t for t in tokens if t.isalpha() and t not in STOPWORDS]
    tokens = [STEMMER.stem(t) for t in tokens]
    return ' '.join(tokens)


class Matcher:
    def __init__(self, db: DB):
        self.db = db
        self.vectorizer = None
        self.corpus_ids = []
        self.corpus_texts = []

    def build(self, opposite_type):
        items = self.db.get_items(type=opposite_type)
        self.corpus_ids = [it['id'] for it in items]
        self.corpus_texts = [preprocess((it['name'] or '') + ' ' + (it['description'] or '') + ' ' + (it['place'] or '')) for it in items]
        if len(self.corpus_texts) == 0:
            self.vectorizer = None
            return
        self.vectorizer = TfidfVectorizer().fit(self.corpus_texts)

    def find_matches(self, item, topk=5):
        opposite = 'found' if item['type']=='lost' else 'lost'
        self.build(opposite)
        if not self.vectorizer:
            return []
        query = preprocess((item.get('name') or '') + ' ' + (item.get('description') or '') + ' ' + (item.get('place') or ''))
        qv = self.vectorizer.transform([query])
        corpus_v = self.vectorizer.transform(self.corpus_texts)
        sims = cosine_similarity(qv, corpus_v)[0]
        ranked = sorted(list(zip(self.corpus_ids, sims)), key=lambda x: x[1], reverse=True)
        results = []
        all_opposite = self.db.get_items(type=opposite)
        for cid,score in ranked[:topk]:
            rows = [it for it in all_opposite if it['id']==cid]
            if rows:
                it = rows[0]
                it['_score'] = float(score)
                results.append(it)
        return results


class Settings:
    def __init__(self, path=SETTINGS_FILE):
        self.path = path
        self.data = {
            'smtp':{
                'enabled': False,
                'host':'', 'port':587, 'username':'', 'password':'', 'from_email':''
            },
            'twilio':{
                'enabled': False,
                'account_sid':'', 'auth_token':'', 'from_number':''
            },
            'ui':{
                'theme':'cosmo', 'dark':False
            }
        }
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path,'r') as f:
                    loaded = json.load(f)
                    # merge safely
                    for k,v in loaded.items():
                        if isinstance(v, dict) and k in self.data:
                            self.data[k].update(v)
                        else:
                            self.data[k] = v
            except Exception:
                pass

    def save(self):
        with open(self.path,'w') as f:
            json.dump(self.data, f, indent=2)


import smtplib
from email.mime.text import MIMEText

class Notifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.twilio_client = None
        if TWILIO_AVAILABLE and self.settings.data['twilio'].get('enabled'):
            try:
                self.twilio_client = TwilioClient(self.settings.data['twilio']['account_sid'], self.settings.data['twilio']['auth_token'])
            except Exception:
                self.twilio_client = None

    def send_email(self, to_email, subject, body):
        s = self.settings.data['smtp']
        if not s.get('enabled'):
            return False, 'SMTP disabled'
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = s.get('from_email') or s.get('username')
            msg['To'] = to_email
            with smtplib.SMTP(s['host'], s.get('port',587)) as server:
                server.starttls()
                server.login(s['username'], s['password'])
                server.sendmail(msg['From'], [to_email], msg.as_string())
            return True, 'Email sent'
        except Exception as e:
            return False, str(e)

    def send_sms(self, to_number, body):
        if not TWILIO_AVAILABLE or not self.settings.data['twilio'].get('enabled') or not self.twilio_client:
            return False, 'Twilio not configured'
        try:
            msg = self.twilio_client.messages.create(body=body, from_=self.settings.data['twilio']['from_number'], to=to_number)
            return True, msg.sid
        except Exception as e:
            return False, str(e)


def generate_pdf_report(item, matches, filename):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError('reportlab not available')
    c = canvas.Canvas(filename, pagesize=A4)
    w, h = A4
    y = h - 40
    c.setFont('Helvetica-Bold', 14)
    c.drawString(40, y, f"PCTE Lost & Found - Report for {item['type'].title()} - {item['name']}")
    y -= 30
    c.setFont('Helvetica', 11)
    c.drawString(40, y, f"Submitted: {item.get('date','')} | Place: {item.get('place','')} | Contact: {item.get('contact','')}")
    y -= 30
    c.drawString(40, y, 'Description:')
    y -= 20
    text = c.beginText(45, y)
    text.setFont('Helvetica', 10)
    for line in (item.get('description') or '').split('\n'):
        text.textLine(line)
        y -= 14
    c.drawText(text)
    y -= 20
    c.setFont('Helvetica-Bold', 12)
    c.drawString(40, y, 'Matches:')
    y -= 20
    c.setFont('Helvetica', 10)
    for m in matches:
        if y < 80:
            c.showPage()
            y = h - 40
        c.drawString(45, y, f"- {m['type'].title()} | {m['name']} | Score: {m.get('_score',0):.2f} | Place: {m.get('place','')} | Contact: {m.get('contact','')}")
        y -= 16
    c.save()


class AppBase:
    def __init__(self):
        self.db = DB()
        self.matcher = Matcher(self.db)
        self.settings = Settings()
        self.notifier = Notifier(self.settings)
        self.selected_image_path = None

    def common_clear_form(self):
        try:
            self.name_entry.delete(0,'end')
            self.desc_text.delete('1.0','end')
            self.place_entry.delete(0,'end')
            self.contact_entry.delete(0,'end')
            self.selected_image_path = None
            if hasattr(self,'img_label'):
                self.img_label.config(image='')
        except Exception:
            pass


# UI classes
if UI_BOOTSTRAP:
    class App(tb.Window, AppBase):
        def __init__(self):
            # Initialize AppBase first so settings are available for theme selection
            AppBase.__init__(self)
            theme = self.settings.data.get('ui',{}).get('theme','cosmo')
            tb.Window.__init__(self, title='PCTE Lost & Found Management System', themename=theme)
            self.geometry('1100x720')
            self.create_widgets()

        def create_widgets(self):
            nb = ttk.Notebook(self)
            nb.pack(fill='both', expand=True)
            self.form_frame = ttk.Frame(nb)
            self.dashboard_frame = ttk.Frame(nb)
            nb.add(self.form_frame, text='Submit Item')
            nb.add(self.dashboard_frame, text='Match Dashboard')

            left = ttk.Frame(self.form_frame, padding=12)
            left.pack(side='left', fill='y')
            ttk.Label(left, text='Type:').pack(anchor='w')
            self.type_var = tk.StringVar(value='lost')
            ttk.Radiobutton(left, text='Lost', variable=self.type_var, value='lost').pack(anchor='w')
            ttk.Radiobutton(left, text='Found', variable=self.type_var, value='found').pack(anchor='w')
            ttk.Label(left, text='Name:').pack(anchor='w', pady=(10,0))
            self.name_entry = ttk.Entry(left, width=30)
            self.name_entry.pack(anchor='w')
            ttk.Label(left, text='Description:').pack(anchor='w', pady=(10,0))
            self.desc_text = tk.Text(left, width=40, height=6)
            self.desc_text.pack(anchor='w')
            ttk.Label(left, text='Place:').pack(anchor='w', pady=(10,0))
            self.place_entry = ttk.Entry(left, width=30)
            self.place_entry.pack(anchor='w')
            ttk.Label(left, text='Contact Info:').pack(anchor='w', pady=(10,0))
            self.contact_entry = ttk.Entry(left, width=30)
            self.contact_entry.pack(anchor='w')
            ttk.Button(left, text='Upload Image', command=self.upload_image).pack(pady=(10,0))
            self.img_label = ttk.Label(left)
            self.img_label.pack(pady=(5,0))
            ttk.Button(left, text='Submit Item', command=self.submit_item).pack(pady=(15,0))
            ttk.Button(left, text='Settings / Notifications', command=self.open_settings).pack(pady=(6,0))

            right = ttk.Frame(self.form_frame, padding=10)
            right.pack(side='left', fill='both', expand=True)
            top_search = ttk.Frame(right)
            top_search.pack(fill='x')
            ttk.Label(top_search, text='Search:').pack(side='left')
            self.search_var = tk.StringVar()
            self.search_var.trace_add('write', lambda *args: self.refresh_list())
            ttk.Entry(top_search, textvariable=self.search_var, width=40).pack(side='left', padx=6)
            ttk.Button(top_search, text='Admin Login', command=self.admin_login).pack(side='right')

            self.tree = ttk.Treeview(right, columns=('type','name','place','date','contact'), show='headings')
            for c in ('type','name','place','date','contact'):
                self.tree.heading(c, text=c.title())
                self.tree.column(c, width=120)
            self.tree.pack(fill='both', expand=True)
            ttk.Button(right, text='Refresh List', command=self.refresh_list).pack(pady=(5,0))

            self.build_dashboard()
            self.refresh_list()

        def admin_login(self):
            LoginDialog(self, self.db)

        def upload_image(self):
            path = filedialog.askopenfilename(filetypes=[('Image Files', '*.png *.jpg *.jpeg *.bmp')])
            if not path:
                return
            ext = os.path.splitext(path)[1]
            newname = str(uuid.uuid4()) + ext
            newpath = os.path.join(IMAGES_DIR, newname)
            shutil.copy(path, newpath)
            self.selected_image_path = newpath
            self.show_thumbnail(newpath)

        def show_thumbnail(self, path, widget=None, size=(150,150)):
            try:
                img = Image.open(path)
                img.thumbnail(size)
                imgtk = ImageTk.PhotoImage(img)
                if widget is None:
                    self.img_label.img = imgtk
                    self.img_label.config(image=imgtk)
                else:
                    widget.img = imgtk
                    widget.config(image=imgtk)
            except Exception as e:
                print('Thumb error', e)

        def submit_item(self):
            itype = self.type_var.get()
            name = self.name_entry.get().strip()
            desc = self.desc_text.get('1.0','end').strip()
            place = self.place_entry.get().strip()
            contact = self.contact_entry.get().strip()
            date = datetime.date.today().isoformat()
            img = self.selected_image_path
            if not name and not desc:
                messagebox.showwarning('Missing', 'Please add at least a name or description')
                return
            item = {
                'id': str(uuid.uuid4()),
                'type': itype,
                'name': name,
                'description': desc,
                'place': place,
                'date': date,
                'contact': contact,
                'image_path': img
            }
            self.db.add_item(item)
            messagebox.showinfo('Saved', 'Item saved to database')
            matches = self.matcher.find_matches(item, topk=5)
            if matches:
                self.show_matches_popup(item, matches)
            self.common_clear_form()
            self.refresh_list()

        def refresh_list(self):
            for r in self.tree.get_children():
                self.tree.delete(r)
            search = self.search_var.get().strip()
            for it in self.db.get_items(search=search):
                self.tree.insert('', 'end', values=(it['type'], it['name'][:30], it['place'][:20], it['date'], it['contact'][:20]))

        def build_dashboard(self):
            frm = self.dashboard_frame
            top = ttk.Frame(frm, padding=10)
            top.pack(fill='x')
            ttk.Label(top, text='View matches for:').pack(side='left')
            self.view_type = tk.StringVar(value='lost')
            ttk.Radiobutton(top, text='Lost', variable=self.view_type, value='lost').pack(side='left')
            ttk.Radiobutton(top, text='Found', variable=self.view_type, value='found').pack(side='left')
            ttk.Button(top, text='Refresh Matches', command=self.populate_matches).pack(side='left', padx=10)
            ttk.Button(top, text='Generate PDF for Selected', command=self.generate_pdf_for_selected).pack(side='right')

            self.matches_canvas = tk.Canvas(frm)
            self.matches_canvas.pack(side='left', fill='both', expand=True)
            self.match_frame = ttk.Frame(self.matches_canvas)
            self.vsb = ttk.Scrollbar(frm, orient='vertical', command=self.matches_canvas.yview)
            self.vsb.pack(side='right', fill='y')
            self.matches_canvas.configure(yscrollcommand=self.vsb.set)
            self.matches_canvas.create_window((0,0), window=self.match_frame, anchor='nw')
            self.match_frame.bind('<Configure>', lambda e: self.matches_canvas.configure(scrollregion=self.matches_canvas.bbox('all')))

        def populate_matches(self):
            for w in self.match_frame.winfo_children():
                w.destroy()
            vtype = self.view_type.get()
            items = self.db.get_items(type=vtype)
            for it in items:
                container = ttk.Frame(self.match_frame, borderwidth=1, relief='solid', padding=6)
                container.pack(fill='x', pady=4, padx=4)
                top = ttk.Frame(container)
                top.pack(fill='x')
                ttk.Label(top, text=f"{it['type'].upper()} - {it['name']}", font=('TkDefaultFont', 12, 'bold')).pack(side='left')
                ttk.Label(top, text=f"{it['date']} @ {it['place']}").pack(side='right')
                mid = ttk.Frame(container)
                mid.pack(fill='x', pady=4)
                img_lbl = ttk.Label(mid)
                img_lbl.pack(side='left')
                if it['image_path']:
                    self.show_thumbnail(it['image_path'], widget=img_lbl, size=(120,120))
                text = ttk.Label(mid, text=(it['description'] or '(No description)')[:200], wraplength=600)
                text.pack(side='left', padx=10)
                matches = self.matcher.find_matches(it, topk=3)
                if matches:
                    ttk.Separator(container, orient='horizontal').pack(fill='x', pady=4)
                    ttk.Label(container, text='Possible matches:', foreground='blue').pack(anchor='w')
                    for m in matches:
                        row = ttk.Frame(container)
                        row.pack(fill='x', pady=2)
                        mimg = ttk.Label(row)
                        mimg.pack(side='left')
                        if m['image_path']:
                            self.show_thumbnail(m['image_path'], widget=mimg, size=(80,80))
                        lbl = ttk.Label(row, text=f"{m['type'].title()} - {m['name']} | Score: {m['_score']:.2f} | Place: {m['place']} | Contact: {m['contact']}", wraplength=700)
                        lbl.pack(side='left', padx=6)
                else:
                    ttk.Label(container, text='No matches found yet').pack()

        def show_matches_popup(self, item, matches):
            win = tk.Toplevel(self)
            win.title('Possible Matches')
            ttk.Label(win, text=f"Submitted: {item['type'].title()} - {item['name']}").pack(pady=4)
            for m in matches:
                frm = ttk.Frame(win, padding=6, borderwidth=1, relief='ridge')
                frm.pack(fill='x', padx=6, pady=4)
                lbl = ttk.Label(frm, text=f"{m['type'].title()} - {m['name']} | Score: {m['_score']:.2f}")
                lbl.pack(side='left')
                if m['image_path']:
                    mimg = ttk.Label(frm)
                    mimg.pack(side='right')
                    self.show_thumbnail(m['image_path'], widget=mimg, size=(80,80))
                btn_frame = ttk.Frame(frm)
                btn_frame.pack(side='right')
                ttk.Button(btn_frame, text='Email', command=lambda mm=m: self.notify_by_email(mm)).pack(side='left', padx=2)
                ttk.Button(btn_frame, text='SMS', command=lambda mm=m: self.notify_by_sms(mm)).pack(side='left', padx=2)

        def notify_by_email(self, match):
            to_email = match.get('contact')
            if not to_email:
                messagebox.showwarning('No contact', 'No contact email available for this match')
                return
            subject = 'Possible match for your lost/found item'
            body = f"We found a possible match: {match['name']} at {match['place']} | Contact: {match['contact']}"
            ok, msg = self.notifier.send_email(to_email, subject, body)
            messagebox.showinfo('Email', msg)

        def notify_by_sms(self, match):
            to_number = match.get('contact')
            if not to_number:
                messagebox.showwarning('No contact', 'No contact number available for this match')
                return
            ok, msg = self.notifier.send_sms(to_number, f"Possible match: {match['name']} at {match['place']}")
            messagebox.showinfo('SMS', msg)

        def generate_pdf_for_selected(self):
            vtype = self.view_type.get()
            items = self.db.get_items(type=vtype)
            if not items:
                messagebox.showwarning('No items', 'No items to generate report for')
                return
            item = items[0]
            matches = self.matcher.find_matches(item, topk=5)
            if not REPORTLAB_AVAILABLE:
                messagebox.showerror('Missing', 'reportlab not installed. Install with pip install reportlab')
                return
            fname = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF Files','*.pdf')])
            if not fname:
                return
            try:
                generate_pdf_report(item, matches, fname)
                messagebox.showinfo('Saved', f'PDF saved: {fname}')
            except Exception as e:
                messagebox.showerror('Error', str(e))

        def open_settings(self):
            SettingsDialog(self, self.settings)


    class LoginDialog(tk.Toplevel):
        def __init__(self, parent, db: DB):
            super().__init__(parent)
            self.db = db
            self.title('Admin Login')
            self.geometry('300x150')
            ttk.Label(self, text='Username').pack(pady=(10,0))
            self.user = ttk.Entry(self)
            self.user.pack()
            ttk.Label(self, text='Password').pack(pady=(6,0))
            self.pwd = ttk.Entry(self, show='*')
            self.pwd.pack()
            ttk.Button(self, text='Login', command=self.try_login).pack(pady=10)

        def try_login(self):
            u = self.user.get().strip()
            p = self.pwd.get().strip()
            if self.db.verify_admin(u,p):
                messagebox.showinfo('OK','Admin login successful')
                self.destroy()
            else:
                messagebox.showerror('Fail','Invalid credentials')


    class SettingsDialog(tk.Toplevel):
        def __init__(self, parent, settings: Settings):
            super().__init__(parent)
            self.settings = settings
            self.title('Settings & Notifications')
            self.geometry('620x420')
            nb = ttk.Notebook(self)
            nb.pack(fill='both', expand=True)
            smtpf = ttk.Frame(nb, padding=8)
            nb.add(smtpf, text='SMTP')
            s = self.settings.data['smtp']
            self.smtp_enabled = tk.BooleanVar(value=s.get('enabled',False))
            ttk.Checkbutton(smtpf, text='Enable SMTP', variable=self.smtp_enabled).pack(anchor='w')
            ttk.Label(smtpf, text='Host:').pack(anchor='w')
            self.smtp_host = ttk.Entry(smtpf)
            self.smtp_host.insert(0,s.get('host',''))
            self.smtp_host.pack(fill='x')
            ttk.Label(smtpf, text='Port:').pack(anchor='w')
            self.smtp_port = ttk.Entry(smtpf)
            self.smtp_port.insert(0,str(s.get('port',587)))
            self.smtp_port.pack(fill='x')
            ttk.Label(smtpf, text='Username:').pack(anchor='w')
            self.smtp_user = ttk.Entry(smtpf)
            self.smtp_user.insert(0,s.get('username',''))
            self.smtp_user.pack(fill='x')
            ttk.Label(smtpf, text='Password:').pack(anchor='w')
            self.smtp_pass = ttk.Entry(smtpf)
            self.smtp_pass.insert(0,s.get('password',''))
            self.smtp_pass.pack(fill='x')
            ttk.Label(smtpf, text='From Email:').pack(anchor='w')
            self.smtp_from = ttk.Entry(smtpf)
            self.smtp_from.insert(0,s.get('from_email',''))
            self.smtp_from.pack(fill='x')

            twf = ttk.Frame(nb, padding=8)
            nb.add(twf, text='Twilio')
            t = self.settings.data['twilio']
            self.tw_enabled = tk.BooleanVar(value=t.get('enabled',False))
            ttk.Checkbutton(twf, text='Enable Twilio', variable=self.tw_enabled).pack(anchor='w')
            ttk.Label(twf, text='Account SID:').pack(anchor='w')
            self.tw_sid = ttk.Entry(twf)
            self.tw_sid.insert(0,t.get('account_sid',''))
            self.tw_sid.pack(fill='x')
            ttk.Label(twf, text='Auth Token:').pack(anchor='w')
            self.tw_auth = ttk.Entry(twf)
            self.tw_auth.insert(0,t.get('auth_token',''))
            self.tw_auth.pack(fill='x')
            ttk.Label(twf, text='From Number:').pack(anchor='w')
            self.tw_from = ttk.Entry(twf)
            self.tw_from.insert(0,t.get('from_number',''))
            self.tw_from.pack(fill='x')

            uif = ttk.Frame(nb, padding=8)
            nb.add(uif, text='UI')
            ui = self.settings.data.get('ui',{})
            ttk.Label(uif, text='Theme name (ttkbootstrap theme)').pack(anchor='w')
            self.ui_theme = ttk.Entry(uif)
            self.ui_theme.insert(0, ui.get('theme','cosmo'))
            self.ui_theme.pack(fill='x')
            self.dark_var = tk.BooleanVar(value=ui.get('dark',False))
            ttk.Checkbutton(uif, text='Dark mode', variable=self.dark_var).pack(anchor='w')
            ttk.Button(self, text='Save Settings', command=self.save).pack(pady=8)

        def save(self):
            self.settings.data['smtp']['enabled'] = bool(self.smtp_enabled.get())
            self.settings.data['smtp']['host'] = self.smtp_host.get().strip()
            try:
                self.settings.data['smtp']['port'] = int(self.smtp_port.get().strip())
            except Exception:
                self.settings.data['smtp']['port'] = 587
            self.settings.data['smtp']['username'] = self.smtp_user.get().strip()
            self.settings.data['smtp']['password'] = self.smtp_pass.get().strip()
            self.settings.data['smtp']['from_email'] = self.smtp_from.get().strip()
            self.settings.data['twilio']['enabled'] = bool(self.tw_enabled.get())
            self.settings.data['twilio']['account_sid'] = self.tw_sid.get().strip()
            self.settings.data['twilio']['auth_token'] = self.tw_auth.get().strip()
            self.settings.data['twilio']['from_number'] = self.tw_from.get().strip()
            self.settings.data['ui']['theme'] = self.ui_theme.get().strip()
            self.settings.data['ui']['dark'] = bool(self.dark_var.get())
            self.settings.save()
            messagebox.showinfo('Saved','Settings saved. Restart app for theme changes to take full effect.')
            self.destroy()


else:
    class App(tk.Tk, AppBase):
        def __init__(self):
            tk.Tk.__init__(self)
            AppBase.__init__(self)
            self.title('PCTE Lost & Found Management System')
            self.geometry('1100x720')
            self.create_widgets()

        def create_widgets(self):
            notebook = ttk.Notebook(self)
            notebook.pack(fill='both', expand=True)
            self.form_frame = ttk.Frame(notebook)
            self.dashboard_frame = ttk.Frame(notebook)
            notebook.add(self.form_frame, text='Submit Item')
            notebook.add(self.dashboard_frame, text='Match Dashboard')

            left = ttk.Frame(self.form_frame, padding=12)
            left.pack(side='left', fill='y')
            ttk.Label(left, text='Type:').pack(anchor='w')
            self.type_var = tk.StringVar(value='lost')
            ttk.Radiobutton(left, text='Lost', variable=self.type_var, value='lost').pack(anchor='w')
            ttk.Radiobutton(left, text='Found', variable=self.type_var, value='found').pack(anchor='w')
            ttk.Label(left, text='Name:').pack(anchor='w', pady=(10,0))
            self.name_entry = ttk.Entry(left, width=30)
            self.name_entry.pack(anchor='w')
            ttk.Label(left, text='Description:').pack(anchor='w', pady=(10,0))
            self.desc_text = tk.Text(left, width=40, height=6)
            self.desc_text.pack(anchor='w')
            ttk.Label(left, text='Place:').pack(anchor='w', pady=(10,0))
            self.place_entry = ttk.Entry(left, width=30)
            self.place_entry.pack(anchor='w')
            ttk.Label(left, text='Contact Info:').pack(anchor='w', pady=(10,0))
            self.contact_entry = ttk.Entry(left, width=30)
            self.contact_entry.pack(anchor='w')
            ttk.Button(left, text='Upload Image', command=self.upload_image).pack(pady=(10,0))
            self.img_label = ttk.Label(left)
            self.img_label.pack(pady=(5,0))
            ttk.Button(left, text='Submit Item', command=self.submit_item).pack(pady=(15,0))
            ttk.Button(left, text='Settings / Notifications', command=self.open_settings).pack(pady=(6,0))

            right = ttk.Frame(self.form_frame, padding=10)
            right.pack(side='left', fill='both', expand=True)
            top_search = ttk.Frame(right)
            top_search.pack(fill='x')
            ttk.Label(top_search, text='Search:').pack(side='left')
            self.search_var = tk.StringVar()
            self.search_var.trace_add('write', lambda *args: self.refresh_list())
            ttk.Entry(top_search, textvariable=self.search_var, width=40).pack(side='left', padx=6)
            ttk.Button(top_search, text='Admin Login', command=self.admin_login).pack(side='right')

            self.tree = ttk.Treeview(right, columns=('type','name','place','date','contact'), show='headings')
            for c in ('type','name','place','date','contact'):
                self.tree.heading(c, text=c.title())
                self.tree.column(c, width=120)
            self.tree.pack(fill='both', expand=True)
            ttk.Button(right, text='Refresh List', command=self.refresh_list).pack(pady=(5,0))

            self.build_dashboard()
            self.refresh_list()

        def admin_login(self):
            LoginDialog(self, self.db)

        def upload_image(self):
            path = filedialog.askopenfilename(filetypes=[('Image Files', '*.png *.jpg *.jpeg *.bmp')])
            if not path:
                return
            ext = os.path.splitext(path)[1]
            newname = str(uuid.uuid4()) + ext
            newpath = os.path.join(IMAGES_DIR, newname)
            shutil.copy(path, newpath)
            self.selected_image_path = newpath
            self.show_thumbnail(newpath)

        def show_thumbnail(self, path, widget=None, size=(150,150)):
            try:
                img = Image.open(path)
                img.thumbnail(size)
                imgtk = ImageTk.PhotoImage(img)
                if widget is None:
                    self.img_label.img = imgtk
                    self.img_label.config(image=imgtk)
                else:
                    widget.img = imgtk
                    widget.config(image=imgtk)
            except Exception as e:
                print('Thumb error', e)

        def submit_item(self):
            itype = self.type_var.get()
            name = self.name_entry.get().strip()
            desc = self.desc_text.get('1.0','end').strip()
            place = self.place_entry.get().strip()
            contact = self.contact_entry.get().strip()
            date = datetime.date.today().isoformat()
            img = self.selected_image_path
            if not name and not desc:
                messagebox.showwarning('Missing', 'Please add at least a name or description')
                return
            item = {
                'id': str(uuid.uuid4()),
                'type': itype,
                'name': name,
                'description': desc,
                'place': place,
                'date': date,
                'contact': contact,
                'image_path': img
            }
            self.db.add_item(item)
            messagebox.showinfo('Saved', 'Item saved to database')
            matches = self.matcher.find_matches(item, topk=5)
            if matches:
                self.show_matches_popup(item, matches)
            self.common_clear_form()
            self.refresh_list()

        def refresh_list(self):
            for r in self.tree.get_children():
                self.tree.delete(r)
            search = self.search_var.get().strip()
            for it in self.db.get_items(search=search):
                self.tree.insert('', 'end', values=(it['type'], it['name'][:30], it['place'][:20], it['date'], it['contact'][:20]))

        def build_dashboard(self):
            frm = self.dashboard_frame
            top = ttk.Frame(frm, padding=10)
            top.pack(fill='x')
            ttk.Label(top, text='View matches for:').pack(side='left')
            self.view_type = tk.StringVar(value='lost')
            ttk.Radiobutton(top, text='Lost', variable=self.view_type, value='lost').pack(side='left')
            ttk.Radiobutton(top, text='Found', variable=self.view_type, value='found').pack(side='left')
            ttk.Button(top, text='Refresh Matches', command=self.populate_matches).pack(side='left', padx=10)
            ttk.Button(top, text='Generate PDF for Selected', command=self.generate_pdf_for_selected).pack(side='right')

            self.matches_canvas = tk.Canvas(frm)
            self.matches_canvas.pack(side='left', fill='both', expand=True)
            self.match_frame = ttk.Frame(self.matches_canvas)
            self.vsb = ttk.Scrollbar(frm, orient='vertical', command=self.matches_canvas.yview)
            self.vsb.pack(side='right', fill='y')
            self.matches_canvas.configure(yscrollcommand=self.vsb.set)
            self.matches_canvas.create_window((0,0), window=self.match_frame, anchor='nw')
            self.match_frame.bind('<Configure>', lambda e: self.matches_canvas.configure(scrollregion=self.matches_canvas.bbox('all')))

        def populate_matches(self):
            for w in self.match_frame.winfo_children():
                w.destroy()
            vtype = self.view_type.get()
            items = self.db.get_items(type=vtype)
            for it in items:
                container = ttk.Frame(self.match_frame, borderwidth=1, relief='solid', padding=6)
                container.pack(fill='x', pady=4, padx=4)
                top = ttk.Frame(container)
                top.pack(fill='x')
                ttk.Label(top, text=f"{it['type'].upper()} - {it['name']}", font=('TkDefaultFont', 12, 'bold')).pack(side='left')
                ttk.Label(top, text=f"{it['date']} @ {it['place']}").pack(side='right')
                mid = ttk.Frame(container)
                mid.pack(fill='x', pady=4)
                img_lbl = ttk.Label(mid)
                img_lbl.pack(side='left')
                if it['image_path']:
                    self.show_thumbnail(it['image_path'], widget=img_lbl, size=(120,120))
                text = ttk.Label(mid, text=(it['description'] or '(No description)')[:200], wraplength=600)
                text.pack(side='left', padx=10)
                matches = self.matcher.find_matches(it, topk=3)
                if matches:
                    ttk.Separator(container, orient='horizontal').pack(fill='x', pady=4)
                    ttk.Label(container, text='Possible matches:', foreground='blue').pack(anchor='w')
                    for m in matches:
                        row = ttk.Frame(container)
                        row.pack(fill='x', pady=2)
                        mimg = ttk.Label(row)
                        mimg.pack(side='left')
                        if m['image_path']:
                            self.show_thumbnail(m['image_path'], widget=mimg, size=(80,80))
                        lbl = ttk.Label(row, text=f"{m['type'].title()} - {m['name']} | Score: {m['_score']:.2f} | Place: {m['place']} | Contact: {m['contact']}", wraplength=700)
                        lbl.pack(side='left', padx=6)
                else:
                    ttk.Label(container, text='No matches found yet').pack()

        def show_matches_popup(self, item, matches):
            win = tk.Toplevel(self)
            win.title('Possible Matches')
            ttk.Label(win, text=f"Submitted: {item['type'].title()} - {item['name']}").pack(pady=4)
            for m in matches:
                frm = ttk.Frame(win, padding=6, borderwidth=1, relief='ridge')
                frm.pack(fill='x', padx=6, pady=4)
                lbl = ttk.Label(frm, text=f"{m['type'].title()} - {m['name']} | Score: {m['_score']:.2f}")
                lbl.pack(side='left')
                if m['image_path']:
                    mimg = ttk.Label(frm)
                    mimg.pack(side='right')
                    self.show_thumbnail(m['image_path'], widget=mimg, size=(80,80))
                btn_frame = ttk.Frame(frm)
                btn_frame.pack(side='right')
                ttk.Button(btn_frame, text='Email', command=lambda mm=m: self.notify_by_email(mm)).pack(side='left', padx=2)
                ttk.Button(btn_frame, text='SMS', command=lambda mm=m: self.notify_by_sms(mm)).pack(side='left', padx=2)

        def notify_by_email(self, match):
            to_email = match.get('contact')
            if not to_email:
                messagebox.showwarning('No contact', 'No contact email available for this match')
                return
            subject = 'Possible match for your lost/found item'
            body = f"We found a possible match: {match['name']} at {match['place']} | Contact: {match['contact']}"
            ok, msg = self.notifier.send_email(to_email, subject, body)
            messagebox.showinfo('Email', msg)

        def notify_by_sms(self, match):
            to_number = match.get('contact')
            if not to_number:
                messagebox.showwarning('No contact', 'No contact number available for this match')
                return
            ok, msg = self.notifier.send_sms(to_number, f"Possible match: {match['name']} at {match['place']}")
            messagebox.showinfo('SMS', msg)

        def generate_pdf_for_selected(self):
            vtype = self.view_type.get()
            items = self.db.get_items(type=vtype)
            if not items:
                messagebox.showwarning('No items', 'No items to generate report for')
                return
            item = items[0]
            matches = self.matcher.find_matches(item, topk=5)
            if not REPORTLAB_AVAILABLE:
                messagebox.showerror('Missing', 'reportlab not installed. Install with pip install reportlab')
                return
            fname = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF Files','*.pdf')])
            if not fname:
                return
            try:
                generate_pdf_report(item, matches, fname)
                messagebox.showinfo('Saved', f'PDF saved: {fname}')
            except Exception as e:
                messagebox.showerror('Error', str(e))

        def open_settings(self):
            SettingsDialog(self, self.settings)


    class LoginDialog(tk.Toplevel):
        def __init__(self, parent, db: DB):
            super().__init__(parent)
            self.db = db
            self.title('Admin Login')
            self.geometry('300x150')
            ttk.Label(self, text='Username').pack(pady=(10,0))
            self.user = ttk.Entry(self)
            self.user.pack()
            ttk.Label(self, text='Password').pack(pady=(6,0))
            self.pwd = ttk.Entry(self, show='*')
            self.pwd.pack()
            ttk.Button(self, text='Login', command=self.try_login).pack(pady=10)

        def try_login(self):
            u = self.user.get().strip()
            p = self.pwd.get().strip()
            if self.db.verify_admin(u,p):
                messagebox.showinfo('OK','Admin login successful')
                self.destroy()
            else:
                messagebox.showerror('Fail','Invalid credentials')


    class SettingsDialog(tk.Toplevel):
        def __init__(self, parent, settings: Settings):
            super().__init__(parent)
            self.settings = settings
            self.title('Settings & Notifications')
            self.geometry('620x420')
            nb = ttk.Notebook(self)
            nb.pack(fill='both', expand=True)
            smtpf = ttk.Frame(nb, padding=8)
            nb.add(smtpf, text='SMTP')
            s = self.settings.data['smtp']
            self.smtp_enabled = tk.BooleanVar(value=s.get('enabled',False))
            ttk.Checkbutton(smtpf, text='Enable SMTP', variable=self.smtp_enabled).pack(anchor='w')
            ttk.Label(smtpf, text='Host:').pack(anchor='w')
            self.smtp_host = ttk.Entry(smtpf)
            self.smtp_host.insert(0,s.get('host',''))
            self.smtp_host.pack(fill='x')
            ttk.Label(smtpf, text='Port:').pack(anchor='w')
            self.smtp_port = ttk.Entry(smtpf)
            self.smtp_port.insert(0,str(s.get('port',587)))
            self.smtp_port.pack(fill='x')
            ttk.Label(smtpf, text='Username:').pack(anchor='w')
            self.smtp_user = ttk.Entry(smtpf)
            self.smtp_user.insert(0,s.get('username',''))
            self.smtp_user.pack(fill='x')
            ttk.Label(smtpf, text='Password:').pack(anchor='w')
            self.smtp_pass = ttk.Entry(smtpf)
            self.smtp_pass.insert(0,s.get('password',''))
            self.smtp_pass.pack(fill='x')
            ttk.Label(smtpf, text='From Email:').pack(anchor='w')
            self.smtp_from = ttk.Entry(smtpf)
            self.smtp_from.insert(0,s.get('from_email',''))
            self.smtp_from.pack(fill='x')

            twf = ttk.Frame(nb, padding=8)
            nb.add(twf, text='Twilio')
            t = self.settings.data['twilio']
            self.tw_enabled = tk.BooleanVar(value=t.get('enabled',False))
            ttk.Checkbutton(twf, text='Enable Twilio', variable=self.tw_enabled).pack(anchor='w')
            ttk.Label(twf, text='Account SID:').pack(anchor='w')
            self.tw_sid = ttk.Entry(twf)
            self.tw_sid.insert(0,t.get('account_sid',''))
            self.tw_sid.pack(fill='x')
            ttk.Label(twf, text='Auth Token:').pack(anchor='w')
            self.tw_auth = ttk.Entry(twf)
            self.tw_auth.insert(0,t.get('auth_token',''))
            self.tw_auth.pack(fill='x')
            ttk.Label(twf, text='From Number:').pack(anchor='w')
            self.tw_from = ttk.Entry(twf)
            self.tw_from.insert(0,t.get('from_number',''))
            self.tw_from.pack(fill='x')

            uif = ttk.Frame(nb, padding=8)
            nb.add(uif, text='UI')
            ui = self.settings.data.get('ui',{})
            ttk.Label(uif, text='Theme name (ttkbootstrap theme)').pack(anchor='w')
            self.ui_theme = ttk.Entry(uif)
            self.ui_theme.insert(0, ui.get('theme','cosmo'))
            self.ui_theme.pack(fill='x')
            self.dark_var = tk.BooleanVar(value=ui.get('dark',False))
            ttk.Checkbutton(uif, text='Dark mode', variable=self.dark_var).pack(anchor='w')
            ttk.Button(self, text='Save Settings', command=self.save).pack(pady=8)

        def save(self):
            self.settings.data['smtp']['enabled'] = bool(self.smtp_enabled.get())
            self.settings.data['smtp']['host'] = self.smtp_host.get().strip()
            try:
                self.settings.data['smtp']['port'] = int(self.smtp_port.get().strip())
            except Exception:
                self.settings.data['smtp']['port'] = 587
            self.settings.data['smtp']['username'] = self.smtp_user.get().strip()
            self.settings.data['smtp']['password'] = self.smtp_pass.get().strip()
            self.settings.data['smtp']['from_email'] = self.smtp_from.get().strip()
            self.settings.data['twilio']['enabled'] = bool(self.tw_enabled.get())
            self.settings.data['twilio']['account_sid'] = self.tw_sid.get().strip()
            self.settings.data['twilio']['auth_token'] = self.tw_auth.get().strip()
            self.settings.data['twilio']['from_number'] = self.tw_from.get().strip()
            self.settings.data['ui']['theme'] = self.ui_theme.get().strip()
            self.settings.data['ui']['dark'] = bool(self.dark_var.get())
            self.settings.save()
            messagebox.showinfo('Saved','Settings saved.')
            self.destroy()


if __name__ == '__main__':
    if UI_BOOTSTRAP:
        app = App()
        app.mainloop()
    else:
        app = App()
        app.mainloop()
