import csv
import json
import os
from difflib import get_close_matches

CSV_PATH = 'referensi/master_prov_kabupaten_kota.csv'
PROVINSI_JSON_PATH = 'provinsi.json'
KABUPATEN_DIR = 'kabupaten'

def load_csv_data():
    provinces = set()
    kab_map = {} # Province Name -> Set of Kabupaten Names
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            # Format: No, Province, Kab/Kota
            if len(row) < 3: continue
            
            prov_name = row[1].strip()
            kab_name = row[2].strip()
            
            provinces.add(prov_name)
            
            if prov_name not in kab_map:
                kab_map[prov_name] = set()
            kab_map[prov_name].add(kab_name)
            
    return provinces, kab_map

def check_provinces(csv_provinces):
    with open(PROVINSI_JSON_PATH, 'r') as f:
        json_provs = json.load(f)
    
    print("--- Checking Provinces ---")
    for p in json_provs:
        name = p['nama']
        if name not in csv_provinces:
            # Try to find a match
            matches = get_close_matches(name, csv_provinces, n=1, cutoff=0.6)
            if matches:
                print(f"Mismatch: '{name}' (JSON) -> '{matches[0]}' (CSV) [ID: {p['id']}]")
            else:
                print(f"Not found in CSV: '{name}' [ID: {p['id']}]")
        # else:
            # print(f"Match: {name}")

    return json_provs

def check_kabupaten(json_provs, csv_kab_map):
    print("\n--- Checking Kabupaten/Kota ---")
    
    # First, we need a map from ID to Correct Province Name (from CSV)
    # But we haven't corrected provinsi.json yet. 
    # Let's try to map JSON province names to CSV province names first.
    
    prov_name_map = {} # JSON Name -> CSV Name
    csv_provinces = csv_kab_map.keys()
    
    for p in json_provs:
        name = p['nama']
        if name in csv_provinces:
            prov_name_map[name] = name
        else:
            matches = get_close_matches(name, csv_provinces, n=1, cutoff=0.6)
            if matches:
                prov_name_map[name] = matches[0]
            else:
                prov_name_map[name] = None # No corresponding province in CSV
    
    for p in json_provs:
        prov_id = p['id']
        prov_name_json = p['nama']
        prov_name_csv = prov_name_map.get(prov_name_json)
        
        if not prov_name_csv:
            print(f"Skipping province {prov_name_json} (ID {prov_id}) - Not found in CSV")
            continue
            
        file_path = os.path.join(KABUPATEN_DIR, f"{prov_id}.json")
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, 'r') as f:
            kabs = json.load(f)
            
        ref_kabs = csv_kab_map[prov_name_csv]
        
        for k in kabs:
            k_name = k['nama']
            if k_name not in ref_kabs:
                matches = get_close_matches(k_name, ref_kabs, n=1, cutoff=0.6)
                if matches:
                    print(f"Mismatch in {prov_name_csv}: '{k_name}' (JSON) -> '{matches[0]}' (CSV) [ID: {k['id']}]")
                else:
                    print(f"Not found in CSV for {prov_name_csv}: '{k_name}' [ID: {k['id']}]")

csv_provinces, csv_kab_map = load_csv_data()
json_provs = check_provinces(csv_provinces)
check_kabupaten(json_provs, csv_kab_map)
