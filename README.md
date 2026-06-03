# English Learning Portfolio

Proyecto de aprendizaje de ingles con arquitectura separada:

- `backend/`: `FastAPI + SQLAlchemy`
- `frontend/`: `React + Tailwind CSS + Vite`
- `data/`: material local, grafo, notas y base previa de Streamlit

## Backend

```bash
source venv/bin/activate
cp .env.example .env
uvicorn backend.app.main:app --reload
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Desarrollo completo

Puedes levantar backend y frontend juntos con:

```bash
./dev.sh
```

- El backend usa `uvicorn --reload`, asi que se reinicia solo al guardar.
- El frontend usa `vite`, asi que hace HMR/recarga automatica al guardar.
- No necesitas volver a ejecutar ambos procesos por cada cambio.

Si un puerto queda ocupado por una ejecucion anterior:

```bash
./dev-stop.sh
```

Eso libera los puertos `8000` y `5173`.

## PostgreSQL

```bash
docker compose up -d postgres
```

Si `DATABASE_URL` no esta definida, el backend usa `SQLite` local en `data/portfolio.db`.
Si defines `DATABASE_URL` con PostgreSQL, el backend migra el historial del `data/ingles.db` al nuevo esquema SQLAlchemy cuando arranca por primera vez.
