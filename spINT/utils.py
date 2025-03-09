import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def wait_for_page_stability(driver, check_interval=1, timeout=30):
    """
    Wait until the page's HTML stabilizes (i.e., doesn't change)
    for at least one check interval.
    """
    start = time.time()
    last_source = driver.execute_script("return document.documentElement.outerHTML")
    while time.time() - start < timeout:
        time.sleep(check_interval)
        current_source = driver.execute_script("return document.documentElement.outerHTML")
        if current_source == last_source:
            return True
        last_source = current_source
    return False

def wait_for_clickable(driver, xpath, timeout=20):
    """Wait for an element to be clickable and return it."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )

def wait_and_click(driver, xpath, timeout=20):
    """Wait for an element to be clickable and then click it."""
    element = wait_for_clickable(driver, xpath, timeout)
    element.click()

def wait_and_send_keys(driver, xpath, keys, timeout=20):
    """Wait for an element to be clickable and then send keys to it."""
    element = wait_for_clickable(driver, xpath, timeout)
    element.send_keys(keys)
