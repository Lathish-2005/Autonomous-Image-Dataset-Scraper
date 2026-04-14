import asyncio
import os
import sys
import re
from scraper.browser import BrowserController

async def debug():
    browser = BrowserController(headed=False)
    await browser.start()
    url = 'https://www.acura.com/suvs/2026/adx/gallery'
    print(f"Navigating to {url}...")
    await browser.navigate(url)
    await asyncio.sleep(10) # Give plenty of time for official site JS
    
    content = await browser.get_page_content()
    print(f"HTML Length: {len(content)}")
    
    # 1. Look for all high-res image extensions
    imgs = re.findall(r'https?://[^\s\"\'\>]+?\.(?:jpg|jpeg|png|webp)', content)
    print(f"Total potential image URLs in HTML: {len(imgs)}")
    
    # 2. Look for specific Acura CDN domains
    acura_imgs = [img for img in imgs if 'acura.com' in img or 'honda' in img or 'widencdn.net' in img]
    print(f"Acura/Honda/Widen specific URLs: {len(acura_imgs)}")
    for img in acura_imgs[:15]:
        print(f"  {img}")
        
    # 3. Search for specific tags
    print(f"Picture tags: {content.count('<picture')}")
    print(f"Source tags: {content.count('<source')}")
    print(f"Img tags: {content.count('<img')}")
    
    # Write a snippet to a file for manual inspection if needed
    with open('acura_debug_snippet.html', 'w', encoding='utf-8') as f:
        f.write(content[:50000]) # First 50k chars
        
    await browser.close()

if __name__ == '__main__':
    asyncio.run(debug())
