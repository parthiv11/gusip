.PHONY: up down logs seed demo test backend-dev frontend-dev fmt

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend worker frontend

seed:
	docker compose exec backend python -m app.seed

demo:
	docker compose exec worker python -m app.workers.demo_scenario

test:
	cd backend && python -m pytest -q

backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

fmt:
	cd backend && python -m ruff check --fix . || true
