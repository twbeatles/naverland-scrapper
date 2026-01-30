import os
import subprocess

def get_empty_files(root_dir):
    empty_files = []
    for root, dirs, files in os.walk(root_dir):
        if ".git" in root or "__pycache__" in root: continue
        for file in files:
            path = os.path.join(root, file)
            if os.path.getsize(path) == 0:
                empty_files.append(path)
    return empty_files

def restore_file(filepath):
    # Convert windows path to git recognizable path (forward slashes)
    rel_path = os.path.relpath(filepath, ".").replace("\\", "/")
    print(f"Restoring {rel_path}...")
    try:
        # Try to get content from HEAD~1
        content = subprocess.check_output(["git", "show", f"HEAD~1:{rel_path}"], stderr=subprocess.PIPE)
        with open(filepath, "wb") as f:
            f.write(content)
        print(f"Successfully restored {filepath}")
    except subprocess.CalledProcessError:
        print(f"Failed to find {rel_path} in HEAD~1. Checking HEAD...")
        try:
             # Fallback to HEAD if HEAD~1 fails (though unlikely if file exists)
            content = subprocess.check_output(["git", "show", f"HEAD:{rel_path}"], stderr=subprocess.PIPE)
            if len(content) > 0:
                with open(filepath, "wb") as f:
                    f.write(content)
                print(f"Successfully restored {filepath} from HEAD")
            else:
                print(f"File {rel_path} is empty in HEAD as well.")
        except:
             print(f"Could not restore {filepath}")

if __name__ == "__main__":
    scan_dir = "src"
    empty = get_empty_files(scan_dir)
    print(f"Found {len(empty)} empty files in {scan_dir}")
    for f in empty:
        restore_file(f)
