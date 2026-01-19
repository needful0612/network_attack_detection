import requests

mock_data = {f"column_{i}": 1.5 for i in range(1, 116)}

response = requests.post("http://localhost:8000/predict", json=mock_data)
print(response.json())