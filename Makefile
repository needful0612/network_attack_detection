COMPOSE_FILE := deployment/docker-compose.yml
PROJECT_DIR  := .
PROJECT_NAME := nids

DOCKER_COMPOSE := docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) --project-directory $(PROJECT_DIR)

.PHONY: up build_up down logs restart ps

up:
	$(DOCKER_COMPOSE) up -d

build_up:
	$(DOCKER_COMPOSE) up --build

logs:
	$(DOCKER_COMPOSE) logs -f

down:
	$(DOCKER_COMPOSE) down --remove-orphans

restart:
	$(DOCKER_COMPOSE) restart

ps:
	$(DOCKER_COMPOSE) ps