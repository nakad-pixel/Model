"""
Project Astra - Global Constants
Configuration, Base DNA, fallback selectors, and timing intervals.
"""

from typing import List, Dict, Any

# =============================================================================
# DEFAULT PERSONA
# =============================================================================
DEFAULT_PERSONA_ID: str = "astra"

# =============================================================================
# PERSONA BASE DNA (MUST be included in every image generation prompt)
# =============================================================================
BASE_DNA_STRING: str = (
    "Photorealistic 8k portrait of Astra, 24yo woman, "
    "honey blonde mid-length wavy hair, hazel eyes with distinct upper-right catchlight, "
    "natural flawless skin texture with visible pores, slight realistic facial asymmetry, "
    "athletic Pilates-oriented physique, warm undertones, subtle freckles across nose bridge, "
    "minimalist silver pendant necklace"
)

# =============================================================================
# CONTEXTUAL SCENE MODIFIERS
# =============================================================================
MORNING_SCENES: List[str] = [
    "Drinking coffee in a bright minimalist kitchen",
    "Stretching on a yoga mat in a sunlit room",
    "Working on a laptop at a bright cafe",
    "Organizing a desk space with morning sunlight",
]

EVENING_SCENES: List[str] = [
    "Sitting in a neon-lit lounge",
    "Coding at a desk with RGB monitor glow",
    "Relaxing on a couch with a book and dim lamp",
    "Looking out a rainy window at city lights",
]

# =============================================================================
# TECHNICAL CAMERA MODIFIERS
# =============================================================================
TECHNICAL_MODIFIERS: str = (
    "Shot on 35mm lens, f/1.8 aperture, soft background bokeh, "
    "natural lighting, masterpiece, hyper-detailed, slight film grain"
)

PORTRAIT_TECHNICAL: str = (
    "Shot on 50mm lens, f/1.8 aperture, soft background bokeh, "
    "natural lighting, masterpiece, hyper-detailed, slight film grain"
)

# =============================================================================
# LIGHTING MODIFIERS BY TIME OF DAY
# =============================================================================
MORNING_LIGHTING: str = "Golden hour natural sunlight streaming through a window, 5000K color temp, bright exposure"
EVENING_LIGHTING: str = "Low-key moody neon lighting, 3200K color temp, screen-glow reflection"

# =============================================================================
# VOICE & CAPTION CONSTRAINTS
# =============================================================================
FORBIDDEN_WORDS: List[str] = [
    "Delve",
    "Tapestry",
    "Furthermore",
    "In conclusion",
    "Hey guys",
    "Link in bio",
    "As an AI",
    "Remember",
]

ALLOWED_PHRASES: List[str] = [
    "Honestly,",
    "Vibes today...",
    "Just thinking about...",
    "Current status:",
    "Long day...",
]

PRIMARY_EMOJIS: List[str] = ["✨", "☕", "🖤"]
SECONDARY_EMOJIS: List[str] = ["🌙", "💻", "🎧", "🌧️"]
FORBIDDEN_EMOJIS: List[str] = ["😂", "💯", "🔥"]

MAX_CAPTION_LENGTH: int = 300
HASHTAG_COUNT: int = 5

# =============================================================================
# POSTING SCHEDULE (IST - Asia/Kolkata)
# =============================================================================
MORNING_WINDOW_START: int = 8    # 08:30 IST
MORNING_WINDOW_END: int = 10     # 10:00 IST
EVENING_WINDOW_START: int = 20   # 20:30 IST
EVENING_WINDOW_END: int = 22     # 22:00 IST
MIN_HOURS_BETWEEN_POSTS: int = 4
MAX_DAILY_POSTS: int = 2

# =============================================================================
# FALLBACK SELECTORS (Used when GLM-4.7 is unreachable)
# =============================================================================
FALLBACK_SELECTORS: Dict[str, str] = {
    "gemini_textbox": 'div[role="textbox"]',
    "gemini_input": 'textarea',
    "buffer_compose_button": 'button[aria-label="Create Post"]',
    "buffer_file_input": 'input[type="file"]',
    "buffer_caption_box": 'div[contenteditable="true"]',
    "buffer_schedule_button": 'button:has-text("Add to Queue")',
    "metricool_compose_button": 'button:has-text("Create")',
    "metricool_file_input": 'input[type="file"]',
    "metricool_caption_box": 'textarea',
    "metricool_schedule_button": 'button:has-text("Schedule")',
}

# =============================================================================
# VALIDATION THRESHOLDS
# =============================================================================
MIN_FILE_SIZE_BYTES: int = 80_000          # 80KB
MIN_IMAGE_DIMENSION: int = 1080            # Minimum 1080px on shortest side
CONFIDENCE_THRESHOLD: int = 80             # GLM-4.7 confidence score minimum
MAX_GENERATION_RETRIES: int = 2            # 3 attempts total (initial + 2 retries)
MAX_CONSECUTIVE_FAILURES: int = 3          # Circuit breaker threshold
E2E_TIMEOUT_SECONDS: int = 180

# =============================================================================
# VIDEO PLATFORM CONFIGURATION
# =============================================================================
VIDEO_RENDER_TIMEOUT_SECONDS: int = 300    # 5 minutes max wait for video render
VIDEO_POLL_INTERVAL_SECONDS: int = 10

# =============================================================================
# STEALTH CONFIGURATION
# =============================================================================
MOBILE_USER_AGENTS: List[str] = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
]

VIEWPORT_CONFIG: Dict[str, Any] = {
    "width": 390,
    "height": 844,
}

DEVICE_SCALE_FACTOR: int = 3
GEOLOCATION_INDIA: Dict[str, float] = {
    "latitude": 28.6139,   # Delhi
    "longitude": 77.2090,
}

BROWSER_LAUNCH_ARGS: List[str] = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--window-position=0,0",
    "--ignore-certificate-errors",
    "--ignore-certificate-errors-spki-list",
    "--disable-dev-shm-usage",
]

# =============================================================================
# BIOMETRIC SIMULATION CONSTANTS
# =============================================================================
TYPING_DELAY_MIN_MS: int = 40
TYPING_DELAY_MAX_MS: int = 150
TYPO_PROBABILITY: float = 0.02
MOUSE_STEPS_MIN: int = 1
MOUSE_STEPS_MAX: int = 3
MOUSE_MOVE_SLEEP_MIN: float = 0.001
MOUSE_MOVE_SLEEP_MAX: float = 0.005

# =============================================================================
# STATE SCHEMA DEFAULTS
# =============================================================================
DEFAULT_STATE: Dict[str, Any] = {
    "last_execution_timestamp_utc": None,
    "daily_post_count": 0,
    "last_theme_used": None,
    "consecutive_failures": 0,
    "cookie_health_status": "unknown",
    "generation_attempt": 0,
    "total_posts_all_time": 0,
    "version": "2026.6.0",
}
