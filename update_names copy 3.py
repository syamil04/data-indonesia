
import json
import os
import csv
import difflib

CSV_PATH = '/Users/syamil/Documents/data-indonesia/referensi/master_prov_kabupaten_kota.csv'
BASE_DIR = '/Users/syamil/Documents/data-indonesia'
KAB_DIR = os.path.join(BASE_DIR, 'kabupaten')
PROV_JSON = os.path.join(BASE_DIR, 'provinsi.json')

# 1. Load CSV Reference
csv_data = {}
all_csv_provs = []

print("Loading CSV Data...")
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 3:
            prov = row[1].strip()
            kab = row[2].strip()
            
            if prov not in csv_data:
                csv_data[prov] = {}
                all_csv_provs.append(prov)
            
            # Key with lower case for lookup
            csv_data[prov][kab.lower()] = kab

print(f"Loaded {len(csv_data)} provinces from CSV.")

# 2. Map JSON IDs to CSV Provinces
with open(PROV_JSON, 'r') as f:
    json_provs = json.load(f)

id_to_csv_prov = {}

for p in json_provs:
    pid = p['id']
    pname = p['nama']
    matches = difflib.get_close_matches(pname, all_csv_provs, n=1, cutoff=0.8)
    if matches:
        id_to_csv_prov[pid] = matches[0]

# 3. Content Analysis
files = os.listdir(KAB_DIR)
used_ids = set()
for f in files:
    if f.endswith('.json'):
        if len(f.split('.')[0]) == 2:
            used_ids.add(f.split('.')[0])
        elif len(f.split('.')[0]) == 4:
            used_ids.add(f.split('.')[0][:2])

for pid in used_ids:
    if pid not in id_to_csv_prov:
        list_file = os.path.join(KAB_DIR, f"{pid}.json")
        if os.path.exists(list_file):
            with open(list_file, 'r') as f:
                try:
                    data = json.load(f)
                    names = [x['nama'].lower() for x in data if 'nama' in x][:10]
                    best_prov = None
                    max_matches = 0
                    for cp in all_csv_provs:
                        matches = 0
                        cp_kabs = csv_data[cp]
                        for n in names:
                            if n in cp_kabs: 
                                matches += 1
                                continue
                            if difflib.get_close_matches(n, cp_kabs.keys(), n=1, cutoff=0.8):
                                matches += 1
                        
                        if matches > max_matches:
                            max_matches = matches
                            best_prov = cp
                    
                    if best_prov and max_matches > 0:
                        print(f"Content-based mapping: ID {pid} -> {best_prov} (Matches: {max_matches})")
                        id_to_csv_prov[pid] = best_prov
                except:
                    pass

# 4. Helper for matching
def find_best_match_in_set(name, candidates_dict):
    low_name = name.lower()
    
    # Pre-normalization
    norm_name = low_name
    prefix_type = None
    
    if low_name.startswith('kab. '):
        norm_name = low_name.replace('kab. ', 'kabupaten ')
        prefix_type = 'kabupaten'
    elif low_name.startswith('kabupaten '):
        prefix_type = 'kabupaten'
    elif low_name.startswith('kota '):
        prefix_type = 'kota'
    elif low_name.startswith('kota. '):
        norm_name = low_name.replace('kota. ', 'kota ')
        prefix_type = 'kota'
        
    filtered_candidates = {}
    for k, v in candidates_dict.items():
        k_low = k.lower()
        if prefix_type == 'kabupaten':
            if k_low.startswith('kabupaten'):
                filtered_candidates[k] = v
        elif prefix_type == 'kota':
            if k_low.startswith('kota'):
                filtered_candidates[k] = v
        else:
            filtered_candidates[k] = v
            
    if not filtered_candidates:
        filtered_candidates = candidates_dict

    # Exact using norm
    if norm_name in filtered_candidates:
        return filtered_candidates[norm_name]
    
    # Fuzzy
    matches = difflib.get_close_matches(norm_name, filtered_candidates.keys(), n=1, cutoff=0.85)
    if matches:
        return filtered_candidates[matches[0]]
        
    # Partial for "Yapen"
    for k in filtered_candidates:
        if 'yapen' in norm_name and 'yapen' in k:
             return filtered_candidates[k]
             
    return None

# 5. Execute
files_updated = 0

print("Updating provinsi.json...")
prov_updated = False
for p in json_provs:
    pid = p['id']
    if pid in id_to_csv_prov:
        target_name = id_to_csv_prov[pid]
        if p['nama'] != target_name:
            print(f"Prop: {p['nama']} -> {target_name}")
            p['nama'] = target_name
            prov_updated = True

if prov_updated:
    with open(PROV_JSON, 'w') as f:
        json.dump(json_provs, f, indent=2)

for fname in files:
    if not fname.endswith('.json'):
        continue
    
    pid = fname.split('.')[0][:2]
    if pid not in id_to_csv_prov:
        continue

    csv_prov_name = id_to_csv_prov[pid]
    candidates = csv_data[csv_prov_name]
    
    fpath = os.path.join(KAB_DIR, fname)
    with open(fpath, 'r') as f:
        try:
            data = json.load(f)
        except:
            continue

    changed = False
    
    if isinstance(data, list):
        for item in data:
            if 'nama' in item:
                orig = item['nama']
                match = find_best_match_in_set(orig, candidates)
                if match and match != orig:
                    print(f"File {fname}: '{orig}' -> '{match}'")
                    item['nama'] = match
                    changed = True
                    
    elif isinstance(data, dict):
        if 'nama' in data:
            orig = data['nama']
            match = find_best_match_in_set(orig, candidates)
            if match and match != orig:
                print(f"File {fname}: '{orig}' -> '{match}'")
                data['nama'] = match
                changed = True
                
    if changed:
        with open(fpath, 'w') as f:
            json.dump(data, f, indent=2)
            files_updated += 1

print(f"Finished. Updated {files_updated} files.")
