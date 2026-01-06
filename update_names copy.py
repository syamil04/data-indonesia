
import json
import os
import csv
import difflib

CSV_PATH = '/Users/syamil/Documents/data-indonesia/referensi/master_prov_kabupaten_kota.csv'
BASE_DIR = '/Users/syamil/Documents/data-indonesia'
KAB_DIR = os.path.join(BASE_DIR, 'kabupaten')
PROV_JSON = os.path.join(BASE_DIR, 'provinsi.json')

# Load CSV Reference
reference_kabs = []
reference_provs = set()

# Map lower_case_name -> proper_name
kab_map = {}
prov_map = {}

print("Loading CSV Data...")
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    # Handle CSV format. It looks like: ID, Prov, Kab
    # But separators might be inconsistent? It seems comma separated.
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 3:
            # Assuming row[0]=id, row[1]=prov, row[2]=kab
            # Trim whitespace
            prov = row[1].strip()
            kab = row[2].strip()
            
            reference_provs.add(prov)
            
            # Key for matching: lowercase, remove "kabupaten", "kota", "adm", etc?
            # Or just raw lowercase for now.
            # Ideally "kabupaten kepulauan yapen" vs "kabupaten kepulauan yapen-waropen"
            
            kab_map[kab.lower()] = kab
            print(f"Loaded ref: {kab}")

print(f"Loaded {len(kab_map)} unique kabupaten/kota names from CSV.")

def find_best_match(name, candidates_map):
    # exact match lower
    lower_name = name.lower()
    if lower_name in candidates_map:
        return candidates_map[lower_name]
    
    # Try fuzzy match
    # Get matches with high similarity
    matches = difflib.get_close_matches(lower_name, candidates_map.keys(), n=1, cutoff=0.8)
    if matches:
        return candidates_map[matches[0]]
    
    # Check for "Yapen" case (substring)
    # If one string is substring of another substantially
    for key in candidates_map:
        if key in lower_name or lower_name in key:
            # Check length ratio to avoid "Kota" matching "Kota Bandung"
            if len(key) > 4 and len(lower_name) > 4:
                # Special manual overrides if needed, or just accept substring
                # "kepulauan yapen" in "kabupaten kepulauan yapen-waropen" (normalized)
                 if "yapen" in lower_name and "yapen" in key:
                     return candidates_map[key]
    
    return None

# Update logic
def update_names():
    # 1. Update Provinsi.json
    print("Checking provinsi.json...")
    with open(PROV_JSON, 'r') as f:
        provinces = json.load(f)
    
    prov_changed = False
    for p in provinces:
        orig = p['nama']
        # Try to find match in reference_provs
        # Map set to dict for helper
        prov_candidates = {x.lower(): x for x in reference_provs}
        
        match = find_best_match(orig, prov_candidates)
        if match and match != orig:
            print(f"Updating Province: '{orig}' -> '{match}'")
            p['nama'] = match
            prov_changed = True
    
    if prov_changed:
        with open(PROV_JSON, 'w') as f:
            json.dump(provinces, f, indent=4) # Ensure indentation if original had specific formatting? 
            # The tool read output showed minimal formatting, json.dump default is compact.
            # Using indent=2 or 4 is safer for readability.
    
    # 2. Update Kabupaten Files
    files = os.listdir(KAB_DIR)
    for fname in files:
        if not fname.endswith('.json'):
            continue
            
        fpath = os.path.join(KAB_DIR, fname)
        with open(fpath, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Error decoding {fname}")
                continue
        
        changed = False
        
        # Handle list or dict
        if isinstance(data, list):
            for item in data:
                if 'nama' in item:
                    orig = item['nama']
                    match = find_best_match(orig, kab_map)
                    if match and match != orig:
                        print(f"Updating {fname}: '{orig}' -> '{match}'")
                        item['nama'] = match
                        changed = True
        elif isinstance(data, dict):
             if 'nama' in data:
                orig = data['nama']
                match = find_best_match(orig, kab_map)
                if match and match != orig:
                    print(f"Updating {fname}: '{orig}' -> '{match}'")
                    data['nama'] = match
                    changed = True
        
        if changed:
            with open(fpath, 'w') as f:
                # Trying to preserve style is hard, but we will print simple pretty json
                # Original files seem compact? 
                # "read_file" output:
                # [
                #   { "id": "9401", "nama": "KABUPATEN MERAUKE" },
                # ]
                # It has spaces. Indent=2 is typical.
                json.dump(data, f, indent=2)

if __name__ == "__main__":
    update_names()
