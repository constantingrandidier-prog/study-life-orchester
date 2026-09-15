import urllib.request, json

HOOK_URL = 'https://api.render.com/deploy/srv-dakfgb2d0e5s73dpuk50?key=lkHIKKYGqoY'

def trigger_deploy():
    req = urllib.request.Request(HOOK_URL, method='POST')
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print('Deploy triggered successfully:', res)
        return res

if __name__ == '__main__':
    trigger_deploy()
