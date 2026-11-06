from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import engine

BASE = Path(__file__).parent

app = FastAPI(
    title="Iris Classification API",
    description="Nhận diện loài diên vĩ bằng nhiều mô hình học máy",
    version="2.0.0",
)

engine.load()  # nạp mô hình (tự huấn luyện nếu chưa có)


class Measurements(BaseModel):
    sepal_length: float = Field(gt=0, le=20)
    sepal_width: float = Field(gt=0, le=20)
    petal_length: float = Field(gt=0, le=20)
    petal_width: float = Field(gt=0, le=20)

    def values(self):
        return [self.sepal_length, self.sepal_width, self.petal_length, self.petal_width]


class IrisInput(Measurements):
    model: str = engine.DEFAULT_MODEL


class BatchInput(BaseModel):
    rows: List[Measurements] = Field(min_length=1, max_length=2000)
    model: str = engine.DEFAULT_MODEL


def check_model(model_id: str):
    if not engine.has_model(model_id):
        raise HTTPException(status_code=404, detail=f"Không có mô hình '{model_id}'")


@app.get("/", include_in_schema=False)
def home():
    page = BASE / "index.html"
    if page.exists():
        return FileResponse(page)
    return {"message": "Iris SVM API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/info")
def info():
    return engine.info()


@app.get("/api/regions")
def regions(model: str = engine.DEFAULT_MODEL):
    check_model(model)
    return engine.regions(model)


@app.post("/predict")
def predict(data: IrisInput):
    check_model(data.model)
    return engine.predict_one(data.values(), data.model)


@app.post("/predict/batch")
def predict_batch(data: BatchInput):
    check_model(data.model)
    results = engine.predict_rows([r.values() for r in data.rows], data.model)
    return {"model": data.model, "count": len(results), "results": results}
