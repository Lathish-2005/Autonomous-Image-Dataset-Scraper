import asyncio
import os
import sys
from scraper.browser import BrowserController
from scraper.cdn_extractor import CDNExtractor

async def test_rdx():
    browser = BrowserController(headed=False)
    await browser.start()
    
    url = 'https://www.pinterest.com/search/pins/?q=acura+rdx+exterior'
    print(f"Navigating to {url}...")
    await browser.navigate(url)
    
    print("Waiting 8 seconds for JS...")
    await asyncio.sleep(8)
    
    content = await browser.get_page_content()
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, 'lxml')
    img_tags = soup.find_all('img')
    print(f"BeautifulSoup found {len(img_tags)} <img> tags.")
    if img_tags:
        print(f"First img tag: {str(img_tags[0])[:200]}")
    
    extractor = CDNExtractor()
    # Check if anything is found without make/model first
    urls = extractor.extract(content, url, None, None)
    print(f"Extracted WITHOUT make/model: {len(urls)}")
    
    # Check with make/model
    urls_filtered = extractor.extract(content, url, "Acura", "RDX")
    print(f"Extracted WITH Acura RDX: {len(urls_filtered)}")
    
    if len(urls) > 0:
        print("Sample URLs:")
        for u in list(urls)[:5]:
            print(f"  {u}")
            
    await browser.close()

if __name__ == '__main__':
    asyncio.run(test_rdx())
