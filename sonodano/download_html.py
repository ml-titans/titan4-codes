import re
import time
from pathlib import Path

import requests
import toml
from tqdm import tqdm

from utils import setup_logger

config = toml.load('CONFIG.toml')

USER = config['user']
PASS = config['passwd']
login_info = {'login_id': USER, 'pswd': PASS}
login_url = 'https://regist.netkeiba.com/account/?pid=login&action=auth'
# セッション開始
session = requests.session()
sess = session.post(login_url, data=login_info)

logger = setup_logger(__name__, 'downloadhtml_log.txt')


def download_race_results(race_list_path='race_list', savedir='race_html'):
    racedir = Path(race_list_path)
    repatter = re.compile('[0-9]+')
    rootdir = Path(savedir)
    rootdir.mkdir(exist_ok=True)
    for race_fname in tqdm(racedir.iterdir()):
        logger.debug(f'{race_fname} の処理中')

        with open(race_fname) as f:
            race_list = f.read().splitlines()

        for race_url in race_list:
            savedir = rootdir/race_fname.stem
            savedir.mkdir(exist_ok=True)

            try:
                fname = repatter.search(race_url).group() + '.html'
                save_fname = savedir / fname

                if save_fname.exists():
                    logger.debug(f'{save_fname} already exists.')
                else:
                    time.sleep(1)
                    res = session.get(race_url)
                    res.encoding = res.apparent_encoding

                    with open(save_fname, 'w', encoding='utf-8') as f:
                        f.write(re.sub('euc-jp', 'utf-8', res.text))

                    logger.debug(f'{fname}のダウンロードに成功しました')
            except Exception as e:
                logger.error(e)


if __name__ == '__main__':
    download_race_results()
