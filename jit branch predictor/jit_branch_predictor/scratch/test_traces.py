import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import (analyze_code, generate_naive_trace, generate_jit_trace,
                 write_trace, run_simulation, TRACE_DIR, NAIVE_MEM, JIT_MEM,
                 TAKEN, NOT_TAKEN, NOP)

TEST_CASES = [
    ('print("hello")', 'HelloWorld (no branches)'),
    ('for i in range(10):\n    x = i*2', 'Simple for loop'),
    (
        'import time, random\n'
        'def worst_case_bench(size=1000):\n'
        '    data = [random.randint(0,100) for _ in range(size)]\n'
        '    sorted_data = sorted(data)\n'
        '    count_best = 0\n'
        '    for x in sorted_data:\n'
        '        if x < 50:\n'
        '            count_best += 1\n'
        '    random.shuffle(data)\n'
        '    count_worst = 0\n'
        '    for x in data:\n'
        '        if x < 50:\n'
        '            count_worst += 1\n'
        '    speed_diff = 1.0\n'
        'if __name__ == "__main__":\n'
        '    worst_case_bench()\n',
        'worst_case_bench (sorted+shuffled)'
    ),
    (
        'class Dog:\n'
        '    def speak(self): return "Woof"\n'
        'class Cat:\n'
        '    def speak(self): return "Meow"\n'
        'animals = [Dog(), Cat(), Dog()]\n'
        'for a in animals:\n'
        '    if isinstance(a, Dog):\n'
        '        a.speak()\n'
        '    elif isinstance(a, Cat):\n'
        '        a.speak()\n',
        'isinstance dispatch'
    ),
    (
        'def process(items):\n'
        '    total = 0\n'
        '    for item in items:\n'
        '        try:\n'
        '            total += int(item)\n'
        '        except ValueError:\n'
        '            total += 0\n'
        '    return total\n',
        'try/except loop'
    ),
]

os.makedirs(TRACE_DIR, exist_ok=True)
all_pass = True
PREDS = ['Static', '1-Bit', '2-Bit', 'GHR']

for code, desc in TEST_CASES:
    analysis = analyze_code(code)
    naive = generate_naive_trace(analysis)
    jit   = generate_jit_trace(analysis)
    write_trace(NAIVE_MEM, naive)
    write_trace(JIT_MEM, jit)

    out = run_simulation()
    rows = {}
    for line in out.splitlines():
        if line.startswith('Naive,') or line.startswith('JIT,'):
            parts = line.split(',')
            if len(parts) >= 8:
                key = parts[0] + '+' + parts[1]
                rows[key] = {
                    'misp': float(parts[5]),
                    'ipc':  float(parts[7]),
                }

    nb = sum(1 for x in naive if x in (TAKEN, NOT_TAKEN))
    jb = sum(1 for x in jit  if x in (TAKEN, NOT_TAKEN))

    case_ok = True
    for p in PREDS:
        ni = rows.get('Naive+' + p, {}).get('ipc', 0)
        ji = rows.get('JIT+'   + p, {}).get('ipc', 0)
        if ji < ni - 0.001:
            case_ok = False
    all_pass = all_pass and case_ok

    status = 'PASS' if case_ok else 'FAIL'
    print('[%s] %s  | Naive=%d branches | JIT=%d branches' % (
        status, desc, nb, jb))
    for p in PREDS:
        nm = rows.get('Naive+' + p, {}).get('misp', 0)
        jm = rows.get('JIT+'   + p, {}).get('misp', 0)
        ni = rows.get('Naive+' + p, {}).get('ipc',  0)
        ji = rows.get('JIT+'   + p, {}).get('ipc',  0)
        su = ji / ni if ni > 0 else 1.0
        ok = 'OK ' if ji >= ni - 0.001 else 'BAD'
        print('  %s %-6s: Naive IPC=%.4f  JIT IPC=%.4f  speedup=%.3fx'
              ' | Naive misp=%.1f%%  JIT misp=%.1f%%'
              % (ok, p, ni, ji, su, nm, jm))
    print()

print('OVERALL:', 'ALL PASS' if all_pass else 'SOME FAILED')
