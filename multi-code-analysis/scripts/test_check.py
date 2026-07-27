import json
from pathlib import Path

def test():
    d = json.load(open(r'D:\workspace\multi_code_source\dep_graph\graph.json'))
    
    include_samples = {}
    
    for path, info in d.items():
        parts = path.split('/')
        if len(parts) < 2:
            continue
        repo = parts[0]
        
        file_path = Path(r'D:\workspace\multi_code_source') / path.replace('/', '\\')
        
        if file_path.suffix in ['.c', '.cpp', '.h', '.hpp']:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for line in content.split('\n'):
                    if '#include' in line and ('common' in line or 'interface' in line or 'pf' in line):
                        if path not in include_samples:
                            include_samples[path] = []
                        include_samples[path].append(line.strip())
                        if len(include_samples) >= 5:
                            break
            except:
                pass
    
    for path, samples in include_samples.items():
        print(f'{path}:')
        for s in samples[:3]:
            print(f'  {s}')

test()
