# Tiered NIDS: Waterfall Architecture

This project implements the first layer of a cascaded Network Intrusion Detection System (NIDS). It utilizes a calibrated Linear Support Vector Machine (SVM) to provide high-speed filtering of network traffic, specifically targeting botnet signatures while identifying "uncertain" traffic for deep investigation.

## System Architecture

The system is designed as a modular pipeline using Docker microservices to separate the training lifecycle from the inference stage.

1.  **Trainer Service**: Handles automated data acquisition, feature engineering, and ONNX model exportation.
2.  **Inference Server**: A FastAPI application serving the model via ONNX Runtime for low-latency triage.



## Technical Specifications

### Feature Engineering & Preprocessing
Our initial experiments with XGBoost and LGBM showed near-perfect overfitting (AUC 1.0) or poor recall, suggesting the raw dataset lacked stable signals. To resolve this, a custom "Precision-Safe" pipeline was implemented:

1. **The "Clock Purge"**: Dropped unstable features with low lambda windows (80, 77, 74, 71, and 68) where signal variance was below 0.01.
2. **Burst Ratios**: Replaced raw weights with logarithmic differences to capture traffic momentum: 
   $$log1p(fast\_stream) - log1p(slow\_stream)$$
3. **Symmetric Log Transform**: Applied to handle long-tailed distributions while preserving sign: 
   $$sign(x) \cdot \log(1 + |x|)$$
4. **Robust Scaling**: Scaled features using Median and IQR. *Note: Scaling is performed before clipping to ensure global distribution is preserved.*
5. **Hard Clipping**: Feature values are clipped to $[-10, 10]$ to prevent outlier-driven instability in the SVM hyperplane.

### Model Selection & Performance
* **Algorithm**: Linear Support Vector Classifier (LinearSVC). 
  * *Reasoning*: While tree-based models (XGBoost) struggled with the linear separation in this dataset, SVM with L2 regularization provided a more stable decision boundary for network triage.
* **Probability Calibration**: Uses **Platt Scaling** (Sigmoid calibration) to transform SVM decision margins into usable probability scores.
* **Format**: Exported to **ONNX** for high-performance, CPU-bound inference in production.

### Triage Logic (Decision Uncertainty)
The system operates as a "Waterfall" filter. Instead of a hard binary choice, we implement a three-tier classification:
* **Benign**: Probability $< 0.2$.
* **Attack**: Probability $> 0.8$.
* **Uncertain (Grey Zone)**: Probability between $0.2$ and $0.8$. 

*Traffic in the "Uncertain" zone is logged for Layer 2 Deep Packet Inspection (DPI) rather than being dropped immediately, reducing False Negatives.*

## Project Structure

    ```
    .
    ├── Dockerfile              # Unified multi-stage build configuration
    ├── docker-compose.yml      # Service orchestration and volume management
    ├── get_data.sh             # Script for dataset acquisition (Mirai/OS Scan)
    ├── requirements.txt        # Python dependency manifest
    ├── data/                   # Shared Volume: Raw CSV datasets
    ├── models/                 # Shared Volume: Exported ONNX model and config
    ├── notebooks               
        └── notebook.ipynb      # EDA/model evaluation/fintetune
    └── scripts/
        ├── trainer/
        │   └── train.py        # Polars-based training and calibration pipeline
        └── svm/
            ├── predictor.py    # Preprocessing and inference logic class
            └── serve.py        # FastAPI server with model-wait retry logic
    ```
Do note that models and data folder will only appear after you run the **get_data.sh** and **train.py**

## Deployment Guide

### before starting
If you run into any **permission denied** scenario,like models and data folder try:
    ```
    sudo chmod -R 777 models data
    ```
or
    ```
    sudo chown -R $USER:$USER models data
    ```
### get the data and start the training
Below is the step to test the train scripts and the model served.   
You can skip to the build and run section if you wanna cold start everything.   
**Do note that the docker would block the downloading and training message**     
**It might take some time(several minutes) before it finish due to the sheer amount of the dataset.**    

1. assign the execute permission and download the datasets
    ```
    chmod +x ./get_data.sh
    ./get_data.sh
    ```
2.  run the training process(this might take awhile too)
    ```
    python ./scripts/trainer/train.py
    ```
3. try load the model
    ```
    python ./scripts/svm/predictor.py
    ```
4. serve through fastapi and  run the testing script
    ```
    python ./scripts/svm/serve.py
    python ./scripts/client_test.py
    ```
### building with docker
1. **build and run**:
    ```
    docker-compose up --build
    ```
Because the **data downloading** and **model training** take times, this process might take awhile if you didn't dry run the **get_data.sh** and **train.py**.

2.  test the result **(remember to stop the script form above,they share the same port)**
    ```
    python ./scripts/client_test.py
    ```

### Cloud Deployment

To deploy this to a cloud environment like **Google Cloud Run**:

1. **Build locally:** Run the trainer to ensure `models/svm_bot_filter.onnx` is generated.
2. **Push to Artifact Registry:** Tag and push the Docker image to Google Artifact Registry:
   ```bash
   docker tag nids-service gcr.io/[PROJECT-ID]/nids-service
   docker push gcr.io/[PROJECT-ID]/nids-service
   ```
3. **Deploy:**Run the deployment command to spin up the service:   
    ```
    gcloud run deploy nids-service --image gcr.io/[PROJECT-ID]/nids-service --platform managed
    ```
    The API would then be accessible via a public Google Cloud URL, allowing integration with network monitoring dashboards or security orchestration (SOAR) tools.

## Future Roadmap

The current implementation serves as **Layer 1 (The Triage Filter)**. The planned expansion involves a cascaded "Waterfall" strategy to increase detection depth without sacrificing real-time performance.

## Planned System Architecture

The system is built via Docker as three distinct microservices to balance speed with detection depth.

* **Container 0 (Sensor & Ambassador)**: The main dispatcher. Performs live packet sniffing (Scapy) or PCAP ingestion and extracts 115-dimensional features via Kitsune's **netStat** logic. It retrieves probabilities from C1 and decides whether to dispatch to C2.
* **Container 1 (Fast Filter)**: A calibrated **LinearSVC** (SVM) running on **ONNX Runtime**. It performs fast triage on known attack signatures (Mirai, OS Scan).
* **Container 2 (Deep Inspector)**: An unsupervised **KitNET Autoencoder Ensemble**. It processes "Grey Zone" traffic that the SVM cannot confidently classify, providing deep anomaly scoring for potential zero-day threats.


## Planned Architecture: Layer 2 (KitNET Ensemble)

The later stage of the waterfall utilizes the **KitNET** algorithm to catch potential attack that svm miss.

### KitNET Logic (Unsupervised)
1.  **Feature Mapping**: The 115 features are mapped into subsets using hierarchical clustering.
2.  **Ensemble Layer**: A collection of "micro" autoencoders trained on normal traffic. Each calculates a **Root Mean Square Error (RMSE)**.
3.  **Output Layer**: A final autoencoder summarizes the RMSEs into an overall anomaly score.

## Personal Reflections & Project Status

This project was a deep dive into the "trench work" of Machine Learning—where the math meets the messy reality of network packets. While I started with high-reaching architectural goals, the reality of setting up a tiered multi-container system proved to be a significant (but rewarding) challenge.

### What I Learned
* **Simple is often better**: I spent a lot of time trying to make XGBoost and LGBM work, only to realize they were overfitting or failing on basic Benign traffic. Moving to a calibrated LinearSVC was a "lightbulb moment"—it reminded me that model complexity shouldn't come before understanding your feature distributions.
* **Preprocessing is the real MVP**: Building the "Precision-Safe" pipeline (Symmetric Log + Robust Scaling) taught me more about production ML than the actual training did. Ensuring that my local Python environment and the Docker ONNX runtime handled math the exact same way was a massive lesson in consistency.
* **The "Waterfall" is hard**: Orchestrating the hand-off between C0 (Sensor), C1 (SVM), and C2 (KitNET) was the most difficult part. Dealing with container synchronization and shared volumes was a steep learning curve that shifted my focus from just "writing code" to "system design."

### Current State & What’s Next
The project has officially wrapped up **Phase 1**. 

I’ve successfully built and containerized the core SVM filter and the data pipeline. While I didn't get the full KitNET "Grey Zone" hand-off working perfectly across all containers before my personal deadline, I’m really proud of the Tier 1 stability. 

 I’m leaving the architecture ready for a "Phase 2" update. It was a blast messing with the math, and even though it's not the "final-final" vision yet, it’s a functional proof-of-concept that I’m happy to stand behind.