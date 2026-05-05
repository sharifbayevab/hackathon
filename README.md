# AI Olympiad Leaderboard

Self-hosted Kaggle-style leaderboard for an AI olympiad. One active task at a time, public/private split scoring, configurable metric, deadline, multilingual UI (uz / ru / en).

## Stack
FastAPI · PostgreSQL · SQLAlchemy + Alembic · Jinja2 + Tailwind (CDN) · scikit-learn · Docker Compose

## Quick start

Only Postgres runs in Docker; the app runs directly on the host.

```bash
cp .env.example .env
# edit .env: at minimum change SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD

# 1. start Postgres
docker compose up -d

# 2. start the app (creates venv, installs deps, migrates, creates admin, runs uvicorn)
./run.sh
```

Open http://localhost:8000 · admin panel: http://localhost:8000/admin/login

## How it works

1. **Admin** opens `/admin`, creates the task: title, description, metric, deadline, ID/answer column names, optional train/sample CSVs.
2. **Admin** uploads the **groundtruth CSV** with three columns: `id`, `answer`, `split` (`public` or `private`).
3. **Participants** open `/`, enter ФИО + group, get redirected to `/task`. They download train data, upload predictions CSV (with `id` and `answer` columns), and see their public score immediately.
4. **Leaderboard** at `/leaderboard` shows the public score per participant (best of all submissions). After the deadline it switches to private scores automatically.
5. There is **no submission limit** — only the best score counts.

## Groundtruth CSV format

```csv
id,answer,split
1,0,public
2,1,public
3,1,private
4,0,private
```

- Column names for `id` and `answer` are configurable per task in the admin panel.
- The `split` column is fixed and required.
- Both `public` and `private` rows are required.

## Submission CSV format

```csv
id,answer
1,0
2,1
3,1
4,0
```

Must contain only the configured ID and answer columns; one prediction per groundtruth row.

## Supported metrics

| Metric | Direction |
|---|---|
| accuracy | higher is better |
| f1_macro | higher is better |
| f1_binary | higher is better |
| roc_auc | higher is better |
| log_loss | lower is better |
| mae | lower is better |
| rmse | lower is better |
| r2 | higher is better |

## Manual run (without `run.sh`)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
set -a && source .env && set +a   # export DATABASE_URL etc.
alembic upgrade head
python -m app.bootstrap
uvicorn app.main:app --reload
```

## Resetting

```bash
docker compose down -v   # drops the database volume
rm -rf data/             # drops uploaded files
```
