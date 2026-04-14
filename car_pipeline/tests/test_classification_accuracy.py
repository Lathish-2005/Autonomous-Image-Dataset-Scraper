"""
Classification Accuracy Test

Tests the enhanced YOLO filter against the manually-verified ASTON MARTIN dataset.
Uses current folder placement (saved_images / rejected_images) as ground truth.

Usage:
    python tests/test_classification_accuracy.py
"""

import os
import sys
import glob

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from vision.yolo_filter import YOLOFilter


def collect_ground_truth(base_path):
    """
    Walk the Aston Martin dataset and return ground truth labels.
    
    Returns:
        List of (img_path, expected_label) tuples
        where expected_label is 'saved' or 'rejected'
    """
    ground_truth = []
    
    for model_dir in sorted(os.listdir(base_path)):
        model_path = os.path.join(base_path, model_dir)
        if not os.path.isdir(model_path):
            continue
        
        saved_dir = os.path.join(model_path, "saved_images")
        rejected_dir = os.path.join(model_path, "rejected_images")
        
        if os.path.isdir(saved_dir):
            for img_file in sorted(os.listdir(saved_dir)):
                img_path = os.path.join(saved_dir, img_file)
                if os.path.isfile(img_path):
                    ground_truth.append((img_path, "saved"))
        
        if os.path.isdir(rejected_dir):
            for img_file in sorted(os.listdir(rejected_dir)):
                img_path = os.path.join(rejected_dir, img_file)
                if os.path.isfile(img_path):
                    ground_truth.append((img_path, "rejected"))
    
    return ground_truth


def run_accuracy_test():
    """Run the enhanced filter against ground truth and report accuracy."""
    
    aston_martin_path = os.path.join(
        config.FINAL_DATASET_DIR, "Aston_Martin"
    )
    
    if not os.path.isdir(aston_martin_path):
        print(f"ERROR: Aston Martin dataset not found at {aston_martin_path}")
        sys.exit(1)
    
    print("=" * 70)
    print("CLASSIFICATION ACCURACY TEST — ASTON MARTIN DATASET")
    print("=" * 70)
    
    # Collect ground truth
    ground_truth = collect_ground_truth(aston_martin_path)
    print(f"\nGround truth: {len(ground_truth)} images")
    print(f"  Saved (exterior): {sum(1 for _, l in ground_truth if l == 'saved')}")
    print(f"  Rejected:         {sum(1 for _, l in ground_truth if l == 'rejected')}")
    
    # Initialize filter (without moving files — we just check classification)
    yolo_filter = YOLOFilter()
    
    # Clear the global hash DB to avoid interference from previous runs
    yolo_filter.global_hashes = set()
    
    yolo_filter.load_model()
    
    # Track results
    tp = 0  # True Positive: correctly identified as saved (exterior)
    tn = 0  # True Negative: correctly identified as rejected
    fp = 0  # False Positive: incorrectly saved (should be rejected)
    fn = 0  # False Negative: incorrectly rejected (should be saved)
    
    misclassified = []
    rejection_reasons = {}
    
    print(f"\nRunning filter on {len(ground_truth)} images...")
    print("-" * 70)
    
    for i, (img_path, expected_label) in enumerate(ground_truth):
        # Reset hash DB for each image to avoid dedup interference during testing
        # (We're testing classification, not deduplication)
        
        # Call the internal filter method directly (without moving files)
        is_approved, reason = yolo_filter._filter_single(img_path, skip_dedup=True)
        predicted_label = "saved" if is_approved else "rejected"
        
        # Track reason distribution
        if not is_approved:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        
        # Compare
        if expected_label == "saved" and predicted_label == "saved":
            tp += 1
        elif expected_label == "rejected" and predicted_label == "rejected":
            tn += 1
        elif expected_label == "rejected" and predicted_label == "saved":
            fp += 1
            model_name = os.path.basename(os.path.dirname(os.path.dirname(img_path)))
            misclassified.append({
                "path": img_path,
                "model": model_name,
                "expected": expected_label,
                "predicted": predicted_label,
                "reason": reason,
                "type": "FALSE_POSITIVE",
            })
        elif expected_label == "saved" and predicted_label == "rejected":
            fn += 1
            model_name = os.path.basename(os.path.dirname(os.path.dirname(img_path)))
            misclassified.append({
                "path": img_path,
                "model": model_name,
                "expected": expected_label,
                "predicted": predicted_label,
                "reason": reason,
                "type": "FALSE_NEGATIVE",
            })
        
        # Progress
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(ground_truth)} images...")
    
    # Calculate metrics
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total * 100 if total > 0 else 0
    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    # Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    print(f"\nConfusion Matrix:")
    print(f"  {'':>20}  Predicted SAVED  Predicted REJECTED")
    print(f"  {'Expected SAVED':>20}     {tp:>5}              {fn:>5}")
    print(f"  {'Expected REJECTED':>20}     {fp:>5}              {tn:>5}")
    
    print(f"\nMetrics:")
    print(f"  Accuracy:  {accuracy:.1f}%")
    print(f"  Precision: {precision:.1f}% (of predicted 'saved', how many are correct)")
    print(f"  Recall:    {recall:.1f}% (of actual 'saved', how many were found)")
    print(f"  F1 Score:  {f1:.1f}%")
    
    print(f"\nBreakdown:")
    print(f"  True Positives  (correctly saved):    {tp}")
    print(f"  True Negatives  (correctly rejected): {tn}")
    print(f"  False Positives (should be rejected): {fp}")
    print(f"  False Negatives (should be saved):    {fn}")
    
    if misclassified:
        print(f"\n{'=' * 70}")
        print(f"MISCLASSIFIED IMAGES ({len(misclassified)}):")
        print(f"{'=' * 70}")
        
        # Group by type
        false_positives = [m for m in misclassified if m["type"] == "FALSE_POSITIVE"]
        false_negatives = [m for m in misclassified if m["type"] == "FALSE_NEGATIVE"]
        
        if false_positives:
            print(f"\n  FALSE POSITIVES ({len(false_positives)}) — should be REJECTED but were SAVED:")
            for m in false_positives[:15]:
                print(f"    [{m['model']}] {os.path.basename(m['path'])}")
        
        if false_negatives:
            print(f"\n  FALSE NEGATIVES ({len(false_negatives)}) — should be SAVED but were REJECTED:")
            for m in false_negatives[:15]:
                print(f"    [{m['model']}] {os.path.basename(m['path'])} — reason: {m['reason']}")
    
    # Print rejection reason distribution
    print(f"\n{'=' * 70}")
    print("REJECTION REASON DISTRIBUTION:")
    print(f"{'=' * 70}")
    for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
        # Truncate long reasons
        display_reason = reason[:60] + "..." if len(reason) > 60 else reason
        print(f"  {count:>4}x  {display_reason}")
    
    # Summary
    print(f"\n{'=' * 70}")
    if accuracy >= 90:
        print(f"✓ PASS — Overall accuracy: {accuracy:.1f}%")
    elif accuracy >= 80:
        print(f"~ ACCEPTABLE — Overall accuracy: {accuracy:.1f}% (needs improvement)")
    else:
        print(f"✗ FAIL — Overall accuracy: {accuracy:.1f}% (significant issues)")
    print(f"{'=' * 70}")
    
    return accuracy


if __name__ == "__main__":
    run_accuracy_test()
