"""
Image Downloader Module
Downloads images to the temp_dataset folder with proper validation,
naming conventions, pacing, deduplication, and error handling.
"""

import os
import re
import sys
import time
import random
import logging
from urllib.parse import urlparse

import requests
import imagehash
from PIL import Image
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)

# Maximum hamming distance to consider two images as duplicates
DUPLICATE_HASH_THRESHOLD = 5

# Domains that are tracking pixels / ad beacons (never real images)
SKIP_DOMAINS = {
    "doubleclick.net", "adsafeprotected.com", "p7cloud.net",
    "facebook.com", "facebook.net", "google-analytics.com",
    "googlesyndication.com", "googletagmanager.com",
    "amazon-adsystem.com", "moatads.com", "serving-sys.com",
    "rubiconproject.com", "pubmatic.com", "openx.net",
    "casalemedia.com", "adnxs.com", "criteo.com",
    "taboola.com", "outbrain.com", "sharethrough.com",
    "liadm.com", "bidswitch.net", "adsrvr.org", "gsspat.jp",
    "adtrafficquality.google", "match.adsrvr.org",
    "demdex.net", "krxd.net", "bluekai.com",
    "quantserve.com", "scorecardsearch.com", "rlcdn.com",
    "turn.com", "contextweb.com", "spotxchange.com",
}

# Max consecutive timeouts before we skip the rest (site is blocking)
MAX_CONSECUTIVE_TIMEOUTS = 5


class ImageDownloader:
    """Downloads images with validation, pacing, and error handling."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.REQUEST_HEADERS)
        self.download_count = 0
        self.duplicate_count = 0
        self.error_count = 0
        self.errors = []
        self._rate_limited = False
        self._seen_hashes = set()  # Perceptual hashes of downloaded images
        self._consecutive_timeouts = 0

    def download_batch(self, urls, make, model, color=None, progress_bar=None, referer=None):
        """
        Download a batch of image URLs to temp_dataset.

        Args:
            urls: Set or list of image URLs
            make: Car make name (for filename)
            model: Car model name (for filename)
            color: Optional color name (for filename)
            progress_bar: Optional tqdm progress bar to update

        Returns:
            List of successfully downloaded file paths
        """
        os.makedirs(config.TEMP_DATASET_DIR, exist_ok=True)

        downloaded_paths = []
        sequence = 1

        for url in urls:
            # Handle direct bytes from browser screenshots (e.g. configurators)
            if isinstance(url, tuple) and len(url) == 2 and url[0] == "bytes:":
                # Bypass URL/domain checks
                pass
            else:
                # Skip known tracking/ad domains
                if self._is_skip_domain(url):
                    continue

                # Bail early if too many consecutive timeouts (site is blocking us)
                if self._consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                    logger.warning(
                        f"Skipping remaining downloads: {MAX_CONSECUTIVE_TIMEOUTS} "
                        f"consecutive timeouts (site is likely blocking requests)"
                    )
                    break

            try:
                if isinstance(url, tuple) and url[0] == "bytes:":
                    # Save screenshot bytes directly
                    shot_bytes = url[1]
                    filepath = self._validate_and_save(shot_bytes, "image/jpeg", "screenshot", make, model, color, sequence)
                else:
                    filepath = self._download_single(url, make, model, color, sequence, referer)
                
                if filepath:
                    downloaded_paths.append(filepath)
                    sequence += 1
                    self.download_count += 1
                    self._consecutive_timeouts = 0  # Reset on success

                if progress_bar:
                    progress_bar.update(1)

                # Pacing delay
                self._delay()

            except Exception as e:
                self._log_error(url, f"Unexpected error: {e}")
                self.error_count += 1

        logger.info(
            f"Downloaded {len(downloaded_paths)}/{len(urls)} images "
            f"for {make} {model}" + (f" ({color})" if color else "")
        )
        return downloaded_paths

    async def download_batch_via_browser(self, urls, make, model, browser_context, color=None, referer=None):
        """
        Download images using Playwright's browser context API.
        This shares cookies/session with the browser, bypassing anti-bot blocks
        that reject standalone HTTP requests.

        Args:
            urls: Set or list of image URLs
            make: Car make name
            model: Car model name
            browser_context: Playwright BrowserContext instance
            color: Optional color name
            referer: Referer URL

        Returns:
            List of successfully downloaded file paths
        """
        import asyncio
        os.makedirs(config.TEMP_DATASET_DIR, exist_ok=True)

        downloaded_paths = []
        sequence = 1
        consecutive_real_fails = 0  # Only count timeouts/HTTP errors, not small files
        MAX_CONSEC_REAL_FAILS = 10

        for url in urls:
            if isinstance(url, tuple) and len(url) == 2 and url[0] == "bytes:":
                pass
            elif self._is_skip_domain(url):
                continue

            if consecutive_real_fails >= MAX_CONSEC_REAL_FAILS:
                logger.warning(
                    f"Skipping remaining: {MAX_CONSEC_REAL_FAILS} consecutive "
                    f"real failures (timeouts/HTTP errors — site is blocking)"
                )
                break

            try:
                if isinstance(url, tuple) and url[0] == "bytes:":
                    # Direct screenshot
                    shot_bytes = url[1]
                    result = self._validate_and_save(shot_bytes, "image/jpeg", "screenshot", make, model, color, sequence)
                else:
                    result = await self._download_single_via_browser(
                        url, make, model, color, sequence, browser_context, referer
                    )
                
                if isinstance(result, str):
                    # Success — got a filepath
                    downloaded_paths.append(result)
                    sequence += 1
                    self.download_count += 1
                    consecutive_real_fails = 0
                elif result is False:
                    # Real failure (timeout, HTTP error) — count it
                    consecutive_real_fails += 1
                # result is None means expected rejection (small file, invalid image) — don't count

                # Small delay to avoid hammering the server
                await asyncio.sleep(random.uniform(0.3, 1.0))

            except Exception as e:
                self._log_error(url, f"Browser download error: {e}")
                self.error_count += 1
                consecutive_real_fails += 1

        logger.info(
            f"Browser-downloaded {len(downloaded_paths)}/{len(urls)} images "
            f"for {make} {model}" + (f" ({color})" if color else "")
        )
        return downloaded_paths

    async def _download_single_via_browser(self, url, make, model, color, sequence, browser_context, referer=None):
        """
        Download a single image using Playwright's API request context.
        Returns:
            str (filepath) on success, None for expected rejections (tiny/invalid), False for real failures
        """
        try:
            headers = {}
            if referer:
                headers["Referer"] = referer

            response = await browser_context.request.get(
                url,
                headers=headers if headers else None,
                timeout=config.DOWNLOAD_TIMEOUT * 1000,  # Playwright uses ms
            )

            if response.status != 200:
                if response.status not in (204, 301, 302):
                    self._log_error(url, f"HTTP {response.status}")
                return False  # Real failure — HTTP error

            content = await response.body()
            content_type = response.headers.get("content-type", "").lower()

            # _validate_and_save returns filepath or None (expected rejection)
            return self._validate_and_save(content, content_type, url, make, model, color, sequence)

        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                self._log_error(url, "Browser timeout")
            else:
                self._log_error(url, f"Browser error: {error_msg[:80]}")
            return False  # Real failure — timeout/connection error

    def _validate_and_save(self, content, content_type, url, make, model, color, sequence):
        """
        Validate image content and save to disk. Shared by both download methods.
        """
        # Check file size
        if len(content) < config.MIN_IMAGE_SIZE_BYTES:
            self._log_error(url, f"File too small: {len(content) // 1024}KB")
            return None

        # Detect and convert AVIF
        is_avif = (b'ftypavif' in content[:32] or b'ftypavis' in content[:32])
        if is_avif:
            try:
                img_avif = Image.open(BytesIO(content))
                buf = BytesIO()
                img_avif.convert("RGB").save(buf, format="JPEG", quality=95)
                content = buf.getvalue()
                content_type = "image/jpeg"
            except Exception as e:
                self._log_error(url, f"AVIF conversion failed: {e}")
                return None

        # Validate image
        try:
            img = Image.open(BytesIO(content))
            img.verify()
        except Exception:
            self._log_error(url, "Invalid image data")
            return None

        # Deduplication
        try:
            img_for_hash = Image.open(BytesIO(content))
            phash = imagehash.phash(img_for_hash)
            for seen_hash in self._seen_hashes:
                if phash - seen_hash <= DUPLICATE_HASH_THRESHOLD:
                    self.duplicate_count += 1
                    logger.debug(f"Duplicate skipped: {url}")
                    return None
            self._seen_hashes.add(phash)
        except Exception:
            pass

        # Save
        ext = self._get_extension(url, content_type)
        if is_avif:
            ext = ".jpg"
        filename = self._build_filename(make, model, color, sequence, ext)
        filepath = os.path.join(config.TEMP_DATASET_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(content)

        logger.debug(f"Saved: {filename}")
        return filepath

    def _download_single(self, url, make, model, color, sequence, referer=None):
        """
        Download a single image URL with validation.

        Returns:
            File path if successful, None otherwise
        """
        retries = 0

        while retries <= config.DOWNLOAD_RETRY_LIMIT:
            try:
                headers = {}
                if referer:
                    headers["Referer"] = referer

                response = self.session.get(
                    url,
                    timeout=config.DOWNLOAD_TIMEOUT,
                    stream=True,
                    headers=headers if referer else None
                )

                # ── Check status code ────────────────────────────────
                if response.status_code == 429:
                    self._rate_limited = True
                    self._log_error(url, "Rate limited (429)")
                    retries += 1
                    self._delay()
                    continue

                if response.status_code == 403:
                    self._log_error(url, "403 Forbidden")
                    return None

                if response.status_code == 404:
                    self._log_error(url, "404 Not Found")
                    return None

                if response.status_code != 200:
                    self._log_error(url, f"HTTP {response.status_code}")
                    retries += 1
                    continue

                # ── Check Content-Type ───────────────────────────────
                content_type = response.headers.get("Content-Type", "").lower()
                if not any(ct in content_type for ct in config.VALID_CONTENT_TYPES):
                    # Some servers don't send proper content-type, try to validate image data
                    pass

                # ── Read content ─────────────────────────────────────
                content = response.content

                # ── Check file size ──────────────────────────────────
                if len(content) < config.MIN_IMAGE_SIZE_BYTES:
                    self._log_error(url, f"File too small: {len(content) // 1024}KB")
                    return None

                # ── Detect and convert AVIF images ───────────────────
                # Some websites (e.g. Audi) serve AVIF images with .jpg/.png
                # extensions. OpenCV cannot read AVIF, so convert to JPEG.
                is_avif = (b'ftypavif' in content[:32] or
                           b'ftypavis' in content[:32])
                if is_avif:
                    try:
                        img_avif = Image.open(BytesIO(content))
                        buf = BytesIO()
                        img_avif.convert("RGB").save(buf, format="JPEG", quality=95)
                        content = buf.getvalue()
                        content_type = "image/jpeg"
                        logger.debug(f"Converted AVIF image to JPEG: {url}")
                    except Exception as e:
                        self._log_error(url, f"AVIF conversion failed: {e}")
                        return None

                # ── Validate it's actually an image ──────────────────
                try:
                    img = Image.open(BytesIO(content))
                    img.verify()
                except Exception:
                    self._log_error(url, "Invalid image data")
                    return None

                # ── Deduplication via perceptual hash ─────────────────
                try:
                    img_for_hash = Image.open(BytesIO(content))
                    phash = imagehash.phash(img_for_hash)

                    # Check against all previously seen hashes
                    for seen_hash in self._seen_hashes:
                        if phash - seen_hash <= DUPLICATE_HASH_THRESHOLD:
                            self.duplicate_count += 1
                            logger.info(f"Duplicate image skipped: {url}")
                            return None

                    self._seen_hashes.add(phash)
                except Exception as e:
                    # If hashing fails, proceed anyway
                    logger.debug(f"Hash check failed for {url}: {e}")

                # ── Build filename and save ──────────────────────────
                ext = self._get_extension(url, content_type)
                # Force .jpg for converted AVIF images
                if is_avif:
                    ext = ".jpg"
                filename = self._build_filename(make, model, color, sequence, ext)
                filepath = os.path.join(config.TEMP_DATASET_DIR, filename)

                with open(filepath, "wb") as f:
                    f.write(content)

                logger.debug(f"Saved: {filename}")
                self._rate_limited = False
                return filepath

            except requests.exceptions.Timeout:
                if retries < config.DOWNLOAD_RETRY_LIMIT:
                    self._log_error(url, "Timeout — retrying")
                    retries += 1
                    continue
                else:
                    self._log_error(url, "Timeout — failed after retry")
                    self._consecutive_timeouts += 1
                    return None

            except requests.exceptions.ConnectionError:
                self._log_error(url, "Connection error")
                return None

            except Exception as e:
                self._log_error(url, f"Download error: {e}")
                return None

        return None

    def _build_filename(self, make, model, color, sequence, ext):
        """Build the temporary filename."""
        make_safe = self._safe_name(make)
        model_safe = self._safe_name(model)
        seq_str = f"{sequence:03d}"

        if color:
            color_safe = self._safe_name(color)
            return f"temp_{make_safe}_{model_safe}_{color_safe}_{seq_str}{ext}"
        else:
            return f"temp_{make_safe}_{model_safe}_{seq_str}{ext}"

    def _safe_name(self, name):
        """Convert a name to a filename-safe string."""
        safe = name.lower().strip()
        safe = re.sub(r'[^a-z0-9_]', '_', safe)
        safe = re.sub(r'_+', '_', safe)
        return safe.strip('_')

    def _get_extension(self, url, content_type):
        """Determine the file extension from URL or content-type."""
        # Try from URL
        parsed = urlparse(url)
        path = parsed.path.lower()
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            if path.endswith(ext):
                return ext

        # Try from content-type
        ct_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }
        for ct, ext in ct_map.items():
            if ct in content_type:
                return ext

        return ".jpg"  # Default

    def _is_skip_domain(self, url):
        """Check if a URL belongs to a known tracking/ad domain."""
        try:
            hostname = urlparse(url).hostname or ""
            for domain in SKIP_DOMAINS:
                if hostname.endswith(domain):
                    return True
        except Exception:
            pass
        return False

    def _delay(self):
        """Apply a download delay based on rate-limiting status."""
        if self._rate_limited:
            delay = random.uniform(
                config.DOWNLOAD_DELAY_429_MIN,
                config.DOWNLOAD_DELAY_429_MAX
            )
        else:
            delay = random.uniform(
                config.DOWNLOAD_DELAY_MIN,
                config.DOWNLOAD_DELAY_MAX
            )
        time.sleep(delay)

    def _log_error(self, url, message):
        """Log a download error."""
        entry = f"DOWNLOAD FAILED: {message} — {url}"
        self.errors.append(entry)
        logger.warning(entry)

    def write_errors(self, path=None):
        """Append all download errors to the error log."""
        path = path or config.ERRORS_LOG_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for err in self.errors:
                f.write(err + "\n")

    def get_stats(self):
        """Return download statistics."""
        return {
            "downloaded": self.download_count,
            "duplicates_skipped": self.duplicate_count,
            "errors": self.error_count,
        }
