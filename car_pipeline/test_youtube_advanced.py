import os
import sys
import shutil
import cv2

base_dir = r"c:\Users\kotla\Downloads\NEW AGENT\car_pipeline"
sys.path.insert(0, base_dir)

from vision.yolo_filter import YOLOFilter

def measure_blur(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def dhash(image, hash_size=8):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size))
    diff = resized[:, 1:] > resized[:, :-1]
    return sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])

def hamming_distance(h1, h2):
    return bin(h1 ^ h2).count('1')

def advanced_filter(filter_mod, img_path):
    img = cv2.imread(img_path)
    if img is None:
        return False, "could not read image", 0, 0
        
    blur_score = measure_blur(img)
    img_hash = dhash(img)
    
    if blur_score < 100:
        return False, f"blurry (score {blur_score:.1f} < 100)", blur_score, img_hash
        
    results = filter_mod.model(img_path, verbose=False)
    
    if not results or len(results) == 0 or not results[0].boxes:
        return False, "no objects detected", blur_score, img_hash
        
    result = results[0]
    
    car_classes = {2, 3, 5, 7} # car, motorcycle, bus, truck
    interior_classes = {56} # chair
    person_class = 0
    
    car_area = 0
    person_area = 0
    interior_detected = False
    
    for box in result.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        if conf <= 0.35:
            continue
            
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        area = (x2 - x1) * (y2 - y1)
        
        if cls_id in car_classes:
            car_area += area
        elif cls_id == person_class:
            person_area += area
        elif cls_id in interior_classes:
            interior_detected = True
            
    if interior_detected:
        return False, "interior class detected", blur_score, img_hash
        
    if car_area == 0:
        return False, "no car detected with sufficient confidence", blur_score, img_hash
        
    if person_area > 1.5 * car_area:
        return False, "person dominates image", blur_score, img_hash
        
    return True, "", blur_score, img_hash

def main():
    testing_dir = r"c:\Users\kotla\Downloads\NEW AGENT\testing folder"
    saved_dir = os.path.join(testing_dir, "saved_images")
    rejected_dir = os.path.join(testing_dir, "rejected_images")
    
    # We will process all images from both folders
    all_images = []
    if os.path.exists(saved_dir):
        all_images.extend([os.path.join(saved_dir, f) for f in os.listdir(saved_dir) if f.lower().endswith('.jpg')])
    if os.path.exists(rejected_dir):
        all_images.extend([os.path.join(rejected_dir, f) for f in os.listdir(rejected_dir) if f.lower().endswith('.jpg')])
        
    filter_mod = YOLOFilter()
    filter_mod.load_model()
    
    # temporary new folders
    new_saved_dir = os.path.join(testing_dir, "saved_images_new")
    new_rejected_dir = os.path.join(testing_dir, "rejected_images_new")
    os.makedirs(new_saved_dir, exist_ok=True)
    os.makedirs(new_rejected_dir, exist_ok=True)
    
    total = len(all_images)
    accepted = 0
    rejected = 0
    duplicates = 0
    
    # dictionary to keep tracking of hashes
    # format: hash -> { 'path': str, 'blur': float, 'accepted': bool }
    seen_hashes = {}
    
    print(f"Processing {total} total images...")
    
    for full_path in all_images:
        filename = os.path.basename(full_path)
        
        is_approved, reason, blur_score, img_hash = advanced_filter(filter_mod, full_path)
        
        # Deduplication logic (only for approved images to find the sharpest among duplicates)
        # Even if rejected, we might still want to track it to not save a blurry version if a sharp one is rejected
        is_duplicate = False
        best_duplicate_reason = ""
        
        found_match_hash = None
        for saved_hash in seen_hashes.keys():
            if hamming_distance(img_hash, saved_hash) <= 5: # tolerance of 5 bits for near-duplicates
                found_match_hash = saved_hash
                break
                
        if found_match_hash is not None:
            # Duplicate found
            prev_info = seen_hashes[found_match_hash]
            
            if is_approved:
                # If this new one is approved, let's compare blur levels.
                # If new is blurrier, reject it.
                if blur_score <= prev_info['blur']:
                    is_approved = False
                    reason = f"duplicate (lower sharpness: {blur_score:.1f} vs {prev_info['blur']:.1f})"
                    is_duplicate = True
                else:
                    # New is sharper. 
                    # If old was accepted, we need to swap!
                    if prev_info['accepted']:
                        # move old to rejected
                        old_filename = os.path.basename(prev_info['path'])
                        old_saved = os.path.join(new_saved_dir, old_filename)
                        if os.path.exists(old_saved):
                            shutil.move(old_saved, os.path.join(new_rejected_dir, old_filename))
                            accepted -= 1
                            rejected += 1
                            duplicates += 1
                            print(f"[SWAP REJECTED] {old_filename} - Replaced by sharper duplicate {filename}")
                            
                    # update seen_hashes with the newer, sharper one
                    seen_hashes[found_match_hash] = {'path': full_path, 'blur': blur_score, 'accepted': True}
            else:
                # new one is rejected anyway
                pass
        else:
            # new hash
            seen_hashes[img_hash] = {'path': full_path, 'blur': blur_score, 'accepted': is_approved}

        if is_approved:
            accepted += 1
            dest = os.path.join(new_saved_dir, filename)
            shutil.copy2(full_path, dest)
            print(f"[SAVED] {filename} (Blur: {blur_score:.1f})")
        else:
            rejected += 1
            if is_duplicate:
                duplicates += 1
            dest = os.path.join(new_rejected_dir, filename)
            shutil.copy2(full_path, dest)
            print(f"[REJECTED] {filename} - {reason}")
            
    print("-" * 50)
    print("MIGRATING FOLDERS")
    print("-" * 50)
    
    # Remove old folders entirely
    shutil.rmtree(saved_dir, ignore_errors=True)
    shutil.rmtree(rejected_dir, ignore_errors=True)
    
    # Rename new to old
    os.rename(new_saved_dir, saved_dir)
    os.rename(new_rejected_dir, rejected_dir)

    print("-" * 50)
    print("ADVANCED SUMMARY")
    print("-" * 50)
    print(f"Total processed: {total}")
    print(f"Accepted: {accepted}")
    print(f"Rejected: {rejected} (including {duplicates} duplicates)")
    print("-" * 50)

if __name__ == "__main__":
    main()
