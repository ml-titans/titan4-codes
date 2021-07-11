# %%
from pathlib import Path
from datetime import datetime
import time
import requests
import re
from bs4 import BeautifulSoup
import toml

from utils import setup_logger

BASEURL = 'https://db.netkeiba.com'
savedir = Path('race_list')
savedir.mkdir(exist_ok=True)
logger = setup_logger(__name__, 'racelist_log.txt')


def extract_race_days(page_url, sleep=1):
    time.sleep(sleep)
    res = requests.get(BASEURL + page_url)
    res.encoding = res.apparent_encoding

    soup = BeautifulSoup(res.content, 'lxml')
    table = soup.find(class_='race_calendar')

    prev_month = table.find(src=re.compile('race_calendar_rev_02.gif')).parent['href']
    race_days = [url.get('href') for url in table.find('table').find_all('a')]

    return race_days, prev_month


def extract_race_list(race_day, sleep=1):
    time.sleep(sleep)
    res = requests.get(BASEURL + race_day)
    res.encoding = res.apparent_encoding

    soup = BeautifulSoup(res.content, 'lxml')
    url_list = soup.find(class_='race_list fc').find_all('a')
    races = [BASEURL + url.get('href') for url in url_list if 'movie' not in url.get('href')]
    return races


if __name__ == '__main__':
    config = toml.load('CONFIG.toml')
    page = '/?pid=race_top'
    repatter = re.compile('[0-9]+')
    calendar = datetime.now().strftime('%Y%m%d')  # 実行時の日付
    end = config['race_list']['last_updated']  # 最終更新日

    while calendar > end:
        race_days, prev_month_url = extract_race_days(page)

        try:
            for d in race_days:
                races = extract_race_list(d)
                fname = repatter.search(d).group() + '.txt'
                with open(savedir / fname, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(races) + '\n')
                logger.debug(f'{fname} を保存しました.')
        except Exception as e:
            logger.error(e)

        page = prev_month_url
        calendar = repatter.search(page).group()

    config['race_list']['last_updated'] = datetime.now().strftime('%Y%m%d')
    toml.dump(config, open('CONFIG.toml', mode='w'))