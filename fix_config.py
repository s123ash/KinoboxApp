import re

api_id = 0
api_hash = ""
try:
    with open("app/src/main/python/config.py", "r", encoding="utf-8") as f:
        txt = f.read()
    m_id = re.search(r"API_ID\s*=\s*(\d+)", txt)
    m_hash = re.search(r"API_HASH\s*=\s*['\"]([^'\"]+)['\"]", txt)
    if m_id: api_id = int(m_id.group(1))
    if m_hash: api_hash = m_hash.group(1)
except Exception as e:
    print(f"Error reading config: {e}")

with open("app/src/main/python/tg_creds.py", "w", encoding="utf-8") as f:
    f.write(f"API_ID = {api_id}\nAPI_HASH = '{api_hash}'\nADMIN_ID = 846768993\n")
print(f"✓ tg_creds.py создан: API_ID={api_id}, ADMIN_ID=846768993")
