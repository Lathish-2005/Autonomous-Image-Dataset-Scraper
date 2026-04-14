# Autonomous Car Dataset Collection Pipeline
## Complete Technical Documentation

> **Project Type:** Autonomous Image Scraping & Filtering Pipeline
> **Environment:** Local Command Prompt / Google Antigravity (Agentic IDE)
> **API Keys Required:** None
> **Cost:** Zero — fully open-source toolchain
> **Dataset Scale:** 73 Makes · 756 Models · 3,855 Active URL Jobs · Est. 219K–1.4M Images

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Excel Sheet Analysis](#2-excel-sheet-analysis)
3. [Project Folder Structure](#3-project-folder-structure)
4. [Installation & Setup](#4-installation--setup)
5. [Pipeline Workflow — Step by Step](#5-pipeline-workflow--step-by-step)
6. [Browser Automation](#6-browser-automation)
7. [CDN Extraction Logic](#7-cdn-extraction-logic)
8. [URL Type Handling](#8-url-type-handling)
9. [Image Downloading](#9-image-downloading)
10. [YOLO Filtering](#10-yolo-filtering)
11. [File Organization](#11-file-organization)
12. [Logging & Run Summary](#12-logging--run-summary)
13. [Running the Pipeline](#13-running-the-pipeline)
14. [Complete Flow Diagram](#14-complete-flow-diagram)
15. [Expected Output & Scale](#15-expected-output--scale)
16. [Constraints & Limitations](#16-constraints--limitations)

---

## 1. Project Overview

### What This Pipeline Does

This pipeline automatically collects real car exterior images from automotive websites and ML dataset sources, filters them using a local AI model, and organizes them into a clean hierarchical folder structure ready for model training — **without any paid API, LLM key, or cloud dependency.**

### Core Capabilities

- Reads the Excel sheet row by row and builds a job queue
- Visits each URL using a real Chromium browser
- Navigates color swatches, arrows, pagination, and gallery interactions automatically
- Extracts high-resolution images directly from CDN source URLs in the DOM
- Downloads images into a temporary staging folder
- Runs local YOLOv8 to detect and keep only car exterior images
- Runs OpenCV heuristics to reject interior, engine bay, and lifestyle shots
- Organizes approved images by Make → Model → Color
- Moves all rejected images to a separate folder for later deletion
- Generates a full run log and error report after every session

### What Is Not Used

| Not Used | Replaced By |
|---|---|
| OpenAI API | Local YOLOv8 model |
| Google Vision API | OpenCV heuristics |
| AWS Rekognition | Python image analysis |
| Any LLM key | Rule-based classification |
| Cloud servers | Local Command Prompt |
| Paid subscriptions | Open-source libraries only |

### What Is Excluded

> **3D Rendering sources (Tier 4 — 3DTuning.com) are completely excluded.**
> All 757 rows tagged as Tier 4 are skipped. Only real photographs are collected.

---

## 2. Excel Sheet Analysis

### File Details

| Property | Value |
|---|---|
| Filename | URL_FOR_CAR_MAKES_AND_THEIR_MODELS.xlsx |
| Sheet Name | Full URL Analysis |
| Total Rows | 5,299 (data rows) |
| Total Columns | 14 |
| Total Unique Makes | 73 |
| Total Unique Models | 756 |
| Entries Per Model | 5 (one per Tier) |

---

### Column Reference

| # | Column Name | Pipeline Usage |
|---|---|---|
| 1 | Car Make | Creates the Make-level folder |
| 2 | Car Model | Creates the Model subfolder |
| 3 | Production Year Range | Stored in metadata only |
| 4 | Vehicle Type | Stored in metadata only |
| 5 | Dataset Source | Informational |
| 6 | Dataset Type | Informational |
| 7 | Original URL | **Not used** — may be broken |
| 8 | URL Status | Filters out INVALID and UNCERTAIN rows |
| 9 | Status Notes | Informational |
| 10 | Corrected / Recommended URL | **Primary URL — always use this column** |
| 11 | Source Type | Determines which handler to use |
| 12 | Image Count Estimate | Used for progress estimation |
| 13 | License Type | Stored in metadata |
| 14 | Source Tier | Determines scraping priority and method |

> **Critical Rule:** The pipeline always reads **Column 10 (Corrected URL)**. Column 7 contains broken, outdated, and partially invalid URLs. Column 10 has the verified working version for every row.

---

### URL Status Breakdown

| Status | Count | Pipeline Action |
|---|---|---|
| VALID | 4,568 | Process normally |
| PARTIALLY INVALID | 664 | Split pipe-separated URL — use valid segment only |
| UNCERTAIN | 63 | Skipped by default — use `--include-uncertain` flag to attempt |
| INVALID | 4 | Skip completely — log to errors.txt |

#### About the 664 PARTIALLY INVALID Rows

Every one of these rows contains two URLs joined by a `|` pipe character. The Stanford Cars dataset URL (first part) is confirmed offline. The second URL — CompCars or Kaggle — is valid. Column 10 already isolates the working URL. The pipeline reads Column 10 directly, so this is automatically resolved without any manual fix.

---

### Source Tier Breakdown

#### Tier 1 — Official Press Kit / Gallery
- **Count:** 757 rows | 753 VALID | 4 INVALID
- **Sources:** Manufacturer newsrooms — acuranews.com, media.ford.com, toyota.com
- **Image Quality:** Highest — official studio and location photography
- **Expected Yield:** 50–500+ real photos per model
- **Access Method:** Browser automation with CDN extraction
- **Priority:** Highest

#### Tier 2 — Photo Gallery
- **Count:** 757 rows | 739 VALID | 18 UNCERTAIN
- **Sources:** NetCarShow.com
- **Image Quality:** High — professional editorial photography
- **Expected Yield:** 20–200 per model
- **Access Method:** Browser automation with gallery pagination
- **Priority:** High

#### Tier 3 — ML / Research Datasets
- **Count:** 1,514 rows | 850 VALID | 664 PARTIALLY INVALID
- **Sources:** Kaggle, Roboflow, CompCars, Open Images
- **Image Quality:** Varies — structured ML dataset archives
- **Expected Yield:** 100–1,000+ per dataset entry
- **Access Method:** Dataset download handler — Kaggle CLI, direct download
- **Priority:** High for bulk collection

#### Tier 4 — 3D Interactive (EXCLUDED)
- **Count:** 757 rows
- **Sources:** 3DTuning.com
- **Status:** ❌ **Completely excluded — CGI renders, not real photographs**
- **Pipeline Action:** Skipped at job queue build stage

#### Tier 5 — Review Gallery
- **Count:** 1,514 rows | 1,513 VALID | 1 UNCERTAIN
- **Sources:** Car and Driver, MotorTrend
- **Image Quality:** Editorial photography — mixed content
- **Expected Yield:** 15–80 per model page
- **Access Method:** Browser automation with CDN extraction
- **Priority:** Medium

---

### All 73 Car Makes Confirmed in Excel

```
AM General     Acura          Alfa Romeo     Aston Martin   Audi
Bentley        Bugatti        Buick          Cadillac       Callaway Cars
Canoo          Chevrolet      Chrysler       Czinger        DeLorean
Dodge          Drako Motors   Elio Motors    Equus Auto     Faraday Future
Ferrari        Fiat           Fisker         Ford           GMC
Genesis        Haval          Hennessey      Honda          Hyundai
INEOS          Infiniti       Jaguar         Jeep           Karma Auto
Kia            Koenigsegg     Lamborghini    Land Rover     Lexus
Lincoln        Lotus          Lucid Motors   MINI           Mahindra
Maserati       Mazda          McLaren        Mercedes-Benz  Mitsubishi
Morgan         Nissan         Pagani         Peugeot        Polestar
Porsche        RAM            Rezvani        Rivian         Rolls-Royce
SSC N. America Saturn         Scion          Shelby         Smart
Subaru         Suzuki         Tesla          Toyota         VinFast
Volkswagen     Volvo
```

---

## 3. Project Folder Structure

Create this structure before running anything:

```
car_pipeline/
│
├── main.py                        ← entry point — run this to start
├── config.py                      ← all settings and thresholds
├── requirements.txt               ← all Python dependencies
│
├── input/
│   └── cars.xlsx                  ← place your Excel file here
│
├── scraper/
│   ├── excel_reader.py            ← reads Excel, builds job queue
│   ├── url_classifier.py          ← identifies URL type per row
│   ├── browser.py                 ← Playwright browser controller
│   ├── cdn_extractor.py           ← finds CDN image URLs in DOM
│   ├── navigator.py               ← clicks colors, arrows, pagination
│   ├── downloader.py              ← saves images to temp folder
│   └── dataset_handler.py         ← handles Kaggle, Roboflow, Open Images
│
├── vision/
│   └── yolo_filter.py             ← YOLOv8 + OpenCV filtering logic
│
├── organizer/
│   └── file_manager.py            ← renames and moves to final structure
│
├── temp_dataset/                  ← all downloads land here first
│
├── final_dataset/                 ← approved exterior images only
│   └── Make_Name/
│       └── Model_Name/
│           ├── Color_Name/        ← created only if colors detected
│           │   ├── image_001.jpg
│           │   └── image_002.jpg
│           ├── image_001.jpg      ← directly here if no colors found
│           └── image_002.jpg
│
├── rejected_images/               ← failed YOLO/OpenCV check — review and delete
│
└── logs/
    ├── run_log.csv                ← full run summary per model
    └── errors.txt                 ← all failed URLs and skipped rows
```

---

## 4. Installation & Setup

### One-Time Setup

```bash
# Install all Python dependencies
pip install playwright selenium beautifulsoup4 requests
pip install ultralytics opencv-python Pillow
pip install openpyxl pandas tqdm kaggle

# Install the Chromium browser engine
playwright install chromium
```

### Kaggle Setup (for Tier 3 dataset sources)

1. Create a free account at [kaggle.com](https://www.kaggle.com)
2. Go to **Account Settings → API → Create New Token**
3. Download `kaggle.json`
4. Place it at `~/.kaggle/kaggle.json` on your machine

> No paid Kaggle subscription needed. Public datasets are freely accessible.

### YOLO Model Setup

YOLOv8 downloads automatically on the first run:

```
yolov8n.pt  ← nano — fastest, works on CPU (~6MB download, one-time)
yolov8m.pt  ← medium — more accurate, recommended if GPU is available
```

After the first download, the model file is stored locally. No internet connection needed after that point.

### System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.10 | 3.11+ |
| RAM | 8GB | 16GB |
| Disk Space | 100GB | 500GB+ |
| GPU | Not required | Strongly recommended for YOLO speed |
| OS | Windows / macOS / Linux | Any |

---

## 5. Pipeline Workflow — Step by Step

### Step 1 — Read Excel and Build Job Queue

**What happens:**

- Pipeline opens `cars.xlsx` from `/input/`
- Reads every row from top to bottom
- Extracts from each row: Make, Model, Corrected URL, URL Status, Source Type, Tier

**Rules applied during reading:**

- Skip rows where URL Status is `INVALID` — log row number to errors.txt
- Skip rows where Tier is `4` — 3D render sources excluded entirely
- For `PARTIALLY INVALID` rows — use only the valid URL segment from Column 10
- Strip whitespace from all cell values
- Apply title case to Make and Model names
- Replace spaces with underscores for folder path construction

**Output:**

- Clean job list grouped by Make + Model
- Approximately **3,855 active jobs** after filtering out INVALID and Tier 4 rows

---

### Step 2 — Classify Each URL

Before visiting any URL, the pipeline detects which type of source it is:

```
Read corrected URL from Column 10
        ↓
Ends with .jpg / .jpeg / .png / .webp?
        → Type A: Direct image — download immediately
        ↓
Contains known CDN domain pattern?
        → Type B: CDN URL — strip params, download directly
        ↓
Contains kaggle.com?
        → Type C: Kaggle dataset — use Kaggle handler
        ↓
Contains roboflow.com or universe.roboflow.com?
        → Type D: Roboflow dataset — browser + extract image URLs
        ↓
Contains storage.googleapis.com/openimages?
        → Type E: Open Images — class-based downloader
        ↓
All other URLs:
        → Type F: Gallery or review website — full browser automation
```

---

### Step 3 — Browser Automation

*(Applies to Type F: Tier 1, Tier 2, Tier 5 gallery and review sites)*

See [Section 6 — Browser Automation](#6-browser-automation) for full detail.

---

### Step 4 — CDN Extraction

Runs after every browser interaction.

See [Section 7 — CDN Extraction Logic](#7-cdn-extraction-logic) for full detail.

---

### Step 5 — Download to Temp Folder

See [Section 9 — Image Downloading](#9-image-downloading) for full detail.

---

### Step 6 — YOLO Filtering

See [Section 10 — YOLO Filtering](#10-yolo-filtering) for full detail.

---

### Step 7 — File Organization

See [Section 11 — File Organization](#11-file-organization) for full detail.

---

## 6. Browser Automation

### When It Runs

Browser automation runs for all **Type F URLs** — gallery pages, press kit pages, and editorial review pages from Tier 1, Tier 2, and Tier 5 sources.

### Step-by-Step Browser Process

#### 6.1 Open the Browser

- Launch Chromium via Playwright in **headless mode** (no visible window) for production
- Use **headed mode** (visible window) when debugging: `python main.py --headed`
- Set a realistic browser user-agent string to avoid bot detection
- Configure browser to handle JavaScript rendering fully

#### 6.2 Navigate to URL

- Go to the corrected URL from Column 10
- Wait for `networkidle` state — browser waits until no network requests have fired for 500ms
- This ensures all JavaScript has finished and all image tags are rendered in the DOM
- If page fails to load within 30 seconds — log to errors.txt, skip, move to next

#### 6.3 Scroll the Page

- Scroll incrementally from top to bottom
- Pause briefly at each scroll step
- This forces lazy-loaded images to appear in the DOM
- Images below the visible viewport are invisible in page source until scrolled to
- After reaching the bottom — scroll back up once to trigger any remaining load events

#### 6.4 Initial DOM Scan

- After full-page scroll — run CDN extractor on the complete page source
- Collect all CDN image URLs found at this point
- Store in a Python `set()` — exact duplicates removed automatically

#### 6.5 Click Color Swatches

- Scan DOM for color selector elements
- **Common patterns detected:**
  - `[data-color]`
  - `.color-swatch`
  - `.color-option`
  - `button[aria-label*="color"]`
  - `.variant-color`
  - `[data-variant]`

**If color swatches are found:**

- Record the color name from the element label or `data-` attribute
- Click color 1 → wait 1.5 seconds → run CDN extractor → collect URLs
- Click color 2 → wait 1.5 seconds → run CDN extractor → collect URLs
- Repeat for every color option available on the page
- Tag each collected URL with the color name for folder organization later

**If no color swatches found:** continue without color tagging — images go directly into the Model folder.

#### 6.6 Handle Pagination and Arrows

- Scan for Next buttons and carousel arrows
- **Common patterns detected:**
  - `[aria-label='Next']`
  - `.slick-next`
  - `.arrow-right`
  - `button.next`
  - `.carousel-control-next`
  - `[data-slide='next']`

**If pagination found:**

- Click Next → wait for DOM update → run CDN extractor → collect URLs
- Keep clicking until Next button has `disabled` attribute or no longer exists
- This captures every slide across the full gallery carousel

#### 6.7 Navigate Sub-Model and Variant Links

- Scan the current page for internal links to model variants or trim levels
- Examples: `/legend/sport`, `/camry/xle`, `/mustang/gt500`, `/kiger/rxt`
- Add each variant URL to a sub-queue
- Process each sub-page through the full cycle: scroll → colors → pagination → extract
- This captures images that only appear on specific trim or variant pages

#### 6.8 Final URL Collection

- After all page interactions complete — take the full deduplicated URL set
- Pass the complete set to the downloader

---

## 7. CDN Extraction Logic

### What Is a CDN and Why It Matters

A CDN (Content Delivery Network) hosts and delivers media files at high speed. Manufacturer websites and automotive publications host their car images on CDNs. By extracting the CDN URL directly, the pipeline bypasses compression applied to inline thumbnails and retrieves the original high-resolution source file.

### What the Extractor Scans in the DOM

| Tag / Attribute | What It Contains |
|---|---|
| `<img src="">` | Primary image source |
| `<img srcset="">` | Multiple resolution options |
| `<img data-src="">` | Lazy-load source |
| `<img data-lazy="">` | Alternative lazy-load attribute |
| `<img data-original="">` | Original uncompressed source |
| `<source>` inside `<picture>` | Responsive image sources |
| Inline CSS `background-image` | Hero and banner images |
| JSON-LD script blocks | Structured image URL arrays |

### CDN Domains Targeted

```
akamaized.net        ← used by major manufacturers
cloudfront.net       ← Amazon CDN, used by media and review sites
imgix.net            ← used by automotive publications
fastly.net           ← used by gallery and media platforms
scene7.com           ← used by Ford, GM, dealer networks
cdn.*                ← generic CDN subdomain pattern
media.*              ← media subdomain pattern
images.*             ← images subdomain pattern
assets.*             ← assets subdomain pattern
```

### Resolution Selection Logic

- From `srcset` — always selects the URL with the **largest width descriptor**
- Strips compression query parameters — removes `?w=400`, `?q=60`, `&resize=800`, `&width=300`
- Replaces size tokens in URL paths:
  - `_thumb` → `_large`
  - `_sm` → `_hd`
  - `_300` → `_1920`
- If multiple sizes of the same image are found — keeps only the largest

### What Is Immediately Rejected

- URLs containing `/icon/`, `/logo/`, `/favicon` in the path
- URLs ending with `.gif` — UI animation elements, not car photos
- URLs containing `/placeholder/` or `/blank/` in path
- Any URL that resolves to a file under **50KB** when fetched

---

## 8. URL Type Handling

### Type A — Direct Image URL

- **Detection:** URL ends with `.jpg`, `.jpeg`, `.png`, `.webp`
- **Action:** Send direct HTTP GET request → validate → save to `/temp_dataset/`
- **No browser needed**

### Type B — CDN URL with Compression Parameters

- **Detection:** URL contains a known CDN domain with query string parameters
- **Action:** Strip compression params → request clean URL → download directly
- **No browser needed**

### Type C — Kaggle Dataset Pages

- **Detection:** URL contains `kaggle.com`
- **Action:**
  - Use Kaggle CLI with `kaggle.json` credentials
  - Download dataset archive to local path
  - Extract ZIP — scan for image files
  - Filter by make/model relevance in filenames or folder paths
- **No browser needed — requires free Kaggle account**

### Type D — Roboflow Dataset Pages

- **Detection:** URL contains `roboflow.com` or `universe.roboflow.com`
- **Action:**
  - Open page in browser
  - Browse image listing — extract direct image URLs
  - Download each image individually
- **Browser used — no API key needed for public datasets**

### Type E — Open Images (Google)

- **Detection:** URL contains `storage.googleapis.com/openimages`
- **Action:**
  - Use `openimages` downloader package (open source)
  - Filter by class label `car`
  - Download car-class images up to configured per-run limit
- **No browser needed — direct class-based download**

### Type F — Gallery and Review Websites

- **Detection:** All other URLs — Tier 1, Tier 2, Tier 5 sources
- **Action:** Full browser automation as described in [Section 6](#6-browser-automation)
- **Browser required**

---

## 9. Image Downloading

### Download Process for Every URL

```
Send HTTP GET request with browser-like headers
        ↓
Check Content-Type — must be image/jpeg or image/png
        ↓ FAIL → discard, log to errors.txt
        ↓ PASS
Check file size — must be above 50KB
        ↓ FAIL → discard, log as "thumbnail or placeholder"
        ↓ PASS
Save to /temp_dataset/
        ↓
Wait 1–2 seconds before next request
```

### Temporary Filename Format

```
temp_{make}_{model}_{color}_{sequence}.jpg

# With color detected:
temp_toyota_camry_midnight_black_001.jpg
temp_ford_mustang_race_red_002.jpg

# Without color detected:
temp_acura_nsx_001.jpg
temp_honda_accord_003.jpg
```

### Download Pacing

| Scenario | Delay |
|---|---|
| Standard download | 1–2 seconds (randomized) |
| After receiving 429 response | Increases to 3–5 seconds automatically |
| Kaggle/dataset downloads | No delay needed — direct archive |

### Error Handling

| Error | Action |
|---|---|
| 403 Forbidden | Log URL and skip |
| 404 Not Found | Log URL and skip |
| Timeout (10s) | Retry once — if fails again, log and skip |
| Connection error | Log and skip |
| File below 50KB | Discard immediately — log as rejected |
| Wrong content type | Discard immediately |

---

## 10. YOLO Filtering

### Overview

After all downloads for a model are complete, every image in `/temp_dataset/` passes through two sequential filtering stages. Only images that pass both stages are approved for the final dataset.

### Stage 1 — YOLO Car Detection

```
Load YOLOv8 model (local .pt file)
        ↓
Run inference on image
        ↓
Are relevant objects detected? (car, bus, truck, motorcycle)
        ↓ NO  → move to /rejected_images/ — log: "no car detected"
        ↓ YES
Confidence score at or above 0.35?
        ↓ NO  → move to /rejected_images/ — log: "low confidence"
        ↓ YES
Does YOLO detect an interior element (e.g. chair/seat) inside the car?
        ↓ YES → move to /rejected_images/ — log: "YOLO interior detected"
        ↓ NO
Are bounding box proportions extreme (Width > 70% AND Height > 96%)?
        ↓ YES → move to /rejected_images/ — log: "extreme crop/interior view"
        ↓ NO
Pass to Stage 2
```

**Model options:**

| Model File | Speed | Accuracy | Best For |
|---|---|---|---|
| `yolov8n.pt` | Fastest | Good | CPU-only machines |
| `yolov8m.pt` | Slower | Better | GPU-available machines |

### Stage 2 — Exterior Confirmation (OpenCV)

Runs on every image that passed Stage 1. YOLO confirms a car exists but cannot distinguish exterior from interior. OpenCV heuristics make that determination.

**Interior signals detected and rejected:**

| Signal | Detection Method |
|---|---|
| Dashboard / instrument panel | High gray/black/beige tone ratio in center 60% of image |
| Dashboard panel signature | Horizontal line density in lower center region |
| Steering wheel | Circular contour with internal spokes detected |
| Seat upholstery | Large flat beige/gray region in mid-frame |

**Exterior confirmation signals:**

| Signal | Detection Method |
|---|---|
| Car occupies frame | Car bounding box covers 40%+ of total frame area |
| Outdoor environment | Sky visible at top edge or ground visible at bottom edge |
| No interior signals | None of the interior patterns detected above |

### Complete Filtering Decision

```
Image in /temp_dataset/
        ↓
YOLO — relevant vehicle detected (car/truck/bus/motorcycle) > 0.35 conf?
        ↓ NO  →  /rejected_images/  [no car detected]
        ↓ YES
YOLO — interior class (chair/seat) detected?
        ↓ YES →  /rejected_images/  [YOLO interior detected]
        ↓ NO
YOLO — is it an extreme crop? (height > 96% and width > 70%)
        ↓ YES →  /rejected_images/  [extreme crop/interior view]
        ↓ NO
OpenCV — interior signals present?
        ↓ YES →  /rejected_images/  [interior detected]
        ↓ NO
Car occupies 40%+ of frame? (or min completeness ratio met)
        ↓ NO  →  /rejected_images/  [car too small or partial/incomplete view]
        ↓ YES   
━━━━━━━━━━━━━━━━━━━━━━━━━━
IMAGE APPROVED
━━━━━━━━━━━━━━━━━━━━━━━━━━
Move to /final_dataset/{Make}/{Model}/{Color}/
```

### Expected Approval Rates by Tier

| Source Tier | Expected Approval Rate | Reason |
|---|---|---|
| Tier 1 — Official Press Kit | 85–95% | Official exterior studio shots |
| Tier 2 — Photo Gallery | 75–90% | Professional photography |
| Tier 3 — ML Datasets | 60–80% | Mixed content in bulk datasets |
| Tier 5 — Review Gallery | 55–75% | Mixed editorial — interiors, lifestyle |

---

## 11. File Organization

### Folder Path Construction Logic

```
Approved image ready
        ↓
Read tracked metadata: which Make / Model / Color
        ↓
Color was detected during scraping?
        ↓ YES:
        /final_dataset/{Make}/{Model}/{Color}/
        ↓ NO:
        /final_dataset/{Make}/{Model}/
        ↓
Create folders if they do not exist
        ↓
Rename image sequentially within folder:
image_001.jpg, image_002.jpg, image_003.jpg ...
        ↓
Move from /temp_dataset/ to constructed path
```

### Folder Naming Rules

| Rule | Example |
|---|---|
| Title case applied | `toyota` → `Toyota` |
| Spaces to underscores | `Midnight Black` → `Midnight_Black` |
| Special characters removed | `e-tron` → `e_tron` |
| Consistent across all runs | Same name always produces same folder |

### Image Naming Convention

- Sequence counter resets at `001` for each Make/Model/Color folder
- Naming is independent per folder — no global counter

```
image_001.jpg
image_002.jpg
image_003.jpg
```

### Final Output Structure Example

```
final_dataset/
├── Toyota/
│   ├── Camry/
│   │   ├── Midnight_Black/
│   │   │   ├── image_001.jpg
│   │   │   ├── image_002.jpg
│   │   │   └── image_003.jpg
│   │   ├── Celestial_Silver/
│   │   │   └── image_001.jpg
│   │   └── Blueprint/
│   │       ├── image_001.jpg
│   │       └── image_002.jpg
│   └── Supra/
│       ├── image_001.jpg
│       └── image_002.jpg
├── Ford/
│   └── Mustang/
│       ├── Race_Red/
│       │   └── image_001.jpg
│       └── Oxford_White/
│           └── image_001.jpg
├── Acura/
│   └── NSX/
│       ├── Sonic_Gray_Pearl/
│       │   └── image_001.jpg
│       └── image_001.jpg
... (73 makes, 756 model folders total)
```

> **Color folders are only created when the browser detects and clicks color swatches on the actual website during scraping. If a model page has no color selector, images go directly into the Model folder.**

---

## 12. Logging & Run Summary

### run_log.csv — One Row Per Model Processed

| Field | Example Value |
|---|---|
| make | Toyota |
| model | Camry |
| tier | Tier 1 |
| source_type | Official Press Kit / Gallery |
| urls_processed | 4 |
| images_downloaded | 87 |
| images_approved | 61 |
| images_rejected | 26 |
| rejection_rate | 29.9% |
| colors_detected | Midnight Black, Celestial Silver, Blueprint |
| run_duration_seconds | 184 |
| errors | 2 |
| timestamp | 2025-03-13T10:45:00Z |

### errors.txt — One Entry Per Issue

```
ROW 4    — SKIPPED: URL Status = INVALID
ROW 11   — DOWNLOAD FAILED: 403 Forbidden — https://...
ROW 47   — FILE TOO SMALL: 18KB — discarded — https://...
ROW 83   — TIMEOUT: No response after 10s — retried once — failed — skipped
ROW 156  — TIER 4: 3D render source — skipped entirely
```

---

## 13. Running the Pipeline

### All Available Commands

```bash
# Run the complete pipeline — all makes and models
python main.py

# Run only for a specific make
python main.py --make Toyota

# Run only for a specific make and model
python main.py --make Toyota --model Camry

# Run only Tier 1 and Tier 2 sources (highest image quality)
python main.py --tiers 1,2

# Run with browser window visible — for debugging
python main.py --headed

# Run only YOLO filtering on existing temp_dataset
python main.py --filter-only

# Run only file organization after filtering is done
python main.py --organize-only

# Include UNCERTAIN status URLs in the run
python main.py --include-uncertain

# Resume from a specific make if a previous run was interrupted
python main.py --resume --make Honda
```

### What Happens When You Run `python main.py`

```
Step 1   Read cars.xlsx from /input/
Step 2   Parse all rows — extract make, model, corrected URL, status, tier
Step 3   Skip INVALID rows — skip Tier 4 rows — fix PARTIALLY INVALID rows
Step 4   Build job queue — approximately 3,855 active jobs
Step 5   For each job — classify URL type
Step 6   Type A/B → download directly to /temp_dataset/
Step 7   Type C → Kaggle CLI download and extract
Step 8   Type D → browser to Roboflow — extract image URLs — download
Step 9   Type E → Open Images class-based download
Step 10  Type F → open browser — scroll — colors — pagination — variants — CDN extract — download
Step 11  After each model batch — run YOLO Stage 1 on all images in /temp_dataset/
Step 12  Run OpenCV Stage 2 on images that passed Stage 1
Step 13  Approved → move to /final_dataset/{Make}/{Model}/{Color}/
Step 14  Rejected → move to /rejected_images/
Step 15  Rename approved images sequentially within each folder
Step 16  Write row to run_log.csv
Step 17  Append any errors to errors.txt
Step 18  Print progress to terminal
Step 19  Move to next model
Step 20  After all models — print final summary to terminal
Step 21  Pipeline exits cleanly
```

---

## 14. Complete Flow Diagram

```
╔══════════════════════════════════════════════════════════════╗
║                      cars.xlsx                               ║
║         73 Makes · 756 Models · 5,299 Rows                   ║
╚══════════════════════════════════════════════════════════════╝
                            │
                            ▼
              ┌─────────────────────────┐
              │    Excel Reader         │
              │  Read Column 10 only    │
              │  Skip INVALID (4 rows)  │
              │  Skip Tier 4 (757 rows) │
              │  Fix PARTIALLY INVALID  │
              │  Active jobs: ~3,855    │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │     URL Classifier      │
              │  Detect URL type        │
              └────────────┬────────────┘
                           │
         ┌─────────────────┼──────────────────────┐
         │                 │                       │
         ▼                 ▼                       ▼
  ┌─────────────┐  ┌───────────────┐    ┌──────────────────┐
  │  Direct /   │  │   Dataset     │    │  Gallery/Review  │
  │  CDN URL    │  │  Kaggle /     │    │  Website         │
  │  Type A, B  │  │  Roboflow /   │    │  Tier 1, 2, 5    │
  │             │  │  Open Images  │    │  Type F          │
  │  Download   │  │  Type C,D,E   │    │                  │
  │  directly   │  │               │    │  Open Chromium   │
  └──────┬──────┘  │  Download     │    │  Wait networkidle│
         │         │  archives or  │    │  Scroll page     │
         │         │  browse pages │    │  Click colors    │
         │         └───────┬───────┘    │  Click Next      │
         │                 │            │  Follow variants │
         │                 │            │  CDN extraction  │
         └─────────────────┴─────┬──────┘
                                 │
                                 ▼
                  ┌──────────────────────────┐
                  │    /temp_dataset/         │
                  │  All downloads staged     │
                  │  Filename tracks:         │
                  │  make / model / color     │
                  └──────────────┬────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────┐
                  │   YOLO Stage 1           │
                  │  Car detected ≥ 0.60?    │
                  └──────────────┬────────────┘
                                 │
               ┌─────────────────┴─────────────────┐
               ▼                                   ▼
          NO / LOW CONF                       YES — PASS
      /rejected_images/           ┌──────────────────────────┐
                                  │   OpenCV Stage 2         │
                                  │  Interior signals found? │
                                  └──────────────┬────────────┘
                                                 │
                               ┌─────────────────┴──────────────┐
                               ▼                                 ▼
                     INTERIOR DETECTED                   NO INTERIOR
                      /rejected_images/          ┌───────────────────────┐
                                                 │  Car occupies 40%+?   │
                                                 └──────────┬────────────┘
                                                            │
                                         ┌──────────────────┴──────────────┐
                                         ▼                                  ▼
                                    TOO SMALL                        APPROVED ✓
                                 /rejected_images/                          │
                                                                            ▼
                                                         ┌──────────────────────────────┐
                                                         │       File Manager           │
                                                         │                              │
                                                         │  With color detected:        │
                                                         │  /final_dataset/             │
                                                         │   Make/Model/Color/          │
                                                         │                              │
                                                         │  Without color:              │
                                                         │  /final_dataset/             │
                                                         │   Make/Model/                │
                                                         │                              │
                                                         │  Renamed sequentially:       │
                                                         │  image_001.jpg ...           │
                                                         └──────────────┬───────────────┘
                                                                        │
                                                                        ▼
                                                         ┌──────────────────────────────┐
                                                         │        Logging               │
                                                         │  run_log.csv updated         │
                                                         │  errors.txt updated          │
                                                         └──────────────┬───────────────┘
                                                                        │
                                                                        ▼
                                                         ╔══════════════════════════════╗
                                                         ║   Dataset Complete           ║
                                                         ║   Training-Ready             ║
                                                         ╚══════════════════════════════╝
```

---

## 15. Expected Output & Scale

### Image Yield Estimate by Tier

| Source Tier | Valid Rows | Avg Images Per URL | Estimated Total |
|---|---|---|---|
| Tier 1 — Official Press Kit | 753 | 100–500 | 75,000–377,000 |
| Tier 2 — Photo Gallery | 739 | 50–200 | 37,000–148,000 |
| Tier 3 — ML Datasets | 850 | 100–1,000+ | 85,000–850,000+ |
| Tier 5 — Review Gallery | 1,513 | 15–80 | 22,000–121,000 |
| **Total** | **3,855** | | **219,000–1.4M+** |

> After YOLO filtering, expect **60–80% approval rate** across the full dataset. Tier 1 sources (official press photography) will have the highest approval rate. Tier 5 (editorial review galleries) will have more rejections due to mixed interior and lifestyle content.

### Final Dataset After Complete Run

```
final_dataset/
├── Acura/           19 models
├── Alfa Romeo/       8 models
├── Aston Martin/    15 models
├── Audi/            28 models
├── Bentley/         10 models
├── Bugatti/         13 models
├── Buick/           16 models
├── Cadillac/        26 models
├── Chevrolet/       44 models
├── Ford/            28 models
├── Honda/           15 models
├── Hyundai/         21 models
├── Kia/             23 models
├── Toyota/          32 models
├── Volkswagen/      14 models
├── Volvo/           14 models
... 73 makes total, 756 model folders
```

---

## 16. Constraints & Limitations

### Known Issues and How They Are Handled

| Issue | Impact | How Pipeline Handles It |
|---|---|---|
| Stanford Cars URL broken (664 rows) | Tier 3 partially affected | Column 10 already contains working URL — resolved automatically |
| Some sites block headless browsers | May cause 403 errors | Realistic user-agent + randomized delays mitigate this |
| Kaggle requires credentials | Tier 3 Kaggle rows need setup | Free account + kaggle.json — one-time setup |
| UNCERTAIN URLs not verified | 63 rows may fail | Skipped by default — use `--include-uncertain` to attempt |
| Interior detection not perfect | Some interiors may pass | Stage 2 heuristics catch majority — improve with custom YOLO fine-tune |
| Rate limiting on aggressive sites | Slower collection | Auto-delay increase after 429 response |

### CPU vs GPU Speed

| Hardware | YOLO Inference Speed | 200 Images Processing Time |
|---|---|---|
| CPU only | 2–5 seconds/image | ~15 minutes |
| GPU (NVIDIA) | 0.1–0.5 seconds/image | ~1 minute |

### Improvement Path After First Dataset Is Built

1. Label 500+ collected images as `car_exterior` / `car_interior` / `engine_bay`
2. Fine-tune YOLOv8 on your own labeled data
3. Replace the Stage 2 OpenCV heuristic with the fine-tuned custom model
4. Accuracy improves from approximately 75% to 95%+
5. Add parallel Playwright sessions to scrape multiple makes simultaneously
6. Add GPU-accelerated YOLO inference for 10x speed improvement

---

## Quick Reference

### Libraries Used

```
playwright          Browser automation
beautifulsoup4      HTML parsing
requests            HTTP image downloading
ultralytics         YOLOv8 local model (no API key)
opencv-python       Exterior/interior heuristic analysis
Pillow              Image validation and processing
openpyxl            Excel file reading
pandas              Data manipulation
tqdm                Progress bar during downloads
kaggle              Kaggle dataset CLI (free account)
```

### Key Thresholds

```
YOLO confidence threshold    0.60 (configurable in config.py)
Minimum file size            50KB
Scroll wait after color      1.5 seconds
Request delay                1–2 seconds (randomized)
Page load timeout            30 seconds
Download retry limit         1 retry per URL
```

### One-Line Summary

> Read Excel → Skip 3D renders → Classify URLs → Browser automation or direct download → CDN extraction → Download to temp → YOLO filter → OpenCV exterior check → Organize by Make/Model/Color → Training-ready dataset. No API keys. No paid tools. Fully local.

---

*Documentation generated based on full analysis of URL_FOR_CAR_MAKES_AND_THEIR_MODELS.xlsx — 5,299 rows, 73 makes, 756 models.*
