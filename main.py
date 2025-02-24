from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
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
captcha_solver_attempts = 0


def solve(filepath: str) -> str:
    global captcha_solver_attempts
    captcha_solver_attempts += 1
    ScraperLog.debug(f"({filepath}) Solving captcha...")
    try:
        solution = solver.normal(filepath)
        code: str = solution["code"].upper()
        ScraperLog.debug(f"Solved captcha with code: {code}")
        return code
    except Exception as e:
        ScraperLog.error(f"Failed to solve captcha: {e}")
        return ""


@browser(
    max_retry=1,
    reuse_driver=True,
    output=None,
    headless=settings.headless,
    user_agent=UserAgent.RANDOM,
    close_on_crash=True,
    block_images_and_css=True,
    create_error_logs=False,
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
    driver.get_via(link, referer=base_link)

    driver.wait_for_element("#captcahCanvas", wait=3)

    filepath = settings.output_dir / f"screenshots/{registration_number}_canvas.png"
    filepath.parent.mkdir(parents=True, exist_ok=True)

    attempt = 0
    while attempt < settings.max_captcha_attempts:
        attempt += 1

        driver.save_element_screenshot("#captcahCanvas", str(filepath))

        code = solve(str(filepath))

        captcha_ele = driver.select("input[name=captcha]")
        captcha_ele.type(code)

        submit_btn = driver.get_element_containing_text("Submit")
        submit_btn.humane_click()

        time.sleep(1)

        invalid_captcha = driver.get_element_containing_text("Invalid Captcha")
        if invalid_captcha is None:
            html: str = driver.page_html
            filepath.unlink(missing_ok=True)
            return html

        ScraperLog.error(f"Invalid captcha, Retrying ({attempt})th time...")
        ok_btn = driver.get_element_containing_text("OK")
        ScraperLog.debug("Clicking OK button")
        ok_btn.humane_click()
        time.sleep(1)

    filepath.unlink(missing_ok=True)

    error_msg = (
        f"Failed to solve captcha after multiple attempts for {registration_number}"
    )
    ScraperLog.error(error_msg)
    raise Exception(error_msg)


def extract_data(soup: BeautifulSoup, registration_number: str) -> Dict[str, Any]:
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
        ScraperLog.error(
            f"({registration_number}) Tag with text 'Complaint Details' not found"
        )
        return result

    parent_tag = complaint_details_tag.find_parent().find_parent()

    if not parent_tag:
        ScraperLog.error(
            f"({registration_number}) Parent tag not found for 'Complaint Details'"
        )
        return result

    next_table = parent_tag.find_next_sibling("table")

    if not next_table:
        ScraperLog.error(f"({registration_number}) No table tag found as a sibling")
        return result

    rows = next_table.find_all("tr")
    data = []
    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]

    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        row_data = dict(zip(headers, cells))
        data.append(row_data)

    if len(data) == 1:
        if data[0].get("#") == "No Records Found":
            ScraperLog.warning(f"({registration_number}) No records found")
            return result
    try:
        required_columns = ["Complaint No.", "Complaint Status"]
        result["complaint_details"] = [
            {col_name: row[col_name] for col_name in required_columns} for row in data
        ]
        return result
    except Exception as e:
        ScraperLog.error(f"({registration_number}) {e}")
        return result


@task(
    output=None,
    close_on_crash=True,
    parallel=settings.parallel,
)  # type: ignore
def scrape_data(data: Dict[str, Any]) -> Dict[str, Any]:
    link = data["link"]
    registration_number: str = data["Registration Number"]

    html: Optional[str] = None

    if link is not None:
        html = scrape_html(data)

    if html is None:
        ScraperLog.error(f"({registration_number}) No result found")
        return {"project_name": None, "complaint_details": []}
    else:
        result = extract_data(soupify(html), registration_number)
        if result["project_name"] is None:
            ScraperLog.debug(html)
        return result


def read_excel(filepath: Path) -> List[Dict[str, Any]]:
    columns = {settings.input_column_name: "Registration Number"}
    df = pd.read_excel(filepath, sheet_name="Sheet1", usecols=list(columns.keys()))
    df = df.rename(columns=columns)
    data: List[Dict[str, Any]] = df.to_dict(orient="records")
    if settings.number_of_projects is not None:
        data = data[: settings.number_of_projects]
    return data


def save_as_excel(data: List[Dict[str, Any]]) -> None:
    rows = []
    for project in data:
        reg_number = project["Registration Number"]
        project_name = project["project_name"]
        for complaint in project["complaint_details"]:
            rows.append(
                {
                    "Registration Number": reg_number,
                    "Complaint Number": complaint["Complaint No."],
                    "Complaint Status": complaint["Complaint Status"],
                    "Project Name": project_name,
                }
            )

    df = pd.DataFrame(rows)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    output_file_path = settings.output_dir / f"{now}.xlsx"
    df.to_excel(output_file_path, index=False)

    ScraperLog.info(f"Saved to {output_file_path}")


def save_as_json(data: List[Dict[str, Any]]) -> None:
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    output_file_path = settings.output_dir / f"{now}.json"
    with output_file_path.open("w") as f:
        json.dump(data, f, indent=4)

    ScraperLog.info(f"Saved to {output_file_path}")


if __name__ == "__main__":
    data = read_excel(settings.input_file_path)
    ScraperLog.info(f"Found {len(data)} projects.")

    start_time = time.time()
    links = scrape_project_links(data=data)
    ScraperLog.info(f"Finshed Searching Links in {time.time() - start_time} seconds")

    for obj, link in zip(data, links):
        obj["link"] = link

    ScraperLog.info(f"Found Links: {json.dumps(links)}")

    start_time = time.time()
    result = scrape_data(data=data)
    ScraperLog.debug(f"Total Captcha Solver Calls: {captcha_solver_attempts}")
    ScraperLog.info(f"Finshed Scraping in {time.time() - start_time} seconds")

    for obj, res in zip(data, result):
        obj.update(res)

    save_as_json(data)
    save_as_excel(data)
