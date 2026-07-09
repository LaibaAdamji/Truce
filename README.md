# Truce

Set up backend (Windows, macOS, Linux):

```bash
python -m venv venv

# activate the virtual environment
# Windows (PowerShell):  .\venv\Scripts\Activate.ps1
# Windows (cmd):         venv\Scripts\activate.bat
# macOS / Linux:         source venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` is UTF-8 with LF line endings. Windows-only packages (for example `pywin32`) use pip environment markers so installs succeed on macOS and Linux too.

Set up frontend:
`streamlit run app.py`

