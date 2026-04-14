import asyncio
import os
import sys
import logging

# Set up logging for the test
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
)
logger = logging.getLogger("test_navigation")

# Ensure the project root is in Python path
base_dir = r"c:\Users\kotla\Downloads\NEW AGENT\car_pipeline"
sys.path.insert(0, base_dir)

from scraper.browser import BrowserController
from scraper.cdn_extractor import CDNExtractor
from scraper.navigator import Navigator
import config

async def test_official_site():
    # Use headed mode so we can see what's happening if needed (though running in background)
    browser = BrowserController(headed=False)
    extractor = CDNExtractor()
    navigator = Navigator(browser, extractor)
    
    try:
        await browser.start()
        
        # Test URL: Acura ADX Gallery (representative of a modern official site)
        url = 'https://www.acura.com/suvs/2026/adx/gallery'
        make = "Acura"
        model = "ADX"
        
        logger.info(f"Navigating to {url}...")
        success = await browser.navigate(url)
        if not success:
            logger.error("Failed to navigate to the test URL.")
            return

        # Give it a moment to settle
        await browser.wait(3)
        
        logger.info("Starting full page extraction...")
        # This will trigger: scroll, color clicks, pagination
        color_results = await navigator.full_page_extraction(url, make, model)
        
        logger.info(f"Extraction complete. Found {len(color_results)} color groups.")
        
        total_urls = 0
        for color, urls in color_results.items():
            color_name = color if color else "Default"
            logger.info(f"  Color: {color_name} -> {len(urls)} URLs")
            total_urls += len(urls)
            if urls:
                logger.info(f"    Sample: {list(urls)[0]}")
        
        if total_urls > 0:
            logger.info(f"SUCCESS: Found {total_urls} total image URLs.")
        else:
            logger.error("FAILURE: No image URLs found.")
            
    except Exception as e:
        logger.error(f"An error occurred during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_official_site())
