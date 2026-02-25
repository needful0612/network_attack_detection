import os
import gc
import hashlib

def clear_memory(*args):
    for var in args:
        if var in globals():
            del globals()[var]
    gc.collect()

def get_script_hash(filepath):
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()
    
def get_project_hash(file_list):
    hasher = hashlib.md5()
    for filepath in sorted(file_list):
        if os.path.exists(filepath):
            hasher.update(filepath.encode()) 
            
            with open(filepath, "rb") as f:
                # read in 8kb chunks
                while chunk := f.read(8192):
                    hasher.update(chunk)
            
            # seperate boundary collison
            hasher.update(b"\0") 
        else:
            # warning if missing
            print(f"Warning: Dependency {filepath} not found.")
            
    return hasher.hexdigest()