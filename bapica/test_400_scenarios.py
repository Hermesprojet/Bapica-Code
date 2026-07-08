#!/usr/bin/env python3
"""Test 100 profils x 4 scénarios = 400 tests"""
import json, time, random
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://bapica.com"

sectors = ["ecommerce","services","immobilier","btp","sante","formation","saas","commerce","freelance","logistique","finance","restauration"]
stages = ["early","growth","scaleup","mature"]
sizes = ["independant","TPE","PME","ETI"]

profiles = []
for i in range(100):
    profiles.append({
        "id": i+1,
        "companyName": f"TestProfil{i+1}",
        "sector": sectors[i % 12],
        "companySize": sizes[min(i//25, 3)],
        "employeeCount": random.choice([1,2,3,5,8,12,20,50]),
        "stage": stages[i % 4],
        "digitalMaturity": random.choice(["low","medium","high"]),
        "maturityScore": random.randint(20, 90),
        "priorities": random.sample(["croissance","rentabilite","automatisation","recrutement"], 2),
        "painPoints": random.sample(["factures","prospection","support","admin","marketing","legal"], 2),
        "customerAcquisition": random.sample(["phone","email","linkedin","site","whatsapp"], 2),
        "currentTools": random.sample(["crm","compta","email","slack","shopify","wordpress","hubspot","notion"], 2),
        "recommendedAgents": random.sample(["general","support","content","prospector","telephone","accounting","scaling"], 3),
        "marketPosition": random.choice(["niche","challenger","newcomer","leader"]),
        "urgencyLevel": random.choice(["low","medium","high","critical"]),
    })

scenarios = [
    "Quel est mon plus gros risque actuellement ?",
    "Quel agent IA dois-je activer en premier et pourquoi ?",
    "Combien puis-je economiser par mois avec Bapica ?",
    "Quelle est ma prochaine etape strategique ?",
]

results = []

def test_profile(profile):
    local = []
    for q in scenarios:
        try:
            import subprocess
            payload = json.dumps({"query":q,"profile":profile})
            r = subprocess.run([
                "curl","-s","--max-time","12","-X","POST",
                f"{BASE_URL}/api/business-chat",
                "-H","Content-Type: application/json",
                "-d",payload
            ], capture_output=True, text=True, timeout=15)
            data = json.loads(r.stdout)
            response = data.get("response","")
            personalized = (
                profile["sector"].lower() in response.lower() or
                any(a.lower() in response.lower() for a in profile.get("recommendedAgents",[]))
            )
            local.append({
                "profile": profile["id"], "sector": profile["sector"],
                "question": q[:40], "length": len(response),
                "personalized": personalized, "response": response[:80]
            })
        except Exception as e:
            local.append({"profile": profile["id"], "error": str(e)[:50]})
    return local

print(f"Testing {len(profiles)} profiles x {len(scenarios)} scenarios = {len(profiles)*len(scenarios)} tests...")

all_results = []
for batch_start in range(0, len(profiles), 10):
    batch = profiles[batch_start:batch_start+10]
    with ThreadPoolExecutor(max_workers=5) as exec:
        futures = [exec.submit(test_profile, p) for p in batch]
        for f in as_completed(futures):
            all_results.extend(f.result())
    print(f"  {min(batch_start+10, len(profiles))}/{len(profiles)} done...")

tested = len(all_results)
errors = sum(1 for r in all_results if "error" in r)
personalized = sum(1 for r in all_results if r.get("personalized"))
good = tested - errors
avg_len = sum(r.get("length",0) for r in all_results if "length" in r) / max(1, good)

print(f"\n=== RESULTS ===")
print(f"Tests: {tested} | Errors: {errors}")
print(f"Personalized: {personalized}/{good} ({round(personalized/max(1,good)*100,1)}%)")
print(f"Avg response: {round(avg_len)} chars")

sector_stats = {}
for r in all_results:
    if "error" in r: continue
    s = r["sector"]
    sector_stats.setdefault(s, {"count":0,"personalized":0,"total_len":0})
    sector_stats[s]["count"] += 1
    if r.get("personalized"): sector_stats[s]["personalized"] += 1
    sector_stats[s]["total_len"] += r.get("length",0)

print("\nPer sector:")
for s, st in sorted(sector_stats.items()):
    pct = round(st["personalized"]/max(1,st["count"])*100,1)
    avg = round(st["total_len"]/max(1,st["count"]))
    print(f"  {s:15s}: {pct:5.1f}% perso, {avg:4d} chars avg")

best = sorted([r for r in all_results if "response" in r], key=lambda x: len(x.get("response","")), reverse=True)[:5]
print("\nTop 5 responses:")
for r in best:
    print(f"  [{r['profile']}] {r['sector']} — {r['question']}")
    print(f"  → {r['response'][:120]}...\n")
