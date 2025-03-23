#!/usr/bin/env python  # -*- coding: utf-8 -*-
#
# SynCals Webブラウザコントロール用 共通Lib
# Copyright (c) 2025 rinos4u, released under the MIT open source license.
#
# 2025.03.15 rinos4u	new

# インストールモジュール
#pip install selenium
#pip install yaml

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

import time
from logging import config, getLogger

################################################################################
# const
################################################################################
CHROME_PROFILE_PATH = r'C:\work\dev\synccals\chrome_prof'
CHROME_PROFILE_NAME = 'Default'
CHROME_DRIVER_PATH  = 'driver/chromedriver.exe'

WAIT_CLICK  = 0.5
WAIT_AFTER  = 1
WAIT_PAGE   = 10

# ログ用ファイル
LOG_CONF	= 'log.conf'
LOG_KEY		= 'root'

################################################################################
# globals
################################################################################
# WebDriver
g_driver = None

# ロガー
config.fileConfig(LOG_CONF)
g_logger = getLogger(LOG_KEY)

################################################################################
# util funcs
################################################################################
# ドライバの初期化
def init():
    global g_driver
    opt = Options()
    opt.add_argument(f'--user-data-dir={CHROME_PROFILE_PATH}')
    opt.add_argument(f"--profile-directory={CHROME_PROFILE_NAME}")
    opt.add_argument("--no-first-run")
    opt.add_argument("--no-default-browser-check")
    opt.add_argument('--no-sandbox')
    g_driver = webdriver.Chrome(service=Service(executable_path=CHROME_DRIVER_PATH), options=opt)
    g_logger.debug('webctrl::init driver')
    
# ドライバの開放
def deinit():
    global g_driver
    g_driver.quit()
    g_driver = None
    g_logger.debug('webctrl::deinit driver')

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
    wait(WAIT_PAGE)

# 現在のページを取得
def url():
    return g_driver.current_url

# エレメントの簡易制御 ##################################################################

# エレメントの抽出(複数)
def find(locator_value, locator_type = By.ID, target = None):
    return (target or g_driver).find_elements(locator_type, locator_value)

# 複数エレメントのテキスト抽出
def gets(locator_value, locator_type = By.ID, target = None):
    return [i.text for i in find(locator_value, locator_type, target)]

# 先頭エレメントのテキスト文字列を取得
def get(locator_value, locator_type = By.ID, target = None):
    # 対象エレメントを取得
    elm = (target or g_driver).find_element(locator_type, locator_value)
    if not elm:
        g_logger.error('webctrl::get %s failed' % locator_value)
        return None

    return elm.text

# テキスト文字列を設定
def set(locator_value, text, locator_type = By.ID, target = None):
    # 対象エレメントを取得
    elm = (target or g_driver).find_element(locator_type, locator_value)
    if not elm:
        g_logger.error('webctrl::set %s failed' % locator_value)
        return None

    # テキストをクリア
    if elm.tag_name == 'input':
        elm.clear()

    # 新しいテキストを入力
    elm.send_keys(text)

# find結果のエレメントをクリック
def fclick(elm):
    elm.click()
    time.sleep(WAIT_CLICK)

# find結果のエレメントにセット
def fset(elm, text):
    if elm.tag_name == 'input':
        elm.clear()
    # 新しいテキストを入力
    elm.send_keys(text)

# 検索しつつ操作 #####################################################################
# ボタンをクリック
def click(locator_value, locator_type = By.ID, target = None):
    # 対象エレメントを取得
    elm = (target or g_driver).find_element(locator_type, locator_value)
    if not elm:
        g_logger.error('webctrl::click %s failed' % locator_value)
        return None
    fclick(elm)

# Selectをインデックスで指定
def selindex(locator_value, index, locator_type = By.ID, target = None):
    elm = (target or g_driver).find_element(locator_type, locator_value)
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
    elm = (target or g_driver).find_element(locator_type, locator_value)
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
    elm = (target or g_driver).find_element(locator_type, locator_value)
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
    elm = (target or g_driver).find_element(locator_type, locator_value)
    if not elm:
        g_logger.error('webctrl::selvalue %s failed' % locator_value)
        return None

    return elm.is_selected()
