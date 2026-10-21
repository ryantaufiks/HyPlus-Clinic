COMPOSE := docker compose
BACKUP_DIR := backups

.PHONY: init-env up down restart logs ps migrate createsuperuser shell test backup restore

init-env:        ## Create .env with generated secrets
	./scripts/init-env.sh

up:              ## Build and start AIVIN
	$(COMPOSE) up -d --build

down:            ## Stop AIVIN (data is kept)
	$(COMPOSE) down

restart:
	$(COMPOSE) restart web

logs:
	$(COMPOSE) logs -f --tail=200 web

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec web python manage.py migrate

createsuperuser: ## Create an admin account (interactive)
	$(COMPOSE) exec web python manage.py createsuperuser

shell:
	$(COMPOSE) exec web python manage.py shell

test:
	$(COMPOSE) run --rm -e DEBUG=true web python manage.py test

backup:          ## Dump the database to backups/aivin-YYYYmmdd-HHMMSS.sql.gz
	@mkdir -p $(BACKUP_DIR) && chmod 700 $(BACKUP_DIR)
	$(COMPOSE) exec -T db sh -c 'pg_dump -U "$$POSTGRES_USER" "$$POSTGRES_DB"' | gzip > $(BACKUP_DIR)/aivin-$$(date +%Y%m%d-%H%M%S).sql.gz
	@ls -1t $(BACKUP_DIR) | head -1

restore:         ## Restore a dump: make restore FILE=backups/aivin-....sql.gz
	@test -n "$(FILE)" || (echo "usage: make restore FILE=..." && exit 1)
	gunzip -c $(FILE) | $(COMPOSE) exec -T db sh -c 'psql -U "$$POSTGRES_USER" "$$POSTGRES_DB"'
