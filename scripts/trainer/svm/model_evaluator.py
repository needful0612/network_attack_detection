import numpy as np
from sklearn.metrics import confusion_matrix

def get_ensemble_weight(
    clf
):
    ensemble_weights = []
    for calibrated_model in clf.calibrated_classifiers_:
        svc_model = calibrated_model.estimator 
        ensemble_weights.append(svc_model.coef_[0])
    return ensemble_weights

def calculate_metrics(
    name, 
    probs,
    y,
    attack_threshold
):
    preds = (probs > attack_threshold).astype(int)
    cm = confusion_matrix(y, preds)
    fn = cm[1, 0] if cm.shape == (2, 2) else 0
    uncertain_rate = ((probs > 0.2) & (probs < 0.8)).mean() * 100
    return {
        "Model": name,
        "Accuracy": (y == preds).mean(),
        "Uncertainty Rate (%)": uncertain_rate,
        "Missed Attacks (FN)": fn
    }

def evaluate_svm(
    clf,
    X_val,
    y_val,
    attack_threshold
):
    probs = clf.predict_proba(X_val)[:, 1]
    metrics = calculate_metrics(
        f"SVM (C={1.0})", 
        probs, 
        y_val,
        attack_threshold
    )
    return metrics

def get_avg_weight(clf):
    ensemble_weights = get_ensemble_weight(clf)
    avg_weights = np.mean(ensemble_weights, axis=0).tolist()
    
    return avg_weights
    