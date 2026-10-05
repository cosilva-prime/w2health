# W2Health Intelligence — atalhos de desenvolvimento
# Requer GNU Make. No Windows sem make, use os comandos `docker compose` diretamente
# (ver README) ou os scripts em scripts/*.ps1.

COMPOSE = docker compose

.PHONY: help up down restart logs ps build test test-backend clean migrate seed seed-full seed-tenant-b bootstrap rebuild-agg

help:
	@echo "up          - sobe todo o ambiente (build + start em background)"
	@echo "down        - para e remove os containers"
	@echo "restart     - down + up"
	@echo "logs        - segue os logs de todos os serviços"
	@echo "ps          - status dos serviços"
	@echo "build       - rebuild das imagens"
	@echo "test        - roda a suite de testes do backend (em container)"
	@echo "seed        - massa sintética do tenant demo (Operadora Vida Plena)"
	@echo "seed-tenant-b - 2º tenant sintético (mesmos códigos de negócio — isolamento)"
	@echo "bootstrap   - catálogo de planos/features + usuários demo (senhas exibidas uma vez)"
	@echo "clean       - down + remove volumes (apaga o banco)"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart: down up

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

test: test-backend

test-backend:
	$(COMPOSE) run --rm --no-deps backend pytest

migrate:
	$(COMPOSE) exec backend alembic upgrade head

seed:
	$(COMPOSE) exec backend python -m app.seed.run --beneficiarios 20000

seed-full:
	$(COMPOSE) exec backend python -m app.seed.run --beneficiarios 100000

seed-tenant-b:
	$(COMPOSE) exec backend python -m app.seed.run --tenant w2h-demo-b --tenant-name "Operadora Horizonte" --beneficiarios 5000 --seed 7

bootstrap:
	$(COMPOSE) exec backend python -m app.saas.cli bootstrap-demo

rebuild-agg:
	$(COMPOSE) exec backend python -m app.seed.aggregate --tenant w2h-demo

clean:
	$(COMPOSE) down -v
