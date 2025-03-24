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
from logconf import g_logger

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

# 検索のコラム数
SEARCH_COLUMN = 8

################################################################################
# globals
################################################################################

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

# 事務所が違うなら変更
def ar_checkgroup(group):
    # 事務所情報を取得
    menu = webctrl.find('cmn-hdr-btn-text', webctrl.By.CLASS_NAME)
    if len(menu) < 2:
        g_logger.error('arr:too small menu %s' % (len(menu)))
        return 1

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
            return 2

    return 0 # 成功
    
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
    pre = 0

    for group in conf['group']:
        # 事務所確認
        g_logger.debug('arr:group %s' % (group))
        ar_checkgroup(group)
        
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

        while True:
            # 抽出した予定をオブジェクトに格納
            bookary = webctrl.get('bookingSearchList').split('\n')
            for i in range(0, len(bookary) - (SEARCH_COLUMN - 1), SEARCH_COLUMN):
                dt = bookary[i + 2].split(' ')
                dbgn = dt[2][:10]
                dend = dt[2][:10] #デフォルトは同日        (例：['2025/01/11(土)', '12:34', '2025/02/22(土)', '13:00～15:00'])
                tm = dt[3].split('～')
                if len(dt) > 4: # 日マタギの場合は特殊形式 (例：['2025/01/11(土)', '12:34', '2025/02/22(土)', '19:00～2025/02/23(日)', '00:00'])
                    dend = tm[1][:10]
                    tm[1] = dt[4]

                book = {
                    'ctyp': CAL_TYPE,
                    'tbgn': datetime.strptime(dbgn + ' ' + tm[0], '%Y/%m/%d %H:%M'),
                    'tend': datetime.strptime(dend + ' ' + tm[1], '%Y/%m/%d %H:%M'),
                    'summ': group + '、' + bookary[i + 5] + '、' + bookary[i + 6] + '、' + bookary[i],
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
            
            # 次ページ処理
            if not webctrl.exclick('icnNext', webctrl.By.CLASS_NAME):
                break

            # 更新を待って次ページの解析
            time.sleep(WAIT_SEARCH)

        # グループごとに取得した件数を表示しておく
        g_logger.info('arr:%-4s=%d件' % (group, len(ret) - pre))
        pre = len(ret)

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
        tbgn  = i['tbgn'].strftime('%Y/%m/%d %H:%M')
        tend  = i['tend'].strftime('%Y/%m/%d %H:%M')
        summ  = i['summ'].split('@')
        group = summ[2]

        if i['ctyp'] == '+': # 追加マーク
            # 追加が無効化されている場合はログ出力のみ
            if conf['skipadd']:
                g_logger.info('arr:skip add %s～%s:%s %s' % (tbgn, tend, i['summ'], i['desc']))
                continue

            # 追加処理開始
            g_logger.info('arr:add %s～%s:%s %s' % (tbgn, tend, i['summ'], i['desc']))

            # 事務所確認
            ar_checkgroup(group)

            # 空いている予定をクリック
            # →schldCellが複数あり、場所によりエラーになる。例外なくなるまで叩く
            for elm in webctrl.find('schldCell', webctrl.By.CLASS_NAME):
                try:
                    webctrl.fclick(elm)
                    time.sleep(WAIT_AFTER)
                    break # 例外が発生しなかったら継続
                except:
                    continue

            # メニューをaddmenuにセットして詳細画面を開く
            webctrl.set('bookingMenuBalloonSelectMenu', conf['addmenu'])
            time.sleep(WAIT_AFTER) # 入力確認も兼ねて、表示したまま少し待つ
            webctrl.click('bookingRegist')
            time.sleep(WAIT_AFTER) # 入力確認も兼ねて、表示したまま少し待つ

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

            # 継続するか確認する設定なら入力待ち
            if conf['waitadd']:
                ret = input('追加処理を継続しますか？(y/n):')
                if ret != 'y' and  ret != 'Y':
                    g_logger.error('追加処理をキャンセルしました')
                    # ×ボタン & OK
                    webctrl.click('js-popupRegistClose', webctrl.By.CLASS_NAME)
                    time.sleep(WAIT_AFTER)
                    webctrl.click('js-popupAlertClose')
                    time.sleep(WAIT_AFTER)
                    continue

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

        if i['ctyp'] == '-': # 削除マーク
            if conf['skipdel']:
                g_logger.info('arr:skip del %s～%s:%s %s' % (tbgn, tend, i['summ'], i['desc']))
                continue

            # 予約番号が格納されているかチェック
            if len(summ) < 4 or len(summ[3]) < 8:
                g_logger.error('arr:invalid booking No %s' % summ)
                continue

            ## 事務所確認
            ar_checkgroup(group)
            time.sleep(WAIT_AFTER)

            ## 予定検索ページを開く
            webctrl.jump(URL_SEARCH)
            time.sleep(WAIT_AFTER)

            # 削除処理追加
            g_logger.info('arr:del %s: %s～%s:%s %s' % (summ[3], tbgn, tend, i['summ'], i['desc']))
            webctrl.set('bookingNo', summ[3])

            # 検索実行
            webctrl.click('btn-search', webctrl.By.CLASS_NAME)
            time.sleep(WAIT_SEARCH)

            # 検索ヒットが１件かつ、サイボウズ入力の場合だけ削除
            bookary = webctrl.get('bookingSearchList').split('\n')
            if len(bookary) != SEARCH_COLUMN:
                g_logger.warning('arr:del 検索数異常 %d' % (len(bookary)))
                continue

            # サイボウズ追加でなければ警告
             
            if bookary[5] != conf['addmenu']:
                g_logger.warning('arr:del 検索タイプ異常 "%s"' % (bookary[5]))
                continue

            # 「該当する予約がありません」の場合はスキップ
            if 'ありません' in webctrl.get('dialogueMessage'):
                g_logger.info('arr:del no data')
                webctrl.click('closeErrDialogue')
                continue

            # 継続するか確認する設定なら入力待ち
            if conf['waitdel']:
                ret = input('削除処理を継続しますか？(y/n):')
                if ret != 'y' and  ret != 'Y':
                    g_logger.error('削除処理をキャンセルしました')
                    continue

            # 削除実行
            webctrl.click('js-popupCancelTrigger', webctrl.By.CLASS_NAME)
            time.sleep(WAIT_AFTER)
            webctrl.set('cancelReason', conf['delreason']) # キャンセル理由
            time.sleep(WAIT_AFTER)
            webctrl.click('doCancel')
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
