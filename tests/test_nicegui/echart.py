from nicegui import ui
from random import random
from db import SQLiteDB

def get_most_common_words(text_list, most_common=10):
    import jieba
    from collections import Counter

    # Suppose this is your string array
    # text_list = [
    #     "Pythonis a widely used high-level programming language",
    #     "It combines the features of interpreted, compiled, interactive, and object-oriented scripting languages",
    #     "Pythondesign philosophy emphasizes code readability and concise syntax",
    #     "especially the use of whitespace indentation to delimit code blocks instead of braces or keywords",
    #     "Pythonlets developers express ideas with fewer lines of code",
    #     "Pythonis an interpreted language, so there is no compile step during development"
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
    most_common_words = word_counts.most_common(most_common)  # Get the 10 most common words

    # Use list comprehensions and dict comprehensions for the conversion
    dict_list = [{'name': name, 'value': value} for name, value in most_common_words]

    print(dict_list)

    return dict_list


db = SQLiteDB("E:\GitHub_pro\AI-Vtuber\data\data.db")
# Query data
select_data_sql = '''
SELECT content FROM danmu
'''
data_list = db.fetch_all(select_data_sql)
text_list = [data[0] for data in data_list]


option = {
    'xAxis': {'type': 'value'},
    'yAxis': {'type': 'category', 'data': ['A', 'B'], 'inverse': True},
    'legend': {'textStyle': {'color': 'gray'}},
    'series': [
        {'type': 'bar', 'name': 'Alpha', 'data': [0.1, 0.2]},
        {'type': 'bar', 'name': 'Beta', 'data': [0.3, 0.4]},
    ],
}

# option = {
#     'tooltip': {
#     },
#     'series': [{
#         'type': 'wordCloud',   #Type
#         'width': '100%',  #Width
#         'height': '100%', #Height
#         'sizeRange': [14, 60],     #Font size range
#         'textStyle': {                  #Get a random style
#             'fontFamily': 'sans-serif',
#             'fontWeight': 'bold'
#         },
#         'emphasis': {    #Style when focused
#             'focus': 'self',
#             'textStyle': {
#                 'textShadowBlur': 10,
#                 'textShadowColor': '#333'
#             }
#         },
#         'data': [{'name':'中国','value':124}, {'name':'啊对','value':52}, {'name':'Test','value':20}]     #Data source is an arrayeg:[{name:'中国',value:124}]
#     }]
# }

# Scrollable legend
option = {
  'title': {
    'text': '弹幕关键词统计',
    'subtext': '源自本地数据库',
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
    'data': [d['name'] for d in get_most_common_words(text_list)] # Use a list comprehension to extract all'name'value of
  },
  'series': [
    {
      'name': '关键词',
      'type': 'pie',
      'radius': '55%',
      'center': ['50%', '60%'],
      'data': get_most_common_words(text_list),
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

echart = ui.echart(option)

def update():
    echart.options['series'][0]['data'][0] = random()
    echart.update()

ui.button('Update', on_click=update)

ui.run(port=8088)