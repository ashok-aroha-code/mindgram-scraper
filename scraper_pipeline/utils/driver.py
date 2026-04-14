"""
utils/driver.py — Chrome WebDriver factory with full stealth layer.

Centralised here so both the collector and scraper stages use
identical driver configuration with no duplication.
"""

from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import undetected_chromedriver as uc

from scraper_pipeline.config import ChromeConfig

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CDP Stealth Injection Script
# Injected on every new document to spoof all JS fingerprinting vectors.
# ---------------------------------------------------------------------------
_STEALTH_JS = """
// 1. Hide webdriver property
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. Spoof plugins (real Chrome has plugins, bots have 0)
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const arr = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
        ];
        arr.__proto__ = PluginArray.prototype;
        return arr;
    }
});

// 3. Spoof languages
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

// 4. Fix chrome object (undetected_chromedriver can miss this)
window.chrome = {
    app: { isInstalled: false },
    runtime: {
        PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
        PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
        RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
        OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }
    }
};

// 5. Spoof permissions (real Chrome returns 'granted' for notifications)
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// 6. Hide automation-related properties in the prototype chain
delete navigator.__proto__.webdriver;

// 7. Randomize canvas fingerprint slightly
const origToBlob = HTMLCanvasElement.prototype.toBlob;
const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;

function addNoise(data) {
    for (let i = 0; i < data.length; i += 100) {
        data[i] = data[i] ^ (Math.random() * 3 | 0);
    }
    return data;
}

HTMLCanvasElement.prototype.toDataURL = function(type) {
    const ctx = this.getContext('2d');
    if (ctx) {
        const imageData = origGetImageData.call(ctx, 0, 0, this.width, this.height);
        addNoise(imageData.data);
        ctx.putImageData(imageData, 0, 0);
    }
    return origToDataURL.apply(this, arguments);
};
"""


def _apply_cdp_stealth(driver: uc.Chrome, ua: str) -> None:
    """Inject CDP commands to override fingerprinting on every new page."""
    try:
        # Override UA at CDP level (more reliable than --user-agent flag alone)
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": ua,
            "platform": "Win32",
            "acceptLanguage": "en-US,en;q=0.9",
        })

        # Inject stealth JS before any page JS runs
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": _STEALTH_JS
        })

        _log.debug("CDP stealth layer applied.")
    except Exception as exc:
        _log.debug("CDP stealth injection failed (non-critical): %s", exc)


def create_driver(cfg: ChromeConfig) -> uc.Chrome:
    """
    Build and return a fully-stealthed undetected Chrome driver.
    """
    options = uc.ChromeOptions()
    options.headless = cfg.headless

    # Core stability flags
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")

    # Stealth: remove automation traces
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-features=SearchEngineChoice,ProfilePicker,IsolateOrigins,site-per-process")
    options.add_argument("--disable-infobars")

    # Stealth: look like a real browser
    options.add_argument("--disable-extensions-file-access-check")
    options.add_argument("--disable-extensions-http-throttling")

    # Random window size — avoid the perfect 1920x1080 bot fingerprint
    resolutions = ["1366,768", "1280,800", "1440,900", "1536,864", "1600,900"]
    chosen_res = random.choice(resolutions)
    options.add_argument(f"--window-size={chosen_res}")

    # User Agent — pick a random one from the list
    ua = random.choice(cfg.user_agents) if cfg.user_agents else None

    if ua:
        options.add_argument(f"--user-agent={ua}")
        _log.debug("Using UA: %s", ua)

    # Sub-profile (for system profiles with multiple users)
    if cfg.profile_name:
        options.add_argument(f"--profile-directory={cfg.profile_name}")
        _log.debug("Using Sub-profile: %s", cfg.profile_name)

    # Resolve profile path to absolute
    user_data_dir = None
    if cfg.user_data_dir:
        user_data_dir = str(Path(cfg.user_data_dir).resolve())

    # Launch driver
    try:
        driver = uc.Chrome(
            options=options,
            version_main=cfg.chrome_version,
            user_data_dir=user_data_dir,
            use_subprocess=True
        )
        
        # Give the browser a moment to register its window handle before interaction
        time.sleep(1)
        try:
            driver.maximize_window()
            driver.execute_script("window.focus();")
        except Exception as win_exc:
            _log.debug("Non-critical: Could not maximize or focus window: %s", win_exc)
            
    except Exception as exc:
        msg = str(exc).lower()
        if "profile in use" in msg or "cannot create default profile directory" in msg:
            _log.critical(
                "CHROME PROFILE IS LOCKED — Close all Chrome windows and try again. "
                "Or run: taskkill /f /im chrome.exe"
            )
        else:
            _log.error("Failed to start undetected-chromedriver: %s", exc)
            _log.info("TIP: Try running 'taskkill /f /im chrome.exe' in your terminal.")
        raise

    # Apply CDP stealth injections
    if ua:
        _apply_cdp_stealth(driver, ua)

    _log.debug(
        "Stealth driver ready (version=%d, res=%s, profile=%s)",
        cfg.chrome_version, chosen_res, user_data_dir
    )
    return driver


@contextmanager
def managed_driver(cfg: ChromeConfig) -> Iterator[uc.Chrome]:
    """
    Context manager that creates a driver and guarantees driver.quit()
    even if an exception is raised inside the `with` block.

    Usage:
        with managed_driver(cfg.chrome) as driver:
            driver.get(url)
    """
    driver: Optional[uc.Chrome] = None
    try:
        driver = create_driver(cfg)
        yield driver
    finally:
        if driver is not None:
            try:
                driver.quit()
                _log.debug("Driver quit cleanly.")
            except Exception as exc:
                _log.debug("Driver quit raised (safe to ignore): %s", exc)


def perform_stealth_jitter(driver: uc.Chrome):
    """
    Simulates human reading behavior through random scrolling and micro-delays.
    Confuses bot detection systems that monitor static/robotic page interaction.
    """
    try:
        # 1. Initial "page loaded, starting to read" pause
        time.sleep(random.uniform(0.8, 2.0))

        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")

        if total_height > viewport_height:
            scroll_steps = random.randint(3, 6)
            for _ in range(scroll_steps):
                # Irregular scroll amounts — humans don't scroll perfectly
                scroll_by = random.randint(80, 350)
                driver.execute_script(f"window.scrollBy({{top: {scroll_by}, left: 0, behavior: 'smooth'}});")
                time.sleep(random.uniform(0.4, 1.2))

            # Occasionally read back up (as if re-reading something)
            if random.random() > 0.4:
                scroll_up = random.randint(80, 250)
                driver.execute_script(f"window.scrollBy({{top: -{scroll_up}, left: 0, behavior: 'smooth'}});")
                time.sleep(random.uniform(0.4, 0.9))

        # 2. Final "done reading, moving to next" pause
        time.sleep(random.uniform(0.8, 1.8))

    except Exception as exc:
        _log.debug("Stealth jitter failed (non-critical): %s", exc)
