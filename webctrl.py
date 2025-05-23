#!/usr/bin/env python  # -*- coding: utf-8 -*-
#
# SynCals Webブラウザコントロール用 共通Lib
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# 2025.03.15 rinos4u	new

################################################################################
# import
################################################################################
from selenium import webdriver                                  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait         # type: ignore
from selenium.webdriver.support.ui import Select                # type: ignore
from selenium.webdriver.support import expected_conditions as EC# type: ignore
from selenium.webdriver.chrome.service import Service           # type: ignore
from selenium.webdriver.chrome.options import Options           # type: ignore
from selenium.webdriver.common.by import By                     # type: ignore
from selenium.webdriver.common.action_chains import ActionChains# type: ignore

import time
from logconf import g_logger

################################################################################
# const
################################################################################
CHROME_PROFILE_PATH = r'C:\work\dev\synccals\chrome_prof'
CHROME_PROFILE_NAME = 'Default'
CHROME_DRIVER_PATH  = 'driver/chromedriver.exe'

WAIT_CLICK  = 0.2
WAIT_AFTER  = 0.5
WAIT_SCROLL = 0.5
WAIT_PAGE   = 10

################################################################################
# globals
################################################################################
# WebDriver
g_driver = None

################################################################################
# util funcs
################################################################################
# ドライバの初期化
def init(scale = '1.0'):
    global g_driver

    # 初期化済みなら省略
    if g_driver:
        g_logger.debug('webctrl::init skip')
        return

    # 新規作成
    opt = Options()
    opt.add_argument(f'--user-data-dir={CHROME_PROFILE_PATH}')
    opt.add_argument(f"--profile-directory={CHROME_PROFILE_NAME}")
    opt.add_argument("--no-first-run")
    opt.add_argument("--no-default-browser-check")
    opt.add_argument('--no-sandbox')
    opt.add_argument('--force-device-scale-factor=' + scale)
    opt.add_experimental_option("excludeSwitches", ['enable-automation', 'enable-logging']) # seleniumのメッセージを消す
    g_driver = webdriver.Chrome(service=Service(executable_path=CHROME_DRIVER_PATH), options=opt)
    g_logger.debug('webctrl::init done')
    #g_driver.execute_script("document.body.style.zoom='100%'")
    
# ドライバの開放
def deinit():
    global g_driver

    # 開放済みなら省略
    if not g_driver:
        g_logger.debug('webctrl::deinit skip')
        return
    
    # ブラウザ終了
    g_driver.quit()
    g_driver = None
    g_logger.debug('webctrl::deinit done')

# ドライバの存在チェック用 (デバッグでdriverを直コントロールしたい場合にも利用)
def driver():
    return g_driver

# ページ更新待ち
def wait(sec = WAIT_PAGE):
    WebDriverWait(g_driver, sec).until(EC.presence_of_all_elements_located)
    time.sleep(WAIT_AFTER)

# ページ遷移&受信待ち
def jump(url):
    g_driver.get(url)
    time.sleep(WAIT_AFTER)
    wait(WAIT_PAGE)
    time.sleep(WAIT_AFTER)

# 現在のページを取得
def url():
    return g_driver.current_url

# エレメントの簡易制御 ##################################################################

# エレメントの抽出(1つ)
def find(locator_value, locator_type = By.ID, target = None):
    return (target or g_driver).find_element(locator_type, locator_value)

# エレメントの抽出(複数)
def finds(locator_value, locator_type = By.ID, target = None):
    return (target or g_driver).find_elements(locator_type, locator_value)

# 先頭エレメントのテキスト文字列を取得
def get(locator_value, locator_type = By.ID, target = None):
    # 対象エレメントを取得
    elm = find(locator_value, locator_type, target)
    if not elm:
        g_logger.error('webctrl::get %s failed' % locator_value)
        return None

    return elm.text

# 複数エレメントのテキスト抽出
def gets(locator_value, locator_type = By.ID, target = None):
    return [i.text for i in finds(locator_value, locator_type, target)]

# エレメントを文字列マッチで抽出(1つ)
def search(locator_value, start, locator_type = By.ID, target = None):
    for elm in finds(locator_value, locator_type, target):
        if elm.text.startswith(start):
            return elm
    g_logger.debug('webctrl::search %s failed' % start)
    return None

# find結果のエレメントへ移動
def fmove(elm, center = 1):
    if center:
        # 画面センタに移動 (move_to_elementだとヘッダ/フッタが邪魔してクリックできないことがある)
        g_driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elm)
    else:
        ActionChains(g_driver).move_to_element(elm).perform() #画面内に移動
    time.sleep(WAIT_SCROLL)

# find結果のエレメントをクリック
def fclick(elm, center = 1):
    fmove(elm, center)
    elm.click()
    time.sleep(WAIT_CLICK)

# find結果のエレメントにセット
def fset(elm, text, center = 1):
    fmove(elm, center)
    if elm.tag_name == 'input':
        elm.clear()
    # 新しいテキストを入力
    elm.send_keys(text)

# 検索しつつ操作 #####################################################################
# テキスト文字列を設定
def set(locator_value, text, locator_type = By.ID, target = None):
    # 対象エレメントを取得
    elm = find(locator_value, locator_type, target)
    if not elm:
        g_logger.error('webctrl::set %s failed' % locator_value)
        return None
    
    fset(elm, text)

# エレメントへ移動
def move(locator_value, locator_type = By.ID, target = None):
    elm = find(locator_value, locator_type, target)
    if not elm:
        g_logger.error('webctrl::move %s failed' % locator_value)
        return None
    fmove(elm)

# ボタンをクリック
def click(locator_value, locator_type = By.ID, target = None):
    # 対象エレメントを取得
    elm = find(locator_value, locator_type, target)
    if not elm:
        g_logger.error('webctrl::click %s failed' % locator_value)
        return None
    fclick(elm)

# Selectをインデックスで指定
def selindex(locator_value, index, locator_type = By.ID, target = None):
    elm = find(locator_value, locator_type, target)
    if not elm:
        g_logger.error('webctrl::selindex %s failed' % locator_value)
        return None

    s = Select(elm)
    if not s:
        g_logger.error('webctrl::selindex %s failed2' % locator_value)
        return None
    s.select_by_index(index)

# Selectを値で指定
def selvalue(locator_value, val, locator_type = By.ID, target = None):
    elm = find(locator_value, locator_type, target)
    if not elm:
        g_logger.error('webctrl::selvalue %s failed' % locator_value)
        return None

    s = Select(elm)
    if not s:
        g_logger.error('webctrl::selvalue %s failed2' % locator_value)
        return None
    s.select_by_value(val)

# Selectを値で指定
def selindexvalue(locator_value, val, locator_type = By.ID, target = None):
    elm = find(locator_value, locator_type, target)
    if not elm:
        g_logger.error('webctrl::selvalue %s failed' % locator_value)
        return None

    s = Select(elm)
    if not s:
        g_logger.error('webctrl::selvalue %s failed2' % locator_value)
        return None
    sel = list(filter(lambda x: x != 'undefined', elm.text.splitlines()))
    s.select_by_index(sel.index(val))

# チェックボックスのチェック確認
def isselect(locator_value, locator_type = By.ID, target = None):
    elm = find(locator_value, locator_type, target)
    if not elm:
        g_logger.error('webctrl::selvalue %s failed' % locator_value)
        return None

    return elm.is_selected()

# 複数のエレメントが見つかった場合に、例外が無くなるelmを探してクリック
def exclick(locator_value, locator_type = By.ID, target = None):
    for elm in finds(locator_value, locator_type, target):
        try:
            fclick(elm)
            return True # 例外が発生しなかったら成功
        except:
            continue
    g_logger.debug('webctrl::exclick failed "%s" %s' % (locator_type, locator_value))
    return False # １つも成功しなかった
