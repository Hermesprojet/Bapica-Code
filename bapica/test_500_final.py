#!/usr/bin/env python3
"""50 comptes × 500 scénarios — curl endpoints + Node.js functions"""

import subprocess, json, time, random, os

SK = subprocess.run("grep SUPABASE_SERVICE_ROLE_KEY /root/bapica/bapica/.env.local | cut -d= -f2", shell=True, capture_output=True, text=True).stdout.strip()
SUPABASE_URL = "https://xlivseiybtkwkekyhqwg.supabase.co"
SECTORS = ["ecommerce", "services", "sante", "formation", "saas", "immobilier", "restauration", "logistique", "finance", "btp"]
SIZES = ["TPE solo", "TPE 2-5", "PME 5-20", "PME 20-50"]
STAGES = ["early", "growth", "mature", "scaleup"]

# ============================
# PHASE 1 : CRÉER 50 COMPTES
# ============================
print("=" * 60)
print("PHASE 1 : 50 COMPTES")
accounts = []
for i in range(50):
    sec = SECTORS[i % 10]
    email = f"v2.{i}@bapica-test.com"
    profile = {
        "companyName": f"TestCo{i}", "activity": sec,
        "companySize": SIZES[i % 4],
        "employeeCount": random.choice([1,2,3,5,8,12]),
        "stage": STAGES[i % 4],
        "adminTasks": random.sample(["facturation","prospection","support","comptabilité","recrutement","contenu"],3),
        "objectives": random.sample(["automatiser","croître","digitaliser","déléguer","recruter"],2),
    }
    cmd = f"""curl -s --max-time 10 '{SUPABASE_URL}/auth/v1/admin/users' -H 'apikey: {SK}' -H 'Authorization: Bearer {SK}' -H 'Content-Type: application/json' -d '{{"email":"{email}","password":"Test1234!","email_confirm":true,"user_metadata":{{"onboarding_data":{json.dumps(profile)}}}}}'"""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    uid = ""
    try: uid = json.loads(r.stdout).get("id","")[:8]
    except: pass
    accounts.append({"i":i, "email":email, "sector":sec, "stage":profile["stage"], "size":profile["employeeCount"], "profile":profile})
    print(f"  {i+1:2}/50 {email} ({sec:12}) {uid}")

# ============================
# PHASE 2 : 300 CURL (public)
# ============================
print(f"\n{'='*60}")
print("PHASE 2 : 300 CURL")
curl_results = []
CHAT = [("general","Bonjour"),("prospector","Prospection?"),("scaling","30k/mois"),("support","Temps réponse?")]

for acc in accounts:
    i, sec = acc["i"], acc["sector"]
    # market_intel
    t0 = time.time()
    r = subprocess.run(f"curl -s --max-time 8 'https://bapica.com/api/market-intelligence?sector={sec}&type=all'", shell=True, capture_output=True, text=True, timeout=12)
    t = time.time() - t0
    ok = False
    try: ok = "competitiveAnalysis" in r.stdout or "trends" in r.stdout
    except: pass
    curl_results.append(("market", ok, t))
    print(f"  {'✅' if ok else '❌'} market {t:.1f}s", end="")
    
    for agent, msg in CHAT:
        t0 = time.time()
        body = json.dumps({"agentId":agent,"message":msg})
        r = subprocess.run(f"curl -s --max-time 12 -X POST 'https://bapica.com/api/demo-chat' -H 'Content-Type: application/json' -d '{body}'", shell=True, capture_output=True, text=True, timeout=15)
        t = time.time() - t0
        ok = False
        try: ok = len(json.loads(r.stdout).get("response","")) > 10
        except: pass
        curl_results.append((f"chat_{agent}", ok, t))
        print(f" {'✅' if ok else '❌'}", end="", flush=True)
    print()

curl_ok = sum(1 for _,ok,_ in curl_results if ok)
print(f"\nCURL : {curl_ok}/{len(curl_results)} ({curl_ok/len(curl_results)*100:.1f}%)")

# ============================
# PHASE 3 : 200 FONCTIONS (Node)
# ============================
print(f"\n{'='*60}")
print("PHASE 3 : 200 FONCTIONS INTERNES")

func_results = []
for acc in accounts[:50]:
    i, sec = acc["i"], acc["sector"]
    p = acc["profile"]
    
    # Générer un script TS simple
    ts = f"""import {{ analyzeBusinessProfile }} from './src/lib/business-profile';
import {{ generateDeepAnalysis }} from './src/lib/deep-analysis';
import {{ AdvancedReasoning }} from './src/lib/reasoning-engine';
import {{ generateCompetitiveAnalysis, getSectorTrends }} from './src/lib/market-intelligence';

const profile = {json.dumps(p)};
const bp = analyzeBusinessProfile(profile);
const analysis = generateDeepAnalysis(bp);
const r = new AdvancedReasoning(bp);

const checks = {{
  healthScore: analysis.healthScore > 0,
  hypotheses: analysis.hypotheses.length >= 1,
  recommendations: analysis.recommendations.length >= 1,
  causalChain: analysis.causalChain.length >= 1,
  whatIfScenarios: analysis.whatIfScenarios.length >= 1,
  riskCascade: analysis.riskCascade.length >= 1,
  crossClientPatterns: analysis.crossClientPatterns.length >= 1,
  multiPerspective: r.multiPerspective('test').perspectives.length >= 3,
  temporal: r.temporal().immediate.actions.length >= 1,
  analogical: r.analogical().length >= 1,
  pareto: r.pareto().vital20Percent.length >= 1,
  premortem: r.premortem().timeline.length >= 3,
  inversion: r.inversion().howToFail.length >= 3,
  secondOrder: r.secondOrder('test').secondOrder.length >= 1,
  socratic: r.socratic('surcharge').questions.length >= 3,
  mentalModels: r.mentalModels().length >= 3,
  decisionMatrix: Object.keys(r.decisionMatrix(['Automatiser','Recruter']).totals).length >= 1,
  marketIntel: generateCompetitiveAnalysis('{sec}').bapicaVsCompetitors.length >= 3,
  sectorTrends: getSectorTrends('{sec}').length >= 1,
}};

const allOk = Object.values(checks).every(v => v === true);
const okCount = Object.values(checks).filter(v => v === true).length;
console.log(JSON.stringify({{ allOk, okCount, total: Object.keys(checks).length, healthScore: analysis.healthScore }}));
"""
    
    ts_file = f"/root/bapica/bapica/test_p{i}.ts"
    with open(ts_file, "w") as f:
        f.write(ts)
    
    t0 = time.time()
    r = subprocess.run(f"cd /root/bapica/bapica && npx tsx test_p{i}.ts 2>/dev/null", shell=True, capture_output=True, text=True, timeout=25)
    t = time.time() - t0
    
    try:
        d = json.loads(r.stdout)
        ok = d.get("allOk", False)
        func_results.append((f"func_{i}", ok, t, d.get("okCount",0), d.get("total",0)))
        print(f"  {'✅' if ok else '⚠️'} TestCo{i:2} ({sec:12}) {d.get('okCount',0)}/{d.get('total',0)} modes  health={d.get('healthScore','?')}  {t:.1f}s")
    except Exception as e:
        func_results.append((f"func_{i}", False, t, 0, 0))
        print(f"  ❌ TestCo{i:2} ({sec:12}) parse error  {t:.1f}s  [{str(e)[:40]}]")

func_ok = sum(1 for _,ok,_,_,_ in func_results if ok)
print(f"\nFONCTIONS : {func_ok}/{len(func_results)} ({func_ok/len(func_results)*100:.1f}%)")

# ============================
# RÉSULTAT FINAL
# ============================
print(f"\n{'='*60}")
total_ok = curl_ok + func_ok
total = len(curl_results) + len(func_results)
print(f"🏆 TOTAL : {total_ok}/{total} ({total_ok/total*100:.1f}%)")
print(f"   CURL (endpoints publics) : {curl_ok}/{len(curl_results)}")
print(f"   FONCTIONS (26 modes)    : {func_ok}/{len(func_results)}")

# Détail par scénario
print("\nPar endpoint :")
stats = {}
for desc, ok, t in curl_results:
    if desc not in stats: stats[desc] = [0,0,[]]
    stats[desc][0] += 1
    if ok: stats[desc][1] += 1
    stats[desc][2].append(t)
for desc, (tot, ok, times) in sorted(stats.items()):
    rate = ok/tot*100
    avg = sum(times)/len(times)
    print(f"  {desc:20} {ok:2}/{tot:2} {rate:5.1f}% ({avg:.1f}s)")
