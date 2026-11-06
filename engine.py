"""Lõi mô hình: huấn luyện, lưu, và dự đoán. Không phụ thuộc FastAPI."""
import os
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

import joblib
import numpy as np
import sklearn
from sklearn import datasets
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

VERSION = 2
ARTIFACT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts.joblib")
SPECIES = ["setosa", "versicolor", "virginica"]
FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
DEFAULT_MODEL = "svm_linear"

MODEL_SPECS = {
    "svm_linear": (
        "SVM tuyến tính",
        "Mô hình trong bài giảng: vẽ ranh giới thẳng giữa các loài.",
        lambda: make_pipeline(StandardScaler(), SVC(kernel="linear", probability=True, random_state=42)),
    ),
    "svm_rbf": (
        "SVM phi tuyến",
        "Cùng họ SVM nhưng ranh giới cong, hợp với dữ liệu chồng lấn.",
        lambda: make_pipeline(StandardScaler(), SVC(kernel="rbf", probability=True, random_state=42)),
    ),
    "logistic": (
        "Hồi quy logistic",
        "Đơn giản và nhanh, cho xác suất tự nhiên.",
        lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
    ),
    "knn": (
        "K láng giềng gần nhất",
        "Nhìn 5 mẫu giống nhất và để chúng bỏ phiếu.",
        lambda: make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5)),
    ),
    "forest": (
        "Rừng ngẫu nhiên",
        "Nhiều cây quyết định bỏ phiếu, cho biết số đo nào quan trọng.",
        lambda: RandomForestClassifier(n_estimators=200, random_state=42),
    ),
}

_CACHE = None


def build():
    iris = datasets.load_iris()
    X, y = iris.data, iris.target
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    models, info, importance = {}, [], None
    for mid, (name, desc, factory) in MODEL_SPECS.items():
        scores = cross_val_score(factory(), X, y, cv=cv)
        pred = cross_val_predict(factory(), X, y, cv=cv)
        model = factory().fit(X, y)
        models[mid] = model
        if mid == "forest":
            importance = [round(float(v), 4) for v in model.feature_importances_]
        info.append({
            "id": mid, "name": name, "desc": desc,
            "cv_mean": round(float(scores.mean()), 4),
            "cv_std": round(float(scores.std()), 4),
            "confusion": confusion_matrix(y, pred).tolist(),
        })

    pca = PCA(n_components=2).fit(X)
    xy = pca.transform(X)
    meta = {
        "species": SPECIES,
        "features": FEATURES,
        "default_model": DEFAULT_MODEL,
        "models": info,
        "importance": importance,
        "ranges": {f: [float(X[:, i].min()), float(X[:, i].max())] for i, f in enumerate(FEATURES)},
        "means": {s: [round(float(v), 2) for v in X[y == i].mean(axis=0)] for i, s in enumerate(SPECIES)},
        "samples": [
            {"v": [float(v) for v in X[i]], "s": int(y[i]), "p": [round(float(xy[i, 0]), 3), round(float(xy[i, 1]), 3)]}
            for i in range(len(X))
        ],
        "explained": round(float(pca.explained_variance_ratio_.sum()), 4),
        "bounds": [float(xy[:, 0].min()), float(xy[:, 0].max()), float(xy[:, 1].min()), float(xy[:, 1].max())],
    }
    return {"version": VERSION, "sklearn": sklearn.__version__, "models": models, "pca": pca, "meta": meta}


def build_and_save():
    art = build()
    joblib.dump(art, ARTIFACT)
    return art


def load():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    art = None
    if os.path.exists(ARTIFACT):
        try:
            art = joblib.load(ARTIFACT)
            if art.get("version") != VERSION or art.get("sklearn") != sklearn.__version__:
                art = None
        except Exception:
            art = None
    if art is None:
        art = build()
        try:
            joblib.dump(art, ARTIFACT)
        except OSError:
            pass
    _CACHE = art
    return art


def info():
    return load()["meta"]


def has_model(model_id):
    return model_id in MODEL_SPECS


def predict_rows(rows, model_id=DEFAULT_MODEL):
    art = load()
    X = np.asarray(rows, dtype=float)
    P = art["models"][model_id].predict_proba(X)
    xy = art["pca"].transform(X)
    out = []
    for p, pt in zip(P, xy):
        i = int(p.argmax())
        out.append({
            "class_id": i,
            "prediction": SPECIES[i],
            "confidence": round(float(p[i]), 4),
            "probabilities": {s: round(float(v), 4) for s, v in zip(SPECIES, p)},
            "pca": [round(float(pt[0]), 3), round(float(pt[1]), 3)],
        })
    return out


def predict_one(values, model_id=DEFAULT_MODEL):
    base = predict_rows([values], model_id)[0]
    votes = {}
    for mid in MODEL_SPECS:
        r = predict_rows([values], mid)[0]
        votes[mid] = {"prediction": r["prediction"], "confidence": r["confidence"]}
    agree = sum(1 for v in votes.values() if v["prediction"] == base["prediction"])
    base["model"] = model_id
    base["agreement"] = {"agree": agree, "total": len(votes), "models": votes}
    return base


_REGIONS = {}


def regions(model_id, nx=120, ny=80):
    if model_id in _REGIONS:
        return _REGIONS[model_id]
    art = load()
    x0, x1, y0, y1 = art["meta"]["bounds"]
    px, py = (x1 - x0) * 0.12, (y1 - y0) * 0.18
    x0, x1, y0, y1 = x0 - px, x1 + px, y0 - py, y1 + py
    gx = np.linspace(x0, x1, nx)
    gy = np.linspace(y0, y1, ny)
    mesh = np.array([[a, b] for b in gy for a in gx])
    pred = art["models"][model_id].predict(art["pca"].inverse_transform(mesh))
    out = {"nx": nx, "ny": ny, "bounds": [float(x0), float(x1), float(y0), float(y1)],
           "cells": "".join(str(int(v)) for v in pred)}
    _REGIONS[model_id] = out
    return out
