#!/usr/bin/env python3
"""Test Bapica : 50 comptes × 10 scénarios = 500 tests"""

import json, time, random, os
from datetime import datetime

SUPABASE_URL = "https://xlivseiybtkwkekyhqwg.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Profils variés
SECTORS = ["ecommerce", "services", "sante", "formation", "saas", "immobilier", "restauration", "logistique", "finance", "btp"]
SIZES = ["TPE solo", "TPE 2-5", "PME 5-20", "PME 20-50"]
STAGES = ["early", "growth", "mature", "scaleup"]

def generate_accounts(n=50):
    accounts = []
    for i in range(n):
        sector = SECTORS[i % len(SECTORS)]
        acc = {
            "email": f"test.reasoning.{i}@bapica-test.com",
            "password": "Test1234!",
            "profile": {
                "companyName": f"TestCo {i}",
                "activity": sector,
                "companySize": SIZES[i % len(SIZES)],
                "employeeCount": random.choice([1, 2, 3, 5, 8, 12, 25, 40]),
                "stage": STAGES[i % len(STAGES)],
                "adminTasks": random.sample(["facturation", "prospection", "support client", "comptabilité", "recrutement", "contenu"], 3),
                "objectives": random.sample(["automatiser", "croître", "digitaliser", "déléguer", "recruter"], 2),
            }
        }
        accounts.append(acc)
    return accounts

SCENARIOS = [
    # Analyse profonde
    {"endpoint": "/api/deep-analysis", "method": "GET", "desc": "deep_analysis"},
    {"endpoint": "/api/reason?q=Comment+scaler+mon+activité", "method": "GET", "desc": "reason_scaling"},
    {"endpoint": "/api/reason?q=Quels+sont+mes+plus+gros+risques", "method": "GET", "desc": "reason_risks"},
    {"endpoint": "/api/reason?q=Quelle+stratégie+pour+doubler+mon+CA", "method": "GET", "desc": "reason_strategy"},
    
    # Intelligence marché (GET, pas de body)
    {"endpoint": "/api/market-intelligence?sector={sector}&type=all", "method": "GET", "body": None, "desc": "market_intel"},
    
    # Chat agents (IDs corrects)
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "general", "message": "Bonjour, peux-tu analyser mon entreprise ?"}, "desc": "chat_general_analyse"},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "general", "message": "Quels agents me recommandes-tu ?"}, "desc": "chat_general_recommend"},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "prospector", "message": "Comment prospecter plus efficacement ?"}, "desc": "chat_prospector"},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "scaling", "message": "Mon entreprise stagne à 30k€/mois"}, "desc": "chat_scaling"},
    {"endpoint": "/api/demo-chat", "method": "POST", "body": {"agentId": "support", "message": "Comment réduire le temps de réponse client ?"}, "desc": "chat_support"},
]

print("=" * 60)
print("TEST BAPICA — 50 comptes × 10 scénarios")
print("=" * 60)

accounts = generate_accounts(50)
results = []
errors = []

for i, account in enumerate(accounts):
    sector = account["profile"]["activity"]
    print(f"\n--- Compte {i+1}/50 : {account['email']} ({sector}) ---")
    
    for j, scenario in enumerate(SCENARIOS):
        start = time.time()
        success = False
        response_text = ""
        
        try:
            import subprocess
            
            url = f"https://bapica.com{scenario['endpoint']}"
            if "{sector}" in url:
                url = url.replace("{sector}", sector)
            
            if scenario["method"] == "GET":
                cmd = f"curl -s --max-time 30 '{url}'"
            elif scenario.get("body"):
                body = json.dumps(scenario["body"]).replace("'", "'\\''")
                cmd = f"curl -s --max-time 30 -X POST '{url}' -H 'Content-Type: application/json' -d '{body}'"
            else:
                cmd = f"curl -s --max-time 30 -X POST '{url}' -H 'Content-Type: application/json' -d '{{}}'"
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=35)
            elapsed = time.time() - start
            
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    if "error" not in data:
                        success = True
                        response_text = str(data)[:100]
                    else:
                        response_text = f"API error: {data.get('error', 'unknown')}"
                except:
                    response_text = result.stdout[:100]
                    success = len(result.stdout) > 20
            else:
                response_text = f"curl error: {result.stderr[:100]}"
                elapsed = 0
            
        except Exception as e:
            elapsed = 0
            response_text = str(e)[:100]
        
        status = "✅" if success else "❌"
        print(f"  {status} {scenario['desc']}: {elapsed:.1f}s")
        
        results.append({
            "account": i, "sector": sector, "scenario": scenario["desc"],
            "success": success, "time": round(elapsed, 1), "response": response_text
        })
        
        if not success:
            errors.append({"account": i, "scenario": scenario["desc"], "response": response_text})

# Analyse des résultats
success_count = sum(1 for r in results if r["success"])
success_rate = (success_count / len(results)) * 100 if results else 0
avg_time = sum(r["time"] for r in results if r["time"] > 0) / max(1, sum(1 for r in results if r["time"] > 0))

# Par secteur
sector_stats = {}
for r in results:
    sec = r["sector"]
    if sec not in sector_stats:
        sector_stats[sec] = {"total": 0, "success": 0, "times": []}
    sector_stats[sec]["total"] += 1
    if r["success"]:
        sector_stats[sec]["success"] += 1
    sector_stats[sec]["times"].append(r["time"])

# Par scénario
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
    "timestamp": datetime.now().isoformat(),
    "total_scenarios": len(results),
    "success_rate": round(success_rate, 1),
    "avg_response_time": round(avg_time, 1),
    "errors": len(errors),
    "by_sector": {s: {"rate": round(v["success"]/v["total"]*100, 1), "avg_time": round(sum(v["times"])/max(1,len(v["times"])), 1)} for s, v in sector_stats.items()},
    "by_scenario": {s: {"rate": round(v["success"]/v["total"]*100, 1), "avg_time": round(sum(v["times"])/max(1,len(v["times"])), 1)} for s, v in scenario_stats.items()},
}

with open("/tmp/bapica-reasoning-test.json", "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 60)
print(f"RÉSULTATS : {success_count}/{len(results)} succès ({success_rate:.1f}%)")
print(f"Temps moyen : {avg_time:.1f}s")
print(f"Erreurs : {len(errors)}")
print(f"\nRapport : /tmp/bapica-reasoning-test.json")
for s, v in sector_stats.items():
    rate = v["success"]/v["total"]*100
    avg = sum(v["times"])/max(1,len(v["times"]))
    bar = "█" * int(rate/5)
    print(f"  {s:15} {rate:5.1f}% {bar} ({avg:.1f}s)")
