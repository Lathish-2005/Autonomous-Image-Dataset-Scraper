"""
Comprehensive Recovery Script
Sweeps through ALL makes/models in final_dataset/US/OFFICIAL,
re-evaluates every image in rejected_images with the patched YOLO filter,
and moves any newly-approved exterior shots back to saved_images.
"""
import os
import sys
import shutil
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from vision.yolo_filter import YOLOFilter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("recover_all")

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

def main():
    base_dir = config.FINAL_DATASET_DIR  # final_dataset/US/OFFICIAL
    if not os.path.isdir(base_dir):
        logger.error(f"Dataset directory not found: {base_dir}")
        return

    # Load YOLO once
    yolo = YOLOFilter(model_name="yolov8m.pt")
    if not yolo.load_model():
        logger.error("Failed to load YOLO model.")
        return

    total_recovered = 0
    total_still_rejected = 0
    total_read_errors = 0
    results = []  # (make, model, recovered, still_rejected, read_errors)

    for make_name in sorted(os.listdir(base_dir)):
        make_path = os.path.join(base_dir, make_name)
        if not os.path.isdir(make_path):
            continue

        for model_name in sorted(os.listdir(make_path)):
            model_path = os.path.join(make_path, model_name)
            if not os.path.isdir(model_path):
                continue

            rejected_dir = os.path.join(model_path, "rejected_images")
            saved_dir = os.path.join(model_path, "saved_images")

            if not os.path.isdir(rejected_dir):
                continue

            # Gather image files
            images = sorted([
                f for f in os.listdir(rejected_dir)
                if os.path.splitext(f)[1].lower() in VALID_EXTENSIONS
            ])

            if not images:
                continue

            os.makedirs(saved_dir, exist_ok=True)

            # Determine next sequence number for saved_images
            existing_saved = [
                f for f in os.listdir(saved_dir)
                if os.path.splitext(f)[1].lower() in VALID_EXTENSIONS
            ]
            next_seq = len(existing_saved) + 1

            recovered = 0
            still_rejected = 0
            read_errors = 0

            logger.info(f"\nProcessing {make_name}/{model_name} ({len(images)} rejected images)...")

            for img_file in images:
                img_path = os.path.join(rejected_dir, img_file)

                # Run through the patched YOLO filter
                approved, rejected = yolo.filter_batch([img_path])

                if approved:
                    # Move to saved_images with proper naming
                    ext = os.path.splitext(img_file)[1].lower()
                    new_name = f"image_{next_seq:03d}{ext}"
                    dest = os.path.join(saved_dir, new_name)
                    shutil.move(img_path, dest)
                    logger.info(f"  [RECOVERED] {img_file} -> {new_name}")
                    next_seq += 1
                    recovered += 1
                elif rejected:
                    reason = rejected[0][1] if isinstance(rejected[0], tuple) else "unknown"
                    if "could not read" in str(reason).lower():
                        read_errors += 1
                    else:
                        still_rejected += 1
                    logger.info(f"  [REJECTED]  {img_file}: {reason}")
                else:
                    still_rejected += 1
                    logger.info(f"  [REJECTED]  {img_file}: filter returned empty")

            total_recovered += recovered
            total_still_rejected += still_rejected
            total_read_errors += read_errors
            results.append((make_name, model_name, recovered, still_rejected, read_errors))

    # ── Final Summary ──
    print("\n" + "=" * 70)
    print("COMPREHENSIVE RECOVERY SUMMARY")
    print("=" * 70)
    print(f"{'Make':<18} {'Model':<20} {'Recovered':>10} {'Still Rej':>10} {'Read Err':>10}")
    print("-" * 70)
    for make, model, rec, rej, err in results:
        print(f"{make:<18} {model:<20} {rec:>10} {rej:>10} {err:>10}")
    print("-" * 70)
    print(f"{'TOTAL':<38} {total_recovered:>10} {total_still_rejected:>10} {total_read_errors:>10}")
    print("=" * 70)

if __name__ == "__main__":
    main()
