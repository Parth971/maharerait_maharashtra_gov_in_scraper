import datetime
import pytz
import filelock

from typing import Dict, Optional
from logging import Handler, StreamHandler, Logger, Formatter, DEBUG, INFO, getLogger
from logging.handlers import RotatingFileHandler


from settings import settings

ist_timezone = pytz.timezone("Asia/Kolkata")


class BaseLog:
    _logger: Optional[Logger] = None
    _max_log_file_size_in_mb: int = 2
    _name: str = "base"
    _debug: bool = False

    @classmethod
    def logger(cls) -> Logger:
        settings.logs_directory.mkdir(parents=True, exist_ok=True)

        if cls._logger is None:
            lock_filepath = settings.logs_directory / f"{cls._name}.lock"
            with filelock.FileLock(lock_filepath):
                formatter = Formatter(
                    "%(asctime)s.%(msecs)03d IST - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
                formatter.converter = lambda *args: datetime.datetime.now(
                    ist_timezone
                ).timetuple()

                trading_logger = getLogger(cls._name)
                trading_logger.setLevel(DEBUG)

                log_filepath = settings.logs_directory / f"{cls._name}.log"

                handlers: Dict[str, Handler] = {
                    "file": RotatingFileHandler(
                        filename=log_filepath,
                        maxBytes=cls._max_log_file_size_in_mb * 1024 * 1024,
                        backupCount=50,
                    ),
                    "console": StreamHandler(),
                }

                formatters: Dict[str, Formatter] = {
                    "file": formatter,
                    "console": formatter,
                }

                loglevels: Dict[str, int] = {
                    "file": DEBUG,
                    "console": DEBUG if cls._debug else INFO,
                }

                for handler_name, handler in handlers.items():
                    current_formatter = formatters[handler_name]
                    log_level = loglevels[handler_name]

                    handler.setFormatter(current_formatter)
                    handler.setLevel(log_level)
                    trading_logger.addHandler(handler)

                cls._logger = trading_logger
                cls._logger.debug(
                    f"\n\n{'#'*50} {cls._name.upper()} LOG INITIALIZED {'#'*50}"
                )

        return cls._logger

    @classmethod
    def error(cls, msg: str) -> None:
        cls.logger().error(msg)

    @classmethod
    def info(cls, msg: str) -> None:
        cls.logger().info(msg)

    @classmethod
    def debug(cls, msg: str) -> None:
        cls.logger().debug(msg)

    @classmethod
    def warning(cls, msg: str) -> None:
        cls.logger().warning(msg)


class ScraperLog(BaseLog):
    _name = "scraper"
    _debug = settings.debug
