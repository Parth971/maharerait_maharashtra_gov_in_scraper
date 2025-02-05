import json
import time
from typing import Any, Dict
from bs4 import BeautifulSoup

from botasaurus.task import task
from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify
from botasaurus.user_agent import UserAgent

from twocaptcha import TwoCaptcha

from logger import ScraperLog
from settings import settings


solver = TwoCaptcha(settings.captcha_solver_api_key)


def solve(filepath: str = "canvas.png") -> str:
    solution = solver.normal(filepath)
    code: str = solution["code"]
    return code


@browser(
    max_retry=1,
    reuse_driver=True,
    output=None,
    headless=settings.headless,
    user_agent=UserAgent.RANDOM,
    close_on_crash=True,
)  # type: ignore
def scrape_html(driver: Driver, link: str) -> str:
    base_link = (
        "https://maharera.maharashtra.gov.in/projects-search-result?project_name=P51700003336&"
        "project_location=&project_completion_date=&project_state=27&project_district=0&carpetAreas="
        "&completionPercentages=&project_division=&page=1&op=Search"
    )

    # driver.get(base_link)
    ScraperLog.info(f"Scraping {link}")
    driver.get_via(link, referer=base_link, wait=5)

    while True:
        filepath = settings.output_dir / "screenshots/canvas.png"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        driver.save_element_screenshot("#captcahCanvas", str(filepath))

        code = solve(str(filepath))
        ScraperLog.debug(f"Solved captcha with code: {code}")

        captcha_ele = driver.select("input[name=captcha]")
        captcha_ele.type(code, wait=5)

        submit_btn = driver.get_element_containing_text("Submit")
        submit_btn.humane_click(wait=5)

        time.sleep(2)

        invalid_captcha = driver.get_element_containing_text("Invalid Captcha")
        if invalid_captcha is None:
            break

        ScraperLog.error("Invalid captcha, Retrying...")
        ok_btn = driver.get_element_containing_text("OK")
        ScraperLog.debug("Clicking OK button")
        ok_btn.humane_click(wait=5)
        time.sleep(1)

    html: str = driver.page_html
    return html


def extract_data(soup: BeautifulSoup) -> Dict[str, Any]:
    complaint_details_tag = soup.find(string="Complaint Details")

    if not complaint_details_tag:
        return {"error": "Tag with text 'Complaint Details' not found"}

    parent_tag = complaint_details_tag.find_parent().find_parent()

    if not parent_tag:
        return {"error": "Parent tag not found for 'Complaint Details'"}

    next_table = parent_tag.find_next_sibling("table")

    if not next_table:
        return {"error": "No table tag found as a sibling"}

    rows = next_table.find_all("tr")
    data = []
    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]

    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        row_data = dict(zip(headers, cells))
        data.append(row_data)

    required_columns = ["Complaint No.", "Complaint Status"]
    required_data = [
        {col_name: row[col_name] for col_name in required_columns} for row in data
    ]
    return {"data": required_data}


@task(
    output=None,
    close_on_crash=True,
    create_error_logs=False,
    parallel=settings.parallel,
)  # type: ignore
def scrape_data(link: str) -> Dict[str, Any]:
    html = scrape_html(link)
    return extract_data(soupify(html))


if __name__ == "__main__":
    data = "https://maharerait.maharashtra.gov.in/project/view/4425"
    result = scrape_data(data)
    ScraperLog.info(f"Result: {json.dumps(result)}")
