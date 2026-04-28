import requests

url = "http://192.168.18.126:8080/api/tc-search"

payload = {
    "token": "9f2b1e3a7c4d5f6a8b0c1d2e3f4a5b6c",
    "name": "GSO1",
    "phone": "",
    "phones": [],
    "email": "",
    "tag": ""
}

response = requests.post(url, json=payload)
data = response.json()

results = data.get("results", [])

for r in results:
    print(f"Name  : {r['NAME']}")
    print(f"Phone : {r['PHONE']}")
    print(f"Email : {r['EMAIL']}")
    print(f"Date  : {r['ASONDATE']}")
    print("-" * 40)