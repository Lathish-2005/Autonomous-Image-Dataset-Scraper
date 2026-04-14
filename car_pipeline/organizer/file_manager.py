"""
File Manager Module
Organizes approved images into the final dataset folder structure:
  final_dataset/{Make}/{Model}/{Color}/image_NNN.jpg
"""

import os
import re
import sys
import shutil
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


class FileManager:
    """Renames and organizes approved images into the final dataset structure."""

    def __init__(self):
        self.moved_count = 0
        self.error_count = 0

    def organize_images(self, image_paths, make, model, color=None, flat=False):
        """
        Move approved images from temp_dataset to the final folder structure.

        Args:
            image_paths: List of approved image file paths
            make: Car make name
            model: Car model name
            color: Optional color name
            flat: If True, save directly into FINAL_DATASET_DIR without subfolders

        Returns:
            List of final file paths
        """
        if flat:
            # Save directly into the output directory, no Make/Model subfolders
            dest_dir = config.FINAL_DATASET_DIR
        else:
            # Build the destination folder path with Make/Model subfolders
            make_folder = self._to_folder_name(make)
            model_folder = self._to_folder_name(model)

            if color:
                color_folder = self._to_folder_name(color)
                dest_dir = os.path.join(
                    config.FINAL_DATASET_DIR, make_folder, model_folder, color_folder
                )
            else:
                dest_dir = os.path.join(
                    config.FINAL_DATASET_DIR, make_folder, model_folder
                )

        os.makedirs(dest_dir, exist_ok=True)

        # Find the next available sequence number in the dest folder
        existing = self._count_existing(dest_dir)
        sequence = existing + 1

        final_paths = []

        for src_path in image_paths:
            try:
                # Determine extension
                _, ext = os.path.splitext(src_path)
                ext = ext.lower()
                if ext not in config.VALID_IMAGE_EXTENSIONS:
                    ext = ".jpg"

                # Build final filename
                filename = f"image_{sequence:03d}{ext}"
                dest_path = os.path.join(dest_dir, filename)

                # Move the file
                shutil.move(src_path, dest_path)
                final_paths.append(dest_path)
                sequence += 1
                self.moved_count += 1

            except Exception as e:
                logger.warning(f"Failed to organize {src_path}: {e}")
                self.error_count += 1

        logger.info(
            f"Organized {len(final_paths)} images → {dest_dir}"
        )
        return final_paths

    def organize_saved_rejected(self, saved_paths, rejected_paths, make, model):
        """
        Organize images into binary saved/rejected folders per the demo requirements.

        Args:
            saved_paths: List of file paths to accepted (exterior) images
            rejected_paths: List of file paths to rejected (interior/errors) images
            make: Car make name
            model: Car model name

        Returns:
            Tuple of (final_saved_paths, final_rejected_paths)
        """
        make_folder = self._to_folder_name(make)
        model_folder = self._to_folder_name(model)

        # Build paths: US/OFFICIAL/{Make}/{Model}/saved_images (or rejected_images)
        saved_dir = os.path.join(
            config.FINAL_DATASET_DIR,
            make_folder,
            model_folder,
            config.SAVED_FOLDER
        )
        rejected_dir = os.path.join(
            config.FINAL_DATASET_DIR,
            make_folder,
            model_folder,
            config.REJECTED_FOLDER
        )

        final_saved = self._move_batch(saved_paths, saved_dir)
        final_rejected = self._move_batch(rejected_paths, rejected_dir)

        logger.info(f"[{make} {model}] Organized {len(final_saved)} saved, {len(final_rejected)} rejected")
        return final_saved, final_rejected

    def organize_color_dataset(self, saved_paths, rejected_paths, color):
        """
        Organize images into binary saved/rejected folders under a specific Color folder in the root output path.
        """
        color_folder = self._to_folder_name(color)

        # Build paths: output_dir/{Color}/saved_images (or rejected_images)
        saved_dir = os.path.join(
            config.FINAL_DATASET_DIR,
            color_folder,
            config.SAVED_FOLDER
        )
        rejected_dir = os.path.join(
            config.FINAL_DATASET_DIR,
            color_folder,
            config.REJECTED_FOLDER
        )

        final_saved = self._move_batch(saved_paths, saved_dir)
        final_rejected = self._move_batch(rejected_paths, rejected_dir)

        logger.info(f"[{color}] Organized {len(final_saved)} saved, {len(final_rejected)} rejected")
        return final_saved, final_rejected

    def organize_scenario(self, paths, color, scenario):
        """
        Organize images directly into a specific Scenario folder under a Color folder, bypassing binary filtering.
        """
        color_folder = self._to_folder_name(color)
        scenario_folder = self._to_folder_name(scenario)

        # Build paths: output_dir/{Color}/{Scenario}
        dest_dir = os.path.join(
            config.FINAL_DATASET_DIR,
            color_folder,
            scenario_folder
        )

        final_paths = self._move_batch(paths, dest_dir)
        logger.info(f"[{color} / {scenario}] Organized {len(final_paths)} images")
        return final_paths

    def _move_batch(self, paths, dest_dir):
        """Helper to move a list of files to a destination directory with sequential naming."""
        if not paths:
            os.makedirs(dest_dir, exist_ok=True)  # Create empty folder even if no images
            return []

        os.makedirs(dest_dir, exist_ok=True)
        existing = self._count_existing(dest_dir)
        sequence = existing + 1
        final_paths = []

        for src_path in paths:
            # Rejects might come as tuples (path, reason), unwrap if needed
            if isinstance(src_path, tuple):
                src_path = src_path[0]
                
            if not os.path.exists(src_path):
                continue
                
            try:
                _, ext = os.path.splitext(src_path)
                ext = ext.lower()
                if ext not in config.VALID_IMAGE_EXTENSIONS:
                    ext = ".jpg"

                filename = f"image_{sequence:03d}{ext}"
                dest_path = os.path.join(dest_dir, filename)
                shutil.move(src_path, dest_path)
                final_paths.append(dest_path)
                sequence += 1
                self.moved_count += 1
            except Exception as e:
                logger.warning(f"Failed to organize {src_path}: {e}")
                self.error_count += 1

        return final_paths
        """
        Organize images that have color tags.

        Args:
            color_url_map: Dict of { color_name: set(urls) } from navigator
            approved_paths: List of approved image file paths
            make: Car make name
            model: Car model name

        Returns:
            List of all final file paths
        """
        all_final = []

        # Build a lookup: filename → color
        color_lookup = self._build_color_lookup(color_url_map, approved_paths)

        # Group by color
        by_color = {}
        for path in approved_paths:
            color = color_lookup.get(os.path.basename(path))
            if color not in by_color:
                by_color[color] = []
            by_color[color].append(path)

        # Organize each color group
        for color, paths in by_color.items():
            final = self.organize_images(paths, make, model, color)
            all_final.extend(final)

        return all_final

    def _build_color_lookup(self, color_url_map, approved_paths):
        """
        Build a mapping from filename to color name based on the temp naming
        convention: temp_{make}_{model}_{color}_{seq}.ext
        """
        lookup = {}

        for path in approved_paths:
            filename = os.path.basename(path)
            # Try to extract color from filename
            # Format: temp_{make}_{model}_{color}_{seq}.ext
            parts = filename.replace("temp_", "").rsplit("_", 1)
            if len(parts) >= 2:
                name_part = parts[0]
                # The color was embedded in the filename by the downloader
                # Try to match against known colors from color_url_map
                for color_name in color_url_map:
                    if color_name and color_name.lower().replace("_", "") in name_part.lower().replace("_", ""):
                        lookup[filename] = color_name
                        break

        return lookup

    def _to_folder_name(self, name):
        """
        Convert a name to folder-safe format.
        - Title case
        - Spaces to underscores
        - Remove special characters (keep alphanumeric and underscores)
        """
        if not name:
            return "Unknown"

        name = str(name).strip().title()
        name = name.replace(" ", "_")

        # Remove special characters except underscores and hyphens
        safe = ""
        for ch in name:
            if ch.isalnum() or ch in ("_", "-"):
                safe += ch
            else:
                safe += "_"

        # Clean up multiple underscores
        safe = re.sub(r'_+', '_', safe)
        safe = safe.strip("_")

        return safe if safe else "Unknown"

    def _count_existing(self, directory):
        """Count how many image files already exist in a directory."""
        if not os.path.exists(directory):
            return 0

        count = 0
        for f in os.listdir(directory):
            _, ext = os.path.splitext(f)
            if ext.lower() in config.VALID_IMAGE_EXTENSIONS:
                count += 1
        return count

    def get_stats(self):
        """Return organization statistics."""
        return {
            "moved": self.moved_count,
            "errors": self.error_count,
        }

    @staticmethod
    def get_dataset_summary(dataset_dir=None):
        """
        Generate a summary of the final dataset folder structure.

        Returns:
            Dict with make/model counts and total images
        """
        dataset_dir = dataset_dir or config.FINAL_DATASET_DIR
        if not os.path.exists(dataset_dir):
            return {"makes": 0, "models": 0, "total_images": 0}

        makes = 0
        models = 0
        total_images = 0

        for make_name in os.listdir(dataset_dir):
            make_path = os.path.join(dataset_dir, make_name)
            if not os.path.isdir(make_path):
                continue
            makes += 1

            for model_name in os.listdir(make_path):
                model_path = os.path.join(make_path, model_name)
                if not os.path.isdir(model_path):
                    continue
                models += 1

                # Count images in model folder and color subfolders
                for root, dirs, files in os.walk(model_path):
                    for f in files:
                        _, ext = os.path.splitext(f)
                        if ext.lower() in config.VALID_IMAGE_EXTENSIONS:
                            total_images += 1

        return {
            "makes": makes,
            "models": models,
            "total_images": total_images,
        }
