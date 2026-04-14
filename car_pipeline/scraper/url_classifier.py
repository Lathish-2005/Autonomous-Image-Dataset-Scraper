"""
URL Classifier Module
Determines the type of each URL to route it to the correct handler.

Types:
    A — Direct image URL (.jpg, .jpeg, .png, .webp)
    B — CDN URL with compression params
    C — Kaggle dataset page
    D — Roboflow dataset page
    E — Google Open Images
    F — Gallery/review website (requires full browser automation)
"""

import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# URL Type constants
TYPE_DIRECT_IMAGE = "A"      # Direct image file URL
TYPE_CDN_URL = "B"           # CDN URL with compression params
TYPE_KAGGLE = "C"            # Kaggle dataset page
TYPE_ROBOFLOW = "D"          # Roboflow dataset page
TYPE_OPEN_IMAGES = "E"       # Google Open Images
TYPE_GALLERY = "F"           # Gallery/review site — browser automation


class URLClassifier:
    """Classifies URLs into handling types A through F."""

    @staticmethod
    def classify(url):
        """
        Classify a URL and return its type string.

        Args:
            url: The URL to classify

        Returns:
            Tuple of (type_code, type_description)
        """
        if not url or not isinstance(url, str):
            return TYPE_GALLERY, "Unknown URL — defaulting to browser automation"

        url_lower = url.lower().strip()
        parsed = urlparse(url_lower)
        path = parsed.path
        domain = parsed.netloc

        # ── Type A: Direct image URL ─────────────────────────────────
        for ext in config.VALID_IMAGE_EXTENSIONS:
            if path.endswith(ext):
                return TYPE_DIRECT_IMAGE, "Direct image URL"

        # ── Type C: Kaggle dataset ───────────────────────────────────
        if config.KAGGLE_DOMAIN in domain:
            return TYPE_KAGGLE, "Kaggle dataset"

        # ── Type D: Roboflow dataset ─────────────────────────────────
        for rb_domain in config.ROBOFLOW_DOMAINS:
            if rb_domain in domain:
                return TYPE_ROBOFLOW, "Roboflow dataset"

        # ── Type E: Google Open Images ───────────────────────────────
        if config.OPEN_IMAGES_DOMAIN in url_lower:
            return TYPE_OPEN_IMAGES, "Google Open Images"

        # ── Type B: CDN URL with compression params ──────────────────
        if URLClassifier._is_cdn_url(url_lower, domain):
            return TYPE_CDN_URL, "CDN URL with compression params"

        # ── Type F: Gallery / review site (default) ──────────────────
        return TYPE_GALLERY, "Gallery/review website — browser automation"

    @staticmethod
    def _is_cdn_url(url_lower, domain):
        """Check if URL is a known CDN with image content."""
        # Check known CDN domains
        for cdn in config.CDN_DOMAINS:
            if cdn in domain:
                # Verify it looks like an image URL (has image-like path)
                if any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp",
                                                      "image", "photo", "img"]):
                    return True

        # Check CDN subdomain patterns
        for pattern in config.CDN_SUBDOMAIN_PATTERNS:
            if domain.startswith(pattern):
                if any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp",
                                                      "image", "photo", "img"]):
                    return True

        return False

    @staticmethod
    def classify_batch(urls):
        """
        Classify a list of URLs.

        Args:
            urls: List of URL strings

        Returns:
            List of (url, type_code, type_description) tuples
        """
        return [(url, *URLClassifier.classify(url)) for url in urls]

    @staticmethod
    def get_type_label(type_code):
        """Return a human-readable label for a URL type code."""
        labels = {
            TYPE_DIRECT_IMAGE: "Type A — Direct Image",
            TYPE_CDN_URL: "Type B — CDN URL",
            TYPE_KAGGLE: "Type C — Kaggle Dataset",
            TYPE_ROBOFLOW: "Type D — Roboflow Dataset",
            TYPE_OPEN_IMAGES: "Type E — Open Images",
            TYPE_GALLERY: "Type F — Gallery/Review (Browser)",
        }
        return labels.get(type_code, f"Unknown type: {type_code}")
