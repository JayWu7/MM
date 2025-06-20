# log_config.py
import os
import logging
from logging.handlers import RotatingFileHandler
from colorama import init, Fore
from datetime import datetime

init(autoreset=True)  # 自动还原颜色

LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARNING,
    'error': logging.ERROR,
    'success': logging.INFO,
    'market': logging.INFO,
    'status': logging.INFO,
}

COLOR_MAP = {
    'debug': Fore.WHITE,
    'info': Fore.YELLOW,
    'warn': Fore.MAGENTA,
    'error': Fore.RED,
    'success': Fore.GREEN,
    'market': Fore.CYAN,
    'status': Fore.BLUE,
}

def setup_logger(log_file='mm.log'):

    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)

def color_log(level: str, message: str):
    level = level.lower()
    log_level = LOG_LEVELS.get(level, logging.INFO)
    color = COLOR_MAP.get(level, Fore.WHITE)

    # Write to log file
    logging.log(log_level, message)

    if log_level >= logging.INFO:
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(color + f"[{timestamp}] {level.upper():<7} {message}")