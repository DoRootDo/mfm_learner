import calendar
import datetime
import logging
import os
import warnings

import matplotlib.pyplot as plt
import yaml
from backtrader.plot import Plot_OldSync
from pandas import Series
from sqlalchemy import create_engine

import conf
import utils

logger = logging.getLogger(__name__)

DB_FILE = "../data/tushare.db"


def load_config():
    if not os.path.exists(conf.CONF_PATH):
        raise ValueError("配置文件[conf/config.yml]不存在!(参考conf/config.sample.yml):" + conf.CONF_PATH)
    f = open(conf.CONF_PATH, 'r', encoding='utf-8')
    result = f.read()
    # 转换成字典读出来
    data = yaml.load(result, Loader=yaml.FullLoader)
    logger.info("读取配置文件:%r", conf.CONF_PATH)
    return data


def connect_db():
    uid = utils.CONF['datasources']['mysql']['uid']
    pwd = utils.CONF['datasources']['mysql']['pwd']
    db = utils.CONF['datasources']['mysql']['db']
    host = utils.CONF['datasources']['mysql']['host']
    port = utils.CONF['datasources']['mysql']['port']
    engine = create_engine("mysql+pymysql://{}:{}@{}:{}/{}?charset={}".format(uid, pwd, host, port, db, 'utf8'))
    # engine = create_engine('sqlite:///' + DB_FILE + '?check_same_thread=False', echo=echo)  # 是否显示SQL：, echo=True)
    return engine


def str2date(s_date, format="%Y%m%d"):
    return datetime.datetime.strptime(s_date, format)


def get_monthly_duration(start_date, end_date):
    """
    把开始日期到结束日期，分割成每月的信息
    比如20210301~20220515 =>
    [   [20210301,20210331],
        [20210401,20210430],
        ...,
        [20220401,20220430],
        [20220501,20220515]
    ]
    """

    start_date = str2date(start_date)
    end_date = str2date(end_date)
    years = list(range(start_date.year, end_date.year + 1))
    scopes = []
    for year in years:
        if start_date.year == year:
            start_month = start_date.month
        else:
            start_month = 1

        if end_date.year == year:
            end_month = end_date.month + 1
        else:
            end_month = 12 + 1

        for month in range(start_month, end_month):

            if start_date.year == year and start_date.month == month:
                s_start_date = date2str(datetime.date(year=year, month=month, day=start_date.day))
            else:
                s_start_date = date2str(datetime.date(year=year, month=month, day=1))

            if end_date.year == year and end_date.month == month:
                s_end_date = date2str(datetime.date(year=year, month=month, day=end_date.day))
            else:
                _, last_day = calendar.monthrange(year, month)
                s_end_date = date2str(datetime.date(year=year, month=month, day=last_day))

            scopes.append([s_start_date, s_end_date])

    return scopes


def get_yearly_duration(start_date, end_date):
    """
    把开始日期到结束日期，分割成每年的信息
    比如20210301~20220501 => [[20210301,20211231],[20220101,20220501]]
    """
    start_date = str2date(start_date)
    end_date = str2date(end_date)
    years = list(range(start_date.year, end_date.year + 1))
    scopes = [[f'{year}0101', f'{year}1231'] for year in years]

    if start_date.year == years[0]:
        scopes[0][0] = date2str(start_date)
    if end_date.year == years[-1]:
        scopes[-1][1] = date2str(end_date)

    return scopes


def tomorrow(s_date):
    today = str2date(s_date)
    __tomorrow = today + datetime.timedelta(days=1)
    return date2str(__tomorrow)


def today():
    now = datetime.datetime.now()
    return datetime.datetime.strftime(now, "%Y%m%d%H%M%S")


def date2str(date, format="%Y%m%d"):
    return datetime.datetime.strftime(date, format)


def dataframe2series(df):
    if type(df) == Series: return df
    assert len(df.columns) == 1, df.columns
    return df.iloc[:, 0]


def init_logger():
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger('matplotlib.font_manager').disabled = True
    logging.getLogger('matplotlib.colorbar').disabled = True
    logging.getLogger('matplotlib').disabled = True
    logging.getLogger('fontTools.ttLib.ttFont').disabled = True
    warnings.filterwarnings("ignore")
    warnings.filterwarnings("ignore", module="matplotlib")

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d P%(process)d: %(message)s')

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handlers = logger.handlers
    for handler in handlers:
        handler.setLevel(level=logging.DEBUG)
        handler.setFormatter(formatter)


class MyPlot(Plot_OldSync):
    def show(self):
        plt.savefig("debug/backtrader回测.jpg")
