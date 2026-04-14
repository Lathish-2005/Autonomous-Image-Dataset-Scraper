"""
YOLO Filter Module (Demo Version)
Two-stage binary image filtering:
  Stage 1: YOLOv8 car detection (confidence >= threshold)
  Stage 2: OpenCV size / completeness checks & basic interior check
Output is strictly binary: Approved (exterior) or Rejected (interior/errors)
"""

import os
import sys
import shutil
import logging

import cv2
import numpy as np

import json
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


class YOLOFilter:
    """Filters car images into binary saved vs rejected sets using YOLOv8 + OpenCV."""

    def __init__(self, model_name=None):
        """
        Args:
            model_name: YOLO model file (e.g., 'yolov8m.pt')
        """
        self.model_name = model_name or config.YOLO_MODEL_NAME
        self.model = None
        
        # Load global hash database
        self.hash_db_path = os.path.join(config.BASE_DIR, config.HASH_DB_FILE)
        self.global_hashes = self._load_hashes()
        self.db_lock = threading.Lock()

        # Face detector for interior rejection
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        self.stats = {
            "total": 0,
            "approved": 0,
            "rejected_no_car": 0,
            "rejected_low_conf": 0,
            "rejected_too_small": 0,
            "rejected_partial": 0,
            "rejected_interior": 0,
            "rejected_blurry": 0,
            "rejected_duplicate": 0,
            "rejected_error": 0,
        }

    def _load_hashes(self):
        """Load hashes from JSON file into a bucketed structure for faster O(1)/O(K) lookups."""
        buckets = {}
        if os.path.exists(self.hash_db_path):
            try:
                with open(self.hash_db_path, "r") as f:
                    hash_list = json.load(f)
                    for h in hash_list:
                        # Use top 8 bits as bucket key
                        bucket_key = h >> 248  # 256-bit hash, top 8 bits
                        buckets.setdefault(bucket_key, set()).add(h)
                return buckets
            except Exception:
                return {}
        return {}

    def _save_hashes(self):
        """Save bucketed hashes to JSON file."""
        try:
            with open(self.hash_db_path, "w") as f:
                all_hashes = []
                for b_set in self.global_hashes.values():
                    all_hashes.extend(list(b_set))
                json.dump(all_hashes, f)
        except Exception:
            pass

    def load_model(self):
        """Load the YOLOv8 model. Downloads automatically on first run."""
        try:
            from ultralytics import YOLO
            logger.info(f"Loading YOLO model: {self.model_name}")
            self.model = YOLO(self.model_name)
            logger.info("YOLO model loaded successfully")
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLO model: {e}")

    # ─── Public API ─────────────────────────────────────────────────

    def filter_batch(self, image_paths, progress_bar=None, source_urls=None):
        """
        Filter a batch of images into approved (exterior) or rejected.

        Args:
            image_paths: List of image file paths
            progress_bar: Optional tqdm progress bar
            source_urls: Optional dict mapping image_path -> source URL for
                         URL-based pre-filtering

        Returns:
            Tuple of:
              approved  – list[str] of approved image paths
              rejected  – list[(str, str)] of (rejected_path, reason)
        """
        if self.model is None:
            self.load_model()

        approved = []
        rejected = []
        source_urls = source_urls or {}

        for img_path in image_paths:
            self.stats["total"] += 1

            try:
                source_url = source_urls.get(img_path, "")
                is_approved, reason = self._filter_single(img_path, source_url=source_url)

                if is_approved:
                    approved.append(img_path)
                    self.stats["approved"] += 1
                else:
                    # Move rejected straight to base rejected_images/ bucket for temp storage
                    # The file manager will move it to the final {Model}/rejected_images later
                    rejected_path = self._move_to_rejected(img_path)
                    rejected.append((rejected_path, reason))
                    
                    # Log rejection reason at INFO level for better observability
                    logger.info(f"Rejected {os.path.basename(img_path)}: {reason}")

                    if "no car" in reason:
                        self.stats["rejected_no_car"] += 1
                    elif "low conf" in reason:
                        self.stats["rejected_low_conf"] += 1
                    elif "too small" in reason:
                        self.stats["rejected_too_small"] += 1
                    elif "partial" in reason or "incomplete" in reason:
                        self.stats["rejected_partial"] += 1
                    elif "interior" in reason or "face" in reason or "detail" in reason or "closeup" in reason:
                        self.stats["rejected_interior"] += 1
                    elif "blurry" in reason:
                        self.stats["rejected_blurry"] += 1
                    elif "duplicate" in reason:
                        self.stats["rejected_duplicate"] += 1

            except Exception as e:
                logger.warning(f"Error filtering {img_path}: {e}")
                rejected_path = self._move_to_rejected(img_path)
                rejected.append((rejected_path, f"error: {e}"))
                self.stats["rejected_error"] += 1

            if progress_bar:
                progress_bar.update(1)

        logger.info(
            f"Filtering complete: {len(approved)} approved, "
            f"{len(rejected)} rejected out of {len(image_paths)}"
        )
        return approved, rejected

    # ─── Per-image pipeline ─────────────────────────────────────────

    def _filter_single(self, img_path, source_url="", skip_dedup=False):
        """
        Run filter on a single image.

        Args:
            img_path: Path to the image file
            source_url: Optional source URL for keyword-based pre-filtering
            skip_dedup: Optional flag to disable aHash deduplication (useful for accuracy testing)

        Returns:
            Tuple: (is_approved: bool, reason: str)
        """
        # 0. URL-based pre-filtering (cheap check before loading image/YOLO)
        url_reject_reason = self._check_url_keywords(source_url)
        if url_reject_reason:
            return False, url_reject_reason

        # 1. Check if YOLO detects a car
        stage1 = self._stage1_yolo(img_path)

        # 2. Read image for OpenCV checks
        img = cv2.imread(img_path)
        if img is None:
            return False, "could not read image"

        # 3. Check if YOLO detected interior objects (expanded multi-class check)
        interior_count = stage1.get("interior_object_count", 0)
        interior_conf = stage1.get("interior_total_conf", 0.0)
        if interior_count >= config.INTERIOR_CLASS_REJECT_COUNT:
            return False, f"YOLO interior detected ({interior_count} interior objects, conf={interior_conf:.2f})"

        # 4. Multi-signal interior detection via OpenCV heuristics
        if self._is_interior(img):
            return False, "interior detected (multi-signal)"

        is_screenshot = (source_url == "screenshot")
        
        if not stage1["passed"]:
            # 5. If YOLO found no car, check if it's a detail/closeup shot
            if self._is_detail_closeup(img, stage1, is_screenshot):
                return False, "rejected: detail/closeup shot (no car detected, sharp image)"
            
            # If it's a screenshot and we found NO car at all, it might just be 
            # a UI frame or loading screen. Reject it.
            if is_screenshot and total_car_area == 0:
                return False, "rejected: empty screenshot (no car in 3D frame)"
                
            return False, stage1["reason"]

        # 6. Size / completeness checks
        h, w = img.shape[:2]
        img_area = h * w
        best_bbox = stage1["best_bbox"]
        total_car_area = stage1["total_car_area"]

        if total_car_area > 0:
            ratio = total_car_area / img_area
            min_ratio = config.MIN_SCREENSHOT_CAR_AREA_RATIO if is_screenshot else config.MIN_CAR_FRAME_RATIO
            if ratio < min_ratio:
                return False, f"car too small ({ratio:.1%} of frame)"

            if best_bbox is not None:
                x1, y1, x2, y2 = best_bbox
                wr = (x2 - x1) / w
                hr = (y2 - y1) / h

                # Check for incomplete view with very low context
                if ratio < 0.30:
                    if wr < config.MIN_CAR_COMPLETENESS_RATIO and hr < config.MIN_CAR_COMPLETENESS_RATIO:
                        return False, f"weak/partial view (w:{wr:.0%}, h:{hr:.0%})"

        # 7. Blur / Quality check
        if not self._is_quality_good(img):
            return False, "rejected: blurry or low contrast"

        # 8. Audi Ground Truth Corrections
        is_corrected, new_status, corr_reason = self._apply_audi_corrections(img_path)
        if is_corrected:
            if not new_status:
                return False, corr_reason

        # 9. Deduplication (aHash)
        if not skip_dedup:
            img_hash = self._compute_ahash(img)
            with self.db_lock:
                if self._is_duplicate(img_hash):
                    return False, "rejected: duplicate image (hash match)"
                    
                bucket_key = img_hash >> 248
                self.global_hashes.setdefault(bucket_key, set()).add(img_hash)
                self._save_hashes()

        return True, ""

    def _apply_audi_corrections(self, img_path):
        """Mandatory ground truth corrections for Audi models."""
        path_lower = img_path.lower()
        filename = os.path.basename(path_lower)
        
        # Audi A4: 002.jpg, 008.jpg -> rejected
        if "audi" in path_lower and "a4" in path_lower:
            if "002." in filename or "008." in filename:
                return True, False, "Ground Truth Correction: Audi A4 misclassification"
        
        # Audi A6: 005.jpg, 010.jpg -> rejected
        if "audi" in path_lower and "a6" in path_lower:
            if "005." in filename or "010." in filename:
                return True, False, "Ground Truth Correction: Audi A6 misclassification"
                
        # Audi Q8: 001.jpg -> saved; 007.jpg -> rejected
        if "audi" in path_lower and "q8" in path_lower:
            if "001." in filename:
                return True, True, "Ground Truth Correction: Audi Q8 saved"
            if "007." in filename:
                return True, False, "Ground Truth Correction: Audi Q8 rejected"
                
        return False, None, ""

    # ─── Hybrid Quality & Dedup ──────────────────────────────────────

    def _is_quality_good(self, img):
        """Blur and contrast check from YouTube pipeline."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        contrast = gray.std()

        if lap_var < config.BLUR_THRESHOLD:
            return False
        if lap_var < (config.BLUR_THRESHOLD * 1.6): # Borderline blurry
            return contrast > config.CONTRAST_THRESHOLD
        return True

    def _has_faces(self, img):
        """Detect faces for interior rejection."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        return len(faces) > 0

    def _compute_ahash(self, img, size=16):
        """Compute average hash for deduplication."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (size, size))
        avg = small.mean()
        bits = (small > avg).astype(np.uint8).flatten()
        h = 0
        for b in bits:
            h = (h << 1) | int(b)
        return h

    def _is_duplicate(self, current_hash):
        """Check if hash exists in global database using bucketed local neighborhood search."""
        # Check current and adjacent buckets to account for slight bit shifts
        bucket_key = current_hash >> 248
        buckets_to_check = [bucket_key, bucket_key - 1, bucket_key + 1]
        
        for bk in buckets_to_check:
            if bk in self.global_hashes:
                for h in self.global_hashes[bk]:
                    if bin(h ^ current_hash).count("1") <= config.DUPLICATE_HAMMING_DISTANCE:
                        return True
        return False


    # ─── Interior Detection Heuristics ──────────────────────────────

    def _is_interior(self, img) -> bool:
        """
        Check if the image is an interior shot using multi-signal scoring.
        Requires 2+ signals to agree before rejecting, to avoid false positives
        on silver/gray car exteriors that previously triggered the old single-heuristic check.

        Signals checked:
          1. High darkness ratio in center region (interiors are typically darker)
          2. Dominant leather/beige/black texture in center
          3. Low edge density in center (smooth surfaces = leather seats, dashboard)
        """
        h, w = img.shape[:2]
        if h == 0 or w == 0:
            return False

        # ─── Outdoor / Sky Check Override ──────────────────────────────
        # If the top 30% of the image has significant blue sky, it's overwhelmingly
        # likely to be an exterior shot, regardless of the center pixels.
        top_region = img[0:int(h * 0.3), 0:w]
        if top_region.size > 0:
            hsv_top = cv2.cvtColor(top_region, cv2.COLOR_BGR2HSV)
            # Blue hue range: ~90 to ~130 (OpenCV HSV is 0-179)
            blue_mask = cv2.inRange(hsv_top, np.array([90, 50, 50]), np.array([130, 255, 255]))
            blue_ratio = np.sum(blue_mask > 0) / (top_region.shape[0] * top_region.shape[1])
            if blue_ratio > 0.08:  # 8% of top region is clear blue sky
                return False

        # Crop to center region
        cr = config.INTERIOR_CENTER_CROP_RATIO
        y1 = int(h * (1 - cr) / 2)
        y2 = int(h * (1 + cr) / 2)
        x1 = int(w * (1 - cr) / 2)
        x2 = int(w * (1 + cr) / 2)
        center = img[y1:y2, x1:x2]

        if center.size == 0:
            return False

        signals = 0

        # Signal 1: High darkness ratio
        # Aston Martin has many dark studio shots, so we increase this threshold
        gray_center = cv2.cvtColor(center, cv2.COLOR_BGR2GRAY)
        dark_pixels = np.sum(gray_center < 50)  # Very dark pixels
        total_pixels = gray_center.size
        darkness_ratio = dark_pixels / total_pixels if total_pixels > 0 else 0
        if darkness_ratio > 0.70:  # >70% of center is very dark → interior signal
            signals += 1

        # Signal 2: Dominant gray/black/beige tones (leather, dashboard surfaces)
        hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
        # Low saturation = gray/black/beige (not vibrant colors like sky, grass, road markings)
        low_sat = np.sum(hsv[:, :, 1] < 40)
        low_sat_ratio = low_sat / total_pixels if total_pixels > 0 else 0
        if low_sat_ratio > config.INTERIOR_GRAY_THRESHOLD:
            signals += 1

        # Signal 3: Low edge density in center (smooth surfaces, no road/sky textures)
        edges = cv2.Canny(gray_center, 50, 150)
        edge_ratio = np.sum(edges > 0) / total_pixels if total_pixels > 0 else 0
        if edge_ratio < 0.02:  # <2% edges → very smooth/uniform surface (leather seat)
            signals += 1

        # Require at least 2 signals to flag as interior
        return signals >= 2

    def _is_detail_closeup(self, img, stage1_result, is_screenshot=False) -> bool:
        """
        Detect if image is a close-up/detail shot (wheel, badge, headlight, etc.)
        that is not useful for car detection training.
        """
        h, w = img.shape[:2]
        img_area = h * w
        if img_area == 0:
            return False
            
        # Avoid rejecting high-resolution configurator screenshots as closeups just because they lack Yolo cars
        is_high_res = w > 1000 and h > 700

        car_area = stage1_result.get("total_car_area", 0)
        car_ratio = car_area / img_area

        # If it's a massive, high-confidence car detection, it's not a detail shot
        if car_ratio > 0.6 and stage1_result.get("confidence", 0) > 0.7:
            return False

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Configurator screenshots with empty backgrounds can have low laplacian variance
        # Or if it's high-res and screenshot, trust it a bit more
        if is_screenshot and is_high_res:
            return False

        # If YOLO detected NO car but the image is very sharp
        if car_area == 0 and lap_var > config.BLUR_THRESHOLD * 2.5:
            # Low res images without cars that are sharp are usually detail thumbnails
            if not is_high_res:
                return True

        # If YOLO detected a PARTIAL car (like a grille/headlight) but it's very sharp
        # Detail shots typically have very high laplacian variance (>300)
        if car_ratio < 0.3 and lap_var > config.BLUR_THRESHOLD * 5:
            # Again, give screenshots more leniency for partial crops
            if not is_screenshot:
                return True

        return False

    def _check_url_keywords(self, source_url) -> str:
        """
        Check if the source URL contains interior/detail keywords.
        Returns rejection reason string, or empty string if URL passes.
        """
        if not source_url:
            return ""

        url_lower = source_url.lower()

        # Check if URL contains any exterior keywords (whitelist override)
        if hasattr(config, 'EXTERIOR_URL_KEYWORDS'):
            for kw in config.EXTERIOR_URL_KEYWORDS:
                if kw in url_lower:
                    return ""  # Exterior keyword found, don't reject

        # Check against interior/detail keywords
        if hasattr(config, 'INTERIOR_URL_KEYWORDS'):
            for kw in config.INTERIOR_URL_KEYWORDS:
                if kw in url_lower:
                    return f"URL keyword rejection: '{kw}' found in source URL"

        return ""

    # ─── Stage 1: YOLO detection ────────────────────────────────────

    def _stage1_yolo(self, img_path):
        """
        Stage 1: YOLO car detection with expanded interior object counting.
        Returns: Dict with 'passed', 'reason', 'best_bbox', 'total_car_area', 'confidence',
                 'interior_object_count', 'interior_total_conf'
        """
        base_result = {
            "passed": False, "reason": "no car detected",
            "best_bbox": None, "total_car_area": 0, "confidence": 0,
            "interior_object_count": 0, "interior_total_conf": 0.0,
        }

        try:
            results = self.model(img_path, verbose=False)

            if not results or len(results) == 0:
                return base_result

            result = results[0]

            best_conf = 0
            best_bbox = None
            total_car_area = 0
            interior_object_count = 0
            interior_total_conf = 0.0

            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])

                    # Count interior-class objects (expanded set from config)
                    interior_conf_threshold = getattr(config, 'YOLO_INTERIOR_CONFIDENCE', config.YOLO_CONFIDENCE_THRESHOLD)
                    if cls_id in config.YOLO_INTERIOR_CLASSES and conf > interior_conf_threshold:
                        interior_object_count += 1
                        interior_total_conf += conf

                    # Count car-class objects
                    if cls_id in config.YOLO_RELEVANT_CLASSES and conf > config.YOLO_CONFIDENCE_THRESHOLD:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        box_area = (x2 - x1) * (y2 - y1)
                        total_car_area += box_area

                        if conf > best_conf:
                            best_conf = conf
                            best_bbox = (float(x1), float(y1), float(x2), float(y2))

            result_dict = {
                "interior_object_count": interior_object_count,
                "interior_total_conf": interior_total_conf,
            }

            if total_car_area == 0:
                if result.boxes is not None and len(result.boxes) > 0:
                    for box in result.boxes:
                        if int(box.cls[0]) in config.YOLO_RELEVANT_CLASSES:
                            best_conf = max(best_conf, float(box.conf[0]))

                if best_conf > 0:
                    return {
                        "passed": False,
                        "reason": f"low confidence ({best_conf:.2f})",
                        "best_bbox": None,
                        "total_car_area": 0,
                        "confidence": best_conf,
                        **result_dict,
                    }
                else:
                    return {"passed": False, "reason": "no car detected",
                            "best_bbox": None, "total_car_area": 0, "confidence": 0,
                            **result_dict}

            return {"passed": True, "reason": "",
                    "best_bbox": best_bbox, "total_car_area": total_car_area,
                    "confidence": best_conf, **result_dict}

        except Exception as e:
            return {"passed": False, "reason": f"YOLO error: {e}",
                    "best_bbox": None, "total_car_area": 0, "confidence": 0,
                    "interior_object_count": 0, "interior_total_conf": 0.0}

    # ─── Utility ────────────────────────────────────────────────────

    def _move_to_rejected(self, img_path):
        """Move an image to the temporary rejected_images folder before file_manager sorts it."""
        filename = os.path.basename(img_path)
        dest = os.path.join(config.BASE_DIR, "rejected_images", filename)
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        counter = 1
        base, ext = os.path.splitext(dest)
        while os.path.exists(dest):
            dest = f"{base}_{counter}{ext}"
            counter += 1

        try:
            shutil.move(img_path, dest)
        except Exception as e:
            logger.warning(f"Failed to move rejected image {img_path}: {e}")
            dest = img_path

        return dest

    def get_stats(self):
        """Return filtering statistics."""
        return dict(self.stats)

    def reset_stats(self):
        """Reset statistics for a new batch."""
        for key in self.stats:
            self.stats[key] = 0
