import traceback
import jieba
from collections import Counter
import os

from .common import Common
from .my_log import logger
from .config import Config
from .db import SQLiteDB


class Data_Analysis:
    def __init__(self, config_path):
        self.config = Config(config_path)
        self.common = Common()

        # # Get the jieba library logger
        # jieba_logger = logger.getLogger("jieba")
        # # Set the jieba logger level to WARNING
        # jieba_logger.setLevel(logger.WARNING)


    # Reloadconfig
    def reload_config(self, config_path):
        self.config = Config(config_path)

    # Get the data of keywords with the most duplicates
    def get_most_common_words(self, text_list, top_num=10):
        """Get the data of keywords with the most duplicates

        Args:
            text_list (list): List of strings
            top_num (int, optional): Top n keywords with the most duplicates. Defaults to 10.

        Returns:
            dict: Keywordjson
        """

        # Suppose this is your string array
        # text_list = [
        #     "Pythonis a widely used high-level programming language",
        #     "It combines the features of interpreted, compiled, interactive, and object-oriented scripting languages",
        #     # ...More strings
        # ]

        # Use jieba for Chinese word segmentation
        words = []
        for text in text_list:
            cut_words = jieba.cut(text)
            # cut_words = jieba.cut_for_search(text)
            words.extend(cut_words)

        # Filter out single-character segmentation results
        words = [word for word in words if len(word) > 1]

        # Count the occurrences of each word
        word_counts = Counter(words)

        # Find the most frequent words
        most_common_words = word_counts.most_common(top_num)  # Get the 10 most common words

        # Use list comprehensions and dict comprehensions for the conversion
        dict_list = [{'name': name, 'value': value} for name, value in most_common_words]

        logger.debug(dict_list)

        return dict_list
    

    def get_comment_word_cloud_option(self, top_num=10):
        """Get the chart option for the danmaku word cloud (for drawing charts with nicegui)

        Args:
            top_num (int, optional): Top n keywords with the most duplicates. Defaults to 10.

        Returns:
            dict: niceguiChart drawing foroption
        """
        try:
            if not os.path.exists(self.config.get('database', 'path')):
                logger.warning(f"Database:{self.config.get('database', 'path')} does not exist. If this is your first time starting the project and it has not been run yet, ignore this error message; the database will be created automatically after a normal run, so there is no need to worry")
                return None

            db = SQLiteDB(self.config.get('database', 'path'))

            # Query data
            select_data_sql = '''
            SELECT content FROM danmu
            '''
            data_list = db.fetch_all(select_data_sql)
            text_list = [data[0] for data in data_list]

            data_json = self.get_most_common_words(text_list, top_num)

            # Scrollable legend
            option = {
                'title': {
                    'text': 'Comment keyword statistics',
                    'left': 'center'
                },
                'tooltip': {
                    'trigger': 'item',
                    'formatter': '{a} <br/>{b} : {c} ({d}%)'
                },
                'legend': {
                    'type': 'scroll',
                    'orient': 'vertical',
                    'right': 10,
                    'top': 20,
                    'bottom': 20,
                    'data': [d['name'] for d in data_json] # Use a list comprehension to extract all'name'value of
                },
                'series': [
                    {
                        'name': 'Keywords',
                        'type': 'pie',
                        'radius': '55%',
                        'center': ['50%', '60%'],
                        'data': data_json,
                        'emphasis': {
                            'itemStyle': {
                                'shadowBlur': 10,
                                'shadowOffsetX': 0,
                                'shadowColor': 'rgba(0, 0, 0, 0.5)'
                            }
                        }
                    }
                ]
            }

            return option
        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    def get_integral_option(self, type="integral", top_num=10):
        """Get the chart option for the points table (for drawing charts with nicegui)

        Args:
            type (str): Data type (integral/view_num/sign_num/total_price)
            top_num (int, optional): Top n largest data. Defaults to 10.

        Returns:
            dict: niceguiChart drawing foroption
        """
        try:
            if not os.path.exists(self.config.get('database', 'path')):
                logger.warning(f"Database:{self.config.get('database', 'path')} does not exist. If this is your first time starting the project and it has not been run yet, ignore this error message; the database will be created automatically after a normal run, so there is no need to worry")
                return None
            
            db = SQLiteDB(self.config.get('database', 'path'))

            # Query data
            select_data_sql = f'''
            SELECT * FROM integral
            ORDER BY {type} DESC
            LIMIT {top_num};
            '''
            data_list = db.fetch_all(select_data_sql)

            
            # Use a list comprehension to convert each tuple to a list
            list_list = [list(t) for t in data_list]
            username_list = [t[1] for t in data_list]

            logger.debug(f"list_list={list_list}")

            option = {
                'title': {
                    'text': 'Points table statistics',
                    'left': 'center'
                },
                'legend': {
                    'data': ['Total points', 'Views', 'Check-ins', 'Total amount'],
                    'top': 30,
                    'bottom': 30
                },
                'dataset': [
                    {
                        'dimensions': ['platform', 'username', 'uid', 'integral', 'view_num', 'sign_num', 'last_sign_ts', 'total_price', 'last_ts'],
                        'source': list_list
                    },
                    {
                        'transform': {
                            'type': 'sort',
                            'config': { 'dimension': 'integral', 'order': 'desc' }
                        }
                    }
                ],
                'tooltip': {
                    'trigger': 'axis',
                    'axisPointer': {
                        'type': 'cross',
                        'crossStyle': {
                            'color': '#999'
                        }
                    }
                },
                'toolbox': {
                    'feature': {
                        'dataView': { 'show': True, 'readOnly': False },
                        'magicType': { 'show': True, 'type': ['line', 'bar'] },
                        'restore': { 'show': True },
                        'saveAsImage': { 'show': True }
                    }
                },
                'xAxis': [
                    {
                        'type': 'category',
                        'axisTick': {
                            'alignWithLabel': True
                        },
                        'data': username_list
                    }
                ],
                'yAxis': [
                    {
                        'type': 'value',
                        'name': 'Total points',
                        'alignTicks': True,
                        'position': 'left',
                        'axisLine': {
                            'show': True
                        },
                        'axisLabel': {
                            'formatter': '{value}'
                        }
                    },
                    {
                        'type': 'value',
                        'name': 'Views',
                        'yAxisIndex': 1,
                        'alignTicks': True,
                        'position': 'left',
                        'offset': -80,
                        'axisLine': {
                            'show': True
                        },
                        'axisLabel': {
                            'formatter': '{value}'
                        }
                    },
                    {
                        'type': 'value',
                        'name': 'Check-ins',
                        'yAxisIndex': 2,
                        'alignTicks': True,
                        'position': 'right',
                        'offset': -80,
                        'axisLine': {
                            'show': True
                        },
                        'axisLabel': {
                            'formatter': '{value}'
                        }
                    },
                    {
                        'type': 'value',
                        'name': 'Total amount',
                        'yAxisIndex': 3,
                        'alignTicks': True,
                        'position': 'right',
                        'axisLine': {
                            'show': True
                        },
                        'axisLabel': {
                            'formatter': '{value}'
                        }
                    }
                ],
                'series': [
                    {
                        'name': 'Total points',
                        'type': 'bar',
                        'encode': { 'x': 'username', 'y': 'integral' }
                    },
                    {
                        'name': 'Views',
                        'type': 'bar',
                        'encode': { 'x': 'username', 'y': 'view_num' }
                    },
                    {
                        'name': 'Check-ins',
                        'type': 'bar',
                        'encode': { 'x': 'username', 'y': 'sign_num' }
                    },
                    {
                        'name': 'Total amount',
                        'type': 'bar',
                        'encode': { 'x': 'username', 'y': 'total_price' }
                    },
                ]
            }

            return option
        except Exception as e:
            logger.error(traceback.format_exc())
            return None
        

    def get_gift_option(self, top_num=10):
        """Get the chart option for the gift table (for drawing charts with nicegui)

        Args:
            top_num (int, optional): Top n largest data. Defaults to 10.

        Returns:
            dict: niceguiChart drawing foroption
        """
        try:
            if not os.path.exists(self.config.get('database', 'path')):
                logger.warning(f"Database:{self.config.get('database', 'path')} does not exist. If this is your first time starting the project and it has not been run yet, ignore this error message; the database will be created automatically after a normal run, so there is no need to worry")
                return None
            
            db = SQLiteDB(self.config.get('database', 'path'))

            # Query data
            select_data_sql = f'''
            SELECT * FROM gift
            ORDER BY total_price DESC
            LIMIT {top_num};
            '''
            data_list = db.fetch_all(select_data_sql)

            # Use a list comprehension to convert each tuple to a list
            username_list = [t[0] for t in data_list]
            total_price_list = [t[4] for t in data_list]

            logger.debug(f"username_list={username_list}")
            logger.debug(f"total_price_list={total_price_list}")

            option = {
                'title': {
                    'text': 'Gift leaderboard',
                    'left': 'center'
                },
                'tooltip': {
                    'trigger': 'axis',
                    'axisPointer': {
                        'type': 'cross',
                        'crossStyle': {
                            'color': '#999'
                        }
                    }
                },
                'toolbox': {
                    'feature': {
                        'dataView': { 'show': True, 'readOnly': False },
                        'magicType': { 'show': True, 'type': ['line', 'bar'] },
                        'restore': { 'show': True },
                        'saveAsImage': { 'show': True }
                    }
                },
                'xAxis': {
                    'max': 'dataMax'
                },
                'yAxis': {
                    'type': 'category',
                    'data': username_list,
                    'inverse': True,
                    'animationDuration': 300,
                    'animationDurationUpdate': 3003
                },
                'series': [
                    {
                        'realtimeSort': True,
                        'name': 'X',
                        'type': 'bar',
                        'data': total_price_list,
                        'label': {
                            'show': True,
                            'position': 'right',
                            'valueAnimation': True
                        }
                    }
                ]
            }

            return option
        except Exception as e:
            logger.error(traceback.format_exc())
            return None



def _empty_if_none(fn):
    """Chart option getters return None when there is no data yet (fresh install). ui.echart needs a dict."""
    import functools

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        res = fn(*a, **kw)
        return {} if res is None else res
    return wrapper


for _name in [n for n in dir(Data_Analysis) if n.startswith("get_") and n.endswith("_option")]:
    setattr(Data_Analysis, _name, _empty_if_none(getattr(Data_Analysis, _name)))
