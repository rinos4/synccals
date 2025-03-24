# SynCals　ログ設定＆共通ロガー
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# ログ出力先は3つ
#  - ファイル出力:   DEBUG以上の全てのログを時刻情報含めて巡回書き出し (1MB x5個)
#  - 標準出力:       INFOレベルのログを簡易表示
#  - 標準エラー出力: WARNINGレベル以上のログをプチ詳細表示(時刻無し)
#
# 2025.03.15 rinos4u	new

from logging import getLogger, config, Filter, WARNING

# フィルタクラス #####################################################################
class InfoFilter(Filter):
    def filter(self, record): return record.levelno <  WARNING
class WarnFilter(Filter):
    def filter(self, record): return record.levelno >= WARNING

# ログ定義 ########################################################################
LOG_PARAM = {
    'version': 1,
    'disable_existing_loggers': True,
    'loggers': {
        '': { # root
            'level': 'DEBUG',
            'handlers': ['logFile', 'stdout', 'stderr'],
        },
    },
    'handlers': {
        'logFile': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'logFile',
            'filename': 'log/synccals.log',
            'mode': 'a',
            'maxBytes': 1048576,
            'backupCount': 5,
            'encoding': 'utf-8',
        },
        'stdout': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'stdout',
            'stream': 'ext://sys.stdout',
            'filters': ['info'],
        },
        'stderr': {
            'class': 'logging.StreamHandler',
            'level': 'WARNING',
            'formatter': 'stderr',
            'stream': 'ext://sys.stderr',
            'filters': ['warn'],
        },
    },
    'formatters': {
        'logFile': {
            'format': '%(asctime)s|%(levelname)-7s|%(message)s',
            'datefmt': '%Y/%m/%d %H:%M:%S',
        },
        'stdout': {
            'format': '%(message)s',
            'datefmt': '%H:%M:%S',
        },
        'stderr': {
            'format': '!%(levelname)-7s! %(message)s',
            'datefmt': '%Y/%m/%d %H:%M:%S',
        },
    },
    'filters': {
        'info': {
            '()': InfoFilter, # INFO以下
        },
        'warn': {
            '()': WarnFilter, # WARN以上
        },
    },
}

# 共通ロガー作成 #####################################################################
config.dictConfig(LOG_PARAM)
g_logger = getLogger('root')
