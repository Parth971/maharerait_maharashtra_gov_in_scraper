import json
from pathlib import Path
import time
from typing import Any, Dict, List
from bs4 import BeautifulSoup
import pandas as pd

from botasaurus.task import task
from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify
from botasaurus.user_agent import UserAgent

from twocaptcha import TwoCaptcha

from logger import ScraperLog
from scrape import scrape_project_links
from settings import settings


solver = TwoCaptcha(settings.captcha_solver_api_key)


def solve(filepath: str = "canvas.png") -> str:
    ScraperLog.debug("Solving captcha...")
    solution = solver.normal(filepath)
    code: str = solution["code"]
    ScraperLog.debug(f"Solved captcha with code: {code}")
    return code


@browser(
    max_retry=1,
    reuse_driver=True,
    output=None,
    headless=settings.headless,
    user_agent=UserAgent.RANDOM,
    close_on_crash=False,
)  # type: ignore
def scrape_html(driver: Driver, data: Dict[str, Any]) -> str:
    link = data["link"]
    registration_number: str = data["Registration Number"]

    ScraperLog.info(f"Scraping for Registration Number: {registration_number}")
    base_link = (
        f"https://maharera.maharashtra.gov.in/projects-search-result?project_name={registration_number}&"
        "project_location=&project_completion_date=&project_state=27&project_district=0&carpetAreas="
        "&completionPercentages=&project_division=&page=1&op=Search"
    )
    driver.get_via(link, referer=base_link, wait=3)

    attempt = 0
    while attempt < settings.max_captcha_attempts:
        attempt += 1
        filepath = settings.output_dir / "screenshots/canvas.png"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        driver.save_element_screenshot("#captcahCanvas", str(filepath))

        code = solve(str(filepath))

        captcha_ele = driver.select("input[name=captcha]")
        captcha_ele.type(code, wait=5)

        submit_btn = driver.get_element_containing_text("Submit")
        submit_btn.humane_click(wait=5)

        time.sleep(2)

        invalid_captcha = driver.get_element_containing_text("Invalid Captcha")
        if invalid_captcha is None:
            html: str = driver.page_html
            return html

        ScraperLog.error(f"Invalid captcha, Retrying ({attempt})th time...")
        ok_btn = driver.get_element_containing_text("OK")
        ScraperLog.debug("Clicking OK button")
        ok_btn.humane_click(wait=5)
        time.sleep(1)

    ScraperLog.error("Failed to solve captcha after multiple attempts")
    raise Exception("Failed to solve captcha after multiple attempts")


def extract_data(soup: BeautifulSoup) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "project_name": None,
        "complaint_details": [],
    }
    label = soup.find("label", string="Project Name ")

    if label:
        value_label = label.find_next_sibling("label")
        if value_label:
            result["project_name"] = value_label.text.strip()

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

    if len(data) == 1:
        if data[0].get("#") == "No Records Found":
            return result
    try:
        required_columns = ["Complaint No.", "Complaint Status"]
        result["complaint_details"] = [
            {col_name: row[col_name] for col_name in required_columns} for row in data
        ]
        return result
    except Exception as e:
        return {"error": str(e)}


@task(
    output=None,
    close_on_crash=True,
    create_error_logs=False,
    parallel=settings.parallel,
)  # type: ignore
def scrape_data(data: Dict[str, Any]) -> Dict[str, Any]:
    link = data["link"]

    registration_number: str = data["Registration Number"]
    if link is None:
        return {"error": f"No result found for {registration_number}"}

    html = scrape_html(data)
    ScraperLog.debug(f"Type of html: {type(html)}")
    return extract_data(soupify(html))


def read_excel(filepath: Path) -> List[Dict[str, Any]]:
    df = pd.read_excel(filepath, sheet_name="Sheet1", usecols=["Registration Number"])
    data: List[Dict[str, Any]] = df.to_dict(orient="records")
    return data


if __name__ == "__main__":
    data = read_excel(settings.input_file_path)
    links = scrape_project_links(data=data)

    for obj, link in zip(data, links):
        obj["link"] = link

    ScraperLog.info(f"Found Links: {json.dumps(links)}")

    result = scrape_data(data=data)

    for obj, res in zip(data, result):
        obj.update(res)

    ScraperLog.info(f"Result: {json.dumps(data)}")
