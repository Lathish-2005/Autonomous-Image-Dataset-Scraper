"""Quick scan of saved/rejected image counts across the entire dataset."""
import os

base = os.path.join("final_dataset", "US", "OFFICIAL")

for make in sorted(os.listdir(base)):
    make_path = os.path.join(base, make)
    if not os.path.isdir(make_path):
        continue
    for model in sorted(os.listdir(make_path)):
        model_path = os.path.join(make_path, model)
        if not os.path.isdir(model_path):
            continue
        saved_dir = os.path.join(model_path, "saved_images")
        rejected_dir = os.path.join(model_path, "rejected_images")
        saved_count = len(os.listdir(saved_dir)) if os.path.isdir(saved_dir) else 0
        rejected_count = len(os.listdir(rejected_dir)) if os.path.isdir(rejected_dir) else 0
        print(f"{make}/{model}: saved={saved_count}, rejected={rejected_count}")
