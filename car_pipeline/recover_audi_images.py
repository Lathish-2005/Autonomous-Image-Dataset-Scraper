import os
import sys
import shutil

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from vision.yolo_filter import YOLOFilter
import config

def recover_images():
    base_dir = config.FINAL_DATASET_DIR
    audi_dir = os.path.join(base_dir, "Audi")
    if not os.path.exists(audi_dir):
        print(f"Directory not found: {audi_dir}")
        return

    filter_instance = YOLOFilter()
    filter_instance.load_model()
    
    total_processed = 0
    total_approved = 0
    total_rejected = 0
    
    models = sorted([d for d in os.listdir(audi_dir) if os.path.isdir(os.path.join(audi_dir, d))])
    
    for model in models:
        folder_path = os.path.join(audi_dir, model)
        rejected_dir = os.path.join(folder_path, "rejected_images")
        saved_dir = os.path.join(folder_path, "saved_images")
        
        all_images = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(tuple(config.VALID_IMAGE_EXTENSIONS)):
                    all_images.append(os.path.join(root, file))
                    
        if not all_images:
            continue
            
        print(f"\nProcessing {model} ({len(all_images)} images)...")
        os.makedirs(saved_dir, exist_ok=True)
        os.makedirs(rejected_dir, exist_ok=True)
        
        for img_path in all_images:
            try:
                is_approved, reason = filter_instance._filter_single(img_path)
                filename = os.path.basename(img_path)
                if is_approved:
                    dest_path = os.path.join(saved_dir, filename)
                    if img_path != dest_path:
                        count = 1
                        while os.path.exists(dest_path) and img_path != dest_path:
                            name, ext = os.path.splitext(filename)
                            dest_path = os.path.join(saved_dir, f"{name}_{count}{ext}")
                            count += 1
                        shutil.move(img_path, dest_path)
                    print(f"  [APPROVED] {os.path.basename(dest_path)}")
                    total_approved += 1
                else:
                    dest_path = os.path.join(rejected_dir, filename)
                    if img_path != dest_path:
                        count = 1
                        while os.path.exists(dest_path) and img_path != dest_path:
                            name, ext = os.path.splitext(filename)
                            dest_path = os.path.join(rejected_dir, f"{name}_{count}{ext}")
                            count += 1
                        shutil.move(img_path, dest_path)
                    print(f"  [REJECTED] {os.path.basename(dest_path)}: {reason}")
                    total_rejected += 1
                total_processed += 1
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
                
    print(f"\nRecovery complete. Total processed: {total_processed}")
    print(f"Total Approved (saved_images): {total_approved}")
    print(f"Total Rejected (rejected_images): {total_rejected}")

if __name__ == "__main__":
    recover_images()
