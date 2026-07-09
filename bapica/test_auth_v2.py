#!/usr/bin/env python3
"""Test Bapica complet — 50 comptes × 10 scénarios avec cookie auth"""

import subprocess, json, time, random, os, base64

SUPABASE_URL = "https://xlivseiybtkwkekyhqwg.supabase.co"
result = subprocess.run("grep SUPABASE_SERVICE_ROLE_KEY /root/bapica/bapica/.env.local | cut -d= -f2", shell=True, capture_output=True, text=True)
SUPABASE_KEY = result.stdout.strip()
PROJECT_REF = "xlivseiybtkwkekyhqwg"

SECTORS = ["ecommerce", "services", "sante", "formation", "saas", "immobilier", "restauration", "logistique", "finance", "btp"]
SIZES = ["TPE solo", "TPE 2-5", "PME 5-20", "PME 20-50"]
STAGES = ["early", "growth", "mature", "scaleup"]

def create_and_login(email, password, profile):
    """Créer compte + login + extraire cookie de session"""
    # Créer le compte
    cmd = f"""curl -s --max-time 10 '{SUPABASE_URL}/auth/v1/admin/users' \
      -H 'apikey: {SUPABASE_KEY}' \
      -H 'Authorization: Bearer {SUPABASE_KEY}' \
      -H 'Content-Type: application/json' \
      -d '{{"email":"{email}","password":"{password}","email_confirm":true,"user_metadata":{{"onboarding_data":{json.dumps(profile)}}}}}'"""
    subprocess.run(cmd, shell=True, capture_output=True, timeout=15)
    
    # Login et récupérer la session
    cmd = f"""curl -s --max-time 10 '{SUPABASE_URL}/auth/v1/token?grant_type=password' \
      -H 'apikey: {SUPABASE_KEY}' \
      -H 'Content-Type: application/json' \
      -d '{{"email":"{email}","password":"{password}"}}'"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    
    try:
        data = json.loads(result.stdout)
        at = data.get("access_token", "")
        rt = data.get("refresh_token", "")
        
        # Construire le cookie de session Supabase
        session = json.dumps({"access_token": at, "refresh_token": rt, "expires_at": int(time.time()) + 3600})
        cookie_value = base64.b64encode(session.encode()).decode()
        cookie = f"sb-{PROJECT_REF}-auth-token={cookie_value}"
        
        return cookie
    except:
        return None

SCENARIOS = [
    ("/api/deep-analysis", "GET", "deep_analysis", True),
    ("/api/reason?q=Comment+scaler+mon+activité", "GET", "reason_scaling", True),
    ("/api/reason?q=Quels+sont+mes+plus+gros+risques", "GET", "reason_risks", True),
    ("/api/reason?q=Quelle+stratégie+pour+doubler+mon+CA", "GET", "reason_strategy", True),
    ("/api/market-intelligence?sector={sector}&type=all", "GET", "market_intel", False),
]

CHAT_SCENARIOS = [
    ("general", "Bonjour, analyse mon entreprise", "chat_general_analyse"),
    ("general", "Quels agents me recommandes-tu ?", "chat_general_recommend"),
    ("prospector", "Comment prospecter plus efficacement ?", "chat_prospector"),
    ("scaling", "Mon entreprise stagne à 30k€/mois", "chat_scaling"),
    ("support", "Comment réduire le temps de réponse client ?", "chat_support"),
]

print("=" * 60)
print("TEST BAPICA COMPLET — 50 comptes × 10 scénarios")
print("=" * 60)

results = []
errors = []

for i in range(50):
    sector = SECTORS[i % 10]
    email = f"test-auth.{i}@bapica-test.com"
    password = "Test1234!"
    
    profile = {
        "companyName": f"TestCo {i}",
        "activity": sector,
        "companySize": SIZES[i % 4],
        "employeeCount": random.choice([1, 2, 3, 5, 8, 12, 25, 40]),
        "stage": STAGES[i % 4],
        "adminTasks": random.sample(["facturation", "prospection", "support client", "comptabilité", "recrutement", "contenu"], 3),
        "objectives": random.sample(["automatiser", "croître", "digitaliser", "déléguer", "recruter"], 2),
    }
    
    print(f"\n--- Compte {i+1}/50 : {email} ({sector}) ---")
    cookie = create_and_login(email, password, profile)
    
    if not cookie:
        print(f"  ❌ Échec login")
        continue
    
    # Test endpoints API
    for endpoint, method, desc, needsAuth in SCENARIOS:
        start = time.time()
        success = False
        
        try:
            url = f"https://bapica.com{endpoint}".replace("{sector}", sector)
            cookie_opt = f"--cookie '{cookie}'" if needsAuth else ""
            
            cmd = f"curl -s --max-time 30 {cookie_opt} '{url}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=35)
            elapsed = time.time() - start
            
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    if "error" not in data or ("Non authentifié" not in str(data.get("error","")) and "JWT" not in str(data.get("error",""))):
                        success = True
                        resp = f"{len(json.dumps(data))}c"
                    else:
                        resp = data.get("error", "?")[:50]
                except:
                    resp = result.stdout[:60]
                    success = len(result.stdout) > 100
            else:
                resp = "empty"
        except Exception as e:
            elapsed = 0
            resp = str(e)[:50]
        
        status = "✅" if success else "❌"
        print(f"  {status} {desc:25} {elapsed:.1f}s {resp}")
        results.append((i, sector, desc, success, elapsed))

    # Test chat agents (public)
    for agent, msg, desc in CHAT_SCENARIOS:
        start = time.time()
        success = False
        
        try:
            body = json.dumps({"agentId": agent, "message": msg}).replace("'", "'\\''")
            cmd = f"curl -s --max-time 30 -X POST 'https://bapica.com/api/demo-chat' -H 'Content-Type: application/json' -d '{body}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=35)
            elapsed = time.time() - start
            
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    if "response" in data:
                        success = True
                        resp = f"{len(data['response'])}c"
                    else:
                        resp = data.get("error","?")[:40]
                except:
                    resp = result.stdout[:40]
            else:
                resp = "empty"
        except Exception as e:
            elapsed = 0
            resp = str(e)[:40]
        
        status = "✅" if success else "❌"
        print(f"  {status} {desc:25} {elapsed:.1f}s {resp}")
        results.append((i, sector, desc, success, elapsed))

# Stats
success_count = sum(1 for _,_,_,s,_ in results if s)
total = len(results)
avg_time = sum(t for _,_,_,_,t in results if t > 0) / max(1, len([t for _,_,_,_,t in results if t > 0]))

scenario_stats = {}
for _, _, desc, success, t in results:
    if desc not in scenario_stats:
        scenario_stats[desc] = {"total": 0, "success": 0, "times": []}
    scenario_stats[desc]["total"] += 1
    if success:
        scenario_stats[desc]["success"] += 1
    scenario_stats[desc]["times"].append(t)

print("\n" + "=" * 60)
print(f"RÉSULTATS : {success_count}/{total} ({success_count/total*100:.1f}%)")
print(f"Temps moyen : {avg_time:.1f}s")

for desc, v in sorted(scenario_stats.items()):
    rate = v["success"] / v["total"] * 100
    avg = sum(v["times"]) / max(1, len(v["times"]))
    bar = "█" * int(rate / 5)
    print(f"  {desc:25} {v['success']:2}/{v['total']:2} {rate:5.1f}% {bar} ({avg:.1f}s)")
