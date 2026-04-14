# Plan: Full Anti-Bot Stealth Hardening

After analysing every file in the pipeline, here is a complete list of weaknesses found and the fixes I will apply.

## Identified Issues & Fixes

---

### 1. `driver.py` — WebDriver Fingerprinting (HIGH RISK)

| Issue | Fix |
|---|---|
| `--disable-blink-features=AutomationControlled` is set but `navigator.webdriver` deletion in stealth JS is redundant — needs cleanup | Clean up and consolidate all stealth patches |
| CDP `Network.setUserAgentOverride` is set but `Accept-Language` header is not matching the `navigator.languages` spoof | Synchronize CDP headers with JS spoofing |
| No `screen resolution` spoofing beyond `--window-size` | Inject JS to match `screen.width/height` to the chosen window size |
| `document.documentElement.runtimes` (**missing `automation` property removal**) | Remove automation-related properties from `navigator.permissions` |
| No WebGL renderer spoofing | Spoof `WEBGL_debug_renderer_info` to mask headless signatures |
| No `HairlineFeature` / `iframe` sandbox detection mitigations | Add standard mitigations |
| No fake battery API | Add `navigator.getBattery()` spoof returning realistic values |
| User agents reference `Chrome/147` which is extremely new and may itself be a flag | Replace with typical production-range UAs (135–145) |

---

### 2. `config.py` — Timing & Profile (HIGH RISK)

| Issue | Fix |
|---|---|
| `inter_page_delay: int = 3` — fixed 3-second gap is robotic | Change to random jitter range using `min/max` |
| `page_load_wait: int = 10` — same wait every time is detectable | Randomize page-load wait slightly |
| `first_page_wait: int = 30` — hardcoded and not actually used for waiting | Ensure it's wired up correctly in collect logic |
| `request_delay_min: float = 0.5` — minimum 0.5s is far too fast for ScienceDirect | Change minimum to `2.0` |

---

### 3. `collect.py` — Page Collection (MEDIUM RISK)

| Issue | Fix |
|---|---|
| After bot clearance, it immediately runs `WebDriverWait` — no jitter between challenge clear and scraping | Add `random.uniform(3, 6)` sleep after clearance |
| All pages use the same inter-page delay with no variance | Already addressed in `config.py` fix |
| Does not scroll before waiting for elements — zero interaction is a bot signal | Add a small scroll before element detection |

---

### 4. `cloudflare.py` — Challenge Detection (MEDIUM RISK)

| Issue | Fix |
|---|---|
| Only checks for Cloudflare challenge elements, not ScienceDirect's own "access denied" page | Add detection of SD-specific access restriction patterns |
| Polling at exactly `2.0` seconds is robotic | Jitter the poll interval (`1.5–2.5s`) |
| No logging of page title during wait — hard to debug what challenge is shown | Log page title while waiting |

---

### 5. `scrape.py` — Article Scraping (MEDIUM RISK)

| Issue | Fix |
|---|---|
| `is_first` parameter detection adds a slightly different first-page delay — bots often do this identically | Treat every page with full jitter, not just non-first |
| `post_nav_jitter` is `1.5` but `random.uniform(1.0, 1.5)` has a tiny window | Widen jitter range |

---

### 6. `models.py` — Code Quality (LOW RISK)

| Issue | Fix |
|---|---|
| `scraped_skipped` is defined **twice** on lines 188 and 189 — this is a Python dataclass bug (silently discards one) | Remove the duplicate field |

---

## Files to Change

#### [MODIFY] [driver.py](file:///d:/Workspace/Mindgram/mindgram-scraper/scraper_pipeline/utils/driver.py)
- Upgrade stealth JS with screen, WebGL, battery, and permissions spoofing.
- Fix User-Agent list to use realistic Chrome 135–143 versions.
- Sync CDP headers with JS navigator language spoof.

#### [MODIFY] [config.py](file:///d:/Workspace/Mindgram/mindgram-scraper/scraper_pipeline/config.py)
- Increase minimum request delay to 2.0 seconds.
- Add `inter_page_delay_min/max` range instead of fixed value.

#### [MODIFY] [collect.py](file:///d:/Workspace/Mindgram/mindgram-scraper/scraper_pipeline/stages/collect.py)
- Add scroll-before-scrape to every listing page.
- Add post-clearance jitter.

#### [MODIFY] [cloudflare.py](file:///d:/Workspace/Mindgram/mindgram-scraper/scraper_pipeline/utils/cloudflare.py)
- Add ScienceDirect-specific block detection.
- Jitter poll interval.
- Log page title during wait.

#### [MODIFY] [models.py](file:///d:/Workspace/Mindgram/mindgram-scraper/scraper_pipeline/models.py)
- Fix duplicate `scraped_skipped` field in `PipelineResult`.
