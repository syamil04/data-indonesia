
import json
import os
import csv
import difflib

CSV_PATH = '/Users/syamil/Documents/data-indonesia/referensi/master_prov_kabupaten_kota.csv'
BASE_DIR = '/Users/syamil/Documents/data-indonesia'
KAB_DIR = os.path.join(BASE_DIR, 'kabupaten')
PROV_JSON = os.path.join(BASE_DIR, 'provinsi.json')

# 1. Load CSV Reference
# Structure: csv_data[ProvName] = { low_name: proper_name }
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
# Load provinsi.json
with open(PROV_JSON, 'r') as f:
    json_provs = json.load(f)

# id -> csv_prov_name
id_to_csv_prov = {}

for p in json_provs:
    pid = p['id']
    pname = p['nama']
    
    # Try fuzzy match against all_csv_provs
    matches = difflib.get_close_matches(pname, all_csv_provs, n=1, cutoff=0.8)
    if matches:
        id_to_csv_prov[pid] = matches[0]
        # print(f"Mapped ID {pid} ({pname}) -> {matches[0]}")
    else:
        # print(f"No name match for ID {pid} ({pname})")
        pass

# 3. Content Analysis for unmapped IDs (or checking validity of mapped ones)
# We specifically want to catch 94 (Papua Tengah) -> Papua
# List unmapped IDs we care about checking content for? Or just all IDs?
# Let's iterate all IDs actually used in kabupaten files
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
        # Try to guess based on content of XX.json if it exists
        list_file = os.path.join(KAB_DIR, f"{pid}.json")
        if os.path.exists(list_file):
            with open(list_file, 'r') as f:
                try:
                    data = json.load(f)
                    # Sample up to 5 names
                    names = [x['nama'].lower() for x in data if 'nama' in x][:10]
                    
                    best_prov = None
                    max_matches = 0
                    
                    for cp in all_csv_provs:
                        matches = 0
                        cp_kabs = csv_data[cp] # dict
                        for n in names:
                            # Fuzzy match n in cp_kabs
                            # If overlap
                            if n in cp_kabs: 
                                matches += 1
                                continue
                            # close match
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

# 4. Helper for matching within a specific set of candidates
def find_best_match_in_set(name, candidates_dict):
    low_name = name.lower()
    if low_name in candidates_dict:
        return candidates_dict[low_name]
    
    # Fuzzy
    matches = difflib.get_close_matches(low_name, candidates_dict.keys(), n=1, cutoff=0.8)
    if matches:
        return candidates_dict[matches[0]]
        
    # Partial for "Yapen"
    for k in candidates_dict:
        # Check if the existing name is a substring of candidate (e.g. Yapen -> Yapen-Waropen)
        # OR candidate is substring of existing (Yapen-Waropen -> Yapen ? No usage usually opposite)
        # We assume CSV is "longer/more correct".
        # Ensure 'yapen' is in both strings
        if 'yapen' in low_name and 'yapen' in k:
             return candidates_dict[k]
             
    return None

# 5. Execute Updates
files_updated = 0

# Update provinsi.json first?
# The user wants "nama provinsi, kabupaten, kota" to match.
# Yes, update provinsi.json names using id_to_csv_prov
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
        json.dump(json_provs, f, indent=2) # Changed indent to 2

# Update kabupaten files
for fname in files:
    if not fname.endswith('.json'):
        continue
    
    pid = fname.split('.')[0][:2]
    if pid not in id_to_csv_prov:
        # print(f"Skipping {fname} (Unmapped Province ID {pid})")
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
