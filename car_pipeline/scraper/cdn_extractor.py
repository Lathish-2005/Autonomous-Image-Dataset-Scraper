"""
CDN Extractor Module
Extracts high-resolution image URLs from page HTML by scanning DOM elements,
CDN domains, srcset attributes, lazy-load sources, and JSON-LD blocks.
"""

import os
import re
import sys
import json
import logging
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


class CDNExtractor:
    """Extracts and cleans high-resolution car image URLs from HTML content."""

    def __init__(self):
        self.seen_urls = set()

    def extract(self, html_content, page_url, make=None, model=None):
        """
        Extract all valid image URLs from the HTML content.

        Args:
            html_content: Full HTML string of the page
            page_url: The URL of the page (for resolving relative URLs)
            make: The car make (e.g., Acura)
            model: The car model (e.g., NSX)

        Returns:
            Set of cleaned, deduplicated image URLs
        """
        if not html_content:
            return set()

        soup = BeautifulSoup(html_content, "lxml")
        found_urls = set()

        # Scan all image sources
        found_urls.update(self._extract_img_tags(soup, page_url))
        found_urls.update(self._extract_picture_sources(soup, page_url))
        found_urls.update(self._extract_background_images(soup, page_url))
        found_urls.update(self._extract_json_ld(soup, page_url))
        found_urls.update(self._extract_data_attributes(soup, page_url))

        # Filter and clean
        cleaned = set()
        for url in found_urls:
            url = self._clean_url(url)
            if url and self._is_valid_image_url(url, make, model):
                cleaned.add(url)

        # Deduplicate against previously seen URLs
        new_urls = cleaned - self.seen_urls
        self.seen_urls.update(new_urls)

        # Classify URLs by type (exterior/interior/unknown)
        classified = self.classify_urls(new_urls)

        logger.debug(
            f"Extracted {len(new_urls)} new image URLs from {page_url} "
            f"({len(classified['exterior'])} exterior, {len(classified['interior'])} interior, "
            f"{len(classified['unknown'])} unclassified)"
        )
        return new_urls

    def process_raw_urls(self, raw_urls, page_url, make=None, model=None):
        """
        Clean, filter, and deduplicate a list of raw URLs (e.g., from network interception).
        """
        cleaned = set()
        for url in raw_urls:
            url = self._resolve_url(url, page_url)
            url = self._clean_url(url)
            if url and self._is_valid_image_url(url, make, model):
                cleaned.add(url)

        new_urls = cleaned - self.seen_urls
        self.seen_urls.update(new_urls)
        
        if new_urls:
            classified = self.classify_urls(new_urls)
            logger.debug(
                f"Processed {len(new_urls)} new image URLs from raw list "
                f"({len(classified['exterior'])} exterior, {len(classified['interior'])} interior)"
            )
        return new_urls

    def classify_urls(self, urls):
        """
        Classify URLs into exterior, interior, or unknown categories
        based on URL keyword patterns from config.

        Returns:
            Dict with 'exterior', 'interior', 'unknown' sets of URLs
        """
        result = {"exterior": set(), "interior": set(), "unknown": set()}

        interior_keywords = getattr(config, 'INTERIOR_URL_KEYWORDS', [])
        exterior_keywords = getattr(config, 'EXTERIOR_URL_KEYWORDS', [])

        for url in urls:
            url_type = self._classify_single_url(url, exterior_keywords, interior_keywords)
            result[url_type].add(url)

        return result

    def _classify_single_url(self, url, exterior_keywords, interior_keywords):
        """
        Classify a single URL as 'exterior', 'interior', or 'unknown'.
        Exterior keywords take priority (whitelist override).
        """
        url_lower = url.lower()

        # Check exterior keywords first (whitelist)
        for kw in exterior_keywords:
            if kw in url_lower:
                return "exterior"

        # Then check interior keywords
        for kw in interior_keywords:
            if kw in url_lower:
                return "interior"

        return "unknown"

    def _extract_img_tags(self, soup, page_url):
        """Extract URLs from <img> tags (src, srcset, data-src, etc.)."""
        urls = set()

        for img in soup.find_all("img"):
            # Primary src
            src = img.get("src", "")
            if src:
                urls.add(self._resolve_url(src, page_url))

            # Lazy-load attributes
            for attr in ("data-src", "data-lazy", "data-original",
                         "data-srcset", "data-lazy-src"):
                val = img.get(attr, "")
                if val:
                    urls.add(self._resolve_url(val, page_url))

            # srcset — pick the largest resolution
            srcset = img.get("srcset", "")
            if srcset:
                best = self._parse_srcset(srcset, page_url)
                if best:
                    urls.add(best)

        return urls

    def _extract_picture_sources(self, soup, page_url):
        """Extract URLs from <picture> <source> elements."""
        urls = set()

        for picture in soup.find_all("picture"):
            for source in picture.find_all("source"):
                srcset = source.get("srcset", "")
                if srcset:
                    best = self._parse_srcset(srcset, page_url)
                    if best:
                        urls.add(best)
                src = source.get("src", "")
                if src:
                    urls.add(self._resolve_url(src, page_url))

        return urls

    def _extract_background_images(self, soup, page_url):
        """Extract URLs from inline CSS background-image properties."""
        urls = set()

        # Elements with style attribute
        for element in soup.find_all(style=True):
            style = element.get("style", "")
            bg_urls = re.findall(r'background-image\s*:\s*url\(["\']?(.*?)["\']?\)', style)
            for url in bg_urls:
                urls.add(self._resolve_url(url, page_url))

        # Also check <style> blocks
        for style_tag in soup.find_all("style"):
            if style_tag.string:
                bg_urls = re.findall(
                    r'background-image\s*:\s*url\(["\']?(.*?)["\']?\)',
                    style_tag.string
                )
                for url in bg_urls:
                    urls.add(self._resolve_url(url, page_url))

        return urls

    def _extract_json_ld(self, soup, page_url):
        """Extract image URLs from JSON-LD structured data blocks."""
        urls = set()

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if script.string:
                    data = json.loads(script.string)
                    urls.update(self._extract_urls_from_json(data, page_url))
            except (json.JSONDecodeError, TypeError):
                continue

        return urls

    def _extract_urls_from_json(self, data, page_url):
        """Recursively extract image URLs from JSON data."""
        urls = set()

        if isinstance(data, dict):
            for key, value in data.items():
                if key.lower() in ("image", "thumbnailurl", "contenturl",
                                   "url", "photo", "logo"):
                    if isinstance(value, str) and self._looks_like_image_url(value):
                        urls.add(self._resolve_url(value, page_url))
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, str) and self._looks_like_image_url(item):
                                urls.add(self._resolve_url(item, page_url))
                            elif isinstance(item, dict):
                                urls.update(self._extract_urls_from_json(item, page_url))
                else:
                    urls.update(self._extract_urls_from_json(value, page_url))
        elif isinstance(data, list):
            for item in data:
                urls.update(self._extract_urls_from_json(item, page_url))

        return urls

    def _extract_data_attributes(self, soup, page_url):
        """Extract URLs from common data-* attributes on any element."""
        urls = set()

        data_attrs = [
            "data-image", "data-img", "data-photo",
            "data-large", "data-full", "data-hires",
            "data-bg", "data-background",
        ]

        for attr in data_attrs:
            for element in soup.find_all(attrs={attr: True}):
                val = element.get(attr, "")
                if val and self._looks_like_image_url(val):
                    urls.add(self._resolve_url(val, page_url))

        return urls

    def _parse_srcset(self, srcset_str, page_url):
        """
        Parse a srcset string and return the URL with the largest width.
        Format: "url1 300w, url2 600w, url3 1200w"
        """
        candidates = []
        parts = [p.strip() for p in srcset_str.split(",") if p.strip()]

        for part in parts:
            tokens = part.strip().split()
            if len(tokens) >= 1:
                url = tokens[0]
                width = 0
                if len(tokens) >= 2:
                    descriptor = tokens[-1]
                    # Parse width descriptor (e.g., "1200w")
                    match = re.match(r"(\d+)w", descriptor)
                    if match:
                        width = int(match.group(1))
                    # Parse pixel density (e.g., "2x")
                    match = re.match(r"(\d+(?:\.\d+)?)x", descriptor)
                    if match:
                        width = int(float(match.group(1)) * 1000)  # Convert to comparable value
                candidates.append((url, width))

        if not candidates:
            return None

        # Sort by width descending, pick largest
        candidates.sort(key=lambda x: x[1], reverse=True)
        return self._resolve_url(candidates[0][0], page_url)

    def _resolve_url(self, url, page_url):
        """Resolve a potentially relative URL to an absolute one."""
        if not url:
            return ""
        url = url.strip()
        if url.startswith("data:") or url.startswith("blob:"):
            return ""
        if url.startswith("//"):
            return "https:" + url
        if not url.startswith(("http://", "https://")):
            return urljoin(page_url, url)
        return url

    def _clean_url(self, url):
        """
        Clean a URL by stripping compression query params and upgrading
        resolution tokens in the path.
        """
        if not url:
            return ""

        parsed = urlparse(url)

        # Upgrade resolution tokens in path
        path = parsed.path
        for old, new in config.RESOLUTION_UPGRADES.items():
            path = path.replace(old, new)

        # ── Site-specific resolution upgrades ────────────────────────
        # cars.usnews.com: /pics/size/333x250/.../image_80x60.jpg → /pics/size/0x0/.../image.jpg
        if "usnews.com" in (parsed.netloc or ""):
            # Upgrade size prefix to full resolution (0x0 = original)
            path = re.sub(r'/pics/size/\d+x\d+/', '/pics/size/0x0/', path)
            # Strip thumbnail dimension suffix from filename (e.g., _80x60)
            path = re.sub(r'_\d+x\d+(\.\w+)$', r'\1', path)

        # Generic: strip _NNxNN dimension suffixes from filenames on any site
        # (common CDN pattern for thumbnails: image_80x60.jpg, image_160x120.jpg)
        elif re.search(r'_\d+x\d+\.\w+$', path):
            path = re.sub(r'_(\d+)x(\d+)(\.\w+)$', lambda m: m.group(3) if int(m.group(1)) < 400 else m.group(0), path)

        # Strip compression query parameters
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered_params = {}
            for key, values in params.items():
                # Remove known compression params
                if not any(cp.rstrip("=") == key.lower() for cp in config.COMPRESSION_PARAMS_TO_STRIP):
                    filtered_params[key] = values

            new_query = urlencode(filtered_params, doseq=True) if filtered_params else ""
        else:
            new_query = ""

        cleaned = urlunparse((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            new_query,
            "",  # No fragment
        ))

        return cleaned

    def _is_valid_image_url(self, url, make=None, model=None):
        """Check if a URL should be kept (not rejected by pattern rules)."""
        if not url:
            return False

        url_lower = url.lower()

        # Reject by path patterns
        for pattern in config.REJECTED_URL_PATTERNS:
            if pattern in url_lower:
                return False

        # Reject by extension
        parsed = urlparse(url_lower)
        _, ext = os.path.splitext(parsed.path)
        if ext in config.REJECTED_EXTENSIONS:
            return False

        # Apply strict make/model filtering for specific gallery sites
        # that use highly structured URLs. This prevents downloading "related cars"
        if make and model:
            structured_domains = ["netcarshow.com", "favcars.com", "auto-data.net", "autowp.ru", "wheelsage.org"]
            if any(domain in url_lower for domain in structured_domains):
                # NetCarShow puts 'Make-Model' in the URL, e.g. /Acura-NSX-1991-thb.jpg
                # If the URL is structured, we expect at least one significant word from the model to be in the URL
                model_clean = model.lower().replace("-", " ")
                model_words = [w for w in model_clean.split() if len(w) > 2]
                
                # If there are model words, at least one MUST be in the URL path
                if model_words and not any(w in parsed.path.lower() for w in model_words):
                    logger.debug(f"Rejected URL (Make/Model mismatch): {url}")
                    return False

        return True

    def _looks_like_image_url(self, value):
        """Quick check if a string looks like an image URL."""
        if not isinstance(value, str):
            return False
        value_lower = value.lower()
        if not value_lower.startswith(("http://", "https://", "//", "/")):
            return False
        # Check for known image extensions
        if any(ext in value_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            return True
        # Check for common image path patterns (manufacturer sites, DAM systems)
        if any(pattern in value_lower for pattern in [
            "/content/dam/", "/media/", "/images/", "/gallery/",
            "/photos/", "/assets/img", "image", "photo", "img"
        ]):
            return True
        return False

    def reset(self):
        """Reset the seen URLs tracker for a new model/page."""
        self.seen_urls.clear()
