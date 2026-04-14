"""
Dataset Handler Module
Handles downloads from ML dataset sources: Kaggle, Roboflow, Open Images.
"""

import os
import re
import sys
import glob
import shutil
import logging
import zipfile
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


class DatasetHandler:
    """Handles Kaggle, Roboflow, and Open Images dataset downloads."""

    def __init__(self):
        self.errors = []

    # ─── Type C: Kaggle ──────────────────────────────────────────────────

    def handle_kaggle(self, url, make, model):
        """
        Download a Kaggle dataset using the Kaggle CLI.

        Args:
            url: Kaggle dataset URL (e.g., kaggle.com/datasets/user/dataset)
            make: Car make name
            model: Car model name

        Returns:
            List of extracted image file paths
        """
        try:
            # Parse dataset identifier from URL
            dataset_id = self._parse_kaggle_id(url)
            if not dataset_id:
                self._log_error(url, "Could not parse Kaggle dataset identifier")
                return []

            # Create temp download directory
            download_dir = os.path.join(config.TEMP_DATASET_DIR, f"kaggle_{make}_{model}")
            os.makedirs(download_dir, exist_ok=True)

            # Download using Kaggle CLI
            logger.info(f"Downloading Kaggle dataset: {dataset_id}")
            result = subprocess.run(
                ["kaggle", "datasets", "download", "-d", dataset_id,
                 "-p", download_dir, "--unzip"],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for large datasets
            )

            if result.returncode != 0:
                self._log_error(url, f"Kaggle CLI error: {result.stderr}")
                return []

            # Find all image files in the extracted dataset
            image_paths = self._find_images_in_directory(download_dir)

            # Filter by relevance (make/model in filename or path)
            relevant = self._filter_by_relevance(image_paths, make, model)

            # Move relevant images to temp_dataset with proper naming
            moved_paths = self._move_to_temp(relevant, make, model)

            # Cleanup download directory
            try:
                shutil.rmtree(download_dir)
            except Exception:
                pass

            logger.info(
                f"Kaggle: {len(moved_paths)} images extracted for {make} {model}"
            )
            return moved_paths

        except FileNotFoundError:
            self._log_error(
                url,
                "Kaggle CLI not found. Install with: pip install kaggle "
                "and place kaggle.json at ~/.kaggle/kaggle.json"
            )
            return []
        except subprocess.TimeoutExpired:
            self._log_error(url, "Kaggle download timed out")
            return []
        except Exception as e:
            self._log_error(url, f"Kaggle error: {e}")
            return []

    def _parse_kaggle_id(self, url):
        """Extract dataset ID from Kaggle URL."""
        # Handles: kaggle.com/datasets/user/dataset-name
        match = re.search(r'kaggle\.com/datasets/([^/]+/[^/\s?#]+)', url)
        if match:
            return match.group(1)

        # Alternative: kaggle.com/user/dataset-name
        match = re.search(r'kaggle\.com/([^/]+/[^/\s?#]+)', url)
        if match:
            return match.group(1)

        return None

    # ─── Type D: Roboflow ────────────────────────────────────────────────

    async def handle_roboflow(self, url, make, model, browser_controller):
        """
        Browse a Roboflow dataset page and extract image URLs.

        Args:
            url: Roboflow dataset URL
            make: Car make name
            model: Car model name
            browser_controller: BrowserController instance

        Returns:
            List of image URLs found on the page
        """
        try:
            from .cdn_extractor import CDNExtractor

            success = await browser_controller.navigate(url)
            if not success:
                self._log_error(url, "Failed to navigate to Roboflow page")
                return []

            await browser_controller.scroll_full_page()

            # Extract images from the page
            extractor = CDNExtractor()
            html = await browser_controller.get_page_content()
            urls = extractor.extract(html, url)

            logger.info(f"Roboflow: {len(urls)} image URLs found for {make} {model}")
            return list(urls)

        except Exception as e:
            self._log_error(url, f"Roboflow error: {e}")
            return []

    # ─── Type E: Open Images ─────────────────────────────────────────────

    def handle_open_images(self, url, make, model, limit=500):
        """
        Download car-class images from Google Open Images.

        Args:
            url: Open Images URL or identifier
            make: Car make name
            model: Car model name
            limit: Maximum images to download

        Returns:
            List of downloaded image file paths
        """
        try:
            download_dir = os.path.join(
                config.TEMP_DATASET_DIR, f"openimages_{make}_{model}"
            )
            os.makedirs(download_dir, exist_ok=True)

            # Try using openimages package
            try:
                from openimages.download import download_dataset

                download_dataset(
                    download_dir,
                    ["Car"],
                    annotation_format="pascal",
                    limit=limit,
                )
            except ImportError:
                # Fallback: try oidv6 package
                try:
                    result = subprocess.run(
                        ["oidv6", "downloader",
                         "--classes", "Car",
                         "--type_csv", "train",
                         "--limit", str(limit),
                         "--download_folder", download_dir],
                        capture_output=True,
                        text=True,
                        timeout=600,
                    )
                    if result.returncode != 0:
                        self._log_error(url, f"oidv6 error: {result.stderr}")
                        return []
                except FileNotFoundError:
                    self._log_error(
                        url,
                        "Open Images downloader not found. "
                        "Install: pip install openimages"
                    )
                    return []

            # Find all downloaded images
            image_paths = self._find_images_in_directory(download_dir)

            # Move to temp_dataset
            moved_paths = self._move_to_temp(image_paths, make, model)

            # Cleanup
            try:
                shutil.rmtree(download_dir)
            except Exception:
                pass

            logger.info(
                f"Open Images: {len(moved_paths)} images for {make} {model}"
            )
            return moved_paths

        except Exception as e:
            self._log_error(url, f"Open Images error: {e}")
            return []

    # ─── Utility Methods ─────────────────────────────────────────────────

    def _find_images_in_directory(self, directory):
        """Find all image files in a directory recursively."""
        image_paths = []
        for ext in config.VALID_IMAGE_EXTENSIONS:
            pattern = os.path.join(directory, "**", f"*{ext}")
            image_paths.extend(glob.glob(pattern, recursive=True))
        return image_paths

    def _filter_by_relevance(self, image_paths, make, model):
        """
        Filter image paths by relevance to the make/model.
        If the dataset is small, keep everything. Otherwise, prefer paths
        containing the make or model name.
        """
        if len(image_paths) <= 100:
            return image_paths  # Small dataset — keep all

        make_lower = make.lower().replace("_", "").replace("-", "")
        model_lower = model.lower().replace("_", "").replace("-", "")

        relevant = []
        for path in image_paths:
            path_lower = path.lower().replace("_", "").replace("-", "")
            if make_lower in path_lower or model_lower in path_lower:
                relevant.append(path)

        # If no relevant matches, keep all (generic dataset)
        return relevant if relevant else image_paths

    def _move_to_temp(self, image_paths, make, model):
        """Move images to temp_dataset with proper naming."""
        moved = []
        for idx, src_path in enumerate(image_paths, start=1):
            ext = os.path.splitext(src_path)[1].lower()
            if ext not in config.VALID_IMAGE_EXTENSIONS:
                ext = ".jpg"

            make_safe = re.sub(r'[^a-z0-9_]', '_', make.lower())
            model_safe = re.sub(r'[^a-z0-9_]', '_', model.lower())
            filename = f"temp_{make_safe}_{model_safe}_{idx:03d}{ext}"
            dest_path = os.path.join(config.TEMP_DATASET_DIR, filename)

            try:
                shutil.move(src_path, dest_path)
                moved.append(dest_path)
            except Exception as e:
                logger.warning(f"Failed to move {src_path}: {e}")

        return moved

    def _log_error(self, url, message):
        """Log a dataset handler error."""
        entry = f"DATASET HANDLER: {message} — {url}"
        self.errors.append(entry)
        logger.warning(entry)

    def write_errors(self, path=None):
        """Append all errors to the error log."""
        path = path or config.ERRORS_LOG_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for err in self.errors:
                f.write(err + "\n")
