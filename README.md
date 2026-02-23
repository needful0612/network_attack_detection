# Tiered NIDS: Ensemble Voting Pipeline

This project implements a distributed, cloud-native pipeline for Network Intrusion Detection (NIDS). It transitions from a monolithic capture tool to a scalable microservices architecture that prioritizes high-fidelity detection through an **Ensemble Voting** mechanism.

Instead of relying on a single model, the system captures traffic and broadcasts features to multiple specialized workers:
- **Supervised Voting (SVM)**: A calibrated Linear SVM trained on known botnet signatures to identify specific attack patterns.
- **Unsupervised Voting (KitNet)**: An online anomaly detection ensemble (Autoencoders) that identifies novel threats without prior training.
- **Reliable Persistence**: A dedicated **Go-based Sinker** that aggregates these "votes," determines the final alert state, and ensures persistence.



## System Architecture
The system is orchestrated on **Kubernetes**, leveraging asynchronous streaming to ensure zero packet loss during analysis spikes:

* **Sniffer Pod (hostNetwork)**: Directly attaches to the host interface to capture raw traffic. It performs real-time feature extraction and streams data to the Redis Broker. 
* **The Broker (Redis Streams)**: Acts as the load balancer and buffer. By using a **Fan-out pattern**, it allows both the SVM and KitNet workers to process the same stream of data in parallel.
* **Parallel Inference Workers (Python/ONNX)**:
    * **SVM Worker**: Supervised classification for known threat patterns.
    * **KitNet Worker**: Unsupervised anomaly detection for zero-day threats.
    * **Decision Logic**: By running these in parallel, the system cross-references "known attacks" with "unusual behavior" to drastically reduce false positives.
* **The Sinker (Go)**: A high-performance consumer that manages Redis Consumer Groups. It implements **AutoClaim** logic to ensure no security alert is ever dropped, even during service interruptions.
* **Database (TimescaleDB)**: A time-series optimized PostgreSQL instance that stores the combined scores for historical analysis and Grafana visualization.

---

## Technical Specifications

### Feature Engineering & Preprocessing
To resolve signal instability and overfitting common in raw network datasets, a custom "Precision-Safe" pipeline was implemented:

1.  **The "Clock Purge"**: Dropped unstable features with low lambda windows (80, 77, 74, 71, and 68) where signal variance was below 0.01.
2.  **Burst Ratios**: Replaced raw weights with logarithmic differences: $log1p(fast\_stream) - log1p(slow\_stream)$.
3.  **Symmetric Log Transform**: Applied to handle long-tailed distributions: $sign(x) \cdot \log(1 + |x|)$.
4.  **Robust Scaling**: Scaled features using Median and IQR to minimize outlier impact.
5.  **Hard Clipping**: Feature values are clipped to $[-10, 10]$ to prevent outlier-driven instability in the SVM hyperplane.

### Model Selection & Performance
* **Algorithm**: Linear Support Vector Classifier (LinearSVC) with L2 regularization for stable decision boundaries.
* **Probability Calibration**: Uses **Platt Scaling** (Sigmoid calibration) to transform SVM decision margins into usable probability scores.
* **Format**: Exported to **ONNX** for low-latency, CPU-bound inference in production.

---

## Deployment Guide

### Step 0: Data Acquisition & Permissions
This project utilizes the **Kitsune Network Attack** datasets (~GBs of raw CSV).
1.  **Disk Space**: Ensure at least 10GB of free space.
2.  **Acquire Data**:
    ```bash
    chmod +x ./get_data.sh
    ./get_data.sh
    chmod -R 755 data/ models/
    ```

### Option 1: Local Development (Docker Compose)
1.  **Spin up services**: `make build_up`
2.  **Network Interface**: Ensure `scripts/sniffer/sniffer.py` is set to `iface="eth0"`.
3.  **Simulate Traffic**:
    > **Note**: Match the network name to your project prefix (default: `nids_nids-internal`).
    ```bash
    docker run --rm -v $(pwd)/data:/data --network nids_nids-internal nicolaka/netshoot /bin/sh -c "apk add tcpreplay && tcpreplay --intf1=eth0 --pps=5000 /data/Mirai_pcap.pcap"
    ```

### Option 2: Cloud-Native Simulation (Kubernetes / KinD)
1.  **Full Automated Deployment**: `make run-deployment`
2.  **Traffic Simulation**: 
    > **Note**: Ensure `sniffer.py` is set to `iface="eth1"` for K8s hostNetwork capture.
    ```bash
    make simulate-attack
    make logs-app
    ```

---

## Roadmap (Next Steps)
* **Observability**: Resolve HTTP/TCP health check failures and implement deep Liveness/Readiness probes based on Redis consumer lag.
* **CI/CD**: Build GitHub Actions for automated ONNX linting and multi-arch Docker builds.
* **IaC Migration**: Transition from raw YAML to **Helm Charts** for modular environment management.
* **Self-Healing**: Implement Horizontal Pod Autoscaler (HPA) to scale inference workers based on stream depth.