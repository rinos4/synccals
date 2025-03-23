#!/usr/bin/env python  # -*- coding: utf-8 -*-
#
# SynCalsメイン
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# 2025.03.15 rinos4u	new

################################################################################
# import
################################################################################
import importlib
import yaml
import webctrl
from logging import config, getLogger

################################################################################
# const
################################################################################
# カレンダー設定ファイル
CONF_FILE = 'config.yaml'

# 中間マージファイルの出力用
MERGE_FILE = 'log/mid_merge.yaml'

# ログ用ファイル
LOG_CONF	= 'log.conf'
LOG_KEY		= 'root'

################################################################################
# globals
################################################################################
# ロガー
config.fileConfig(LOG_CONF)
g_logger = getLogger(LOG_KEY)

################################################################################
# util funcs
################################################################################

################################################################################
# Data control
################################################################################

# confsに定義されたカレンダーから情報を取得
def get_cals(confs):
    ret = []
    for conf in confs['cals']:
        g_logger.debug('top:import plugin %s for %s (GET)' % (conf['file'], conf['name']))
        mod = importlib.import_module(conf['file'])
        dat = mod.get_cal(conf)
        g_logger.info('%sから%d件取得しました' % (conf['name'], len(dat)))
        ret += dat
    return ret

# マージ済み予定を各カレンダに設定
def set_cals(confs, merge):
    for conf in confs['cals']:
        g_logger.info('top:import plugin %s for %s (SET)' % (conf['file'], conf['name']))
        mod = importlib.import_module(conf['file'])
        mod.set_cal(conf, merge)

# カレンダ設定前の確認
def check_merge(confs, merge):
    for conf in confs['merge']:
        g_logger.info('top:import plugin %s for %s (MERGE)' % (conf['file'], conf['name']))
        mod = importlib.import_module(conf['file'])
        merge = mod.diff(conf, merge)
    return merge

################################################################################
# main
################################################################################
if __name__ == '__main__':
	# 設定を開く
    with open(CONF_FILE, 'r', encoding='utf-8') as f:
        confs = yaml.safe_load(f)
    if not confs:
        g_logger.error('Invalid config file')
        exit(1)

    g_logger.info('top:start SyncCalc %s' % (confs['keep']))

    # ブラウザ常駐設定ならメインでブラウザを開いておく (終了まで使いまわす)
    if confs['keep']:
        webctrl.init()

    if confs['skipget']:
        g_logger.info('top:load old merge file')
        with open(MERGE_FILE, mode='r', encoding='utf-8')as f:
            merge = yaml.safe_load(f)
    else:
        # まず全てのカレンダーの情報を抽出
        g_logger.info('top:get schedule')
        merge = get_cals(confs)
        g_logger.info('top:get %d items', len(merge))
        with open(MERGE_FILE, mode='w', encoding='utf-8')as f:
            yaml.safe_dump(merge, f, allow_unicode=True)
    
    ret = input('%d件読み込みました。\n差分チェックに進みますか？ (y/n):' % len(merge))
    if ret == 'y' or ret == 'Y':
        # カレンダーの差分を表示して、継続してよいか確認
        merge2 = check_merge(confs, merge)
        g_logger.info('%d件の設定があります。' % len(merge2))
        for item in merge2:
            if item['ctyp'] == '+':
                g_logger.info('+ %s～%s %s "%s"' % (item['tbgn'].strftime("%m/%d %H:%M"), item['tend'].strftime("%m/%d %H:%M"), item['summ'], item['desc']))

        ret = input('%d件のカレンダ登録に進みますか？(y/n):' % len(merge2))
        if ret == 'y' or ret == 'Y':
            set_cals(confs, merge2) # 継続OKならカレンダに設定
        else:
            g_logger.info('top:Skip cal set')
    else:
        g_logger.info('top:Skip cal merge')

    # ブラウザ常駐設定ならメインで開放
    if confs['keep']:
        webctrl.deinit()

    g_logger.info('top:End SyncCalc')

