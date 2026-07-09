#!/usr/bin/env python3
"""Test complet — endpoints publics (curl) + fonctions internes (Node.js)"""

import subprocess, json, time, random, os

SECTORS = ["ecommerce", "services", "sante", "formation", "saas", "immobilier", "restauration", "logistique", "finance", "btp"]
SIZES = ["TPE solo", "TPE 2-5", "PME 5-20", "PME 20-50"]
STAGES = ["early", "growth", "mature", "scaleup"]

print("=" * 60)
print("TEST BAPICA — ENDPOINTS PUBLICS + FONCTIONS INTERNES")
print("=" * 60)

results = []

for i in range(50):
    sector = SECTORS[i % 10]
    profile = {
        "companyName": f"TestCo {i}",
        "activity": sector,
        "companySize": SIZES[i % 4],
        "employeeCount": random.choice([1, 2, 3, 5, 8, 12, 25, 40]),
        "stage": STAGES[i % 4],
        "adminTasks": random.sample(["facturation", "prospection", "support client", "comptabilité", "recrutement", "contenu"], 3),
        "objectives": random.sample(["automatiser", "croître", "digitaliser", "déléguer", "recruter"], 2),
    }
    
    print(f"\n--- Compte {i+1}/50 : TestCo {i} ({sector}) ---")
    
    # 1. Test curl : market_intel
    start = time.time()
    url = f"https://bapica.com/api/market-intelligence?sector={sector}&type=all"
    r = subprocess.run(f"curl -s --max-time 10 '{url}'", shell=True, capture_output=True, text=True, timeout=15)
    elapsed = time.time() - start
    try:
        d = json.loads(r.stdout)
        success = "competitiveAnalysis" in d or "trends" in d or "opportunities" in d
        print(f"  {'✅' if success else '❌'} market_intel     {elapsed:.1f}s {len(r.stdout)}c")
        results.append((i, sector, "market_intel", success, elapsed))
    except:
        print(f"  ❌ market_intel     {elapsed:.1f}s parse error")
        results.append((i, sector, "market_intel", False, elapsed))
    
    # 2. Test curl : chat agents
    chat_tests = [
        ("general", "Bonjour, analyse mon entreprise"),
        ("general", "Quels agents me recommandes-tu ?"),
        ("prospector", "Comment prospecter plus efficacement ?"),
        ("scaling", "Mon entreprise stagne à 30k€/mois"),
        ("support", "Comment réduire le temps de réponse client ?"),
    ]
    
    for agent, msg in chat_tests:
        start = time.time()
        body = json.dumps({"agentId": agent, "message": msg}).replace("'", "'\\''")
        r = subprocess.run(f"curl -s --max-time 15 -X POST 'https://bapica.com/api/demo-chat' -H 'Content-Type: application/json' -d '{body}'", shell=True, capture_output=True, text=True, timeout=20)
        elapsed = time.time() - start
        try:
            d = json.loads(r.stdout)
            success = "response" in d and len(d["response"]) > 10
            chars = len(d.get("response", ""))
            print(f"  {'✅' if success else '❌'} chat_{agent:12} {elapsed:.1f}s {chars}c")
            results.append((i, sector, f"chat_{agent}", success, elapsed))
        except:
            print(f"  ❌ chat_{agent:12} {elapsed:.1f}s error")
            results.append((i, sector, f"chat_{agent}", False, elapsed))

# Stats
success_count = sum(1 for r in results if r[3])
total = len(results)
times = [r[4] for r in results if r[4] > 0]
avg_time = sum(times) / len(times) if times else 0

# Par scénario
scenario_stats = {}
for _, _, desc, success, t in results:
    if desc not in scenario_stats:
        scenario_stats[desc] = {"total": 0, "success": 0, "times": []}
    scenario_stats[desc]["total"] += 1
    if success: scenario_stats[desc]["success"] += 1
    scenario_stats[desc]["times"].append(t)

# Par secteur
sector_stats = {}
for _, sector, _, success, t in results:
    if sector not in sector_stats:
        sector_stats[sector] = {"total": 0, "success": 0, "times": []}
    sector_stats[sector]["total"] += 1
    if success: sector_stats[sector]["success"] += 1
    sector_stats[sector]["times"].append(t)

print("\n" + "=" * 60)
print(f"RÉSULTATS : {success_count}/{total} ({success_count/total*100:.1f}%)")
print(f"Temps moyen : {avg_time:.1f}s")

# Test Node.js des fonctions internes
print("\n--- TEST FONCTIONS INTERNES (Node.js) ---")
node_test = """
const { analyzeBusinessProfile } = require('./src/lib/business-profile');
const { generateDeepAnalysis } = require('./src/lib/deep-analysis');
const { AdvancedReasoning } = require('./src/lib/reasoning-engine');

const profiles = [""" + ",".join([json.dumps({
    "companyName": f"TestCo{i}", "sector": SECTORS[i%10],
    "employeeCount": random.choice([1,2,3,5,8]),
    "stage": STAGES[i%4]
}) for i in range(10)]) + """];

let ok = 0;
profiles.forEach((p, i) => {
    try {
        const bp = analyzeBusinessProfile(p);
        const analysis = generateDeepAnalysis(bp);
        const reasoning = new AdvancedReasoning(bp);
        const systems = reasoning.reasonSystemically();
        
        if (analysis.healthScore !== undefined && analysis.hypotheses && systems.leveragePoints) {
            ok++;
        }
    } catch(e) {
        console.log('FAIL profile', i, e.message);
    }
});
console.log('OK ' + ok + '/' + profiles.length + ' profils');
console.log('Engine OK:', ok === profiles.length ? '100%' : 'FAIL');
"""

node_r = subprocess.run(f"cd /root/bapica/bapica && node -e '{node_test}'", shell=True, capture_output=True, text=True, timeout=30)
print(node_r.stdout or node_r.stderr[:200])

print("\nPar scénario :")
for desc, v in sorted(scenario_stats.items()):
    rate = v["success"]/v["total"]*100
    avg = sum(v["times"])/len(v["times"])
    bar = "█" * int(rate/5)
    print(f"  {desc:20} {v['success']:2}/{v['total']:2} {rate:5.1f}% {bar} ({avg:.1f}s)")

print("\nPar secteur :")
for sec, v in sorted(sector_stats.items()):
    rate = v["success"]/v["total"]*100
    avg = sum(v["times"])/len(v["times"])
    bar = "█" * int(rate/5)
    print(f"  {sec:15} {v['success']:2}/{v['total']:2} {rate:5.1f}% {bar} ({avg:.1f}s)")
