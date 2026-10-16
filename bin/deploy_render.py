import urllib.request, json

HOOK_URL = 'https://api.render.com/deploy/srv-dakfgb2d0e5s73dpuk50?key=lkHIKKYGqoY'

def trigger_deploy():
    req = urllib.request.Request(HOOK_URL, method='POST')
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode('utf-8')
        try:
            res = json.loads(raw) if raw else {"status": resp.status}
        except Exception:
            res = {"status": resp.status, "response": raw}
        print('Deploy triggered successfully:', res)
        return res

if __name__ == '__main__':
    trigger_deploy()
