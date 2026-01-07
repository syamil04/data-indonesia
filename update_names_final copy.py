import json
import csv
import os
import re
from difflib import get_close_matches, SequenceMatcher

CSV_PATH = 'referensi/master_prov_kabupaten_kota.csv'
PROVINSI_JSON_PATH = 'provinsi.json'
PROPINSI_JSON_PATH = 'propinsi.json'
KABUPATEN_DIR = 'kabupaten'
KOTA_DIR = 'kota'

def normalize_name(name):
    """Normalize for comparison"""
    name = name.lower()
    name = name.replace('kab.', '').replace('kabupaten', '')
    name = name.replace('kota adm.', '').replace('kota', '')
    name = name.replace('wil.', '')
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def title_case_name(name):
    """Convert UPPER CASE to Title Case, fixing abbreviations"""
    # Fix KAB. -> Kabupaten, KOTA -> Kota
    if name.startswith('KAB. '):
        name = 'Kabupaten ' + name[5:]
    elif name.startswith('KOTA '):
        name = 'Kota ' + name[5:]
    
    # Title Case properly
    words = name.split()
    new_words = []
    for w in words:
        if w.lower() in ['d/h', 'di', 'dan', 'ke']: # particles
            new_words.append(w.lower())
        elif w.startswith('('):
            new_words.append(w.title())
        else:
            new_words.append(w.title())
    return " ".join(new_words)

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def load_csv():
    provinces = {} # Normalized -> real name
    kabupatens = {} # Province Real Name -> {Normalized Kab Name -> Real Kab Name}
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 3: continue
            
            prov_real = row[1].strip()
            kab_real = row[2].strip()
            
            # Skip "Lainnya"
            if "Lainnya" in kab_real:
                continue

            prov_norm = normalize_name(prov_real)
            provinces[prov_norm] = prov_real
            
            if prov_real not in kabupatens:
                kabupatens[prov_real] = {}
            
            kab_norm = normalize_name(kab_real)
            kabupatens[prov_real][kab_norm] = kab_real
            
    return provinces, kabupatens

def update_provinces(provinces_map):
    files = [PROVINSI_JSON_PATH]
    if os.path.exists(PROPINSI_JSON_PATH):
        files.append(PROPINSI_JSON_PATH)
        
    province_id_to_name = {}

    for fpath in files:
        with open(fpath, 'r') as f:
            data = json.load(f)
        
        updated = False
        for p in data:
            original_name = p['nama']
            norm_name = normalize_name(original_name)
            
            # Direct match on normalized name
            if norm_name in provinces_map:
                new_name = provinces_map[norm_name]
                if new_name != original_name:
                    p['nama'] = new_name
                    updated = True
                    print(f"Updated Prov: {original_name} -> {new_name}")
            else:
                # Fuzzy match
                # Get all keys
                keys = list(provinces_map.keys())
                matches = get_close_matches(norm_name, keys, n=1, cutoff=0.7)
                if matches:
                    new_name = provinces_map[matches[0]]
                    if new_name != original_name:
                        p['nama'] = new_name
                        updated = True
                        print(f"Fuzzy Updated Prov: {original_name} -> {new_name}")
                else:
                    # No match (new provinces), just Title Case
                    new_name = title_case_name(original_name)
                    if new_name != original_name:
                        p['nama'] = new_name
                        updated = True
                        print(f"Refined Prov Name: {original_name} -> {new_name}")
            
            province_id_to_name[p['id']] = p['nama']

        if updated:
            with open(fpath, 'w') as f:
                json.dump(data, f, indent=2)
                f.write('\n') # Add newline at end
    
    return province_id_to_name

def update_kabupatens(province_ids, csv_kabs):
    # Iterate through all json files in kabupaten folder
    for filename in os.listdir(KABUPATEN_DIR):
        if not filename.endswith('.json'):
            continue
            
        prov_id = filename.replace('.json', '')
        if prov_id not in province_ids:
            continue
            
        current_prov_name = province_ids[prov_id]
        
        # Check if we have CSV data for this province
        # We might have mismatches if province name in CSV is different slightly
        # But we just updated province_ids from CSV, so current_prov_name should matches CSV keys if it was found
        
        target_kabs_map = csv_kabs.get(current_prov_name)
        
        filepath = os.path.join(KABUPATEN_DIR, filename)
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        updated = False
        for k in data:
            original_name = k['nama']
            
            if target_kabs_map:
                norm_name = normalize_name(original_name)
                
                # Direct match
                if norm_name in target_kabs_map:
                    new_name = target_kabs_map[norm_name]
                else:
                    # Fuzzy match
                    keys = list(target_kabs_map.keys())
                    matches = get_close_matches(norm_name, keys, n=1, cutoff=0.6)
                    if matches:
                        new_name = target_kabs_map[matches[0]]
                    else:
                        # Try searching by containment (e.g. "Bireuen" in "Aceh Jeumpa/Bireuen")
                        found_cnt = None
                        for key in keys:
                            if norm_name in key or key in norm_name:
                                found_cnt = key
                                break
                        
                        if found_cnt:
                            new_name = target_kabs_map[found_cnt]
                        else:
                            new_name = title_case_name(original_name)

                if new_name != original_name:
                    k['nama'] = new_name
                    updated = True
                    # print(f"Updated Kab ({current_prov_name}): {original_name} -> {new_name}")
            else:
                # No CSV data for this province (e.g. new Papua provinces)
                new_name = title_case_name(original_name)
                if new_name != original_name:
                    k['nama'] = new_name
                    updated = True
                    # print(f"Refined Kab Name ({current_prov_name}): {original_name} -> {new_name}")

        if updated:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                # f.write('\n')
            print(f"Updated {filename}")
            
def update_kota(province_ids, csv_kabs):
    # Iterate through all json files in kabupaten folder
    for filename in os.listdir(KOTA_DIR):
        if not filename.endswith('.json'):
            continue
            
        prov_id = filename.replace('.json', '')
        if prov_id not in province_ids:
            continue
            
        current_prov_name = province_ids[prov_id]
        
        # Check if we have CSV data for this province
        # We might have mismatches if province name in CSV is different slightly
        # But we just updated province_ids from CSV, so current_prov_name should matches CSV keys if it was found
        
        target_kabs_map = csv_kabs.get(current_prov_name)
        
        filepath = os.path.join(KOTA_DIR, filename)
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        updated = False
        for k in data:
            original_name = k['nama']
            
            if target_kabs_map:
                norm_name = normalize_name(original_name)
                
                # Direct match
                if norm_name in target_kabs_map:
                    new_name = target_kabs_map[norm_name]
                else:
                    # Fuzzy match
                    keys = list(target_kabs_map.keys())
                    matches = get_close_matches(norm_name, keys, n=1, cutoff=0.6)
                    if matches:
                        new_name = target_kabs_map[matches[0]]
                    else:
                        # Try searching by containment (e.g. "Bireuen" in "Aceh Jeumpa/Bireuen")
                        found_cnt = None
                        for key in keys:
                            if norm_name in key or key in norm_name:
                                found_cnt = key
                                break
                        
                        if found_cnt:
                            new_name = target_kabs_map[found_cnt]
                        else:
                            new_name = title_case_name(original_name)

                if new_name != original_name:
                    k['nama'] = new_name
                    updated = True
                    # print(f"Updated Kab ({current_prov_name}): {original_name} -> {new_name}")
            else:
                # No CSV data for this province (e.g. new Papua provinces)
                new_name = title_case_name(original_name)
                if new_name != original_name:
                    k['nama'] = new_name
                    updated = True
                    # print(f"Refined Kab Name ({current_prov_name}): {original_name} -> {new_name}")

        if updated:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                # f.write('\n')
            print(f"Updated {filename}")

if __name__ == "__main__":
    csv_provinces, csv_kabs = load_csv()
    final_prov_map = update_provinces(csv_provinces)
    update_kabupatens(final_prov_map, csv_kabs)
    update_kabupatens(final_prov_map, csv_kabs)
