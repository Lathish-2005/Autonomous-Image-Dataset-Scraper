"""
Central configuration for the Car Dataset Collection Pipeline (Demo Version).
All paths, thresholds, selectors, and CDN patterns are defined here.
"""

import os

# ─── Base Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
TEMP_DATASET_DIR = os.path.join(BASE_DIR, "temp_dataset")
FINAL_DATASET_DIR = os.path.join(BASE_DIR, "final_dataset", "US", "OFFICIAL")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# ─── Excel Configuration ────────────────────────────────────────────────────
# Place your Excel file in the input/ folder and set the filename here.
EXCEL_FILENAME = "Testing of Car models official urls 1.xlsx"
EXCEL_PATH = os.path.join(INPUT_DIR, EXCEL_FILENAME)

# Column names expected inside each sheet
COL_MANUFACTURER = "Manufacturer"
COL_MODEL_NAME = "Model Name"
COL_URL = "Official Direct Url"

RUN_LOG_PATH = os.path.join(LOGS_DIR, "run_log.csv")
ERRORS_LOG_PATH = os.path.join(LOGS_DIR, "errors.txt")

# ─── Output Subfolder Names ─────────────────────────────────────────────────
SAVED_FOLDER = "saved_images"
REJECTED_FOLDER = "rejected_images"

# ─── YOLO Configuration ─────────────────────────────────────────────────────
YOLO_MODEL_NAME = "yolov8m.pt"  # Options: yolov8n.pt (fast/CPU), yolov8m.pt (accurate/GPU)
YOLO_CONFIDENCE_THRESHOLD = 0.30
YOLO_CAR_CLASS_ID = 2  # COCO class ID for 'car'
YOLO_TRUCK_CLASS_ID = 7  # COCO class ID for 'truck' (also relevant for SUVs)
YOLO_BUS_CLASS_ID = 5 # COCO class ID for 'bus' (vans/large SUVs are sometimes classified as buses)
YOLO_RELEVANT_CLASSES = {2, 3, 5, 7}  # car, motorcycle, bus, and truck

# COCO classes that indicate interior/non-exterior content
# 56=chair (car seats), 57=couch (rear bench), 60=dining table (flat dashboards),
# 62=tv (infotainment), 63=laptop (tablet screens), 67=cell phone (smaller screens),
# 73=book (dashboard manuals), 74=clock (instrument cluster gauges), 75=vase (gear shifter knobs)
YOLO_INTERIOR_CLASSES = {56, 57, 60, 62, 63, 67, 73, 74, 75}
YOLO_INTERIOR_CONFIDENCE = 0.15       # Lower threshold for interior object detection
INTERIOR_CLASS_REJECT_COUNT = 1       # Reject if >= N interior objects found

# ─── URL-Based Interior/Detail Keyword Filtering ────────────────────────────
# URLs containing these keywords are soft-rejected (downloaded but auto-rejected
# without YOLO processing) to reduce misclassification
INTERIOR_URL_KEYWORDS = [
    "interior", "cabin", "cockpit", "dashboard", "steering",
    "console", "seat", "trunk-open", "boot-open", "engine-bay",
    "detail", "close-up", "closeup", "macro", "badge", "logo",
    "emblem", "wheel-detail", "rim-detail", "headlight-detail",
    "taillight-detail", "configurator", "accessory", "accessories",
]

# URL keywords that strongly suggest exterior car views (higher priority)
EXTERIOR_URL_KEYWORDS = [
    "exterior", "gallery", "hero", "beauty", "profile",
    "front", "rear", "side", "driving", "action",
]


# ─── OpenCV Filtering ───────────────────────────────────────────────────────
MIN_CAR_FRAME_RATIO = 0.08      # Relaxed: Car bounding box must cover 8%+ of total frame area
MIN_CAR_COMPLETENESS_RATIO = 0.25  # Relaxed: Car bbox must span 25%+ of image width or height
MAX_CAR_CROP_RATIO_H = 0.96     # If bbox height > 96% and width > 70%, it's likely an interior/crop
MAX_CAR_CROP_RATIO_W = 0.70
INTERIOR_GRAY_THRESHOLD = 0.70  # Relaxed: If >70% of center region is gray/black/beige → interior
INTERIOR_CENTER_CROP_RATIO = 0.60  # Analyze center 60% of image for interior signals
STEERING_WHEEL_MIN_CIRCULARITY = 0.7  # Minimum circularity for steering wheel detection
BLUR_THRESHOLD = 50             # Laplacian variance below this is rejected
CONTRAST_THRESHOLD = 25         # Std dev below this is rejected if blur is borderline
HASH_DB_FILE = "dataset_hashes.json"
DUPLICATE_HAMMING_DISTANCE = 6   # Max hamming distance for aHash duplicates
YOLO_APPEARANCE_SIM_THRESHOLD = 0.95 # Threshold for cosine similarity of signatures
COOLDOWN_SECONDS = 2            # Prevent saving same vehicle too frequently (mostly for video)
MAX_VIDEOS_PER_CHANNEL = 5      # Default limit if not specified

# ─── Screenshot / Canvas Configurator Settings ───────────────────────────────
SCREENSHOT_ENABLED = True                  # Enable screenshot capture for canvas/WebGL pages
CANVAS_RENDER_WAIT = 4.0                   # Seconds to wait for WebGL/3D model to render
SCREENSHOT_WAIT_AFTER_COLOR_CLICK = 3.0    # Seconds after clicking a color before screenshot
SCREENSHOT_WAIT_AFTER_ANGLE_CLICK = 2.5    # Seconds after clicking angle/rotation arrow
MAX_SCREENSHOTS_PER_MODEL = 200            # Safety limit for total screenshots per model
MAX_ANGLE_CAPTURES = 12                    # Max angle rotations to capture (e.g. every 30°)
SCREENSHOT_JPEG_QUALITY = 95               # JPEG quality for saved screenshots
MIN_SCREENSHOT_CAR_AREA_RATIO = 0.05       # Min car area ratio for screenshot validity

# ─── Download Settings ───────────────────────────────────────────────────────
MIN_IMAGE_SIZE_BYTES = 10 * 1024  # 10KB minimum
DOWNLOAD_DELAY_MIN = 1.0          # seconds
DOWNLOAD_DELAY_MAX = 2.0          # seconds
DOWNLOAD_DELAY_429_MIN = 3.0      # seconds (after rate limit)
DOWNLOAD_DELAY_429_MAX = 5.0      # seconds (after rate limit)
DOWNLOAD_TIMEOUT = 20             # seconds
DOWNLOAD_RETRY_LIMIT = 1
PAGE_LOAD_TIMEOUT = 30000         # milliseconds (Playwright)
COLOR_CLICK_WAIT = 1.5            # seconds after clicking a color swatch

# ─── Configurator Domain Detection ──────────────────────────────────────────
# Domains/URL patterns that indicate a WebGL/canvas car configurator
CONFIGURATOR_URL_PATTERNS = [
    "build-your-own",
    "configurator",
    "configure.",
    "/configure/",
    "build-and-price",
    "buildandprice",
    "customizer",
    "/studio/",
    "design-your",
]

# ─── BMW-Specific Selectors ─────────────────────────────────────────────────
BMW_COLOR_SWATCH_SELECTORS = [
    # BMW Build Your Own configurator color chips
    '[data-testid="color-chip"]',
    '[data-testid="exterior-color"]',
    '.byo-color-swatch',
    '.byo-color-chip',
    '.color-chip',
    '.cdk-byo__color-chip',
    '[class*="ColorChip"]',
    '[class*="color-chip"]',
    '[class*="colorChip"]',
    '[class*="color_chip"]',
    'button[class*="swatch"]',
    '[role="radio"][aria-label*="color" i]',
    '[role="option"][aria-label*="color" i]',
    'li[data-color]',
    '.exterior-colors button',
    '.exterior-colors li',
    '.exterior-color-selector button',
    '[class*="ExteriorColor"] button',
    '[class*="exterior-color"] button',
    '[class*="paint"] button',
    '[class*="Paint"] button',
    # Generic configurator color selectors
    'input[type="radio"][name*="color" i]',
    'input[type="radio"][name*="paint" i]',
    '.color-option',
    '.paint-selector button',
    '[data-component="color-selector"] button',
]

# BMW / Configurator angle rotation selectors
CONFIGURATOR_ANGLE_SELECTORS = [
    # BMW-specific angle buttons
    '[data-testid="rotate-left"]',
    '[data-testid="rotate-right"]',
    '[aria-label*="rotate" i]',
    '[aria-label*="angle" i]',
    '[class*="rotate"]',
    '[class*="Rotate"]',
    # Generic 360 viewer controls
    '.rotation-control',
    '.view-360-control',
    '[class*="360"]',
    '.angle-selector button',
    '.view-angle button',
    # Carousel-style angle views
    '[aria-label*="view" i][aria-label*="next" i]',
    '[aria-label*="Next view" i]',
    '.exterior-view-nav button',
    '.view-selector button',
    '[class*="ViewSelector"] button',
]

# ─── Browser Settings ───────────────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ─── CDN Domain Patterns ────────────────────────────────────────────────────
CDN_DOMAINS = [
    "akamaized.net",
    "cloudfront.net",
    "imgix.net",
    "fastly.net",
    "scene7.com",
]

CDN_SUBDOMAIN_PATTERNS = [
    "cdn.",
    "media.",
    "images.",
    "assets.",
    "static.",
]

# ─── URL Rejection Patterns ─────────────────────────────────────────────────
REJECTED_URL_PATTERNS = [
    "/icon/",
    "/logo/",
    "/favicon",
    "/placeholder/",
    "/blank/",
]

REJECTED_EXTENSIONS = {".gif", ".svg", ".ico"}

# ─── Resolution Upgrade Tokens ──────────────────────────────────────────────
RESOLUTION_UPGRADES = {
    "_thumb": "_large",
    "_sm": "_hd",
    "_300": "_1920",
    "_small": "_large",
    "_medium": "_large",
}

COMPRESSION_PARAMS_TO_STRIP = [
    "w=", "q=", "resize=", "width=", "height=",
    "quality=", "size=", "fit=", "crop=",
]

# ─── Color Swatch Selectors ─────────────────────────────────────────────────
COLOR_SWATCH_SELECTORS = [
    "[data-color]",
    "[data-variant]",
    "[data-feature-name*='color' i]",
    "[class*='color-swatch' i]",
    "[class*='color-option' i]",
    "[class*='swatch-item' i]",
    "[class*='paint-chip' i]",
    "button[aria-label*='color' i]",
    "button[aria-label*='paint' i]",
    "button[title*='color' i]",
    ".color-selector button",
    ".color-picker button",
    ".swatch",
    ".paint-option",
    "li[data-value*='color' i]",
    ".configurator-color-item",
]

# ─── Cookie Dismissal Selectors ─────────────────────────────────────────────
# Common cookie/consent banner selectors used across car manufacturer sites
# Prioritizing "Reject" and "Decline" selectors over "Accept" as requested.
COOKIE_DISMISS_SELECTORS = [
    # Reject / Decline / Manage options
    'button:has-text("Reject All")',
    'button:has-text("Decline All")',
    'button:has-text("Reject")',
    'button:has-text("Decline")',
    'button[class*="reject" i]',
    'button[id*="reject" i]',
    'button[aria-label*="reject" i]',
    'button:has-text("Necessary only")',
    'button:has-text("Functional only")',
    # Fallback to Accept if Reject is absent
    'button[id*="cookie" i][id*="accept" i]',
    'button[id*="cookie" i][id*="ok" i]',
    'button[id*="consent" i][id*="accept" i]',
    'button[class*="cookie" i][class*="accept" i]',
    'button[aria-label*="accept" i]',
    'button[aria-label*="agree" i]',
    'a[id*="cookie" i][id*="accept" i]',
    '#onetrust-accept-btn-handler',  # OneTrust
    '#onetrust-reject-all-handler',
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
    # Specific manufacturer selectors
    '.toyota-cookie-accept',
    '#ford-cookie-accept',
    '.acura-consent-accept',
    'button:has-text("Manage Cookies")',
    'button:has-text("Cookie Settings")',
]

# ─── Gallery Tab Selectors (Exterior / Interior / etc.) ─────────────────────
GALLERY_TAB_SELECTORS = [
    'button:has-text("Exterior")',
    'button:has-text("Interior")',
    'a:has-text("Exterior")',
    'a:has-text("Interior")',
    'button[aria-label*="exterior" i]',
    'button[aria-label*="interior" i]',
    'a[aria-label*="exterior" i]',
    'a[aria-label*="interior" i]',
    '[data-tab*="exterior" i]',
    '[data-tab*="interior" i]',
    '[role="tab"]:has-text("Exterior")',
    '[role="tab"]:has-text("Interior")',
    '.gallery-tab',
    '.gallery-nav button',
    '.tab-item:contains("Exterior")',
    '.tab-item:contains("Interior")',
]

# ─── Load More Selectors ────────────────────────────────────────────────────
# Selectors for Load More / View More buttons in galleries
LOAD_MORE_SELECTORS = [
    'button:has-text("Load More")',
    'button:has-text("View More")',
    'button:has-text("Show More")',
    'button:has-text("Show All")',
    'button:has-text("View Gallery")',
    'a:has-text("View All")',
    '.load-more-btn',
    '[aria-label*="Load more" i]',
]

# ─── Pagination / Carousel Selectors ────────────────────────────────────────
NEXT_BUTTON_SELECTORS = [
    "[aria-label*='Next' i]",
    "[aria-label*='forward' i]",
    ".slick-next",
    ".arrow-right",
    "button.next",
    ".carousel-control-next",
    "[data-slide='next']",
    ".swiper-button-next",
    ".next-btn",
    ".nav-next",
    ".gallery-next",
    ".icon-chevron-right",
    ".chevron-right",
    "button:has(.icon-next)",
    "button:has(.icon-chevron-right)",
]

# ─── Kaggle Dataset Domains ─────────────────────────────────────────────────
KAGGLE_DOMAIN = "kaggle.com"
ROBOFLOW_DOMAINS = ["roboflow.com", "universe.roboflow.com"]
OPEN_IMAGES_DOMAIN = "storage.googleapis.com/openimages"

# ─── Valid Image Content Types ───────────────────────────────────────────────
VALID_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
}

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# ─── Request Headers ────────────────────────────────────────────────────────
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# ─── Ensure directories exist ───────────────────────────────────────────────
def ensure_directories():
    """Create all required directories if they don't exist."""
    for directory in [
        INPUT_DIR,
        TEMP_DATASET_DIR,
        FINAL_DATASET_DIR,
        LOGS_DIR,
    ]:
        os.makedirs(directory, exist_ok=True)
