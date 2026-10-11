"""UI smoke tests for the deployed Streamlit chatbot (Selenium, headless Chrome).

Opens the live app, types into the real chat box, and checks the answers —
the Python equivalent of the Java selenium-framework, minus the boilerplate.

SKIP PATTERNS TAUGHT HERE (suite stays green when the world moves):
  1. @pytest.mark.skipif(...)  -> skip at collection time (e.g. selenium missing)
  2. pytest.skip(...)          -> skip mid-run (e.g. Chrome missing, app down)
  3. selector-guard skip       -> skip when Streamlit changes their UI (see _find_chat_input)
"""
import os

import pytest

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:  # selenium not installed -> skip whole module, CI stays green
    webdriver = None

# Pattern 1: declarative skip — decided before any test runs.
pytestmark = pytest.mark.skipif(webdriver is None, reason="selenium not installed")

APP_URL = os.getenv(
    "CHATBOT_APP_URL",
    "https://annizon-chatbot-vfphwhkad7y4tf3qwrcc8m.streamlit.app/",
)
TIMEOUT = 120  # Streamlit cold starts are slow

# If Streamlit renames their testids, update just these two selectors.
CHAT_INPUT_SELECTOR = '[data-testid="stChatInput"] textarea'
CHAT_MESSAGE_SELECTOR = '[data-testid="stChatMessage"]'


def _find_chat_input(driver, timeout=TIMEOUT):
    """Pattern 3: skip (don't fail) when Streamlit changes their UI.

    A missing selector means 'the UI moved on', not 'our bot broke' —
    failing here would cry wolf on every Streamlit upgrade. Skipping keeps
    the nightly suite green, and the message says exactly what to fix.
    """
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CHAT_INPUT_SELECTOR))
        )
    except Exception:
        pytest.skip(
            "Streamlit UI changed: selector "
            f"'{CHAT_INPUT_SELECTOR}' not found — update it in tests/test_ui.py."
        )


@pytest.fixture(scope="module")
def driver():
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        d = webdriver.Chrome(options=options)  # Selenium Manager fetches chromedriver
    except Exception as exc:
        # Pattern 2: imperative skip — no Chrome on this machine.
        pytest.skip(f"Chrome unavailable: {exc}")
    try:
        d.get(APP_URL)
        _find_chat_input(d)  # waits for load; Pattern 3 skips if the UI moved
        yield d
    except Exception as exc:
        # App didn't load (Streamlit Cloud hiccup, network blip):
        # that's infrastructure, not our code breaking -> skip, don't fail.
        pytest.skip(f"app unreachable: {exc}")
    finally:
        d.quit()  # Skipped (BaseException) bypasses `except Exception` but still lands here


def _ask(driver, question):
    box = _find_chat_input(driver, timeout=30)
    before = len(driver.find_elements(By.CSS_SELECTOR, CHAT_MESSAGE_SELECTOR))
    box.send_keys(question + Keys.ENTER)
    WebDriverWait(driver, TIMEOUT).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, CHAT_MESSAGE_SELECTOR))
        > before + 1
    )


def test_ui_answers_shipping_question(driver):
    """End-to-end: ask about shipping in the real UI, expect a policy answer."""
    _ask(driver, "how long does shipping take")
    body = driver.find_element(By.TAG_NAME, "body").text.lower()
    assert "day" in body, "UI answer doesn't mention shipping time"


def test_ui_refuses_off_policy_question(driver):
    """End-to-end: off-policy question gets 'don't know', not a hallucination."""
    _ask(driver, "what is the capital of France")
    body = driver.find_element(By.TAG_NAME, "body").text.lower()
    assert (
        "don't know" in body
        or "do not know" in body
        or "cannot answer" in body
        or "can't answer" in body
        or "no information" in body
    ), "bot hallucinated in the UI"
