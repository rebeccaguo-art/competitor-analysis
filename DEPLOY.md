# How to deploy to Databricks Apps

## Step 1 — Build the React frontend (run once locally)

```bash
cd frontend
npm install
npm run build
# This creates frontend/dist/ — the compiled React app
```

## Step 2 — Set the table name (if migrated to shared schema)

Edit `backend/config.py`, change the one line:
```python
TABLE_NAME = "your_new_schema.competiscan_master_with_competitor"
```

## Step 3 — Upload to Databricks

Upload the entire `competiscan-app/` folder to your Databricks workspace.
You can use the Databricks UI (Workspace → Import) or the CLI:

```bash
databricks workspace import-dir competiscan-app /Workspace/Users/rebecca.guo@avant.com/competiscan-app
```

## Step 4 — Create the Databricks App

1. Go to **Databricks Apps** in the left sidebar
2. Click **Create app**
3. Point it to the uploaded folder
4. Set these **environment variables** in the App settings:
   - `DATABRICKS_HTTP_PATH` — your SQL warehouse HTTP path
     (find it in SQL Warehouses → your warehouse → Connection details)
   - `DATABRICKS_HOST` and `DATABRICKS_TOKEN` are set automatically
5. Set the **start command**:
   ```
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```
   with working directory: `backend/`
6. Click **Deploy**

## Step 5 — Open the app

Databricks will give you a URL like:
`https://your-workspace.azuredatabricks.net/apps/competiscan-dashboard`

---

## Local development (optional)

Run backend and frontend separately:

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
export DATABRICKS_HOST=...
export DATABRICKS_HTTP_PATH=...
export DATABRICKS_TOKEN=...
uvicorn app:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
# Open http://localhost:5173
```
