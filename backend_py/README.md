Swasthya — FastAPI backend

Project Repository: https://github.com/kapil-parmar9399/AI-BASED-QR-HEALTHACRE-PROJECT.git

What's included

- `main.py` — FastAPI application exposing API endpoints similar to the original Node server:
  - `GET /api/` — health check
  - `POST /api/register` — register user (stores bcrypt-hashed password in `users` collection)
  - `POST /api/login` — login check
  - `GET /api/patients` — list patients
  - `GET /api/doctors` — list doctors (stub)
  - `GET /api/appointments` — list appointments (stub)

How to run (Windows)

1. Create and activate a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
# or
.\.venv\Scripts\activate.bat   # cmd.exe
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. (Optional) Set `MONGO_URL` environment variable if your MongoDB is remote. Default is `mongodb://127.0.0.1:27017`.

4. Run the server:

```powershell
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 3001 --reload
```

Notes

- The FastAPI app will attempt to serve a static React build placed at `../frontend/dist` (relative to this folder). If you prefer to keep development with React separately, you can build the React app and copy its `dist` (Vite) into that folder, or run React's dev server separately and let it talk to this API.
- The Node backend in `backend/server.js` had references to `./routes/*` that do not exist in that subfolder; that mismatch likely caused API failures. This FastAPI scaffold provides the same API paths under `/api/*` and can be used to replace the Node server.
- If you want, I can: (A) port every Node route in detail (CRUD + admin auth), (B) add token-based auth, or (C) wire the frontend to this API now.

Full-Python mode

I converted the project to server-rendered Python using FastAPI + Jinja2 templates. The `backend_py` folder now contains:

- `main.py` — full application serving pages and API endpoints.
- `templates/` — Jinja templates for `home`, `login`, `register`, and `patients` pages.
- `static/` — CSS and static files served at `/static`.
- `requirements.txt` — updated with `jinja2` and `python-multipart`.

How to run the full app (Windows):

```powershell
cd backend_py
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Open http://localhost:3001 in your browser. Default seeded user: `admin` / `admin` (use the Register page to create new users). The app will seed sample doctors, patients, and appointments on first start when connected to MongoDB.

If MongoDB is not running, the app will still start and you can use the UI but data will not persist and DB-backed features will display stub messages.
