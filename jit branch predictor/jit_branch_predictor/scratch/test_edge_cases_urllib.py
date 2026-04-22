import urllib.request
import json

URL = 'http://localhost:5173/simulate'
req = urllib.request.Request(URL, headers={'Content-Type': 'application/json'}, method='POST')

EDGE_CASES = {
    '1. Empty String': '   \n  \t ',
    '2. Syntax Error': 'def test( { \n print("fail")',
    '3. No Branches': 'a = 10\nb = 20\nc = a + b\nprint(c)',
    '4. Massive Loop': 'for i in range(1000000000000):\n  pass',
    '5. Deeply Nested Loops': 'for i in range(2):\n  for j in range(2):\n    for k in range(2):\n      pass',
    '6. Pure C Code Fallback': '#include <stdio.h>\nint main() {\n  for(int i=0; i<10; i++) {\n    if (i % 2 == 0) continue;\n  }\n  return 0;\n}',
    '7. Extreme Polymorphism': '\n'.join([f'if isinstance(x, type{i}): pass' for i in range(15)]),
    '8. Long If-Elif Chain': 'if a == 1: pass\n' + '\n'.join([f'elif a == {i}: pass' for i in range(2, 10)]),
    '9. Infinite While Loop': 'while True:\n  pass',
    '10. Mixed Chaos': 'for i in range(5):\n  if isinstance(i, int):\n    while True:\n      if a:\n        break'
}

results_md = '# Edge Case Analysis Results\n\n'

for name, code in EDGE_CASES.items():
    try:
        data = json.dumps({'code': code}).encode('utf-8')
        resp = urllib.request.urlopen(req, data=data, timeout=15)
        resp_data = json.loads(resp.read().decode('utf-8'))
        
        results_md += f'## {name}\n'
        
        if 'error' in resp_data:
            results_md += f'**Result:** Handled with Error Message\n> {resp_data["error"]}\n\n'
        else:
            analysis = resp_data.get('analysis', {})
            rows = resp_data.get('rows', [])
            ghr_row = next((r for r in rows if r['exp'] == 'JIT' and r['predictor'] == 'GHR'), None)
            ghr_miss = ghr_row['mispredict_rate'] if ghr_row else 'N/A'
            bit2_row = next((r for r in rows if r['exp'] == 'JIT' and r['predictor'] == '2-Bit'), None)
            bit2_miss = bit2_row['mispredict_rate'] if bit2_row else 'N/A'
            
            results_md += f'**Language Detected:** {analysis.get("language", "Unknown")}\n'
            results_md += f'**Simulation Result:**\n- 2-Bit Misprediction: {bit2_miss}%\n- GShare Misprediction: {ghr_miss}%\n\n'
            
    except Exception as e:
        results_md += f'## {name}\n**Result:** CRASH/EXCEPTION\n> {str(e)}\n\n'
        
open('scratch/edge_case_report.md', 'w').write(results_md)
print('Done!')
