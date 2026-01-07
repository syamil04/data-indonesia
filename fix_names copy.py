import csv
import json
import os
import difflib
import re

CSV_PATH = 'referensi/master_prov_kabupaten_kota.csv'
DIR_KABUPATEN = 'kabupaten'
DIR_KOTA = 'kota'
PROVINSI_FILE = 'propinsi.json'
PROVINSI_FILE_2 = 'provinsi.json'

def load_csv_reference(csv_path):
    provinces = set()
    kabkota = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                # layout: id, province_name, kabkota_name
                prov = row[1].strip()
                kk = row[2].strip()
                
                # Ignore placeholders
                if "Kabupaten/Kota Lainnya" in kk:
                    continue
                    
                provinces.add(prov)
                kabkota.append(kk)
                
    return list(provinces), kabkota

def normalize_name(name):
    # Remove KAB., KOTA, prefixes
    name = name.upper()
    name = re.sub(r'^(KABUPATEN|KAB\.?|KOTA|WIL\.|WILAYAH)\s*', '', name)
    name = re.sub(r'^(KEP\.?|KEPULAUAN)\s*', 'KEPULAUAN ', name) # Standardize Kepulauan
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def normalize_csv_name(name):
    # Remove Kabupaten, Kota prefixes for matching logic
    name_upper = name.upper()
    name_upper = re.sub(r'^(KABUPATEN|KOTA|WIL\.\s*KOTA)\s*', '', name_upper)
    name_upper = re.sub(r'\s+', ' ', name_upper).strip()
    return name_upper

def find_best_match(name, candidates, threshold=0.8):
    # name: the raw name from JSON (e.g. "KAB. ACEH SELATAN")
    # candidates: list of full names from CSV (e.g. "Kabupaten Aceh Selatan")
    
    # We normalized both to compare core names
    norm_name = normalize_name(name)
    
    # specific override for some abbreviations if needed
    
    best_ratio = 0
    best_match = None
    
    for candidate in candidates:
        norm_cand = normalize_csv_name(candidate)
        
        # Exact core match
        if norm_name == norm_cand:
            return candidate
            
        ratio = difflib.SequenceMatcher(None, norm_name, norm_cand).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = candidate
            
    if best_ratio >= threshold:
        return best_match
    
    return None

def is_kota(id_code):
    # Returns True if ID indicates Kota (xx71 .. xx99)
    # Returns False if Kabupaten (xx01 .. xx69)
    # Assumes 4 digit code.
    if not id_code or len(id_code) != 4:
        return False
    try:
        suffix = int(id_code[2:])
        return 71 <= suffix <= 99
    except ValueError:
        return False

def process_file_list(directory, csv_kabkota):
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist.")
        return

    files = [f for f in os.listdir(directory) if f.endswith('.json')]
    print(f"Processing {len(files)} files in {directory}...")
    
    updates_count = 0
    
    for filename in files:
        path = os.path.join(directory, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[{filename}] Error reading: {e}")
            continue
            
        if isinstance(data, list):
             # Skip list files (likely index files or lists of sub-districts)
             # print(f"[{filename}] Skipped (is list)")
             continue
        
        if not isinstance(data, dict):
            continue

        original_name = data.get('nama', '')
        file_id = data.get('id', '')
        
        if not original_name:
            continue
            
        # Determine strict candidate filtering based on ID
        is_city = is_kota(file_id)
        
        filtered_candidates = []
        if is_city:
            # Must contain Kota
            filtered_candidates = [c for c in csv_kabkota if "Kota " in c or "Wil. Kota" in c]
            expected_type = "KOTA"
        else:
            # Must contain Kabupaten
            filtered_candidates = [c for c in csv_kabkota if "Kabupaten " in c]
            expected_type = "KABUPATEN"
            
        if not filtered_candidates:
            # Fallback (e.g. if CSV is unexpected)
            filtered_candidates = csv_kabkota

        match = find_best_match(original_name, filtered_candidates)
        
        if file_id == "3371":
            print(f"DEBUG 3371: Is Kota: {is_city}. Orig: {original_name}. Candidates len: {len(filtered_candidates)}")
            if filtered_candidates:
                print(f"DEBUG 3371 Cand[0]: {filtered_candidates[0]}")
            m = find_best_match(original_name, filtered_candidates)
            print(f"DEBUG 3371 Match: {m}")

        if match:
             if original_name != match:
                # print(f"[{filename}] {original_name} -> {match}")
                data['nama'] = match
                with open(path, 'w', encoding='utf-8') as f:
                     json.dump(data, f) # Compact dump
                updates_count += 1
        else:
             pass
             # print(f"[{filename}] No match for '{original_name}' (Expect {expected_type})")

    print(f"Updated {updates_count} files in {directory}.")

def process_provinces(csv_provinces):
    # Process propinsi.json and provinsi.json
    for pfile in [PROVINSI_FILE, PROVINSI_FILE_2]:
        if not os.path.exists(pfile):
            continue
            
        print(f"Processing {pfile}...")
        with open(pfile, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        updated = False
        for entry in data:
            name = entry.get('nama', '')
            # Try exact match first
            if name in csv_provinces:
                continue
                
            # Try fuzzy match
            # For provinces, we don't have many, so fuzzy is safe.
            # Normalize "DI Yogyakarta" vs "D.I. Yogyakarta"
            
            best_p = None
            best_score = 0
            
            for cp in csv_provinces:
                score = difflib.SequenceMatcher(None, name.lower(), cp.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_p = cp
            
            if best_score > 0.95: # Very strict (fixes 'Papua Barat Daya' -> 'Papua Barat' issue)
                 if name != best_p:
                     print(f"Province Update: '{name}' -> '{best_p}'")
                     entry['nama'] = best_p
                     updated = True
            else:
                print(f"Province No Match: '{name}'")
                
        if updated:
            with open(pfile, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2) # propinsi.json is multiline

def main():
    if not os.path.exists(CSV_PATH):
        print("CSV Reference not found!")
        return
        
    ref_provinces, ref_kabkota = load_csv_reference(CSV_PATH)
    
    print(f"Loaded {len(ref_provinces)} provinces and {len(ref_kabkota)} kab/kota from CSV.")
    
    process_provinces(ref_provinces)
    process_file_list(DIR_KABUPATEN, ref_kabkota)
    process_file_list(DIR_KOTA, ref_kabkota)

if __name__ == "__main__":
    main()
