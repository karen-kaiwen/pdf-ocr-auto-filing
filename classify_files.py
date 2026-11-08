import os
import re
import shutil
 
 
# Classification rules (in priority order)
CATEGORIES = {
    "corrupt":       "corrupt",
    "unrecognized":  "unrecognized",
    "duplicate":     "duplicate",
    "other_docs":    "other_docs",
    "valid_ref":     "valid_ref",
}
 
 
def classify_filename(filename):
    name, _ = os.path.splitext(filename)
 
    # 1. Starts with "corrupt" (highest priority)
    if name.lower().startswith("corrupt"):
        return "corrupt"
 
    # 2. Has a numeric suffix in parentheses (N) → duplicate
    if re.search(r'\(\d+\)$', name):
        return "duplicate"
 
    # 3. Starts with "MAL-"
    if re.match(r'^MAL-', name, re.IGNORECASE):
        return "unrecognized"
 
    # 4. Ends with "review" or "check"
    if name.lower().endswith("review") or name.lower().endswith("check"):
        return "other_docs"
 
    # 5. Digits only → valid reference number
    if re.match(r'^\d+$', name):
        return "valid_ref"
 
    return None
 
 
def classify_and_move(source_dir, dry_run=False):
    if not os.path.isdir(source_dir):
        print(f"❌ Folder not found: {source_dir}")
        return False
 
    files = [f for f in os.listdir(source_dir)
             if os.path.isfile(os.path.join(source_dir, f))]
 
    if not files:
        print("⚠️  No files found in folder.")
        return False
 
    summary = {cat: [] for cat in CATEGORIES}
    unclassified = []
 
    for filename in files:
        category = classify_filename(filename)
        if category:
            summary[category].append(filename)
        else:
            unclassified.append(filename)
 
    print(f"\n{'[Preview]' if dry_run else '[Running]'} Source folder: {source_dir}\n")
    print("=" * 50)
 
    for category, file_list in summary.items():
        if file_list:
            print(f"\n📁 {category} ({len(file_list)} file(s))")
            for f in file_list:
                print(f"   → {f}")
 
    if unclassified:
        print(f"\n❓ Unclassified ({len(unclassified)} file(s))")
        for f in unclassified:
            print(f"   → {f}")
 
    print("\n" + "=" * 50)
 
    if dry_run:
        return True
 
    moved_count = 0
    for category, file_list in summary.items():
        if not file_list:
            continue
        dest_dir = os.path.join(source_dir, category)
        os.makedirs(dest_dir, exist_ok=True)
        for filename in file_list:
            src = os.path.join(source_dir, filename)
            dst = os.path.join(dest_dir, filename)
            if os.path.exists(dst):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(dest_dir, f"{base}_dup{counter}{ext}")
                    counter += 1
            shutil.move(src, dst)
            moved_count += 1
 
    print(f"\n✅ Done! Moved {moved_count} file(s).")
    return True
 
 
def main():
    print("=" * 50)
    print("       File Auto-Classifier")
    print("=" * 50)
 
    source_dir = input("\nEnter the folder path to organize: ").strip().strip('"').strip("'")
    if not source_dir:
        source_dir = "."
 
    ok = classify_and_move(source_dir=source_dir, dry_run=True)
    if not ok:
        return
 
    confirm = input("\nProceed with moving files? (y/n): ").strip().lower()
    if confirm == "y":
        classify_and_move(source_dir=source_dir, dry_run=False)
    else:
        print("\nCancelled. No files were moved.")
 
 
if __name__ == "__main__":
    main()
 
