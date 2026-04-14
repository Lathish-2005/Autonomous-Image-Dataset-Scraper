"""
Car Dataset Collection Pipeline — Main Entry Point

Usage:
    python main.py                              # Run complete pipeline
    python main.py --make Toyota                # Run for a specific make
    python main.py --make Toyota --model Camry  # Run for a specific model
    python main.py --tiers 1,2                  # Run specific tiers only
    python main.py --headed                     # Run with visible browser
    python main.py --filter-only                # Only run YOLO filtering on temp_dataset
    python main.py --organize-only              # Only organize already-filtered images
    python main.py --include-uncertain          # Include UNCERTAIN status URLs
    python main.py --resume --make Honda        # Resume from a specific make
"""

import os
import sys
import csv
import time
import asyncio
import logging
import argparse
from datetime import datetime, timezone
from collections import defaultdict

# Ensure the project root is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from scraper.excel_reader import ExcelReader
from scraper.url_classifier import (
    URLClassifier,
    TYPE_DIRECT_IMAGE, TYPE_CDN_URL, TYPE_KAGGLE,
    TYPE_ROBOFLOW, TYPE_OPEN_IMAGES, TYPE_GALLERY,
)
from scraper.browser import BrowserController
from scraper.cdn_extractor import CDNExtractor
from scraper.navigator import Navigator
from scraper.downloader import ImageDownloader
from scraper.dataset_handler import DatasetHandler
from vision.yolo_filter import YOLOFilter
from organizer.file_manager import FileManager

# --- Logging Setup -------------------------------------------------------
def setup_logging():
    """Configure logging for the pipeline."""
    config.ensure_directories()

    # Force UTF-8 on Windows console
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                os.path.join(config.LOGS_DIR, "pipeline.log"),
                encoding="utf-8",
            ),
        ],
    )

logger = logging.getLogger("pipeline")


# ─── CLI Arguments ───────────────────────────────────────────────────────────
def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Car Dataset Collection Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              Run complete pipeline
  python main.py --make Toyota                Run for Toyota only
  python main.py --make Toyota --model Camry  Run for Toyota Camry only
  python main.py --tiers 1,2                  Run Tier 1 and Tier 2 only
  python main.py --headed                     Show browser window
  python main.py --filter-only                Only run YOLO filtering
  python main.py --organize-only              Only organize filtered images
  python main.py --include-uncertain          Include UNCERTAIN URLs
  python main.py --resume --make Honda        Resume from Honda
        """,
    )

    parser.add_argument("--make", type=str, default=None,
                        help="Process only this car make")
    parser.add_argument("--model", type=str, default=None,
                        help="Process only this car model (requires --make)")
    parser.add_argument("--tiers", type=str, default=None,
                        help="Comma-separated tier numbers to process (e.g., 1,2)")
    parser.add_argument("--headed", action="store_true",
                        help="Run browser in headed mode (visible window)")
    parser.add_argument("--filter-only", action="store_true",
                        help="Only run YOLO filtering on existing temp_dataset")
    parser.add_argument("--organize-only", action="store_true",
                        help="Only run file organization on already-filtered images")
    parser.add_argument("--include-uncertain", action="store_true",
                        help="Include UNCERTAIN status URLs")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from a previously interrupted run")
    parser.add_argument("--yolo-model", type=str, default=None,
                        help="YOLO model to use (e.g., yolov8n.pt, yolov8m.pt)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Custom folder path to save organized images")
    parser.add_argument("--flat", action="store_true",
                        help="Save images directly into --output-dir without creating Make/Model subfolders")

    return parser.parse_args()


# ─── Run Log Writer ──────────────────────────────────────────────────────────
class RunLogger:
    """Writes per-model run summaries to run_log.csv."""

    def __init__(self):
        self.log_path = config.RUN_LOG_PATH
        self._ensure_header()

    def _ensure_header(self):
        """Create the CSV file with header if it doesn't exist."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "make", "model", "tier", "source_type",
                    "urls_processed", "images_downloaded",
                    "images_approved", "images_rejected",
                    "rejection_rate", "colors_detected",
                    "run_duration_seconds", "errors", "timestamp",
                ])

    def log_model(self, make, model, tier, source_type, urls_processed,
                  images_downloaded, images_approved, images_rejected,
                  colors_detected, duration_seconds, error_count):
        """Write a single model's run data to the CSV log."""
        rejection_rate = (
            f"{images_rejected / images_downloaded * 100:.1f}%"
            if images_downloaded > 0 else "0%"
        )
        colors_str = ", ".join(colors_detected) if colors_detected else ""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                make, model, f"Tier {tier}", source_type,
                urls_processed, images_downloaded,
                images_approved, images_rejected,
                rejection_rate, colors_str,
                int(duration_seconds), error_count, timestamp,
            ])


# ─── Pipeline Orchestrator ───────────────────────────────────────────────────
class Pipeline:
    """Main pipeline orchestrator — coordinates all modules."""

    def __init__(self, args):
        self.args = args
        self.downloader = ImageDownloader()
        self.dataset_handler = DatasetHandler()
        self.yolo_filter = YOLOFilter(model_name=args.yolo_model)
        self.file_manager = FileManager()
        self.run_logger = RunLogger()
        self.cdn_extractor = CDNExtractor()

        # Parse tier filter
        self.filter_tiers = None
        if args.tiers:
            self.filter_tiers = {int(t.strip()) for t in args.tiers.split(",")}

    def run(self):
        """Execute the pipeline."""
        config.ensure_directories()

        print("\n" + "=" * 70)
        print("  AUTONOMOUS CAR DATASET COLLECTION PIPELINE")
        print("=" * 70 + "\n")

        if self.args.filter_only:
            self._run_filter_only()
            return

        if self.args.organize_only:
            self._run_organize_only()
            return

        # Full pipeline
        asyncio.run(self._run_full_pipeline())

    async def _run_full_pipeline(self):
        """Run the complete pipeline: read → scrape → filter → organize."""
        try:
            from tqdm import tqdm
        except ImportError:
            tqdm = None

        # ── Step 1: Read Excel and build job queue ───────────────────
        print("Step 1: Reading Excel file and building job queue...")
        reader = ExcelReader()
        jobs = reader.read_jobs(
            filter_make=self.args.make,
            filter_model=self.args.model,
        )
        reader.write_errors()

        summary = reader.get_job_summary(jobs)
        print(f"  >> {summary['total_jobs']} active jobs")
        print(f"  >> {summary.get('unique_makes', 0)} makes, {summary.get('unique_models', 0)} models")
        print()

        if not jobs:
            print("No jobs to process. Check your filters and Excel file.")
            return

        # ── Group jobs by Make + Model ───────────────────────────────
        model_groups = defaultdict(list)
        for job in jobs:
            key = (job["make"], job["model"])
            model_groups[key].append(job)

        total_models = len(model_groups)
        print(f"Processing {total_models} model groups...\n")

        # ── Pre-load YOLO model ──────────────────────────────────────
        print("Loading YOLO model...")
        self.yolo_filter.load_model()
        print("  → YOLO model ready\n")

        # ── Process each Make + Model ────────────────────────────────
        browser = BrowserController(headed=self.args.headed)
        browser_started = False

        model_iter = enumerate(model_groups.items(), 1)
        if tqdm:
            model_iter_pbar = tqdm(
                model_groups.items(),
                total=total_models,
                desc="Models",
                unit="model",
            )
        else:
            model_iter_pbar = None

        for idx, ((make, model), model_jobs) in enumerate(model_groups.items(), 1):
            model_start = time.time()
            print(f"\n{'-' * 60}")
            print(f"[{idx}/{total_models}] {make} {model}")
            print(f"{'-' * 60}")

            all_downloaded = []
            colors_detected = set()
            urls_processed = 0
            error_count = 0

            for job in model_jobs:
                url = job["url"]
                tier = job["tier"]
                source_type = job["source_type"]

                # ── Classify URL ─────────────────────────────────────
                url_type, type_desc = URLClassifier.classify(url)
                print(f"  URL type: {URLClassifier.get_type_label(url_type)}")
                urls_processed += 1

                try:
                    if url_type == TYPE_DIRECT_IMAGE or url_type == TYPE_CDN_URL:
                        # ── Types A/B: Direct download ───────────────
                        paths = self.downloader.download_batch(
                            [url], make, model, referer=url
                        )
                        all_downloaded.extend(paths)

                    elif url_type == TYPE_KAGGLE:
                        # ── Type C: Kaggle dataset ───────────────────
                        paths = self.dataset_handler.handle_kaggle(url, make, model)
                        all_downloaded.extend(paths)

                    elif url_type == TYPE_ROBOFLOW:
                        # ── Type D: Roboflow ─────────────────────────
                        if not browser_started:
                            await browser.start()
                            browser_started = True
                        image_urls = await self.dataset_handler.handle_roboflow(
                            url, make, model, browser
                        )
                        if image_urls:
                            paths = self.downloader.download_batch(
                                image_urls, make, model, referer=url
                            )
                            all_downloaded.extend(paths)

                    elif url_type == TYPE_OPEN_IMAGES:
                        # ── Type E: Open Images ──────────────────────
                        paths = self.dataset_handler.handle_open_images(url, make, model)
                        all_downloaded.extend(paths)

                    elif url_type == TYPE_GALLERY:
                        # ── Type F: Full browser automation ──────────
                        if not browser_started:
                            await browser.start()
                            browser_started = True

                        success = await browser.navigate(url)
                        if not success:
                            error_count += 1
                            continue

                        # Full extraction: scroll + colors + pagination
                        navigator = Navigator(browser, self.cdn_extractor)
                        color_results = await navigator.full_page_extraction(url, make, model)

                        # Discover and process variant pages
                        variant_links = await navigator.discover_variant_links(url)
                        for variant_url in variant_links[:3]:  # Limit variants to avoid over-scraping
                            success = await browser.navigate(variant_url)
                            if success:
                                variant_colors = await navigator.full_page_extraction(variant_url, make, model)
                                for color, urls in variant_colors.items():
                                    if color in color_results:
                                        color_results[color].update(urls)
                                    else:
                                        color_results[color] = urls

                        # If no results found, it returns {None: set(urls)} or {}
                        if not color_results or (len(color_results) == 1 and None in color_results and not color_results[None]):
                            logger.warning(f"  No images discovered for {model}")
                            continue

                        for color_name, urls in color_results.items():
                            if not urls:
                                continue
                            
                            display_color = color_name if color_name else "Default"
                            logger.info(f"  Processing {len(urls)} URLs for color: {display_color}")
                            
                            # Add detected color to the set for logging
                            if color_name:
                                colors_detected.add(color_name)

                            # Download and pass to YOLO for each color group (using browser to bypass blocks)
                            if not hasattr(self.downloader, 'download_batch_via_browser'):
                                # Fallback if method missing
                                paths = self.downloader.download_batch(
                                    urls, make, model, color_name, referer=url
                                )
                            else:
                                paths = await self.downloader.download_batch_via_browser(
                                    urls=urls, 
                                    make=make, 
                                    model=model, 
                                    browser_context=browser.context, 
                                    color=color_name, 
                                    referer=url
                                )
                            all_downloaded.extend(paths)

                        self.cdn_extractor.reset()

                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    error_count += 1

            # ── YOLO Filtering ───────────────────────────────────────
            if all_downloaded:
                print(f"  Filtering {len(all_downloaded)} images...")
                self.yolo_filter.reset_stats()
                approved, rejected = self.yolo_filter.filter_batch(all_downloaded)

                # ── File Organization ──────────────────────────────────
                if len(approved) > 0 or len(rejected) > 0:
                    if self.args.flat:
                        # Flat mode: merge all into one folder
                        final_paths = self.file_manager.organize_images(
                            approved, make, model, flat=True
                        )
                        print(f"  [OK] {len(final_paths)} images approved (flat)")
                    else:
                        saved, rej = self.file_manager.organize_saved_rejected(
                            approved, rejected, make, model
                        )
                        print(f"  [OK] {len(saved)} saved, {len(rej)} rejected")
                else:
                    print(f"  [--] No images passed filtering")

                images_downloaded = len(all_downloaded)
                images_approved = len(approved)
                images_rejected = len(rejected)
            else:
                images_downloaded = 0
                images_approved = 0
                images_rejected = 0
                print(f"  [--] No images downloaded")

            # ── Log results ──────────────────────────────────────────
            duration = time.time() - model_start
            self.run_logger.log_model(
                make=make,
                model=model,
                tier=model_jobs[0]["tier"],
                source_type=model_jobs[0]["source_type"],
                urls_processed=urls_processed,
                images_downloaded=images_downloaded,
                images_approved=images_approved,
                images_rejected=images_rejected,
                colors_detected=list(colors_detected),
                duration_seconds=duration,
                error_count=error_count,
            )

            print(f"  Time: {duration:.0f}s")

            if model_iter_pbar:
                model_iter_pbar.update(1)

        # ── Cleanup ──────────────────────────────────────────────────
        if browser_started:
            await browser.close()

        self.downloader.write_errors()
        self.dataset_handler.write_errors()

        # ── Final summary ────────────────────────────────────────────
        self._print_summary()

    def _run_filter_only(self):
        """Run YOLO filtering on all images in temp_dataset."""
        print("Running YOLO filtering on existing temp_dataset...\n")

        # Find all images in temp_dataset
        image_paths = []
        if os.path.exists(config.TEMP_DATASET_DIR):
            for f in os.listdir(config.TEMP_DATASET_DIR):
                _, ext = os.path.splitext(f)
                if ext.lower() in config.VALID_IMAGE_EXTENSIONS:
                    image_paths.append(os.path.join(config.TEMP_DATASET_DIR, f))

        if not image_paths:
            print("No images found in temp_dataset/")
            return

        print(f"Found {len(image_paths)} images to filter\n")

        try:
            from tqdm import tqdm
            pbar = tqdm(total=len(image_paths), desc="Filtering", unit="img")
        except ImportError:
            pbar = None

        self.yolo_filter.load_model()
        approved, rejected = self.yolo_filter.filter_batch(image_paths, pbar)

        if pbar:
            pbar.close()

        print(f"\n  [OK] Approved: {len(approved)}")
        print(f"  [--] Rejected: {len(rejected)}")

        print(f"\nApproved images remain in temp_dataset/")
        print(f"Rejected images moved to rejected_images/")

    def _run_organize_only(self):
        """Organize already-filtered images from temp_dataset to final_dataset."""
        print("Organizing images from temp_dataset to final_dataset...\n")

        # Parse temp filenames to group by make/model/color
        groups = defaultdict(list)

        if os.path.exists(config.TEMP_DATASET_DIR):
            for f in os.listdir(config.TEMP_DATASET_DIR):
                _, ext = os.path.splitext(f)
                if ext.lower() not in config.VALID_IMAGE_EXTENSIONS:
                    continue

                path = os.path.join(config.TEMP_DATASET_DIR, f)

                # Parse: temp_{make}_{model}_{color?}_{seq}.ext
                parts = f.replace("temp_", "").split("_")
                if len(parts) >= 3:
                    make = parts[0].title()
                    model = parts[1].title()
                    color = None
                    if len(parts) >= 4:
                        # Last part is sequence, middle parts might be color
                        try:
                            int(parts[-1].split(".")[0])
                            if len(parts) > 3:
                                color = "_".join(parts[2:-1]).title()
                        except ValueError:
                            pass

                    groups[(make, model, color)].append(path)

        if not groups:
            print("No images found in temp_dataset/")
            return

        for (make, model, color), paths in groups.items():
            final = self.file_manager.organize_images(paths, make, model, color)
            label = f"{make} {model}" + (f" ({color})" if color else "")
            print(f"  {label}: {len(final)} images organized")

        dataset_summary = FileManager.get_dataset_summary()
        print(f"\nFinal dataset: {dataset_summary['makes']} makes, "
              f"{dataset_summary['models']} models, "
              f"{dataset_summary['total_images']} total images")

    def _print_summary(self):
        """Print the final pipeline run summary."""
        print("\n" + "=" * 70)
        print("  PIPELINE RUN COMPLETE")
        print("=" * 70)

        dl_stats = self.downloader.get_stats()
        fm_stats = self.file_manager.get_stats()
        dataset = FileManager.get_dataset_summary()
        filter_stats = self.yolo_filter.get_stats()

        print(f"\n  Images downloaded:  {dl_stats['downloaded']}")
        print(f"  Images organized:   {fm_stats['moved']}")
        print(f"  Download errors:    {dl_stats['errors']}")

        print(f"\n  Rejections:")
        print(f"    No car detected:   {filter_stats.get('rejected_no_car', 0)}")
        print(f"    Low confidence:    {filter_stats.get('rejected_low_conf', 0)}")
        print(f"    Too small:         {filter_stats.get('rejected_too_small', 0)}")
        print(f"    Partial/incomplete:{filter_stats.get('rejected_partial', 0)}")
        print(f"    Interior views:    {filter_stats.get('rejected_interior', 0)}")
        print(f"    Errors:            {filter_stats.get('rejected_error', 0)}")

        print(f"\n  Final dataset:")
        print(f"    Makes:   {dataset['makes']}")
        print(f"    Models:  {dataset['models']}")
        print(f"    Images:  {dataset['total_images']}")
        print(f"\n  Logs: {config.RUN_LOG_PATH}")
        print(f"  Errors: {config.ERRORS_LOG_PATH}")
        print()


# ─── Entry Point ─────────────────────────────────────────────────────────────
def main():
    """Main entry point."""
    args = parse_args()

    if args.output_dir:
        config.FINAL_DATASET_DIR = os.path.abspath(os.path.expanduser(args.output_dir))

    setup_logging()

    # Validate args
    if args.model and not args.make:
        print("Error: --model requires --make to be set.")
        sys.exit(1)

    pipeline = Pipeline(args)
    pipeline.run()


if __name__ == "__main__":
    main()
