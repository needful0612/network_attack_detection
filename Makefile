COMPOSE_FILE := docker/docker-compose.yml
PROJECT_DIR  := .
PROJECT_NAME := nids

DOCKER_COMPOSE := docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) --project-directory $(PROJECT_DIR)

REGISTRY := localhost:5001
REPO     := nids

PROJECT_ROOT := $(shell pwd)

HELM_RELEASE := nids
CHART_DIR    := ./charts/nids
NAMESPACE    := default

.PHONY: up build_up logs down restart ps \
        cluster-up cluster-down clear-network \
        clean-infra clean-pvc clean-all clean-artifacts \
        rollout deploy-db deploy-infra deploy-app train \
        status-all status watch logs-app logs-trainer check-models debug \
        simulate-attack run-deployment \
        build-and-push-all build-all push-all \
        build-main build-sinker build-grafana \
		e2e-test \
		helm-install run-helm-deployment helm-clean helm-run-trainer helm-simulate-attack \
		helm-watch helm-logs

# --- Docker Compose (Local Dev) ---
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
# --- Kubernetes / KinD Setup ---
cluster-up:
	chmod +x ./cluster-setup.sh
	PROJECT_ROOT=$(PROJECT_ROOT) ./cluster-setup.sh

cluster-down:
	kind delete cluster --name nids-cluster
	docker stop kind-registry && docker rm kind-registry
# --- soft reset  ---
clean-infra:
	kubectl delete -f k8s/db.yaml
	kubectl delete -f k8s/redis.yaml
	kubectl delete -f k8s/grafana.yaml
	kubectl delete -f k8s/redis-exporter.yaml
	kubectl delete configmap db-init-script || true

clean-pvc:
	kubectl delete pvc timescale-pvc
	
clean-all: clean-infra
	kubectl delete -f k8s/prometheus.yaml
	kubectl delete -f k8s/sinker.yaml
	kubectl delete -f k8s/svm-worker.yaml
	kubectl delete -f k8s/kitnet-worker.yaml
	kubectl delete -f k8s/sniffer.yaml

clean-artifacts:
	sudo rm -rf data
	sudo rm -rf models

# Usage: make rollout name=sniffer
rollout:
	kubectl rollout restart deployment $(name)
	kubectl rollout status deployment $(name)

# --- Build & Push ---
build-and-push-all: build-all push-all

build-all: build-main build-sinker build-grafana

push-all:
	docker push $(REGISTRY)/$(REPO)-main:latest
	docker push $(REGISTRY)/$(REPO)-sinker:latest
	docker push $(REGISTRY)/$(REPO)-grafana:latest

build-main:
	docker build -t $(REGISTRY)/$(REPO)-main:latest -f docker/Dockerfile .

build-sinker:
	docker build -t $(REGISTRY)/$(REPO)-sinker:latest -f docker/Dockerfile.sinker .

build-grafana:
	docker build -t $(REGISTRY)/$(REPO)-grafana:latest -f docker/Dockerfile.grafana .
# --- Deployment Logic ---
deploy-db:
	-kubectl delete configmap db-init-script 2>/dev/null || true
	kubectl create configmap db-init-script --from-file=init.sql=./postgres/init.sql
	kubectl apply -f k8s/db.yaml

deploy-infra: deploy-db
	kubectl apply -f k8s/redis.yaml
	kubectl apply -f k8s/prometheus.yaml
	kubectl apply -f k8s/grafana.yaml
	kubectl apply -f k8s/redis-exporter.yaml

deploy-app:
	kubectl apply -f k8s/sinker.yaml
	cat k8s/sniffer.yaml | sed 's|$${PROJECT_ROOT}|$(PROJECT_ROOT)|g' | kubectl apply -f -
	cat k8s/svm-worker.yaml | sed 's|$${PROJECT_ROOT}|$(PROJECT_ROOT)|g' | kubectl apply -f -
	cat k8s/kitnet-worker.yaml | sed 's|$${PROJECT_ROOT}|$(PROJECT_ROOT)|g' | kubectl apply -f -

train:
	kubectl delete job nids-trainer --ignore-not-found=true
	cat k8s/trainer-job.yaml | sed 's|$${PROJECT_ROOT}|$(PROJECT_ROOT)|g' | kubectl apply -f -

# --- Deployment monitoring ---
status-all:
	kubectl get all

status:
	@kubectl get pods,jobs,services,deployments -o wide

watch:
	watch kubectl get all

logs-app:
	kubectl logs -l 'app in (svm-worker, kitnet-worker, sinker, sniffer)' --all-containers=true -f --tail=50 --max-log-requests=10

logs-trainer:
	kubectl logs -l job-name=nids-trainer -f

check-models:
	@echo ">>> Files in models directory:"
	ls -lh $(PROJECT_ROOT)/models
	@echo ">>> Files in data directory:"
	ls -lh $(PROJECT_ROOT)/data

debug:
	kubectl describe pod $(pod)

# --- Deployment test ----
simulate-attack:
	kubectl delete job traffic-generator --ignore-not-found=true
	cat k8s/traffic-generator.yaml | sed 's|$${PROJECT_ROOT}|$(PROJECT_ROOT)|g' | kubectl apply -f -

# --- full deployment ---
run-deployment: cluster-up build-and-push-all
	@echo ">>> Deploying Infrastructure..."
	$(MAKE) deploy-infra
	
	@echo ">>> Polling for broker Deployment..."
	@until kubectl get deployment broker >/dev/null 2>&1; do \
		echo "Waiting for Redis resource to be created in K8s..."; \
		sleep 2; \
	done
	kubectl wait --for=condition=available deployment/broker --timeout=60s

	@echo ">>> Polling for DB Deployment..."
	@until kubectl get deployment db >/dev/null 2>&1; do \
		echo "Waiting for DB resource to be created in K8s..."; \
		sleep 2; \
	done
	kubectl wait --for=condition=available deployment/db --timeout=120s
	
	@echo ">>> Starting Training Job..."
	$(MAKE) train
	@echo ">>> Waiting for Models to generate..."
	kubectl wait --for=condition=complete job/nids-trainer --timeout=300s
	
	@echo ">>> Deploying Application..."
	$(MAKE) deploy-app

generate-protos:
	docker run --rm -v $(PWD):/workspace -w /workspace python:3.11-slim sh -c "\
		apt-get update && apt-get install -y protobuf-compiler && \
		pip install mypy-protobuf && \
		protoc -I./protos \
		--python_out=./scripts/DTO \
		--mypy_out=./scripts/DTO \
		./protos/packet.proto && \
		chown $(shell id -u):$(shell id -g) ./scripts/DTO/packet_pb2.py* "

e2e-test:
	@echo ">>> Cleaning up previous E2E jobs..."
	-kubectl delete job nids-e2e-test 2>/dev/null || true
	@echo ">>> Deploying E2E Integration Tester..."
	cat k8s/e2e-tester.yaml | sed 's|$${PROJECT_ROOT}|$(PROJECT_ROOT)|g' | kubectl apply -f -
	@echo ">>> Waiting for E2E test to complete (timeout 60s)..."
	@kubectl wait --for=condition=complete job/nids-e2e-test --timeout=60s || (echo "E2E Test Failed or Timed Out" && kubectl logs job/nids-e2e-test && exit 1)
	@echo ">>> E2E Test Passed"

# --- helm section ---
helm-install:
	@echo ">>> Installing NIDS via Helm..."
	helm upgrade --install $(HELM_RELEASE) $(CHART_DIR) \
		--namespace $(NAMESPACE) \
		--set global.projectRoot=$(PROJECT_ROOT) \
		--set global.registry=$(REGISTRY) \
		--set-file database.initSqlContent=$(PROJECT_ROOT)/postgres/init.sql \
		--atomic --timeout 10m

run-helm-deployment: cluster-up build-and-push-all helm-install
	@echo ">>> NIDS is live. Check status with 'make status'"

# --- Clean up ---
helm-clean:
	helm uninstall $(HELM_RELEASE) || true
	kubectl delete pvc --all || true

# --- Logic Overrides ---
helm-run-trainer:
	helm upgrade --install $(HELM_RELEASE) $(CHART_DIR) \
		--set trainer.enabled=true \
		--set global.projectRoot=$(PROJECT_ROOT)

helm-simulate-attack:
	kubectl delete job traffic-generator --ignore-not-found=true
	# You can still use the old YAML if you haven't templated it yet,
	# but eventually, this should be: helm test nids
	cat k8s/traffic-generator.yaml | sed 's|$${PROJECT_ROOT}|$(PROJECT_ROOT)|g' | kubectl apply -f -

helm-watch:
	watch "kubectl get all -l app.kubernetes.io/instance=$(HELM_RELEASE)"

helm-logs:
	kubectl logs -l 'app.kubernetes.io/instance=$(HELM_RELEASE)' --all-containers=true -f --tail=50