"""
Navigator Module
Handles page interactions: color swatches, pagination arrows, and variant links.
Works with the BrowserController to click through gallery elements and collect
all image URLs across different states of the page.
"""

import os
import sys
import logging
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


class Navigator:
    """Navigates gallery pages: clicks colors, arrows, pagination, and variant links."""

    def __init__(self, browser_controller, cdn_extractor):
        """
        Args:
            browser_controller: BrowserController instance
            cdn_extractor: CDNExtractor instance
        """
        self.browser = browser_controller
        self.extractor = cdn_extractor

    async def full_page_extraction(self, page_url, make=None, model=None):
        """
        Perform the complete extraction process on a page:
        1. Scroll the full page
        2. Initial DOM scan
        3. Click all color swatches (collect URLs per color)
        4. Handle pagination / carousel arrows
        5. Return collected URLs with color tags

        Args:
            page_url: URL of the page being processed

        Returns:
            Dict of { color_name: set(urls) }
            If no colors detected, returns { None: set(urls) }
        """
        color_urls = {}

        # ── Step 1: Scroll full page ─────────────────────────────────
        await self.browser.scroll_full_page()

        # ── Step 2: Initial DOM scan ─────────────────────────────────
        html = await self.browser.get_page_content()
        initial_urls = self.extractor.extract(html, page_url, make, model)
        logger.info(f"Initial scan: {len(initial_urls)} URLs found")

        # ── Step 2a: Fallback to live DOM if static HTML found nothing ─
        #    React/Vue/Angular sites render images via JS, so BeautifulSoup
        #    may see an empty shell. Use JS page.evaluate() as fallback.
        if len(initial_urls) == 0:
            logger.info("Static HTML yielded 0 URLs, trying live DOM extraction...")
            live_dom_urls = await self.browser.extract_images_from_live_dom()
            if live_dom_urls:
                processed = self.extractor.process_raw_urls(live_dom_urls, page_url, make, model)
                initial_urls.update(processed)
                logger.info(f"Live DOM fallback: {len(processed)} URLs recovered")

        # ── Step 2b: Configurator / Canvas Fallback ───────────────────
        # If we STILL have no useful URLs, OR we're on a known configurator domain,
        # OR the page has a massive canvas, use the screenshot capture approach.
        is_configurator_url = any(p in page_url.lower() for p in config.CONFIGURATOR_URL_PATTERNS)
        has_canvas = await self.browser.has_canvas_renderer()
        
        if config.SCREENSHOT_ENABLED and (is_configurator_url or has_canvas or len(initial_urls) == 0):
            if has_canvas or is_configurator_url:
                logger.info(f"Detected WebGL/Configurator page. Using screenshot capture mode.")
                return await self._handle_configurator_page()

        # ── Step 2.5: Click gallery tabs (Exterior / Interior) ───────
        gallery_urls = await self._handle_gallery_tabs(page_url, make, model)
        if gallery_urls:
            initial_urls.update(gallery_urls)
            logger.info(f"Gallery tabs added {len(gallery_urls)} URLs")

        # ── Step 3: Click color swatches ─────────────────────────────
        colors_found = await self._handle_color_swatches(page_url, make, model)

        if colors_found:
            color_urls = colors_found
            # Add initial URLs to the first color or as untagged
            if initial_urls:
                # Associate initial URLs with "default" if we have colors
                if None not in color_urls:
                    color_urls[None] = set()
                color_urls[None].update(initial_urls)
        else:
            color_urls[None] = initial_urls

        # ── Step 4: Handle pagination/arrows ─────────────────────────
        pagination_urls = await self._handle_pagination(page_url, make, model)
        if pagination_urls:
            if None not in color_urls:
                color_urls[None] = set()
            color_urls[None].update(pagination_urls)

        # ── Step 4.5: Click Load More buttons ─────────────────────────
        load_more_urls = await self._handle_load_more(page_url, make, model)
        if load_more_urls:
            if None not in color_urls:
                color_urls[None] = set()
            color_urls[None].update(load_more_urls)

        # ── Step 5: Collect intercepted network URLs ─────────────────
        network_urls = self.browser.get_network_urls()
        if network_urls:
            processed_network = self.extractor.process_raw_urls(network_urls, page_url, make, model)
            if processed_network:
                if None not in color_urls:
                    color_urls[None] = set()
                color_urls[None].update(processed_network)
                logger.info(f"Adding {len(processed_network)} URLs from network traffic")

        # Summary
        total = sum(len(urls) for urls in color_urls.values())
        colors_count = len([k for k in color_urls if k is not None])
        logger.info(
            f"Page extraction complete: {total} total URLs, "
            f"{colors_count} colors detected"
        )

        return color_urls

    async def _handle_color_swatches(self, page_url, make=None, model=None):
        """
        Detect and click through all color swatches on the page.

        Returns:
            Dict of { color_name: set(urls) } or empty dict if no colors found
        """
        color_results = {}

        for selector in config.COLOR_SWATCH_SELECTORS:
            elements = await self.browser.get_elements(selector)
            if not elements:
                continue

            logger.info(f"Found {len(elements)} color swatches with selector: {selector}")

            for idx, element in enumerate(elements):
                try:
                    # Get color name from the element
                    color_name = await self._get_color_name(element)
                    if not color_name:
                        color_name = f"Color_{idx+1}"

                    # Click the color swatch
                    logger.info(f"  Attempting to click color swatch: {color_name}")
                    
                    # Ensure element is in view before clicking
                    await element.scroll_into_view_if_needed()
                    await self.browser.wait(0.5)
                    
                    await element.click()
                    await self.browser.wait(config.COLOR_CLICK_WAIT)
                    
                    # Scroll after clicking to trigger any color-specific lazy loads
                    await self.browser.scroll_full_page()

                    # Extract URLs after color change (DOM + Network)
                    html = await self.browser.get_page_content()
                    urls = self.extractor.extract(html, page_url, make, model)
                    
                    # Also include network URLs captured during the wait
                    network_urls = self.browser.get_network_urls()
                    if network_urls:
                        processed_network = self.extractor.process_raw_urls(network_urls, page_url, make, model)
                        urls.update(processed_network)

                    if urls:
                        if color_name in color_results:
                            color_results[color_name].update(urls)
                        else:
                            color_results[color_name] = urls
                        logger.info(f"  Color '{color_name}': {len(urls)} URLs")
                    else:
                        logger.debug(f"  No new images found for color '{color_name}'")

                except Exception as e:
                    logger.debug(f"  Error clicking color swatch: {e}")
                    continue

            # We DO NOT break here anymore. We want to test all selector 
            # groups in case there are multiple types of swatches (e.g., exterior & interior)

        return color_results

    async def _handle_configurator_page(self):
        """
        Handle a 3D Canvas / WebGL configurator page.
        Instead of URLs, this returns dictionary containing raw screenshot bytes
        with a special 'bytes:' prefix marker.
        """
        logger.info("Configurator mode: Waiting for 3D render...")
        await self.browser.wait(config.CANVAS_RENDER_WAIT)

        color_results = {}
        screenshot_count = 0
        
        # 1. Grab initial default snapshot
        initial_shot = await self.browser.capture_car_screenshot()
        if initial_shot:
            color_results[None] = set([("bytes:", initial_shot)])
            screenshot_count += 1
            logger.info("Configurator mode: Captured default view screenshot")

        # 2. Iterate colors (BMW + Generic selectors)
        all_swatch_selectors = config.BMW_COLOR_SWATCH_SELECTORS + config.COLOR_SWATCH_SELECTORS
        swatch_elements = []
        
        for selector in all_swatch_selectors:
            elements = await self.browser.get_elements(selector)
            if elements:
                logger.info(f"Configurator mode: Found {len(elements)} colors with {selector}")
                swatch_elements.extend(elements)
                
        # Deduplicate elements by position or let Playwright handle
        clicked_color_names = set()
        
        # For BMW configurator, don't click more than ~15 colors to avoid taking hours
        max_colors_to_click = min(15, len(swatch_elements))
        
        for idx in range(max_colors_to_click): 
            if screenshot_count >= config.MAX_SCREENSHOTS_PER_MODEL:
                break
                
            try:
                # RE-QUERY elements because clicking angles/colors can detach previous handles from DOM in React/SPAs
                current_swatches = []
                for selector in all_swatch_selectors:
                    elems = await self.browser.get_elements(selector)
                    if elems:
                        current_swatches.extend(elems)
                
                # If DOM changed so much we lost the elements, bail
                if idx >= len(current_swatches):
                    break
                    
                element = current_swatches[idx]

                # Check visibility
                if not await element.is_visible():
                    continue

                color_name = await self._get_color_name(element)
                if not color_name or color_name in clicked_color_names:
                    if color_name in clicked_color_names:
                        continue 
                    color_name = f"Color_{idx+1}"
                    
                clicked_color_names.add(color_name)
                logger.info(f"Configurator mode: Selecting color '{color_name}'")
                
                await element.scroll_into_view_if_needed()
                await self.browser.wait(0.5)
                await element.click()
                
                # Wait for 3D model to re-render paint material
                await self.browser.wait(config.SCREENSHOT_WAIT_AFTER_COLOR_CLICK)
                
                color_set = color_results.setdefault(color_name, set())
                
                # Capture base shot for this color
                shot = await self.browser.capture_car_screenshot()
                if shot:
                    color_set.add(("bytes:", shot))
                    screenshot_count += 1

                # 3. Angle Rotations
                # Find the working selector first
                active_angle_selector = None
                for a_sel in config.CONFIGURATOR_ANGLE_SELECTORS:
                    a_elems = await self.browser.get_elements(a_sel)
                    if a_elems:
                        for el in a_elems:
                            if await el.is_visible():
                                active_angle_selector = a_sel
                                break
                        if active_angle_selector:
                            break
                
                if active_angle_selector:
                    captures = 0
                    logger.info(f"Configurator mode: Rotating through angles")
                    
                    while captures < config.MAX_ANGLE_CAPTURES - 1 and screenshot_count < config.MAX_SCREENSHOTS_PER_MODEL:
                        # Re-query rotation button every click to avoid detached elements
                        a_elems = await self.browser.get_elements(active_angle_selector)
                        if not a_elems:
                            break
                            
                        rotate_btn = None
                        for el in a_elems:
                            if await el.is_visible() and not await self.browser.is_element_disabled(el):
                                rotate_btn = el
                                break
                                
                        if not rotate_btn:
                            break
                            
                        await rotate_btn.click()
                        await self.browser.wait(config.SCREENSHOT_WAIT_AFTER_ANGLE_CLICK)
                        
                        shot = await self.browser.capture_car_screenshot()
                        if shot:
                            color_set.add(("bytes:", shot))
                            screenshot_count += 1
                        captures += 1

            except Exception as e:
                logger.warning(f"Configurator mode interaction error on color {idx}: {e}")
                continue

        logger.info(f"Configurator mode complete: Captured {screenshot_count} screenshots")
        return color_results

    async def _get_color_name(self, element):
        """
        Extract a human-readable color name from a swatch element.
        Tries data attributes, aria-label, title, and text content.
        """
        # Try common attributes
        for attr in ("data-color", "data-variant", "aria-label", "title", "alt"):
            value = await self.browser.get_element_attribute(element, attr)
            if value and len(value.strip()) > 0:
                return self._format_color_name(value.strip())

        # Try text content
        text = await self.browser.get_element_text(element)
        if text and len(text.strip()) > 0 and len(text.strip()) < 50:
            return self._format_color_name(text.strip())

        return None

    def _format_color_name(self, raw_name):
        """Clean and format a color name for folder naming."""
        # Remove "color" prefix if present
        name = raw_name
        for prefix in ("color:", "color ", "select "):
            if name.lower().startswith(prefix):
                name = name[len(prefix):]

        # Title case and replace spaces with underscores
        name = name.strip().title()
        name = name.replace(" ", "_")

        # Remove special characters
        safe = ""
        for ch in name:
            if ch.isalnum() or ch == "_":
                safe += ch

        return safe if safe else None

    async def _handle_gallery_tabs(self, page_url, make=None, model=None):
        """
        Click through gallery category tabs (e.g., Exterior, Interior)
        to trigger lazy-loaded image sections.

        Returns:
            Set of image URLs found across all tabs
        """
        all_urls = set()
        clicked_tabs = set()

        for selector in config.GALLERY_TAB_SELECTORS:
            elements = await self.browser.get_elements(selector)
            if not elements:
                continue

            logger.info(f"Found {len(elements)} gallery tabs with selector: {selector}")

            for element in elements:
                try:
                    # Get tab label to avoid clicking same tab twice
                    label = await self.browser.get_element_text(element)
                    if not label:
                        label = await self.browser.get_element_attribute(element, "aria-label")
                    label = (label or "").strip().lower()

                    if label in clicked_tabs:
                        continue

                    # Check visibility
                    is_visible = await element.is_visible()
                    if not is_visible:
                        continue

                    # Click the tab
                    await element.click()
                    clicked_tabs.add(label)
                    await self.browser.wait(2.0)  # Wait for content to load

                    # Scroll within the newly visible section
                    await self.browser.scroll_full_page()

                    # Extract URLs
                    html = await self.browser.get_page_content()
                    urls = self.extractor.extract(html, page_url, make, model)
                    all_urls.update(urls)

                    logger.info(f"  Gallery tab '{label}': {len(urls)} URLs")

                except Exception as e:
                    logger.debug(f"  Error clicking gallery tab: {e}")
                    continue

            # Don't break, keep looking for other gallery tabs

        if clicked_tabs:
            logger.info(f"Gallery tabs: clicked {len(clicked_tabs)} tabs, {len(all_urls)} total URLs")

        return all_urls

    async def _handle_pagination(self, page_url, make=None, model=None):
        """
        Click through pagination/carousel Next buttons until exhausted.

        Returns:
            Set of all image URLs found across all pages/slides
        """
        all_urls = set()
        click_count = 0
        max_clicks = 50  # Safety limit

        for selector in config.NEXT_BUTTON_SELECTORS:
            elements = await self.browser.get_elements(selector)
            if not elements:
                continue

            logger.info(f"Found pagination with selector: {selector}")

            while click_count < max_clicks:
                try:
                    # Find the Next button
                    next_btn = await self.browser.page.query_selector(selector)
                    if not next_btn:
                        break

                    # Check if disabled
                    if await self.browser.is_element_disabled(next_btn):
                        break

                    # Check visibility
                    is_visible = await next_btn.is_visible()
                    if not is_visible:
                        break

                    # Click the Next button
                    await next_btn.scroll_into_view_if_needed()
                    await self.browser.wait(0.5)
                    
                    await next_btn.click()
                    await self.browser.wait(2.0) # Increased wait for animation and loading
                    
                    # Scroll to trigger any lazy loading within slides
                    await self.browser.scroll_full_page()

                    # Extract URLs from the new state (DOM + Network)
                    html = await self.browser.get_page_content()
                    urls = self.extractor.extract(html, page_url, make, model)
                    
                    network_urls = self.browser.get_network_urls()
                    if network_urls:
                        processed_network = self.extractor.process_raw_urls(network_urls, page_url, make, model)
                        urls.update(processed_network)

                    if urls:
                        new_urls = urls - all_urls
                        if not new_urls and click_count > 5:
                            # If no new URLs found for several clicks, probably reached end of carousel
                            break
                        all_urls.update(urls)
                    
                    click_count += 1
                    logger.debug(f"  Pagination click {click_count}: {len(urls)} URLs in current view")

                except Exception as e:
                    logger.debug(f"  Pagination ended: {e}")
                    break

            # Let it try other selectors too

        if click_count > 0:
            logger.info(f"Pagination: {click_count} clicks, {len(all_urls)} total URLs")

        return all_urls

    async def _handle_load_more(self, page_url, make=None, model=None):
        """Click Load More buttons to reveal hidden images."""
        all_urls = set()
        click_count = 0
        max_clicks = 10
        
        for selector in config.LOAD_MORE_SELECTORS:
            elements = await self.browser.get_elements(selector)
            if not elements:
                continue

            for element in elements:
                while click_count < max_clicks:
                    try:
                        if not await element.is_visible():
                            break
                            
                        await element.scroll_into_view_if_needed()
                        await self.browser.wait(0.5)
                        await element.click()
                        await self.browser.wait(2.0)
                        await self.browser.scroll_full_page()
                        
                        html = await self.browser.get_page_content()
                        urls = self.extractor.extract(html, page_url, make, model)
                        
                        network_urls = self.browser.get_network_urls()
                        if network_urls:
                            processed_network = self.extractor.process_raw_urls(network_urls, page_url, make, model)
                            urls.update(processed_network)
                            
                        if urls:
                            new_urls = urls - all_urls
                            if not new_urls:
                                break
                            all_urls.update(urls)
                            
                        click_count += 1
                        
                        # Note: the element might be destroyed and recreated, so re-querying might be safer 
                        # but querying element multiple times if we can't find it breaks. 
                        # Playwright elements are robust to simple clicks.
                    except Exception as e:
                        logger.debug(f"  Load more ended: {e}")
                        break
                        
        if click_count > 0:
            logger.info(f"Load More: {click_count} clicks, {len(all_urls)} total URLs")
            
        return all_urls

    async def discover_variant_links(self, page_url):
        """
        Find links to sub-model/variant pages on the current page.

        Returns:
            List of variant page URLs
        """
        return await self.browser.find_internal_links(page_url)
