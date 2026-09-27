import re
import httpx

r = httpx.get("https://www.psit.ac.in/main.js", timeout=20)
text = r.text

matches = [m.start() for m in re.finditer(r"Angular/PrintIDCard", text)]
for idx in matches:
    start = max(0, idx - 1000)
    end = min(len(text), idx + 200)
    print("--- CONTEXT ---")
    print(text[start:end])
