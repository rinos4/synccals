#!/usr/bin/env python  # -*- coding: utf-8 -*-
#
# SynCals  Cybozu to AirReserve 処理用プラグイン
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# 2025.03.15 rinos4u	new

################################################################################
# import
################################################################################
import yaml
import copy
import re

from logconf import g_logger

################################################################################
# const
################################################################################
MERGE_TYPE = 'cb2ar'

CAL_CYBOZU = 'cybozu'
CAL_ARR    = 'airr'


CONF_FILE = 'config.yaml'
MIDDLE_FILE1 = 'log/mid_cb2ar1.yaml'
MIDDLE_FILE2 = 'log/mid_cb2ar2.yaml'

# 名前欄に入れられる最大文字列
MAX_DESC    = 20

################################################################################
# globals
################################################################################

################################################################################
# util funcs
################################################################################
# 全角変換
TO_ZENKAKU = str.maketrans(''.join(chr(0x20 + i) for i in range(95)), '　' + ''.join(chr(0xff01 + i) for i in range(94)))

# Airリザーブの姓名で使えない文字の補正
def normalize_text(s):
    return s.encode('shift-jis', errors='replace').decode('shift-jis').translate(TO_ZENKAKU)

################################################################################
# Plugin API
################################################################################
# 予定比較
def diff(conf, merge):
    cyb = list(filter(lambda x: x['ctyp'] == CAL_CYBOZU, merge))
    arr = list(filter(lambda x: x['ctyp'] == CAL_ARR,    merge))
    g_logger.debug('c2a:start (%d, %d)' % (len(cyb), len(arr)))

    # 同一予定を集約
    uniq = {}
    for item in cyb:
        key = '%s/%s/%s' % (item['tbgn'], item['tend'], item['desc'])
        # 同一時刻 & 同一Descなら、同じ予定とみなす
        if key not in uniq:
            uniq[key] = {'item':item, 'room':[], 'person':[]}
        if item['summ'] in conf['room']:
            uniq[key]['room'].append(item['summ'])
        elif item['summ'] in conf['person']:
            uniq[key]['person'].append(item['summ'])
        else:
            g_logger.error('c2a:invalid summ %s' % (item['summ']))
    
    # 人/事務所/ルームのマッチング
    merge2 = []
    for ui in uniq.values():
        item   = ui['item']
        room   = ui['room']
        person = ui['person']

        # 人→roomマッチング
        cat  = set()
        for p in person:
            locP = conf['person'][p]
            for r in room:
                locR = conf['room'][r]
                if locP == locR[0]:
                    cat.add('%s@%s@%s' % (p, locR[1], locP))
                    break
            else:
                g_logger.debug('c2a:Unmatch person %s %s, use %s for %s' % (p, room, conf['noroom'], item['desc']))
                cat.add('%s@%s@%s' % (p, conf['noroom'], locP))
            
        # room→人マッチング
        for r in room:
            locR = conf['room'][r]
            for p in person:
                locP = conf['person'][p]
                if locP == locR[0]:
                    cat.add('%s@%s@%s' % (p, locR[1], locP))
                    break
            else:
                g_logger.debug('c2a:Unmatch room %s %s, use %s for %s' % (r, person, conf['noperson'], item['desc']))
                cat.add('%s@%s@%s' % (conf['noperson'], locR[1], locR[0]))
        
        # 除外者チェック
        for eject in conf['eject']:
            for pp in list(filter(lambda x: x.startswith(eject), cat)):
                # 部屋無しなら無条件で除外
                if pp.split('@')[1] == conf['noroom']:
                    cat.remove(pp)
                else:
                    # 同じ会議でeject者以外が部屋を予約しているなら除外
                    endw = pp[len(eject):]
                    hit = list(filter(lambda x: x.endswith(endw) and not x.startswith(eject) , cat))
                    if len(hit):
                        g_logger.debug('c2a:eject %s %s' % (pp, hit))
                        cat.remove(pp)

        # 有効なマッチングが残っていれば登録
        if len(cat):
            merge2.append(item | {'summ': list(cat)})

    # デバッグ用に、中間の会議リストをダンプしておく
    with open(MIDDLE_FILE1, mode='w', encoding='utf-8')as f:
        yaml.safe_dump(merge2, f, allow_unicode=True)

    # Airリザーブで予約済みの情報をリストアップ (descが全角になっていることに注意)
    booked = set()
    bookmap = {}
    for item in arr:
        sep = item['summ'].split('、') # Airリザーブは「、」区切り (loc、メニュー名、room、person、予約番号)
        # Airリザーブの検索は、稀に、room/personが逆になる事がある！？
        room  =  sep[2]
        person = sep[3]
        if room not in conf['roomcheck']:
            room, person = person, room # 逆なら反転しておく

        # 比較文字列の作成。descはcompdesc設定に応じて変える
        desc = item['desc'][:MAX_DESC].rstrip() if conf['compdesc'] else ''
        ids = '%s %s %s@%s@%s %s' % (item['tbgn'], item['tend'], person, room, sep[0], desc)
        booked.add(ids)
        bookmap[ids] = item # 逆引き用テーブル
        g_logger.debug('c2a:arr-ids %s' % (ids))
    booked = tuple(booked) # startswithで探せるようにタプルに変換しておく
            
    # 差分チェックして追加/削除が必要なものだけ返す
    deldesc = tuple(conf['deldesc'])
    skipdesc = re.compile(conf['skipdesc'])
    ret = []
    for item in merge2:
        for summ in item['summ']:
            add = copy.deepcopy(item) | {'summ': summ, 'desc':normalize_text(item['desc'])}
            ids = '%s %s %s %s' % (add['tbgn'], add['tend'], add['summ'], add['desc'])
            if skipdesc.match(add['desc']):
                g_logger.debug('c2a:skip %s' % (ids))
                continue

            if add['desc'].startswith(deldesc):
                # 削除ーモード
                if ids.startswith(booked): # AirリザーブはDESC後半40文字以上が入らないので前方一致で確認
                    add['ctyp'] = '-' # 削除マーク
                    # 削除時は予約番号を追加しておく
                    for id in booked:
                        if ids.startswith(id):
                            menu = bookmap[id]['summ'].split('、')[1]
                            if menu != conf['automenu']:
                                g_logger.warning('c2a:menu type error %s != %s' % (menu, conf['automenu']))
                                continue

                            # 自動入力されたものを削除対象とする
                            g_logger.warning('c2a:del *未サポート*\n%s\n%s %s %s' % (ids, id, bookmap[id]['desc'], bookmap[id]['summ']))
                            add['summ'] = add['summ'] + '@' + bookmap[id]['summ'].split('、')[-1]
                            break
                    else:
                        # 削除対象がない(恐らく、サイボウズでない予定)
                        g_logger.warning('c2a:skip del %s' % ids)
                        continue

                    ret.append(add)
                    #g_logger.warning('c2a:削除は未サポート %s～%s %s "%s%s"' % (add['tbgn'].strftime("%m/%d %H:%M"), add['tend'].strftime("%H:%M"), add['summ'], add['desc'][:20], '…' if len(add['desc']) > 20 else ''))
                else:
                    g_logger.debug('c2a:non %s' % (ids))
            else:
                # 追加ーモード
                if ids.startswith(booked): # AirリザーブはDESC後半40文字以上が入らないので前方一致で確認
                    g_logger.debug('c2a:reg %s' % (ids))
                else:
                    add['ctyp'] = '+' # 追加マーク
                    ret.append(add)
                    g_logger.debug('c2a:add %s' % (ids))
    
    # Airリザーブで入力しやいように優先度の高い方から「1.事務所、2.追加/削除、3.日付」順にする
    ret = sorted(ret, key=lambda x: '%s%s%s' % (x['summ'].split('@')[2], x['ctyp'], x['tbgn']))

    g_logger.info("c2a:サイボウズ:%d件 → 集約:%d会議 → リザーブ差分:%d予定" % (len(cyb), len(uniq), len(ret)))
    print('─' * 70)

    # デバッグ用に、中間の予定リストをダンプしておく
    with open(MIDDLE_FILE2, mode='w', encoding='utf-8')as f:
        yaml.safe_dump(ret, f, allow_unicode=True)

    return ret

################################################################################
# main
################################################################################
if __name__ == '__main__':
    with open(CONF_FILE, 'r', encoding='utf-8') as f:
        confs = yaml.safe_load(f)

    conf = next(filter(lambda c: c['file'] == MERGE_TYPE, confs['merge']), None)
    if conf:
        with open('log/mid_merge.yaml', mode='r', encoding='utf-8')as f:
            merge = yaml.safe_load(f)

        ret = diff(conf, merge)
        print('%d件抽出' % len(ret))
