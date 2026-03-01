.PHONY: dev-backend dev-frontend docker-up docker-down lint-backend lint-frontend

dev-backend:
	cd backend && uvicorn main:app --reload

dev-frontend:
	cd frontend && bun run dev

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

lint-backend:
	cd backend && ruff check . && ruff format --check .

lint-frontend:
	cd frontend && bun run lint
