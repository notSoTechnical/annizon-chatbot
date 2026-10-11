"""UI smoke tests for the deployed Streamlit chatbot (Selenium, headless Chrome).

Opens the live app, types into the real chat box, and checks the answers —
the Python equivalent of the Java selenium-framework, minus the boilerplate.
Skips gracefully when Chrome isn't available.
"""
import os

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

APP_URL = os.getenv(
    "CHATBOT_APP_URL",
    "https://annizon-chatbot-vfphwhkad7y4tf3qwrcc8m.streamlit.app/",
)
TIMEOUT = 120  # Streamlit cold starts are slow


@pytest.fixture(scope="module")
def driver():
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        d = webdriver.Chrome(options=options)  # Selenium Manager fetches chromedriver
    except Exception as exc:
        pytest.skip(f"Chrome unavailable: {exc}")
    d.get(APP_URL)
    WebDriverWait(d, TIMEOUT).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-testid="stChatInput"] textarea')
        )
    )
    yield d
    d.quit()


def _ask(driver, question):
    box = driver.find_element(
        By.CSS_SELECTOR, '[data-testid="stChatInput"] textarea'
    )
    before = len(
        driver.find_elements(By.CSS_SELECTOR, '[data-testid="stChatMessage"]')
    )
    box.send_keys(question + Keys.ENTER)
    WebDriverWait(driver, TIMEOUT).until(
        lambda d: len(
            d.find_elements(By.CSS_SELECTOR, '[data-testid="stChatMessage"]')
        )
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
