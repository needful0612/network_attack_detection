#!/bin/bash
set -e

REG_NAME='kind-registry'
REG_PORT='5001'

# Create registry container if it doesn't exist
if [ "$(docker inspect -f '{{.State.Running}}' "${REG_NAME}" 2>/dev/null || true)" != 'true' ]; then
  echo ">>> Creating local registry..."
  docker run -d --restart=always -p "127.0.0.1:${REG_PORT}:5000" --network bridge --name "${REG_NAME}" registry:2
fi

# Create KinD cluster with the registry config
echo ">>> Creating KinD cluster..."
cat <<EOF | kind create cluster --name nids-cluster --image kindest/node:v1.31.0 --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5001"]
    endpoint = ["http://kind-registry:5000"]
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30000
    hostPort: 3000
EOF

# Connect registry to cluster network
docker network connect "kind" "${REG_NAME}" || true

# Document the registry
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

echo ">>> Cluster is ready!"