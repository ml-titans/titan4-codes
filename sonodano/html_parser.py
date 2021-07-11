import re
from datetime import datetime
from pathlib import Path

import toml
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, SmallInteger, \
    Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.functions import current_timestamp
from sqlalchemy_utils import database_exists, create_database
from tqdm import tqdm

from utils import to_int, to_sec, setup_logger, replace_str, get_id, get_bs4text, get_bs4int, get_bs4float, find_bs4href

# 200808020399と200808020398は存在しない

logger = setup_logger(__name__, 'htmlparser.log')

# %% 正規表現
pttr_num = re.compile('[0-9]+')
pttr_rot = re.compile('(右|左|直線)')
pttr_suf = re.compile('(良|稍重|重|不良)')
pttr_class = re.compile('(オープン|1600万下|3勝クラス|1000万下|2勝クラス|500万下|1勝クラス|未勝利|新馬)')
pttr_grade = re.compile('(G1|G2|G3)')
pttr_place = re.compile('(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)')

# %% DBとテーブルの定義
dbconfig = toml.load('CONFIG.toml')['database']
DATABASE = f"postgresql://{dbconfig['user']}:{dbconfig['passwd']}@{dbconfig['host']}:{dbconfig['port']}/{dbconfig['dbname']}"
engine = create_engine(DATABASE)  # , echo=True

if not database_exists(engine.url):
    # DBの作成
    create_database(engine.url)
    logger.debug(f"DB: {dbconfig['dbname']} を作成しました")
else:
    logger.debug(f"DB: {dbconfig['dbname']} は存在します")
Base = declarative_base()


class RaceInfo(Base):
    # テーブル名
    __tablename__ = 'race_info'

    race_id = Column(Integer, primary_key=True, autoincrement=False)  # 普通のIntだとidの桁数が足りない…
    race_name = Column(String)
    place = Column(String)
    surface = Column(String)
    surface_condition = Column(String)
    surface_index = Column(SmallInteger)
    distance = Column(Integer)
    rotation = Column(String)
    weather = Column(String)
    race_grade = Column(String)
    start_time = Column(DateTime)

    steeple = Column(Boolean)
    surface_comment = Column(String)

    # 以下どちらかというとResultに入れたい
    corner1 = Column(String)
    corner2 = Column(String)
    corner3 = Column(String)
    corner4 = Column(String)

    lap = Column(String)
    pace = Column(String)

    created_at = Column(DateTime, server_default=current_timestamp())
    updated_at = Column(DateTime, onupdate=current_timestamp())


class RaceResult(Base):
    # テーブル名
    __tablename__ = 'race_result'

    race_id = Column(Integer, primary_key=True, autoincrement=False)
    horse_id = Column(Integer, primary_key=True, autoincrement=False)
    jockey_id = Column(Integer)

    arrival = Column(SmallInteger)
    horse_num = Column(SmallInteger)
    bracket = Column(SmallInteger)
    sex = Column(String)
    age = Column(SmallInteger)
    impost = Column(SmallInteger)
    race_time = Column(Float)
    margin = Column(String)
    speed_index = Column(SmallInteger)
    passage = Column(String)
    furlong = Column(Float)
    odds = Column(Float)
    favor = Column(SmallInteger)
    weight = Column(SmallInteger)
    weight_diff = Column(SmallInteger)
    train_time_url = Column(String)
    barn_comment_url = Column(String)
    remark = Column(String)
    trainer_id = Column(Integer)
    owner_id = Column(Integer)
    earnings = Column(Float)

    created_at = Column(DateTime, server_default=current_timestamp())
    updated_at = Column(DateTime, onupdate=current_timestamp())


class PayOff(Base):
    # テーブル名
    __tablename__ = 'payoff'

    race_id = Column(Integer, primary_key=True, autoincrement=False)

    win = Column(Integer)  # 単勝
    place1 = Column(Integer)  # 複勝
    place2 = Column(Integer)
    place3 = Column(Integer)
    bracket = Column(Integer)  # 枠連
    quine = Column(Integer)  # 馬連
    wide1 = Column(Integer)  # ワイド
    wide2 = Column(Integer)
    wide3 = Column(Integer)
    exacta = Column(Integer)  # 馬単
    trio = Column(Integer)  # 三連複
    trifecta = Column(Integer)  # 3連単

    created_at = Column(DateTime, server_default=current_timestamp())
    updated_at = Column(DateTime, onupdate=current_timestamp())


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
sess = Session()


# %% レース情
def get_race_info(race_id: int, soup: BeautifulSoup):
    race_info = {'race_id': race_id}

    intro = soup.find(class_='data_intro')
    race_name = intro.select_one('h1').get_text(strip=True)
    race_info['race_name'] = race_name
    race_info['place'] = pttr_place.search(intro.select_one('p.smalltxt').get_text()).group()
    # race_info['race_round'] = pttr_num.search(intro.select_one('dt').get_text()).group() # いらない

    conditions = intro.select_one('span').get_text().replace('\xa0', '').split('/')
    if '障' in conditions[0]:
        steeple = True
        rot = None
    else:
        steeple = False
        rot = pttr_rot.search(conditions[0]).group()

    surface_info = soup.find(summary='馬場情報')
    surface_index = surface_info.find(text='馬場指数')

    race_info['surface'] = '芝' if conditions[0] in '芝' else 'ダート'
    race_info['surface_condition'] = pttr_suf.search(conditions[2]).group()
    if surface_index is not None:
        race_info['surface_index'] = to_int(
            replace_str(list(surface_index.parent.next_siblings)[1].get_text(), '\xa0(?)', ''))
    race_info['distance'] = to_int(pttr_num.search(conditions[0]).group())
    race_info['rotation'] = rot
    race_info['weather'] = replace_str(conditions[1], '天候 : ', '')  # conditions[1].replace('天候 : ', '')

    start_time = replace_str(conditions[3], '発走 : ', '')  # conditions[3].replace('発走 : ', '')
    start_time = datetime.strptime(target_source.parent.name + start_time, '%Y%m%d%H:%M')
    race_grade = pttr_class.search(intro.select_one('p.smalltxt').get_text()).group()
    if race_grade == 'オープン':
        g123 = pttr_grade.search(race_name)
        if g123 is not None:
            race_grade = g123.group()

    race_info['race_grade'] = race_grade
    race_info['start_time'] = start_time
    race_info['steeple'] = steeple
    surface_comment = surface_info.find(text='馬場コメント')
    if surface_comment is not None:
        race_info['surface_comment'] = list(surface_comment.parent.next_siblings)[1].get_text()

    corner_dict = {}
    corner_info = soup.find(summary='コーナー通過順位').find_all('tr')
    corner_parser = {'1コーナー': 'corner1', '2コーナー': 'corner2', '3コーナー': 'corner3', '4コーナー': 'corner4'}
    for c in corner_info:
        corner_dict[corner_parser[c.th.get_text()]] = c.td.get_text()

    lap_dict = {}
    lap_info = soup.find(summary='ラップタイム').find_all('tr')
    lap_parser = {'ラップ': 'lap', 'ペース': 'pace'}
    for l in lap_info:
        lap_dict[lap_parser[l.th.get_text()]] = replace_str(replace_str(l.td.get_text(), '\xa0', ' '), '\n', '')
        # l.td.get_text().replace('\xa0', ' ').replace('\n', '')

    race_info.update(**corner_dict, **lap_dict)
    return race_info


# %% レース結果
def get_race_result(race_id, soup):
    result = soup.select_one('table.race_table_01.nk_tb_common')
    rows = result.select('tr')  # 0はカラム
    results = []
    for row in rows[1:]:
        r = row.find_all(['td'])

        race_result = {'race_id': race_id}
        race_result['arrival'] = get_bs4int(r[0])
        race_result['bracket'] = get_bs4int(r[1])
        race_result['horse_num'] = get_bs4int(r[2])  # 馬番
        # race_result['horse_name'] = r[3].get_text().replace('\n', '') # RaceResultに含めない
        race_result['horse_id'] = get_id(r[3])
        sex_age = get_bs4text(r[4])
        if sex_age is not None:
            sex = sex_age[0]
            age = to_int(sex_age[1])
        else:
            sex = None
            age = None
        race_result['sex'] = sex
        race_result['age'] = age
        race_result['impost'] = get_bs4int(r[5])  # 斤量
        # race_result['jockey_name'] = r[6].get_text().replace('\n', '')　# RaceResultに含めない
        race_result['jockey_id'] = get_id(r[6])
        race_result['race_time'] = to_sec(get_bs4text(r[7]))  # 秒に変換
        race_result['margin'] = get_bs4text(r[8])  # 着差いらないかも
        race_result['speed_index'] = get_bs4int(r[9])  # スピード指数
        race_result['passage'] = get_bs4text(r[10])  # 通過順いらないかも
        race_result['furlong'] = get_bs4float(r[11])  # 上がり3F
        race_result['odds'] = get_bs4float(r[12])
        race_result['favor'] = get_bs4int(r[13])  # 人気
        w = get_bs4text(r[14])
        if w is not None and len(w) >= 4:
            weight = to_int(w[:3])
            diff = to_int(replace_str(w[4:], ')', ''))
        else:
            weight = None
            diff = None
        race_result['weight'] = weight
        race_result['weight_diff'] = diff  # w[4:].replace(')', '')
        race_result['train_time_url'] = replace_str(find_bs4href(r[15]), 'amp;', '')  # 調教タイムいらないかも
        race_result['barn_comment_url'] = replace_str(find_bs4href(r[16]), 'amp;', '')  # 厩舎コメントいらないかも
        race_result['remark'] = replace_str(get_bs4text(r[17]), '\n', '')
        # race_result['trainer_name'] = r[18].a.get('title') # RaceResultに含めない
        race_result['trainer_id'] = get_id(r[18])
        # race_result['owner_name'] = r[19].a.get('title')
        race_result['owner_id'] = get_id(r[19])
        race_result['earnings'] = get_bs4float(r[20])
        results.append(race_result)
    return results


# %%　払い戻しテーブル
def get_payoff(race_id, soup):
    payoff_table = soup.select_one('dl.pay_block')
    baken = {'単勝': ['win'], '複勝': ('place1', 'place2', 'place3'),
             '枠連': ['bracket'], '馬連': ['quine'], 'ワイド': ('wide1', 'wide2', 'wide3'),
             '馬単': ['exacta'], '三連複': ['trio'], '三連単': ['trifecta']}

    payoff_dict = {'race_id': race_id}
    for k, v in baken.items():
        if payoff_table.find(text=k) is not None:
            pays = list(
                map(int,
                    list(payoff_table.find(text=k).parent.next_siblings)[3].get_text(' ').replace(',', '').split()))
            payoff_dict.update(dict(zip(v, pays)))

    return payoff_dict


def insert_db(insert_obj):
    try:
        if isinstance(insert_obj, list):
            sess.bulk_save_objects(insert_obj)
        else:
            sess.add(insert_obj)
        sess.commit()
    except Exception as e:
        logger.error(e)
        sess.rollback()


# %%
if __name__ == '__main__':
    with open('CONFIG.toml') as f:
        html_dir = Path(toml.load(f)['html']['path'])  # Path('html')
    html_files = html_dir.glob('**/*.html')

    for target_source in tqdm(html_files):
        if target_source.stem in {'200808020399', '200808020398'}:
            logger.info(f'{target_source} はnetkeiba自体のエラーにより正しいファイルではありません。')
            pass  # '200808020399'と200808020398は存在しない
        with open(target_source, encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')
        race_id = int(target_source.stem[2:])  # 桁が大すぎるので頭2桁落とす

        # レース情報
        try:
            race_info = get_race_info(race_id, soup)
        except Exception as e:
            logger.error(f'レース情報の取得に失敗しました. ファイル名: {target_source}')
            logger.error(e)
            # race_info = None

        # レース結果
        try:
            race_results = get_race_result(race_id, soup)
        except Exception as e:
            logger.error(f'レース結果の取得に失敗しました. ファイル名: {target_source}')
            logger.error(e)
            # race_results = None

        # 払い戻し
        try:
            payoff = get_payoff(race_id, soup)
        except Exception as e:
            logger.error(f'払い戻しテーブルの取得に失敗しました. ファイル名: {target_source}')
            logger.error(e)

        try:
            insert_db(RaceInfo(**race_info))
            insert_db([RaceResult(**d) for d in race_results])
            insert_db(PayOff(**payoff))

        except Exception as e:
            logger.error(e)
