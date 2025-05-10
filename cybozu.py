#!/usr/bin/env python  # -*- coding: utf-8 -*-
#
# SynCals  cybozuプラグイン
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# 2025.03.15 rinos4u	new

################################################################################
# import
################################################################################
import time
import yaml
import webctrl
import re
from datetime import datetime, timedelta
from logconf import g_logger

################################################################################
# const
################################################################################
# 予定表ページ
URL_SEARCH = 'https://%s.cybozu.com/o/ag.cgi?page=ScheduleIndex'
# 詳細ページ (待機用)
URL_DETAIL = 'https://%s.cybozu.com/o/ag.cgi?page=ScheduleView&UID='

CAL_TYPE = 'cybozu'

CONF_FILE = 'config.yaml'
MIDDLE_FILE = 'log/mid_cybozu.yaml'

WAIT_LOGIN  = 1 # どのアカウントでログインしたか分かるように表示を止める
WAIT_SEARCH = 1 # カレンダ表示が更新されるまでの時間

BTN_NEXTWEEK = -1 # 翌週ボタンはユニークIDがないためインデックスで指定(-1=最後のボタン)

################################################################################
# globals
################################################################################

################################################################################
# util funcs
################################################################################
# ログインページ処理
def cb_login(conf):
    g_logger.debug('cyb:cb_login')
    # ユーザ/パスワード設定
    webctrl.set('username', conf['user'], webctrl.By.NAME)
    webctrl.set('password', conf['pass'], webctrl.By.NAME)
    if not webctrl.isselect('input-rememberMe-slash'):
        webctrl.click('label-checkbox', webctrl.By.CLASS_NAME)

    time.sleep(WAIT_LOGIN) # 入力確認も兼ねて、表示したまま少し待つ

    # クリックしてページ遷移を待つ
    webctrl.click('login-button', webctrl.By.CLASS_NAME)
    webctrl.wait() # ページ読み込み待ち

# 分を計算
def calcmin(s):
    t = s.split(':')
    if len(t) < 2:
        return -1
    try:
        return int(t[0]) * 60 + int(t[1])
    except ValueError:
        return -1
    

################################################################################
# Plugin API
################################################################################
# 予定取得
def get_cal(conf):
    keep = webctrl.driver()
    if not keep:
        webctrl.init(conf['devscale'])

    # 予定検索ページを開く
    webctrl.jump(URL_SEARCH % conf['serv'])

    # ユーザ/パスワード画面に遷移した？
    if 'login' in webctrl.url():
        cb_login(conf)

    # カレンダーから予定を抽出
    old = set() # 追加済みセット
    ret = []    # 関数から戻す配列
    pre = 0     # カウント用
    # 抽出範囲
    today = datetime.now()
    daymin = today.replace(hour=0, minute=0, second=0, microsecond=0)
    daymax = daymin + timedelta(days=conf['range'])
    g_logger.debug('cyb:get %s to %s' % (daymin, daymax))

    # 登録された全グループの予定を順に抽出
    alldayre   = re.compile(conf['alldayre']) # 正規表現の終日判定

    for group in conf['group']:
        webctrl.jump(URL_SEARCH % conf['serv']) # 日付を戻すためにグループ毎にトップカレンダーに移動
        #webctrl.selvalue('groupSelect', group['value'])
        webctrl.selindexvalue('groupSelect', group['name'])
        webctrl.wait() # ページ読み込み待ち
        time.sleep(WAIT_SEARCH) # グループ変更後の更新待ち
        
        # 受付可能なリストを作成
        groupOK = tuple(group['target'])

        # 指定期間をサーチ
        for week in range(int(conf['range'] / 7) + 1):
            # 2回目以降は[翌週]ボタンで進む (押下後の先頭は日曜日。1週間後でない事に注意)
            # このため、1回目と2回目で日付重複することがある。また最終日は余分なデータが追加されることがある。
            if week:
                btn = webctrl.finds('scheduleMove', webctrl.By.CLASS_NAME)
                webctrl.fclick(btn[BTN_NEXTWEEK]) # 最後のボタンが翌週
                webctrl.wait() # ページ読み込み待ち
                time.sleep(WAIT_SEARCH)

            # カレンダーのタイトルから年月日を抽出 (dt→0:年、1:月、2:日)
            title = re.split('[ 　年月日]+', webctrl.gets('dateheadInnerDateCellText', webctrl.By.CLASS_NAME)[1])
            start_dt = datetime(*[int(n) for n in title[:3]])
            g_logger.debug('cyb:week %s: %s...' % (group['name'], '/'.join(title[:3])))
            
            # グループ予定のアイテムをサーチ        
            for row in webctrl.finds('eventrow', webctrl.By.CLASS_NAME):
                col = webctrl.get('th', webctrl.By.TAG_NAME, row)
                if not col.startswith(groupOK):
                    g_logger.debug('cyb:skip %s' % (key))
                    continue # 対象外のIDはスキップ
                key = col.split('\n')[0].strip()
                
                # 有効な予定を抽出(1週間の列挙)
                col = webctrl.gets('td', webctrl.By.TAG_NAME, row)
                for i in range(len(col)):
                    day = start_dt + timedelta(days=i)
                    # 検索範囲のチェック
                    if day < daymin:  # 発生しないはずだが、念のためチェック
                        g_logger.warning('cyb:past %s %s' % (day, daymin))
                        continue
                    if day >= daymax: # 最終日を過ぎたら、週ループそのものを終える
                        g_logger.debug('cyb:break %s %s' % (day, daymax))
                        break
                        
                    # 有効な予定を抽出(1日の列挙)
                    #g_logger.debug('cyb:COL\n%s' % (col[i]))
                    sched = col[i].split('\n')
                    idx = 0
                    nch = len(sched)
                    while idx < nch: # "時間&Desc"が連続するペアを有効データとして抽出
                        # 次レコードチェック
                        tm = sched[idx]
                        idx += 1

                        # 終日予定の確認
                        if tm.startswith(tuple(conf['alldaysw'])) or alldayre.match(tm):
                            desc = tm
                            tm = conf['alltime']
                        else:
                            desc = None

                        # 時刻チェック
                        t = tm.split('-')
                        if len(t) < 2:
                            g_logger.debug('cyb:invalid schedule %s' % (tm))
                            continue # 正しい時刻が含まれない、かつ終日予定でもない (恐らく、先頭の予定メモ)
                        tbegin = calcmin(t[0])
                        tend   = calcmin(t[1])
                        if tbegin < 0 or tend < 0:
                            g_logger.debug('cyb:invalid time %s %s' % (t[0], t[1]))
                            continue # 正しい時刻が含まれない (予定メモに'-'が含まれていた?)
                        if tbegin > tend:
                            g_logger.debug('cyb:all night %s > %s' % (t[0], t[1]))
                            tend += 60 * 24 # 日またぎ
                        
                        # 終日予定でなければ、次がDESC
                        if not desc:
                            # 予定内容(=DESC)があるか確認
                            if idx >= nch:
                                g_logger.warning('cyb:empty desc1 %s' % (idx, nch))
                                # DESC情報が取れない場合は追加できない
                                break

                            # 予定内容チェック
                            desc = sched[idx]
                            idx += 1
                            if len(desc) < 1:
                                g_logger.warning('cyb:empty desc2 %s %s' % (idx - 1, tm))
                                continue # 情報が空ならスキップ

                        # 抽出した予定を共通フォーマットに変換
                        book = {
                            'ctyp': CAL_TYPE,
                            'tbgn': day + timedelta(minutes = tbegin),
                            'tend': day + timedelta(minutes = tend),
                            'summ': key,
                            'desc': desc  
                        }

                        # 同一の予定が無ければ追加
                        sbook = str(book) # 文字列化したオブジェクトで同一チェック
                        if sbook not in old:
                            old.add(sbook)
                            ret.append(book)
                            g_logger.debug('cyb:add  %s' % (sbook))
                        else:
                            g_logger.debug('cyb:skip %s' % (sbook))
                            
        # グループごとに取得した件数を表示しておく
        g_logger.info('cyb:%-4s=%d件' % (group['name'], len(ret) - pre))
        pre = len(ret)

    # 開放
    if not keep:
        webctrl.deinit()

    # 中間ファイルを保存しておく
    with open(MIDDLE_FILE, mode='w', encoding='utf-8')as f:
        yaml.safe_dump(ret, f, allow_unicode=True)

    return ret

# TODO
def set_cal(conf, merge):
    return 0

################################################################################
# コピーモードの予定取得
def get_one_cal(conf):
    keep = webctrl.driver()
    if not keep:
        webctrl.init() #  コピーモードはユーザ操作させるためdevscaleは指定しない

    # 予定検索ページを開く
    webctrl.jump(URL_SEARCH % conf['serv'])

    # ユーザ/パスワード画面に遷移した？
    if 'login' in webctrl.url():
        cb_login(conf)

    # ユーザが特定の予定ページを押すのを待つ
    print('抽出する予定を選択してください')
    while not webctrl.url().startswith(URL_DETAIL % conf['serv']):
        time.sleep(WAIT_SEARCH) # グループ変更後の更新待ち

    # 参加者が縮小表示されている可能性があるため、フル表示しておく
    tofull = webctrl.search('a', '参加者をすべて表示', webctrl.By.TAG_NAME)
    if tofull:
        webctrl.fclick(tofull)
        webctrl.wait(WAIT_SEARCH) # ページ読み込み待ち

    # 詳細ページからテキスト抽出取得
    text = webctrl.get('scheduleDataView', webctrl.By.CLASS_NAME)
    dt      = re.search(r'日時\s*(20.*)', text).group(1)
    desc    = re.search(r'予定\n(.*)',    text).group(1)
    room    = re.search(r'施設\s*(.*)',   text).group(1)
    person  = re.search(r'参加者\s*(.*)', text).group(1)

    # 扱いやすい構造に変換
    dt = re.split('[ 　年月日火水木金土]+', dt)
    roomOK = tuple(conf['group'][0]['target'])
    room = list(filter(lambda a: a.startswith(roomOK), room.split(' ')))
    personOK = tuple(conf['group'][1]['target'])
    person = list(filter(lambda a: a.startswith(personOK), person.split(' ')))

    # 日付パターン
    # 2025 年 1 月 23 日 （木） （終日）
    # 2025 年 1 月 23 日 （木） 10 時 00 分 ～ 24 時 00 分
    day  = datetime(*[int(n) for n in dt[:3]])
    if len(dt) < 13: # 終日
        tbgn, tend = conf['alltime'].split('-')
    else:
        tbgn = dt[ 5] + ':' + dt[ 7]
        tend = dt[10] + ':' + dt[12]

    ret = []
    for summ in person + room:
        # 共通フォーマットに設定
        book = {
        'ctyp': CAL_TYPE,
            'tbgn': day + timedelta(minutes = calcmin(tbgn)),
            'tend': day + timedelta(minutes = calcmin(tend)),
            'summ': summ,
            'desc': desc  
        }
        g_logger.debug('cyb:book:%s' % (book))
        ret.append(book)

    if not keep:
        webctrl.deinit()
    return ret

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
