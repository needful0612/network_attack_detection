#!/bin/bash
set -e

REG_NAME='kind-registry'
REG_PORT='5001'
PROJECT_ROOT=${PROJECT_ROOT:-$(pwd)}

# Start Registry
if [ "$(docker inspect -f '{{.State.Running}}' "${REG_NAME}" 2>/dev/null || true)" != 'true' ]; then
  docker run -d --restart=always -p "127.0.0.1:${REG_PORT}:5000" --network bridge --name "${REG_NAME}" registry:2
fi

# Create Cluster
cat <<EOF | kind create cluster --name nids-cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."kind-registry:5000"]
    endpoint = ["http://kind-registry:5000"]
    insecure_skip_verify = true
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30000
    hostPort: 3000 # Grafana
  - containerPort: 30001
    hostPort: 9090 # Prometheus
  extraMounts:
  - hostPath: ${PROJECT_ROOT}
    containerPath: ${PROJECT_ROOT}
EOF

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REG_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

# Network Link
docker network connect "kind" "${REG_NAME}" || true

echo ">>> Cluster is ready!"