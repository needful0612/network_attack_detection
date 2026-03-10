# NIDS: Distributed Network Intrusion Detection System

A microservices-based pipeline for real-time network traffic analysis, feature extraction, and multi-model threat classification. Built for Kubernetes using Go, Python (ONNX), and Redis Streams.

## 1. System Architecture
The system transitions from a monolithic capture tool to an asynchronous, scalable pipeline prioritizing high-fidelity detection through an **Ensemble Voting** mechanism.

### Service Roles
* **Sniffer**: Captures raw traffic on the `hostNetwork`. It performs real-time feature extraction and publishes Protobuf-encoded features to the Redis Broker.
* **Broker (Redis Streams)**: Manages message distribution using a **Fan-out pattern**. This allows parallel processing of the same traffic stream by multiple specialized workers.
* **Inference Workers (Python/ONNX)**: 
    * **SVM Worker**: Supervised classification for known threat signatures (Mirai, Gafgyt).
    * **KitNet Worker**: Unsupervised anomaly detection for novel zero-day threats.
* **Sinker (Go)**: A high-performance consumer utilizing **Redis Consumer Groups** and **AutoClaim** logic to ensure zero-drop persistence into the database.
* **Database (TimescaleDB)**: Stores alert scores and traffic metadata for historical analysis and Grafana visualization.

## 2. Technical Specifications

### Feature Engineering & Preprocessing
To handle signal instability in network telemetry, a custom pipeline was implemented:
1.  **Clock Purge**: Dropped features with variance $< 0.01$ in low lambda windows.
2.  **Logarithmic Burst Ratios**: Replaced weights with differences: $log1p(fast\_stream) - log1p(slow\_stream)$.
3.  **Symmetric Log Transform**: Applied to handle long-tailed distributions: $sign(x) \cdot \log(1 + |x|)$.
4.  **Hard Clipping**: Feature values are clipped to $[-10, 10]$ to maintain SVM hyperplane stability.

## 3. Operational Guide

### Local & Cluster Setup
The project utilizes a `Makefile` to abstract complex Kubernetes/Docker commands.

> **Note**: To use `make helm-` commands, you must have the **Helm** binary installed. Refer to the [official Helm installation guide](https://helm.sh/docs/intro/install/).

| Command | Action |
| :--- | :--- |
| `make cluster-up` | Initializes KinD cluster and local registry. |
| `make build-all` | Builds all Docker images (Main, Sinker, Grafana). |
| `make run-deployment` | Deploys full stack (DB, Redis, App) with automated health checks. |
| `make helm-install` | Deploys the stack using the local Helm chart. |
| `make logs-app` | Streams logs from all active microservices. |

### Testing & Simulation
To verify the pipeline against a Mirai botnet attack:
1.  **Simulate Traffic**: `make simulate-attack` (Replays PCAP into the host's dummy `eth1` interface).
2.  **Verify Results**: `make e2e-test` or `make helm-e2e-test`. This executes a `pytest` suite that queries TimescaleDB to confirm that alerts were successfully generated and persisted.

---

## 4. Known Issues & Troubleshooting

### E2E Test & `hostNetwork` DNS Conflict

**The Issue:** To inject traffic into the host interface, the Pod must use the host network namespace. This causes it to inherit the host's DNS settings, which often fails to resolve internal K8s addresses like `nids-db.default.svc.cluster.local`.

---

## 5. Engineering Reflections (Technical Decisions)

Building this Project required several architectural trade-offs to balance low-latency analysis with cloud-native reliability:

* **Reliable Persistence**: A high-performance consumer using Redis Consumer Groups. It implements XAutoClaim to detect and recover "stalled" messages. If a Sinker instance fails during a database write, other instances automatically claim the pending alerts to ensure 100% persistence reliability.
* **ONNX for Inference**: By exporting Python models to ONNX allows workers to handle high packet-per-second (PPS) loads on standard CPU nodes without requiring GPU acceleration.
* **Host Networking Challenges**: Utilizing `hostNetwork: true` was necessary for raw packet capture via `libpcap`, but it bypassed internal Kubernetes DNS. Solving this via `ClusterFirstWithHostNet` and manual `dnsConfig` demonstrated the complexities of hybrid networking in Linux environments.


## 6. Future Roadmap & Hardening

The current architecture is a functional distributed alpha. Future development is focused on making this into a production-grade piepline and observability:

### High-Performance Networking & Kernel Optimization
* **XDP/eBPF Ingestion**: Transition the Sniffer from scapy to **eBPF (XDP)**. By processing packets directly in the NIC driver space, we can drop or redirect traffic before it even hits the heavy Linux networking stack, significantly reducing CPU overhead.
* **io_uring for Async I/O**: Implement `io_uring` in the Go Sinker and Sniffer to handle disk and socket I/O. This reduces expensive system calls and context switching when streaming massive amounts of feature data to Redis or TimescaleDB.

### Observability & Resilience
* **Metric-Based Probes**: Transition from basic process checks to custom Liveness/Readiness probes that monitor Redis consumer lag and stream depth.
* **Horizontal Pod Autoscaling (HPA)**: Implement HPA to dynamically scale the SVM and KitNet worker pools based on real-time traffic volume in the Redis Broker.

### CI/CD & Security
* **Automated ML-Ops**: Build GitHub Actions for automated ONNX model linting and multi-architecture (AMD64/ARM64) Docker builds.
* **Principle of Least Privilege**: Refine the Sniffer's security context by moving from `privileged: true` to granular Linux Capabilities (`CAP_NET_RAW`, `CAP_IPC_LOCK`).
* **Service Mesh Integration**: Explore mTLS encryption (via Istio or Linkerd) for secure data-in-transit between the Sinker and the TimescaleDB instance.

## 7. Maintenance
* **Logs**: `make logs-app` for unified streaming of all service logs.
* **Cleanup**: `make helm-clean` to remove the release and associated PVCs.
* **Artifacts**: `make clean-artifacts` to remove downloaded datasets and trained models.