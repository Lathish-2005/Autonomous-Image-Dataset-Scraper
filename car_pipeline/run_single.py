import os
import sys
import argparse
import asyncio
import logging

from scraper.browser import BrowserController
from scraper.cdn_extractor import CDNExtractor
from scraper.navigator import Navigator
from scraper.downloader import ImageDownloader
from vision.yolo_filter import YOLOFilter
from organizer.file_manager import FileManager
import config

# python run_single.py --make Acura --model TLX --url "https://www.google.com/search?q=acura+tlx"

# "python run_single.py --make "Tata" --model "Nexon" --url "https://example.com/tata-nexon" --output-dir "car_pipeline\final_dataset\Indian"
# "


# Set up logging specifically for the single runner
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("run_single")

async def process_single_url(make, model, target_url, headed=False, flat=False, color=None, scenario=None):
    """
    Run the entire car image pipeline on a single URL.
    """
    config.ensure_directories()
    
    logger.info("=" * 60)
    logger.info(f"  SINGLE URL PIPELINE: {make} {model}")
    logger.info(f"  Target: {target_url}")
    logger.info("=" * 60)
    
    # ── Initialize Components ──
    downloader = ImageDownloader()
    cdn_extractor = CDNExtractor()
    yolo_filter = YOLOFilter(model_name="yolov8m.pt")
    file_manager = FileManager()
    
    if not yolo_filter.load_model():
        logger.error("Failed to load YOLO model. Exiting.")
        sys.exit(1)
        
    browser = BrowserController(headed=headed)
    await browser.start()
    
    try:
        logger.info("Navigating to target URL...")
        success = await browser.navigate(target_url)
        if not success:
            logger.error("Failed to load the URL.")
            return
            
        logger.info("Waiting 5 seconds for dynamic content (lazy-loading pins/images)...")
        await asyncio.sleep(5)
            
        navigator = Navigator(browser, cdn_extractor)
        
        # ── Step 1: Extract Image URLs ──
        logger.info("Extracting image URLs from page...")
        color_urls = await navigator.full_page_extraction(target_url, make, model)
        
        # (Optional) check variant links if applicable
        variant_links = await navigator.discover_variant_links(target_url)
        for variant_url in variant_links[:3]:  # Limit to 3 variants to avoid infinite crawl
            v_success = await browser.navigate(variant_url)
            if v_success:
                variant_colors = await navigator.full_page_extraction(variant_url, make, model)
                for color, urls in variant_colors.items():
                    if color in color_urls:
                        color_urls[color].update(urls)
                    else:
                        color_urls[color] = urls
                        
        total_urls = sum(len(urls) for urls in color_urls.values())
        if total_urls == 0:
            logger.warning(f"No valid URLs found bridging {make} {model} at {target_url}.")
            return
            
        logger.info(f"Found {total_urls} valid URLs across {len([c for c in color_urls if c])} colors.")
        
        # ── Step 2: Download Images (via browser context) ──
        all_downloaded = []
        for color, urls in color_urls.items():
            if not urls:
                continue
            # Use browser-context downloads to share session/cookies with the browser
            paths = await downloader.download_batch_via_browser(
                urls, make, model, browser.context, color, referer=target_url
            )
            all_downloaded.extend(paths)
            
        if not all_downloaded:
            logger.warning("No images successfully downloaded.")
            return
            
        # ── Step 3: Vision Filtering (skipped if scenario provided) ──
        if scenario:
            logger.info("Skipping YOLO vision filtering because scenario is provided.")
            approved = all_downloaded
            rejected = []
        else:
            logger.info(f"Filtering {len(all_downloaded)} downloaded images with YOLO...")
            approved, rejected = yolo_filter.filter_batch(all_downloaded)
            logger.info(f"YOLO Filter complete: {len(approved)} approved, {len(rejected)} rejected.")

            # ── Step 4: Organization ──
            if len(approved) == 0 and len(rejected) == 0:
                logger.warning("No images passed the vision filter.")
                return

        logger.info("Organizing images...")
        if scenario:
            final_paths = file_manager.organize_scenario(approved, color or "DefaultColor", scenario)
            logger.info(f"Success! Organized {len(final_paths)} images for scenario {scenario}.")
        elif flat:
            organized = file_manager.organize_images(approved, make, model, flat=True)
            logger.info(f"Success! Organized {len(organized)} images (flat).")
        elif color:
            saved, rej = file_manager.organize_color_dataset(approved, rejected, color)
            logger.info(f"Success! Organized {len(saved)} saved, {len(rej)} rejected for color {color}.")
        else:
            saved, rej = file_manager.organize_saved_rejected(approved, rejected, make, model)
            logger.info(f"Success! Organized {len(saved)} saved, {len(rej)} rejected.")
        
    finally:
        await browser.close()
        logger.info("Browser closed. Pipeline finished.")

def main():
    parser = argparse.ArgumentParser(description="Run the car pipeline on a single unlisted URL.")
    parser.add_argument("--make", type=str, default="Vehicle", help="Car make (e.g., Acura)")
    parser.add_argument("--model", type=str, default="Unknown", help="Car model (e.g., NSX)")
    parser.add_argument("--url", required=True, type=str, help="Target URL to scrape")
    parser.add_argument("--color", type=str, default=None, help="Specific color for the dataset extraction (bypasses Make/Model subfolders)")
    parser.add_argument("--scenario", type=str, default=None, help="Specific scenario for the dataset (e.g., 'day light scenario'). Bypasses YOLO segregation.")
    parser.add_argument("--headed", action="store_true", help="Run browser in visible mode")
    parser.add_argument("--output-dir", type=str, default=None, help="Custom folder path to save organized images")
    parser.add_argument("--flat", action="store_true", help="Save images directly into --output-dir without creating Make/Model subfolders")
    
    args = parser.parse_args()

    if args.output_dir:
        config.FINAL_DATASET_DIR = os.path.abspath(os.path.expanduser(args.output_dir))
    
    # Run async loop
    asyncio.run(process_single_url(
        make=args.make,
        model=args.model,
        target_url=args.url,
        headed=args.headed,
        flat=args.flat,
        color=args.color,
        scenario=args.scenario
    ))

if __name__ == "__main__":
    main()
