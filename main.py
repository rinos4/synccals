#!/usr/bin/env python  # -*- coding: utf-8 -*-
#
# SynCalsメイン
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# 2025.03.15 rinos4u	new
# 2025.03.23 rinos4u	一致チェックにdescを含めるか設定できるように変更
# 2025.03.30 rinos4u	処理継続をinputで確認できるよう機能を追加
# 2025.04.06 qqe		サイボウズからのコピーモードを追加

################################################################################
# import
################################################################################
import importlib
import yaml
import webctrl
from logconf import g_logger
import sys

################################################################################
# const
################################################################################
APP_VER = '1.0.3'
# カレンダー設定ファイル
CONF_FILE = 'config.yaml'

# 中間マージファイルの出力用
MERGE_FILE = 'log/mid_merge.yaml'

DESC_MAX = 25 # 表示目的のみ。よく使う画面幅に応じて設定。

################################################################################
# globals
################################################################################

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
        try:
            dat = mod.get_cal(conf)
        except Exception:
            #g_logger.exception('GETプラグイン例外(%s)' % conf['name'])
            g_logger.debug('%s - get_cal' % conf['name'],exc_info=True) #ダンプはログファイルのみに出す
            g_logger.info('GETプラグインの例外により、プログラムを中断します')
            exit(101)

        g_logger.info('%sから%d件取得しました' % (conf['name'], len(dat)))
        ret += dat
    return ret

# 同期した差分を各カレンダに設定
def set_cals(confs, merge):
    ret = 0
    for conf in confs['cals']:
        g_logger.debug('top:import plugin %s for %s (SET)' % (conf['file'], conf['name']))
        mod = importlib.import_module(conf['file'])
        try:
            ret += mod.set_cal(conf, merge)
        except Exception:
            #g_logger.exception('SETプラグイン例外(%s)' % conf['name'])
            g_logger.debug('%s - set_cal' % conf['name'],exc_info=True) #ダンプはログファイルのみに出す
            g_logger.info('SETプラグインの例外により、プログラムを中断します')
            exit(102)
    return ret

# カレンダの同期
def sync_cals(confs, merge):
    for conf in confs['sync']:
        g_logger.debug('top:import plugin %s for %s (SYNC)' % (conf['file'], conf['name']))
        mod = importlib.import_module(conf['file'])
        try:
            merge = mod.sync_cal(conf, merge)
        except Exception:
            #g_logger.exception('SYNCプラグイン例外(%s)' % conf['name'])
            g_logger.debug('%s - sync_cal' % conf['name'],exc_info=True) #ダンプはログファイルのみに出す
            g_logger.info('SYNCプラグインの例外により、プログラムを中断します')
            exit(103)
    return merge

# カレンダから一つの予定を取り出す
def get_one_cals(confs):
    ret = []
    for conf in confs['cals']:
        g_logger.debug('top:import plugin %s for %s (GET-ONE)' % (conf['file'], conf['name']))
        mod = importlib.import_module(conf['file'])
        try:
            dat = mod.get_one_cal(conf)
        except Exception:
            g_logger.debug('%s - get_one_cal' % conf['name'],exc_info=True) #ダンプはログファイルのみに出す
            g_logger.info('GET-ONEプラグインの例外により、プログラムを中断します')
            exit(104)

        g_logger.info('%sから%d件取得しました' % (conf['name'], len(dat)))
        ret += dat
    return ret

################################################################################
# 同期モード
def DoSync(confs):
    # 取得処理の要否判定
    if confs['skipget']:
        # 前回保存したデータを読み込んで進む 
        g_logger.info('top:load old merge file')
        with open(MERGE_FILE, mode='r', encoding='utf-8')as f:
            merge = yaml.safe_load(f)
    else:
        # カレンダーにアクセスして情報を抽出
        g_logger.debug('top:get schedule')
        merge = get_cals(confs)
        g_logger.debug('top:get %d items', len(merge))

        # 中間ファイルの保存(skipget=1の場合に利用 & デバッグ用)
        with open(MERGE_FILE, mode='w', encoding='utf-8')as f:
            yaml.safe_dump(merge, f, allow_unicode=True)

    # カレンダーの読み込み数を表示して、継続してよいか確認
    print('─' * 70)
    print('合計%d件読み込みました。' % len(merge))
    if confs['waitsync']:
        ret = input('差分チェックに進みますか？ (y/n):')
        if ret != 'y' and ret != 'Y':
            g_logger.info('処理を中止しました')
            return 201

    # 同期処理を実行し、同期が必要なデータを表示
    merge2 = sync_cals(confs, merge)
    count = 0
    for item in merge2:
        if item['ctyp'] == '+' or item['ctyp'] == '-':
            count += 1
            g_logger.info('%s%3d %s～%s %s "%s%s"' % (item['ctyp'], count, item['tbgn'].strftime("%m/%d %H:%M"), item['tend'].strftime("%H:%M"), '-'.join(item['summ'].split('@')[:3]), item['desc'][:DESC_MAX], '…' if len(item['desc']) > DESC_MAX else ''))

    # 同期リストでカレンダー登録してよいか確認
    setcount = 0
    if count:
        print('─' * 70)
        if confs['waitset']:
            ret = input('%d件のカレンダ登録/削除に進みますか？(y/n):' % count)
            if ret != 'y' and ret != 'Y':
                g_logger.info('処理を中止しました')
                return 202

        setcount = set_cals(confs, merge2) # 継続OKならカレンダに設定
        g_logger.info('%d件/%d件を登録しました' % (setcount, count))
    else:
        g_logger.info('同期する予定がありませんでした')
    
    return 0


################################################################################
# コピーモード
def DoCopy(confs):
    # カレンダーにアクセスして１つのカレンダー情報を抽出
    g_logger.debug('top:get schedule')
    merge = get_one_cals(confs)
    g_logger.debug('top:get %d items', len(merge))

    # 同期処理を実行し、同期が必要なデータを表示
    merge2 = sync_cals(confs, merge)

    count = 0
    for item in merge2:
        if item['ctyp'] == '+' or item['ctyp'] == '-':
            count += 1
            g_logger.info('%s%3d %s～%s %s "%s%s"' % (item['ctyp'], count, item['tbgn'].strftime("%m/%d %H:%M"), item['tend'].strftime("%H:%M"), '-'.join(item['summ'].split('@')[:3]), item['desc'][:DESC_MAX], '…' if len(item['desc']) > DESC_MAX else ''))
    
    # 同期リストでカレンダー登録してよいか確認
    if count:
        print('─' * 70)
        if confs['waitcopy']:
            ret = input('%d件のカレンダ登録/削除に進みますか？(y/n):' % count)
            if ret != 'y' and ret != 'Y':
                g_logger.info('処理を中止しました')
                return 202

        setcount = set_cals(confs, merge2) # 継続OKならカレンダに設定
        g_logger.info('%d件/%d件を登録しました' % (setcount, count))
    else:
        g_logger.info('同期する予定がありませんでした')

    return 0

################################################################################
# main
################################################################################
if __name__ == '__main__':
    # 設定を開く
    with open(CONF_FILE, 'r', encoding='utf-8') as f:
        confs = yaml.safe_load(f)
    if not confs:
        g_logger.error('Invalid config file')
        exit(-1)

    g_logger.debug('top:start SyncCalc %s %s' % (APP_VER, confs['keepdriver']))

    # ブラウザ常駐設定ならメインでブラウザを開いておく (終了まで使いまわす)
    if confs['keepdriver']:
        webctrl.init(confs['devscale'])

    # 引数に応じてモードを切り替え
    if len(sys.argv) < 2:
        ret = DoSync(confs)
    else:
        ret = DoCopy(confs)

    # ブラウザ常駐設定ならメインで開放
    if confs['keepdriver']:
        webctrl.deinit()

    g_logger.debug('top:End SyncCalc')
    exit(ret)
