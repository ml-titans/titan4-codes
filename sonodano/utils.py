import re
from logging import getLogger, StreamHandler, Formatter, DEBUG, FileHandler, ERROR, INFO
import bs4

pttr_num = re.compile('[0-9]+')


# loggerオブジェクトの宣言
def setup_logger(name, logfile='LOGFILENAME.txt'):
    logger = getLogger(name)
    logger.setLevel(DEBUG)

    # create file handler which logs even DEBUG messages
    fh = FileHandler(logfile)
    fh.setLevel(ERROR)
    fh_formatter = Formatter('%(asctime)s - %(levelname)s - %(filename)s - %(name)s - %(funcName)s - %(message)s')
    fh.setFormatter(fh_formatter)

    # create console handler with a INFO log level
    ch = StreamHandler()
    ch.setLevel(INFO)
    ch_formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    ch.setFormatter(ch_formatter)

    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# logger = setup_logger(__name__)

# 関数群
def to_int(s: str):
    try:
        s = int(s)
    except Exception as e:
        # logger.debug(e)
        # logger.debug(f'{s} cannot be converted to int. Return None')
        s = None
    return s


def to_float(s: str):
    try:
        s = float(s)
    except Exception as e:
        # logger.debug(e)
        # logger.debug(f'{s} cannot be converted to float. Return None')
        s = None
    return s


def to_sec(s: str):
    try:
        race_time = int(s[0]) * 60 + int(s[2:4]) + 0.1 * int(s[-1])
    except Exception as e:
        # logger.debug(e)
        # logger.debug(f'{s} cannot be converted to sec. Return None')
        race_time = None
    return race_time


def replace_str(s: str, old, new):
    try:
        s = s.replace(old, new)
    except Exception as e:
        # logger.debug(e)
        s = None
    return s


def get_bs4text(s, default=None):
    if isinstance(s, bs4.element.Tag):
        return s.get_text()
    else:
        return default


def get_bs4int(s):
    s = get_bs4text(s)
    return to_int(s)


def get_bs4float(s):
    s = get_bs4text(s)
    return to_float(s)


def find_bs4href(s):
    try:
        ret = s.find('a')['href']
    except:
        ret = None
    return ret


def get_id(s):
    if isinstance(s, bs4.element.Tag):
        s = find_bs4href(s)
        if s is not None:
            s = pttr_num.search(s).group()
            return to_int(s)
        else:
            return None
    else:
        return None
