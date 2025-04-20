#!/usr/bin/env python  # -*- coding: utf-8 -*-
#
# SynCals  Cybozu to AirReserve 処理用プラグイン
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# 2025.03.15 rinos4u	new
# 2025.03.23 rinos4u	一致チェックにdescを含めるか設定できるように変更

################################################################################
# import
################################################################################
import yaml
import copy
import re
import unicodedata
from datetime import datetime, timedelta

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
MAX_DESC  = 20
COMP_DESC = 40 # DESCの比較長さ (姓20文字+名20文字で最大40文字まで)

# 開始/終了時刻の間隔の最小値[s]
MINIMAL_DIFF = 10 * 60 # 最低でも10分以上が必要

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
    return unicodedata.normalize('NFKC', s.encode('shift-jis', errors='replace').decode('shift-jis')).translate(TO_ZENKAKU)

################################################################################
# Plugin API
################################################################################
# 予定比較
def sync_cal(conf, merge):
    cyb = list(filter(lambda x: x['ctyp'] == CAL_CYBOZU, merge))
    arr = list(filter(lambda x: x['ctyp'] == CAL_ARR,    merge))
    g_logger.debug('c2a:start (%d, %d)' % (len(cyb), len(arr)))

    # サイボウズの同一予定を集約
    uniq = {}
    for item in cyb:
        key = '%s%s%s' % (item['tbgn'], item['tend'], item['desc'])
        # 同一時刻 & 同一descなら、同じ予定とみなす
        if key not in uniq:
            uniq[key] = {'item':item, 'room':[], 'person':[]}
        if item['summ'] in conf['room']:
            uniq[key]['room'].append(item['summ'])
        elif item['summ'] in conf['person']:
            uniq[key]['person'].append(item['summ'])
        else:
            g_logger.error('c2a:invalid summ %s' % (item['summ']))
    
    # サイボウズの事務所-ルーム-人のマッチングした新mergeを作成
    # 予定名が除外リストに入っていれば除外
    deltuple = tuple(conf['deldesc'])       # 先頭一致での削除用 (startswith用にタプル化)
    skipre   = re.compile(conf['skipdesc']) # 正規表現用

    merge2 = []
    for ui in uniq.values():
        # 無視する予定は除外
        item = ui['item']
        if item['desc'].startswith(deltuple):
            g_logger.debug('c2a:del  %s' % (item['desc']))
            continue
        if skipre.match(item['desc']):
            g_logger.debug('c2a:skip %s' % (item['desc']))
            continue

        # 人→roomマッチング
        room   = ui['room']
        person = ui['person']
        cat  = set()
        for p in person:
            locP = conf['person'][p]   # 人に紐づいた事務所
            for r in room:
                locR = conf['room'][r] # 部屋に紐づいた事務所
                if locP == locR[0]:
                    cat.add('%s@%s@%s' % (locP, locR[1], p)) # 一致あり → そのペアを追加
                    break
            else:
                # 一致無し → 部屋無し(noroom)で割り当て
                g_logger.debug('c2a:Unmatch person %s %s, use %s for %s' % (p, room, conf['noroom'], item['desc']))
                cat.add('%s@%s@%s' % (locP, conf['noroom'], p))
            
        # room→人マッチング
        for r in room:
            locR = conf['room'][r]         # 部屋に紐づいた事務所
            for p in person:
                locP = conf['person'][p]   # 人に紐づいた事務所
                if locP == locR[0]:
                    cat.add('%s@%s@%s' % (locP, locR[1], p)) # 一致あり → そのペアを追加
                    break
            else:
                # 一致無し → 人無し(noperson)で割り当て
                g_logger.debug('c2a:Unmatch room %s %s, use %s for %s' % (r, person, conf['noperson'], item['desc']))
                cat.add('%s@%s@%s' % (locR[0], locR[1], conf['noperson']))
        
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
        
        # 曜日に応じたSUMM変更処理
        for ws in conf['weeksumm']:
            if ws[0] & (1 << item['tbgn'].weekday()): # 対象曜日
                for su in list(cat):
                    # もし正規表現で置換されたらcatを入れ替える
                    rep = re.sub(ws[1], ws[2], su)
                    if rep != su:
                        g_logger.debug('c2a:replce %s %s -> %s' % (item['tbgn'], su, rep))
                        cat.remove(su)
                        cat.add(rep)

        # 有効なマッチングが1つ以上あれば登録
        if len(cat):
            merge2.append(item | {'summ': list(cat)})

    # デバッグ用に、中間の会議リストをダンプしておく
    with open(MIDDLE_FILE1, mode='w', encoding='utf-8')as f:
        yaml.safe_dump(merge2, f, allow_unicode=True)

    # Airリザーブで予約済みの情報をリストアップ
    airrmap = {} # マッピング用
    for item in arr:
        # Airリザーブのsummは「@」区切り (事務所@部屋@人@メニュー名@予約番号)
        sep = item['summ'].split('@')

        # 比較文字の作成 ※compdesc=Falseならdescは比較対象にしない
        ids = '%s %s %s@%s@%s %s' % (item['tbgn'], item['tend'], sep[0], sep[1], sep[2], item['desc'][:COMP_DESC] if conf['compdesc'] else '') # 開始時間 終了時間 事務所@部屋@人 desc
        airrmap[ids] = item # マッピングテーブル (重複しているものは後半優先)
        g_logger.debug('c2a:arr-ids %s' % (ids))
    
    # 差分チェックして追加/削除が必要なものだけ返す
    ret = []
    for item in merge2:
        # エアリザーブに登録できる文字に変換しておく
        zendesc = normalize_text(item['desc'])[:COMP_DESC]

        # 全summ(事務所@部屋@人)をチェックして、Airリザーブに予定が無ければ追加リストに入れる
        for summ in item['summ']:
            # エアリザーブは、姓[20]+名[20]に分けて格納されるが、それぞれ前後スペースが削除されることに注意
            se = zendesc[        :MAX_DESC    ]
            na = zendesc[MAX_DESC:MAX_DESC * 2]

            # サイボウズは開始時刻=終了時刻を設定できるが、エアリザーブはエラーとなるため最小期間を加える
            if (item['tend'] - item['tbgn']).seconds < MINIMAL_DIFF:
                item['tend'] = item['tbgn'] + timedelta(seconds=MINIMAL_DIFF)
                g_logger.info('arr:Change end time to %s' % (item['tend']))

            ids = '%s %s %s %s' % (item['tbgn'], item['tend'], summ, se.strip('　') + na.strip('　'))

            # 既にAirリザーブに登録済？
            if ids in airrmap:
                # 登録済 (追加はautomenuで入れたもの以外も同一判定)
                del airrmap[ids] # 後続処理の削除対象にならないように外しておく
                g_logger.debug('c2a:match %s' % (ids))
            else:
                # 未登録
                ret.append(copy.deepcopy(item) | {'ctyp': '+', 'summ': summ, 'desc':zendesc})
                g_logger.debug('c2a:add list %s' % (ids))

    # エアリザーブにしか無い予定は削除リストとして追加
    for ids, item in airrmap.items():
        # 自動ツールが入力したものだけを対象にする
        if item['summ'].split('@')[3] == conf['automenu']: # 自分で追加したのと同じメニュー
            ret.append(copy.deepcopy(item) | {'ctyp': '-'})
            g_logger.debug('c2a:del list %s' % (ids))
        else:
            g_logger.debug('c2a:skip list %s' % (ids))
    
    # Airリザーブの入力を最適化するため、優先度「1.事務所、2.追加/削除、3.日付」順でソートしておく
    ret = sorted(ret, key=lambda x: '%s%s%s' % (x['summ'].split('@')[0], x['ctyp'], x['tbgn']))

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

        ret = sync_cal(conf, merge)
        print('%d件抽出' % len(ret))
