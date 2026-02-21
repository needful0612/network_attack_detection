COMPOSE_FILE := docker/docker-compose.yml
PROJECT_DIR  := .
PROJECT_NAME := nids

DOCKER_COMPOSE := docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) --project-directory $(PROJECT_DIR)

.PHONY: up build_up down logs restart ps cluster-up cluster-down build-and-push

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

cluster-up:
	chmod +x ./cluster-setup.sh
	./cluster-setup.sh

cluster-down:
	kind delete cluster --name nids-cluster
	docker stop kind-registry && docker rm kind-registry

build-and-push:
	docker build -t localhost:5001/nids-main:latest -f docker/Dockerfile .
	docker push localhost:5001/nids-main:latest