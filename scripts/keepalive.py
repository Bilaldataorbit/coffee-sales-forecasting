from playwright.sync_api import sync_playwright
URL = "https://coffee-sales-forecasting-zbha9jfqwanpgk5gih8qzp.streamlit.app/"
WAKE_TEXT = "Yes, get this app back up!"
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(URL, timeout=120_000)
    page.wait_for_timeout(8_000)
    button = page.get_by_role("button", name=WAKE_TEXT)
    if button.count() > 0:
        print("App was asleep: clicking the wake-up button")
        button.first.click()
        page.wait_for_timeout(60_000)
    else:
        print("App is awake")
    page.wait_for_timeout(5_000)
    print("Page title:", page.title())
    browser.close()
