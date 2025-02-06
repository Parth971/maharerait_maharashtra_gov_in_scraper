from typing import Any, Dict, List, Optional

from botasaurus import bt
from botasaurus.task import task
from botasaurus.browser import browser, Driver
from botasaurus.user_agent import UserAgent

from twocaptcha import TwoCaptcha

from logger import ScraperLog
from settings import settings


solver = TwoCaptcha(settings.captcha_solver_api_key)


class CacheProjectLink:
    map_: Optional[Dict[str, str]] = None

    @classmethod
    def get_project_link(cls, registration_number: str) -> Optional[str]:
        cls.load()
        if cls.map_ is None:
            return None
        return cls.map_.get(registration_number)

    @classmethod
    def load(cls) -> None:
        if cls.map_ is None:
            if settings.cache_file_path.exists():
                cls.map_ = bt.read_json(str(settings.cache_file_path))
            else:
                cls.map_ = {}

    @classmethod
    def update_cache(cls, registration_number: str, link: str) -> None:
        cls.load()
        assert cls.map_ is not None
        cls.map_[registration_number] = link
        settings.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        bt.write_json(cls.map_, str(settings.cache_file_path))


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
def scrape_html(driver: Driver, registration_number: str) -> Optional[str]:
    ScraperLog.info(f"Searching for Registration Number: {registration_number}")
    base_link = (
        f"https://maharera.maharashtra.gov.in/projects-search-result?project_name={registration_number}&"
        "project_location=&project_completion_date=&project_state=27&project_district=0&carpetAreas="
        "&completionPercentages=&project_division=&page=1&op=Search"
    )

    driver.get(base_link)

    boxes = driver.select_all(".container > .row.shadow")
    if len(boxes) != 1:
        ScraperLog.error(f"Found {len(boxes)} results for {registration_number}")
        return None

    anchor_tag = driver.get_element_with_exact_text("View Details", wait=5)
    link: str = anchor_tag.get_attribute("href")
    return link


@task(
    output=None,
    close_on_crash=True,
    create_error_logs=False,
    parallel=settings.parallel,
)  # type: ignore
def _scrape_project_links(data: Dict[str, Any]) -> Optional[str]:
    registration_number: str = data["Registration Number"]
    project_link = CacheProjectLink.get_project_link(registration_number)
    if project_link is not None:
        return project_link

    link: Optional[str] = scrape_html(registration_number)
    if link:
        CacheProjectLink.update_cache(registration_number, link)
    return link


def scrape_project_links(data: List[Dict[str, Any]]) -> List[str]:
    result: List[str] = _scrape_project_links(data)
    scrape_html.close()
    return result
