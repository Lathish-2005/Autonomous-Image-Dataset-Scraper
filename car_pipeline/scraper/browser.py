"""
Browser Controller Module
Manages Playwright Chromium browser sessions for web scraping.
Includes auto-dismissal of cookie/consent banners and robust page loading.
"""

import os
import sys
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)

# Common cookie/consent banner selectors used across car manufacturer sites
COOKIE_DISMISS_SELECTORS = [
    'button[id*="cookie" i][id*="accept" i]',
    'button[id*="cookie" i][id*="ok" i]',
    'button[id*="consent" i][id*="accept" i]',
    'button[class*="cookie" i][class*="accept" i]',
    'button[aria-label*="accept" i]',
    'button[aria-label*="agree" i]',
    'a[id*="cookie" i][id*="accept" i]',
    '#onetrust-accept-btn-handler',  # OneTrust (very common)
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',  # Cookiebot
    '.cookie-banner button.accept',
    '.cookie-consent button.accept',
    '.privacy-banner button',
    '[data-testid="cookie-accept"]',
    'button:has-text("Accept All")',
    'button:has-text("Accept Cookies")',
    'button:has-text("Accept all cookies")',
    'button:has-text("I agree")',
    'button:has-text("OK")',
    'button:has-text("Agree")',
    # Reject / Decline / Manage options (sometimes cleaner to just reject)
    'button:has-text("Reject All")',
    'button:has-text("Decline All")',
    'button[id*="reject" i]',
    'button[class*="reject" i]',
    'button[aria-label*="reject" i]',
    'button:has-text("Necessary only")',
    'button:has-text("Functional only")',
    # Specific manufacturer selectors
    '.toyota-cookie-accept',
    '#ford-cookie-accept',
    '.acura-consent-accept',
    'button:has-text("Manage Cookies")',
    'button:has-text("Cookie Settings")',
]

# Selectors for human verification challenges (to log them if they appear)
CHALLENGE_SELECTORS = [
    'iframe[src*="cloudflare" i]',
    'iframe[src*="recaptcha" i]',
    '#challenge-form',
    '#px-captcha',
]


class BrowserController:
    """Controls a Playwright Chromium browser for scraping gallery pages."""

    def __init__(self, headed=False):
        """
        Args:
            headed: If True, show the browser window (debug mode).
        """
        self.headed = headed
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.network_urls = set()

    async def start(self):
        """Launch the browser and create a new page."""
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=not self.headed,
            args=[
                "--disable-http2",           # Avoid ERR_HTTP2_PROTOCOL_ERROR on anti-bot sites
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self.context = await self.browser.new_context(
            user_agent=config.USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
            bypass_csp=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1",
            }
        )

        self.page = await self.context.new_page()

        # Apply stealth settings to bypass bot detection (edmunds, kbb, etc.)
        try:
            from playwright_stealth import Stealth
            stealth = Stealth()
            await stealth.apply_stealth_async(self.page)
            logger.info("Stealth mode applied")
        except ImportError:
            logger.warning("playwright-stealth not installed — bot detection may block some sites")
        except Exception as e:
            logger.warning(f"Stealth mode failed (non-fatal): {e}")

        # Intercept network requests to capture image URLs silently
        self.page.on("request", self._handle_request)

        # Block heavy non-image resources to speed up page loading
        await self.page.route("**/*.{mp4,webm,ogg,mp3,wav,flac,woff2,woff,ttf,eot}", 
                              lambda route: route.abort())

        logger.info(f"Browser launched ({'headed' if self.headed else 'headless'} mode)")

    async def extract_images_from_live_dom(self):
        """
        Extract image URLs directly from the live DOM using JavaScript.
        This captures images rendered by React, Vue, Angular, or other JS frameworks
        that may not appear in the static HTML returned by page.content().

        Returns:
            Set of image URLs found in the live DOM
        """
        try:
            urls = await self.page.evaluate("""
                () => {
                    const urls = new Set();
                    
                    // 1. All <img> tags: src, data-src, data-lazy, data-original, srcset
                    document.querySelectorAll('img').forEach(img => {
                        ['src', 'data-src', 'data-lazy', 'data-original', 'data-lazy-src'].forEach(attr => {
                            const val = img.getAttribute(attr);
                            if (val && !val.startsWith('data:') && !val.startsWith('blob:')) {
                                urls.add(val);
                            }
                        });
                        // srcset: pick all URLs
                        const srcset = img.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(entry => {
                                const parts = entry.trim().split(/\\s+/);
                                if (parts[0] && !parts[0].startsWith('data:')) {
                                    urls.add(parts[0]);
                                }
                            });
                        }
                        // currentSrc (what the browser actually loaded)
                        if (img.currentSrc && !img.currentSrc.startsWith('data:') && !img.currentSrc.startsWith('blob:')) {
                            urls.add(img.currentSrc);
                        }
                    });
                    
                    // 2. <picture> <source> srcset
                    document.querySelectorAll('picture source').forEach(source => {
                        const srcset = source.getAttribute('srcset');
                        if (srcset) {
                            srcset.split(',').forEach(entry => {
                                const parts = entry.trim().split(/\\s+/);
                                if (parts[0] && !parts[0].startsWith('data:')) {
                                    urls.add(parts[0]);
                                }
                            });
                        }
                    });
                    
                    // 3. Background images from computed styles
                    document.querySelectorAll('[style*="background"]').forEach(el => {
                        const bg = getComputedStyle(el).backgroundImage;
                        const match = bg.match(/url\\(["']?(.+?)["']?\\)/);
                        if (match && match[1] && !match[1].startsWith('data:')) {
                            urls.add(match[1]);
                        }
                    });
                    
                    return Array.from(urls);
                }
            """)
            logger.info(f"Live DOM extraction: {len(urls)} image URLs found")
            return set(urls)
        except Exception as e:
            logger.warning(f"Live DOM extraction failed: {e}")
            return set()

    def _handle_request(self, request):
        """Capture image URLs directly from intercepted network traffic."""
        try:
            url = request.url
            if request.resource_type in ("image", "media") or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                if url.startswith("data:") or url.startswith("blob:"):
                    return

                url_lower = url.lower()

                # Skip tracking/ad domains (these fire as resource_type="image" but are 1x1 pixels)
                ad_domains = (
                    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
                    "google-analytics.com", "googletagmanager.com", "google.com/pagead",
                    "google.co.in/pagead", "google.co.in/ads",
                    "adsafeprotected.com", "facebook.net", "facebook.com",
                    "amazon-adsystem.com", "moatads.com", "adnxs.com",
                    "rubiconproject.com", "pubmatic.com", "openx.net",
                    "criteo.com", "taboola.com", "outbrain.com",
                    "liadm.com", "bidswitch.net", "adsrvr.org", "gsspat.jp",
                    "adtrafficquality.google", "demdex.net", "krxd.net",
                    "bluekai.com", "quantserve.com", "rlcdn.com",
                    "eyeota.net", "tribalfusion.com", "sharethrough.com",
                    "agkn.com", "1rx.io", "adform.net", "tremorhub.com",
                    "smartadserver.com", "semasio.net", "yieldmo.com",
                    "mediarithmics.com", "seedtag.com", "inmobi.com",
                    "smaato.net", "tapad.com", "contextweb.com",
                    "pippio.com", "everesttech.net", "analytics.yahoo.com",
                    "creativecdn.com", "bidr.io", "ladsp.com",
                    "smartytech.io", "admatic.de", "cootlogix.com",
                    "primis.tech", "adroll.com", "temu.com",
                    "teads.tv", "id5-sync.com", "serving-sys.com",
                    "p7cloud.net", "xplosion.de", "betweendigital.com",
                    "media.net", "sodar",
                )
                if any(d in url_lower for d in ad_domains):
                    return

                # Skip URLs with extremely long query strings (tracking beacons)
                if len(url) > 500:
                    return

                self.network_urls.add(url)
        except Exception:
            pass

    async def navigate(self, url, retries=3):
        """
        Navigate to a URL and wait for the page to be loaded.
        Retries on failure and auto-dismisses cookie banners.
        Uses a 3-stage fallback: networkidle → load → domcontentloaded.

        Args:
            url: The URL to navigate to
            retries: Number of retry attempts

        Returns:
            True if navigation succeeded, False otherwise
        """
        # Progressive fallback strategies: most thorough → most lenient
        wait_strategies = ["networkidle", "load", "domcontentloaded", "commit"]

        for attempt in range(retries + 1):
            strategy = wait_strategies[min(attempt, len(wait_strategies) - 1)]
            try:
                await self.page.goto(
                    url,
                    wait_until=strategy,
                    timeout=config.PAGE_LOAD_TIMEOUT,
                )

                # Wait a moment for dynamic JS frameworks to render
                await self.page.wait_for_timeout(2000)

                # Perform initial scroll to trigger basic lazy loading
                await self.scroll_full_page()

                # Auto-dismiss cookie/consent banners
                await self._dismiss_cookie_banners()

                logger.info(f"Navigated to: {url} (strategy={strategy})")
                return True

            except Exception as e:
                if attempt < retries:
                    wait_sec = 2 + attempt * 2  # 2s, 4s, 6s between retries
                    logger.warning(
                        f"Navigation attempt {attempt + 1} failed for {url} "
                        f"(strategy={strategy}): {e}. "
                        f"Retrying in {wait_sec}s with strategy={wait_strategies[min(attempt + 1, len(wait_strategies) - 1)]}..."
                    )
                    await self.page.wait_for_timeout(wait_sec * 1000)
                else:
                    logger.error(f"Navigation failed for {url} after {retries + 1} attempts: {e}")
                    return False

        return False

    async def _dismiss_cookie_banners(self):
        """
        Automatically dismiss cookie/consent banners that can block interaction.
        Tries multiple common selectors and loops to handle multi-step banners.
        """
        for _ in range(3):  # Try up to 3 times for multi-step prompts
            clicked_in_round = False
            for selector in config.COOKIE_DISMISS_SELECTORS:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            await element.click()
                            await self.page.wait_for_timeout(800)
                            logger.debug(f"Dismissed cookie banner with selector: {selector}")
                            clicked_in_round = True
                            break  # Found one in this round, move to next round
                except Exception:
                    continue
            if not clicked_in_round:
                break  # No more banners found

    async def scroll_full_page(self):
        """
        Scroll the page from top to bottom to trigger lazy-loaded images.
        Uses smaller steps and longer pauses for thorough lazy-load triggering.
        """
        try:
            # Get the total scrollable height
            total_height = await self.page.evaluate("document.body.scrollHeight")
            viewport_height = 1080
            current_position = 0

            # Scroll down incrementally with smaller steps
            while current_position < total_height:
                current_position += viewport_height // 3  # One-third viewport steps
                await self.page.evaluate(f"window.scrollTo(0, {current_position})")
                await self.page.wait_for_timeout(400)  # Slightly longer pause for lazy loading

                # Recheck height (page may have grown with lazy load)
                total_height = await self.page.evaluate("document.body.scrollHeight")

            # Scroll back to top to trigger any remaining events
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(500)

            logger.debug("Full page scroll completed")
        except Exception as e:
            logger.warning(f"Scroll error (non-fatal): {e}")

    def get_network_urls(self):
        """Return captured network URLs and clear the buffer."""
        urls = set(self.network_urls)
        self.network_urls.clear()
        return urls

    async def get_page_content(self):
        """Return the full HTML content of the current page."""
        try:
            return await self.page.content()
        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            return ""

    async def click_element(self, selector, timeout=5000):
        """
        Click an element matching the given selector.

        Args:
            selector: CSS selector
            timeout: Max wait time in ms

        Returns:
            True if click succeeded, False otherwise
        """
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                await element.click()
                return True
        except Exception:
            pass
        return False

    async def get_elements(self, selector):
        """Return all elements matching the selector."""
        try:
            return await self.page.query_selector_all(selector)
        except Exception:
            return []

    async def get_element_attribute(self, element, attribute):
        """Get an attribute value from an element."""
        try:
            return await element.get_attribute(attribute)
        except Exception:
            return None

    async def get_element_text(self, element):
        """Get the text content of an element."""
        try:
            return await element.text_content()
        except Exception:
            return ""

    async def is_element_disabled(self, element):
        """Check if an element has the disabled attribute."""
        try:
            disabled = await element.get_attribute("disabled")
            return disabled is not None
        except Exception:
            return True

    async def wait(self, seconds):
        """Wait for a specified duration."""
        await self.page.wait_for_timeout(int(seconds * 1000))

    async def get_current_url(self):
        """Return the current page URL."""
        return self.page.url

    async def find_internal_links(self, base_url):
        """
        Find internal links on the page that might lead to variant/trim pages.

        Returns:
            List of absolute URLs
        """
        try:
            from urllib.parse import urljoin, urlparse

            links = await self.page.evaluate("""
                () => {
                    const anchors = document.querySelectorAll('a[href]');
                    return Array.from(anchors).map(a => a.href);
                }
            """)

            base_parsed = urlparse(base_url)
            variant_links = []

            for link in links:
                try:
                    parsed = urlparse(link)
                    # Same domain, different path, looks like a variant/trim
                    if parsed.netloc == base_parsed.netloc and parsed.path != base_parsed.path:
                        # Must be a subpath related to the current car
                        base_path_stripped = base_parsed.path.rstrip('/')
                        if parsed.path.startswith(base_path_stripped):
                            full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                            if full_url not in variant_links:
                                variant_links.append(full_url)
                except Exception:
                    continue

            return variant_links
        except Exception as e:
            logger.warning(f"Error finding internal links: {e}")
            return []

    async def has_canvas_renderer(self):
        """
        Check if the page uses a large <canvas> element (likely WebGL) for rendering the car.
        
        Returns:
            True if a large canvas is found, False otherwise
        """
        try:
            # Check for a canvas that takes up a significant portion of the viewport
            result = await self.page.evaluate('''
                () => {
                    const canvases = document.querySelectorAll('canvas');
                    for (const canvas of canvases) {
                        const rect = canvas.getBoundingClientRect();
                        // Assume it's a 3D car renderer if the canvas is reasonably large
                        if (rect.width > 400 && rect.height > 300) {
                            return true;
                        }
                    }
                    return false;
                }
            ''')
            return bool(result)
        except Exception as e:
            logger.debug(f"Error checking for canvas renderer: {e}")
            return False

    async def capture_car_screenshot(self):
        """
        Capture a screenshot of the main 3D car renderer (canvas or main viewport).
        
        Returns:
            Bytes of the JPEG screenshot, or None if failed
        """
        try:
            if not config.SCREENSHOT_ENABLED:
                return None

            # First try to find a large canvas to screenshot specifically
            canvas_handle = await self.page.evaluate_handle('''
                () => {
                    const canvases = document.querySelectorAll('canvas');
                    let largest = null;
                    let maxArea = 0;
                    
                    for (const canvas of canvases) {
                        const rect = canvas.getBoundingClientRect();
                        const area = rect.width * rect.height;
                        if (area > maxArea && rect.width > 400) {
                            largest = canvas;
                            maxArea = area;
                        }
                    }
                    
                    // If no canvas is large enough, return null to fallback to viewport
                    return largest;
                }
            ''')
            
            # If we found a large canvas, capture just that element to avoid UI clutter
            # Otherwise, fallback to full page/viewport
            handle_is_element = await self.page.evaluate('(h) => h !== null', canvas_handle)
            
            if handle_is_element:
                logger.debug("Capturing screenshot of specific canvas element")
                element = canvas_handle.as_element()
                if element:
                    screenshot_bytes = await element.screenshot(
                        type='jpeg',
                        quality=config.SCREENSHOT_JPEG_QUALITY
                    )
                    return screenshot_bytes

            # Fallback: Capture the main viewport
            # Hide common fixed elements (headers, footers, sidebars) first to get a cleaner shot
            logger.debug("Capturing viewport screenshot")
            await self.page.evaluate('''
                () => {
                    const elementsToHide = [
                        'header', 'footer', 'nav', 
                        // BMW specific UI
                        '.byo-core-layout__header',
                        '.cdk-byo__header',
                        '[data-testid="header"]'
                    ];
                    elementsToHide.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            if (el && el.style) {
                                el.dataset.originalDisplay = el.style.display || '';
                                el.style.display = 'none';
                            }
                        });
                    });
                }
            ''')
            
            screenshot_bytes = await self.page.screenshot(
                type='jpeg',
                quality=config.SCREENSHOT_JPEG_QUALITY,
                full_page=False  # Only viewport, we want what the user sees
            )
            
            # Restore elements
            await self.page.evaluate('''
                () => {
                    const elementsToHide = [
                        'header', 'footer', 'nav', 
                        '.byo-core-layout__header',
                        '.cdk-byo__header',
                        '[data-testid="header"]'
                    ];
                    elementsToHide.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            if (el && el.dataset && el.dataset.originalDisplay !== undefined) {
                                el.style.display = el.dataset.originalDisplay;
                            }
                        });
                    });
                }
            ''')
            
            return screenshot_bytes
            
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")
            return None

    async def close(self):
        """Close the browser and cleanup."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
