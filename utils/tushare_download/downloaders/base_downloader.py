import logging
import math
import os.path
import time

import pandas as pd
import sqlalchemy
import tushare

from utils import utils, CONF, db_utils

logger = logging.getLogger(__name__)

RETRY = 5  # 尝试几次
WAIT = 1  # 每次delay时常(秒)
MAX_PER_SECOND = 200  # 每分钟可以访问多少次，200元/年的账号默认是400/分钟，但是大量访问会降级到200/分钟，所以可能要经常手工调整
CALL_INTERVAL = 60 / MAX_PER_SECOND  # 150毫秒,1分钟400次
EALIEST_DATE = '20080101'  # 最早的数据日期


class BaseDownload():
    """
    主要实现一个下载基类，用于完成，控制下载速度，和反复尝试，以及保存到数据库中的基础功能
    """

    def __init__(self):
        self.db_engine = utils.connect_db()
        token = CONF['datasources']['tushare']['token']
        tushare.set_token(token)
        self.pro = tushare.pro_api()
        logger.debug("注册到Tushare上，token:%s***", token[:10])
        self.retry_count = 0
        self.save_dir = "data/tushare_download"
        if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)
        self.call_interval = CALL_INTERVAL

    def get_table_name(self):
        """
        用于返回需要存到数据库中的表名
        :return:
        """
        raise NotImplemented()

    def get_date_column_name(self):
        """
        用于返回需要存到数据库中的表中的关键日期的字段名
        :return:
        """
        raise NotImplemented()

    def get_start_date(self):
        """
        如果表存在，就返回关键日期字段中，最后的日期，
        这个函数主要用于帮助下载后续日期的数据。
        如果表不存在，返回20080101
        :return:
        """

        if not db_utils.is_table_exist(self.db_engine, self.get_table_name()):
            logger.debug("表[%s]在数据库中不存在，返回默认最早开始日期[%s]", self.get_table_name(), EALIEST_DATE)
            return EALIEST_DATE

        table_name = self.get_table_name()
        date_column_name = self.get_date_column_name()
        df = pd.read_sql('select max({}) from {}'.format(date_column_name, table_name), self.db_engine)
        assert len(df) == 1
        latest_date = df.iloc[:, 0].item()
        if latest_date is None:
            logger.debug("表[%s]中无数据，返回默认最早开始日期[%s]", self.get_table_name(), EALIEST_DATE)
            return EALIEST_DATE

        # 日期要往后错一天，比DB中的
        latest_date = utils.tomorrow(latest_date)
        logger.debug("数据库中表[%s]的最后日期[%s]为：%s", table_name, date_column_name, latest_date)
        return latest_date

    def to_db(self, df, if_exists='append'):
        """
        保存dataframe到数据库中，需要处理一下日期字段变为str，而不是text
        :param df:
        :param if_exists:
        :return:
        """

        start_time = time.time()
        dtype_dic = {
            'ts_code': sqlalchemy.types.VARCHAR(length=9),
            'trade_date': sqlalchemy.types.VARCHAR(length=8),
            'ann_date': sqlalchemy.types.VARCHAR(length=8)
        }
        df.to_sql(self.get_table_name(),
                  self.db_engine,
                  index=False,
                  if_exists=if_exists,
                  dtype=dtype_dic,
                  chunksize=1000)
        logger.debug("导入 [%.2f] 秒, df[%d条]=>db[表%s] ", time.time() - start_time, len(df), self.get_table_name())

        # 保存到数据库中的时候，看看有无索引，如果没有，创建之
        db_utils.create_db_index(self.db_engine, self.get_table_name(), df)

    def retry_call(self, func, **kwargs):
        """
        下载时候，频繁调用会出发tushare的限制：
        `
            Tushare Exception: 抱歉，您每分钟最多访问该接口400次，
            权限的具体详情访问：https://tushare.pro/document/1?doc_id=108
        `
        所以，每200毫秒调用一次，比较安全，大概是一分钟最多是5*60=300次。
        这个函数，就用于来控制下载的速度。
        还支持5次的不断拉长间隔的重试。
        """

        while self.retry_count < RETRY:
            try:
                # print(kwargs)
                df = func(**kwargs)
                self.retry_count = 0
                return df
            except:
                logger.exception("调用Tushare函数[%s]失败:%r", str(func), kwargs)
                sleep = int(math.pow(2, self.retry_count))
                logger.debug("sleep %d 秒再试", sleep*30)
                time.sleep(sleep*30)
                self.retry_count += 1
        raise RuntimeError("尝试调用Tushare API多次失败......")

    def save(self, name, df):
        """
        保存dataframe到默认的文件夹内
        :param name:
        :param df:
        :return:
        """

        file_path = os.path.join(self.save_dir, name)
        df.to_csv(file_path)
        return file_path
