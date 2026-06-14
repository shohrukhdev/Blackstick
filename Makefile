DC      = docker compose -f docker-compose.yml
DC_PROD = docker compose -f docker-compose.prod.yml

.PHONY: help \
        up down build rebuild logs logs-web \
        shell bash migrate makemigrations createsuperuser collectstatic test lint \
        infra-up infra-down \
        prod-up prod-down prod-logs prod-shell prod-bash prod-migrate

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Local: full stack (web + postgres + redis) ─────────────────────────────────

up: ## Start all local services (web, postgres, redis)
	$(DC) up -d

down: ## Stop all local services
	$(DC) down

build: ## Build the local dev image
	$(DC) build web

rebuild: ## Rebuild dev image and restart
	$(DC) up -d --build web

logs: ## Stream all local container logs
	$(DC) logs -f

logs-web: ## Stream web container logs only
	$(DC) logs -f web

shell: ## Open Django shell inside the local web container
	$(DC) exec web python manage.py shell

bash: ## Open a shell inside the local web container
	$(DC) exec web /bin/sh

migrate: ## Apply database migrations
	$(DC) exec web python manage.py migrate

makemigrations: ## Create new migration files
	$(DC) exec web python manage.py makemigrations

createsuperuser: ## Create a Django superuser
	$(DC) exec web python manage.py createsuperuser

collectstatic: ## Collect static files
	$(DC) exec web python manage.py collectstatic --no-input \
		--ignore=chartjs --ignore=dist --ignore=dt --ignore=fc \
		--ignore=jui --ignore=login --ignore=node_modules \
		--ignore=plugins --ignore=summernote --ignore=teeth \
		--ignore=admin --ignore=venv --ignore=rest_framework \
		--ignore=fontawesomefree

test: ## Run the test suite
	$(DC) exec web python manage.py test orders booket

lint: ## Run flake8
	$(DC) exec web flake8

# ── Local: infra only (run Django natively, Docker for postgres + redis) ────────

infra-up: ## Start only postgres and redis (for native manage.py runserver workflow)
	$(DC) up -d postgres redis

infra-down: ## Stop postgres and redis
	$(DC) stop postgres redis

# ── Production helpers (run on the server) ─────────────────────────────────────

prod-up: ## Start the production stack
	$(DC_PROD) up -d

prod-down: ## Stop the production stack
	$(DC_PROD) down

prod-logs: ## Stream production logs
	$(DC_PROD) logs -f

prod-shell: ## Django shell in the production web container
	$(DC_PROD) exec web python manage.py shell

prod-bash: ## Shell in the production web container
	$(DC_PROD) exec web /bin/sh

prod-migrate: ## Apply migrations in production
	$(DC_PROD) exec web python manage.py migrate
