# 🌱 FoodSaver – Food Waste Reduction Platform

Flask + SQLite + HTML/CSS/JS. Connects food donors with people who need food.

## Folder structure
```
foodsaver/
├── app.py              # Flask backend (routes + database)
├── requirements.txt
├── foodsaver.db        # created automatically on first run
├── static/
│   ├── style.css
│   └── script.js
└── templates/
    ├── base.html  index.html  register.html  login.html
    ├── donate.html  foods.html  dashboard.html
    └── tips.html  admin.html
```

## Run in VS Code (step by step)
1. Install **Python 3.9+** from python.org (tick "Add Python to PATH" on Windows).
2. Install **VS Code** and the **Python** extension.
3. Unzip this folder, then in VS Code: **File → Open Folder → foodsaver**.
4. Open the terminal: **Terminal → New Terminal**.
5. Create a virtual environment:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - Mac/Linux: `python3 -m venv venv` then `source venv/bin/activate`
6. Install Flask: `pip install -r requirements.txt`
7. Run: `python app.py`
8. Open **http://127.0.0.1:5000** in your browser.

## Default admin login
- Email: `admin@foodsaver.com`
- Password: `admin123`

## Try it
1. Register a donor account → **Donate** → fill the form.
2. Log out, register a second account → **Available Food** → **Request Food**.
3. Check **Dashboard** for stats, and log in as admin to see **Admin**.

To reset all data, stop the app and delete `foodsaver.db`.
