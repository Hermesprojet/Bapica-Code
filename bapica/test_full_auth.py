#!/usr/bin/env python3
"""Test Bapica complet avec auth — 50 comptes × 10 scénarios = 500 tests"""

import subprocess, json, time, random, os

SUPABASE_URL = "https://xlivseiybtkwkekyhqwg.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    # Essayer de le récupérer
    result = subprocess.run("grep SUPABASE_SERVICE_ROLE_KEY /root/bapica/bapica/.env.local | cut -d= -f2", shell=True, capture_output=True, text=True)
    SUPABASE_KEY = result.stdout.strip()

if not SUPABASE_KEY:
    print("❌ SUPABASE_SERVICE_ROLE_KEY non trouvée")
    exit(1)

SECTORS = ["ecommerce", "services", "sante", "formation", "saas", "immobilier", "restauration", "logistique", "finance", "btp"]
SIZES = ["TPE solo", "TPE 2-5", "PME 5-20", "PME 20-50"]
STAGES = ["early", "growth", "mature", "scaleup"]

def create_account(email, password, profile):
    """Créer un compte via Supabase Admin API"""
    cmd = f"""curl -s --max-time 10 '{SUPABASE_URL}/auth/v1/admin/users' \
      -H 'apikey: {SUPABASE_KEY}' \
      -H 'Authorization: Bearer {SUPABASE_KEY}' \
      -H 'Content-Type: application/json' \
      -d '{{"email":"{email}","password":"{password}","email_confirm":true,"user_metadata":{{"onboarding_data":{json.dumps(profile)}}}}}'"""
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    try:
        return json.loads(result.stdout)
    except:
        return None

def sign_in(email, password):
    """Se connecter et obtenir le cookie de session"""
    cmd = f"""curl -s --max-time 10 '{SUPABASE_URL}/auth/v1/token?grant_type=password' \
      -H 'apikey: {SUPABASE_KEY}' \
      -H 'Content-Type: application/json' \
      -d '{{"email":"{email}","password":"{password}"}}' \
      -c /tmp/supabase-cookies-{email.replace('@','_').replace('.','_')}.txt"""
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    try:
        data = json.loads(result.stdout)
        return data.get("access_token"), f"/tmp/supabase-cookies-{email.replace('@','_').replace('.','_')}.txt"
    except:
        return None, None

SCENARIOS = [
    {"endpoint": "/api/deep-analysis", "method": "GET", "desc": "deep_analysis", "needsAuth": True},
    {"endpoint": "/api/reason?q=Comment+scaler+mon+activité", "method": "GET", "desc": "reason_scaling", "needsAuth": True},
    {"endpoint": "/api/reason?q=Quels+sont+mes+plus+gros+risques", "method": "GET", "desc": "reason_risks", "needsAuth": True},
    {"endpoint": "/api/reason?q=Quelle+stratégie+pour+doubler+mon+CA", "method": "GET", "desc": "reason_strategy", "needsAuth": True},
    {"endpoint": "/api/market-intelligence?sector={sector}&type=all", "method": "GET", "desc": "market_intel", "needsAuth": False},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "general", "message": "Bonjour, analyse mon entreprise"}, "desc": "chat_general_analyse", "needsAuth": False},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "general", "message": "Quels agents me recommandes-tu ?"}, "desc": "chat_general_recommend", "needsAuth": False},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "prospector", "message": "Comment prospecter plus efficacement ?"}, "desc": "chat_prospector", "needsAuth": False},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "scaling", "message": "Mon entreprise stagne à 30k€/mois"}, "desc": "chat_scaling", "needsAuth": False},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "support", "message": "Comment réduire le temps de réponse client ?"}, "desc": "chat_support", "needsAuth": False},
]

print("=" * 60)
print("TEST BAPICA COMPLET AVEC AUTH")
print("=" * 60)

results = []
errors = []
tokens = {}  # Cache des tokens

for i in range(50):
    sector = SECTORS[i % 10]
    email = f"test.full.{i}@bapica-test.com"
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
    
    # Créer le compte
    print(f"\n--- Compte {i+1}/50 : {email} ({sector}) ---")
    user = create_account(email, password, profile)
    
    if not user or "id" not in user:
        print(f"  ⚠️ Compte déjà existant, on tente la connexion...")
    
    # Se connecter
    token, cookie_file = sign_in(email, password)
    if not token:
        print(f"  ❌ Échec connexion, skip")
        continue
    
    tokens[email] = token
    
    for j, scenario in enumerate(SCENARIOS):
        start = time.time()
        success = False
        response_text = ""
        
        try:
            url = f"https://bapica.com{scenario['endpoint']}".replace("{sector}", sector)
            
            # Utiliser le cookie de session Supabase
            cookie_opt = f"-b {cookie_file}" if scenario.get("needsAuth") else ""
            
            if scenario["method"] == "GET":
                cmd = f"curl -s --max-time 30 {cookie_opt} '{url}'"
            elif scenario.get("body"):
                body = json.dumps(scenario["body"]).replace("'", "'\\''")
                cmd = f"curl -s --max-time 30 -X POST {cookie_opt} '{url}' -H 'Content-Type: application/json' -d '{body}'"
            else:
                cmd = f"curl -s --max-time 30 -X POST {cookie_opt} '{url}' -H 'Content-Type: application/json' -d '{{}}'"
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=35)
            elapsed = time.time() - start
            
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    if "error" not in data or "Non authentifié" not in str(data.get("error", "")):
                        success = True
                        # Compter la richesse de la réponse
                        resp_str = json.dumps(data)
                        response_text = f"{len(resp_str)} chars"
                    else:
                        response_text = f"Auth error: {data.get('error', 'unknown')}"
                except:
                    response_text = result.stdout[:80]
                    success = len(result.stdout) > 50
            else:
                response_text = f"curl error"
                elapsed = 0
            
        except Exception as e:
            elapsed = 0
            response_text = str(e)[:80]
        
        status = "✅" if success else "❌"
        print(f"  {status} {scenario['desc']:25} {elapsed:.1f}s {response_text}")
        
        results.append({
            "account": i, "sector": sector, "scenario": scenario["desc"],
            "success": success, "time": round(elapsed, 1), "response": response_text
        })
        
        if not success:
            errors.append({"account": i, "scenario": scenario["desc"], "response": response_text})

# Analyse
success_count = sum(1 for r in results if r["success"])
success_rate = (success_count / len(results)) * 100 if results else 0
avg_time = sum(r["time"] for r in results if r["time"] > 0) / max(1, sum(1 for r in results if r["time"] > 0))

scenario_stats = {}
for r in results:
    sc = r["scenario"]
    if sc not in scenario_stats:
        scenario_stats[sc] = {"total": 0, "success": 0, "times": []}
    scenario_stats[sc]["total"] += 1
    if r["success"]:
        scenario_stats[sc]["success"] += 1
    scenario_stats[sc]["times"].append(r["time"])

# Sauvegarder
report = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "total_scenarios": len(results),
    "success_rate": round(success_rate, 1),
    "avg_response_time": round(avg_time, 1),
    "errors": len(errors),
    "by_scenario": {s: {"rate": round(v["success"]/v["total"]*100, 1), "avg_time": round(sum(v["times"])/max(1,len(v["times"])), 1)} for s, v in scenario_stats.items()},
}

with open("/tmp/bapica-full-test.json", "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 60)
print(f"RÉSULTATS COMPLETS : {success_count}/{len(results)} succès ({success_rate:.1f}%)")
print(f"Temps moyen : {avg_time:.1f}s")
print(f"Erreurs : {len(errors)}")

for s, v in scenario_stats.items():
    rate = v["success"]/v["total"]*100
    avg = sum(v["times"])/max(1,len(v["times"]))
    bar = "█" * int(rate/5)
    print(f"  {s:25} {rate:5.1f}% {bar} ({avg:.1f}s)")

print(f"\nRapport : /tmp/bapica-full-test.json")
