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
// 1. Hide webdriver property completely
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
delete navigator.__proto__.webdriver;

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

// 3. Spoof languages — match exactly what CDP sets
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'language', { get: () => 'en-US' });

// 4. Fix chrome object (undetected_chromedriver can miss this)
window.chrome = {
    app: { isInstalled: false, getDetails: function(){}, getIsInstalled: function(){}, runningState: function(){} },
    runtime: {
        PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
        PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
        RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
        OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
        connect: function() {},
        sendMessage: function() {},
    },
    loadTimes: function() {},
    csi: function() {},
};

// 5. Permissions — match real Chrome (notifications prompt, not denied)
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// 6. Screen resolution — match window size set at launch
Object.defineProperty(screen, 'width', { get: () => window.outerWidth || 1366 });
Object.defineProperty(screen, 'height', { get: () => window.outerHeight || 768 });
Object.defineProperty(screen, 'availWidth', { get: () => window.outerWidth || 1366 });
Object.defineProperty(screen, 'availHeight', { get: () => (window.outerHeight || 768) - 40 });
Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });

// 7. WebGL — spoof renderer to avoid headless detection
try {
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';  // UNMASKED_VENDOR_WEBGL
        if (parameter === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
        return getParameter.call(this, parameter);
    };
    const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter2.call(this, parameter);
    };
} catch(e) {}

// 8. Battery API — return realistic values
try {
    Object.defineProperty(navigator, 'getBattery', {
        get: () => () => Promise.resolve({
            charging: true,
            chargingTime: 0,
            dischargingTime: Infinity,
            level: 0.87 + Math.random() * 0.1,
            addEventListener: () => {},
        })
    });
} catch(e) {}

// 9. Connection — spoof network info
try {
    Object.defineProperty(navigator, 'connection', {
        get: () => ({
            rtt: 50 + Math.floor(Math.random() * 50),
            downlink: 8 + Math.random() * 4,
            effectiveType: '4g',
            saveData: false,
        })
    });
} catch(e) {}

// 10. Hardware concurrency — typical 4-core machine
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

// 11. Device memory — typical real-browser value
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// 12. Canvas fingerprint — add subtle noise to avoid unique signature
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

// 13. Remove automation-related iframe detection
Object.defineProperty(document, 'hidden', { get: () => false });
Object.defineProperty(document, 'visibilityState', { get: () => 'visible' });
"""

# ---------------------------------------------------------------------------
# Realistic User-Agent pool — Chrome 147, matching the installed browser.
# The minor version variants add diversity without triggering version mismatch.
# ---------------------------------------------------------------------------
_STEALTH_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.56 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.67 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.88 Safari/537.36",
    # Mac variants for header diversity
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.56 Safari/537.36",
]


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

    # Stealth: remove ALL automation traces
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-infobars")
    options.add_argument("--excludeSwitches=enable-automation")
    options.add_argument("--useAutomationExtension=false")

    # Stealth: look like a real browser
    options.add_argument("--disable-extensions-file-access-check")
    options.add_argument("--disable-extensions-http-throttling")
    options.add_argument("--disable-ipc-flooding-protection")

    # Stealth: realistic media & GPU flags
    options.add_argument("--enable-webgl")
    options.add_argument("--use-gl=swiftshader")
    options.add_argument("--enable-accelerated-2d-canvas")

    # Stealth: avoid bot-checked flags
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")

    # Random window size — avoid the perfect 1920x1080 bot fingerprint
    resolutions = [(1366, 768), (1280, 800), (1440, 900), (1536, 864), (1600, 900), (1280, 1024)]
    chosen_w, chosen_h = random.choice(resolutions)
    options.add_argument(f"--window-size={chosen_w},{chosen_h}")

    # User Agent — pick a stealth UA from our list
    ua_pool = cfg.user_agents if cfg.user_agents else _STEALTH_USER_AGENTS
    ua = random.choice(ua_pool)
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

        # Give the browser a moment to register its window handle
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
    _apply_cdp_stealth(driver, ua)

    _log.debug(
        "Stealth driver ready (version=%d, res=%dx%d, profile=%s)",
        cfg.chrome_version, chosen_w, chosen_h, user_data_dir
    )
    return driver


@contextmanager
def managed_driver(cfg: ChromeConfig) -> Iterator[uc.Chrome]:
    """
    Context manager that creates a driver and guarantees driver.quit()
    even if an exception is raised inside the `with` block.
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
        time.sleep(random.uniform(1.2, 2.8))

        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")

        if total_height > viewport_height:
            scroll_steps = random.randint(3, 7)
            for _ in range(scroll_steps):
                # Irregular scroll amounts — humans don't scroll perfectly
                scroll_by = random.randint(100, 400)
                driver.execute_script(f"window.scrollBy({{top: {scroll_by}, left: 0, behavior: 'smooth'}});")
                time.sleep(random.uniform(0.5, 1.5))

            # Occasionally read back up (as if re-reading something)
            if random.random() > 0.35:
                scroll_up = random.randint(100, 300)
                driver.execute_script(f"window.scrollBy({{top: -{scroll_up}, left: 0, behavior: 'smooth'}});")
                time.sleep(random.uniform(0.5, 1.2))

            # Occasionally move to bottom and back (real reading behavior)
            if random.random() > 0.7:
                driver.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
                time.sleep(random.uniform(0.8, 1.5))
                driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
                time.sleep(random.uniform(0.5, 1.0))

        # 2. Final "done reading, moving to next" pause
        time.sleep(random.uniform(1.0, 2.2))

    except Exception as exc:
        _log.debug("Stealth jitter failed (non-critical): %s", exc)
