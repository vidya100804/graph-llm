import requests
res = requests.post("http://localhost:5000/api/chat", json={"query": "in answer there are 86 deleiveries How many deliveries are there?"})
print(res.json())
