# Email Automation & Alerts Platform — Full Project

```
email_automation_project/
├── app/                    FastAPI backend (emails, alerts, scheduler, SMTP)
├── streamlit_app.py        Streamlit dashboard (talks to the backend over HTTP)
├── requirements.txt        Backend dependencies
├── requirements-ui.txt     Dashboard dependencies
├── .env.example            SMTP + database settings template
├── README_platform.md      Detailed API usage and examples
├── milestone2_prototype/   Milestone 2: standalone core modules + runnable demo
└── docs/                   Milestone 1 & 2 PDF reports, architecture diagrams
```

## Setup (Windows, PowerShell or CMD)

Run these from inside this folder. **The venv step matters** — the error
`No module named 'pydantic_settings'` means packages were not installed into
the Python you are running.

```
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

Dashboard (second terminal, same folder, venv activated):

```
python -m pip install -r requirements-ui.txt
python -m streamlit run streamlit_app.py
```

macOS/Linux: use `python3 -m venv venv` and `source venv/bin/activate`.

Always use `python -m pip` / `python -m uvicorn` so pip and Python are guaranteed
to be the same interpreter.

## Milestone 2 prototype

```
cd milestone2_prototype
python -m pip install -r requirements.txt
python tests.py
python prototype_demo.py
```
