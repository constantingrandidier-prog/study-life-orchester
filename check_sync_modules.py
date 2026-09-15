import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/schedule/anki/local-sync?deck_scope=curriculum', data=b'', method='POST')
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode())
print('Modules found:')
for m in data.get('modules', []):
    print(f"  {m['name']}: {m['cards']} cards, {m['reviews']} reviews")
