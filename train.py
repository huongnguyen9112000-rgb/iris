import pandas as pd
from sklearn.svm import SVC
import joblib

# Đọc dữ liệu từ file Iris.csv
df = pd.read_csv("Iris.csv")

# Thứ tự cột phải khớp với app.py:
# sepal_length, sepal_width, petal_length, petal_width
features = ["SepalLengthCm", "SepalWidthCm", "PetalLengthCm", "PetalWidthCm"]
X = df[features].values

# Mã hóa nhãn khớp với dict species trong app.py: 0=setosa, 1=versicolor, 2=virginica
label_map = {
    "Iris-setosa": 0,
    "Iris-versicolor": 1,
    "Iris-virginica": 2,
}
y = df["Species"].map(label_map).values

model = SVC(kernel="linear")
model.fit(X, y)

print("Số mẫu:", len(df))
print("Độ chính xác trên tập huấn luyện:", round(model.score(X, y), 4))

joblib.dump(model, "svm_model.pkl")
print("Model saved!")
