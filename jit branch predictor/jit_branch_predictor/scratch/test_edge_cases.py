import requests
import json
import time

URL = "http://localhost:5173/simulate"

EDGE_CASES = {
    "1. Empty String": "   \n  \t ",
    "2. Syntax Error": "def test( { \n print('fail')",
    "3. No Branches": "a = 10\nb = 20\nc = a + b\nprint(c)",
    "4. Massive Loop": "for i in range(1000000000000):\n  pass",
    "5. Deeply Nested Loops": "for i in range(2):\n  for j in range(2):\n    for k in range(2):\n      pass",
    "6. Pure C Code Fallback": "#include <stdio.h>\nint main() {\n  for(int i=0; i<10; i++) {\n    if (i % 2 == 0) continue;\n  }\n  return 0;\n}",
    "7. Extreme Polymorphism (Aliasing Test)": "\n".join([f"if isinstance(x, type{i}): pass" for i in range(15)]),
    "8. Long If-Elif Chain": "if a == 1: pass\n" + "\n".join([f"elif a == {i}: pass" for i in range(2, 10)]),
    "9. Infinite While Loop": "while True:\n  pass",
    "10. Mixed Chaos": "for i in range(5):\n  if isinstance(i, int):\n    while True:\n      if a:\n        break"
}

results_md = "# Edge Case Analysis Results\n\n"

for name, code in EDGE_CASES.items():
    print(f"Testing {name}...")
    try:
        resp = requests.post(URL, json={"code": code}, timeout=5)
        data = resp.json()
        
        results_md += f"## {name}\n"
        results_md += f"**Input Code:**\n```python\n{code}\n```\n"
        
        if "error" in data:
            results_md += f"**Result:** Handled with Error Message\n> {data['error']}\n\n"
        else:
            analysis = data.get("analysis", {})
            rows = data.get("rows", [])
            # Find JIT GHR mispredict rate
            ghr_row = next((r for r in rows if r['exp'] == 'JIT' and r['predictor'] == 'GHR'), None)
            ghr_miss = ghr_row['mispredict_rate'] if ghr_row else 'N/A'
            
            # Find JIT 2-Bit mispredict rate
            bit2_row = next((r for r in rows if r['exp'] == 'JIT' and r['predictor'] == '2-Bit'), None)
            bit2_miss = bit2_row['mispredict_rate'] if bit2_row else 'N/A'
            
            results_md += f"**Language Detected:** {analysis.get('language', 'Unknown')}\n"
            results_md += f"**Parsed Features:** Loops: {len(analysis.get('for_loops', [])) + analysis.get('while_loops', 0)}, Type Checks: {analysis.get('isinstance_calls', 0)}\n"
            results_md += f"**Simulation Result:**\n- 2-Bit Misprediction: {bit2_miss}%\n- GShare Misprediction: {ghr_miss}%\n\n"
            
    except Exception as e:
        results_md += f"## {name}\n**Result:** ❌ CRASH/EXCEPTION\n> {str(e)}\n\n"
        
with open("edge_case_report.md", "w") as f:
    f.write(results_md)

print("Report generated at edge_case_report.md")
