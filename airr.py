#!/usr/bin/env python  # -*- coding: utf-8 -*-
#
# SynCals  Airリザーブプラグイン
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# 2025.03.15 rinos4u	new

################################################################################
# import
################################################################################
import time
import yaml
import webctrl

from datetime import datetime, timedelta
from logging import config, getLogger

################################################################################
# const
################################################################################
URL_SEARCH = 'https://airreserve.net/reserve/booking/list/?from=header'
URL_APPEND = 'https://airreserve.net/reserve/calendar/'

CAL_TYPE = 'airr'

CONF_FILE = 'config.yaml'
MIDDLE_FILE = 'log/mid_airr.yaml'

WAIT_AFTER  = 0.5
WAIT_SEARCH = 3
WAIT_INPUT  = 2

# 名前欄に入れられる最大文字列
MAX_DESC    = 20

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
# ログインページ処理
def ar_login(conf):
    # ユーザ/パスワード設定
    webctrl.set('username', conf['user'], webctrl.By.NAME)
    webctrl.set('password', conf['pass'], webctrl.By.NAME)
    time.sleep(WAIT_AFTER) # 入力確認も兼ねて、表示したまま少し待つ

    # クリックしてページ遷移を待つ
    webctrl.click('primary', webctrl.By.CLASS_NAME)
    webctrl.wait()

################################################################################
# Plugin API
################################################################################
# 予定取得
def get_cal(conf):
    keep = webctrl.driver()
    if not keep:
        webctrl.init()

    # 予定検索ページを開く
    webctrl.jump(URL_SEARCH)

    # ユーザ/パスワード画面に遷移した？
    if 'login' in webctrl.url():
        ar_login(conf)
        webctrl.jump(URL_SEARCH) # 再度予定検索ページに移動

    # 店舗選択画面なら先頭を叩いておく
    selst = webctrl.gets('h1', webctrl.By.TAG_NAME)
    if selst and '選択' in selst[0]:
        g_logger.debug('arr:select top page1 %s' % (selst[0]))
        webctrl.click('storeList__list__innerBox__name', webctrl.By.CLASS_NAME)

    # 応答値格納用
    old = set() # 追加済みセット
    ret = []    # 関数から戻す配列

    for group in conf['group']:
        g_logger.info('arr:group %s' % (group))
        # 事務所確認
        menu = webctrl.find('cmn-hdr-btn-text', webctrl.By.CLASS_NAME)
        if len(menu) < 2:
            g_logger.error('arr:too small menu %s' % (len(menu)))
            continue

        # 事務所が違うなら変更
        if group not in menu[1].text:
            g_logger.debug('change:group from %s' % (menu[1].text))
            menu[1].click()
            webctrl.click('cmn-hdr-account-menu-link', webctrl.By.CLASS_NAME)
            time.sleep(WAIT_AFTER)
            webctrl.wait()
            store = webctrl.find('storeList__list__innerBox', webctrl.By.CLASS_NAME)
            for s in store:
                if group in s.text:
                    s.click()
                    webctrl.wait()
                    break
            else:
                # 事務所が見つからなかった!?
                g_logger.error('arr:store not found %s' % (group))
                continue
        
        # 予定検索ボタン
        webctrl.click('h-ico-search', webctrl.By.CLASS_NAME)
        time.sleep(WAIT_AFTER)

        # 終了日を設定
        today = datetime.now()
        daymin = today.replace(hour=0, minute=0, second=0, microsecond=0)
        daymax = daymin + timedelta(days=conf['range'] - 1)
        g_logger.debug('arr:get %s to %s' % (daymin, daymax))
        webctrl.set('bookingFromDt', daymin.strftime('%Y/%m/%d'))
        webctrl.set('bookingToDt', daymax.strftime('%Y/%m/%d'))
        time.sleep(WAIT_AFTER) # レンジを1秒表示

        # 予約ステータス指定(キャンセル状態を除く)
        for i in range(3):
            webctrl.click('bookingStatusCdList%d' % i)    

        # 検索実行
        webctrl.click('btn-search', webctrl.By.CLASS_NAME)
        time.sleep(WAIT_SEARCH)

        # 「該当する予約がありません」の場合はスキップ
        if 'ありません' in webctrl.get('dialogueMessage'):
            g_logger.info('arr:no data')
            webctrl.click('closeErrDialogue')
            continue

        # 抽出した予定をオブジェクトに格納
        bookary = webctrl.get('bookingSearchList').split('\n')
        for i in range(0, len(bookary) - 7, 8):
            dt = bookary[i + 2].split(' ')
            tm = dt[3].split('～')
            book = {
                'ctyp': CAL_TYPE,
                'tbgn': datetime.strptime(dt[2][:10] + ' ' + tm[0], '%Y/%m/%d %H:%M'),
                'tend': datetime.strptime(dt[2][:10] + ' ' + tm[1], '%Y/%m/%d %H:%M'),
                'summ': group + '、' + bookary[i + 5] + '、' + bookary[i + 6],
                'desc': bookary[i + 3]
            }

            # 同一の予定が無ければ追加
            sbook = str(book) # 文字列化したオブジェクトで同一チェック
            if sbook not in old:
                old.add(sbook)
                ret.append(book)
                g_logger.debug('arr:book add  %s' % (sbook))
            else:
                g_logger.debug('arr:book skip %s' % (sbook))

    # 開放
    if not keep:
        webctrl.deinit()

    # 中間ファイルを保存しておく
    with open(MIDDLE_FILE, mode='w', encoding='utf-8')as f:
        yaml.safe_dump(ret, f, allow_unicode=True)

    return ret

# 予定設定 ########################################################################
# グループ切り替えを最小限にするために、mergeは事務所順に並べておくことが望ましい
def set_cal(conf, merge):
    keep = webctrl.driver()
    if not keep:
        webctrl.init()

    # 予定追加のページを開く
    webctrl.jump(URL_APPEND)

    # ユーザ/パスワード画面に遷移した？
    if 'login' in webctrl.url():
        ar_login(conf)

    # 店舗選択画面なら先頭を叩いておく
    selst = webctrl.gets('h1', webctrl.By.TAG_NAME)
    if selst and '選択' in selst[0]:
        g_logger.debug('arr:select top page2 %s' % (selst[0]))
        webctrl.click('storeList__list__innerBox__name', webctrl.By.CLASS_NAME)

    # 予定追加のページを開く
    webctrl.jump(URL_APPEND)

    for i in merge:
        if i['ctyp'] == '+': # 追加マーク
            summ = i['summ'].split('@')

            # 事務所確認
            group = summ[2]
            menu = webctrl.find('cmn-hdr-btn-text', webctrl.By.CLASS_NAME)
            if len(menu) < 2:
                g_logger.error('arr:too small menu2 %s' % (len(menu)))
                continue

            # 事務所が違うなら変更
            if group not in menu[1].text:
                g_logger.debug('change:group from %s' % (menu[1].text))
                menu[1].click()
                webctrl.click('cmn-hdr-account-menu-link', webctrl.By.CLASS_NAME)
                time.sleep(WAIT_AFTER)
                webctrl.wait()
                store = webctrl.find('storeList__list__innerBox', webctrl.By.CLASS_NAME)
                for s in store:
                    if group in s.text:
                        s.click()
                        webctrl.wait()
                        break
                else:
                    # 事務所が見つからなかった!?
                    g_logger.error('arr:store not found2 %s' % (group))
                    continue

            # とりあえず、空いている予定をクリック
            webctrl.click('staffSchld', webctrl.By.CLASS_NAME)

            # メニューをaddmenuにセットして詳細画面を開く
            webctrl.set('bookingMenuBalloonSelectMenu', conf['addmenu'])
            time.sleep(WAIT_AFTER) # 入力確認も兼ねて、表示したまま少し待つ
            webctrl.click('bookingRegist')
            time.sleep(WAIT_AFTER) # 入力確認も兼ねて、表示したまま少し待つ

            tbgn = i['tbgn'].strftime('%Y/%m/%d %H:%M')
            tend = i['tend'].strftime('%Y/%m/%d %H:%M')
            g_logger.info('arr:add %s～%s:%s' % (tbgn, tend, i['desc']))

            # 開始時間を設定 (2025/01/23 12:34)
            webctrl.set('rmStartDate',       tbgn[  :10])
            time.sleep(WAIT_AFTER)
            webctrl.selindexvalue('rmStartTimeHour',   tbgn[11:13])
            time.sleep(WAIT_AFTER)
            webctrl.selindexvalue('rmStartTimeMinute', tbgn[14:16])
            time.sleep(WAIT_AFTER)

            # 終了時間を設定
            webctrl.set('rmEndDate',         tend[  :10])
            time.sleep(WAIT_AFTER)
            webctrl.selindexvalue('rmEndTimeHour',     tend[11:13])
            time.sleep(WAIT_AFTER)
            webctrl.selindexvalue('rmEndTimeMinute',   tend[14:16])
            time.sleep(WAIT_AFTER)
            webctrl.click('exItem01', webctrl.By.NAME) # カレンダのフォーカス外し

            # 場所/人をセット
            sel = webctrl.find('resrcSelect', webctrl.By.CLASS_NAME)
            time.sleep(WAIT_AFTER) # 入力確認も兼ねて、表示したまま少し待つ
            if len(sel) < 2:
                g_logger.error('arr:Invalid menu %d' % (len(sel)))
                break # 予期せぬ事態。継続しても同じなので停止する。
            webctrl.fset(sel[0], summ[1])
            webctrl.fset(sel[1], summ[0])

            # セイは全角カナのみ。登録した文字をセット
            webctrl.set('lastNmKn',          conf['addsei'], webctrl.By.NAME)
            webctrl.set('lastNm',            i['desc'][:MAX_DESC],             webctrl.By.NAME)
            webctrl.set('firstNm',           i['desc'][MAX_DESC:MAX_DESC * 2], webctrl.By.NAME)
            time.sleep(WAIT_INPUT) # 入力確認も兼ねて、表示したまま少し待つ
 
            # 少しだけ設定を見えるようにする
            time.sleep(WAIT_INPUT)
            webctrl.click('rmRegistButton')
            time.sleep(WAIT_INPUT)
            webctrl.click('rmRegistButton')
            time.sleep(WAIT_SEARCH)

            # 上手く押せなかった場合はエラーを出す
            if webctrl.get('rmRegistButton'):
                g_logger.error('arr:failed %s～%s:%s' % (tbgn, tend, i['desc']))
                # ×ボタン & OK
                webctrl.click('js-popupRegistClose', webctrl.By.CLASS_NAME)
                time.sleep(WAIT_AFTER)
                webctrl.click('js-popupAlertClose')
                time.sleep(WAIT_AFTER)
            
    # 開放
    if not keep:
        webctrl.deinit()

################################################################################
# main
################################################################################
if __name__ == '__main__':
    # 直呼び出しは読み出しテスト
    with open(CONF_FILE, 'r', encoding='utf-8') as f:
        confs = yaml.safe_load(f)

    conf = next(filter(lambda c: c['file'] == CAL_TYPE, confs['cals']), None)
    if conf:
        ret = get_cal(conf)
        print(ret)
