# -*- coding: utf-8 -*-
# v2.0.0 勝率雷達 WinRadar (PySide6 GUI Dashboard)
import sys
import re
import time
import json
import math
import os
import shutil
import logging
import concurrent.futures
import threading
from datetime import datetime, timedelta, timezone

# 解決 curl_cffi 0.13.0 版本的 SSRF 參數 Bug 與 Windows 中文路徑 SSL 憑證 Bug
try:
    import curl_cffi.requests.utils
    import curl_cffi.requests.session

    original_set_curl_options = curl_cffi.requests.utils.set_curl_options

    def get_ascii_ca_bundle():
        try:
            import certifi
            source = certifi.where()
            
            candidates = []
            try:
                candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".certifi"))
            except Exception:
                pass
            if sys.platform.startswith("win"):
                candidates.append("C:\\Users\\Public\\.certifi")
            temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
            if temp_dir:
                candidates.append(os.path.join(temp_dir, ".certifi"))
            try:
                candidates.append(os.path.join(os.path.expanduser("~"), ".certifi"))
            except Exception:
                pass
            candidates.append("/tmp/.certifi")
            
            valid_target = None
            for d in candidates:
                try:
                    d.encode("ascii")
                    os.makedirs(d, exist_ok=True)
                    test_file = os.path.join(d, "write_test.tmp")
                    with open(test_file, "w") as f:
                        f.write("ok")
                    os.remove(test_file)
                    valid_target = os.path.join(d, "cacert.pem")
                    break
                except Exception:
                    continue
            
            if not valid_target:
                valid_target = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".certifi", "cacert.pem")
                os.makedirs(os.path.dirname(valid_target), exist_ok=True)
                
            if (not os.path.exists(valid_target)) or os.path.getsize(valid_target) != os.path.getsize(source):
                shutil.copyfile(source, valid_target)
            return valid_target
        except Exception:
            return None

    ASCII_CA_BUNDLE = get_ascii_ca_bundle()
    if ASCII_CA_BUNDLE:
        os.environ["CURL_CA_BUNDLE"] = ASCII_CA_BUNDLE
        os.environ["SSL_CERT_FILE"] = ASCII_CA_BUNDLE

    def patched_set_curl_options(*args, **kwargs):
        if 'allow_redirects' in kwargs:
            if kwargs['allow_redirects'] == 'safe':
                kwargs['allow_redirects'] = True
        else:
            args = list(args)
            for i, val in enumerate(args):
                if val == 'safe':
                    args[i] = True
        if os.environ.get("AIGG_DISABLE_SSL_VERIFY", "").lower() in {"1", "true", "yes"}:
            kwargs['verify_list'] = [False, False]
        else:
            ascii_ca = ASCII_CA_BUNDLE or get_ascii_ca_bundle()
            if ascii_ca:
                verify_list = list(kwargs.get('verify_list') or [None, None])
                while len(verify_list) < 2:
                    verify_list.append(None)
                base_verify, verify = verify_list[0], verify_list[1]
                if verify is not False:
                    if isinstance(verify, str):
                        try:
                            verify.encode("ascii")
                        except UnicodeEncodeError:
                            verify = ascii_ca
                    elif verify in (None, True):
                        verify = None
                    if isinstance(base_verify, str):
                        try:
                            base_verify.encode("ascii")
                        except UnicodeEncodeError:
                            base_verify = ascii_ca
                    elif base_verify in (None, True, False):
                        base_verify = ascii_ca
                    kwargs['verify_list'] = [base_verify, verify]
        return original_set_curl_options(*args, **kwargs)

    curl_cffi.requests.utils.set_curl_options = patched_set_curl_options
    curl_cffi.requests.session.set_curl_options = patched_set_curl_options
except Exception:
    pass

from scrapling import Fetcher
from PySide6 import QtCore
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QTextEdit, QProgressBar, QSplitter, QHeaderView,
    QMessageBox, QFrame, QGridLayout, QComboBox, QCheckBox,
    QDialog, QMenu, QTextBrowser, QProgressDialog, QInputDialog, QListWidget
)

# ----------------- 靜態配置與對應 -----------------
AI_STOCK_MAP = {
    # AI 晶片與 CoWoS 核心
    "2330": {"name": "台積電", "theme": "AI晶片代工霸主"},
    "3443": {"name": "創意", "theme": "ASIC設計 / IP開發"},
    "2454": {"name": "聯發科", "theme": "AI ASIC / 手機端AI晶片"},
    "3035": {"name": "智原", "theme": "ASIC IP / 設計服務"},
    "2449": {"name": "京元電", "theme": "AI晶片測試大廠"},
    "6510": {"name": "精測", "theme": "半導體高速測試介面卡"},
    "2368": {"name": "金像電", "theme": "AI伺服器高階PCB板"},
    "2383": {"name": "台光電", "theme": "AI伺服器高速CCL銅箔基板"},
    "3037": {"name": "欣興", "theme": "AI伺服器 ABF載板"},
    "8046": {"name": "南電", "theme": "ABF載板製造"},
    "3189": {"name": "景碩", "theme": "ABF載板生產"},
    
    # CoWoS 設備概念股
    "2467": {"name": "志聖", "theme": "CoWoS設備龍頭 / 烤箱與載板"},
    "3583": {"name": "辛耘", "theme": "CoWoS先進封裝濕製程設備"},
    "6187": {"name": "萬潤", "theme": "CoWoS先進封裝點膠設備"},
    "3131": {"name": "弘塑", "theme": "CoWoS先進封裝濕製程設備"},
    "3680": {"name": "家登", "theme": "先進製程 EUV 載具 / 傳送盒"},
    "6640": {"name": "均華", "theme": "CoWoS先進封裝設備"},
    "5443": {"name": "均豪", "theme": "先進封裝與半導體設備整合"},
    "1597": {"name": "直得", "theme": "精密線性滑軌 / 精密模組"},
    "4540": {"name": "全球傳動", "theme": "精密滾珠螺桿 / 傳動元件"},
    
    # AI 散熱
    "3017": {"name": "奇鋐", "theme": "AI伺服器液冷與風冷散熱霸主"},
    "3324": {"name": "雙鴻", "theme": "AI伺服器水冷板與散熱系統"},
    "3653": {"name": "健策", "theme": "AI晶片高階均熱片"},
    "6125": {"name": "廣運", "theme": "AI伺服器散熱機構與液冷系統"},
    "3013": {"name": "晟銘電", "theme": "AI伺服器機殼與散熱機櫃"},
    "8210": {"name": "勤誠", "theme": "AI伺服器高階機殼設計"},
    
    # AI 伺服器
    "2317": {"name": "鴻海", "theme": "AI伺服器 (GB200) 最大整機代工"},
    "2382": {"name": "廣達", "theme": "AI伺服器 (GB200) 核心 CSP 代工"},
    "3231": {"name": "緯創", "theme": "AI伺服器基板代工"},
    "6669": {"name": "緯穎", "theme": "雲端高階AI伺服器代工"},
    "2356": {"name": "英業達", "theme": "AI伺服器與主機板設計"},
    "2376": {"name": "技嘉", "theme": "AI伺服器與顯示卡品牌大廠"},
    "2377": {"name": "微星", "theme": "AI伺服器與電競主機設計"},
    "6117": {"name": "迎廣", "theme": "AI伺服器機櫃與機殼"},
    "2327": {"name": "國巨", "theme": "AI伺服器高階被動元件"},
    
    # 矽光子 CPO
    "3163": {"name": "波若威", "theme": "矽光子與高速光收發器"},
    "3450": {"name": "聯鈞", "theme": "光電半導體封裝與光模組"},
    "4979": {"name": "華星光", "theme": "高速光通訊主動元件"},
    "4908": {"name": "前鼎", "theme": "高速光纖收發模組元件"},
    "3363": {"name": "上詮", "theme": "矽光子 CPO 共同封裝光學概念"},
    "3081": {"name": "聯亞", "theme": "光通訊雷射磊晶晶片"},
    "6411": {"name": "晶焱", "theme": "高速傳輸靜電保護 (ESD) 元件"},
    "6223": {"name": "旺矽", "theme": "高階探針卡與晶圓測試"},
    
    # 機器人概念
    "2049": {"name": "上銀", "theme": "機器人滾珠螺桿與線性滑軌龍頭"},
    "4583": {"name": "台灣精銳", "theme": "精密減速機與自動化機械元件"},
    "1590": {"name": "亞德客-KY", "theme": "精密氣動元件設計製造"},
    "4562": {"name": "穎漢", "theme": "全自動化機器人彎管設備"},
    "1536": {"name": "和大", "theme": "機器人高精度齒輪與傳動軸"},
    "4510": {"name": "高鋒", "theme": "自動化工具機與加工中心機"},
    "6606": {"name": "建德工業", "theme": "高精度平面磨床與精密加工"},
    
    # 低軌衛星 (Starlink)
    "3491": {"name": "昇達科", "theme": "低軌衛星微波與毫米波元件最大受惠"},
    "2314": {"name": "台揚", "theme": "低軌衛星地面接收站與衛星通訊"},
    "6285": {"name": "啟碁", "theme": "低軌衛星與 5G 移動通訊終端"},
    "5388": {"name": "中磊", "theme": "低軌衛星接收設備與寬頻網通"},
    "3704": {"name": "合勤控", "theme": "網通設備與寬頻傳輸"},
    "3596": {"name": "智易", "theme": "衛星網通與高頻寬接取設備"},
    "3447": {"name": "展達", "theme": "衛星與網通訊硬體設計製造"},
    "8071": {"name": "能率網通", "theme": "衛星通訊材料與通路營運"},
    
    # AI 電力概念
    "1519": {"name": "華城", "theme": "AI資料中心高壓超高壓變壓器"},
    "1503": {"name": "士電", "theme": "重電設備與配電控制盤"},
    "1513": {"name": "中興電", "theme": "高壓氣體絕緣開關與綠能電網"},
    "1514": {"name": "亞力", "theme": "高低壓配電盤與變壓器"},
    "2371": {"name": "大同", "theme": "大型電力變壓器與電能管理系統"},
    "4572": {"name": "駐龍", "theme": "航太與電力工程結構件"},
    "6451": {"name": "訊芯-KY", "theme": "CPO封裝 / 高速光模組封裝 / 鴻海集團"}
}

# 產業鏈分群映射 — 用於計算族群共振分數
SECTOR_MAP = {
    "AI晶片與CoWoS核心": ["2330", "3443", "2454", "3035", "2449", "6510", "2368", "2383", "3037", "8046", "3189"],
    "CoWoS設備概念": ["2467", "3583", "6187", "3131", "3680", "6640", "5443", "1597", "4540"],
    "AI散熱/液冷": ["3017", "3324", "3653", "6125", "3013", "8210"],
    "AI伺服器整機": ["2317", "2382", "3231", "6669", "2356", "2376", "2377", "6117", "2327"],
    "矽光子CPO": ["3163", "3450", "4979", "4908", "3363", "3081", "6411", "6223", "6451"],
    "機器人概念": ["2049", "4583", "1590", "4540", "1597", "4562", "1536", "4510", "6606"],
    "低軌衛星Starlink": ["3491", "2314", "6285", "5388", "3704", "3596", "3447", "8071"],
    "AI電力概念": ["1519", "1503", "1513", "1514", "2371", "4572"]
}

ETF_THEME_MAP = {
    "0050": {"name": "元大台灣50", "theme": "被動股票型 / 市值代表"},
    "006208": {"name": "富邦台50", "theme": "被動股票型 / 市值代表 / 低費用"},
    "0051": {"name": "元大中型100", "theme": "被動股票型 / 中型股代表"},
    "00692": {"name": "富邦公司治理", "theme": "被動股票型 / ESG / 公司治理"},
    "0056": {"name": "元大高股息", "theme": "被動股票型 / 經典高股息"},
    "00878": {"name": "國泰永續高股息", "theme": "被動股票型 / ESG高股息 / 季配息"},
    "00919": {"name": "群益台灣精選高息", "theme": "被動股票型 / 精選高股息 / 季配息"},
    "00929": {"name": "復華台灣科技優息", "theme": "被動股票型 / 科技高股息 / 月配息"},
    "00713": {"name": "元大台灣高息低波", "theme": "被動股票型 / 高息低波動 / 季配息"},
    "00940": {"name": "元大台灣價值高息", "theme": "被動股票型 / 巴菲特價值高息 / 月配息"},
    "00915": {"name": "凱基優選高股息30", "theme": "被動股票型 / 高息低波多因子 / 季配息"},
    "0052": {"name": "富邦科技", "theme": "被動股票型 / 科技半導體比重高"},
    "00881": {"name": "國泰台灣5G+", "theme": "被動股票型 / 5G通訊半導體"},
    "00891": {"name": "中信關鍵半導體", "theme": "被動股票型 / 台灣半導體產業鏈"},
    "00757": {"name": "統一FANG+", "theme": "被動股票型 / 美股科技巨頭"},
    "00980A": {"name": "主動野村臺灣優選", "theme": "主動股票型 / 野村台灣優質選股"},
    "00981A": {"name": "主動統一台股增長", "theme": "主動股票型 / 統一台股主動選股"},
    "00982A": {"name": "主動群益台灣強棒", "theme": "主動股票型 / 群益強棒選股"},
    "00984A": {"name": "主動安聯台灣高息", "theme": "主動股票型 / 安聯台灣高息選股"},
    "00990A": {"name": "主動元大 AI 新經濟", "theme": "主動股票型 / 元大 AI 新經濟主題選股"},
    "00400A": {"name": "主動國泰動能高息", "theme": "主動股票型 / 國泰動能因子高息選股"},
    "00403A": {"name": "主動統一升級50", "theme": "主動股票型 / 統一升級50主動選股"},
    "00679B": {"name": "元大美債20年", "theme": "債券型 / 美國長天期公債 / 避險標的"},
    "00751B": {"name": "元大AAA至A級公司債", "theme": "債券型 / 高信用評等投資級公司債"},
    "00720B": {"name": "元大投資級公司債", "theme": "債券型 / 投資級公司債"}
}

# ===================== 美股靜態配置 =====================
US_STOCK_MAP = {
    # 科技龍頭/M7
    "AAPL": {"name": "Apple", "theme": "科技龍頭 / M7 / 行動終端與邊緣AI"},
    "MSFT": {"name": "Microsoft", "theme": "科技龍頭 / M7 / 雲端與 OpenAI 合作"},
    "GOOGL": {"name": "Alphabet", "theme": "科技龍頭 / M7 / 搜尋引擎與 Gemini AI"},
    "AMZN": {"name": "Amazon", "theme": "科技龍頭 / M7 / AWS 雲端運算"},
    "META": {"name": "Meta Platforms", "theme": "科技龍頭 / M7 / 社交與 Llama 開源LLM"},
    "NVDA": {"name": "NVIDIA", "theme": "科技龍頭 / M7 / AI 晶片霸主"},
    "TSLA": {"name": "Tesla", "theme": "科技龍頭 / M7 / 機器人、自駕與 Physical AI"},
    
    # AI 超級核心
    "AVGO": {"name": "Broadcom", "theme": "AI 超級核心 / 網路與 ASIC"},
    "TSM": {"name": "TSMC ADR", "theme": "AI 超級核心 / 先進製程晶圓代工霸主"},
    "AMD": {"name": "Advanced Micro Devices", "theme": "AI 超級核心 / AI 晶片與 CPU"},
    "MU": {"name": "Micron Technology", "theme": "AI 超級核心 / HBM 高頻寬記憶體"},
    "ASML": {"name": "ASML", "theme": "AI 超級核心 / EUV 光刻機設備霸主"},
    "ARM": {"name": "Arm Holdings", "theme": "AI 超級核心 / ARM 架構 IP 授權"},
    "MRVL": {"name": "Marvell Technology", "theme": "AI 超級核心 / 資料中心光通訊晶片"},
    "ANET": {"name": "Arista Networks", "theme": "AI 超級核心 / 高階資料中心交換機"},
    "QCOM": {"name": "Qualcomm", "theme": "AI 超級核心 / 行動與車端 AI 晶片"},
    
    # AI 雲端與平台
    "ORCL": {"name": "Oracle", "theme": "AI 雲端與資料庫基礎設施"},
    "NFLX": {"name": "Netflix", "theme": "影音串流龍頭與訂閱平台"},
    "PLTR": {"name": "Palantir", "theme": "AI 數據 analysis 與企業軟體平台"},
    
    # 機器人與自動化
    "ABB": {"name": "ABB", "theme": "機器人與自動化 / 工業機器人自動化"},
    "SYM": {"name": "Symbotic", "theme": "機器人與自動化 / AI 倉儲物流系統"},
    "ROK": {"name": "Rockwell Automation", "theme": "機器人與自動化 / 工業自動化龍頭"},
    "ISRG": {"name": "Intuitive Surgical", "theme": "機器人與自動化 / 達文西手術機器人"},
    
    # 低軌衛星與太空
    "ASTS": {"name": "AST SpaceMobile", "theme": "低軌衛星與太空 / 直接連網技術"},
    "RKLB": {"name": "Rocket Lab", "theme": "低軌衛星與太空 / 小型火箭發射"},
    "IRDM": {"name": "Iridium Communications", "theme": "低軌衛星與太空 / 全球衛星通訊"},
    "GSAT": {"name": "Globalstar", "theme": "低軌衛星與太空 / 行動通訊"},
    "LUNR": {"name": "Intuitive Machines", "theme": "低軌衛星與太空 / 登月艙太空運輸"},
    
    # AI 電力與基建
    "VRT": {"name": "Vertiv Holdings", "theme": "AI 電力與基建 / 液冷與熱管理大廠"},
    "ETN": {"name": "Eaton", "theme": "AI 電力與基建 / 電能管理與UPS"},
    "CEG": {"name": "Constellation Energy", "theme": "AI 電力與基建 / 核能清潔能量供應"},
    "VST": {"name": "Vistra", "theme": "AI 電力與基建 / 電力公用事業"},
    "NRG": {"name": "NRG Energy", "theme": "AI 電力與基建 / 電力供應與零售"},

    # 🔥 Serenity 核心與重倉
    "AAOI": {"name": "Applied Optoelectronics", "theme": "Serenity 核心愛股 / 光模組龍頭"},
    "SIVEOF": {"name": "Sivers Semiconductors", "theme": "Serenity 核心愛股 / CPO雷射技術"},
    "AXTI": {"name": "AXT Inc.", "theme": "Serenity 核心愛股 / InP 磷化銦基板大廠"},
    "NBIS": {"name": "Nebius Group", "theme": "Serenity 最新重倉 / AI GPU 基礎設施雲端"},
    "TSEM": {"name": "Tower Semiconductor", "theme": "Serenity 最新重倉 / 特殊製程晶圓代工"},
    
    # 🌈 CPO光子第二梯隊
    "LITE": {"name": "Lumentum Holdings", "theme": "CPO光子第二梯隊 / 光通訊與雷射"},
    "COHR": {"name": "Coherent", "theme": "CPO光子第二梯隊 / 光模組材料與雷射"},
    "FN": {"name": "Fabrinet", "theme": "CPO光子第二梯隊 / 高階光收發精密製造"},
    "AMKR": {"name": "Amkor Technology", "theme": "CPO光子第二梯隊 / 先進封裝大廠"},
    "CLS": {"name": "Celestica", "theme": "CPO光子第二梯隊 / AI 伺服器硬體製造"},
    "VICR": {"name": "Vicor Corporation", "theme": "CPO光子第二梯隊 / 高階電源模組"},
    
    # 🤖 Serenity AI基建與注意
    "JBL": {"name": "Jabil", "theme": "Serenity AI基建與注意 / AI伺服器組裝與電子製造"},
    "GFS": {"name": "GlobalFoundries", "theme": "Serenity AI基建與注意 / 晶圓代工"},
    "NOK": {"name": "Nokia", "theme": "Serenity AI基建與注意 / 光通訊網通設備"},
    "ASX": {"name": "日月光投控 ADR", "theme": "Serenity AI基建與注意 / 全球半導體封測龍頭"},
    "RDDT": {"name": "Reddit", "theme": "Serenity AI基建與注意 / AI數據庫授權與社群平台"},
    "XFAB": {"name": "X-Fab Silicon Foundries", "theme": "Serenity AI基建與注意 / 矽光子+SiC代工"},
    "AEHR": {"name": "Aehr Test Systems", "theme": "Serenity AI基建與注意 / AI晶片老化測試"},
    "GLW": {"name": "Corning", "theme": "Serenity AI基建與注意 / 光纖材料與基建"}
}

US_SECTOR_MAP = {
    "科技龍頭/M7": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
    "AI 超級核心": ["AVGO", "TSM", "AMD", "MU", "ASML", "ARM", "MRVL", "ANET", "QCOM"],
    "AI 雲端與平台": ["ORCL", "NFLX", "PLTR"],
    "機器人與自動化": ["TSLA", "ABB", "SYM", "ROK", "ISRG"],
    "低軌衛星與太空": ["ASTS", "RKLB", "IRDM", "GSAT", "LUNR"],
    "AI 電力與基建": ["VRT", "ETN", "CEG", "VST", "NRG"],
    "Serenity 核心與重倉": ["AAOI", "SIVEOF", "AXTI", "NBIS", "TSEM"],
    "CPO光子第二梯隊": ["LITE", "COHR", "FN", "AMKR", "CLS", "VICR"],
    "Serenity AI基建與注意": ["JBL", "GFS", "NOK", "ASX", "RDDT", "XFAB", "AEHR", "GLW"]
}

GLOBAL_OTC_SET = {"6187", "3131", "3583", "00679B", "00751B", "00720B"}
GLOBAL_TSE_SET = set()
GLOBAL_SET_LOCK = threading.Lock()

# ----------------- 快取管理系統 -----------------
# 確保打包 EXE 後快取資料夾固定建立在執行檔旁邊
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_DIR = os.path.join(BASE_DIR, "data")
HISTORY_CACHE_FILE = os.path.join(CACHE_DIR, "history_cache.json")
INST_CACHE_FILE = os.path.join(CACHE_DIR, "institutional_cache.json")
LAST_SCAN_CACHE_FILE = os.path.join(CACHE_DIR, "last_scan_result.json")
FUNDAMENTALS_CACHE_FILE = os.path.join(CACHE_DIR, "fundamentals_cache.json")

# 美股快取檔案
US_UNIVERSE_CACHE_FILE = os.path.join(CACHE_DIR, "us_stock_universe.json")
US_HISTORY_CACHE_FILE = os.path.join(CACHE_DIR, "us_history_cache.json")
GLOBAL_US_HISTORY_CACHE = {}
GLOBAL_US_REALTIME_CACHE = {}
GLOBAL_FUNDAMENTALS_CACHE = {}

GLOBAL_HISTORY_CACHE = {}
GLOBAL_INST_CACHE = {}
GLOBAL_REALTIME_CACHE = {}
GLOBAL_TWSE_BLOCKED = False
GLOBAL_TAIEX_20D_RETURN = None

USER_UNIVERSE_FILE = os.path.join(CACHE_DIR, "custom_universe.json")
DISABLED_STOCKS = set()
DISABLED_US_STOCKS = set()

DEFAULT_AI_STOCK_MAP = {k: v.copy() for k, v in AI_STOCK_MAP.items()}
DEFAULT_SECTOR_MAP = {k: list(v) for k, v in SECTOR_MAP.items()}
DEFAULT_US_STOCK_MAP = {k: v.copy() for k, v in US_STOCK_MAP.items()}
DEFAULT_US_SECTOR_MAP = {k: list(v) for k, v in US_SECTOR_MAP.items()}

def load_user_universe():
    global AI_STOCK_MAP, SECTOR_MAP, DISABLED_STOCKS
    global US_STOCK_MAP, US_SECTOR_MAP, DISABLED_US_STOCKS
    if os.path.exists(USER_UNIVERSE_FILE):
        try:
            with open(USER_UNIVERSE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 載入台股
            new_stock_map = {}
            new_sector_map = {}
            for group_name, stocks in data.get("groups", {}).items():
                new_sector_map[group_name] = []
                for code, info in stocks.items():
                    new_stock_map[code] = info
                    new_sector_map[group_name].append(code)
            if new_stock_map:
                AI_STOCK_MAP.clear()
                AI_STOCK_MAP.update(new_stock_map)
                SECTOR_MAP.clear()
                SECTOR_MAP.update(new_sector_map)
                DISABLED_STOCKS.clear()
                DISABLED_STOCKS.update(data.get("disabled_stocks", []))
                
            # 載入美股
            new_us_stock_map = {}
            new_us_sector_map = {}
            for group_name, stocks in data.get("us_groups", {}).items():
                new_us_sector_map[group_name] = []
                for ticker, info in stocks.items():
                    new_us_stock_map[ticker] = info
                    new_us_sector_map[group_name].append(ticker)
            if new_us_stock_map:
                US_STOCK_MAP.clear()
                US_STOCK_MAP.update(new_us_stock_map)
                US_SECTOR_MAP.clear()
                US_SECTOR_MAP.update(new_us_sector_map)
                DISABLED_US_STOCKS.clear()
                DISABLED_US_STOCKS.update(data.get("disabled_us_stocks", []))
                
            # 自動升級合併台股新預設
            tw_updated = False
            for code, info in DEFAULT_AI_STOCK_MAP.items():
                if code not in AI_STOCK_MAP:
                    AI_STOCK_MAP[code] = info.copy()
                    tw_updated = True
                for group_name, codes in DEFAULT_SECTOR_MAP.items():
                    if code in codes:
                        if group_name not in SECTOR_MAP:
                            SECTOR_MAP[group_name] = []
                            tw_updated = True
                        if code not in SECTOR_MAP[group_name]:
                            SECTOR_MAP[group_name].append(code)
                            tw_updated = True
            
            # 自動升級合併美股新預設
            us_updated = False
            for ticker, info in DEFAULT_US_STOCK_MAP.items():
                if ticker not in US_STOCK_MAP:
                    US_STOCK_MAP[ticker] = info.copy()
                    us_updated = True
                for group_name, tickers in DEFAULT_US_SECTOR_MAP.items():
                    if ticker in tickers:
                        if group_name not in US_SECTOR_MAP:
                            US_SECTOR_MAP[group_name] = []
                            us_updated = True
                        if ticker not in US_SECTOR_MAP[group_name]:
                            US_SECTOR_MAP[group_name].append(ticker)
                            us_updated = True
            
            if tw_updated or us_updated:
                logging.info("偵測到系統預設監控池升級，自動合併新個股...")
                save_user_universe()
        except Exception as e:
            logging.error(f"讀取自訂監控池失敗: {e}")

def save_user_universe():
    try:
        data = {
            "disabled_stocks": list(DISABLED_STOCKS),
            "groups": {},
            "disabled_us_stocks": list(DISABLED_US_STOCKS),
            "us_groups": {}
        }
        for group, codes in SECTOR_MAP.items():
            data["groups"][group] = {}
            for code in codes:
                if code in AI_STOCK_MAP:
                    data["groups"][group][code] = AI_STOCK_MAP[code]
                    
        for group, tickers in US_SECTOR_MAP.items():
            data["us_groups"][group] = {}
            for ticker in tickers:
                if ticker in US_STOCK_MAP:
                    data["us_groups"][group][ticker] = US_STOCK_MAP[ticker]
                    
        os.makedirs(os.path.dirname(USER_UNIVERSE_FILE), exist_ok=True)
        with open(USER_UNIVERSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存自訂監控池失敗: {e}")

if os.path.exists(USER_UNIVERSE_FILE):
    load_user_universe()
else:
    save_user_universe()

ETF_DIVIDEND_DATABASE = {
    "00915": {"score": 20.0, "fill_score": 6.0, "stability_score": 4.0, "growth_score": 2.0},
    "00878": {"score": 19.0, "fill_score": 6.0, "stability_score": 4.0, "growth_score": 1.5},
    "00919": {"score": 18.0, "fill_score": 5.0, "stability_score": 4.0, "growth_score": 1.5},
    "00713": {"score": 18.0, "fill_score": 6.0, "stability_score": 4.0, "growth_score": 1.5},
    "0056": {"score": 17.0, "fill_score": 5.0, "stability_score": 4.0, "growth_score": 1.5},
    "00929": {"score": 17.0, "fill_score": 5.0, "stability_score": 4.0, "growth_score": 1.5},
    "00940": {"score": 15.0, "fill_score": 4.0, "stability_score": 3.5, "growth_score": 1.5},
    "00984A": {"score": 16.0, "fill_score": 5.0, "stability_score": 4.0, "growth_score": 1.5},
    "00400A": {"score": 16.0, "fill_score": 5.0, "stability_score": 4.0, "growth_score": 1.5},
    "00751B": {"score": 16.0, "fill_score": 6.0, "stability_score": 4.0, "growth_score": 1.5},
    "00679B": {"score": 15.0, "fill_score": 5.5, "stability_score": 4.0, "growth_score": 1.5},
    "00720B": {"score": 15.0, "fill_score": 5.5, "stability_score": 4.0, "growth_score": 1.5},
    "00692": {"score": 14.0, "fill_score": 6.0, "stability_score": 3.5, "growth_score": 1.5},
    "0050": {"score": 13.0, "fill_score": 6.0, "stability_score": 3.0, "growth_score": 1.5},
    "006208": {"score": 13.0, "fill_score": 6.0, "stability_score": 3.0, "growth_score": 1.5},
    "0051": {"score": 13.0, "fill_score": 5.5, "stability_score": 3.0, "growth_score": 1.5},
    "00891": {"score": 13.0, "fill_score": 5.0, "stability_score": 3.5, "growth_score": 1.5},
    "00881": {"score": 12.0, "fill_score": 5.0, "stability_score": 3.0, "growth_score": 1.5},
    "0052": {"score": 11.0, "fill_score": 6.0, "stability_score": 2.5, "growth_score": 1.0},
    "00757": {"score": 8.0, "fill_score": 6.0, "stability_score": 1.0, "growth_score": 0.5},
}

def init_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)

def load_json_cache(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"讀取快取失敗 {file_path}: {e}")
        return {}

def save_json_cache(file_path, data):
    try:
        init_cache_dir()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"寫入快取失敗 {file_path}: {e}")

def load_all_caches():
    global GLOBAL_HISTORY_CACHE, GLOBAL_INST_CACHE, GLOBAL_US_HISTORY_CACHE, GLOBAL_FUNDAMENTALS_CACHE
    GLOBAL_HISTORY_CACHE = load_json_cache(HISTORY_CACHE_FILE)
    GLOBAL_INST_CACHE = load_json_cache(INST_CACHE_FILE)
    GLOBAL_US_HISTORY_CACHE = load_json_cache(US_HISTORY_CACHE_FILE)
    GLOBAL_FUNDAMENTALS_CACHE = load_json_cache(FUNDAMENTALS_CACHE_FILE)

def save_all_caches():
    save_json_cache(HISTORY_CACHE_FILE, GLOBAL_HISTORY_CACHE)
    save_json_cache(INST_CACHE_FILE, GLOBAL_INST_CACHE)
    save_json_cache(US_HISTORY_CACHE_FILE, GLOBAL_US_HISTORY_CACHE)
    save_json_cache(FUNDAMENTALS_CACHE_FILE, GLOBAL_FUNDAMENTALS_CACHE)

def get_date_diff_days(date_str1, date_str2):
    try:
        d1 = datetime.strptime(str(date_str1), "%Y%m%d")
        d2 = datetime.strptime(str(date_str2), "%Y%m%d")
        return abs((d1 - d2).days)
    except Exception:
        return 999

# ----------------- 基礎工具函數 -----------------
def clean_html_to_text(response):
    try:
        raw_html = response.body.decode('utf-8', errors='ignore')
        raw_html = re.sub(r'<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>', '', raw_html, flags=re.I)
        raw_html = re.sub(r'<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>', '', raw_html, flags=re.I)
        pure_text = re.sub(r'<[^>]+>', ' ', raw_html)
        return re.sub(r'\s+', ' ', pure_text).strip()
    except Exception:
        return ""

def calculate_std(values):
    if not values or len(values) < 2:
        return 1.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5 if variance > 0 else 1.0

def calculate_hurst(prices):
    if len(prices) < 30:
        return 0.5
    windows = [20, 30]
    h_list = []
    log_returns = []
    for i in range(len(prices) - 1):
        if prices[i+1] > 0 and prices[i] > 0:
            log_returns.append(math.log(prices[i] / prices[i+1]))
            
    for w in windows:
        sub_ret = log_returns[:w]
        n = len(sub_ret)
        if n < 10:
            continue
        mean = sum(sub_ret) / n
        deviations = []
        cum_sum = 0.0
        for r in sub_ret:
            cum_sum += (r - mean)
            deviations.append(cum_sum)
        R = max(deviations) - min(deviations) if deviations else 1.0
        variance = sum((r - mean) ** 2 for r in sub_ret) / n
        S = variance ** 0.5 if variance > 0 else 1.0
        if S > 0 and R > 0:
            rs = R / S
            h = math.log(rs) / math.log(n) if rs > 1 else 0.5
            h_list.append(h)
    return sum(h_list) / len(h_list) if h_list else 0.5

def check_trend_alignment(prices, is_reverse=False):
    """
    趨勢過濾器: 20MA > 60MA > 120MA
    is_reverse=True 代表 prices 序列是由舊到新 (美股)
    is_reverse=False 代表 prices 序列是由新到舊 (台股)
    """
    n = len(prices)
    if n < 20:
        return False
    
    if is_reverse:
        ma20 = sum(prices[-20:]) / 20
        ma60 = sum(prices[-min(n, 60):]) / min(n, 60)
        ma120 = sum(prices[-min(n, 120):]) / min(n, 120)
    else:
        ma20 = sum(prices[:20]) / 20
        ma60 = sum(prices[:min(n, 60)]) / min(n, 60)
        ma120 = sum(prices[:min(n, 120)]) / min(n, 120)
        
    return ma20 > ma60 > ma120

def calculate_price_slope(prices):
    n = min(len(prices), 10)
    if n < 5: return 0.0
    y = prices[:n][::-1]
    x = list(range(n))
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(i*i for i in x)
    sum_xy = sum(i*y[i] for i in x)
    denominator = n * sum_xx - sum_x * sum_x
    if denominator == 0: return 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    mean_y = sum_y / n
    return (slope / mean_y) * 100 if mean_y > 0 else 0.0

def calculate_volatility_contraction(prices):
    if len(prices) < 20: return 1.0
    p_5 = prices[:5]
    p_20 = prices[:20]
    cv_5 = calculate_std(p_5) / (sum(p_5)/5) if sum(p_5) > 0 else 0.0
    cv_20 = calculate_std(p_20) / (sum(p_20)/20) if sum(p_20) > 0 else 1.0
    return cv_5 / cv_20 if cv_20 > 0 else 1.0

def is_market_open():
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz_tw)
    if now_tw.weekday() >= 5: return False, now_tw, 270.0
    if now_tw.hour < 9: return False, now_tw, 270.0
    if now_tw.hour >= 14 or (now_tw.hour == 13 and now_tw.minute >= 30): return False, now_tw, 270.0
    elapsed = (now_tw.hour - 9) * 60 + now_tw.minute
    return True, now_tw, float(elapsed if elapsed > 0 else 1.0)

def is_us_market_open():
    """ET 9:30-16:00 = TWN 21:30/22:30 ~ 04:00/05:00 (夏令/冬令)"""
    # 用 UTC offset 計算，不依賴 pytz
    tz_et = timezone(timedelta(hours=-4))  # EDT (夏令)
    now_et = datetime.now(tz_et)
    if now_et.weekday() >= 5: return False, now_et, 390.0
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    if now_et < market_open or now_et >= market_close:
        return False, now_et, 390.0
    elapsed = (now_et - market_open).total_seconds() / 60.0
    return True, now_et, float(elapsed if elapsed > 0 else 1.0)

# ----------------- 資料獲取端點 -----------------
def fetch_us_stock_universe(use_cache=True):
    """
    獲取美股宇宙，包含 S&P 500 + 市值前 1500 大的活躍股
    """
    if use_cache and os.path.exists(US_UNIVERSE_CACHE_FILE):
        try:
            mtime = os.path.getmtime(US_UNIVERSE_CACHE_FILE)
            if time.time() - mtime < 7 * 86400:
                with open(US_UNIVERSE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cached_tickers = json.load(f)
                    if cached_tickers and len(cached_tickers) > 100:
                        logging.info(f"從快取載入 {len(cached_tickers)} 檔美股宇宙")
                        return cached_tickers
        except Exception as e:
            logging.warning(f"讀取美股宇宙快取失敗: {e}")

    logging.info("開始下載美股宇宙清單...")
    tickers = set()
    import ssl
    import urllib.request
    ssl_context = ssl._create_unverified_context()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 1. 抓取 Wikipedia S&P 500
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ssl_context, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
            matches = re.findall(r'href="https://www\.(?:nasdaq|nyse)\.com/[^"]*(?:stocks/|quote/XNYS:)([A-Za-z0-9\.-]+)"', html)
            if not matches:
                matches = re.findall(r'<td><a[^>]+class="external text"[^>]*>([A-Z\.-]+)</a></td>', html)
            for t in matches:
                tickers.add(t.replace('.', '-').strip())
            logging.info(f"Wikipedia S&P 500 取得 {len(matches)} 檔股票")
    except Exception as e:
        logging.warning(f"Wikipedia S&P 500 下載失敗: {e}")

    # 2. 抓取 GitHub 上的市值排名前 1500 檔美股
    try:
        url_csv = "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv"
        req = urllib.request.Request(url_csv, headers=headers)
        with urllib.request.urlopen(req, context=ssl_context, timeout=15) as response:
            csv_data = response.read().decode('utf-8', errors='ignore')
            lines = csv_data.splitlines()
            cnt = 0
            for line in lines[1:]:
                parts = line.split(',')
                if parts:
                    symbol = parts[0].strip().replace('"', '')
                    if re.match(r'^[A-Z\-]+$', symbol):
                        tickers.add(symbol)
                        cnt += 1
                        if cnt >= 1500:
                            break
            logging.info(f"GitHub US Stock Tickers 取得前 {cnt} 檔股票")
    except Exception as e:
        logging.warning(f"GitHub US Stock Tickers 下載失敗: {e}")

    # 3. 確保預設的 AI 10 檔晶片股在宇宙中
    for t in US_STOCK_MAP.keys():
        tickers.add(t)

    # 確保全部轉成大寫並過濾不合法字元
    final_tickers = sorted(list({t.upper().strip() for t in tickers if t and re.match(r'^[A-Za-z0-9\.-]+$', t)}))
    
    if len(final_tickers) > 100:
        try:
            os.makedirs(os.path.dirname(US_UNIVERSE_CACHE_FILE), exist_ok=True)
            with open(US_UNIVERSE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(final_tickers, f, ensure_ascii=False, indent=2)
            logging.info(f"美股宇宙已快取至 {US_UNIVERSE_CACHE_FILE}")
        except Exception as e:
            logging.warning(f"儲存美股宇宙快取失敗: {e}")
    else:
        final_tickers = sorted(list(set(US_STOCK_MAP.keys()) | {"AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NFLX", "JPM", "V", "DIS"}))

    return final_tickers

def fetch_us_market_regime():
    """
    獲取美股大盤狀態 (S&P 500, 道瓊, 納指, 費指)
    """
    import urllib.request
    import ssl
    import urllib.parse
    
    ssl_context = ssl._create_unverified_context()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    tickers = {"sp500": "^GSPC", "dow": "^DJI", "nasdaq": "^IXIC", "sox": "^SOX"}
    result = {}
    
    for key, symbol in tickers.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=7d&interval=1d"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                result_node = data.get("chart", {}).get("result", [])
                if result_node:
                    meta = result_node[0].get("meta", {})
                    meta_price = meta.get("regularMarketPrice")
                    
                    # 提取歷史收盤價，使用倒數第一與第二個有效值作為最新價與前收價
                    closes = result_node[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                    
                    # 盤中或剛收盤修補：若最新一筆 close 為 None，用 meta_price 進行修補
                    if closes and closes[-1] is None and meta_price is not None:
                        closes = list(closes)
                        closes[-1] = meta_price
                        
                    valid_closes = [c for c in closes if c is not None]
                    
                    if len(valid_closes) >= 2:
                        price = valid_closes[-1]
                        prev_close = valid_closes[-2]
                    elif len(valid_closes) == 1:
                        price = valid_closes[-1]
                        prev_close = meta.get("chartPreviousClose") or price
                    else:
                        price = meta_price if meta_price is not None else 0.0
                        prev_close = meta.get("chartPreviousClose") or price

                    if prev_close > 0.0:
                        change_val = price - prev_close
                        change_pct = (change_val / prev_close) * 100
                    else:
                        change_val = 0.0
                        change_pct = 0.0

                    result[key] = {
                        "price": price if price else 0.0, 
                        "change_pct": change_pct,
                        "change_val": change_val
                    }
                else:
                    result[key] = {"price": 0.0, "change_pct": 0.0, "change_val": 0.0}
        except Exception as e:
            logging.warning(f"獲取美股大盤指數 {symbol} 失敗: {e}")
            result[key] = {"price": 0.0, "change_pct": 0.0, "change_val": 0.0}
            
    sp_pct = result.get("sp500", {}).get("change_pct", 0.0)
    nasdaq_pct = result.get("nasdaq", {}).get("change_pct", 0.0)
    
    if sp_pct > 0.5 and nasdaq_pct > 0.5:
        status = "強勢 (美股多頭 Regime)"
        multiplier = 1.15
    elif sp_pct < -0.5 and nasdaq_pct < -0.5:
        status = "弱勢 (美股空頭 Regime)"
        multiplier = 0.85
    else:
        status = "中性 (美股震盪 Regime)"
        multiplier = 1.00
        
    result["status"] = status
    result["multiplier"] = multiplier
    result["change_pct"] = sp_pct
    return result

def fetch_us_bulk_quotes(tickers):
    """
    使用 Yahoo v7/finance/spark 獲取批量美股即時報價。
    這解決了 query1.finance.yahoo.com v7/finance/quote 401 Unauthorized 的問題。
    支援二分拆分重試機制，防止個別代碼異常導致整批 400 Bad Request。
    """
    import urllib.request
    import ssl
    import json
    import urllib.parse
    import time
    
    ssl_context = ssl._create_unverified_context()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # 清洗輸入 tickers，轉為大寫並去重，移除空值
    cleaned_tickers = []
    seen = set()
    for t in tickers:
        if not t:
            continue
        t_upper = t.strip().upper()
        if t_upper not in seen:
            seen.add(t_upper)
            cleaned_tickers.append(t_upper)
            
    batch_size = 50
    result = {}
    
    def fetch_batch_with_retry(batch):
        if not batch:
            return {}
        
        symbols_str = ",".join(batch)
        url = f"https://query2.finance.yahoo.com/v7/finance/spark?symbols={urllib.parse.quote(symbols_str)}&range=1d&interval=5m"
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ssl_context, timeout=12) as response:
                data = json.loads(response.read().decode('utf-8'))
                results = data.get("spark", {}).get("result", [])
                batch_result = {}
                for r in results:
                    symbol = r.get("symbol")
                    if not symbol:
                        continue
                    symbol_upper = symbol.upper()
                    response_node = r.get("response", [{}])[0]
                    meta = response_node.get("meta", {})
                    
                    price = meta.get("regularMarketPrice")
                    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                    
                    if price is None:
                        closes = response_node.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                        closes_cleaned = [c for c in closes if c is not None]
                        if closes_cleaned:
                            price = closes_cleaned[-1]
                            
                    if price and prev_close:
                        change_pct = (price - prev_close) / prev_close * 100
                    else:
                        change_pct = 0.0
                        
                    batch_result[symbol_upper] = {
                        "name": meta.get("longName") or meta.get("shortName") or symbol,
                        "close": price if price else 0.0,
                        "open": meta.get("regularMarketPrice", price if price else 0.0),
                        "high": meta.get("regularMarketDayHigh", price if price else 0.0),
                        "low": meta.get("regularMarketDayLow", price if price else 0.0),
                        "yest_close": prev_close if prev_close else 0.0,
                        "volume": meta.get("regularMarketVolume", 0),
                        "change_pct": change_pct,
                        "market_cap": meta.get("marketCap", 0)
                    }
                return batch_result
        except Exception as e:
            # 檢查是否為 HTTP 400 (Bad Request)
            is_http_400 = False
            if hasattr(e, "code") and e.code == 400:
                is_http_400 = True
            elif "400" in str(e):
                is_http_400 = True
                
            if is_http_400 and len(batch) > 1:
                mid = len(batch) // 2
                left_batch = batch[:mid]
                right_batch = batch[mid:]
                logging.info(f"⚡ 偵測到美股報價含有無效代碼，啟動二分拆分重試: {len(left_batch)} 檔 / {len(right_batch)} 檔")
                time.sleep(0.1)
                left_res = fetch_batch_with_retry(left_batch)
                time.sleep(0.1)
                right_res = fetch_batch_with_retry(right_batch)
                left_res.update(right_res)
                return left_res
            else:
                logging.warning(f"批量獲取 {batch} 美股報價失敗: {e}")
                return {}

    for i in range(0, len(cleaned_tickers), batch_size):
        batch = cleaned_tickers[i:i+batch_size]
        batch_quotes = fetch_batch_with_retry(batch)
        result.update(batch_quotes)
        time.sleep(0.35)
        
    return result

def fetch_us_historical_closes(ticker):
    """
    獲取單檔美股最近 6 個月的歷史 K 線 (從新到舊)
    """
    import urllib.request
    import ssl
    import json
    import urllib.parse
    
    ssl_context = ssl._create_unverified_context()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?range=6mo&interval=1d"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ssl_context, timeout=12) as response:
            data = json.loads(response.read().decode('utf-8'))
            result_node = data.get("chart", {}).get("result", [])
            if result_node:
                chart_data = result_node[0]
                timestamps = chart_data.get("timestamp", [])
                indicators = chart_data.get("indicators", {})
                quote = indicators.get("quote", [{}])[0]
                closes = list(quote.get("close", []) or [])
                volumes = list(quote.get("volume", []) or [])
                opens = list(quote.get("open", []) or [])
                highs = list(quote.get("high", []) or [])
                lows = list(quote.get("low", []) or [])
                
                # 盤中或剛收盤修補：若最新一筆為 None，使用 meta 數據進行修補
                meta = chart_data.get("meta", {})
                meta_price = meta.get("regularMarketPrice")
                meta_vol = meta.get("regularMarketVolume")
                
                if closes and closes[-1] is None and meta_price is not None:
                    closes[-1] = meta_price
                    if volumes and volumes[-1] is None and meta_vol is not None:
                        volumes[-1] = meta_vol
                    if opens and opens[-1] is None: opens[-1] = meta_price
                    if highs and highs[-1] is None: highs[-1] = meta_price
                    if lows and lows[-1] is None: lows[-1] = meta_price
                
                cleaned = []
                for idx, t in enumerate(timestamps):
                    if idx < len(closes) and closes[idx] is not None and volumes[idx] is not None:
                        cleaned.append({
                            "timestamp": t,
                            "close": closes[idx],
                            "volume": volumes[idx],
                            "open": opens[idx] if idx < len(opens) else closes[idx],
                            "high": highs[idx] if idx < len(highs) else closes[idx],
                            "low": lows[idx] if idx < len(lows) else closes[idx]
                        })
                return sorted(cleaned, key=lambda x: x["timestamp"], reverse=True)
    except Exception as e:
        logging.warning(f"獲取 {ticker} 歷史 K 線失敗: {e}")
    return []

def fetch_us_volume_flow(historical_data):
    """
    從歷史 K 線中萃取量價動能指標，替代台股法人買賣超
    """
    if len(historical_data) < 5:
        return {"buy_pressure_days": 0, "vol_trend_ratio": 1.0}
        
    buy_pressure_days = 0
    for i in range(len(historical_data) - 1):
        today = historical_data[i]
        yesterday = historical_data[i+1]
        
        price_up = today["close"] > yesterday["close"]
        vol_up = today["volume"] > yesterday["volume"]
        
        if price_up and vol_up:
            buy_pressure_days += 1
        else:
            break
            
    vol_5 = sum(x["volume"] for x in historical_data[:5]) / 5
    vol_20_len = min(len(historical_data), 20)
    vol_20 = sum(x["volume"] for x in historical_data[:vol_20_len]) / vol_20_len
    
    vol_trend_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0
    
    return {
        "buy_pressure_days": buy_pressure_days,
        "vol_trend_ratio": vol_trend_ratio
    }

def fetch_mops_financials(code):
    url = f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={code}"
    roe = 0.0
    try:
        response = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status == 200:
            pure_text = clean_html_to_text(response)
            roe_match = re.search(r'(?:ROE|股東權益報酬率)\s*([0-9\.\-]+)\s*%', pure_text)
            if roe_match:
                roe = float(roe_match.group(1))
    except Exception:
        pass
    if roe == 0.0:
        roe = 19.5 if code in AI_STOCK_MAP else 9.5
    return {"roe": roe}

def fetch_clean_fundamentals(code, is_us=False):
    """
    獲取個股基本面數據並計算基本面評分 (Fundamental Score)。
    支援台股與美股，優先使用 Yahoo Finance API。
    """
    global GLOBAL_FUNDAMENTALS_CACHE
    date_str = datetime.now().strftime("%Y%m%d")
    
    # 1. 嘗試從記憶體快取讀取
    if code in GLOBAL_FUNDAMENTALS_CACHE:
        cached = GLOBAL_FUNDAMENTALS_CACHE[code]
        c_date = cached.get("update_date", "19700101")
        if get_date_diff_days(c_date, date_str) <= 7:
            return cached

    # 初始化預設值
    data = {
        "revenue_yoy": 0.0,
        "gross_margin": 0.0,
        "prev_gross_margin": 0.0,
        "gross_margin_increased": False,
        "latest_eps": 0.0,
        "eps_yoy": 0.0,
        "fundamental_score": 50.0,  # 預設中位數
        "update_date": date_str
    }

    # 2. 爬取數據
    fetched = False
    suffixes = [""] if is_us else [".TW", ".TWO"]
    
    def safe_pct(val):
        try:
            return float(str(val).replace('%', '').replace(',', '').strip())
        except (ValueError, AttributeError):
            return 0.0
            
    for suffix in suffixes:
        try:
            symbol = f"{code}{suffix}"
            url = f"https://query1.finance.yahoo.com/v11/finance/quoteSummary/{symbol}?modules=financialData,defaultKeyStatistics,incomeStatementHistoryQuarterly"
            res = Fetcher.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if res.status == 200:
                api_data = json.loads(res.body.decode('utf-8', errors='ignore'))
                result = api_data.get("quoteSummary", {}).get("result", [{}])[0]
                
                fin = result.get("financialData", {})
                # 營收年增率
                if fin.get("revenueGrowth", {}).get("raw") is not None:
                    data["revenue_yoy"] = round(fin["revenueGrowth"]["raw"] * 100, 2)
                
                # 最新毛利率
                if fin.get("grossMargins", {}).get("raw") is not None:
                    data["gross_margin"] = round(fin["grossMargins"]["raw"] * 100, 2)
                
                # 最新 EPS
                if fin.get("earningsPerShare", {}).get("raw") is not None:
                    data["latest_eps"] = round(fin["earningsPerShare"]["raw"], 2)
                
                # 獲取過去數季的毛利率以比較是否提升
                inc_stmt = result.get("incomeStatementHistoryQuarterly", {}).get("incomeStatementHistory", [])
                if len(inc_stmt) >= 2:
                    try:
                        q1_rev = inc_stmt[0].get("totalRevenue", {}).get("raw", 0.0)
                        q1_gp = inc_stmt[0].get("grossProfit", {}).get("raw", 0.0)
                        q2_rev = inc_stmt[1].get("totalRevenue", {}).get("raw", 0.0)
                        q2_gp = inc_stmt[1].get("grossProfit", {}).get("raw", 0.0)
                        
                        if q1_rev > 0 and q2_rev > 0:
                            gm1 = q1_gp / q1_rev
                            gm2 = q2_gp / q2_rev
                            data["gross_margin"] = round(gm1 * 100, 2)
                            data["prev_gross_margin"] = round(gm2 * 100, 2)
                            data["gross_margin_increased"] = (gm1 > gm2)
                    except Exception:
                        pass
                
                # 預估或最新 EPS 年增
                if fin.get("earningsGrowth", {}).get("raw") is not None:
                    data["eps_yoy"] = round(fin["earningsGrowth"]["raw"] * 100, 2)
                else:
                    data["eps_yoy"] = data["revenue_yoy"]  # 降級估計
                
                fetched = True
                break
        except Exception:
            continue
            
    # 降級後備：網頁爬取
    if not fetched:
        if is_us:
            # 美股 HTML 爬取後備
            try:
                url_stats = f"https://finance.yahoo.com/quote/{code}/key-statistics"
                res = Fetcher.get(url_stats, timeout=10)
                if res.status == 200:
                    pure = clean_html_to_text(res)
                    rev_yoy_match = re.search(r'Quarterly\s+Revenue\s+Growth\s*\(yoy\)\s*([\-\d\.,]+)%?', pure)
                    eps_yoy_match = re.search(r'Quarterly\s+Earnings\s+Growth\s*\(yoy\)\s*([\-\d\.,]+)%?', pure)
                    eps_match = re.search(r'Diluted\s+EPS\s*\(ttm\)\s*([\-\d\.,]+)', pure)
                    
                    if rev_yoy_match:
                        data["revenue_yoy"] = safe_pct(rev_yoy_match.group(1))
                    if eps_yoy_match:
                        data["eps_yoy"] = safe_pct(eps_yoy_match.group(1))
                    if eps_match:
                        data["latest_eps"] = safe_pct(eps_match.group(1))
                        
                    data["gross_margin_increased"] = True
                    fetched = True
            except Exception as e:
                logging.error(f"美股基本面網頁爬取失敗 {code}: {e}")
        else:
            # 台股 HTML 爬取後備
            try:
                url_rev = f"https://tw.stock.yahoo.com/quote/{code}.TW/revenue"
                res = Fetcher.get(url_rev, timeout=8)
                if res.status == 200:
                    pure = clean_html_to_text(res)
                    match = re.search(r'(\d{4}/\d{2})\s+([\d,]+)\s+([\-\d\.%]+)\s+([\d,]+)\s+([\-\d\.%]+)', pure)
                    if match and len(match.groups()) >= 5:
                        data["revenue_yoy"] = safe_pct(match.group(5))
                url_eps = f"https://tw.stock.yahoo.com/quote/{code}.TW/eps"
                res = Fetcher.get(url_eps, timeout=8)
                if res.status == 200:
                    pure = clean_html_to_text(res)
                    match = re.search(r'(\d{4}\s+Q\d)\s+([\-\d\.]+)\s+([\-\d\.%]+)\s+([\-\d\.%]+)', pure)
                    if match and len(match.groups()) >= 4:
                        data["latest_eps"] = safe_pct(match.group(2))
                        data["eps_yoy"] = safe_pct(match.group(4))
                data["gross_margin_increased"] = True
                fetched = True
            except Exception:
                pass

    # 3. 計算評分
    score = 0.0
    rev_yoy = data["revenue_yoy"]
    if rev_yoy > 20.0:
        score += 40.0
        extra = min(10.0, ((rev_yoy - 20.0) // 10) * 2)
        score += extra
    elif rev_yoy > 0.0:
        score += (rev_yoy / 20.0) * 40.0
        
    if data["gross_margin_increased"]:
        score += 30.0
        
    eps_y = data["eps_yoy"]
    if eps_y > 0.0:
        score += 20.0
        if eps_y > 100.0:
            score += 10.0
    elif data["latest_eps"] > 0.0:
        score += 15.0
        
    data["fundamental_score"] = round(min(100.0, max(0.0, score)), 1)
    
    # 4. 寫入快取
    GLOBAL_FUNDAMENTALS_CACHE[code] = data
    return data

def fetch_yahoo_institutional_flow(code):
    suffix = ".TWO" if code in GLOBAL_OTC_SET else ".TW"
    url = f"https://tw.stock.yahoo.com/quote/{code}{suffix}/institutional-trading"
    flow_data = {"foreign_buys": [], "trust_buys": [], "dealer_buys": [], "volumes": [], "changes": [], "dates": []}
    try:
        res = Fetcher.get(url, timeout=10)
        if res.status == 200:
            pure = clean_html_to_text(res)
            pattern = r'(\d{4}/\d{2}/\d{2})\s+([\-\d,]+)\s+([\-\d,]+)\s+([\-\d,]+)\s+([\-\d,]+)\s+([\-\d\.%]+)\s+([\-\d\.%]+)\s+([\d,]+)'
            rows = re.findall(pattern, pure)
            for row in rows:
                try:
                    f_val = int(row[1].replace(',', ''))
                    t_val = int(row[2].replace(',', ''))
                    d_val = int(row[3].replace(',', ''))
                    v_val = int(row[7].replace(',', ''))
                    c_val = float(row[6].replace('%', '').strip())
                    
                    flow_data["dates"].append(row[0])
                    flow_data["foreign_buys"].append(f_val)
                    flow_data["trust_buys"].append(t_val)
                    flow_data["dealer_buys"].append(d_val)
                    flow_data["volumes"].append(v_val)
                    flow_data["changes"].append(c_val)
                except ValueError:
                    continue
    except Exception:
        pass
    return flow_data

def fetch_blave_broker_concentration(code, date_str=None):
    """
    從 Blave API 獲取台股分點買賣超數據，並計算主力分點籌碼集中度 (Broker Concentration)
    """
    api_key = os.environ.get("blave_api_key")
    secret_key = os.environ.get("blave_secret_key")
    if not api_key or not secret_key:
        return None
        
    try:
        if not date_str:
            date_str = datetime.today().strftime('%Y-%m-%d')
        else:
            if len(date_str) == 8 and date_str.isdigit():
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
        url = f"https://api.blave.org/studio/market/twstock/broker/stock/{code}?date={date_str}"
        headers = {
            "api-key": api_key,
            "secret-key": secret_key,
            "User-Agent": "Mozilla/5.0"
        }
        res = Fetcher.get(url, headers=headers, timeout=10)
        if res and res.status == 200:
            import json
            res_data = json.loads(res.text).get("data", [])
            if not res_data:
                return 0.0
                
            net_flows = []
            total_vol = 0
            for row in res_data:
                buy = row.get("buy", 0)
                sell = row.get("sell", 0)
                net = buy - sell
                net_flows.append(net)
                total_vol += (buy + sell)
                
            if total_vol == 0:
                return 0.0
                
            buy_flows = sorted([n for n in net_flows if n > 0], reverse=True)
            sell_flows = sorted([abs(n) for n in net_flows if n < 0], reverse=True)
            
            top_buy = sum(buy_flows[:15])
            top_sell = sum(sell_flows[:15])
            
            concentration = (top_buy - top_sell) / (total_vol / 2.0) * 100
            return round(concentration, 2)
    except Exception as e:
        logging.warning(f"獲取 Blave 分點買賣超異常: {e}")
    return None

def fetch_historical_closes(code, realtime_price):
    closes = []
    last_timestamp = None
    suffixes = [".TW", ".TWO"]
    if code in GLOBAL_OTC_SET: suffixes = [".TWO", ".TW"]
    elif code in GLOBAL_TSE_SET: suffixes = [".TW", ".TWO"]

    for suffix in suffixes:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}{suffix}?range=6mo&interval=1d"
        raw_text = None
        try:
            res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if res.status == 200:
                raw_text = res.body.decode('utf-8', errors='ignore')
        except Exception as e:
            logging.warning(f"Fetcher 獲取 K 線失敗 ({code}{suffix}): {e}，將使用 urllib.request 重試...")

        if not raw_text:
            try:
                import urllib.request
                import ssl
                ssl_context = ssl._create_unverified_context()
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                    if response.status == 200:
                        raw_text = response.read().decode('utf-8', errors='ignore')
            except Exception as e:
                logging.error(f"urllib 獲取 K 線亦失敗 ({code}{suffix}): {e}")

        if raw_text:
            try:
                json_data = json.loads(raw_text)
                if "chart" in json_data and json_data["chart"]["result"]:
                    result = json_data["chart"]["result"][0]
                    quote = result["indicators"]["quote"][0]
                    raw_closes = quote.get("close", [])
                    closes = [c for c in raw_closes if c is not None]
                    timestamps = result.get("timestamp", [])
                    if closes:
                        if timestamps:
                            last_timestamp = timestamps[-1]
                        if suffix == ".TWO":
                            with GLOBAL_SET_LOCK: GLOBAL_OTC_SET.add(code)
                        else:
                            with GLOBAL_SET_LOCK: GLOBAL_TSE_SET.add(code)
                        break
            except Exception as e:
                logging.error(f"解析 K 線 JSON 失敗 ({code}{suffix}): {e}")
    if not closes: return None
    
    if realtime_price > 0:
        is_today = False
        if last_timestamp is not None:
            try:
                tz_taiwan = timezone(timedelta(hours=8))
                today_str = datetime.now(tz_taiwan).strftime("%Y%m%d")
                last_k_date = datetime.fromtimestamp(last_timestamp, tz=tz_taiwan).strftime("%Y%m%d")
                if last_k_date == today_str:
                    is_today = True
            except Exception:
                pass
        
        if is_today:
            closes[-1] = realtime_price
        else:
            closes.append(realtime_price)
            
    return closes

def fetch_twse_realtime_data(code):
    global GLOBAL_OTC_SET, GLOBAL_TSE_SET, GLOBAL_TWSE_BLOCKED
    if GLOBAL_TWSE_BLOCKED:
        return {"price": 0.0, "yest_close": 0.0, "open": 0.0, "high": 0.0, "low": 0.0, "today_vol": 0, "bid_vol": 1.0, "ask_vol": 1.0, "amplitude": 0.0, "name": ""}
        
    markets = ["otc", "tse"] if code in GLOBAL_OTC_SET else (["tse", "otc"] if code in GLOBAL_TSE_SET else ["tse", "otc"])
    data = {"price": 0.0, "yest_close": 0.0, "open": 0.0, "high": 0.0, "low": 0.0, "today_vol": 0, "bid_vol": 1.0, "ask_vol": 1.0, "amplitude": 0.0, "name": ""}
    
    for market in markets:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={market}_{code}.tw"
        try:
            res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if res.status == 200:
                raw_text = res.body.decode('utf-8', errors='ignore')
                json_data = json.loads(raw_text)
                if "msgArray" in json_data and len(json_data["msgArray"]) > 0:
                    info = json_data["msgArray"][0]
                    y_val = info.get("y", "")
                    o_val = info.get("o", "")
                    h_val = info.get("h", "")
                    if (y_val and y_val != "-") or (o_val and o_val != "-") or (h_val and h_val != "-"):
                        if market == "otc":
                            with GLOBAL_SET_LOCK: GLOBAL_OTC_SET.add(code)
                        else:
                            with GLOBAL_SET_LOCK: GLOBAL_TSE_SET.add(code)
                        
                        data["price"] = float(info.get("z", "0").replace(",", "")) if info.get("z") and info.get("z") != "-" else 0.0
                        data["yest_close"] = float(info.get("y", "0").replace(",", "")) if info.get("y") and info.get("y") != "-" else 0.0
                        data["open"] = float(info.get("o", "0").replace(",", "")) if info.get("o") and info.get("o") != "-" else 0.0
                        data["high"] = float(info.get("h", "0").replace(",", "")) if info.get("h") and info.get("h") != "-" else 0.0
                        data["low"] = float(info.get("l", "0").replace(",", "")) if info.get("l") and info.get("l") != "-" else 0.0
                        data["today_vol"] = int(info.get("v", "0").replace(",", "")) if info.get("v") else 0
                        data["name"] = info.get("n", "").strip()
                        
                        if data["price"] == 0.0:
                            b_prices = info.get("b", "").split("_")
                            a_prices = info.get("a", "").split("_")
                            b_val = float(b_prices[0].replace(",", "")) if b_prices and b_prices[0] and b_prices[0] != "-" else 0.0
                            a_val = float(a_prices[0].replace(",", "")) if a_prices and a_prices[0] and a_prices[0] != "-" else 0.0
                            if b_val > 0 and a_val > 0: data["price"] = (b_val + a_val) / 2.0
                            elif b_val > 0: data["price"] = b_val
                            elif a_val > 0: data["price"] = a_val
                            elif data["open"] > 0: data["price"] = data["open"]
                            elif data["yest_close"] > 0: data["price"] = data["yest_close"]
                            
                        if data["yest_close"] > 0 and data["high"] > 0 and data["low"] > 0:
                            data["amplitude"] = (data["high"] - data["low"]) / data["yest_close"] * 100
                            
                        bids = info.get("g", "")
                        asks = info.get("f", "")
                        bid_sum = sum(int(x) for x in bids.split("_") if x.isdigit())
                        ask_sum = sum(int(x) for x in asks.split("_") if x.isdigit())
                        data["bid_vol"] = float(bid_sum) if bid_sum > 0 else 1.0
                        data["ask_vol"] = float(ask_sum) if ask_sum > 0 else 1.0
                        break
        except Exception:
            GLOBAL_TWSE_BLOCKED = True
            pass
    return data

def fetch_twse_bulk_realtime(codes):
    global GLOBAL_OTC_SET, GLOBAL_TSE_SET, GLOBAL_TWSE_BLOCKED
    if GLOBAL_TWSE_BLOCKED:
        return {}
    ex_ch_list = []
    for code in codes:
        if code in GLOBAL_OTC_SET:
            ex_ch_list.append(f"otc_{code}.tw")
        elif code in GLOBAL_TSE_SET:
            ex_ch_list.append(f"tse_{code}.tw")
        else:
            if code.startswith('00'):
                ex_ch_list.append(f"otc_{code}.tw" if code.endswith('B') else f"tse_{code}.tw")
            else:
                ex_ch_list.append(f"tse_{code}.tw")
                
    batch_size = 40
    results = {}
    for i in range(0, len(ex_ch_list), batch_size):
        if GLOBAL_TWSE_BLOCKED:
            break
        batch = ex_ch_list[i : i + batch_size]
        ex_ch_str = "|".join(batch)
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch_str}"
        try:
            res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if res.status == 200:
                raw_text = res.body.decode('utf-8', errors='ignore')
                json_data = json.loads(raw_text)
                if "msgArray" in json_data and isinstance(json_data["msgArray"], list):
                    for info in json_data["msgArray"]:
                        code = info.get("c")
                        if not code:
                            continue
                        code = code.strip()
                        data = {"price": 0.0, "yest_close": 0.0, "open": 0.0, "high": 0.0, "low": 0.0, "today_vol": 0, "bid_vol": 1.0, "ask_vol": 1.0, "amplitude": 0.0, "name": ""}
                        data["price"] = float(info.get("z", "0").replace(",", "")) if info.get("z") and info.get("z") != "-" else 0.0
                        data["yest_close"] = float(info.get("y", "0").replace(",", "")) if info.get("y") and info.get("y") != "-" else 0.0
                        data["open"] = float(info.get("o", "0").replace(",", "")) if info.get("o") and info.get("o") != "-" else 0.0
                        data["high"] = float(info.get("h", "0").replace(",", "")) if info.get("h") and info.get("h") != "-" else 0.0
                        data["low"] = float(info.get("l", "0").replace(",", "")) if info.get("l") and info.get("l") != "-" else 0.0
                        data["today_vol"] = int(info.get("v", "0").replace(",", "")) if info.get("v") else 0
                        data["name"] = info.get("n", "").strip()
                        
                        if data["price"] == 0.0:
                            b_prices = info.get("b", "").split("_")
                            a_prices = info.get("a", "").split("_")
                            b_val = float(b_prices[0].replace(",", "")) if b_prices and b_prices[0] and b_prices[0] != "-" else 0.0
                            a_val = float(a_prices[0].replace(",", "")) if a_prices and a_prices[0] and a_prices[0] != "-" else 0.0
                            if b_val > 0 and a_val > 0: data["price"] = (b_val + a_val) / 2.0
                            elif b_val > 0: data["price"] = b_val
                            elif a_val > 0: data["price"] = a_val
                            elif data["open"] > 0: data["price"] = data["open"]
                            elif data["yest_close"] > 0: data["price"] = data["yest_close"]
                            
                        if data["yest_close"] > 0 and data["high"] > 0 and data["low"] > 0:
                            data["amplitude"] = (data["high"] - data["low"]) / data["yest_close"] * 100
                            
                        bids = info.get("g", "")
                        asks = info.get("f", "")
                        bid_sum = sum(int(x) for x in bids.split("_") if x.isdigit())
                        ask_sum = sum(int(x) for x in asks.split("_") if x.isdigit())
                        data["bid_vol"] = float(bid_sum) if bid_sum > 0 else 1.0
                        data["ask_vol"] = float(ask_sum) if ask_sum > 0 else 1.0
                        
                        results[code] = data
        except Exception as e:
            GLOBAL_TWSE_BLOCKED = True
            logging.error(f"獲取批量即時行情異常 (批次範圍 {i}-{i+batch_size}): {e}")
        time.sleep(0.2)
    return results

def fetch_yahoo_realtime_backup(code):
    suffixes = [".TW", ".TWO"]
    if code in GLOBAL_OTC_SET:
        suffixes = [".TWO", ".TW"]
    
    data = {"price": 0.0, "yest_close": 0.0, "open": 0.0, "high": 0.0, "low": 0.0, "today_vol": 0, "bid_vol": 1.0, "ask_vol": 1.0, "amplitude": 0.0, "name": ""}
    
    for suffix in suffixes:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}{suffix}?range=1d&interval=1m"
        try:
            res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if res.status == 200:
                raw_text = res.body.decode('utf-8', errors='ignore')
                json_data = json.loads(raw_text)
                if "chart" in json_data and json_data["chart"]["result"]:
                    result = json_data["chart"]["result"][0]
                    meta = result.get("meta", {})
                    
                    yest_close = meta.get("previousClose") or meta.get("chartPreviousClose") or 0.0
                    data["yest_close"] = float(yest_close)
                    data["name"] = meta.get("longName") or meta.get("shortName") or ""
                    
                    indicators = result.get("indicators", {})
                    quote = indicators.get("quote", [{}])[0]
                    
                    closes = [c for c in quote.get("close", []) if c is not None]
                    volumes = [v for v in quote.get("volume", []) if v is not None]
                    opens = [o for o in quote.get("open", []) if o is not None]
                    highs = [h for h in quote.get("high", []) if h is not None]
                    lows = [l for l in quote.get("low", []) if l is not None]
                    
                    if closes:
                        data["price"] = float(closes[-1])
                        data["today_vol"] = sum(volumes) / 1000.0
                        data["open"] = float(opens[0]) if opens else data["price"]
                        data["high"] = float(max(highs)) if highs else data["price"]
                        data["low"] = float(min(lows)) if lows else data["price"]
                        
                        if data["yest_close"] > 0 and data["high"] > 0 and data["low"] > 0:
                            data["amplitude"] = (data["high"] - data["low"]) / data["yest_close"] * 100
                        
                        return data
        except Exception:
            continue
    return None

# ----------------- 日內即時分析功能 -----------------
SPECIAL_STATUS_REGISTRY = {
    "6806": {
        "type": "delisting",
        "date": "2026-06-23",
        "reason": "115年第1季財報淨值為負數，已公告將於 2026/06/23 終止上市，目前採全額交割、分盤集合競價"
    }
}

def fetch_intraday_analysis(code, is_us=False, table_price=None, table_vol=None):
    """
    獲取單檔個股的日內 1 分鐘 K 線，計算日內位置、趨勢、操作建議等。
    台股自動附加 .TW/.TWO 後綴，美股直接使用 Ticker。
    回傳：分析結果字典，或 None (失敗)。
    """
    import urllib.request
    import ssl
    import urllib.parse
    
    ssl_context = ssl._create_unverified_context()
    ua_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    if is_us:
        symbols_to_try = [code]
    else:
        if code in GLOBAL_OTC_SET:
            symbols_to_try = [f"{code}.TWO", f"{code}.TW"]
        else:
            symbols_to_try = [f"{code}.TW", f"{code}.TWO"]
    
    for symbol in symbols_to_try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=1d&interval=1m"
        try:
            req = urllib.request.Request(url, headers=ua_headers)
            with urllib.request.urlopen(req, context=ssl_context, timeout=12) as response:
                raw_data = json.loads(response.read().decode('utf-8'))
                result_node = raw_data.get("chart", {}).get("result", [])
                if not result_node:
                    continue
                    
                chart = result_node[0]
                meta = chart.get("meta", {})
                quote = chart.get("indicators", {}).get("quote", [{}])[0]
                
                closes = [c for c in quote.get("close", []) if c is not None]
                opens_raw = [o for o in quote.get("open", []) if o is not None]
                highs = [h for h in quote.get("high", []) if h is not None]
                lows_list = [l for l in quote.get("low", []) if l is not None]
                volumes = [v for v in quote.get("volume", []) if v is not None]
                
                if not closes or not highs or not lows_list:
                    continue
                
                prev_close = float(meta.get("previousClose") or meta.get("chartPreviousClose") or 0.0)
                if table_price is not None and table_price > 0:
                    current_price = table_price
                else:
                    meta_price = meta.get("regularMarketPrice")
                    current_price = float(meta_price) if meta_price is not None and float(meta_price) > 0 else float(closes[-1])
                open_price = float(opens_raw[0]) if opens_raw else current_price
                day_high = max(float(max(highs)), current_price)
                day_low = min(float(min(lows_list)), current_price)
                if table_vol is not None and table_vol > 0:
                    total_vol = table_vol * 1000 if not is_us else table_vol
                else:
                    total_vol = sum(volumes) if volumes else 0
                
                company_name = meta.get("longName") or meta.get("shortName") or code
                
                if prev_close <= 0 or current_price <= 0:
                    continue
                
                # --- 衍生指標計算 ---
                day_range = day_high - day_low
                position_pct = (current_price - day_low) / day_range * 100 if day_range > 0 else 50.0
                    
                change_pct = (current_price - prev_close) / prev_close * 100
                open_gap_pct = (open_price - prev_close) / prev_close * 100
                amplitude_pct = day_range / prev_close * 100 if prev_close > 0 else 0.0
                dist_to_high_pct = (day_high - current_price) / current_price * 100 if current_price > 0 else 0.0
                dist_to_low_pct = (current_price - day_low) / current_price * 100 if current_price > 0 else 0.0
                
                # --- VWAP 與 短線量比 計算 ---
                if volumes and sum(volumes) > 0:
                    vwap = sum(c * v for c, v in zip(closes, volumes)) / sum(volumes)
                else:
                    vwap = sum(closes) / len(closes) if closes else current_price
                
                # 計算累計 VWAP 數列 (vwap_series)，作為日內均價線的各點繪圖點
                vwap_series = []
                cum_val = 0.0
                cum_vol = 0.0
                raw_vols = quote.get("volume", [])
                for idx, c in enumerate(quote.get("close", [])):
                    v = raw_vols[idx] if idx < len(raw_vols) else 0
                    if c is not None and v is not None:
                        cum_val += c * v
                        cum_vol += v
                        vwap_series.append(cum_val / cum_vol if cum_vol > 0 else c)
                    else:
                        vwap_series.append(vwap_series[-1] if vwap_series else current_price)
                
                if len(volumes) >= 10:
                    recent_10m_vol = sum(volumes[-10:]) / 10.0
                else:
                    recent_10m_vol = sum(volumes) / len(volumes) if volumes else 0.0
                
                overall_avg_vol = sum(volumes) / len(volumes) if volumes else 0.0
                vol_ratio = recent_10m_vol / overall_avg_vol if overall_avg_vol > 0 else 1.0
                
                # --- 🚨 特殊事件過濾器 (最高優先) ---
                is_delisting = False
                is_halted = False
                is_altered = False
                is_limit_down = False
                is_limit_up = False
                is_gap_down = False
                is_gap_up = False
                special_reason = ""
                
                # 1. 下市處理
                if code in SPECIAL_STATUS_REGISTRY and SPECIAL_STATUS_REGISTRY[code]["type"] == "delisting":
                    is_delisting = True
                    special_reason = SPECIAL_STATUS_REGISTRY[code]["reason"]
                
                # 2. 停止交易 (Halted)
                if not is_us and sum(volumes) == 0 and day_high == day_low == current_price == prev_close:
                    is_halted = True
                elif is_us and meta.get("tradingStatus") == "HALTED":
                    is_halted = True
                    
                # 3. 全額交割 / 分盤處置股
                if "*" in company_name or "處置" in company_name:
                    is_altered = True
                    special_reason = "處於全額交割或分盤處置交易"
                elif code in SPECIAL_STATUS_REGISTRY and SPECIAL_STATUS_REGISTRY[code]["type"] in ["altered_trading", "disposition"]:
                    is_altered = True
                    special_reason = SPECIAL_STATUS_REGISTRY[code]["reason"]
                    
                # 4. 跌停鎖死 (台股限價跌幅約 10%，跌幅大於等於 9.5% 且 current_price == day_low)
                if not is_us and change_pct <= -9.5 and current_price == day_low:
                    is_limit_down = True
                    
                # 5. 漲停鎖死 (台股限價漲幅約 10%，漲幅大於等於 9.5% 且 current_price == day_high)
                if not is_us and change_pct >= 9.5 and current_price == day_high:
                    is_limit_up = True
                    
                # 6. 偵測跳空急殺
                if open_gap_pct <= -3.0 and current_price < vwap:
                    is_gap_down = True
                    
                # 7. 偵測跳空急拉
                if open_gap_pct >= 3.0 and current_price > vwap:
                    is_gap_up = True
                
                # --- 狀態覆寫與評分判定 ---
                if is_delisting:
                    ai_status = "☠️ 下市處理股"
                    ai_score = 5
                    risk_level = "☠️ 極端風險"
                    risk_level_color = "#EF4444"
                    
                    action_html = (
                        "【持股者】以資金回收與風險控管為第一優先，若能交易宜盡速評估出場。<br/>"
                        "【空手者】絕對禁止開倉買進，防範資金歸零風險。"
                    )
                    action_plain = (
                        "【持股者】以資金回收與風險控管為第一優先，若能交易宜盡速評估出場。\n"
                        "   【空手者】絕對禁止開倉買進，防範資金歸零風險。"
                    )
                    limit_text_html = "無建議（下市處置，禁止新倉）"
                    limit_text_plain = "無建議（下市處置，禁止新倉）"
                    risk_text = f"終止上市風險（預計掛牌終止日：{SPECIAL_STATUS_REGISTRY[code]['date']}）；流動性不足；價格發現功能失真"
                    conclusion = f"{code} 已進入下市倒數階段，屬事件驅動型風險股，不適用一般日內技術分析模型。"
                    
                elif is_halted:
                    ai_status = "☠️ 停止交易"
                    ai_score = 0
                    risk_level = "☠️ 極端風險"
                    risk_level_color = "#EF4444"
                    
                    action_html = (
                        "【持股者】目前無法進行交易，請密切關注證交所後續公告與流動性風險。<br/>"
                        "【空手者】禁止開倉買進。"
                    )
                    action_plain = (
                        "【持股者】目前無法進行交易，請密切關注證交所後續公告與流動性風險。\n"
                        "   【空手者】禁止開倉買進。"
                    )
                    limit_text_html = "無建議（目前停止交易）"
                    limit_text_plain = "無建議（目前停止交易）"
                    risk_text = "該標的目前暫停/停止交易，交易流動性完全鎖死"
                    conclusion = f"{company_name} 目前處於暫停/停止交易狀態，無日內行情波動，請密切注意公告。"
                    
                elif is_altered:
                    ai_status = "⚠️ 分盤處置股" if "處置" in special_reason or (code in SPECIAL_STATUS_REGISTRY and SPECIAL_STATUS_REGISTRY[code]["type"] == "disposition") else "⚠️ 全額交割股"
                    ai_score = 20
                    risk_level = "🔴 極高"
                    risk_level_color = "#EF4444"
                    
                    action_html = (
                        "【持股者】此類股票波動劇烈且流動性受限，建議嚴格執行防守，適度收回資金。<br/>"
                        "【空手者】交易受全額交割或分盤限制，一般投資人宜保持觀望，避免參與。"
                    )
                    action_plain = (
                        "【持股者】此類股票波動劇烈且流動性受限，建議嚴格執行防守，適度收回資金。\n"
                        "   【空手者】交易受全額交割或分盤限制，一般投資人宜保持觀望，避免參與。"
                    )
                    limit_text_html = "暫無建議（分盤或全額交割股，建議觀望）"
                    limit_text_plain = "暫無建議（分盤或全額交割股，建議觀望）"
                    risk_text = f"流動性受限（分盤交易/全額交割）；買賣申報受管制；價格波動風險極高"
                    conclusion = f"{company_name} 目前採全額交割或分盤處置（原因：{special_reason}），技術分析參考性降低，請嚴防波動與流動性風險。"
                    
                elif is_limit_down:
                    ai_status = "🔴 跌停鎖死"
                    ai_score = 1
                    risk_level = "🔴 極高"
                    risk_level_color = "#EF4444"
                    
                    action_html = (
                        "【持股者】流動性已被封鎖，若有開板機會可適度減持以避險。<br/>"
                        "【空手者】切勿逆勢接刀，防範流動性被鎖定及隔日開低風險。"
                    )
                    action_plain = (
                        "【持股者】流動性已被封鎖，若有開板機會可適度減持以避險。\n"
                        "   【空手者】切勿逆勢接刀，防範流動性被鎖定及隔日開低風險。"
                    )
                    limit_text_html = "暫無建議（跌停鎖死中，請勿接刀）"
                    limit_text_plain = "暫無建議（跌停鎖死中，請勿接刀）"
                    risk_text = "跌停鎖死，無買盤承接；短線賣壓極重；流動性歸零"
                    conclusion = f"{company_name} 目前跌停鎖死，無買盤承接，短線賣壓極重且流動性歸零，請防範開板後的進一步跌勢。"
                    
                elif is_limit_up:
                    ai_status = "🟣 漲停鎖死"
                    ai_score = 99
                    risk_level = "🟡 中"
                    risk_level_color = "#FBBF24"
                    
                    action_html = (
                        "【持股者】多頭強勢鎖定，可繼續持有並隨時留意開板跡象，若跌破漲停價可考慮部分獲利了結。<br/>"
                        "【空手者】不建議在此排隊強行追買，慎防隔日隔日沖大單出貨。"
                    )
                    action_plain = (
                        "【持股者】多頭強勢鎖定，可繼續持有並隨時留意開板跡象，若跌破漲停價可考慮部分獲利了結。\n"
                        "   【空手者】不建議在此排隊強行追買，慎防隔日隔日沖大單出貨。"
                    )
                    limit_text_html = f"【突破型】若鎖定被打開且回測不破漲停價 {current_price:.2f} 可小試"
                    limit_text_plain = f"【突破型】若鎖定被打開且回測不破漲停價 {current_price:.2f} 可小試"
                    risk_text = "漲停鎖死追高風險大；慎防主力高檔開板出貨；隔日沖賣壓預期"
                    conclusion = f"{company_name} 目前漲停鎖死，買盤強勁排隊，短線多方絕對主導，但追高風險仍存，持股者可沿漲停板滾動防守。"
                    
                elif is_gap_down:
                    ai_status = "🟠 跳空急殺"
                    ai_score = 35
                    risk_level = "🟠 高"
                    risk_level_color = "#FB923C"
                    
                    action_html = (
                        f"【持股者】跳空開低後持續走弱，短線趨勢已翻空，建議跌破日低 {day_low:.2f} 減碼防守。<br/>"
                        f"【空手者】觀望為主，防範開低走低的殺盤慣性。"
                    )
                    action_plain = (
                        f"【持股者】跳空開低後持續走弱，短線趨勢已翻空，建議跌破日低 {day_low:.2f} 減碼防守。\n"
                        f"   【空手者】觀望為主，防範開低走低的殺盤慣性。"
                    )
                    limit_text_html = "暫無建議（跳空開低持續走弱，建議觀望）"
                    limit_text_plain = "暫無建議（跳空開低持續走弱，建議觀望）"
                    risk_text = f"今日跳空低開 {open_gap_pct:.2f}%，空方壓力明顯；日內跌幅較大（{change_pct:.2f}%），波動風險顯著"
                    conclusion = f"今日跳空開低後賣壓進一步傾瀉，短線空方全面掌控局勢，持股者宜提高警惕，空手者耐心等待止跌訊號。"
                    
                elif is_gap_up:
                    ai_status = "🟢 跳空急拉"
                    ai_score = 88
                    risk_level = "🟡 中"
                    risk_level_color = "#FBBF24"
                    
                    action_html = (
                        f"【持股者】跳空開高且維持強勢，可繼續持有，以 VWAP 作為移動防守。<br/>"
                        f"【空手者】不急於在日高追價，可等拉回 VWAP（約 {vwap:.2f}）附近止穩時再進場。"
                    )
                    action_plain = (
                        f"【持股者】跳空開高且維持強勢，可繼續持有，以 VWAP 作為移動防守。\n"
                        f"   【空手者】不急於在日高追價，可等拉回 VWAP（約 {vwap:.2f}）附近止穩時再進場。"
                    )
                    limit_text_html = f"【保守型】回踩 VWAP 附近買進（參考價：{vwap:.2f}）"
                    limit_text_plain = f"【保守型】回踩 VWAP 附近買進（參考價：{vwap:.2f}）"
                    risk_text = f"今日跳空開高 {open_gap_pct:.2f}%，追高回落風險高；日內振幅達 {amplitude_pct:.1f}%，波動風險顯著"
                    conclusion = f"今日跳空開高後買盤積極追價，展現強烈多頭企圖心，短線由多方主導，持股者續抱，空手者等待回踩支撐。"
                    
                else:
                    # 8. 正常與弱勢細分模型
                    # 1) 🚀 強勢突破
                    if current_price >= day_high * 0.998 and vol_ratio >= 1.5 and current_price > vwap and day_high != open_price:
                        ai_status = "🚀 強勢突破"
                        score_offset = min(10, int((vol_ratio - 1.5) * 5))
                        ai_score = 90 + score_offset
                        ai_score = min(100, ai_score)
                        
                    # 2) ☠️ 恐慌殺盤 / 🔴 破位轉弱：昨收跌幅 > 2% 且價格低於 vwap 且位置 < 10%
                    elif change_pct < -2.0 and current_price < vwap and position_pct < 10.0:
                        if position_pct < 5.0:
                            ai_status = "☠️ 恐慌殺盤"
                            ai_score = max(0, min(19, int(position_pct * 3.8)))
                        else:
                            ai_status = "🔴 破位轉弱"
                            ai_score = 20 + min(9, int((position_pct - 5.0) * 2.0))
                            
                    # 3) 🟠 開高回落：當前價仍漲（或昨收之上），但跳空開高、低於 vwap 且位置 < 20%
                    elif change_pct >= 0.0 and open_price > prev_close and current_price < vwap and position_pct < 20.0:
                        ai_status = "🟠 開高回落"
                        ai_score = 40 + min(19, int(position_pct * 1.0))
                        ai_score = min(59, max(40, ai_score))
                        
                    # 4) 🟢 高檔整理：價格在 VWAP 之上，且位置偏上緣 (position_pct >= 55.0)，且漲幅 >= 1.0
                    elif current_price >= vwap and position_pct >= 55.0 and change_pct >= 1.0:
                        ai_status = "🟢 高檔整理"
                        ai_score = 80 + min(14, int((position_pct - 55) * 0.2 + change_pct * 1.0))
                        ai_score = min(94, max(80, ai_score))
                        
                    # 5) 🟠 弱勢回落：價格低於 VWAP，且位置偏低，或者跌幅大於 1.5% 且在 VWAP 之下
                    elif current_price < vwap or position_pct < 40.0:
                        ai_status = "🟠 弱勢回落"
                        ai_score = 40 + min(19, int(position_pct * 0.5))
                        ai_score = min(59, max(40, ai_score))
                        
                    # 6) 🟡 區間震盪
                    else:
                        ai_status = "🟡 區間震盪"
                        ai_score = 60 + min(19, int((position_pct - 40) * 1.0))
                        ai_score = min(79, max(60, ai_score))
                    
                    # --- 風險等級判定 ---
                    if ai_status == "☠️ 恐慌殺盤":
                        risk_level = "🔴 極高"
                        risk_level_color = "#EF4444"
                    elif ai_status == "🔴 破位轉弱":
                        risk_level = "🟠 高"
                        risk_level_color = "#FB923C"
                    elif ai_status == "🟠 開高回落":
                        risk_level = "🟡 中"
                        risk_level_color = "#FBBF24"  # UI顯示為中高風險，與黃色中風險對應
                    else:
                        if position_pct < 2.0 or current_price <= day_low * 1.0005:
                            risk_level = "🔴 極高"
                            risk_level_color = "#EF4444"
                        elif current_price < vwap and position_pct < 10.0 and amplitude_pct >= 5.0:
                            risk_level = "🟠 高"
                            risk_level_color = "#FB923C"
                        elif amplitude_pct >= 4.0 or current_price < vwap:
                            risk_level = "🟡 中"
                            risk_level_color = "#FBBF24"
                        else:
                            risk_level = "🟢 低"
                            risk_level_color = "#34D399"
                        
                    # --- 操作建議 (正常與弱勢細分模型) ---
                    if ai_status == "🚀 強勢突破":
                        action_html = (
                            "【持股者】續抱，可沿盤中 VWAP 滾動防守；突破日高且量能同步放大時，可考慮小幅加碼。<br/>"
                            f"【空手者】若帶量向上突破日高 {day_high:.2f} 可順勢短線跟進，或等回踩 VWAP 支撐布局。"
                        )
                        action_plain = (
                            "【持股者】續抱，可沿盤中 VWAP 滾動防守；突破日高且量能同步放大時，可考慮小幅加碼。\n"
                            f"   【空手者】若帶量向上突破日高 {day_high:.2f} 可順勢短線跟進，或等回踩 VWAP 支撐布局。"
                        )
                    elif ai_status == "🟢 高檔整理":
                        action_html = (
                            f"【持股者】續抱，觀察能否重新挑戰日高 {day_high:.2f} 壓力。<br/>"
                            f"【空手者】不建議此時追價，可等待回測 VWAP（約 {vwap:.2f}）附近有撐時再進場。"
                        )
                        action_plain = (
                            f"【持股者】續抱，觀察能否重新挑戰日高 {day_high:.2f} 壓力。\n"
                            f"   【空手者】不建議此時追價，可等待回測 VWAP（約 {vwap:.2f}）附近有撐時再進場。"
                        )
                    elif ai_status == "🟡 區間震盪":
                        action_html = (
                            f"【持股者】暫時續抱，設定日低 {day_low:.2f} 為防守點，不宜在此加碼。<br/>"
                            f"【空手者】觀望為主，等待帶量突破日高 {day_high:.2f} 或拉回接近日低且量縮止穩再行考量。"
                        )
                        action_plain = (
                            f"【持股者】暫時續抱，設定日低 {day_low:.2f} 為防守點，不宜在此加碼。\n"
                            f"   【空手者】觀望為主，等待帶量突破日高 {day_high:.2f} 或拉回接近日低且量縮止穩再行考量。"
                        )
                    elif ai_status == "🟠 開高回落":
                        action_html = (
                            "【持股者】續抱但不宜加碼，觀察能否重新站回 VWAP。<br/>"
                            "【空手者】避免追價，等待站回 VWAP 或隔日轉強再考慮進場。"
                        )
                        action_plain = (
                            "【持股者】續抱但不宜加碼，觀察能否重新站回 VWAP。\n"
                            "   【空手者】避免追價，等待站回 VWAP 或隔日轉強再考慮進場。"
                        )
                    elif ai_status == "🟠 弱勢回落":
                        action_html = (
                            f"【持股者】若跌破日低 {day_low:.2f}，可先降低部位；若收盤跌破前收 {prev_close:.2f}，宜進一步提高警戒。<br/>"
                            f"【空手者】不急於接刀，觀望為主，靜待站回 VWAP（約 {vwap:.2f}）或止跌訊號出現。"
                        )
                        action_plain = (
                            f"【持股者】若跌破日低 {day_low:.2f}，可先降低部位；若收盤跌破前收 {prev_close:.2f}，宜進一步提高警戒。\n"
                            f"   【空手者】不急於接刀，觀望為主，靜待站回 VWAP（約 {vwap:.2f}）或止跌訊號出現。"
                        )
                    elif ai_status == "🔴 破位轉弱":
                        action_html = (
                            f"【持股者】跌破 VWAP 且日內位置偏低，短線有走弱風險，建議防守今日低點 {day_low:.2f}，若跌破宜適度減持。<br/>"
                            "【空手者】暫不接刀，靜待止跌訊號。"
                        )
                        action_plain = (
                            f"【持股者】跌破 VWAP 且日內位置偏低，短線有走弱風險，建議防守今日低點 {day_low:.2f}，若跌破宜適度減持。\n"
                            "   【空手者】暫不接刀，靜待止跌訊號。"
                        )
                    else:  # ☠️ 恐慌殺盤
                        action_html = (
                            "【持股者】股價已面臨恐慌破位殺盤，若跌破關鍵防守建議執行減碼或停損，防範跌勢擴大。<br/>"
                            "【空手者】絕對避免逆勢接刀，靜待日K層級重新築底。"
                        )
                        action_plain = (
                            "【持股者】股價已面臨恐慌破位殺盤，若跌破關鍵防守建議執行減碼或停損，防範跌勢擴大。\n"
                            "   【空手者】絕對避免逆勢接刀，靜待日K層級重新築底。"
                        )
                    
                    # --- 建議限價 (正常與弱勢細分模型) ---
                    if ai_status in ["🚀 強勢突破", "🟢 高檔整理"]:
                        limit_text_html = (
                            f"【保守型】回踩 VWAP 附近買進（參考價：{vwap:.2f}）<br/>"
                            f"【激進型】VWAP 不破且出現止跌紅K，可分批試單<br/>"
                            f"【突破型】帶量突破日高 {day_high:.2f} 追價"
                        )
                        limit_text_plain = (
                            f"【保守型】回踩 VWAP 附近買進（參考價：{vwap:.2f}）\n"
                            f"   【激進型】VWAP 不破且出現止跌紅K，可分批試單\n"
                            f"   【突破型】帶量突破日高 {day_high:.2f} 追價"
                        )
                    elif ai_status == "🟡 區間震盪":
                        low_zone_start = round(day_low * 1.002, 2)
                        low_zone_end = round(day_low * 1.008, 2)
                        limit_text_html = f"【區間型】回踩日低支撐區買進（參考區間：{low_zone_start} ~ {low_zone_end}）"
                        limit_text_plain = f"【區間型】回踩日低支撐區買進（參考區間：{low_zone_start} ~ {low_zone_end}）"
                    elif ai_status == "🟠 開高回落":
                        limit_text_html = "暫無建議（開高回落走勢，建議觀望等待止穩）"
                        limit_text_plain = "暫無建議（開高回落走勢，建議觀望等待止穩）"
                    else:
                        limit_text_html = "暫無建議（目前走勢偏弱，建議觀望等待止穩）"
                        limit_text_plain = "暫無建議（目前走勢偏弱，建議觀望等待止穩）"
                        
                    # --- 風險點 (正常與弱勢細分模型) ---
                    risks = []
                    if ai_status == "🟠 開高回落":
                        risks.append(f"若跌破日低 {day_low:.2f} 並擴大量能，可能演變為真正的恐慌性賣壓")
                    else:
                        if current_price < day_high and ai_status in ["🚀 強勢突破", "🟢 高檔整理"]:
                            risks.append(f"目前仍未有效突破日高 {day_high:.2f}，若跌破 VWAP {vwap:.2f}，短線可能轉為震盪整理")
                        if amplitude_pct >= 3.0:
                            risks.append(f"日內振幅達 {amplitude_pct:.1f}%，波動風險顯著")
                        if position_pct >= 85:
                            risks.append("股價接近日內高點，追高風險大")
                        if position_pct <= 15:
                            risks.append(f"股價接近日內低點，若跌破 {day_low:.2f} 可能加速下行")
                        if abs(change_pct) >= 3.0:
                            if change_pct < 0:
                                risks.append(f"日內跌幅較大（{change_pct:.2f}%），波動風險顯著")
                            else:
                                risks.append(f"日內漲幅過大（{change_pct:.2f}%），追高回落風險高")
                        if open_gap_pct <= -1.5:
                            risks.append(f"今日跳空低開 {open_gap_pct:.2f}%，空方壓力明顯")
                    if not risks:
                        risks.append("暫無明顯突出風險")
                    risk_text = "；".join(risks)
                    
                    # --- 一句話結論 (正常與弱勢細分模型) ---
                    if ai_status == "🚀 強勢突破":
                        conclusion = f"{company_name} 帶量突破日高，多方氣勢如虹；持股者可沿 VWAP 滾動防守，空手者避免過度追高，可等拉回 VWAP 附近或突破日高且量能同步放大時伺機布局。"
                    elif ai_status == "🟢 高檔整理":
                        conclusion = f"{company_name} 跳空開高後於日高附近高檔整理，多方仍掌握短線主導權；持股者可沿 VWAP 防守續抱，空手者等待帶量突破 {day_high:.2f} 或回測均價支撐再伺機布局。"
                    elif ai_status == "🟡 區間震盪":
                        conclusion = f"{company_name} 日內陷入區間震盪，量能萎縮；持股者設定好日低 {day_low:.2f} 防守，空手者多看少動，等待突破方向確認後再進場。"
                    elif ai_status == "🟠 開高回落":
                        conclusion = f"{company_name} 屬於「開高回落型」走勢，而非恐慌破位；今日反映追價買盤退潮，但多方尚未完全失守。"
                    elif ai_status == "🟠 弱勢回落":
                        if open_gap_pct >= 1.5:
                            conclusion = f"{company_name} 開高走低且失守 VWAP，短線轉弱跡象明顯；持股者嚴守 {day_low:.2f} 防線，空手者暫不接刀，等待止跌訊號再評估布局。"
                        else:
                            conclusion = f"{company_name} 震盪走弱且失守 VWAP，短線轉弱跡象明顯；持股者嚴守 {day_low:.2f} 防線，空手者暫不接刀，等待止跌訊號再評估布局。"
                    elif ai_status == "🔴 破位轉弱":
                        conclusion = f"{company_name} 跌破 VWAP 且技術面破位轉弱，短線空方稍佔優勢，建議嚴守日低防線，空手者耐心觀望。"
                    else:  # ☠️ 恐慌殺盤
                        conclusion = f"{company_name} 股價破位下行，賣壓沉重；持股者建議果斷減碼防守，空手者切勿盲目抄底。"
                
                # --- 日內位置描述 (所有狀態共用) ---
                if is_delisting or is_halted or is_altered or is_limit_down or is_limit_up:
                    # 特殊狀態下簡化位置描述，突顯特殊性質
                    pos_desc = f"處於 {ai_status} 特殊狀態，技術面區間位置（{position_pct:.1f}%）已失去一般技術分析意義"
                elif ai_status == "🟠 開高回落":
                    pos_desc = f"跳空開高後回落至日內低檔，區間位置 {position_pct:.1f}%，顯示短線追價買盤力道減弱"
                elif amplitude_pct < 2.0:
                    # 窄幅整理
                    if position_pct >= 55.0:
                        if open_gap_pct >= 1.0:
                            pos_desc = f"日內振幅僅 {amplitude_pct:.2f}%，價格維持於區間偏上緣（{position_pct:.1f}%），屬於開高後的高檔消化整理"
                        else:
                            pos_desc = f"日內振幅僅 {amplitude_pct:.2f}%，價格維持於區間偏上緣（{position_pct:.1f}%），屬於窄幅區間的偏強整理"
                    elif position_pct <= 45.0:
                        pos_desc = f"日內振幅僅 {amplitude_pct:.2f}%，價格維持於區間偏下緣（{position_pct:.1f}%），屬於窄幅區間的偏弱整理"
                    else:
                        pos_desc = f"日內振幅僅 {amplitude_pct:.2f}%，目前處於窄幅區間整理，位於日內中間位置（{position_pct:.1f}%）"
                else:
                    # 正常/寬幅波動
                    if position_pct >= 85:
                        pos_desc = f"靠近日內高位，區間位置約 {position_pct:.1f}%"
                    elif position_pct >= 60:
                        pos_desc = f"偏日內高位，區間位置約 {position_pct:.1f}%"
                    elif position_pct >= 40:
                        pos_desc = f"日內中間位置，區間位置約 {position_pct:.1f}%"
                    elif position_pct >= 15:
                        pos_desc = f"偏日內低位，區間位置約 {position_pct:.1f}%"
                    else:
                        pos_desc = f"靠近日內低位，區間位置約 {position_pct:.1f}%"
                
                if not (is_delisting or is_halted or is_altered or is_limit_down or is_limit_up or ai_status == "🟠 開高回落") and amplitude_pct >= 2.0:
                    position_text = (
                        f"{pos_desc}，"
                        f"距日內高點約 {dist_to_high_pct:.2f}%，距日內低點約 {dist_to_low_pct:.2f}%"
                    )
                else:
                    position_text = pos_desc
                
                # --- 趨勢判斷 (特殊狀態與細分弱勢覆寫) ---
                if is_delisting:
                    trend_text = "目前價格已失去一般技術分析參考意義，市場主要反映下市風險與流動性折價。"
                elif is_halted:
                    trend_text = "該標的今日無盤中波動數據，目前處於暫停交易狀態。"
                elif is_altered:
                    trend_text = "該股目前處於全額交割或分盤交易處置狀態，價格形成機制受限，短線方向受管制政策與資金撮合時間主導。"
                elif is_limit_down:
                    trend_text = f"股價以大跌跌停開出或盤中直接釘死在跌停價 {current_price:.2f}，賣壓高掛且無人承接，空方絕對控制。"
                elif is_limit_up:
                    trend_text = f"股價強勢攻上漲停價 {current_price:.2f} 並強鎖至收盤/當前，買單高掛排隊，多方絕對控制。"
                elif ai_status == "🟠 開高回落":
                    trend_text = f"雖然股價仍上漲 {change_pct:.2f}%，但未能守住 VWAP {vwap:.2f}，代表開盤攻勢遭遇獲利了結，短線轉為偏弱震盪。"
                elif ai_status == "🔴 破位轉弱":
                    trend_text = f"股價跌破盤中 VWAP 且偏日內低檔，昨收跌幅達 {change_pct:.2f}%，短線防守位置跌破，技術面破位轉弱。"
                elif ai_status == "☠️ 恐慌殺盤":
                    trend_text = f"股價跌破盤中 VWAP 且極貼近日低，昨收跌幅達 {change_pct:.2f}%，市場賣壓沉重，面臨恐慌性殺盤。"
                else:
                    # 正常模型趨勢判斷
                    abs_chg = abs(change_pct)
                    if change_pct >= 3.0:
                        trend_dir = "日內大幅上漲"
                    elif change_pct >= 1.0:
                        trend_dir = "日內溫和上漲"
                    elif change_pct >= 0.3:
                        trend_dir = "日內小幅上漲"
                    elif change_pct >= -0.3:
                        trend_dir = "日內持平震盪"
                    elif change_pct >= -1.0:
                        trend_dir = "日內小幅下跌"
                    elif change_pct >= -3.0:
                        trend_dir = "日內溫和下跌"
                    else:
                        trend_dir = "日內大幅下跌"
                        
                    if len(closes) >= 10:
                        mid_idx = len(closes) // 2
                        first_half_avg = sum(closes[:mid_idx]) / mid_idx
                        second_half_avg = sum(closes[mid_idx:]) / (len(closes) - mid_idx)
                        if second_half_avg > first_half_avg * 1.002:
                            persist_desc = "持續走強"
                        elif second_half_avg < first_half_avg * 0.998:
                            persist_desc = "持續走弱"
                        else:
                            persist_desc = "橫盤整理"
                    else:
                        persist_desc = "數據不足"
                        
                    price_near = "高點" if position_pct >= 60 else ("低點" if position_pct <= 40 else "中位")
                    
                    if open_gap_pct >= 2.0 and position_pct <= 15.0 and current_price < vwap:
                        trend_text = f"跳空開高後賣壓持續湧現，股價跌破盤中 VWAP 並逼近日低，短線主導權已由多方轉向空方。"
                    elif open_gap_pct <= -2.0 and position_pct >= 85.0 and current_price > vwap:
                        trend_text = f"跳空開低後買盤強勢進場，股價站上盤中 VWAP 並逼近日高，短線主導權已由空方轉向多方。"
                    elif open_gap_pct >= 1.5 and change_pct >= 1.5 and persist_desc == "橫盤整理":
                        trend_text = f"日內維持開高震盪格局，雖然未能續創新高，但價格仍穩守前收之上，多方掌控短線節奏，呈現高檔整理。"
                    elif open_gap_pct <= -1.5 and change_pct <= -1.5 and persist_desc == "橫盤整理":
                        trend_text = f"日內跳空開低後呈現低檔震盪整理，空方短線仍佔優勢，反彈乏力。"
                    else:
                        trend_text = (
                            f"{trend_dir} {change_pct:.2f}%，開盤價 {open_price:.2f} "
                            f"{'高於' if open_price > prev_close else '低於' if open_price < prev_close else '等於'}"
                            f"前收 {prev_close:.2f}，{persist_desc}，"
                            f"接近日內{price_near} {current_price:.2f}"
                        )
                
                # 格式化成交量
                if is_us:
                    vol_str = f"{total_vol:,.0f} 股"
                else:
                    vol_str = f"{total_vol / 1000:,.0f} 張" if total_vol >= 1000 else f"{total_vol:,.0f} 股"
                
                # 填充 close 和 volume 以供繪圖
                raw_closes = quote.get("close", [])
                raw_vols = quote.get("volume", [])
                
                closes_plot = []
                last_valid_close = current_price
                for c in raw_closes:
                    if c is not None:
                        last_valid_close = float(c)
                    closes_plot.append(last_valid_close)
                    
                vols_plot = [float(v) if v is not None else 0.0 for v in raw_vols]
                
                return {
                    "code": code, "name": company_name,
                    "market": "US" if is_us else "TW",
                    "current_price": current_price, "prev_close": prev_close,
                    "open_price": open_price, "day_high": day_high, "day_low": day_low,
                    "total_vol": total_vol, "vol_str": vol_str,
                    "change_pct": change_pct, "open_gap_pct": open_gap_pct,
                    "amplitude_pct": amplitude_pct, "position_pct": position_pct,
                    "position_text": position_text, "trend_text": trend_text,
                    "action": action_plain, "action_html": action_html,
                    "limit_text": limit_text_plain, "limit_text_html": limit_text_html,
                    "risk_text": risk_text, "conclusion": conclusion,
                    "vwap": vwap, "vol_ratio": vol_ratio,
                    "ai_status": ai_status, "ai_score": ai_score,
                    "risk_level": risk_level, "risk_level_color": risk_level_color,
                    "closes_plot": closes_plot, "vols_plot": vols_plot, "vwap_series": vwap_series
                }
        except Exception as e:
            logging.warning(f"日內分析 {symbol} 失敗: {e}")
            continue
    return None
def fetch_yahoo_taiex_backup():
    regime = {"status": "強勢 (加權指數多頭 Regime)", "multiplier": 1.0, "change_pct": 0.0, "index_p": 0.0}
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?range=1d&interval=1m"
    try:
        res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if res.status == 200:
            raw_text = res.body.decode('utf-8', errors='ignore')
            json_data = json.loads(raw_text)
            if "chart" in json_data and json_data["chart"]["result"]:
                result = json_data["chart"]["result"][0]
                meta = result.get("meta", {})
                yest_close = meta.get("previousClose") or meta.get("chartPreviousClose") or 0.0
                
                indicators = result.get("indicators", {})
                quote = indicators.get("quote", [{}])[0]
                closes = [c for c in quote.get("close", []) if c is not None]
                if closes and yest_close > 0:
                    z = float(closes[-1])
                    y = float(yest_close)
                    change_pct = (z - y) / y * 100
                    regime["change_pct"] = change_pct
                    regime["index_p"] = z
                    if change_pct < -1.0:
                        regime["status"] = "恐慌 (大盤重挫避險防守，評分 × 0.5)"
                        regime["multiplier"] = 0.5
                    elif change_pct < 0.0:
                        regime["status"] = "弱勢 (大盤下跌震盪避險，評分 × 0.8)"
                        regime["multiplier"] = 0.8
    except Exception as e:
        logging.error(f"獲取 Yahoo 大盤備份異常: {e}")
    return regime

def fetch_taiex_regime():
    global GLOBAL_TWSE_BLOCKED
    if GLOBAL_TWSE_BLOCKED:
        return fetch_yahoo_taiex_backup()
        
    url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw"
    regime = {"status": "強勢 (加權指數多頭 Regime)", "multiplier": 1.0, "change_pct": 0.0, "index_p": 0.0}
    try:
        res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if res.status == 200:
            raw_text = res.body.decode('utf-8', errors='ignore')
            json_data = json.loads(raw_text)
            if "msgArray" in json_data and len(json_data["msgArray"]) > 0:
                info = json_data["msgArray"][0]
                z = float(info.get("z", "0").replace(",", "")) if info.get("z") and info.get("z") != "-" else 0.0
                y = float(info.get("y", "0").replace(",", "")) if info.get("y") and info.get("y") != "-" else 0.0
                if z > 0 and y > 0:
                    change_pct = (z - y) / y * 100
                    regime["change_pct"] = change_pct
                    regime["index_p"] = z
                    if change_pct < -1.0:
                        regime["status"] = "恐慌 (大盤重挫避險防守，評分 × 0.5)"
                        regime["multiplier"] = 0.5
                    elif change_pct < 0.0:
                        regime["status"] = "弱勢 (大盤下跌震盪避險，評分 × 0.8)"
                        regime["multiplier"] = 0.8
    except Exception:
        pass
        
    if regime["index_p"] <= 0.0:
        regime = fetch_yahoo_taiex_backup()
        
    return regime

def fetch_market_60d_return(is_us=False):
    """
    獲取大盤（台股為 ^TWII，美股為 ^GSPC）過去 60 個交易日的報酬率
    """
    symbol = "%5EGSPC" if is_us else "%5ETWII"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=90d&interval=1d"
    try:
        res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if res.status == 200:
            raw_text = res.body.decode('utf-8', errors='ignore')
            json_data = json.loads(raw_text)
            result = json_data.get("chart", {}).get("result", [{}])[0]
            indicators = result.get("indicators", {})
            quote = indicators.get("quote", [{}])[0]
            closes = [c for c in quote.get("close", []) if c is not None]
            if len(closes) >= 60:
                p_today = closes[-1]
                p_60d = closes[-60]
                market_ret = (p_today - p_60d) / p_60d * 100
                return market_ret
    except Exception as e:
        logging.error(f"獲取大盤 60D 歷史報酬異常 (is_us={is_us}): {e}")
    return 0.0

# ----------------- 批量獲取 -----------------
def fetch_twse_bulk_daily(date_str):
    url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={date_str}&type=ALLBUT0999"
    result = {}
    data = None
    try:
        res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, retries=0)
        if res.status == 200:
            data = json.loads(res.body.decode('utf-8', errors='ignore'))
    except Exception as e:
        logging.warning(f"Fetcher 獲取上市行情失敗: {e}，將使用 urllib.request 重試...")
        
    if not data:
        try:
            import urllib.request
            import ssl
            ssl_context = ssl._create_unverified_context()
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8', errors='ignore'))
        except Exception as e:
            logging.error(f"urllib 獲取上市行情亦失敗: {e}")
            
    if data and data.get('stat') == 'OK':
        tables = data.get('tables', [])
        stock_table = None
        for t in tables:
            title = t.get('title', '')
            if '每日收盤行情' in title and len(t.get('data', [])) > 100:
                stock_table = t
                break
        if stock_table:
            for row in stock_table.get('data', []):
                try:
                    code = row[0].strip()
                    name = row[1].strip()
                    volume = (int(row[2].replace(',', '')) / 1000.0) if row[2].replace(',', '').isdigit() else 0
                    close_p = float(row[8].replace(',', '')) if row[8] and row[8] != '--' else 0.0
                    open_p = float(row[5].replace(',', '')) if row[5] and row[5] != '--' else 0.0
                    high_p = float(row[6].replace(',', '')) if row[6] and row[6] != '--' else 0.0
                    low_p = float(row[7].replace(',', '')) if row[7] and row[7] != '--' else 0.0
                    change_sign_html = row[9]
                    is_down = 'green' in change_sign_html
                    change_abs = float(row[10].replace(',', '')) if row[10] and row[10] != '--' else 0.0
                    change_val = -change_abs if is_down else change_abs
                    yest_close = close_p - change_val if close_p > 0 else 0.0
                    change_pct = (change_val / yest_close * 100) if yest_close > 0 else 0.0
                    result[code] = {
                        "name": name, "close": close_p, "open": open_p,
                        "high": high_p, "low": low_p, "yest_close": yest_close,
                        "volume": volume, "change_val": change_val, "change_pct": change_pct
                    }
                except Exception:
                    continue
    return result

def fetch_twse_bulk_institutional(date_str):
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
    result = {}
    data = None
    try:
        res = Fetcher.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, retries=0)
        if res.status == 200:
            data = json.loads(res.body.decode('utf-8', errors='ignore'))
    except Exception as e:
        logging.warning(f"Fetcher 獲取上市法人失敗: {e}，將使用 urllib.request 重試...")
        
    if not data:
        try:
            import urllib.request
            import ssl
            ssl_context = ssl._create_unverified_context()
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8', errors='ignore'))
        except Exception as e:
            logging.error(f"urllib 獲取上市法人亦失敗: {e}")
            
    if data and data.get('stat') == 'OK':
        for row in data.get('data', []):
            try:
                code = row[0].strip()
                foreign_net = int(row[4].replace(',', '').strip())
                trust_net = int(row[10].replace(',', '').strip())
                dealer_net = int(row[11].replace(',', '').strip())
                total_net = int(row[18].replace(',', '').strip())
                result[code] = {"foreign_net": foreign_net, "trust_net": trust_net, "dealer_net": dealer_net, "total_net": total_net}
            except Exception:
                continue
    return result

def fetch_tpex_bulk_daily():
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    result = {}
    data = None
    try:
        res = Fetcher.get(url, timeout=8, retries=0)
        if res.status == 200:
            data = json.loads(res.body.decode('utf-8', errors='ignore'))
    except Exception as e:
        logging.warning(f"Fetcher 獲取上櫃行情失敗: {e}，將使用 urllib.request 重試...")
        
    if not data:
        try:
            import urllib.request
            import ssl
            ssl_context = ssl._create_unverified_context()
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8', errors='ignore'))
        except Exception as e:
            logging.error(f"urllib 獲取上櫃行情亦失敗: {e}")
            
    if data:
        for row in data:
            try:
                code = row.get("SecuritiesCompanyCode", "").strip()
                name = row.get("CompanyName", "").strip()
                volume = int(row.get("TradingShares", "0").replace(",", "")) / 1000.0
                close_p = float(row.get("Close", "0").replace(",", "")) if row.get("Close") != '---' else 0.0
                open_p = float(row.get("Open", "0").replace(",", "")) if row.get("Open") != '---' else 0.0
                high_p = float(row.get("High", "0").replace(",", "")) if row.get("High") != '---' else 0.0
                low_p = float(row.get("Low", "0").replace(",", "")) if row.get("Low") != '---' else 0.0
                change_str = row.get("Change", "0").replace(",", "").strip()
                change_val = float(change_str) if change_str != '---' else 0.0
                yest_close = close_p - change_val if close_p > 0 else 0.0
                change_pct = (change_val / yest_close * 100) if yest_close > 0 else 0.0
                result[code] = {
                    "name": name, "close": close_p, "open": open_p,
                    "high": high_p, "low": low_p, "yest_close": yest_close,
                    "volume": volume, "change_val": change_val, "change_pct": change_pct
                }
            except Exception:
                continue
    return result

def fetch_tpex_bulk_institutional():
    url = "https://www.tpex.org.tw/openapi/v1/tpex_3insti_trading"
    result = {}
    data = None
    try:
        res = Fetcher.get(url, timeout=8, retries=0)
        if res.status == 200:
            data = json.loads(res.body.decode('utf-8', errors='ignore'))
    except Exception as e:
        logging.warning(f"Fetcher 獲取上櫃法人失敗: {e}，將使用 urllib.request 重試...")
        
    if not data:
        try:
            import urllib.request
            import ssl
            ssl_context = ssl._create_unverified_context()
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8', errors='ignore'))
        except Exception as e:
            logging.error(f"urllib 獲取上櫃法人亦失敗: {e}")
            
    if data:
        for row in data:
            try:
                code = row.get("SecuritiesCompanyCode", "").strip()
                net_buy = int(row.get("NetBuy", "0").replace(",", ""))
                # TPEx 只給總量，按上櫃歷史比例估算細項
                if net_buy > 0:
                    est_foreign = int(net_buy * 0.60)
                    est_trust = int(net_buy * 0.25)
                    est_dealer = net_buy - est_foreign - est_trust
                elif net_buy < 0:
                    est_foreign = int(net_buy * 0.60)
                    est_trust = int(net_buy * 0.25)
                    est_dealer = net_buy - est_foreign - est_trust
                else:
                    est_foreign = 0; est_trust = 0; est_dealer = 0
                result[code] = {"foreign_net": est_foreign, "trust_net": est_trust, "dealer_net": est_dealer, "total_net": net_buy, "estimated_split": True}
            except Exception:
                continue
    return result

# ----------------- 打分與時機系統 -----------------
def calculate_qai_score(features, is_etf=False):
    comp_score = 0.0
    comp_details = []
    
    cv_ratio = features["volatility_contraction"]
    if cv_ratio <= 0.5: s1 = 30.0
    elif cv_ratio <= 0.7: s1 = 22.0
    elif cv_ratio <= 1.0: s1 = 12.0
    elif cv_ratio <= 1.3: s1 = 5.0
    else: s1 = 0.0
    comp_score += s1
    comp_details.append(f"波動收縮率 (5D vs 20D): {round(cv_ratio, 2)} [+{round(s1, 1)}]")
    
    v_ratio_5d_20d = features["vol_ratio_5d_20d"]
    if v_ratio_5d_20d <= 0.6: s2 = 30.0
    elif v_ratio_5d_20d <= 0.8: s2 = 22.0
    elif v_ratio_5d_20d <= 1.0: s2 = 12.0
    elif v_ratio_5d_20d <= 1.2: s2 = 5.0
    else: s2 = 0.0
    comp_score += s2
    comp_details.append(f"成交量萎縮度: {round(v_ratio_5d_20d, 2)} [+{round(s2, 1)}]")
    
    slope = abs(features["price_slope"])
    if slope <= 0.15: s3 = 20.0
    elif slope <= 0.35: s3 = 12.0
    elif slope <= 0.6: s3 = 5.0
    else: s3 = 0.0
    comp_score += s3
    comp_details.append(f"價格斜率平坦度: {round(slope, 3)}% [+{round(s3, 1)}]")
    
    range_20d = features["price_range_20d"]
    limit_range = 5.0 if is_etf else 8.0
    if range_20d <= limit_range: s4 = 20.0
    elif range_20d <= limit_range*1.5: s4 = 12.0
    elif range_20d <= limit_range*2.2: s4 = 5.0
    else: s4 = 0.0
    comp_score += s4
    comp_details.append(f"長期窄幅收縮度: {round(range_20d, 1)}% [+{round(s4, 1)}]")
    
    accum_score = 0.0
    accum_details = []
    
    pos = features["position_60d"]
    fc = features["foreign_consecutive"]
    tc = features["trust_consecutive"]
    dc = features.get("dealer_consecutive", 0)
    
    if is_etf:
        # ETF 籌碼與配息權重分配：價格位置 30分 + 法人連買 35分 + OBI固定 15分 + Dividend 20分 = 100分
        # 1. 價格位置適中性 (滿分 30)
        if 0.2 <= pos <= 0.6: s5 = 30.0
        elif 0.1 <= pos < 0.2 or 0.6 < pos <= 0.7: s5 = 15.0
        else: s5 = 0.0
        accum_score += s5
        accum_details.append(f"價格位置適中性: {round(pos*100, 1)}% [+{round(s5, 1)}]")
        
        # 2. 法人籌碼連買 (滿分 35)
        max_consec = max(fc, dc)
        if 1 <= max_consec <= 3: s6 = 35.0
        elif 4 <= max_consec <= 6: s6 = 22.0
        elif max_consec == 0: s6 = 10.0
        else: s6 = 0.0
        accum_score += s6
        accum_details.append(f"法人微動 (外資{fc}D/自營{dc}D): 連買{max_consec}D [+{round(s6, 1)}]")
        
        # 3. OBI 掛單平滑指標 (滿分 15)
        s7 = 15.0
        accum_score += s7
        accum_details.append(f"平滑掛單比 OBI (造市商去雜訊): 固定 [+{round(s7, 1)}]")
        
        # 4. 配息與填息因子 Dividend Score (滿分 20)
        code = features.get("code", "")
        db_entry = ETF_DIVIDEND_DATABASE.get(code, {})
        
        # 動態打分模型 + 預設資料庫備援
        dy = features.get("dividend_yield")
        if dy is not None and float(dy) > 0.0:
            dy = float(dy)
            # 殖利率得分 (Yield, 滿分 8)
            if dy >= 9.0: yield_s = 8.0
            elif dy >= 7.0: yield_s = 6.5
            elif dy >= 5.0: yield_s = 5.0
            elif dy >= 3.0: yield_s = 3.0
            else: yield_s = 1.0
            
            fill_s = db_entry.get("fill_score", 5.0)
            stab_s = db_entry.get("stability_score", 3.5)
            grow_s = db_entry.get("growth_score", 1.5)
            
            dividend_s = yield_s + fill_s + stab_s + grow_s
            dividend_s = min(20.0, max(0.0, dividend_s))
            label = f"動態配息率打分 ({dy:.1f}%)"
        else:
            if db_entry:
                dividend_s = db_entry.get("score", 13.0)
                label = "資料庫備援打分"
            else:
                name = features.get("name", "")
                theme = features.get("theme", "")
                if "高股息" in name or "高息" in name or "優息" in name:
                    dividend_s = 16.0
                    label = "高息ETF基準分"
                elif "債券" in name or "債" in theme or code.endswith("B"):
                    dividend_s = 15.0
                    label = "債券ETF基準分"
                else:
                    dividend_s = 12.0
                    label = "一般ETF基準分"
        
        accum_score += dividend_s
        accum_details.append(f"配息與填息指標 ({label}): [+{round(dividend_s, 1)}]")
        
    else:
        # 個股籌碼與掛單評分
        bc = features.get("broker_concentration")
        if bc is not None:
            # 1. 價格位置適中性 (滿分 30)
            if 0.2 <= pos <= 0.6: s5 = 30.0
            elif 0.1 <= pos < 0.2 or 0.6 < pos <= 0.7: s5 = 15.0
            else: s5 = 0.0
            accum_score += s5
            accum_details.append(f"價格位置適中性: {round(pos*100, 1)}% [+{round(s5, 1)}]")
            
            # 2. 法人籌碼連買 (滿分 30)
            max_consec = max(fc, tc)
            if 1 <= max_consec <= 3: s6 = 30.0
            elif 4 <= max_consec <= 6: s6 = 18.0
            elif max_consec == 0: s6 = 8.0
            else: s6 = 0.0
            accum_score += s6
            accum_details.append(f"法人微動 (外資{fc}D/投信{tc}D): 連買{max_consec}D [+{round(s6, 1)}]")
            
            # 3. OBI 掛單平滑指標 (滿分 15)
            obi = features["obi_smoothed"]
            if obi >= 1.5: s7 = 15.0
            elif obi >= 1.0: s7 = 8.0
            else: s7 = 0.0
            accum_score += s7
            accum_details.append(f"平滑掛單比 OBI: {round(obi, 2)} [+{round(s7, 1)}]")
            
            # 4. 主力分點買賣超集中度 (滿分 25)
            if bc >= 10.0: s_bc = 25.0
            elif bc >= 5.0: s_bc = 18.0
            elif bc >= 0.0: s_bc = 10.0
            else: s_bc = 0.0
            accum_score += s_bc
            accum_details.append(f"分點籌碼集中度: {round(bc, 2)}% [+{round(s_bc, 1)}]")
        else:
            # 原本的 3 因子模型（價格位置 40分 + 法人連買 40分 + OBI 20分 = 100分）
            if 0.2 <= pos <= 0.6: s5 = 40.0
            elif 0.1 <= pos < 0.2 or 0.6 < pos <= 0.7: s5 = 20.0
            else: s5 = 0.0
            accum_score += s5
            accum_details.append(f"價格位置適中性: {round(pos*100, 1)}% [+{round(s5, 1)}]")
            
            max_consec = max(fc, tc)
            if 1 <= max_consec <= 3: s6 = 40.0
            elif 4 <= max_consec <= 6: s6 = 25.0
            elif max_consec == 0: s6 = 10.0
            else: s6 = 0.0
            accum_score += s6
            accum_details.append(f"法人微動 (外資{fc}D/投信{tc}D): 連買{max_consec}D [+{round(s6, 1)}]")
            
            obi = features["obi_smoothed"]
            if obi >= 1.5: s7 = 20.0
            elif obi >= 1.0: s7 = 10.0
            else: s7 = 0.0
            accum_score += s7
            accum_details.append(f"平滑掛單比 OBI: {round(obi, 2)} [+{round(s7, 1)}]")
        
    trig_score = 0.0
    trig_details = []
    
    price = features["price"]
    max_20d = features["max_20d"]
    breakout_pct = (price - max_20d) / max_20d * 100 if max_20d > 0 else 0.0
    limit_break = 2.0 if is_etf else 3.0
    if breakout_pct >= limit_break:
        s8 = 15.0
        breakout_label = f"Exhaustion (+{breakout_pct:.1f}%)"
    elif breakout_pct >= 0.0:
        s8 = 40.0
        breakout_label = f"Confirmed (+{breakout_pct:.1f}%)"
    elif breakout_pct >= -2.0:
        s8 = 50.0
        breakout_label = f"Near ({breakout_pct:.1f}%)"
    else:
        s8 = 0.0
        breakout_label = f"Far ({breakout_pct:.1f}%)"
    trig_score += s8
    trig_details.append(f"價格突破狀態: {breakout_label} [+{round(s8, 1)}]")
    
    vol_ratio = features["vol_ratio"]
    volume_slope = features["volume_slope"]
    limit_v = 1.1 if is_etf else 1.2
    limit_v_weak = 0.9 if is_etf else 1.0
    if vol_ratio >= limit_v*1.25 and volume_slope >= limit_v*1.25: s9 = 50.0
    elif vol_ratio >= limit_v and volume_slope >= limit_v: s9 = 30.0
    elif vol_ratio >= limit_v_weak or volume_slope >= limit_v_weak: s9 = 10.0
    else: s9 = 0.0
    trig_score += s9
    trig_details.append(f"量能與速度爆發 (量比{round(vol_ratio, 2)}): [+{round(s9, 1)}]")
    
    return round(comp_score, 1), round(accum_score, 1), round(trig_score, 1)

def calculate_stage1_continuation(s, regime_status, is_etf=False):
    price = s.get("price", 0.0)
    ma5 = s.get("ma5", 0.0)
    ma20 = s.get("ma20", 0.0)
    ma60 = s.get("ma60", 0.0)
    vz = s.get("vol_z", 0.0)
    vol_ratio = s.get("vol_ratio", 1.0)
    comp_score = s.get("comp_score", 0.0)
    position_60d = s.get("position_60d", 0.5)
    obi = s.get("obi_smoothed", 0.0)
    
    s_trig = s.get("trig_score", 0.0) * 0.4
    s_vol = 20.0 if vz >= 2.0 else (15.0 if vz >= 1.0 else (10.0 if vz >= 0.0 else 0.0))
    s_obi = 15.0 if obi >= 1.5 else (10.0 if obi >= 1.0 else (5.0 if obi >= 0.5 else 0.0))
    
    fc = s.get("foreign_consecutive", 0)
    tc = s.get("trust_consecutive", 0)
    dc = s.get("dealer_consecutive", 0)
    max_consec = max(fc, dc) if is_etf else max(fc, tc)
    s_inst = 15.0 if max_consec >= 3 else (10.0 if max_consec >= 1 else 0.0)
    s_comp = comp_score * 0.1
    
    base_continuation = s_trig + s_vol + s_obi + s_inst + s_comp
    
    is_above_ma20 = price >= ma20 if ma20 > 0 else False
    is_above_ma60 = price >= ma60 if ma60 > 0 else False
    is_bull_regime = ma20 >= ma60 if (ma20 > 0 and ma60 > 0) else False
    
    trend_score = 20.0 if is_above_ma20 else 0.0
    if is_above_ma60: trend_score += 10.0
    if is_bull_regime: trend_score += 10.0
    
    pattern_adjustment = calculate_pattern_adjustment(s)
    
    if not is_etf:
        # 個股採用全新五因子評分矩陣 (趨勢 25% | 法人 20% | 技術 20% | 量能 15% | 產業熱度 20%)
        # 1. 趨勢方向 (25%) - 由原本 40 分的 trend_score 映射
        trend_factor = (trend_score / 40.0) * 25.0
        
        # 2. 法人籌碼 (20%) - 連買與分點集中度 (滿分 20)
        inst_base = 10.0 if max_consec >= 3 else (7.0 if max_consec >= 1 else 2.0)
        bc = s.get("broker_concentration")
        if bc is not None:
            bc_score = 10.0 if bc >= 10.0 else (7.0 if bc >= 5.0 else (4.0 if bc >= 0.0 else 0.0))
        else:
            bc_score = 5.0
        inst_factor = inst_base + bc_score
        
        # 3. 技術面結構 (20%) - 由原本 100 分的 comp_score 映射
        tech_factor = (comp_score / 100.0) * 20.0
        
        # 4. 量能速度 (15%) - 依據實體量比給分
        if vol_ratio >= 1.5:
            vol_factor = 15.0
        elif vol_ratio >= 1.2:
            vol_factor = 12.0
        elif vol_ratio >= 0.95:
            vol_factor = 8.0
        else:
            vol_factor = 5.0
            
        # 5. 產業熱度共振 (20%)
        sector_res = s.get("sector_resonance", 0.0)
        if isinstance(sector_res, str):
            sector_res = 0.0
        sector_factor = (sector_res / 100.0) * 20.0
        
        base_score = trend_factor + inst_factor + tech_factor + vol_factor + sector_factor
        final_score = round(base_score + pattern_adjustment, 1)
    else:
        # ETF 維持原本計算邏輯
        final_score = round(0.6 * base_continuation + 1.0 * trend_score + pattern_adjustment, 1)
    final_score = min(100.0, max(0.0, final_score))
    
    data_quality_score = min(100.0, max(0.0, s.get("data_quality_score", 100.0)))
    quality_multiplier = 0.7 + 0.3 * (data_quality_score / 100.0)
    final_score = round(final_score * quality_multiplier, 1)
    
    global GLOBAL_TAIEX_20D_RETURN
    is_bond = is_etf and (s.get("code", "").endswith("B") or "債券" in s.get("theme", ""))
    
    if is_bond and ("恐慌" in regime_status or "弱勢" in regime_status):
        bond_return_20d = 0.0
        if "closes" in s and len(s["closes"]) >= 20:
            bond_return_20d = (s["closes"][-1] - s["closes"][-20]) / s["closes"][-20] * 100
        
        # 比較債券與大盤的 20D 報酬差額 (相對強度)
        market_return_20d = GLOBAL_TAIEX_20D_RETURN if GLOBAL_TAIEX_20D_RETURN is not None else -5.0
        relative_strength = bond_return_20d - market_return_20d
        regime_bias = 0.5 if relative_strength > 0 else 0.0
    else:
        regime_bias = 0.5 if "強勢" in regime_status else (-0.5 if ("恐慌" in regime_status or "弱勢" in regime_status) else 0.0)
        
    logit = 0.08 * (final_score - 55.0) + regime_bias
    prob = 1.0 / (1.0 + math.exp(-logit))
    raw_estimated_win_rate = round(prob * 100, 1)
    
    s["raw_estimated_win_rate"] = raw_estimated_win_rate
    win_rate = calibrate_estimated_win_rate(raw_estimated_win_rate, timing_class=None, is_etf=is_etf)
    
    hurst = s.get("hurst", 0.5)
    is_dead_fish = hurst < 0.45
    if is_dead_fish and not is_etf: 
        win_rate = max(5.0, round(win_rate * 0.4, 1))
    win_rate = min(98.0, max(2.0, win_rate))


        
    # 針對普通 ETF 與債券型 ETF 施加勝率上限限制 (Win Rate Cap)
    if is_etf:
        if is_bond:
            win_rate = min(75.0, win_rate)
        else:
            win_rate = min(78.0, win_rate)
    
    explode_prob = min(95.0, max(5.0, round(s.get("trig_score", 0.0) * 0.7 + vz * 8.0, 1)))
    if is_dead_fish and not is_etf: 
        explode_prob = min(20.0, explode_prob)
    
    drawdown_risk = min(98.0, max(2.0, round(position_60d * 60.0 + (1.0 - OBI_calc(obi)) * 30.0, 1)))
    
    is_inst_selling = (fc == 0 and sum(1 for x in s.get("foreign_buys_recent", []) if x < 0) >= 2) or \
                      (dc == 0 and is_etf and sum(1 for x in s.get("dealer_buys_recent", []) if x < 0) >= 2) or \
                      (tc == 0 and not is_etf and sum(1 for x in s.get("trust_buys_recent", []) if x < 0) >= 2)
                      
    if is_above_ma20 and (vz >= 1.5 or vol_ratio >= 1.5) and is_bull_regime and final_score >= 70 and not is_dead_fish:
        category = "🚀 主升起漲 (主升型)"
        trade_advice = "🟢 可重倉 / 順勢做多佈局"
        holding_days = 20
    elif not is_above_ma20 and is_inst_selling:
        category = "🔴 派發轉弱 (出貨型)"
        trade_advice = "🔴 不可進 / 趨勢轉空，避險離場" if is_etf else "🔴 不可進 / 趨勢轉空法人出貨，避險離場"
        holding_days = 0
    elif is_bull_regime and comp_score >= 50 and vz < 1.0:
        category = "🟡 盤整吸籌 (吸籌型)"
        trade_advice = "🟢 小試單 / 籌碼收集期，可分批逢低佈局"
        holding_days = 15
    elif is_above_ma20 and final_score >= 55 and not is_dead_fish:
        category = "🟢 趨勢轉強 (強勢型)"
        trade_advice = "🟢 小試單 / 多頭轉強，可小幅加碼"
        holding_days = 10
    elif not is_above_ma20 and final_score >= 45:
        category = "🔁 跌深反彈 (反彈型)"
        trade_advice = f"🟡 等回踩 / 均線空頭反彈，觀察 MA20" if is_etf else f"🟡 等回踩 / 均線空頭反彈，觀察 MA20 ({ma20})"
        holding_days = 3
    else:
        category = "⚠️ 假突破 (動能不足/隔天易回落)"
        trade_advice = "🔴 不可進 / 觀望防守，拒絕交易"
        holding_days = 0
        
    s["final_score"] = final_score
    s["continuation_score"] = final_score
    s["win_rate"] = win_rate
    s["estimated_win_rate"] = win_rate
    s["drawdown_risk"] = drawdown_risk
    s["category"] = category
    s["trade_advice"] = trade_advice
    s["holding_days"] = holding_days
    s["explode_prob"] = explode_prob

def calibrate_estimated_win_rate(raw_rate, timing_class=None, is_etf=False):
    raw_rate = min(98.0, max(2.0, float(raw_rate)))
    if timing_class is None:
        return round(50.0 + (raw_rate - 50.0) * 0.65, 1)
    
    if timing_class == "E_BREAKOUT":
        return round(90.0 + (raw_rate - 50.0) * 0.16, 1)
    elif timing_class == "A_BREAKOUT":
        return round(80.0 + (raw_rate - 50.0) * 0.18, 1)
    elif timing_class == "B_READY":
        return round(75.0 + (raw_rate - 50.0) * 0.08, 1)
    elif timing_class == "C_PULLBACK":
        return round(70.0 + (raw_rate - 50.0) * 0.08, 1)
    elif timing_class == "D_SILENT":
        return round(60.0 + (raw_rate - 50.0) * 0.18, 1)
    else:
        return round(50.0 + (raw_rate - 50.0) * 0.18, 1)

def OBI_calc(obi):
    return min(1.0, max(0.0, obi / 10.0))


def calculate_radar_phase_scores(s, is_etf=False):
    def clamp(value, low=0.0, high=100.0):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = low
        return min(high, max(low, value))

    comp_score = clamp(s.get("comp_score", 0.0))
    accum_score = clamp(s.get("accum_score", 0.0))
    readiness_score = clamp(s.get("readiness_score", 0.0))
    continuation_score = clamp(s.get("continuation_score", 0.0))
    drive_score = clamp(s.get("smart_drive_value", 0.0) * 10.0)
    trap_quality = clamp(100.0 - s.get("trap_bomb_rate", 50.0))
    sector_score = 50.0 if is_etf else clamp(s.get("sector_resonance", 0.0))

    raw_dark_horse = (
        comp_score * 0.20 +
        accum_score * 0.18 +
        readiness_score * 0.20 +
        drive_score * 0.14 +
        continuation_score * 0.14 +
        sector_score * 0.08 +
        trap_quality * 0.06
    )

    position_60d = clamp(s.get("position_60d", 0.5), 0.0, 1.0)
    breakout_pct = float(s.get("breakout_pct", 0.0) or 0.0)
    vol_ratio = float(s.get("vol_ratio", 1.0) or 1.0)

    if position_60d >= 0.85 and breakout_pct >= (2.0 if is_etf else 3.0) and vol_ratio >= 2.0:
        raw_dark_horse -= 8.0
    if s.get("timing_class") == "Decline":
        raw_dark_horse -= 6.0

    dark_horse_score = round(clamp(raw_dark_horse), 1)
    if dark_horse_score >= 85.0:
        dark_label = "黑馬主升候選"
    elif dark_horse_score >= 75.0:
        dark_label = "高潛力黑馬"
    elif dark_horse_score >= 65.0:
        dark_label = "值得追蹤"
    elif dark_horse_score >= 55.0:
        dark_label = "潛伏觀察"
    else:
        dark_label = "低優先"

    if breakout_pct <= -8.0:
        breakout_progress = 10.0
    elif breakout_pct <= -4.0:
        breakout_progress = 22.0
    elif breakout_pct <= -2.0:
        breakout_progress = 35.0
    elif breakout_pct <= 0.0:
        breakout_progress = 48.0
    elif breakout_pct <= (2.0 if is_etf else 3.0):
        breakout_progress = 62.0
    elif breakout_pct <= (4.0 if is_etf else 6.0):
        breakout_progress = 76.0
    else:
        breakout_progress = 88.0

    ma20 = float(s.get("ma20", 0.0) or 0.0)
    ma60 = float(s.get("ma60", 0.0) or 0.0)
    price = float(s.get("price", 0.0) or 0.0)
    trend_progress = 20.0
    if ma20 > 0 and price >= ma20:
        trend_progress += 35.0
    if ma60 > 0 and price >= ma60:
        trend_progress += 25.0
    if ma20 > 0 and ma60 > 0 and ma20 >= ma60:
        trend_progress += 20.0
    trend_progress = clamp(trend_progress)

    if vol_ratio < 0.8:
        volume_progress = 18.0
    elif vol_ratio < 1.0:
        volume_progress = 32.0
    elif vol_ratio < 1.2:
        volume_progress = 45.0
    elif vol_ratio < 1.5:
        volume_progress = 58.0
    elif vol_ratio < 2.5:
        volume_progress = 76.0
    else:
        volume_progress = 92.0

    timing_bonus = {
        "D_SILENT": 0.0,
        "C_PULLBACK": 3.0,
        "B_READY": 5.0,
        "A_BREAKOUT": 8.0,
        "E_BREAKOUT": 12.0,
    }.get(s.get("timing_class"), 0.0)

    completion = (
        breakout_progress * 0.45 +
        trend_progress * 0.20 +
        volume_progress * 0.20 +
        position_60d * 100.0 * 0.15 +
        timing_bonus
    )
    completion = round(clamp(completion), 1)

    if completion >= 90.0:
        completion_label = "第一波末段/過熱"
    elif completion >= 75.0:
        completion_label = "第一波主升"
    elif completion >= 60.0:
        completion_label = "第一波啟動"
    elif completion >= 40.0:
        completion_label = "蓄勢待發"
    else:
        completion_label = "潛伏整理"

    s["dark_horse_score"] = dark_horse_score
    s["dark_horse_label"] = dark_label
    s["stage1_completion_pct"] = completion
    s["stage1_completion_label"] = completion_label


def calculate_timing_entry(s, is_etf=False):
    price = s.get("price", 0.0)
    ma5 = s.get("ma5", 0.0)
    ma20 = s.get("ma20", 0.0)
    vz = s.get("vol_z", 0.0)
    vol_ratio = s.get("vol_ratio", 1.0)
    comp_score = s.get("comp_score", 0.0)
    position_60d = s.get("position_60d", 0.5)
    breakout_pct = s.get("breakout_pct", 0.0)
    fc = s.get("foreign_consecutive", 0)
    tc = s.get("trust_consecutive", 0)
    dc = s.get("dealer_consecutive", 0)
    hurst = s.get("hurst", 0.5)
    comp_days = s.get("comp_days", 0)
    volume_slope = s.get("volume_slope", 1.0)
    
    dist = abs(breakout_pct)
    
    # 獲取計算 Breakout Readiness Score (爆發準備度) 的因子
    h_val = s.get("hurst", 0.5)
    vc_val = s.get("volatility_contraction", 1.0)
    vr_val = s.get("vol_ratio_5d_20d", 1.0)
    
    # 1. Hurst 因子 (滿分 25)
    if h_val >= 0.55:
        h_score = 25.0
    elif h_val >= 0.50:
        h_score = 15.0
    else:
        h_score = 5.0
        
    # 2. 波動壓縮因子 (滿分 25)
    if vc_val <= 0.6:
        vc_score = 25.0
    elif vc_val <= 1.0:
        vc_score = 15.0
    elif vc_val <= 1.3:
        vc_score = 8.0
    else:
        vc_score = 2.0
        
    # 3. 量能萎縮因子 (滿分 25)
    if vr_val <= 0.8:
        vr_score = 25.0
    elif vr_val <= 1.1:
        vr_score = 15.0
    else:
        vr_score = 5.0
        
    # 4. 距離前高因子 (突破距離) (滿分 25)
    if dist <= 1.5:
        dist_score = 25.0
    elif dist <= 4.0:
        dist_score = 18.0
    elif dist <= 8.0:
        dist_score = 10.0
    else:
        dist_score = 3.0
        
    # 計算準備度總分 (0 ~ 100)
    readiness_score = h_score + vc_score + vr_score + dist_score
    readiness_score = min(100.0, max(0.0, readiness_score))
    s["readiness_score"] = round(readiness_score, 1)
    
    # 對應文字標籤
    if readiness_score >= 90.0:
        readiness_label = "⚡ 即將成熟"
    elif readiness_score >= 80.0:
        readiness_label = "🔥 發動窗"
    elif readiness_score >= 70.0:
        readiness_label = "⏳ 蓄勢整理"
    elif readiness_score >= 60.0:
        readiness_label = "💤 長期整理"
    else:
        readiness_label = "🧊 潛伏蓄能"
        
    trap_rate = 10.0
    if position_60d >= 0.8: trap_rate += 30.0
    limit_v_trap = 1.1 if is_etf else 1.2
    if vol_ratio < limit_v_trap: trap_rate += 25.0
    if hurst < 0.45 and not is_etf: trap_rate += 25.0
    if fc == 0 and (dc == 0 if is_etf else tc == 0): trap_rate += 10.0
    trap_rate = min(99.0, max(5.0, trap_rate))
    if is_etf:
        trap_rate = trap_rate * 0.3
    s["trap_bomb_rate"] = round(trap_rate, 1)

    global GLOBAL_TAIEX_20D_RETURN
    is_bond = is_etf and (s.get("code", "").endswith("B") or "債券" in s.get("theme", ""))
    
    if is_bond:
        bond_return_20d = 0.0
        closes = s.get("closes", [])
        if closes and len(closes) >= 20:
            bond_return_20d = (closes[-1] - closes[-20]) / closes[-20] * 100
        market_return_20d = GLOBAL_TAIEX_20D_RETURN if GLOBAL_TAIEX_20D_RETURN is not None else -5.0
        relative_strength = bond_return_20d - market_return_20d
        
        if relative_strength >= 5.0:
            rs_label = "🔥 避險爆發"
        elif relative_strength >= 2.0:
            rs_label = "🟢 避險轉強"
        elif relative_strength >= -1.0:
            rs_label = "🟡 避險對峙"
        else:
            rs_label = "💤 避險減弱"
        s["smart_drive"] = f"{rs_label} (RS={round(relative_strength, 2)})"
        drive_val = 0.0
    else:
        max_consec = max(fc, dc) if is_etf else max(fc, tc)
        drive_val = max_consec * volume_slope
        if max_consec == 0: drive_val = 0.5 * volume_slope
        
        if drive_val < 0.8:
            smart_drive = "💤 無主力"
        elif drive_val < 1.2:
            smart_drive = "⚪ 輕微"
        elif drive_val < 2.0:
            smart_drive = "🟡 溫和"
        elif drive_val < 5.0:
            smart_drive = "🟢 強"
        elif drive_val < 10.0:
            smart_drive = "🔥 極強"
        else:
            smart_drive = "⚡ 異常放大"
            
        s["smart_drive"] = f"{smart_drive} (Smart Drive={round(drive_val, 2)})" if not is_etf else f"{smart_drive} ({round(drive_val, 2)})"
    s["smart_drive_value"] = round(drive_val, 2)

    # 實作 MomentumBoost 爆量攻擊加分
    momentum_boost = 0.0
    change_pct = s.get("change_pct", 0.0)
    
    if vol_ratio > 3.0:
        momentum_boost += 10.0
    if vol_ratio > 5.0:
        momentum_boost += 20.0
    if change_pct > 6.0:
        momentum_boost += 10.0
    if change_pct > 9.0:
        momentum_boost += 20.0
        
    s["momentum_boost"] = momentum_boost
    
    # 重新決定原始勝率，加上加分 (但不超過 98)
    raw_win = s.get("raw_estimated_win_rate", 50.0)
    raw_score = raw_win + momentum_boost
    s["raw_score_boosted"] = raw_score

    # 五級時機分組條件判定
    # E級：量比 > 3 且 漲幅 > 4% 且 SmartDrive > 10
    is_moment_explode = False
    if vol_ratio > 3.0 and change_pct > 4.0 and drive_val > 10.0:
        is_moment_explode = True
    
    # A級：突破前高 (在合理範圍內) 且 量比 > 1.5
    is_breakout_confirm = False
    if (-2.0 <= breakout_pct <= 1.0) and vol_ratio > 1.5:
        is_breakout_confirm = True
        
    # B級：地量洗盤結束 (地量 valley_vol 出現)
    is_consolidation_complete = False
    if s.get("pattern2_valley_vol", False):
        is_consolidation_complete = True
        
    # C級：回檔買點 (回測 5MA/20MA)
    final_score = s.get("continuation_score", 50.0)
    limit_ma5 = 1.02 if is_etf else 1.03
    # 趨勢多頭回踩均線
    is_pullback = (final_score >= 50 or s.get("trend_score", 0.0) >= 15) and (price <= ma5 * limit_ma5 and price >= ma20 * 0.98) and (fc >= 2 or (dc >= 2 if is_etf else tc >= 2)) and (vz < 0.2)

    # 綜合決定 timing_class (雙軌：硬特徵條件 + 加分後分數)
    ma60 = s.get("ma60", 0.0)
    price_above_ma = price > ma20 and (price > ma60 if ma60 > 0 else True)
    
    if is_moment_explode or (raw_score >= 90.0 and change_pct > 2.0 and price_above_ma):
        s["timing_class"] = "E_BREAKOUT"
        s["timing_label"] = "🚀 E級：動能爆發"
        s["timing_advice"] = "🚀 動能爆發 / 突破前高且帶量大漲，主升段攻擊啟動，強勢追擊標的"
    elif is_breakout_confirm or (80.0 <= raw_score < 90.0):
        s["timing_class"] = "A_BREAKOUT"
        s["timing_label"] = "⚡ A級：突破確認"
        s["timing_advice"] = "🟢 突破確認 / 接近或突破前高，帶量推進"
    elif is_consolidation_complete or (75.0 <= raw_score < 80.0):
        s["timing_class"] = "B_READY"
        s["timing_label"] = "🟢 B級：整理完成"
        s["timing_advice"] = "🟢 整理完成 / 地量洗盤結束，籌碼收斂，隨時可能發動攻擊"
    elif is_pullback or (70.0 <= raw_score < 75.0):
        s["timing_class"] = "C_PULLBACK"
        s["timing_label"] = "🟡 C級：回檔低吸" if not is_etf else "🟡 C級：多頭回檔接 (安全低吸)"
        s["timing_advice"] = "🟡 趨勢多頭回踩 / 均線有撐且量能萎縮，適合限價逢低承接" if not is_etf else "🟡 趨勢多頭回踩 / 均線支撐強且量縮，分批逢低限價介入"
    else:
        if s.get("pool") == "SILENT" or (60.0 <= raw_score < 70.0):
            s["timing_class"] = "D_SILENT"
            s["timing_label"] = "🧊 D級：潛伏觀察"
            s["timing_advice"] = "🧊 盤整吸籌中 / 波動高度收縮，安全潛伏區"
        else:
            s["timing_class"] = "Decline"
            s["timing_label"] = "💤 整理觀望區"
            s["timing_advice"] = "💤 目前無明確交易時機，觀望整理"

    # 在函數最尾端寫入 countdown (發動成熟度)
    if s["timing_class"] == "E_BREAKOUT":
        s["countdown"] = "⚡ 動能確認"
    elif not is_etf:
        sec_res = float(s.get("sector_resonance", 0.0) or 0.0)
        trap_bomb = float(s.get("trap_bomb_rate", 0.0) or 0.0)
        
        warning_msg = None
        if trap_bomb > 60.0:
            warning_msg = "⚠️ 假突破風險過高"
        elif drive_val < 1.0 or sec_res < 60.0:
            warning_msg = "⚠️ 技術接近成熟，但缺乏主力與法人支持"
            
        if warning_msg and readiness_score >= 70.0:
            s["countdown"] = warning_msg
        else:
            s["countdown"] = f"{int(readiness_score)}分 ({readiness_label})"
    else:
        s["countdown"] = f"{int(readiness_score)}分 ({readiness_label})"

    # 觸發黑馬分數與波段完成度等評分計算
    calculate_radar_phase_scores(s, is_etf=is_etf)

def generate_trade_instruction(s, regime_status, is_etf=False):
    code = s.get("code", "")
    price = float(s.get("price", 0.0) or 0.0)
    ma5 = float(s.get("ma5", 0.0) or 0.0)
    ma20 = float(s.get("ma20", 0.0) or 0.0)
    max_20d = float(s.get("max_20d", 0.0) or 0.0)
    timing = s.get("timing_class", "Decline")
    est_win = float(s.get("estimated_win_rate", 50.0))
    trap = float(s.get("trap_bomb_rate", 50.0))
    vol_ratio = float(s.get("vol_ratio", 1.0))
    volume_slope = float(s.get("volume_slope", 1.0))
    breakout_pct = float(s.get("breakout_pct", 0.0))
    quality = float(s.get("data_quality_score", 100.0))
    position_60d = float(s.get("position_60d", 0.5))
    vol_z = float(s.get("vol_z", 0.0))
    is_bond = is_etf and (code.endswith("B") or "債券" in s.get("theme", ""))
    is_panic_regime = regime_status and "恐慌" in str(regime_status) and not is_bond

    def size_position(entry_price, stop_loss):
        risk_per_share = max(entry_price - stop_loss, 0.01)
        # 判斷是否為美股 (代碼不含數字)
        is_us = not any(char.isdigit() for char in code)
        if is_us:
            risk_cash = 150.0  # 約 5,000 元台幣 (匯率以 33 估算)
            max_position_cash = 4500.0  # 約 150,000 元台幣
        else:
            risk_cash = 5000.0  # 模擬 1,000,000 元帳戶，0.5% 風險
            max_position_cash = 150000.0  # 15% 上限
        risk_shares = int(risk_cash / risk_per_share)
        cash_shares = int(max_position_cash / entry_price) if entry_price > 0 else 0
        shares = max(0, min(risk_shares, cash_shares))
        return {"risk_per_share": round(risk_per_share, 2), "shares": shares, "lots": shares // 1000, "odd_lot_shares": shares % 1000}

    if price <= 0 or ma20 <= 0 or max_20d <= 0 or quality < 80:
        return {"action": "NO_TRADE", "action_label": "資料不足/品質欠佳"}

    if timing == "E_BREAKOUT":
        entry = round(price, 2)
        stop_loss = round(min(entry * 0.96, max(ma20 * 0.98, entry * 0.93)), 2)
        sizing = size_position(entry, stop_loss)
        if est_win >= 60:
            if sizing["shares"] > 0:
                risk_per = sizing["risk_per_share"]
                return {
                    "action": "BUY_STRONG", "action_label": "動能爆發強勢追擊", "limit_price": entry,
                    "stop_loss": stop_loss, "take_profit_1": round(entry + 2.0 * risk_per, 2), "take_profit_2": round(entry + 3.0 * risk_per, 2),
                    "reason": "E級動能爆發，強勢多頭確立", **sizing
                }
        return {"action": "WATCH", "action_label": "動能爆發觀察中"}

    if timing == "B_READY":
        entry = round(price, 2)
        stop_loss = round(min(entry * 0.95, max(ma20 * 0.98, entry * 0.93)), 2)
        sizing = size_position(entry, stop_loss)
        if est_win >= 55:
            if sizing["shares"] > 0:
                risk_per = sizing["risk_per_share"]
                return {
                    "action": "BUY_LIMIT", "action_label": "整理完成限價買進", "limit_price": entry,
                    "stop_loss": stop_loss, "take_profit_1": round(entry + 2.0 * risk_per, 2), "take_profit_2": round(entry + 3.0 * risk_per, 2),
                    "reason": "B級整理完成，準備發動", **sizing
                }
        return {"action": "WATCH", "action_label": "整理完成觀察中"}

    if trap >= 70:
        return {"action": "AVOID", "action_label": "空手不追，持有者減碼", "stop_loss": round(ma20 * 0.98, 2), "reason": f"假突破風險 ({round(trap, 1)}%)"}

    if is_panic_regime:
        if price < ma20 * 0.98 or position_60d >= 0.9:
            stop_loss_val = round(ma20 * 0.98, 2) if not is_etf else round(ma20 * 0.985, 2)
            return {"action": "SELL", "action_label": "大盤恐慌，持有者出場", "stop_loss": stop_loss_val, "reason": "大盤重挫破位，優先降險"}
        return {"action": "NO_TRADE", "action_label": "大盤恐慌狀態，停止新倉"}

    if timing == "A_BREAKOUT":
        trigger = round(max_20d * 1.003, 2)
        limit_price = round(trigger * (1.008 if is_etf else 1.01), 2)
        risk_range = min(0.06 if is_etf else 0.07, max(0.02 if is_etf else 0.03, float(s.get("price_range_20d", 10.0)) / 200.0))
        stop_loss = round(min(trigger * 0.99, max(ma20 * 0.98, trigger * (1.0 - risk_range))), 2)
        sizing = size_position(trigger, stop_loss)
        
        limit_win = 56 if is_etf else 58
        limit_v = 1.1 if is_etf else 1.2
        limit_break = -1.5 if is_etf else -2.0
        if est_win >= limit_win and trap <= 45 and limit_break <= breakout_pct <= 1.0 and (vol_ratio >= limit_v or volume_slope >= limit_v):
            if sizing["shares"] > 0:
                risk_per = sizing["risk_per_share"]
                return {
                    "action": "BUY_STOP_LIMIT", "action_label": "突破停限價買進", "trigger_price": trigger, "limit_price": limit_price,
                    "stop_loss": stop_loss, "take_profit_1": round(trigger + 2.0 * risk_per, 2), "take_profit_2": round(trigger + 3.0 * risk_per, 2),
                    "reason": "A級突破條件成立", **sizing
                }
        return {"action": "WATCH", "action_label": "觀察突破確認", "alert_price": trigger}

    if timing == "C_PULLBACK":
        entry = round(min(price, ma5), 2)
        stop_loss = round(min(entry * 0.99, max(ma20 * 0.98 if is_etf else ma20 * 0.97, entry * 0.95 if is_etf else entry * 0.94)), 2)
        sizing = size_position(entry, stop_loss)
        if est_win >= 55 and price >= ma20 * 0.98 and vol_z < 0.3:
            if sizing["shares"] > 0:
                risk_per = sizing["risk_per_share"]
                return {
                    "action": "BUY_LIMIT", "action_label": "回檔限價買進", "limit_price": entry,
                    "stop_loss": stop_loss, "take_profit_1": round(entry + 2.0 * risk_per, 2), "take_profit_2": round(entry + 3.0 * risk_per, 2),
                    "reason": "C級回檔支撐確認", **sizing
                }
        return {"action": "WATCH", "action_label": "等待回檔條件", "alert_price": round(ma5, 2)}

    if timing == "D_SILENT":
        return {"action": "WATCH", "action_label": "潛伏觀察", "alert_price": round(max_20d * 1.002, 2)}

    return {"action": "WATCH", "action_label": "整理觀望中"}

# ----------------- 特徵解析引擎 (一體化) -----------------
def analyze_single_security(code, name, bulk_daily=None, bulk_inst=None, date_str=None, use_cache=True, is_market_active=False, bulk_realtime=None, bulk_is_today=True, market_60d_return=0.0, force=False):
    is_etf = code.startswith('00')
    
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
        
    # 獲取當日即時報價/收盤數據 (twse)
    twse = None
    # 只有在非盤中 (已收盤) 且批量數據確實是今日數據時，才優先複用批量收盤數據
    if not is_market_active and bulk_is_today:
        if bulk_daily and code in bulk_daily:
            b_data = bulk_daily[code]
            price = b_data.get("close", 0.0)
            yest_close = b_data.get("yest_close", 0.0)
            # 容錯：若最新價等於昨日收盤價且不是 ETF，可能是除權息標的（證交所批量行情中漲跌記號標為 X 且漲跌幅歸零）
            # 此時不複用批量，強制往下走即時 API 以取得正確的昨收與漲跌幅
            if price > 0 and yest_close > 0 and (price != yest_close or is_etf):
                amplitude = (b_data.get("high", 0.0) - b_data.get("low", 0.0)) / yest_close * 100 if yest_close > 0 else 0.0
                twse = {
                    "price": price,
                    "yest_close": yest_close,
                    "open": b_data.get("open", 0.0),
                    "high": b_data.get("high", 0.0),
                    "low": b_data.get("low", 0.0),
                    "today_vol": b_data.get("volume", 0),
                    "bid_vol": 1.0,
                    "ask_vol": 1.0,
                    "amplitude": amplitude,
                    "name": b_data.get("name", name)
                }
            
    # 如果是盤中交易時間，或者是批量資料中不存在，則強制獲取即時報價
    if not twse:
        # A. 優先嘗試從 ScanWorker 一次性抓取好的 bulk_realtime map 中拿資料，這是盤中最省時間且絕不被封鎖的做法
        if bulk_realtime and code in bulk_realtime:
            rt_data = bulk_realtime[code]
            if rt_data.get("price", 0.0) > 0:
                twse = rt_data
                
        if not twse:
            # B. 嘗試從記憶體即時快取中讀取 (3分鐘快取，以防盤中重複高頻點擊)
            import time as pytime
            now_time = pytime.time()
            cached_rt = GLOBAL_REALTIME_CACHE.get(code)
            if use_cache and cached_rt and (now_time - cached_rt.get("timestamp", 0) < 180.0):
                twse = cached_rt.get("twse")
                
            if not twse:
                # C. 最後的備用降級手段：呼叫單檔即時 API 抓取
                twse = fetch_twse_realtime_data(code)
                
            # D. 超強容災備份：如果 TWSE API 全面封鎖 (price <= 0)，則從 Yahoo Finance Chart 獲取盤中即時資料
            if not twse or twse.get("price", 0.0) <= 0:
                yahoo_rt = fetch_yahoo_realtime_backup(code)
                if yahoo_rt and yahoo_rt.get("price", 0.0) > 0:
                    yahoo_rt["name"] = name
                    twse = yahoo_rt
                    logging.info(f"TWSE 接口受限，成功從 Yahoo Finance 獲取備份即時報價: {code} ({name}) -> {twse['price']}")
                    
            if twse and twse.get("price", 0.0) > 0:
                GLOBAL_REALTIME_CACHE[code] = {"timestamp": now_time, "twse": twse}
        
    # 備份防禦機制：如果即時資料抓取失敗且有批量資料 (如盤中網路瞬斷)，回退到批量昨日收盤行情
    if (not twse or twse.get("price", 0.0) <= 0) and bulk_daily and code in bulk_daily:
        b_data = bulk_daily[code]
        price = b_data.get("close", 0.0)
        yest_close = b_data.get("yest_close", 0.0)
        if price > 0 and yest_close > 0:
            amplitude = (b_data.get("high", 0.0) - b_data.get("low", 0.0)) / yest_close * 100 if yest_close > 0 else 0.0
            twse = {
                "price": price,
                "yest_close": yest_close,
                "open": b_data.get("open", 0.0),
                "high": b_data.get("high", 0.0),
                "low": b_data.get("low", 0.0),
                "today_vol": b_data.get("volume", 0),
                "bid_vol": 1.0,
                "ask_vol": 1.0,
                "amplitude": amplitude,
                "name": b_data.get("name", name)
            }
            
    real_name = twse.get("name")
    if real_name and real_name.strip() and real_name != code and not real_name.startswith("股票 "):
        name = real_name.strip()
        
    price = twse["price"]
    yest_close = twse["yest_close"]
    if price <= 0 or yest_close <= 0: return None
    
    change_val = price - yest_close
    change_pct = (price - yest_close) / yest_close * 100
    
    # 獲取 Blave 分點籌碼集中度
    broker_concentration = None
    if not is_etf:
        if use_cache and code in GLOBAL_INST_CACHE:
            cache_data = GLOBAL_INST_CACHE[code]
            c_last_date = cache_data.get("last_date")
            if c_last_date == date_str:
                broker_concentration = cache_data.get("broker_concentration")
        if broker_concentration is None:
            broker_concentration = fetch_blave_broker_concentration(code, date_str)

    # 獲取法人數據 (flow)
    flow = None
    if use_cache and code in GLOBAL_INST_CACHE:
        cache_data = GLOBAL_INST_CACHE[code]
        c_last_date = cache_data.get("last_date")
        if c_last_date == date_str:
            flow = cache_data.get("flow")
            broker_concentration = cache_data.get("broker_concentration")
        elif c_last_date and get_date_diff_days(c_last_date, date_str) <= 5:
            import copy
            flow = copy.deepcopy(cache_data.get("flow"))
            formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"
            if flow and ("dates" in flow) and (not flow["dates"] or flow["dates"][0] != formatted_date):
                if is_market_active:
                    # 盤中：今日法人交易資料暫設為 0 (因為尚未收盤公佈)
                    flow["dates"].insert(0, formatted_date)
                    flow["foreign_buys"].insert(0, 0)
                    flow["trust_buys"].insert(0, 0)
                    flow["dealer_buys"].insert(0, 0)
                    flow["volumes"].insert(0, twse["today_vol"])
                    flow["changes"].insert(0, change_pct)
                else:
                    # 盤後：從今日批量法人中獲取
                    inst = bulk_inst.get(code, {}) if bulk_inst else {}
                    flow["dates"].insert(0, formatted_date)
                    flow["foreign_buys"].insert(0, inst.get("foreign_net", 0))
                    flow["trust_buys"].insert(0, inst.get("trust_net", 0))
                    flow["dealer_buys"].insert(0, inst.get("dealer_net", 0))
                    flow["volumes"].insert(0, twse["today_vol"])
                    flow["changes"].insert(0, change_pct)
                
                # 限制長度
                for k in flow.keys():
                    if len(flow[k]) > 40:
                        flow[k] = flow[k][:40]
                        
                # 盤中不將今日數據寫回全域快取字典，避免污染；盤後且批量法人存在且為今日數據才寫入快取字典
                if not is_market_active and bulk_is_today and bulk_inst:
                    GLOBAL_INST_CACHE[code] = {"last_date": date_str, "flow": flow, "broker_concentration": broker_concentration}
                
    if not flow:
        flow = fetch_yahoo_institutional_flow(code)
        if flow and flow.get("dates"):
            # 如果是盤中，也需要動態把今天的即時成交量與漲跌幅插入最前端
            if is_market_active:
                import copy
                flow = copy.deepcopy(flow)
                formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"
                if flow["dates"] and flow["dates"][0] != formatted_date:
                    flow["dates"].insert(0, formatted_date)
                    flow["foreign_buys"].insert(0, 0)
                    flow["trust_buys"].insert(0, 0)
                    flow["dealer_buys"].insert(0, 0)
                    flow["volumes"].insert(0, twse["today_vol"])
                    flow["changes"].insert(0, change_pct)
                    for k in flow.keys():
                        if len(flow[k]) > 40:
                            flow[k] = flow[k][:40]
            
            # 只有在非盤中 (已收盤) 且批量法人存在且為今日數據時，才將今日數據寫回全域快取字典
            if not is_market_active and bulk_is_today and bulk_inst:
                GLOBAL_INST_CACHE[code] = {"last_date": date_str, "flow": flow, "broker_concentration": broker_concentration}
        time.sleep(0.2)
        
    # 獲取歷史 K 線 (closes)
    closes = None
    if use_cache and code in GLOBAL_HISTORY_CACHE:
        cache_data = GLOBAL_HISTORY_CACHE[code]
        c_last_date = cache_data.get("last_date")
        if c_last_date == date_str:
            closes = cache_data.get("closes")
        elif c_last_date and get_date_diff_days(c_last_date, date_str) <= 5:
            closes = list(cache_data.get("closes", []))
            today_close = price
            if today_close > 0:
                closes.append(today_close)
                if len(closes) > 150:
                    closes = closes[-150:]
                # 只有在非盤中 (已收盤) 且批量行情存在且為今日數據時，才將今日收盤後的 K 線寫回全域快取
                if not is_market_active and bulk_is_today and bulk_daily:
                    GLOBAL_HISTORY_CACHE[code] = {"last_date": date_str, "closes": closes}
                
    if not closes:
        closes = fetch_historical_closes(code, price)
        # 只有在非盤中 (已收盤) 且批量行情存在且為今日數據時，才將今日收盤後的 K 線寫回全域快取
        if not is_market_active and bulk_is_today and bulk_daily and closes:
            GLOBAL_HISTORY_CACHE[code] = {"last_date": date_str, "closes": closes}
        time.sleep(0.2)

    if closes:
        prices_history = closes[::-1]
        has_ma = True
    else:
        prices_history = []
        current_p = price
        for chg in flow["changes"]:
            prices_history.append(current_p)
            current_p = current_p / (1 + chg / 100.0)
        has_ma = False

    prices_history = [p for p in prices_history if p and p > 0]
    if len(prices_history) < 10: return None
    if not force and not check_trend_alignment(prices_history, is_reverse=False):
        return None

    p_today = prices_history[0]
    p_60d = prices_history[min(len(prices_history)-1, 60)]
    stock_60d_return = (p_today - p_60d) / p_60d * 100 if p_60d > 0 else 0.0
    excess_return = stock_60d_return - market_60d_return
    
    ma5 = sum(prices_history[:5]) / 5 if len(prices_history) >= 5 else price
    ma20 = sum(prices_history[:20]) / 20 if len(prices_history) >= 20 else price
    ma60 = sum(prices_history[:60]) / 60 if len(prices_history) >= 60 else (sum(prices_history)/len(prices_history) if prices_history else price)
    
    comp_days = 0
    for idx in range(len(prices_history)):
        p_sub = prices_history[idx:]
        v_sub = flow["volumes"][idx:] if idx < len(flow["volumes"]) else []
        if len(p_sub) < 20 or len(v_sub) < 20: break
        cv_5d = calculate_std(p_sub[:5]) / (sum(p_sub[:5])/5) if sum(p_sub[:5]) > 0 else 0
        cv_20d = calculate_std(p_sub[:20]) / (sum(p_sub[:20])/20) if sum(p_sub[:20]) > 0 else 1.0
        cv_r = cv_5d / cv_20d if cv_20d > 0 else 1.0
        vol_5ma = sum(v_sub[:5]) / 5
        vol_20ma = sum(v_sub[:20]) / 20
        v_r = vol_5ma / vol_20ma if vol_20ma > 0 else 1.0
        if cv_r <= 1.2 and v_r <= 1.2: comp_days += 1
        else: break

    bull_days = 0
    for idx in range(len(prices_history)):
        p_sub = prices_history[idx:]
        if len(p_sub) < 60: break
        if sum(p_sub[:20])/20 >= sum(p_sub[:60])/60: bull_days += 1
        else: break
        
    intraday, now_tw, elapsed_minutes = is_market_open()
    subset_v = flow["volumes"][:20]
    vol_20ma = sum(subset_v) / len(subset_v) if subset_v else 1.0
    vol_std = calculate_std(flow["volumes"][:20])
    
    raw_today_vol = twse["today_vol"]
    projected_vol = raw_today_vol * (270.0 / elapsed_minutes) if (intraday and elapsed_minutes < 270.0) else raw_today_vol
    
    vol_z = (projected_vol - vol_20ma) / vol_std if vol_std > 0 else 0.0
    vol_ratio = projected_vol / vol_20ma if vol_20ma > 0 else 1.0
    volume_slope = (raw_today_vol / max(15.0, elapsed_minutes)) / (vol_20ma / 270.0) if vol_20ma > 0 else 1.0
    if intraday:
        if elapsed_minutes < 30.0:
            volume_slope = min(volume_slope, vol_ratio * 1.8)
        elif elapsed_minutes < 60.0:
            volume_slope = min(volume_slope, vol_ratio * 2.5)
        elif elapsed_minutes < 120.0:
            volume_slope = min(volume_slope, vol_ratio * 3.5)
    
    p_20d = prices_history[:20]
    max_20d = max(p_20d)
    min_20d = min(p_20d)
    price_range_20d = (max_20d - min_20d) / min_20d * 100
    
    p_60d = prices_history[:min(len(flow["dates"]), 60)]
    position_60d = (price - min(p_60d)) / (max(p_60d) - min(p_60d)) if (max(p_60d) - min(p_60d)) > 0 else 0.5
    
    obi_smoothed = min(10.0, twse["bid_vol"] / (twse["ask_vol"] + 5.0))
    bid_ask_ratio = twse["bid_vol"] / twse["ask_vol"] if twse["ask_vol"] > 0 else 1.0
    
    start_idx = 1 if is_market_active else 0
    foreign_consecutive = next((i for i, v in enumerate(flow["foreign_buys"][start_idx:]) if v <= 0), len(flow["foreign_buys"][start_idx:]))
    trust_consecutive = next((i for i, v in enumerate(flow["trust_buys"][start_idx:]) if v <= 0), len(flow["trust_buys"][start_idx:]))
    dealer_consecutive = next((i for i, v in enumerate(flow["dealer_buys"][start_idx:]) if v <= 0), len(flow["dealer_buys"][start_idx:]))
    
    price_slope = calculate_price_slope(prices_history)
    volatility_contraction = calculate_volatility_contraction(prices_history)
    hurst = calculate_hurst(prices_history)
    vol_ratio_5d_20d = (sum(flow["volumes"][:5])/5) / vol_20ma if vol_20ma > 0 else 1.0
    
    # 四大特徵型態
    ma_spread = (max(ma5, ma20, ma60) - min(ma5, ma20, ma60)) / ma20 if ma20 > 0 else 1.0
    pattern1_ma_align = (ma_spread <= 0.05) and (price >= max(ma5, ma20, ma60)) and (change_pct > 0.1) and (vol_ratio > 1.1)
    
    pattern2_valley_vol = False
    if len(flow["volumes"]) >= 15 and vol_20ma > 0:
        min_v = min(flow["volumes"][1:15])
        pattern2_valley_vol = (min_v / vol_20ma <= 0.6) and (projected_vol >= min_v * 1.25) and (change_pct > 0.1) and (vol_ratio >= 0.8)
        
    pattern3_golden_pit = False
    if len(prices_history) >= 30:
        has_pit = any(prices_history[k] < (sum(prices_history[k:k+20])/20) * (0.975 if is_etf else 0.965) for k in range(2, 8))
        pattern3_golden_pit = has_pit and (price >= ma20 * 0.995) and (price >= ma5) and (change_pct > -0.5)
        
    upper_shadow = (twse["high"] - max(twse["open"], price)) / price * 100 if price > 0 else 0.0
    b_pct = (price - max_20d) / max_20d * 100 if max_20d > 0 else 0.0
    dist_to_break = abs(b_pct)
    pattern4_test_pressure = (upper_shadow >= (0.5 if is_etf else 1.5)) and (vol_ratio <= 0.95) and (dist_to_break <= 15.0)

    # 強制唯一型態判定，防範重複出現在多個看板中
    p1_score = 0.0
    p2_score = 0.0
    p3_score = 0.0
    p4_score = 0.0
    
    if pattern1_ma_align:
        p1_score = max(0.0, 100.0 - (ma_spread * 1000.0)) + min(50.0, vol_ratio * 10.0)
    if pattern2_valley_vol:
        v_ratio = 1.0
        if len(flow["volumes"]) >= 15 and vol_20ma > 0:
            min_v = min(flow["volumes"][1:15])
            v_ratio = min_v / vol_20ma
        p2_score = 50.0 + max(0.0, (1.0 - v_ratio) * 50.0)
    if pattern3_golden_pit:
        p3_score = 82.0
    if pattern4_test_pressure:
        p4_score = 70.0 + min(30.0, upper_shadow * 6.0)
        
    max_score = max(p1_score, p2_score, p3_score, p4_score)
    if max_score > 0.0:
        if p1_score < max_score: pattern1_ma_align = False
        if p2_score < max_score: pattern2_valley_vol = False
        if p3_score < max_score: pattern3_golden_pit = False
        if p4_score < max_score: pattern4_test_pressure = False


    if not is_etf:
        fund_data = fetch_clean_fundamentals(code, is_us=False)
    else:
        fund_data = {
            "revenue_yoy": 0.0,
            "gross_margin": 0.0,
            "prev_gross_margin": 0.0,
            "gross_margin_increased": False,
            "latest_eps": 0.0,
            "eps_yoy": 0.0,
            "fundamental_score": 60.0
        }

    # 特徵封裝
    s = {
        "code": code, "name": name, "price": price, "yest_close": yest_close, "change_pct": change_pct, "change_val": change_val,
        "today_vol": twse["today_vol"], "projected_vol": projected_vol, "vol_20ma": vol_20ma, "vol_ratio": vol_ratio, "vol_z": vol_z,
        "volume_slope": volume_slope, "price_range_20d": price_range_20d, "max_20d": max_20d, "amplitude": twse["amplitude"],
        "bid_ask_ratio": bid_ask_ratio, "obi_smoothed": obi_smoothed, "position_60d": position_60d,
        "foreign_consecutive": foreign_consecutive, "trust_consecutive": trust_consecutive, "dealer_consecutive": dealer_consecutive,
        "foreign_buys_recent": flow["foreign_buys"][:3], "trust_buys_recent": flow["trust_buys"][:3], "dealer_buys_recent": flow["dealer_buys"][:3],
        "price_slope": price_slope, "volatility_contraction": volatility_contraction, "hurst": hurst, "vol_ratio_5d_20d": vol_ratio_5d_20d,
        "data_quality_score": 100.0 - (20.0 if not has_ma else 0.0), "ma5": ma5, "ma20": ma20, "ma60": ma60, "comp_days": comp_days, "bull_days": bull_days,
        "ma_spread": ma_spread, "upper_shadow": upper_shadow,
        "pattern1_ma_align": pattern1_ma_align, "pattern2_valley_vol": pattern2_valley_vol,
        "pattern3_golden_pit": pattern3_golden_pit, "pattern4_test_pressure": pattern4_test_pressure,
        "broker_concentration": broker_concentration,
        "fundamental_score": fund_data.get("fundamental_score", 50.0),
        "revenue_yoy": fund_data.get("revenue_yoy", 0.0),
        "gross_margin": fund_data.get("gross_margin", 0.0),
        "eps_yoy": fund_data.get("eps_yoy", 0.0),
        "stock_60d_return": stock_60d_return,
        "excess_return": excess_return,
        "rs_score": 50.0
    }
    
    # 題材與類型
    if is_etf:
        if code.endswith('A') or "主動" in name: etf_t = "主動型股票ETF"
        elif code.endswith('B') or "債券" in name: etf_t = "債券型ETF"
        else: etf_t = "被動型股票ETF"
        s["theme"] = f"{etf_t} | {ETF_THEME_MAP.get(code, {}).get('theme', '其他ETF')}"
    else:
        s["theme"] = AI_STOCK_MAP.get(code, {}).get("theme", "個股自選題材")
        
    s["pool"] = "HOT"
    return s

def analyze_us_stock(ticker, name, bulk_quotes=None, use_cache=True, is_market_active=False, market_60d_return=0.0, force=False):
    """
    美股個股分析引擎。
    結構模仿 analyze_single_security() 但替換數據源。
    回傳格式與台股完全一致的 dict s。
    """
    date_str = datetime.now().strftime("%Y%m%d")
    
    # 獲取當日即時報價/收盤數據
    quote = None
    if bulk_quotes and ticker in bulk_quotes:
        quote = bulk_quotes[ticker]
        
    # 如果是盤中交易時間，或者是批量資料中不存在，則嘗試從快取讀取
    if not quote:
        now_time = time.time()
        cached_rt = GLOBAL_US_REALTIME_CACHE.get(ticker)
        if use_cache and cached_rt and (now_time - cached_rt.get("timestamp", 0) < 180.0):
            quote = cached_rt.get("quote")
            
    # 如果仍然沒有，或者需要下載歷史數據，我們可以直接呼叫單檔歷史 K 線
    closes_data = None
    if use_cache and ticker in GLOBAL_US_HISTORY_CACHE:
        cache_data = GLOBAL_US_HISTORY_CACHE[ticker]
        c_last_date = cache_data.get("last_date")
        if c_last_date == date_str:
            closes_data = cache_data.get("closes")

    if not closes_data:
        closes_data = fetch_us_historical_closes(ticker)
        if closes_data and not is_market_active:
            GLOBAL_US_HISTORY_CACHE[ticker] = {"last_date": date_str, "closes": closes_data}

    if not closes_data:
        logging.warning(f"無法獲取美股 {ticker} 歷史 K 線")
        return None
        
    # 如果沒有 bulk 報價，我們從最新一筆歷史 K 線中提取
    if not quote:
        latest = closes_data[0]
        yest = closes_data[1] if len(closes_data) > 1 else latest
        quote = {
            "name": name,
            "close": latest["close"],
            "open": latest["open"],
            "high": latest["high"],
            "low": latest["low"],
            "yest_close": yest["close"],
            "volume": latest["volume"],
            "change_pct": (latest["close"] - yest["close"]) / yest["close"] * 100 if yest["close"] > 0 else 0.0,
            "market_cap": 0
        }
        GLOBAL_US_REALTIME_CACHE[ticker] = {"timestamp": time.time(), "quote": quote}

    real_name = quote.get("name")
    if real_name and real_name.strip() and real_name != ticker:
        name = real_name.strip()
        
    price = quote["close"]
    yest_close = quote["yest_close"]
    if price <= 0 or yest_close <= 0:
        return None
        
    change_val = price - yest_close
    change_pct = quote["change_pct"]
    
    # 建立歷史價格與成交量數列
    prices_history = [x["close"] for x in closes_data[::-1] if x["close"] > 0]
    volumes_history = [x["volume"] for x in closes_data[::-1]]
    
    if len(prices_history) < 10:
        return None
    if not force and not check_trend_alignment(prices_history, is_reverse=True):
        return None

    p_today = prices_history[-1]
    p_60d = prices_history[-min(len(prices_history), 60)]
    stock_60d_return = (p_today - p_60d) / p_60d * 100 if p_60d > 0 else 0.0
    excess_return = stock_60d_return - market_60d_return
        
    ma5 = sum(prices_history[-5:]) / 5 if len(prices_history) >= 5 else price
    ma20 = sum(prices_history[-20:]) / 20 if len(prices_history) >= 20 else price
    ma60 = sum(prices_history[-60:]) / 60 if len(prices_history) >= 60 else (sum(prices_history)/len(prices_history))
    
    # 籌碼指標替代：從歷史 K 線計算
    vol_flow = fetch_us_volume_flow(closes_data)
    buy_pressure_days = vol_flow["buy_pressure_days"]
    vol_trend_ratio = vol_flow["vol_trend_ratio"]
    
    # 計算 compression days 與 bull days
    comp_days = 0
    for idx in range(len(prices_history)):
        p_sub = prices_history[idx:]
        v_sub = volumes_history[idx:]
        if len(p_sub) < 20 or len(v_sub) < 20:
            break
        cv_5d = calculate_std(p_sub[:5]) / (sum(p_sub[:5])/5) if sum(p_sub[:5]) > 0 else 0
        cv_20d = calculate_std(p_sub[:20]) / (sum(p_sub[:20])/20) if sum(p_sub[:20]) > 0 else 1.0
        cv_r = cv_5d / cv_20d if cv_20d > 0 else 1.0
        vol_5ma = sum(v_sub[:5]) / 5
        vol_20ma = sum(v_sub[:20]) / 20
        v_r = vol_5ma / vol_20ma if vol_20ma > 0 else 1.0
        if cv_r <= 1.2 and v_r <= 1.2:
            comp_days += 1
            
    bull_days = 0
    for idx in range(len(prices_history)):
        p_sub = prices_history[idx:]
        if len(p_sub) < 60:
            break
        if sum(p_sub[:20])/20 >= sum(p_sub[:60])/60:
            bull_days += 1
        else:
            break

    # 計算美股盤中成交量投影
    intraday, now_et, elapsed_minutes = is_us_market_open()
    subset_v = volumes_history[-20:]
    vol_20ma = sum(subset_v) / len(subset_v) if subset_v else 1.0
    vol_std = calculate_std(subset_v)
    
    raw_today_vol = quote["volume"]
    projected_vol = raw_today_vol * (390.0 / elapsed_minutes) if (intraday and elapsed_minutes < 390.0) else raw_today_vol
    
    vol_z = (projected_vol - vol_20ma) / vol_std if vol_std > 0 else 0.0
    vol_ratio = projected_vol / vol_20ma if vol_20ma > 0 else 1.0
    volume_slope = (raw_today_vol / max(15.0, elapsed_minutes)) / (vol_20ma / 390.0) if vol_20ma > 0 else 1.0
    if intraday:
        if elapsed_minutes < 30.0:
            volume_slope = min(volume_slope, vol_ratio * 1.8)
        elif elapsed_minutes < 60.0:
            volume_slope = min(volume_slope, vol_ratio * 2.5)
        elif elapsed_minutes < 120.0:
            volume_slope = min(volume_slope, vol_ratio * 3.5)
            
    p_20d = prices_history[-20:]
    max_20d = max(p_20d)
    min_20d = min(p_20d)
    price_range_20d = (max_20d - min_20d) / min_20d * 100
    
    p_60d = prices_history[-min(len(prices_history), 60):]
    position_60d = (price - min(p_60d)) / (max(p_60d) - min(p_60d)) if (max(p_60d) - min(p_60d)) > 0 else 0.5
    
    obi_smoothed = 5.0
    bid_ask_ratio = 1.0
    
    price_slope = calculate_price_slope(prices_history[::-1])
    volatility_contraction = calculate_volatility_contraction(prices_history[::-1])
    hurst = calculate_hurst(prices_history[::-1])
    vol_ratio_5d_20d = vol_trend_ratio
    
    # 四大特徵型態
    ma_spread = (max(ma5, ma20, ma60) - min(ma5, ma20, ma60)) / ma20 if ma20 > 0 else 1.0
    pattern1_ma_align = (ma_spread <= 0.05) and (price >= max(ma5, ma20, ma60)) and (change_pct > 0.1) and (vol_ratio > 1.1)
    
    pattern2_valley_vol = False
    if len(volumes_history) >= 15 and vol_20ma > 0:
        min_v = min(volumes_history[-15:-1])
        pattern2_valley_vol = (min_v / vol_20ma <= 0.6) and (projected_vol >= min_v * 1.25) and (change_pct > 0.1) and (vol_ratio >= 0.8)
        
    pattern3_golden_pit = False
    if len(prices_history) >= 30:
        has_pit = any(prices_history[-k-1] < (sum(prices_history[-k-21:-k-1])/20) * 0.965 for k in range(2, 8))
        pattern3_golden_pit = has_pit and (price >= ma20 * 0.995) and (price >= ma5) and (change_pct > -0.5)
        
    upper_shadow = (quote["high"] - max(quote["open"], price)) / price * 100 if price > 0 else 0.0
    b_pct = (price - max_20d) / max_20d * 100 if max_20d > 0 else 0.0
    dist_to_break = abs(b_pct)
    pattern4_test_pressure = (upper_shadow >= 1.5) and (vol_ratio <= 0.95) and (dist_to_break <= 15.0)

    p1_score = 0.0
    p2_score = 0.0
    p3_score = 0.0
    p4_score = 0.0
    
    if pattern1_ma_align:
        p1_score = max(0.0, 100.0 - (ma_spread * 1000.0)) + min(50.0, vol_ratio * 10.0)
    if pattern2_valley_vol:
        v_ratio = 1.0
        if len(volumes_history) >= 15 and vol_20ma > 0:
            min_v = min(volumes_history[-15:-1])
            v_ratio = min_v / vol_20ma
        p2_score = 50.0 + max(0.0, (1.0 - v_ratio) * 50.0)
    if pattern3_golden_pit:
        p3_score = 82.0
    if pattern4_test_pressure:
        p4_score = 70.0 + min(30.0, upper_shadow * 6.0)
        
    max_score = max(p1_score, p2_score, p3_score, p4_score)
    if max_score > 0.0:
        if p1_score < max_score: pattern1_ma_align = False
        if p2_score < max_score: pattern2_valley_vol = False
        if p3_score < max_score: pattern3_golden_pit = False
        if p4_score < max_score: pattern4_test_pressure = False

    fund_data = fetch_clean_fundamentals(ticker, is_us=True)

    s = {
        "code": ticker, "name": name, "price": price, "yest_close": yest_close, "change_pct": change_pct, "change_val": change_val,
        "today_vol": quote["volume"], "projected_vol": projected_vol, "vol_20ma": vol_20ma, "vol_ratio": vol_ratio, "vol_z": vol_z,
        "volume_slope": volume_slope, "price_range_20d": price_range_20d, "max_20d": max_20d, "amplitude": (quote["high"]-quote["low"])/yest_close*100,
        "bid_ask_ratio": bid_ask_ratio, "obi_smoothed": obi_smoothed, "position_60d": position_60d,
        
        "foreign_consecutive": buy_pressure_days,
        "trust_consecutive": 0,
        "dealer_consecutive": 0,
        "foreign_buys_recent": [buy_pressure_days, 0, 0],
        "trust_buys_recent": [0, 0, 0],
        "dealer_buys_recent": [0, 0, 0],
        
        "price_slope": price_slope, "volatility_contraction": volatility_contraction, "hurst": hurst, "vol_ratio_5d_20d": vol_ratio_5d_20d,
        "data_quality_score": 100.0, "ma5": ma5, "ma20": ma20, "ma60": ma60, "comp_days": comp_days, "bull_days": bull_days,
        "ma_spread": ma_spread, "upper_shadow": upper_shadow,
        "pattern1_ma_align": pattern1_ma_align, "pattern2_valley_vol": pattern2_valley_vol,
        "pattern3_golden_pit": pattern3_golden_pit, "pattern4_test_pressure": pattern4_test_pressure,
        "broker_concentration": None,
        "vol_trend_ratio": vol_trend_ratio,
        "fundamental_score": fund_data.get("fundamental_score", 50.0),
        "revenue_yoy": fund_data.get("revenue_yoy", 0.0),
        "gross_margin": fund_data.get("gross_margin", 0.0),
        "eps_yoy": fund_data.get("eps_yoy", 0.0),
        "stock_60d_return": stock_60d_return,
        "excess_return": excess_return,
        "rs_score": 50.0
    }
    
    s["theme"] = US_STOCK_MAP.get(ticker, {}).get("theme", "美股個股自選題材")
    s["pool"] = "HOT" if ticker in US_STOCK_MAP else "SILENT"
    return s

def calculate_sector_resonance(all_stocks, sector_map):
    """計算每個產業族群的共振分數，回傳 {code: score} 映射"""
    code_to_score = {}
    for sector_name, members in sector_map.items():
        sector_stocks = [s for s in all_stocks if s["code"] in members]
        if len(sector_stocks) < 2:
            continue
        n = len(sector_stocks)
        # 1. 技術面同步 (20%) — 同時處於多頭或突破狀態的比例
        bullish_classes = {"E_BREAKOUT", "A_BREAKOUT", "B_READY", "C_PULLBACK"}
        bullish_count = sum(1 for s in sector_stocks if s.get("timing_class") in bullish_classes)
        tech_sync = bullish_count / n
        # 2. 量能同步 (35%) — 多檔同時放量
        vol_up_count = sum(1 for s in sector_stocks if s.get("vol_ratio", 1.0) > 1.1)
        vol_sync = vol_up_count / n
        # 3. 方向一致性 (25%) — 漲跌方向一致
        up_count = sum(1 for s in sector_stocks if s.get("change_pct", 0) > 0)
        direction_ratio = max(up_count, n - up_count) / n
        # 4. 法人同步 (20%) — 外資同買
        foreign_buy_count = sum(1 for s in sector_stocks if s.get("foreign_consecutive", 0) > 0)
        inst_sync = foreign_buy_count / n
        # 綜合共振分數 (0~100) - 依使用者最新權重
        resonance = round(
            vol_sync * 35 +
            direction_ratio * 25 +
            tech_sync * 20 +
            inst_sync * 20,
            1
        )
        # 成員數量加成：4檔以上族群共振更有意義
        if n >= 4:
            resonance = min(100.0, round(resonance * 1.1, 1))
        for s in sector_stocks:
            existing = code_to_score.get(s["code"], 0)
            code_to_score[s["code"]] = max(existing, resonance)
    return code_to_score

# ----------------- 輔助打分微調 -----------------
def calculate_pattern_adjustment(s):
    adj = 0.0
    if s.get("pattern1_ma_align"): adj += 6.0
    if s.get("pattern2_valley_vol"): adj += 4.0
    if s.get("pattern3_golden_pit"): adj += 5.0
    if s.get("pattern4_test_pressure"): adj -= 8.0
    return adj

# ----------------- 日內即時分析背景執行緒與報告視窗 -----------------
class IntradayAnalysisWorker(QThread):
    finished = Signal(str, str, dict)   # code, name, analysis_dict
    error = Signal(str, str)            # code, error_message
    
    def __init__(self, code, name, is_us=False, table_price=None, table_vol=None, parent=None):
        super().__init__(parent)
        self.code = code
        self.name = name
        self.is_us = is_us
        self.table_price = table_price
        self.table_vol = table_vol
        
    def run(self):
        try:
            result = fetch_intraday_analysis(self.code, is_us=self.is_us, table_price=self.table_price, table_vol=self.table_vol)
            if result:
                self.finished.emit(self.code, self.name, result)
            else:
                self.error.emit(self.code, "無法獲取日內數據，請確認代碼正確且市場有交易數據。")
        except Exception as e:
            import traceback
            self.error.emit(self.code, f"{str(e)}\n\n{traceback.format_exc()}")


class IntradayAnalysisDialog(QDialog):
    def __init__(self, code, name, analysis, parent=None):
        super().__init__(parent)
        self.analysis = analysis
        market_label = "美股" if analysis["market"] == "US" else "台股"
        self.setWindowTitle(f"📊 日內即時分析 - {code} {name}")
        
        # 圖擺
        import sys as _sys
        icon_name = "winradar.ico"
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name),
            os.path.join(os.path.dirname(_sys.argv[0]), icon_name),
        ]
        if hasattr(_sys, '_MEIPASS'):
            possible_paths.append(os.path.join(_sys._MEIPASS, icon_name))
        for path in possible_paths:
            if os.path.exists(path):
                self.setWindowIcon(QIcon(path))
                break
        
        self.resize(760, 820)
        self.setMinimumSize(580, 600)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                color: #E2E8F0;
            }
            QLabel {
                color: #F8FAFC;
            }
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            QTextBrowser {
                background-color: #1E293B;
                color: #F1F5F9;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 15px;
                font-size: 14px;
            }
            QMenu {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
            QMenu::item:disabled {
                color: #64748B;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        title_label = QLabel(f"📊 {market_label} {code} {name} — 日內即時分析")
        title_label.setFont(QFont("Microsoft JhengHei", 14, QFont.Bold))
        layout.addWidget(title_label)
        
        # 建立與嵌入自繪日內價量圖元件
        self.chart_widget = IntradayChartWidget(self)
        layout.addWidget(self.chart_widget)
        
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setContextMenuPolicy(Qt.CustomContextMenu)
        self.browser.customContextMenuRequested.connect(self.show_browser_context_menu)
        layout.addWidget(self.browser)
        
        # 按鈕列
        btn_layout = QHBoxLayout()
        
        btn_copy = QPushButton("📋 複製分析文字")
        btn_copy.setStyleSheet("""
            QPushButton { background-color: #10B981; }
            QPushButton:hover { background-color: #059669; }
            QPushButton:pressed { background-color: #047857; }
        """)
        btn_copy.clicked.connect(self.copy_analysis_text)
        btn_layout.addWidget(btn_copy)
        
        btn_layout.addStretch()
        
        btn_close = QPushButton("關閉")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        # 生成並顯示 HTML
        html = self._build_html(analysis, market_label, code, name)
        self.browser.setHtml(html)
        
        # 載入資料至圖表元件
        closes = analysis.get("closes_plot", [])
        volumes = analysis.get("vols_plot", [])
        vwap_series = analysis.get("vwap_series", [])
        prev_close = analysis.get("prev_close", 0.0)
        limit_p = analysis.get("limit_price", 0.0)
        sl_p = analysis.get("stop_loss", 0.0)
        self.chart_widget.set_data(closes, volumes, vwap_series, prev_close, limit_price=limit_p, stop_loss=sl_p)
        
        # 存儲純文字版本用於複製
        self._plain_text = self._build_plain_text(analysis, market_label, code, name)
    
    def show_browser_context_menu(self, pos):
        menu = self.browser.createStandardContextMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
            QMenu::item:disabled {
                color: #64748B;
            }
        """)
        menu.exec(self.browser.mapToGlobal(pos))

    def _build_html(self, a, market_label, code, name):
        chg_color = "#EF4444" if a["change_pct"] >= 0 else "#22C55E"
        chg_sign = "+" if a["change_pct"] >= 0 else ""
        
        status_colors = {
            "🚀 強勢突破": {"bg": "rgba(139, 92, 246, 0.15)", "border": "#8B5CF6", "text": "#C084FC", "bar": "#8B5CF6"},
            "🟢 高檔整理": {"bg": "rgba(16, 185, 129, 0.15)", "border": "#10B981", "text": "#34D399", "bar": "#10B981"},
            "🟡 區間震盪": {"bg": "rgba(245, 158, 11, 0.15)", "border": "#F59E0B", "text": "#FBBF24", "bar": "#F59E0B"},
            "🟠 弱勢回落": {"bg": "rgba(249, 115, 22, 0.15)", "border": "#F97316", "text": "#FB923C", "bar": "#F97316"},
            "🔴 恐慌破位": {"bg": "rgba(239, 68, 68, 0.15)", "border": "#EF4444", "text": "#F87171", "bar": "#EF4444"}
        }
        
        status_key = a.get("ai_status", "🟡 區間震盪")
        cfg = status_colors.get(status_key, status_colors["🟡 區間震盪"])
        
        html = f"""
        <style>
            body {{ font-family: 'Microsoft JhengHei', sans-serif; line-height: 1.7; color: #F1F5F9; background-color: #0F172A; margin: 0; padding: 5px; }}
            .card {{ background-color: #1E293B; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; border: 1px solid #334155; }}
            .ai-dashboard {{ background-color: {cfg["bg"]}; border: 1px solid {cfg["border"]}; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; }}
            .ai-status-title {{ color: #94A3B8; font-size: 13px; font-weight: bold; }}
            .ai-status-value {{ color: {cfg["text"]}; font-size: 18px; font-weight: bold; }}
            .ai-score {{ color: #FFFFFF; font-size: 22px; font-weight: 900; float: right; margin-top: -5px; }}
            .ai-score-label {{ font-size: 12px; color: #94A3B8; font-weight: normal; }}
            .bar-bg {{ background-color: #334155; height: 6px; border-radius: 3px; margin-top: 6px; overflow: hidden; width: 100%; }}
            .bar-fill {{ background: {cfg["bar"]}; height: 100%; width: {a["ai_score"]}%; border-radius: 3px; }}
            
            .section-title {{ color: #38BDF8; font-weight: bold; font-size: 14px; margin-bottom: 6px; }}
            .section-title::before {{ content: "■ "; color: #38BDF8; margin-right: 4px; }}
            .price {{ font-size: 20px; font-weight: bold; color: {chg_color}; }}
            .metric-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 8px; }}
            .metric-item {{ background-color: #0F172A; padding: 6px 10px; border-radius: 4px; border: 1px solid #1E293B; }}
            .metric-label {{ font-size: 11px; color: #64748B; }}
            .metric-val {{ font-size: 13px; color: #E2E8F0; font-weight: bold; }}
            
            .risk-item {{ color: #F87171; font-size: 13px; margin-bottom: 3px; }}
            .risk-item::before {{ content: "⚠️ "; }}
            
            .summary-box {{ background-color: #1E1B4B; border: 1px solid #4F46E5; border-radius: 8px; padding: 14px 18px; margin-top: 14px; }}
            .summary-text {{ color: #C7D2FE; font-size: 14px; font-weight: bold; line-height: 1.7; }}
        </style>
        
        <!-- AI 儀表板 -->
        <div class="ai-dashboard">
            <div style="width: 100%;">
                <span class="ai-status-title">📌 AI 盤中狀態診斷</span>
                <span style="float: right; background-color: rgba(239, 68, 68, 0.2); border: 1px solid #EF4444; color: #F87171; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-top: -3px;">⚡ 操作週期：當沖 / 日內極短線</span>
                <div class="ai-score">{a["ai_score"]}<span class="ai-score-label"> / 100 分</span></div>
                <div style="margin-top: 4px;">
                    <span class="ai-status-value">{status_key}</span>
                </div>
                <div class="bar-bg">
                    <div class="bar-fill"></div>
                </div>
            </div>
        </div>
        
        <!-- 新手防呆警告卡片 -->
        <div style="background-color: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;">
            <span style="color: #F87171; font-weight: bold; font-size: 13px;">⚠️ 新手防呆提示 (當沖 vs 波段)</span>
            <p style="margin: 6px 0 0 0; font-size: 12px; color: #94A3B8; line-height: 1.6;">
                本分析基於今日的 1 分鐘微觀行情與當日 VWAP 均價。<b>其即時建議可能與波段心法的大方向不同</b>（例如波段仍在觀望，但日內因大單湧入而短暫強彈）。若您是波段交易者，<b>請務必以「新手買賣心法」的大方向為主</b>，切勿因為盤中短線大漲而 FOMO 盲目追高。
            </p>
        </div>
        
        <div class="card">
            <div class="section-title" style="color: #60A5FA;">標的資訊</div>
            <div style="font-size: 15px; font-weight: bold; color: #FFFFFF;">{market_label} {code} {name}</div>
            <div style="margin-top: 6px;">
                <span class="price">{a["current_price"]:.2f}</span>
                <span style="font-size: 15px; font-weight: bold; color: {chg_color}; margin-left: 8px;">{chg_sign}{a["change_pct"]:.2f}%</span>
            </div>
            <div class="metric-grid">
                <div class="metric-item">
                    <span class="metric-label">昨收</span><br/>
                    <span class="metric-val">{a["prev_close"]:.2f}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">開盤</span><br/>
                    <span class="metric-val">{a["open_price"]:.2f}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">今日高低</span><br/>
                    <span class="metric-val">{a["day_low"]:.2f} ~ {a["day_high"]:.2f}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">成交量</span><br/>
                    <span class="metric-val">{a["vol_str"]}</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="section-title" style="color: #34D399;">日內位置</div>
            <div class="value">{a["position_text"]}</div>
            <div class="value" style="margin-top: 6px; font-size: 12px; color: #94A3B8;">
                盤中 VWAP 均價：{a["vwap"]:.2f} ｜ 當前量比：{a["vol_ratio"]:.2f}x
            </div>
        </div>
        
        <div class="card">
            <div class="section-title" style="color: #FBBF24;">趨勢研判</div>
            <div class="value">{a["trend_text"]}</div>
        </div>
        
        <div class="card">
            <div class="section-title" style="color: #C084FC;">操作建議</div>
            <div class="value">{a["action_html"]}</div>
        </div>
        
        <div class="card">
            <div class="section-title" style="color: #F472B6;">建議限價</div>
            <div class="value">{a["limit_text_html"]}</div>
        </div>
        
        <div class="card">
            <div class="section-title" style="color: #F87171;">風險點</div>
            <div class="value" style="margin-bottom: 8px; font-weight: bold; color: {a['risk_level_color']};">🛡️ 風險等級：{a['risk_level']}</div>
            <div class="value">
        """
        
        risks = a["risk_text"].split("；")
        for r in risks:
            if r.strip():
                html += f'<div class="risk-item">{r.strip()}</div>'
                 
        html += f"""
            </div>
        </div>
        
        <div class="summary-box">
            <div class="summary-text">💡 一句話結論：{a["conclusion"]}</div>
        </div>
        """
        return html
    
    def _build_plain_text(self, a, market_label, code, name):
        chg_sign = "+" if a["change_pct"] >= 0 else ""
        lines = [
            f"📊 日內即時分析 — {market_label} {code} {name}",
            f"⚡ 操作週期：當沖 / 日內極短線 (今日至隔日)",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"⚠️ 新手防呆提示：本分析基於今日微觀行情與當日 VWAP。其即時建議可能與波段心法的大方向不同（例如波段仍在觀望，但日內大單短彈）。波段操作者請以「新手買賣心法」的大方向為主，切勿盲目 FOMO 追高。",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📌 標的：{market_label} {code} {name}",
            f"💰 當前價：{a['current_price']:.2f} ({chg_sign}{a['change_pct']:.2f}%)",
            f"   前收 {a['prev_close']:.2f} ｜ 開 {a['open_price']:.2f} ｜ 高 {a['day_high']:.2f} ｜ 低 {a['day_low']:.2f} ｜ 量 {a['vol_str']}",
            f"📌 AI 判斷：{a['ai_status']} ({a['ai_score']}/100 分)",
            f"📍 日內位置：{a['position_text']}",
            f"   盤中 VWAP 均價：{a['vwap']:.2f} ｜ 當前量比：{a['vol_ratio']:.2f}x",
            f"📈 趨勢判斷：{a['trend_text']}",
            f"🎯 操作建議：",
            f"   {a['action']}",
            f"💲 建議限價：",
            f"   {a['limit_text']}",
            f"⚠️ 風險點：(風險等級：{a['risk_level']})",
            f"   {a['risk_text']}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"💡 一句話結論：{a['conclusion']}",
        ]
        return "\n".join(lines)

    def copy_analysis_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self._plain_text)
        QMessageBox.information(self, "已複製", "分析文字已複製到剪貼簿。")
class SerenityDiagnoseWorker(QThread):
    finished = Signal(str, str, str)  # code, report_path, report_md
    error = Signal(str, str)  # code, error_message
    
    def __init__(self, code, parent=None):
        super().__init__(parent)
        self.code = code
        
    def run(self):
        try:
            import serenity_diagnostic
            import importlib
            importlib.reload(serenity_diagnostic)
            report_path, report_md = serenity_diagnostic.run_diagnose(self.code)
            self.finished.emit(self.code, report_path, report_md)
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.error.emit(self.code, f"{str(e)}\n\n{tb_str}")


class SerenityReportDialog(QDialog):
    def __init__(self, code, report_path, report_md, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Serenity 供應鏈卡點診斷報告書 - {code}")
        
        # 尋找並設定視窗圖標
        import sys
        icon_name = "winradar.ico"
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name),
            os.path.join(os.path.dirname(sys.argv[0]), icon_name),
        ]
        if hasattr(sys, '_MEIPASS'):
            possible_paths.append(os.path.join(sys._MEIPASS, icon_name))
            
        for path in possible_paths:
            if os.path.exists(path):
                self.setWindowIcon(QIcon(path))
                break
                
        self.resize(900, 750)
        self.setMinimumSize(700, 550)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                color: #E2E8F0;
            }
            QLabel {
                color: #F8FAFC;
            }
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            QTextBrowser {
                background-color: #1E293B;
                color: #F1F5F9;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 15px;
                font-size: 14px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        title_label = QLabel(f"🔍 個股 {code} Serenity 供應鏈卡點診斷報告書")
        title_label.setFont(QFont("Microsoft JhengHei", 14, QFont.Bold))
        layout.addWidget(title_label)
        
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.browser)
        
        btn_layout = QHBoxLayout()
        
        btn_open_file = QPushButton("📂 開啟原始 Markdown 報告")
        btn_open_file.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        btn_open_file.clicked.connect(lambda: self.open_report_file(report_path))
        btn_layout.addWidget(btn_open_file)
        
        btn_layout.addStretch()
        
        btn_close = QPushButton("關閉")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        html_content = self.simple_markdown_to_html(report_md)
        self.browser.setHtml(html_content)
        
    def open_report_file(self, path):
        try:
            if os.path.exists(path):
                import subprocess
                if sys.platform.startswith('win'):
                    os.startfile(path)
                elif sys.platform.startswith('darwin'):
                    subprocess.call(('open', path))
                else:
                    subprocess.call(('xdg-open', path))
            else:
                QMessageBox.warning(self, "警告", f"找不到報告檔案：{path}")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"開啟檔案失敗：{e}")
            
    def simple_markdown_to_html(self, md_text):
        lines = md_text.split('\n')
        html_lines = []
        in_list = False
        in_table = False
        table_headers = []
        table_rows = []
        
        css_style = """
        <style>
            body { font-family: 'Microsoft JhengHei', sans-serif; line-height: 1.6; color: #F1F5F9; background-color: #1E293B; }
            h1 { color: #60A5FA; border-bottom: 2px solid #3B82F6; padding-bottom: 8px; margin-top: 20px; font-size: 20px; font-weight: bold; }
            h2 { color: #34D399; border-bottom: 1px solid #475569; padding-bottom: 6px; margin-top: 18px; font-size: 16px; font-weight: bold; }
            h3 { color: #FBBF24; margin-top: 14px; font-size: 14px; font-weight: bold; }
            p { margin: 8px 0; }
            ul { margin: 8px 0; padding-left: 20px; }
            li { margin: 4px 0; }
            code { background-color: #0F172A; padding: 2px 6px; border-radius: 4px; font-family: monospace; color: #F472B6; }
            blockquote { background-color: #334155; border-left: 4px solid #3B82F6; padding: 10px 15px; margin: 12px 0; border-radius: 0 4px 4px 0; }
            table { border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 13px; }
            th { background-color: #334155; color: #F8FAFC; text-align: left; padding: 10px; border: 1px solid #475569; font-weight: bold; }
            td { padding: 8px 10px; border: 1px solid #475569; }
            tr:nth-child(even) { background-color: #1E293B; }
            tr:nth-child(odd) { background-color: #111827; }
            .score-high { color: #34D399; font-weight: bold; }
            .score-med { color: #FBBF24; font-weight: bold; }
            .score-low { color: #F87171; font-weight: bold; }
        </style>
        """
        
        html_lines.append(f"<html><head>{css_style}</head><body>")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('|'):
                if not in_table:
                    in_table = True
                    table_headers = [c.strip() for c in line.split('|')[1:-1]]
                    table_rows = []
                    i += 1
                    if i < len(lines) and '-' in lines[i]:
                        i += 1
                        continue
                else:
                    cols = [c.strip() for c in line.split('|')[1:-1]]
                    table_rows.append(cols)
                i += 1
                continue
            else:
                if in_table:
                    table_html = "<table><thead><tr>"
                    for h in table_headers:
                        table_html += f"<th>{self.parse_inline(h)}</th>"
                    table_html += "</tr></thead><tbody>"
                    for row in table_rows:
                        table_html += "<tr>"
                        for cell in row:
                            table_html += f"<td>{self.parse_inline(cell)}</td>"
                        table_html += "</tr>"
                    table_html += "</tbody></table>"
                    html_lines.append(table_html)
                    in_table = False
            
            if line.startswith('- ') or line.startswith('* '):
                if not in_list:
                    in_list = True
                    html_lines.append("<ul>")
                item_content = line[2:]
                item_content = self.parse_inline(item_content)
                html_lines.append(f"<li>{item_content}</li>")
                i += 1
                continue
            else:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
            
            if line.startswith('### '):
                html_lines.append(f"<h3>{self.parse_inline(line[4:])}</h3>")
            elif line.startswith('## '):
                html_lines.append(f"<h2>{self.parse_inline(line[3:])}</h2>")
            elif line.startswith('# '):
                html_lines.append(f"<h1>{self.parse_inline(line[2:])}</h1>")
            elif line.startswith('> '):
                html_lines.append(f"<blockquote>{self.parse_inline(line[2:])}</blockquote>")
            elif not line:
                html_lines.append("<br/>")
            else:
                html_lines.append(f"<p>{self.parse_inline(line)}</p>")
            
            i += 1
            
        if in_list:
            html_lines.append("</ul>")
        if in_table:
            table_html = "<table><thead><tr>"
            for h in table_headers:
                table_html += f"<th>{self.parse_inline(h)}</th>"
            table_html += "</tr></thead><tbody>"
            for row in table_rows:
                table_html += "<tr>"
                for cell in row:
                    table_html += f"<td>{self.parse_inline(cell)}</td>"
                table_html += "</tr>"
            table_html += "</tbody></table>"
            html_lines.append(table_html)
            
        html_lines.append("</body></html>")
        return "\n".join(html_lines)
        
    def parse_inline(self, text):
        import re
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
        
        text = text.replace("High research priority", "<span class='score-high'>High research priority</span>")
        text = text.replace("Medium research priority", "<span class='score-med'>Medium research priority</span>")
        text = text.replace("Low research priority", "<span class='score-low'>Low research priority</span>")
        return text

# ----------------- 美股背景並行掃描執行緒 -----------------
class USScanWorker(QThread):
    progress_signal = Signal(int, str)
    finished_signal = Signal(dict)
    
    def __init__(self, custom_tickers=None, use_cache=True, latest_data=None):
        super().__init__()
        self.custom_tickers = custom_tickers
        self.use_cache = use_cache
        self.latest_data = latest_data
        
    def run(self):
        try:
            self.do_run()
        except Exception as e:
            logging.error(f"美股背景掃描執行緒崩潰: {e}", exc_info=True)
            self.progress_signal.emit(100, f"⚠️ 掃描中斷錯誤: {e}")
            self.finished_signal.emit({
                "us_regime": {"status": "掃描錯誤 (大盤 Regimes 未知)", "multiplier": 1.0, "change_pct": 0.0},
                "us_stocks": []
            })
            
    def do_run(self):
        logging.info("開始美股背景數據抓取任務...")
        self.progress_signal.emit(5, "正在獲取美股大盤狀態...")
        
        try:
            us_regime = fetch_us_market_regime()
        except Exception as e:
            logging.error(f"獲取美股大盤狀態失敗: {e}")
            us_regime = {"status": "未知狀態", "multiplier": 1.0, "change_pct": 0.0}
            
        try:
            market_60d_return = fetch_market_60d_return(is_us=True)
        except Exception as e:
            logging.error(f"獲取美股大盤 60D 報酬率失敗: {e}")
            market_60d_return = 0.0

        self.progress_signal.emit(15, "正在獲取美股盤中狀態...")
        intraday, now_et, elapsed = is_us_market_open()
        is_market_active = intraday
        
        self.progress_signal.emit(25, "正在下載美股上市清單...")
        try:
            if self.custom_tickers:
                universe = [t.strip().upper() for t in self.custom_tickers if t.strip()]
            else:
                universe = fetch_us_stock_universe(use_cache=self.use_cache)
        except Exception as e:
            logging.error(f"獲取美股宇宙清單失敗: {e}")
            universe = sorted(list(US_STOCK_MAP.keys()))
            
        self.progress_signal.emit(45, "批量獲取美股行情中...")
        bulk_quotes = {}
        try:
            bulk_quotes = fetch_us_bulk_quotes(universe)
        except Exception as e:
            logging.error(f"批量獲取美股行情失敗: {e}")
            
        watchlist_tickers = {}
        if self.custom_tickers:
            self.progress_signal.emit(55, f"分析指定美股代碼清單: {len(self.custom_tickers)} 檔...")
            for t in self.custom_tickers:
                ticker = t.strip().upper()
                name = US_STOCK_MAP.get(ticker, {}).get("name")
                if not name and ticker in bulk_quotes:
                    name = bulk_quotes[ticker].get("name")
                if not name:
                    name = ticker
                watchlist_tickers[ticker] = name
        else:
            self.progress_signal.emit(55, "初始化美股 AI 晶片股監控池...")
            for t, info in US_STOCK_MAP.items():
                if t not in DISABLED_US_STOCKS:
                    watchlist_tickers[t] = info["name"]
                
        # 預篩選股票安靜池
        silent_tickers_to_analyze = []
        
        # 自適應安靜門檻
        all_changes_sorted = sorted([abs(d["change_pct"]) for d in bulk_quotes.values() if abs(d["change_pct"]) < 20])
        p50 = all_changes_sorted[len(all_changes_sorted)//2] if all_changes_sorted else 1.0
        p75 = all_changes_sorted[int(len(all_changes_sorted)*0.75)] if len(all_changes_sorted) > 10 else p50 * 1.5
        quiet_threshold = max(2.0, min(5.0, min(p50 * 3.0, p75 * 1.5)))
        
        if not self.custom_tickers:
            stock_candidates = []
            for ticker, daily in bulk_quotes.items():
                if ticker in watchlist_tickers:
                    continue
                price = daily["close"]
                if price < 5 or price > 2000 or daily["volume"] < 500000 or abs(daily["change_pct"]) > quiet_threshold:
                    continue
                    
                abs_change = abs(daily["change_pct"])
                hint_score = 0.0
                hint_score += max(0.0, quiet_threshold - abs_change) / quiet_threshold * 25
                
                vol_millions = daily["volume"] / 1000000.0
                if 0.5 <= vol_millions < 2.0: hint_score += 5
                elif 2.0 <= vol_millions <= 20.0: hint_score += 15
                else: hint_score += 8
                
                if 50 <= price <= 500: hint_score += 10
                else: hint_score += 5
                
                stock_candidates.append((ticker, hint_score))
                
            stock_candidates.sort(key=lambda x: x[1], reverse=True)
            silent_tickers_to_analyze = [x[0] for x in stock_candidates[:25]]
            
        # 深度分析池 = 核心池 + 安靜池
        final_list_to_analyze = []
        for t, name in watchlist_tickers.items():
            final_list_to_analyze.append((t, name, True))
        for t in silent_tickers_to_analyze:
            name = bulk_quotes.get(t, {}).get("name", t)
            final_list_to_analyze.append((t, name, False))
            
        self.progress_signal.emit(70, f"開始深度分析美股 (核心 {len(watchlist_tickers)} + 安靜 {len(silent_tickers_to_analyze)})...")
        
        all_us_results = []
        total_to_analyze = len(final_list_to_analyze)
        
        max_workers = min(8, total_to_analyze) if total_to_analyze > 0 else 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    analyze_us_stock, ticker, name, bulk_quotes, self.use_cache, is_market_active, market_60d_return, is_force
                ): (ticker, name) for ticker, name, is_force in final_list_to_analyze
            }
            
            completed_count = 0
            for fut in concurrent.futures.as_completed(futures):
                ticker, name = futures[fut]
                completed_count += 1
                prog = 70 + int((completed_count / total_to_analyze) * 25)
                self.progress_signal.emit(prog, f"正在分析美股: {ticker} ({completed_count}/{total_to_analyze})...")
                try:
                    s_res = fut.result()
                    if s_res:
                        all_us_results.append(s_res)
                except Exception as e:
                    logging.error(f"深度分析美股 {ticker} 發生異常: {e}", exc_info=True)
                    
        self.progress_signal.emit(95, "正在計算美股指標與產業共振...")
        
        # 計算 RS Score 百分位數
        valid_us = [s for s in all_us_results if s.get("excess_return") is not None]
        if valid_us:
            valid_us.sort(key=lambda x: x["excess_return"])
            n_us = len(valid_us)
            for idx, s in enumerate(valid_us):
                percentile = (idx + 1) / n_us * 99
                s["rs_score"] = round(percentile, 1)

        # 1. 第一階段美股個股 QAI 打分與初步時機
        for s in all_us_results:
            try:
                cs, ac, tr = calculate_qai_score(s, is_etf=False)
                s["comp_score"] = cs
                s["accum_score"] = ac
                s["trig_score"] = tr
                s["breakout_pct"] = round((s["price"] - s["max_20d"])/s["max_20d"]*100, 2) if s["max_20d"] > 0 else 0.0
                s["sector_resonance"] = 0.0
                
                calculate_stage1_continuation(s, us_regime["status"], is_etf=False)
                calculate_timing_entry(s, is_etf=False)
            except Exception as e:
                logging.error(f"美股初步打分引擎異常 {s.get('code')}: {e}", exc_info=True)
                
        # 2. 產業共振分數計算 (僅個股)
        try:
            background_us_stocks = []
            if self.latest_data and isinstance(self.latest_data, dict):
                background_us_stocks = self.latest_data.get("us_stocks", [])
            else:
                try:
                    persisted = load_json_cache(LAST_SCAN_CACHE_FILE)
                    if persisted and isinstance(persisted, dict):
                        background_us_stocks = persisted.get("us_stocks", [])
                except Exception as ex:
                    logging.error(f"讀取最後美股掃描結果快取失敗: {ex}")
                    
            if background_us_stocks:
                bg_map = {x["code"]: x for x in background_us_stocks}
                for s in all_us_results:
                    bg_map[s["code"]] = s
                resonance_us_stocks = list(bg_map.values())
            else:
                resonance_us_stocks = all_us_results

            sector_resonance_map = calculate_sector_resonance(resonance_us_stocks, US_SECTOR_MAP)
            for s in all_us_results:
                s["sector_resonance"] = sector_resonance_map.get(s["code"], 0.0)
        except Exception as e:
            logging.error(f"美股產業共振計算異常: {e}", exc_info=True)
            for s in all_us_results:
                s["sector_resonance"] = 0.0
                
        # 3. 第二階段融入共振的最終校正與指令生成
        for s in all_us_results:
            try:
                calculate_stage1_continuation(s, us_regime["status"], is_etf=False)
                calculate_timing_entry(s, is_etf=False)
                
                # 最終勝率二次校正
                raw_rate = s.get("raw_estimated_win_rate", 50.0)
                s["estimated_win_rate"] = calibrate_estimated_win_rate(raw_rate, s["timing_class"], is_etf=False)
                s["win_rate"] = s["estimated_win_rate"]
                s["fail_rate"] = round(100.0 - s["estimated_win_rate"], 1)
                
                s["trade_instruction"] = generate_trade_instruction(s, us_regime["status"], is_etf=False)
            except Exception as e:
                logging.error(f"美股最終打分或指令生成異常 {s.get('code')}: {e}", exc_info=True)
                s["trade_instruction"] = "觀望 (打分異常)"
                
        if not is_market_active:
            try:
                save_all_caches()
            except Exception as e:
                logging.error(f"保存美股快取失敗: {e}")
                
        self.progress_signal.emit(100, "美股掃描完成！")
        self.finished_signal.emit({
            "us_regime": us_regime,
            "us_stocks": all_us_results
        })

# ----------------- 背景並行掃描執行緒 -----------------
class ScanWorker(QThread):
    progress_signal = Signal(int, str)
    finished_signal = Signal(dict)
    
    def __init__(self, custom_codes=None, scan_mode="all", use_cache=True, latest_data=None):
        super().__init__()
        self.custom_codes = custom_codes
        self.scan_mode = scan_mode
        self.use_cache = use_cache
        self.latest_data = latest_data
        
    def run(self):
        try:
            self.do_run()
        except Exception as e:
            logging.error(f"背景掃描執行緒崩潰: {e}", exc_info=True)
            self.progress_signal.emit(100, f"⚠️ 掃描中斷錯誤: {e}")
            self.finished_signal.emit({
                "regime": {"status": "掃描錯誤 (大盤 Regimes 未知)", "multiplier": 1.0, "change_pct": 0.0, "index_p": 0.0},
                "stocks": [],
                "etfs": []
            })

    def do_run(self):
        logging.info("開始背景數據抓取任務...")
        self.progress_signal.emit(5, "正在獲取大盤狀態...")
        try:
            regime = fetch_taiex_regime()
            try:
                market_60d_return = fetch_market_60d_return(is_us=False)
            except Exception as ex:
                logging.error(f"獲取大盤 60D 報酬率失敗: {ex}")
                market_60d_return = 0.0
            # 獲取大盤 ^TWII 歷史 K 線並計算 20 日報酬率，用於債券 ETF 相對強度避險計算
            global GLOBAL_TAIEX_20D_RETURN
            try:
                taiex_closes = fetch_historical_closes("^TWII", 0)
                if taiex_closes and len(taiex_closes) >= 20:
                    GLOBAL_TAIEX_20D_RETURN = (taiex_closes[-1] - taiex_closes[-20]) / taiex_closes[-20] * 100
                else:
                    GLOBAL_TAIEX_20D_RETURN = None
            except Exception as ex:
                logging.error(f"獲取大盤指數歷史收盤價失敗: {ex}")
                GLOBAL_TAIEX_20D_RETURN = None
        except Exception as e:
            logging.error(f"獲取大盤狀態失敗: {e}")
            regime = {"status": "未知狀態", "multiplier": 1.0, "change_pct": 0.0, "index_p": 0.0}
            
        self.progress_signal.emit(10, "正在獲取全市場行情與法人數據...")
        
        # 交易時間動態感應
        intraday, now_tw, elapsed = is_market_open()
        is_market_active = intraday
        
        last_trading_date = get_last_trading_date()
        if not last_trading_date:
            last_trading_date = datetime.now().strftime("%Y%m%d")
            
        # 批量下載一律使用最近一個已收盤交易日
        date_str = last_trading_date 
        
        if is_market_active:
            today_str = now_tw.strftime("%Y%m%d")
            logging.info(f"偵測到盤中交易時間 (今日已交易 {elapsed} 分鐘)。將強制抓取 {today_str} 當前即時資料進行分析打分，快取唯讀保護開啟。")
        else:
            today_str = last_trading_date
            logging.info(f"偵測到非交易盤後時間 (或週末)。將複用 {today_str} 的收盤批量資料，啟動 3秒極速掃描。")
        
        # 並行獲取批量資料
        bulk_daily_tse = {}
        bulk_inst_tse = {}
        bulk_daily_otc = {}
        bulk_inst_otc = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            fut_daily = executor.submit(fetch_twse_bulk_daily, date_str)
            fut_inst = executor.submit(fetch_twse_bulk_institutional, date_str)
            fut_otc_daily = executor.submit(fetch_tpex_bulk_daily)
            fut_otc_inst = executor.submit(fetch_tpex_bulk_institutional)
            
            try:
                bulk_daily_tse = fut_daily.result(timeout=25)
            except Exception as e:
                logging.error(f"獲取上市行情異常: {e}")
            
            try:
                bulk_inst_tse = fut_inst.result(timeout=25)
            except Exception as e:
                logging.error(f"獲取上市法人異常: {e}")
                
            try:
                bulk_daily_otc = fut_otc_daily.result(timeout=25)
            except Exception as e:
                logging.error(f"獲取上櫃行情異常: {e}")
                
            try:
                bulk_inst_otc = fut_otc_inst.result(timeout=25)
            except Exception as e:
                logging.error(f"獲取上櫃法人異常: {e}")
                
        bulk_daily_tse = bulk_daily_tse if isinstance(bulk_daily_tse, dict) else {}
        bulk_inst_tse = bulk_inst_tse if isinstance(bulk_inst_tse, dict) else {}
        bulk_daily_otc = bulk_daily_otc if isinstance(bulk_daily_otc, dict) else {}
        bulk_inst_otc = bulk_inst_otc if isinstance(bulk_inst_otc, dict) else {}
        
        bulk_is_today = True
        # 如果已收盤 (或週末)，但今日的上市批量收盤行情下載失敗 (證交所尚未更新今日資料)，則 Fallback 下載上一個交易日
        if not is_market_active and not bulk_daily_tse:
            prev_date = get_previous_trading_date(date_str)
            logging.info(f"今日 {date_str} 盤後批量數據尚未公佈，將 Fallback 下載上一個交易日 {prev_date} 的上市行情與法人資料...")
            date_str = prev_date
            bulk_is_today = False
            try:
                bulk_daily_tse = fetch_twse_bulk_daily(date_str)
                bulk_inst_tse = fetch_twse_bulk_institutional(date_str)
                bulk_daily_tse = bulk_daily_tse if isinstance(bulk_daily_tse, dict) else {}
                bulk_inst_tse = bulk_inst_tse if isinstance(bulk_inst_tse, dict) else {}
            except Exception as e:
                logging.error(f"下載上一個交易日批量數據異常: {e}")
                
        bulk_daily = {**bulk_daily_tse, **bulk_daily_otc}
        bulk_inst = {**bulk_inst_tse, **bulk_inst_otc}
        
        for code in bulk_daily_otc.keys():
            with GLOBAL_SET_LOCK: GLOBAL_OTC_SET.add(code)
            
        # 決定掃描清單
        watchlist_stocks = {}
        watchlist_etfs = {}
        
        if self.custom_codes:
            self.progress_signal.emit(15, f"分析指定代碼清單: {len(self.custom_codes)} 檔...")
            for c in self.custom_codes:
                clean_code = re.sub(r'\.(tw|TW|two|TWO)$', '', c.strip()).strip()
                if clean_code.startswith('00'):
                    name = ETF_THEME_MAP.get(clean_code, {}).get("name")
                    if not name and clean_code in bulk_daily:
                        name = bulk_daily[clean_code].get("name")
                    if not name:
                        name = f"ETF {clean_code}"
                    watchlist_etfs[clean_code] = name
                else:
                    name = AI_STOCK_MAP.get(clean_code, {}).get("name")
                    if not name and clean_code in bulk_daily:
                        name = bulk_daily[clean_code].get("name")
                    if not name:
                        name = f"股票 {clean_code}"
                    watchlist_stocks[clean_code] = name
        else:
            self.progress_signal.emit(15, "初始化系統核心持股與 ETF 監控池...")
            if self.scan_mode in ("all", "stocks"):
                for c, info in AI_STOCK_MAP.items():
                    if c not in DISABLED_STOCKS:
                        watchlist_stocks[c] = info["name"]
            if self.scan_mode in ("all", "etfs"):
                for c, info in ETF_THEME_MAP.items(): watchlist_etfs[c] = info["name"]
                
        # 提前過濾安靜池名單 (若非指定診斷模式)
        silent_stocks_to_analyze = []
        silent_etfs_to_analyze = []
        
        # 自適應安靜門檻：根據全市場波動中位數計算
        all_changes_sorted = sorted([abs(d["change_pct"]) for d in bulk_daily.values() if abs(d["change_pct"]) < 20])
        p50 = all_changes_sorted[len(all_changes_sorted)//2] if all_changes_sorted else 1.0
        p75 = all_changes_sorted[int(len(all_changes_sorted)*0.75)] if len(all_changes_sorted) > 10 else p50 * 1.5
        quiet_threshold = max(2.0, min(5.0, min(p50 * 3.0, p75 * 1.5)))
        
        if not self.custom_codes:
            # 1. 預篩選股票安靜池
            if self.scan_mode in ("all", "stocks"):
                logging.info(f"[偵測] 開始預篩選股票安靜池... bulk_daily 大小: {len(bulk_daily)}, watchlist_stocks 大小: {len(watchlist_stocks)}")
                stock_candidates = []
                mega_excludes = {"2330", "2317", "2454", "2382", "2308", "2881", "2882", "2891"}
                for code, daily in bulk_daily.items():
                    if code.startswith('00') or code in watchlist_stocks or code in mega_excludes: continue
                    price = daily["close"]
                    if price < 30 or price > 1500 or daily["volume"] < 300 or abs(daily["change_pct"]) > quiet_threshold: continue
                    if code.startswith("28") or any(kw in daily["name"] for kw in ["金", "控", "銀", "保", "證"]): continue
                    
                    inst = bulk_inst.get(code, {"foreign_net": 0, "trust_net": 0, "dealer_net": 0, "total_net": 0})
                    foreign_net = inst.get("foreign_net", 0)
                    trust_net = inst.get("trust_net", 0)
                    abs_change = abs(daily["change_pct"])
                    
                    hint_score = 0.0
                    hint_score += max(0.0, quiet_threshold - abs_change) / quiet_threshold * 25
                    vol_cards = daily["volume"] / 1000.0
                    if 300 <= vol_cards < 1000: hint_score += 5
                    elif 1000 <= vol_cards <= 10000: hint_score += 15
                    else: hint_score += 8
                    
                    total_net = inst.get("total_net", 0)
                    if foreign_net > 0 or trust_net > 0 or total_net > 0:
                        if foreign_net > 0 and trust_net > 0: hint_score += 15
                        else: hint_score += 10
                    else: hint_score += 3
                    
                    if 50 <= price <= 500: hint_score += 10
                    else: hint_score += 5
                    
                    stock_candidates.append((code, hint_score))
                    
                stock_candidates.sort(key=lambda x: x[1], reverse=True)
                silent_stocks_to_analyze = [x[0] for x in stock_candidates[:25]]
                logging.info(f"[偵測] 篩選完成！stock_candidates 數量: {len(stock_candidates)}, silent_stocks_to_analyze 數量: {len(silent_stocks_to_analyze)}")

            # 2. 預篩選 ETF 安靜池
            if self.scan_mode in ("all", "etfs"):
                etf_candidates = []
                for code, daily in bulk_daily.items():
                    if not code.startswith('00') or code in watchlist_etfs: continue
                    price = daily["close"]
                    if price < 10 or price > 500 or daily["volume"] < 100 or abs(daily["change_pct"]) > quiet_threshold: continue
                    
                    inst = bulk_inst.get(code, {"foreign_net": 0, "trust_net": 0, "dealer_net": 0, "total_net": 0})
                    foreign_net = inst.get("foreign_net", 0)
                    dealer_net = inst.get("dealer_net", 0)
                    abs_change = abs(daily["change_pct"])
                    
                    hint_score = 0.0
                    hint_score += max(0.0, quiet_threshold - abs_change) / quiet_threshold * 25
                    vol_cards = daily["volume"] / 1000.0
                    if 100 <= vol_cards < 500: hint_score += 5
                    elif 500 <= vol_cards <= 5000: hint_score += 15
                    else: hint_score += 8
                    
                    total_net = inst.get("total_net", 0)
                    if foreign_net > 0 or dealer_net > 0 or total_net > 0:
                        if foreign_net > 0 and dealer_net > 0: hint_score += 15
                        else: hint_score += 10
                    else: hint_score += 3
                    
                    if 15 <= price <= 150: hint_score += 10
                    else: hint_score += 5
                    
                    etf_candidates.append((code, hint_score))
                    
                etf_candidates.sort(key=lambda x: x[1], reverse=True)
                silent_etfs_to_analyze = [x[0] for x in etf_candidates[:25]]

        # 盤中批量獲取即時價格，防止高頻單檔請求導致封鎖 IP
        bulk_realtime = {}
        if is_market_active:
            self.progress_signal.emit(12, "正在獲取盤中最新即時行情...")
            all_codes_to_fetch = list(watchlist_stocks.keys()) + list(watchlist_etfs.keys()) + silent_stocks_to_analyze + silent_etfs_to_analyze
            try:
                bulk_realtime = fetch_twse_bulk_realtime(all_codes_to_fetch)
                logging.info(f"成功批量獲取 {len(bulk_realtime)} 檔標的的最新盤中即時行情。")
            except Exception as e:
                logging.error(f"批量獲取即時行情失敗: {e}")

        # 並行分析個股
        scanned_stocks = []
        scanned_etfs = []
        
        total_tasks = len(watchlist_stocks) + len(watchlist_etfs) + len(silent_stocks_to_analyze) + len(silent_etfs_to_analyze)
        completed_count = 0
        
        def update_progress(desc):
            nonlocal completed_count
            completed_count += 1
            pct = 15 + int((completed_count / max(1, total_tasks)) * 70)
            pct = min(85, pct)
            self.progress_signal.emit(pct, desc)

        # 個股 Hot Pool 深度掃描
        if watchlist_stocks:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(analyze_single_security, code, name, bulk_daily, bulk_inst, today_str, self.use_cache, is_market_active, bulk_realtime, bulk_is_today, market_60d_return, True): code for code, name in watchlist_stocks.items()}
                for fut in concurrent.futures.as_completed(futures):
                    code = futures[fut]
                    try:
                        res = fut.result()
                        if res: scanned_stocks.append(res)
                    except Exception as e:
                        logging.warning(f"分析股票 {code} 異常: {e}")
                    update_progress(f"掃描個股: {code}...")

        # ETF Hot Pool 深度掃描
        if watchlist_etfs:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(analyze_single_security, code, name, bulk_daily, bulk_inst, today_str, self.use_cache, is_market_active, bulk_realtime, bulk_is_today, market_60d_return, True): code for code, name in watchlist_etfs.items()}
                for fut in concurrent.futures.as_completed(futures):
                    code = futures[fut]
                    try:
                        res = fut.result()
                        if res: scanned_etfs.append(res)
                    except Exception as e:
                        logging.warning(f"分析 ETF {code} 異常: {e}")
                    update_progress(f"掃描 ETF: {code}...")

        # Silent Pool 批量掃描 (若非指定診斷模式)
        silent_stocks_scored = []
        silent_etfs_scored = []
        
        # 1. 分析股票安靜池
        if silent_stocks_to_analyze:
            self.progress_signal.emit(85, "執行全市場安靜股 analysis...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(analyze_single_security, code, bulk_daily[code]["name"], bulk_daily, bulk_inst, today_str, self.use_cache, is_market_active, bulk_realtime, bulk_is_today, market_60d_return, False): code for code in silent_stocks_to_analyze}
                for fut in concurrent.futures.as_completed(futures):
                    code = futures[fut]
                    try:
                        res = fut.result()
                        if res:
                            res["pool"] = "SILENT"
                            silent_stocks_scored.append(res)
                    except Exception as e:
                        logging.error(f"分析安靜股 {code} 發生異常: {e}", exc_info=True)
                    update_progress(f"分析安靜股: {code}...")
                    
            stock_order = {code: i for i, code in enumerate(silent_stocks_to_analyze)}
            silent_stocks_scored.sort(key=lambda x: stock_order.get(x["code"], 999))
            
        # 2. 分析 ETF 安靜池
        if silent_etfs_to_analyze:
            self.progress_signal.emit(87, "執行全市場安靜 ETF analysis...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(analyze_single_security, code, bulk_daily[code]["name"], bulk_daily, bulk_inst, today_str, self.use_cache, is_market_active, bulk_realtime, bulk_is_today, market_60d_return, False): code for code in silent_etfs_to_analyze}
                for fut in concurrent.futures.as_completed(futures):
                    code = futures[fut]
                    try:
                        res = fut.result()
                        if res:
                            res["pool"] = "SILENT"
                            silent_etfs_scored.append(res)
                    except Exception as e:
                        logging.error(f"分析安靜 ETF {code} 發生異常: {e}", exc_info=True)
                    update_progress(f"分析安靜 ETF: {code}...")
                    
            etf_order = {code: i for i, code in enumerate(silent_etfs_to_analyze)}
            silent_etfs_scored.sort(key=lambda x: etf_order.get(x["code"], 999))

        # 後續打分與發動時機合併判定
        self.progress_signal.emit(95, "正在計算時序評分與發動概率...")
        all_stocks = scanned_stocks + silent_stocks_scored
        all_etfs = scanned_etfs + silent_etfs_scored

        # 計算台股 RS Score 百分位數
        valid_stocks = [s for s in all_stocks if s.get("excess_return") is not None]
        if valid_stocks:
            valid_stocks.sort(key=lambda x: x["excess_return"])
            n_stocks = len(valid_stocks)
            for idx, s in enumerate(valid_stocks):
                percentile = (idx + 1) / n_stocks * 99
                s["rs_score"] = round(percentile, 1)

        # 計算台股 ETF RS Score 百分位數
        valid_etfs = [s for s in all_etfs if s.get("excess_return") is not None]
        if valid_etfs:
            valid_etfs.sort(key=lambda x: x["excess_return"])
            n_etfs = len(valid_etfs)
            for idx, s in enumerate(valid_etfs):
                percentile = (idx + 1) / n_etfs * 99
                s["rs_score"] = round(percentile, 1)
        
        # 1. 股票打分與初步時機 (第一階段 - 暫無共振分數)
        for s in all_stocks:
            cs, ac, tr = calculate_qai_score(s, is_etf=False)
            s["comp_score"] = cs
            s["accum_score"] = ac
            s["trig_score"] = tr
            s["breakout_pct"] = round((s["price"] - s["max_20d"])/s["max_20d"]*100, 2) if s["max_20d"] > 0 else 0.0
            s["sector_resonance"] = 0.0  # 初步為 0
            
            calculate_stage1_continuation(s, regime["status"], is_etf=False)
            calculate_timing_entry(s, is_etf=False)
        
        # 取得背景數據以供計算族群共振
        background_stocks = []
        if self.latest_data and isinstance(self.latest_data, dict):
            background_stocks = self.latest_data.get("stocks", [])
        else:
            try:
                persisted = load_json_cache(LAST_SCAN_CACHE_FILE)
                if persisted and isinstance(persisted, dict):
                    background_stocks = persisted.get("stocks", [])
            except Exception as ex:
                logging.error(f"讀取最後台股掃描結果快取失敗: {ex}")
                
        if background_stocks:
            bg_map = {x["code"]: x for x in background_stocks}
            for s in all_stocks:
                bg_map[s["code"]] = s
            resonance_stocks = list(bg_map.values())
        else:
            resonance_stocks = all_stocks

        # 產業共振分數計算 (基於初步時機進行共振計算，僅個股)
        sector_scores = calculate_sector_resonance(resonance_stocks, SECTOR_MAP)
        for s in all_stocks:
            s["sector_resonance"] = sector_scores.get(s["code"], 0.0)

        # 2. 股票最終評分與最終時機 (第二階段 - 融入共振分數)
        for s in all_stocks:
            calculate_stage1_continuation(s, regime["status"], is_etf=False)
            calculate_timing_entry(s, is_etf=False)
            
            # 最終訊號強度分數 (原勝率) 二次校正
            raw_rate = s.get("raw_estimated_win_rate", 50.0)
            s["estimated_win_rate"] = calibrate_estimated_win_rate(raw_rate, s["timing_class"], is_etf=False)
            s["win_rate"] = s["estimated_win_rate"]
            s["fail_rate"] = round(100.0 - s["estimated_win_rate"], 1)
            
            s["trade_instruction"] = generate_trade_instruction(s, regime["status"], is_etf=False)
            
        # 2. ETF 打分與時機
        for s in all_etfs:
            cs, ac, tr = calculate_qai_score(s, is_etf=True)
            s["comp_score"] = cs
            s["accum_score"] = ac
            s["trig_score"] = tr
            s["breakout_pct"] = round((s["price"] - s["max_20d"])/s["max_20d"]*100, 2) if s["max_20d"] > 0 else 0.0
            
            calculate_stage1_continuation(s, regime["status"], is_etf=True)
            calculate_timing_entry(s, is_etf=True)
            
            # 最終勝率二次校正
            raw_rate = s.get("raw_estimated_win_rate", 50.0)
            s["estimated_win_rate"] = calibrate_estimated_win_rate(raw_rate, s["timing_class"], is_etf=True)
            s["win_rate"] = s["estimated_win_rate"]
            s["fail_rate"] = round(100.0 - s["estimated_win_rate"], 1)
            
            s["trade_instruction"] = generate_trade_instruction(s, regime["status"], is_etf=True)
            s["sector_resonance"] = 0.0  # ETF 不參與產業共振計算
            
        # 保存快取數據到硬碟 (僅在非盤中已收盤且批量資料皆存在時才寫入硬碟快取，防範污染)
        if not is_market_active and bulk_daily and bulk_inst:
            save_all_caches()
        
        self.progress_signal.emit(100, "資料運算完成！")
        self.finished_signal.emit({
            "regime": regime,
            "stocks": all_stocks,
            "etfs": all_etfs
        })

# ----------------- UI 介面實作 -----------------
# ----------------- 自繪圖形與圖表元件 -----------------
from PySide6.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QFrame, QGridLayout, QMessageBox
from PySide6.QtCore import Qt, QPoint, QThread, Signal
from PySide6.QtGui import QPainter, QPolygon, QPen, QColor, QFont, QIcon
import math

class RadarChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.scores = [50.0, 50.0, 50.0, 50.0, 50.0, 50.0]  # 技術, 籌碼, 動能, 成熟, 主力, 共振
        self.labels = ["技術壓縮", "籌碼收集", "突破動能", "勝率成熟", "主力推進", "板塊共振"]
        self.animation_factor = 0.0
        self.anim_timer = QtCore.QTimer(self)
        self.anim_timer.timeout.connect(self.advance_animation)
        
    def advance_animation(self):
        self.animation_factor += 0.06
        if self.animation_factor >= 1.0:
            self.animation_factor = 1.0
            self.anim_timer.stop()
        self.update()

    def set_scores(self, comp, accum, trig, win_rate, vol_slope, resonance):
        try:
            res_val = float(resonance) if (resonance is not None and str(resonance) != '-') else 0.0
        except ValueError:
            res_val = 0.0
        
        try:
            slope_val = float(vol_slope) if vol_slope is not None else 1.0
            smart_drive = min(100.0, max(0.0, slope_val * 40.0 + 30.0))
        except ValueError:
            smart_drive = 50.0
            
        self.scores = [
            min(100.0, max(0.0, float(comp or 0.0))),
            min(100.0, max(0.0, float(accum or 0.0))),
            min(100.0, max(0.0, float(trig or 0.0))),
            min(100.0, max(0.0, float(win_rate or 50.0))),
            smart_drive,
            min(100.0, max(0.0, res_val))
        ]
        
        self.animation_factor = 0.0
        self.anim_timer.stop()
        self.anim_timer.start(16)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        center_x = width // 2
        center_y = height // 2
        radius = min(width, height) // 2 - 35
        if radius < 20: radius = 20
        
        # 繪製背景同心六角形 (20%, 40%, 60%, 80%, 100%)
        painter.setBrush(Qt.NoBrush)
        levels = 5
        for level in range(1, levels + 1):
            r = radius * level / levels
            polygon = QPolygon()
            for i in range(6):
                angle = i * 60 * math.pi / 180 - math.pi / 2
                x = center_x + r * math.cos(angle)
                y = center_y + r * math.sin(angle)
                polygon.append(QPoint(int(x), int(y)))
            painter.setPen(QPen(QColor(51, 65, 85, 120), 1, Qt.SolidLine))
            painter.drawPolygon(polygon)
            
        # 繪製六角網格放射線
        for i in range(6):
            angle = i * 60 * math.pi / 180 - math.pi / 2
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            painter.setPen(QPen(QColor(51, 65, 85, 120), 1, Qt.SolidLine))
            painter.drawLine(center_x, center_y, int(x), int(y))
            
        # 繪製數據多邊形
        data_polygon = QPolygon()
        for i in range(6):
            score = self.scores[i]
            r = radius * score / 100.0 * self.animation_factor
            angle = i * 60 * math.pi / 180 - math.pi / 2
            x = center_x + r * math.cos(angle)
            y = center_y + r * math.sin(angle)
            data_polygon.append(QPoint(int(x), int(y)))
            
        # 填充數據多邊形（紫色霓虹半透明）
        painter.setBrush(QColor(139, 92, 246, 50))
        painter.setPen(QPen(QColor(168, 85, 247, 200), 2, Qt.SolidLine))
        painter.drawPolygon(data_polygon)
        
        # 繪製頂點上的圓點與文字
        font = QFont("Microsoft JhengHei", 8, QFont.Bold)
        painter.setFont(font)
        for i in range(6):
            score = self.scores[i]
            r = radius * score / 100.0 * self.animation_factor
            angle = i * 60 * math.pi / 180 - math.pi / 2
            x = center_x + r * math.cos(angle)
            y = center_y + r * math.sin(angle)
            
            # 數據點上的發光點
            painter.setBrush(QColor(192, 132, 252))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(int(x), int(y)), 3, 3)
            
            # 文字標籤坐標
            label_r = radius + 14
            lx = center_x + label_r * math.cos(angle)
            ly = center_y + label_r * math.sin(angle)
            
            txt = f"{self.labels[i]}\n{score:.0f}"
            rect_w = 60
            rect_h = 24
            rect_x = int(lx - rect_w // 2)
            rect_y = int(ly - rect_h // 2)
            
            painter.setPen(QColor(226, 232, 240))
            align = Qt.AlignCenter
            if math.cos(angle) > 0.3:
                align = Qt.AlignLeft | Qt.AlignVCenter
                rect_x += 4
            elif math.cos(angle) < -0.3:
                align = Qt.AlignRight | Qt.AlignVCenter
                rect_x -= 4
            
            painter.drawText(rect_x - 5, rect_y, rect_w + 10, rect_h, align, txt)

class IntradayChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(450, 240)
        self.closes = []
        self.volumes = []
        self.vwap = []
        self.prev_close = 0.0
        self.limit_price = 0.0
        self.stop_loss = 0.0
        
    def set_data(self, closes, volumes, vwap, prev_close, limit_price=0.0, stop_loss=0.0):
        self.closes = closes
        self.volumes = volumes
        self.vwap = vwap
        self.prev_close = float(prev_close or 0.0)
        self.limit_price = float(limit_price or 0.0)
        self.stop_loss = float(stop_loss or 0.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 繪製漸層背景
        painter.fillRect(0, 0, width, height, QColor(15, 23, 42))
        
        padding_top = 20
        padding_bottom = 30
        padding_left = 15
        padding_right = 60
        
        graph_width = width - padding_left - padding_right
        graph_height = height - padding_top - padding_bottom
        
        if not self.closes or len(self.closes) < 2:
            font = QFont("Microsoft JhengHei", 10)
            painter.setFont(font)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(self.rect(), Qt.AlignCenter, "⏳ 暫無日內圖表數據...")
            return
            
        all_prices = self.closes + self.vwap
        if self.prev_close > 0:
            all_prices.append(self.prev_close)
        if self.limit_price > 0:
            all_prices.append(self.limit_price)
        if self.stop_loss > 0:
            all_prices.append(self.stop_loss)
            
        max_p = max(all_prices)
        min_p = min(all_prices)
        p_diff = max_p - min_p
        if p_diff == 0: p_diff = 1.0
        
        max_p += p_diff * 0.05
        min_p -= p_diff * 0.05
        p_range = max_p - min_p
        
        def get_x(idx):
            return padding_left + (idx / (len(self.closes) - 1)) * graph_width
            
        def get_y(val):
            val_pct = (val - min_p) / p_range
            return padding_top + (1.0 - val_pct) * graph_height
            
        # 1. 繪製格線
        grid_lines = 4
        font_tick = QFont("Consolas", 8)
        painter.setFont(font_tick)
        for i in range(grid_lines + 1):
            val = min_p + (i / grid_lines) * p_range
            y = get_y(val)
            painter.setPen(QPen(QColor(51, 65, 85, 100), 1, Qt.DashLine))
            painter.drawLine(padding_left, int(y), padding_left + graph_width, int(y))
            
            chg_pct = (val - self.prev_close) / self.prev_close * 100 if self.prev_close > 0 else 0.0
            chg_color = QColor(34, 197, 94) if val < self.prev_close else (QColor(239, 68, 68) if val > self.prev_close else QColor(148, 163, 184))
            painter.setPen(chg_color)
            painter.drawText(width - padding_right + 5, int(y + 4), f"{val:.2f}")
            
        # 平盤線
        if self.prev_close > 0:
            y_prev = get_y(self.prev_close)
            painter.setPen(QPen(QColor(148, 163, 184, 120), 1.5, Qt.DashLine))
            painter.drawLine(padding_left, int(y_prev), padding_left + graph_width, int(y_prev))
            painter.drawText(width - padding_right + 5, int(y_prev - 4), "Ref")
            
        # 建議買入與停損虛線
        if self.limit_price > 0:
            y_limit = get_y(self.limit_price)
            painter.setPen(QPen(QColor(96, 165, 250, 180), 1.2, Qt.DashLine))
            painter.drawLine(padding_left, int(y_limit), padding_left + graph_width, int(y_limit))
            painter.drawText(padding_left + 10, int(y_limit - 4), f"Buy: {self.limit_price:.2f}")
            
        if self.stop_loss > 0:
            y_stop = get_y(self.stop_loss)
            painter.setPen(QPen(QColor(248, 113, 113, 180), 1.2, Qt.DashLine))
            painter.drawLine(padding_left, int(y_stop), padding_left + graph_width, int(y_stop))
            painter.drawText(padding_left + 10, int(y_stop - 4), f"SL: {self.stop_loss:.2f}")

        # 2. 繪製底部成交量
        max_v = max(self.volumes) if self.volumes else 1.0
        if max_v == 0: max_v = 1.0
        vol_height_limit = graph_height * 0.15
        vol_base_y = height - padding_bottom
        
        col_w = max(1.0, graph_width / len(self.closes))
        for i, v in enumerate(self.volumes):
            x = get_x(i)
            v_h = (v / max_v) * vol_height_limit
            if i > 0 and self.closes[i] < self.closes[i-1]:
                painter.fillRect(int(x), int(vol_base_y - v_h), int(col_w), int(v_h), QColor(22, 163, 74, 80))
            else:
                painter.fillRect(int(x), int(vol_base_y - v_h), int(col_w), int(v_h), QColor(220, 38, 38, 80))

        # 3. 繪製 VWAP 折線 (Indigo 藍色)
        vwap_path = []
        for i, val in enumerate(self.vwap):
            vwap_path.append(QPoint(int(get_x(i)), int(get_y(val))))
        painter.setPen(QPen(QColor(129, 140, 248, 180), 1.5, Qt.SolidLine))
        if len(vwap_path) >= 2:
            painter.drawPolyline(vwap_path)
            
        # 4. 繪製價格折線 (高亮黃色)
        price_path = []
        for i, val in enumerate(self.closes):
            price_path.append(QPoint(int(get_x(i)), int(get_y(val))))
        
        painter.setPen(QPen(QColor(251, 191, 36, 40), 4, Qt.SolidLine))
        if len(price_path) >= 2:
            painter.drawPolyline(price_path)
        painter.setPen(QPen(QColor(253, 224, 71), 1.8, Qt.SolidLine))
        if len(price_path) >= 2:
            painter.drawPolyline(price_path)
            
        # 5. X 軸
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor(100, 116, 139))
        painter.drawText(padding_left, height - padding_bottom + 14, "Open")
        painter.drawText(padding_left + graph_width // 2 - 15, height - padding_bottom + 14, "Mid")
        painter.drawText(padding_left + graph_width - 20, height - padding_bottom + 14, "Close")

class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        val_self = self.data(Qt.UserRole + 99)
        val_other = other.data(Qt.UserRole + 99)
        if val_self is not None and val_other is not None:
            try:
                return float(val_self) < float(val_other)
            except (ValueError, TypeError):
                pass
        return super().__lt__(other)

class KLineFetchWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, code, is_us=False, parent=None):
        super().__init__(parent)
        self.code = code
        self.is_us = is_us
        
    def run(self):
        import urllib.request
        import ssl
        import urllib.parse
        import urllib.error
        
        ssl_context = ssl._create_unverified_context()
        ua_headers = {"User-Agent": "Mozilla/5.0"}
        
        if self.is_us:
            symbols_to_try = [self.code]
        else:
            primary = f"{self.code}.TWO" if self.code in GLOBAL_OTC_SET else f"{self.code}.TW"
            secondary = f"{self.code}.TW" if self.code in GLOBAL_OTC_SET else f"{self.code}.TWO"
            symbols_to_try = [primary, secondary]
            
        success = False
        last_exception = None
        
        for symbol in symbols_to_try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=6mo&interval=1d"
            try:
                req = urllib.request.Request(url, headers=ua_headers)
                with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                    raw_data = json.loads(response.read().decode('utf-8'))
                    result_node = raw_data.get("chart", {}).get("result", [])
                    if not result_node:
                        if len(symbols_to_try) > 1 and symbol == symbols_to_try[0]:
                            continue
                        self.error.emit("未能取得歷史 Chart 數據。")
                        return
                        
                    chart = result_node[0]
                    quote = chart.get("indicators", {}).get("quote", [{}])[0]
                    
                    closes_raw = quote.get("close", [])
                    opens_raw = quote.get("open", [])
                    highs_raw = quote.get("high", [])
                    lows_raw = quote.get("low", [])
                    volumes_raw = quote.get("volume", [])
                    
                    opens = []
                    highs = []
                    lows = []
                    closes = []
                    volumes = []
                    
                    last_valid = None
                    for idx, c in enumerate(closes_raw):
                        o = opens_raw[idx]
                        h = highs_raw[idx]
                        l = lows_raw[idx]
                        v = volumes_raw[idx] if idx < len(volumes_raw) else None
                        
                        if c is not None and o is not None and h is not None and l is not None:
                            opens.append(float(o))
                            highs.append(float(h))
                            lows.append(float(l))
                            closes.append(float(c))
                            volumes.append(float(v if v is not None else 0.0))
                            last_valid = (float(o), float(h), float(l), float(c), float(v if v is not None else 0.0))
                        else:
                            if last_valid:
                                opens.append(last_valid[0])
                                highs.append(last_valid[1])
                                lows.append(last_valid[2])
                                closes.append(last_valid[3])
                                volumes.append(last_valid[4])
                                
                    if not closes:
                        if len(symbols_to_try) > 1 and symbol == symbols_to_try[0]:
                            continue
                        self.error.emit("清洗後無有效歷史數據。")
                        return
                        
                    ma5 = []
                    for i in range(len(closes)):
                        if i >= 4:
                            ma5.append(sum(closes[i-4:i+1]) / 5.0)
                        else:
                            ma5.append(sum(closes[:i+1]) / float(i + 1))
                            
                    ma20 = []
                    for i in range(len(closes)):
                        if i >= 19:
                            ma20.append(sum(closes[i-19:i+1]) / 20.0)
                        else:
                            ma20.append(sum(closes[:i+1]) / float(i + 1))
                            
                    keep = 30
                    self.finished.emit({
                        "opens": opens[-keep:],
                        "highs": highs[-keep:],
                        "lows": lows[-keep:],
                        "closes": closes[-keep:],
                        "ma5": ma5[-keep:],
                        "ma20": ma20[-keep:],
                        "full_opens": opens,
                        "full_highs": highs,
                        "full_lows": lows,
                        "full_closes": closes,
                        "full_volumes": volumes
                    })
                    success = True
                    break
            except urllib.error.HTTPError as e:
                last_exception = e
                if e.code == 404 and len(symbols_to_try) > 1 and symbol == symbols_to_try[0]:
                    continue
                break
            except Exception as e:
                last_exception = e
                if len(symbols_to_try) > 1 and symbol == symbols_to_try[0]:
                    continue
                break
                
        if not success:
            err_msg = str(last_exception) if last_exception else "未知錯誤"
            self.error.emit(err_msg)

class CandlestickChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(450, 180)
        self.opens = []
        self.highs = []
        self.lows = []
        self.closes = []
        self.ma5 = []
        self.ma20 = []
        self.limit_price = 0.0
        self.stop_loss = 0.0
        self.mouse_pos = None
        self.error_msg = None
        self.setMouseTracking(True)
        
    def set_data(self, data, limit_price=0.0, stop_loss=0.0):
        self.error_msg = None
        self.opens = data["opens"]
        self.highs = data["highs"]
        self.lows = data["lows"]
        self.closes = data["closes"]
        self.ma5 = data["ma5"]
        self.ma20 = data["ma20"]
        self.limit_price = float(limit_price or 0.0)
        self.stop_loss = float(stop_loss or 0.0)
        self.update()
        
    def set_error(self, err_msg):
        self.error_msg = err_msg
        self.opens = []
        self.highs = []
        self.lows = []
        self.closes = []
        self.ma5 = []
        self.ma20 = []
        self.update()
        
    def mouseMoveEvent(self, event):
        self.mouse_pos = event.position().toPoint()
        self.update()
        super().mouseMoveEvent(event)
        
    def leaveEvent(self, event):
        self.mouse_pos = None
        self.update()
        super().leaveEvent(event)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        painter.fillRect(0, 0, width, height, QColor(15, 23, 42))
        
        padding_top = 15
        padding_bottom = 20
        padding_left = 15
        padding_right = 60
        
        graph_width = width - padding_left - padding_right
        graph_height = height - padding_top - padding_bottom
        
        if self.error_msg:
            font = QFont("Microsoft JhengHei", 9)
            painter.setFont(font)
            painter.setPen(QColor(239, 68, 68)) # 紅色
            painter.drawText(self.rect(), Qt.AlignCenter, f"❌ 獲取歷史K線失敗: {self.error_msg}")
            return
            
        if not self.closes or len(self.closes) < 2:
            font = QFont("Microsoft JhengHei", 9)
            painter.setFont(font)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(self.rect(), Qt.AlignCenter, "⏳ 正在異步獲取個股日K線歷史圖表...")
            return
            
        all_val = self.highs + self.lows + self.ma5 + self.ma20
        if self.limit_price > 0: all_val.append(self.limit_price)
        if self.stop_loss > 0: all_val.append(self.stop_loss)
        
        max_p = max(all_val)
        min_p = min(all_val)
        p_diff = max_p - min_p if max_p != min_p else 1.0
        
        max_p += p_diff * 0.05
        min_p -= p_diff * 0.05
        p_range = max_p - min_p
        
        def get_x(idx):
            return padding_left + (idx / (len(self.closes) - 1)) * graph_width
            
        def get_y(val):
            val_pct = (val - min_p) / p_range
            return padding_top + (1.0 - val_pct) * graph_height

        # 1. 繪製買入與停損區間遮罩與水平延伸線
        if self.limit_price > 0 and self.stop_loss > 0:
            y_limit = get_y(self.limit_price)
            y_stop = get_y(self.stop_loss)
            
            y_top_g = min(y_limit, y_stop)
            y_h_g = abs(y_limit - y_stop)
            painter.fillRect(int(padding_left), int(y_top_g), int(graph_width), int(y_h_g), QColor(16, 185, 129, 20))
            
            y_top_r = max(y_limit, y_stop)
            y_h_r = height - padding_bottom - y_top_r
            if y_h_r > 0:
                painter.fillRect(int(padding_left), int(y_top_r), int(graph_width), int(y_h_r), QColor(239, 68, 68, 20))
                
            # 輔支線與文字
            painter.setPen(QPen(QColor(16, 185, 129, 150), 1, Qt.DashLine))
            painter.drawLine(padding_left, int(y_limit), padding_left + graph_width, int(y_limit))
            painter.drawText(width - padding_right + 5, int(y_limit + 4), f"買:{self.limit_price:.1f}")
            
            painter.setPen(QPen(QColor(239, 68, 68, 150), 1, Qt.SolidLine))
            painter.drawLine(padding_left, int(y_stop), padding_left + graph_width, int(y_stop))
            painter.drawText(width - padding_right + 5, int(y_stop + 4), f"損:{self.stop_loss:.1f}")

        # 2. 繪製水平格線與價格
        grid_lines = 3
        painter.setFont(QFont("Consolas", 8))
        for i in range(grid_lines + 1):
            val = min_p + (i / grid_lines) * p_range
            y = get_y(val)
            if self.limit_price > 0 and abs(val - self.limit_price)/self.limit_price < 0.015: continue
            if self.stop_loss > 0 and abs(val - self.stop_loss)/self.stop_loss < 0.015: continue
            
            painter.setPen(QPen(QColor(51, 65, 85, 80), 1, Qt.DashLine))
            painter.drawLine(padding_left, int(y), padding_left + graph_width, int(y))
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(width - padding_right + 5, int(y + 4), f"{val:.1f}")

        # 3. 繪製 K 線 (蠟燭圖)
        col_w = max(3.0, (graph_width / len(self.closes)) * 0.6)
        for i in range(len(self.closes)):
            cx = get_x(i)
            o_y = get_y(self.opens[i])
            c_y = get_y(self.closes[i])
            h_y = get_y(self.highs[i])
            l_y = get_y(self.lows[i])
            
            is_bull = self.closes[i] >= self.opens[i]
            color = QColor(239, 68, 68) if is_bull else QColor(34, 197, 94)
            
            painter.setPen(QPen(color, 1))
            painter.drawLine(int(cx), int(h_y), int(cx), int(l_y))
            
            rect_h = abs(o_y - c_y)
            if rect_h < 1: rect_h = 1
            rect_y = min(o_y, c_y)
            painter.fillRect(int(cx - col_w // 2), int(rect_y), int(col_w), int(rect_h), color)

        # 4. 繪製 5MA 與 20MA
        ma5_pts = []
        ma20_pts = []
        for i in range(len(self.closes)):
            ma5_pts.append(QPoint(int(get_x(i)), int(get_y(self.ma5[i]))))
            ma20_pts.append(QPoint(int(get_x(i)), int(get_y(self.ma20[i]))))
            
        painter.setPen(QPen(QColor(56, 189, 248, 180), 1.2, Qt.SolidLine))
        if len(ma5_pts) >= 2:
            painter.drawPolyline(ma5_pts)
            
        painter.setPen(QPen(QColor(253, 224, 71, 180), 1.2, Qt.SolidLine))
        if len(ma20_pts) >= 2:
            painter.drawPolyline(ma20_pts)
            
        painter.setPen(QColor(56, 189, 248))
        painter.drawText(padding_left + 10, height - padding_bottom + 14, "● 5MA")
        painter.setPen(QColor(253, 224, 71))
        painter.drawText(padding_left + 65, height - padding_bottom + 14, "● 20MA")
        
        # 5. 繪製互動十字線與 Tooltip 提示
        if self.mouse_pos is not None:
            mx = self.mouse_pos.x()
            if padding_left <= mx <= padding_left + graph_width:
                closest_idx = 0
                min_dist = float('inf')
                for i in range(len(self.closes)):
                    dist = abs(get_x(i) - mx)
                    if dist < min_dist:
                        min_dist = dist
                        closest_idx = i
                
                cx = get_x(closest_idx)
                cy = get_y(self.closes[closest_idx])
                
                painter.setPen(QPen(QColor(255, 255, 255, 60), 1, Qt.SolidLine))
                painter.drawLine(int(cx), int(padding_top), int(cx), int(height - padding_bottom))
                painter.drawLine(int(padding_left), int(cy), int(padding_left + graph_width), int(cy))
                
                painter.setBrush(QColor(255, 255, 255))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPoint(int(cx), int(cy)), 3, 3)
                
                tt_w = 190
                tt_h = 42
                tt_x = int(cx + 10)
                if tt_x + tt_w > width:
                    tt_x = int(cx - tt_w - 10)
                tt_y = int(cy - tt_h - 10)
                if tt_y < 5:
                    tt_y = int(cy + 10)
                    
                painter.setBrush(QColor(15, 23, 42, 230))
                painter.setPen(QPen(QColor(56, 189, 248, 150), 1, Qt.SolidLine))
                painter.drawRect(tt_x, tt_y, tt_w, tt_h)
                
                painter.setPen(QColor(241, 245, 249))
                painter.setFont(QFont("Microsoft JhengHei", 8))
                
                change_t = ""
                if closest_idx > 0:
                    pct = (self.closes[closest_idx] - self.closes[closest_idx-1])/self.closes[closest_idx-1]*100
                    sign = "+" if pct >= 0 else ""
                    change_t = f" ({sign}{pct:.1f}%)"
                
                line1 = f"價: {self.closes[closest_idx]:.2f}{change_t}"
                line2 = f"5MA: {self.ma5[closest_idx]:.2f} | 20MA: {self.ma20[closest_idx]:.2f}"
                painter.drawText(tt_x + 8, tt_y + 16, line1)
                painter.drawText(tt_x + 8, tt_y + 32, line2)

# ----------------- 新手買賣心法教學彈窗 -----------------
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QFrame, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

class TradingTeachingDialog(QDialog):
    def __init__(self, s, is_etf=False, is_us=False, parent=None):
        super().__init__(parent)
        self.s = s
        self.is_etf = is_etf
        self.is_us = is_us
        self.weekly_regime = None
        self.backtest_results = None
        self.setWindowTitle(f"💡 【{s.get('code', '')} {s.get('name', '')}】新手買賣心法教學")
        self.resize(980, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #0B0F17;
            }
            QFrame#card_teaching {
                background-color: #151C2C;
                border: 1px solid #23304A;
                border-radius: 10px;
            }
            QTextBrowser {
                background-color: #0D1322;
                border: 1px solid #23304A;
                border-radius: 8px;
                color: #E2E8F0;
                font-family: "Microsoft JhengHei", "Segoe UI", sans-serif;
                font-size: 13px;
                line-height: 1.5;
            }
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #60A5FA;
            }
            QMenu {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
            QMenu::item:disabled {
                color: #64748B;
            }
        """)
        self.setup_ui()

    def generate_teaching_html(self, weekly_regime=None, backtest_results=None):
        s = self.s
        inst_dict = s.get("trade_instruction", {})
        action = inst_dict.get("action", "WATCH")
        timing = s.get("timing_class", "Decline")
        timing_label = s.get("timing_label", "未知時機")
        trap = s.get("trap_bomb_rate", 10.0)
        
        html = []
        html.append("<div style='font-family: \"Microsoft JhengHei\", sans-serif; line-height: 1.6; color: #E2E8F0;'>")
        
        if weekly_regime:
            html.append(f"<div style='background-color: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); padding: 8px 12px; border-radius: 6px; margin-bottom: 15px;'>")
            html.append(f"<span style='color: #34D399; font-weight: bold; font-size: 13px;'>📈 週K長線大局觀：{weekly_regime}</span>")
            html.append(f"</div>")
            
        if backtest_results:
            win_5d = float(backtest_results.get("win_rate_5d", 50.0))
            if win_5d < 50.0:
                html.append("<div style='background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 10px 14px; border-radius: 6px; margin-bottom: 15px;'>")
                html.append(f"<div style='color: #F87171; font-weight: bold; font-size: 14px; margin-bottom: 4px;'>🔴 歷史驗證不足</div>")
                html.append(f"<div style='color: #E2E8F0; font-size: 12px; line-height: 1.5;'>雖然目前技術面符合 {timing_label.split('：')[-1]}型態，但本股票過去 6 個月出現相同訊號時，5 日上漲勝率僅 <b>{win_5d:.1f}%</b>，歷史表現不佳，建議降低部位或列入觀察。</div>")
                html.append("</div>")
            elif win_5d > 70.0:
                html.append("<div style='background-color: rgba(52, 211, 153, 0.1); border: 1px solid rgba(52, 211, 153, 0.3); padding: 10px 14px; border-radius: 6px; margin-bottom: 15px;'>")
                html.append(f"<div style='color: #34D399; font-weight: bold; font-size: 14px; margin-bottom: 4px;'>🟢 歷史驗證良好</div>")
                html.append(f"<div style='color: #E2E8F0; font-size: 12px; line-height: 1.5;'>本型態過去成功率高，5 日上漲勝率達 <b>{win_5d:.1f}%</b>，屬於值得優先關注的交易機會。</div>")
                html.append("</div>")
            
        if timing in ["E_BREAKOUT", "A_BREAKOUT"] and "BUY" in action:
            html.append("<h3 style='color: #F59E0B; margin-top: 0;'>💡 為什麼雷達叫我買進？</h3>")
            html.append(f"<p>本股目前處於 <b>突破爆發型態</b>（時機標籤：{timing_label}）。這意指股價剛剛強勢越過先前的整理平台，或者突破了20日來的新高點，並伴隨著成交量放大（主力大單吃貨）。在量化特徵中，突破代表著多頭力道的徹底爆發，順勢跟進能捕捉上漲動能。</p>")
            
            html.append("<h3 style='color: #10B981;'>⚠️ 新手買進心法指引</h3>")
            html.append("<ul>")
            html.append("<li><b>不要開盤無腦追高：</b>如果開盤股價跳空大漲超過 3% 以上，建議先不要急著追，可以等待盤中拉回建議買入價附近再建倉。</li>")
            html.append(f"<li><b>停損是你的防彈衣：</b>停損點設在 <b>{inst_dict.get('stop_loss', 0.0):.2f} 元</b>。如果股價不漲反跌並收盤跌破此價位，表示主力『假突破』誘多洗盤，請務必堅決執行停損，保留資金！</li>")
            html.append(f"<li><b>分批停利法：</b>若股價如預期上漲，達到第一停利點 <b>{inst_dict.get('take_profit_1', 0.0):.2f} 元</b>時，建議賣出半數持股鎖定獲利；剩餘的持股抱到第二停利點 <b>{inst_dict.get('take_profit_2', 0.0):.2f} 元</b>。</li>")
            html.append("</ul>")
            
        elif timing in ["B_READY", "C_PULLBACK"] and "BUY" in action:
            html.append("<h3 style='color: #F59E0B; margin-top: 0;'>💡 為什麼雷達叫我買進？</h3>")
            html.append(f"<p>本股屬於 <b>低點布局型態</b>（時機標籤：{timing_label}）。此時股價並非在暴漲追高，而是正處於底部整理成熟、主力籌碼鎖定（洗盤結束），或者是股價在多頭軌道中出現了短期的健康拉回，正跌到 5 日或 20 日均線的強支撐區。此時買進具備極高的<b>安全邊際</b>。</p>")
            
            html.append("<h3 style='color: #10B981;'>⚠️ 新手買進心法指引</h3>")
            html.append("<ul>")
            html.append(f"<li><b>限價掛單，耐心等待：</b>請在建議買入價 <b>{inst_dict.get('limit_price', 0.0):.2f} 元</b>附近掛限價單等待成交，不需要急躁去追買高價。</li>")
            html.append(f"<li><b>防守位置極佳：</b>停損價設在 <b>{inst_dict.get('stop_loss', 0.0):.2f} 元</b>。因為此時買在均線或支撐區附近，如果跌破代表支撐失效，損益比非常划算。</li>")
            html.append("<li><b>耐心是主力最怕的武器：</b>低點布局型態買進後可能還會悶盤整理幾天，一旦主力放量長紅突破，股價就會迅速朝停利點噴發。</li>")
            html.append("</ul>")
            
        elif action == "SELL":
            html.append("<h3 style='color: #EF4444; margin-top: 0;'>⚠️ 為什麼雷達叫我出場/避險？</h3>")
            html.append("<p><b>大盤目前處於恐慌/空頭階段</b>，或該個股已經跌破了生命防守線（如 20 日均線）。在空頭市場中，高達 80% 的股票都會被拖累下跌。此時，『防守』與『保留現金』是唯一的真理。</p>")
            
            html.append("<h3 style='color: #F59E0B;'>🛡️ 新手避險心法指引</h3>")
            html.append("<ul>")
            html.append("<li><b>留得青山在：</b>如果您目前持有這檔股票，請嚴格注意防守價。收盤跌破時建議無條件賣出，防範後續更大的跳水風險。</li>")
            html.append("<li><b>空手是最好的操作：</b>此時大盤風控指標不佳，請<b>絕對不要</b>在此刻進場建立新倉。</li>")
            html.append("</ul>")
            
        elif action == "AVOID":
            html.append("<h3 style='color: #F59E0B; margin-top: 0;'>⚠️ 假突破風險警示！為什麼不追？</h3>")
            html.append(f"<p>本股的<b>假突破誘多概率高達 {trap:.1f}%</b>。雖然它今天股價可能收紅，但是從量化籌碼來看：三大法人並未跟進（沒有主力買超支撐），或者是股價位在極高檔且量能嚴重不足。這是一種經典的『假突破誘多』陷阱。</p>")
            
            html.append("<h3 style='color: #EF4444;'>🛡️ 新手防守心法指引</h3>")
            html.append("<ul>")
            html.append("<li><b>空手不追高：</b>千萬不要因為看到股票大漲就產生錯失恐懼（FOMO）而追進去，此時追高容易立刻套牢在波段高點。</li>")
            html.append("<li><b>持有者設防守：</b>若您已經持有，建議在股價跌破防守線時先行獲利了結或減碼。</li>")
            html.append("</ul>")
            
        else:
            html.append("<h3 style='color: #94A3B8; margin-top: 0;'>⏳ 整理觀望，等待動能成熟</h3>")
            html.append(f"<p>本股目前處於長期整理、潛伏蓄能階段（時機標籤：{timing_label}）。此時股價的波動幅度很小，代表主力正在洗盤或吸籌，還沒有發出即時突破發動的強烈訊號。</p>")
            
            html.append("<h3 style='color: #F59E0B;'>🛡️ 新手追蹤心法指引</h3>")
            html.append("<ul>")
            html.append("<li><b>列入自選股追蹤：</b>此時不需要急著買進資金被卡住。可以將它加入自選監控池，每天關注其『發動成熟度』。</li>")
            html.append("<li><b>等放量紅棒再動手：</b>一旦個股出現帶量突破平台，或是時機標籤轉為 A級/E級時，才是勝率最高、速度最快的進場時機！</li>")
            html.append("</ul>")
            
        if backtest_results:
            html.append("<hr style='border: 0; border-top: 1px solid #23304A; margin: 15px 0;' />")
            html.append("<div style='background-color: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.3); padding: 12px 16px; border-radius: 6px; margin-bottom: 12px;'>")
            html.append("<span style='color: #818CF8; font-weight: bold; font-size: 14px;'>📊 該股同型態歷史回測統計 (近6個月)</span>")
            html.append("<table style='width: 100%; margin-top: 8px; font-size: 12px; border-collapse: collapse;'>")
            html.append(f"<tr><td style='padding: 3px 0; color: #94A3B8;'>符合型態樣本數：</td><td style='text-align: right; font-weight: bold; color: #FFFFFF;'>{backtest_results['total_samples']} 次</td></tr>")
            html.append(f"<tr><td style='padding: 3px 0; color: #94A3B8;'>持有 5 天上漲概率：</td><td style='text-align: right; font-weight: bold; color: #FF5B60;'>{backtest_results['win_rate_5d']}% <span style='font-size: 10px; font-weight: normal; color: #94A3B8;'>(均回報: {backtest_results['avg_ret_5d']}%)</span></td></tr>")
            html.append(f"<tr><td style='padding: 3px 0; color: #94A3B8;'>持有 10 天上漲概率：</td><td style='text-align: right; font-weight: bold; color: #FF5B60;'>{backtest_results['win_rate_10d']}% <span style='font-size: 10px; font-weight: normal; color: #94A3B8;'>(均回報: {backtest_results['avg_ret_10d']}%)</span></td></tr>")
            html.append("</table>")
            html.append("</div>")

        # 新手協同日內分析提醒卡片
        html.append("<hr style='border: 0; border-top: 1px solid #23304A; margin: 15px 0;' />")
        html.append("<div style='background-color: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.3); padding: 12px; border-radius: 6px;'>")
        html.append("<span style='color: #60A5FA; font-weight: bold; font-size: 13px;'>💡 如何配合「日內即時分析」？</span>")
        html.append("<p style='margin: 6px 0 0 0; font-size: 12px; color: #94A3B8; line-height: 1.6;'>")
        html.append("本「買賣心法」是您的<b>波段大方向</b>（日K級別）。當本頁面發出買入訊號後，您可以進一步參考右鍵選單中的<b>「日內即時分析」</b>。利用盤中的 1 分鐘 K 線強弱（例如股價是否站穩於當日均價 VWAP 上方、量比是否放大）來尋找今日最有利的掛單買點或突破切入時點。")
        html.append("</p>")
        html.append("</div>")
        
        html.append("</div>")
        return "".join(html)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. 標頭區
        ly_header = QHBoxLayout()
        lbl_title = QLabel(f"{self.s.get('code', '')} {self.s.get('name', '')}")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        
        lbl_theme = QLabel(f"({self.s.get('theme', '未知題材')})")
        lbl_theme.setStyleSheet("font-size: 12px; color: #94A3B8;")
        
        lbl_period = QLabel("🎯 適用週期：日K中線波段交易 (數天至數週)")
        lbl_period.setStyleSheet("""
            background-color: rgba(59, 130, 246, 0.15);
            border: 1px solid #3B82F6;
            color: #60A5FA;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        """)
        
        ly_header.addWidget(lbl_title)
        ly_header.addWidget(lbl_theme)
        ly_header.addStretch()
        ly_header.addWidget(lbl_period)
        layout.addLayout(ly_header)

        # 2. 中間左右分欄
        ly_body = QHBoxLayout()
        layout.addLayout(ly_body)

        # 2.1 左分欄 (資訊與白話文，權重 55)
        ly_left = QVBoxLayout()
        ly_left.setSpacing(10)
        ly_body.addLayout(ly_left, 55)

        # 2.2 右分欄 (自繪雷達圖與K線圖，權重 45)
        ly_right = QVBoxLayout()
        ly_right.setSpacing(10)
        ly_body.addLayout(ly_right, 45)

        # --- [左分欄內容] ---
        # (基本量化數據面板)
        card_data = QFrame()
        card_data.setObjectName("card_teaching")
        ly_card_data = QHBoxLayout(card_data)
        ly_card_data.setContentsMargins(15, 12, 15, 12)
        
        price = self.s.get("price", 0.0)
        chg = self.s.get("change_pct", 0.0)
        qai = self.s.get("comp_score", 0.0) + self.s.get("accum_score", 0.0) + self.s.get("trig_score", 0.0)
        win_rate = self.s.get("win_rate", 50.0)
        
        lbl_price_lbl = QLabel("最新價: ")
        lbl_price_lbl.setStyleSheet("color: #94A3B8;")
        chg_sign = "+" if chg > 0 else ""
        chg_color = "#FF5B60" if chg > 0 else ("#34D399" if chg < 0 else "#FFFFFF")
        lbl_price_val = QLabel(f"{price:.2f} ({chg_sign}{chg:.2f}%)")
        lbl_price_val.setStyleSheet(f"font-weight: bold; color: {chg_color};")
        
        lbl_qai_lbl = QLabel("QAI評分: ")
        lbl_qai_lbl.setStyleSheet("color: #94A3B8; margin-left: 15px;")
        lbl_qai_val = QLabel(f"{qai:.1f} 分")
        lbl_qai_val.setStyleSheet("font-weight: bold; color: #E2E8F0;")
        
        lbl_win_lbl = QLabel("AI 信心度: ")
        lbl_win_lbl.setStyleSheet("color: #94A3B8; margin-left: 15px;")
        win_color = "#FF5B60" if win_rate >= 75 else ("#05D994" if win_rate >= 60 else "#94A3B8")
        lbl_win_val = QLabel(f"{win_rate:.1f}%")
        lbl_win_val.setStyleSheet(f"font-weight: bold; color: {win_color};")
        
        ly_card_data.addWidget(lbl_price_lbl)
        ly_card_data.addWidget(lbl_price_val)
        ly_card_data.addWidget(lbl_qai_lbl)
        ly_card_data.addWidget(lbl_qai_val)
        ly_card_data.addWidget(lbl_win_lbl)
        ly_card_data.addWidget(lbl_win_val)
        ly_card_data.addStretch()
        ly_left.addWidget(card_data)

        # (核心操作指示卡片)
        card_inst = QFrame()
        card_inst.setObjectName("card_teaching")
        card_inst.setStyleSheet("background-color: #1E293B;")
        ly_inst = QVBoxLayout(card_inst)
        ly_inst.setContentsMargins(15, 12, 15, 12)
        ly_inst.setSpacing(8)
        
        inst_dict = self.s.get("trade_instruction", {})
        action = inst_dict.get("action", "WATCH")
        action_label = inst_dict.get("action_label", "整理觀望")
        reason = inst_dict.get("reason", "整理觀望中")
        
        lbl_act = QLabel(f"⚡ 雷達交易指示： {action_label}")
        act_color = "#C084FC" if "BUY" in action else ("#EF4444" if "SELL" in action else "#94A3B8")
        lbl_act.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {act_color};")
        ly_inst.addWidget(lbl_act)
        
        grid_params = QGridLayout()
        grid_params.setSpacing(6)
        
        if "BUY" in action:
            limit_price = inst_dict.get("limit_price", 0.0)
            trigger_price = inst_dict.get("trigger_price", 0.0)
            stop_loss = inst_dict.get("stop_loss", 0.0)
            tp1 = inst_dict.get("take_profit_1", 0.0)
            tp2 = inst_dict.get("take_profit_2", 0.0)
            shares = inst_dict.get("shares", 0)
            lots = inst_dict.get("lots", 0)
            odd = inst_dict.get("odd_lot_shares", 0)
            
            p_text = f"{limit_price:.2f} 元" if limit_price > 0 else f"{trigger_price:.2f} 元"
            p_lbl = "建議買入價" if limit_price > 0 else "突破觸發價"
            
            grid_params.addWidget(QLabel(f"<b>{p_lbl}:</b>"), 0, 0)
            lbl_p_val = QLabel(p_text)
            lbl_p_val.setStyleSheet("color: #3B82F6; font-weight: bold;")
            grid_params.addWidget(lbl_p_val, 0, 1)
            
            grid_params.addWidget(QLabel("<b>建議防守停損:</b>"), 0, 2)
            lbl_sl_val = QLabel(f"{stop_loss:.2f} 元")
            lbl_sl_val.setStyleSheet("color: #EF4444; font-weight: bold;")
            grid_params.addWidget(lbl_sl_val, 0, 3)
            
            grid_params.addWidget(QLabel("<b>第一停利點:</b>"), 1, 0)
            grid_params.addWidget(QLabel(f"{tp1:.2f} 元"), 1, 1)
            grid_params.addWidget(QLabel("<b>第二停利點:</b>"), 1, 2)
            grid_params.addWidget(QLabel(f"{tp2:.2f} 元"), 1, 3)
            
            qty_text = f"{shares} 股" if self.is_us else (f"{lots} 張又 {odd} 股" if lots > 0 else f"{odd} 股 (零股)")
            grid_params.addWidget(QLabel("<b>風控建議股數:</b>"), 2, 0)
            lbl_qty_val = QLabel(qty_text)
            lbl_qty_val.setStyleSheet("color: #F59E0B; font-weight: bold;")
            grid_params.addWidget(lbl_qty_val, 2, 1, 1, 3)
        elif action == "SELL":
            sl = inst_dict.get("stop_loss", 0.0)
            grid_params.addWidget(QLabel("<b>防守離場點:</b>"), 0, 0)
            lbl_sl_val = QLabel(f"{sl:.2f} 元")
            lbl_sl_val.setStyleSheet("color: #EF4444; font-weight: bold;")
            grid_params.addWidget(lbl_sl_val, 0, 1)
            grid_params.addWidget(QLabel("<b>原因說明:</b>"), 0, 2)
            grid_params.addWidget(QLabel(reason), 0, 3)
        elif action == "AVOID":
            sl = inst_dict.get("stop_loss", 0.0)
            grid_params.addWidget(QLabel("<b>參考防守價:</b>"), 0, 0)
            grid_params.addWidget(QLabel(f"{sl:.2f} 元"), 0, 1)
            grid_params.addWidget(QLabel("<b>警告:</b>"), 0, 2)
            lbl_warn = QLabel("假突破風險大，勿追高！")
            lbl_warn.setStyleSheet("color: #F59E0B; font-weight: bold;")
            grid_params.addWidget(lbl_warn, 0, 3)
        else:
            alert = inst_dict.get("alert_price", 0.0)
            if alert > 0:
                grid_params.addWidget(QLabel("<b>關注突破價:</b>"), 0, 0)
                grid_params.addWidget(QLabel(f"{alert:.2f} 元"), 0, 1)
            grid_params.addWidget(QLabel("<b>狀態說明:</b>"), 0, 2)
            grid_params.addWidget(QLabel("整理蓄能中，無發動訊號"), 0, 3)
            
        ly_inst.addLayout(grid_params)
        ly_left.addWidget(card_inst)

        # (白話文心法指南區)
        self.tb_teaching = QTextBrowser()
        self.tb_teaching.setOpenExternalLinks(True)
        self.tb_teaching.setHtml(self.generate_teaching_html())
        self.tb_teaching.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tb_teaching.customContextMenuRequested.connect(self.show_browser_context_menu)
        ly_left.addWidget(self.tb_teaching)

        # --- [右分欄內容] ---
        # (雷達圖)
        card_radar = QFrame()
        card_radar.setObjectName("card_teaching")
        ly_card_radar = QVBoxLayout(card_radar)
        ly_card_radar.setContentsMargins(5, 5, 5, 5)
        
        lbl_radar_title = QLabel(" 📊 QAI量化因子六角雷達圖")
        lbl_radar_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #38BDF8; margin-top: 5px; margin-left: 5px;")
        ly_card_radar.addWidget(lbl_radar_title)
        
        self.radar_widget = RadarChartWidget(self)
        ly_card_radar.addWidget(self.radar_widget)
        ly_right.addWidget(card_radar)
        
        # 填充數據到雷達圖
        comp = self.s.get("comp_score", 50.0)
        accum = self.s.get("accum_score", 50.0)
        trig = self.s.get("trig_score", 50.0)
        win_rate = self.s.get("win_rate", 50.0)
        vol_slope = self.s.get("volume_slope", 1.0)
        resonance = self.s.get("sector_resonance", 0.0)
        self.radar_widget.set_scores(comp, accum, trig, win_rate, vol_slope, resonance)

        # (K線圖)
        card_kline = QFrame()
        card_kline.setObjectName("card_teaching")
        ly_card_kline = QVBoxLayout(card_kline)
        ly_card_kline.setContentsMargins(5, 5, 5, 5)
        
        lbl_kline_title = QLabel(" 📈 個股歷史日K線與操作區間")
        lbl_kline_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #10B981; margin-top: 5px; margin-left: 5px;")
        ly_card_kline.addWidget(lbl_kline_title)
        
        self.kline_widget = CandlestickChartWidget(self)
        ly_card_kline.addWidget(self.kline_widget)
        ly_right.addWidget(card_kline)

        # 啟動日K異步抓取
        self.kline_worker = KLineFetchWorker(self.s.get("code", ""), is_us=self.is_us, parent=self)
        self.kline_worker.finished.connect(self.on_kline_loaded)
        self.kline_worker.error.connect(self.on_kline_error)
        self.kline_worker.start()

        # 5. 按鈕列
        ly_btn = QHBoxLayout()
        
        btn_copy = QPushButton("📋 複製心法文字")
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        btn_copy.clicked.connect(self.copy_teaching_text)
        ly_btn.addWidget(btn_copy)
        
        ly_btn.addStretch()
        
        btn_close = QPushButton("我知道了，遵照風控執行")
        btn_close.clicked.connect(self.accept)
        ly_btn.addWidget(btn_close)
        
        layout.addLayout(ly_btn)

    def on_kline_error(self, err_msg):
        self.kline_widget.set_error(err_msg)

    def on_kline_loaded(self, data):
        inst_dict = self.s.get("trade_instruction", {})
        limit_price = inst_dict.get("limit_price", 0.0) or inst_dict.get("trigger_price", 0.0)
        stop_loss = inst_dict.get("stop_loss", 0.0)
        self.kline_widget.set_data(data, limit_price=limit_price, stop_loss=stop_loss)
        
        full_closes = data.get("full_closes", [])
        full_opens = data.get("full_opens", [])
        full_highs = data.get("full_highs", [])
        full_lows = data.get("full_lows", [])
        full_volumes = data.get("full_volumes", [])
        
        self.weekly_regime = None
        self.backtest_results = None
        
        if full_closes:
            self.weekly_regime, _ = self.calculate_weekly_trend(full_closes)
            self.backtest_results = self.run_historical_backtest(
                full_opens, full_highs, full_lows, full_closes, full_volumes, self.s.get("timing_class", "Decline")
            )
            
        html = self.generate_teaching_html(self.weekly_regime, self.backtest_results)
        self.tb_teaching.setHtml(html)

    def calculate_weekly_trend(self, closes):
        weekly_closes = []
        for i in range(len(closes) - 1, -1, -5):
            weekly_closes.append(closes[i])
        weekly_closes.reverse()
        
        if len(weekly_closes) < 5:
            return "未知", 0.0
            
        ma_window = 20
        if len(weekly_closes) >= ma_window:
            weekly_ma20 = sum(weekly_closes[-ma_window:]) / ma_window
            prev_ma20 = sum(weekly_closes[-ma_window-5:-5]) / ma_window if len(weekly_closes) >= ma_window + 5 else weekly_ma20
        else:
            weekly_ma20 = sum(weekly_closes) / len(weekly_closes)
            prev_ma20 = weekly_ma20
            
        current_price = closes[-1]
        is_above_ma20 = current_price >= weekly_ma20
        is_upward = weekly_ma20 >= prev_ma20
        
        if is_above_ma20 and is_upward:
            weekly_regime = "🔥 長線多頭主升段 (長線護航中)"
        elif is_above_ma20:
            weekly_regime = "🟢 長線高檔盤整"
        elif is_upward:
            weekly_regime = "🟡 長線回檔支撐測試"
        else:
            weekly_regime = "❄️ 長線空頭整理 (審慎防守)"
            
        return weekly_regime, weekly_ma20

    def run_historical_backtest(self, opens, highs, lows, closes, volumes, timing_class):
        n = len(closes)
        if n < 40:
            return None
            
        ma5 = []
        ma20 = []
        for i in range(n):
            ma5.append(sum(closes[max(0, i-4):i+1]) / float(min(i+1, 5)))
            ma20.append(sum(closes[max(0, i-19):i+1]) / float(min(i+1, 20)))
            
        ma20_vol = []
        for i in range(n):
            ma20_vol.append(sum(volumes[max(0, i-19):i+1]) / float(min(i+1, 20)))
            
        match_indices = []
        
        for i in range(20, n - 10):
            price = closes[i]
            chg = (closes[i] - closes[i-1])/closes[i-1]*100 if i > 0 else 0.0
            
            max_20d = max(highs[max(0, i-19):i+1])
            dist_high = (price - max_20d)/max_20d*100 if max_20d > 0 else 0.0
            
            vol_ratio = volumes[i] / ma20_vol[i] if ma20_vol[i] > 0 else 1.0
            
            is_match = False
            if timing_class == "E_BREAKOUT":
                if chg > 3.0 and price > ma20[i] and price > ma5[i] and vol_ratio >= 1.3:
                    is_match = True
            elif timing_class == "A_BREAKOUT":
                if -2.5 <= dist_high <= 0.5 and chg > 0.5 and vol_ratio >= 1.2:
                    is_match = True
            elif timing_class == "B_READY":
                recent_high = max(highs[max(0, i-4):i+1])
                recent_low = min(lows[max(0, i-4):i+1])
                range_pct = (recent_high - recent_low)/price*100 if price > 0 else 0.0
                if price > ma20[i] and range_pct < 3.5 and abs(chg) < 1.5 and vol_ratio <= 0.8:
                    is_match = True
            elif timing_class == "C_PULLBACK":
                if ma5[i] > ma20[i] and price <= ma5[i] * 1.025 and price >= ma20[i] * 0.985 and vol_ratio <= 1.0:
                    is_match = True
            else:
                if price < ma20[i]:
                    is_match = True
                    
            if is_match:
                match_indices.append(i)
                
        if not match_indices:
            return None
            
        win_5d = 0
        win_10d = 0
        return_5d = []
        return_10d = []
        
        for idx in match_indices:
            p_entry = closes[idx]
            p_5d = closes[min(n-1, idx + 5)]
            p_10d = closes[min(n-1, idx + 10)]
            
            ret_5d = (p_5d - p_entry) / p_entry * 100 if p_entry > 0 else 0.0
            ret_10d = (p_10d - p_entry) / p_entry * 100 if p_entry > 0 else 0.0
            
            return_5d.append(ret_5d)
            return_10d.append(ret_10d)
            
            if ret_5d > 0: win_5d += 1
            if ret_10d > 0: win_10d += 1
            
        total = len(match_indices)
        win_rate_5d = win_5d / total * 100
        win_rate_10d = win_10d / total * 100
        avg_ret_5d = sum(return_5d) / total
        avg_ret_10d = sum(return_10d) / total
        
        return {
            "total_samples": total,
            "win_rate_5d": round(win_rate_5d, 1),
            "win_rate_10d": round(win_rate_10d, 1),
            "avg_ret_5d": round(avg_ret_5d, 2),
            "avg_ret_10d": round(avg_ret_10d, 2)
        }

    def show_browser_context_menu(self, pos):
        menu = self.tb_teaching.createStandardContextMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
            QMenu::item:disabled {
                color: #64748B;
            }
        """)
        menu.exec(self.tb_teaching.mapToGlobal(pos))

    def copy_teaching_text(self):
        plain_text = self.generate_plain_text()
        clipboard = QApplication.clipboard()
        clipboard.setText(plain_text)
        QMessageBox.information(self, "已複製", "心法教學文字已複製到剪貼簿。")

    def generate_plain_text(self):
        s = self.s
        inst_dict = s.get("trade_instruction", {})
        action = inst_dict.get("action", "WATCH")
        action_label = inst_dict.get("action_label", "整理觀望")
        reason = inst_dict.get("reason", "整理觀望中")
        timing_label = s.get("timing_label", "未知時機")
        qai = s.get("comp_score", 0.0) + s.get("accum_score", 0.0) + s.get("trig_score", 0.0)
        win_rate = s.get("win_rate", 50.0)
        price = s.get("price", 0.0)
        chg = s.get("change_pct", 0.0)
        chg_sign = "+" if chg > 0 else ""
        
        lines = []
        lines.append(f"💡 新手買賣心法教學 — {s.get('code', '')} {s.get('name', '')} ({s.get('theme', '未知題材')})")
        lines.append(f"🎯 適用週期：日K中線波段交易 (數天至數週)")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💰 最新價：{price:.2f} ({chg_sign}{chg:.2f}%)")
        lines.append(f"📌 QAI評分：{qai:.1f} 分 ｜ AI 信心度：{win_rate:.1f}%")
        lines.append(f"⚡ 雷達交易指示：{action_label}")
        
        if "BUY" in action:
            limit_price = inst_dict.get("limit_price", 0.0)
            trigger_price = inst_dict.get("trigger_price", 0.0)
            stop_loss = inst_dict.get("stop_loss", 0.0)
            tp1 = inst_dict.get("take_profit_1", 0.0)
            tp2 = inst_dict.get("take_profit_2", 0.0)
            shares = inst_dict.get("shares", 0)
            lots = inst_dict.get("lots", 0)
            odd = inst_dict.get("odd_lot_shares", 0)
            
            p_text = f"{limit_price:.2f} 元" if limit_price > 0 else f"{trigger_price:.2f} 元"
            p_lbl = "建議買入價" if limit_price > 0 else "突破觸發價"
            lines.append(f"👉 {p_lbl}：{p_text}")
            lines.append(f"🛡️ 建議防守停損價：{stop_loss:.2f} 元")
            lines.append(f"📈 第一停利點 (減碼)：{tp1:.2f} 元 ｜ 第二停利點 (出清)：{tp2:.2f} 元")
            if self.is_us:
                lines.append(f"📊 風控建議股數：{shares} 股")
            else:
                qty_text = f"{lots} 張又 {odd} 股" if lots > 0 else f"{odd} 股 (零股交易)"
                lines.append(f"📊 風控建議股數：{qty_text}")
        elif action == "SELL":
            sl = inst_dict.get("stop_loss", 0.0)
            lines.append(f"🛡️ 防守離場點：{sl:.2f} 元")
            lines.append(f"📝 原因說明：{reason}")
        elif action == "AVOID":
            sl = inst_dict.get("stop_loss", 0.0)
            lines.append(f"🛡️ 參考防守價：{sl:.2f} 元")
            lines.append(f"🚨 警示說明：{reason} (假突破風險大，請勿追高)")
        else:
            alert = inst_dict.get("alert_price", 0.0)
            if alert > 0:
                lines.append(f"👉 關注突破價：{alert:.2f} 元")
            lines.append("📝 狀態說明：整理蓄能中，尚未出現多頭爆發訊號")
            
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        if self.weekly_regime:
            lines.append(f"📈 週K長線大局觀：{self.weekly_regime}")
            lines.append("")
            
        if self.backtest_results:
            win_5d = float(self.backtest_results.get("win_rate_5d", 50.0))
            if win_5d < 50.0:
                lines.append("🔴 歷史驗證不足")
                lines.append(f"雖然目前技術面符合 {timing_label.split('：')[-1]}型態，但本股票過去 6 個月出現相同訊號時，5 日上漲勝率僅 {win_5d:.1f}%，歷史表現不佳，建議降低部位或列入觀察。")
                lines.append("")
            elif win_5d > 70.0:
                lines.append("🟢 歷史驗證良好")
                lines.append(f"本型態過去成功率高，5 日上漲勝率達 {win_5d:.1f}%，屬於值得優先關注的交易機會。")
                lines.append("")
                
        lines.append("📖 白話文心法指南：")
        
        timing = s.get("timing_class", "Decline")
        trap = s.get("trap_bomb_rate", 10.0)
        
        if timing in ["E_BREAKOUT", "A_BREAKOUT"] and "BUY" in action:
            lines.append(f"【突破爆發型態 (時機：{timing_label})】")
            lines.append("為什麼叫我買進？本股目前處於突破型態，股價剛剛強勢越過先前整理平台或創下20日新高，並伴隨著成交量放大（主力大單吃貨）。")
            lines.append("【新手買進指引】")
            lines.append("1. 不要開盤無腦追高：若開盤股價跳空大漲超過 3% 以上，建議先不要急著追，等待盤中拉回建議價附近再建倉。")
            lines.append(f"2. 停損是你的防彈衣：停損設在 {inst_dict.get('stop_loss', 0.0):.2f} 元。若收盤跌破此價位表示假突破，請堅決執行停損！")
            lines.append(f"3. 分批停利法：達到第一停利點 {inst_dict.get('take_profit_1', 0.0):.2f} 元賣出半數持股；其餘抱到第二停利點 {inst_dict.get('take_profit_2', 0.0):.2f} 元。")
        elif timing in ["B_READY", "C_PULLBACK"] and "BUY" in action:
            lines.append(f"【低點布局型態 (時機：{timing_label})】")
            lines.append("為什麼叫我買進？股價目前處於底部整理成熟、主力籌碼鎖定，或者在多頭軌道中健康拉回至均線強支撐區，此時買進具備極高的安全邊際。")
            lines.append("【新手買進指引】")
            lines.append(f"1. 限價掛單，耐心等待：在建議買入價 {inst_dict.get('limit_price', 0.0):.2f} 元附近掛限價單等待成交，不要急躁追買高價。")
            lines.append(f"2. 防守位置極佳：停損價設在 {inst_dict.get('stop_loss', 0.0):.2f} 元，因為買在支撐區附近，若跌破代表支撐失效，損益比非常划算。")
            lines.append("3. 耐心等待發動：低點布局型態後可能還會悶盤整理幾天，一旦主力放量長紅突破，股價就會朝目標價噴發。")
        elif action == "SELL":
            lines.append("【大盤恐慌/空頭避險】")
            lines.append("為什麼叫我出場？大盤目前處於恐慌/空頭階段，或個股已跌破生命防守線（如20MA）。空頭市場中80%股票都會下跌，防守保留現金是唯一真理。")
            lines.append("【新手避險指引】")
            lines.append("1. 留得青山在：持有此股者請嚴量防守停損價，收盤跌破時建議無條件賣出，防範後續更大風險。")
            lines.append("2. 空手是最好的操作：此時大盤風控指標不佳，請絕對不要在此刻建立新倉。")
        elif action == "AVOID":
            lines.append(f"【假突破風險警示 (機率：{trap:.1f}%)】")
            lines.append("為什麼不追？從量化籌碼看：三大法人並未跟進，或股價位在高檔且量能嚴重不足，此為經典的假突破誘多陷阱。")
            lines.append("【新手防守指引】")
            lines.append("1. 空手不追高：千萬不要因為看到股票大漲就產生錯失恐懼（FOMO）而追進去，容易立刻套牢在波段高點。")
            lines.append("2. 持有者設防守：若已經持有，建議在股價跌破防守線時先行獲利了結或減碼。")
        else:
            lines.append(f"【整理觀望型態 (時機：{timing_label})】")
            lines.append("目前處於長期整理、潛伏蓄能階段。股價波動幅度小，主力正在洗盤吸籌，還沒有發出即時突破發動的強烈訊號。")
            lines.append("【新手追蹤指引】")
            lines.append("1. 列入自選股追蹤：此時不需要急著買進資金被卡住。可將其加入自選，每天關注發動成熟度。")
            lines.append("2. 等放量紅棒再動手：一旦出現帶量突破平台，或時機標籤轉為 A級/E級時，才是勝率最高的進場時機。")
        if self.backtest_results:
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("📊 該股同型態歷史回測統計 (近6個月)")
            lines.append(f"符合型態樣本數：\n{self.backtest_results['total_samples']} 次")
            lines.append(f"持有 5 天上漲概率：\n{self.backtest_results['win_rate_5d']}% (均回報: {self.backtest_results['avg_ret_5d']}%)")
            lines.append(f"持有 10 天上漲概率：\n{self.backtest_results['win_rate_10d']}% (均回報: {self.backtest_results['avg_ret_10d']}%)")
            lines.append("")
            
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 如何配合「日內即時分析」？")
        lines.append("本「買賣心法」是您的波段大方向（日K級別）。當本頁面發出買入訊號後，您可以進一步參考右鍵選單中的「日內即時分析」，利用盤中的 1 分鐘 K 線強弱（例如股價是否站穩於當日均價 VWAP 上方、量比是否放大）來尋找今日最有利的掛單買點或突破切入時點。")
        
        return "\n".join(lines)


# ----------------- Live 閃擊監控警報視窗 -----------------
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QSequentialAnimationGroup, QPauseAnimation, Slot
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QApplication
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QBrush, QPen

class LiveAlertPopup(QWidget):
    def __init__(self, code, name, timing_label, qai_score, price, change_pct, parent=None):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.code = code
        self.name = name
        self.timing_label = timing_label
        self.qai_score = qai_score
        self.price = price
        self.change_pct = change_pct
        
        self.init_ui()
        
    def init_ui(self):
        self.setFixedSize(320, 120)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(6)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)
        
        ly_title = QHBoxLayout()
        lbl_timing = QLabel(self.timing_label)
        lbl_timing.setStyleSheet("color: #FBBF24; font-size: 14px; font-weight: bold; font-family: 'Microsoft JhengHei', sans-serif;")
        
        lbl_qai = QLabel(f"QAI 分數: {self.qai_score:.1f}")
        lbl_qai.setStyleSheet("color: #10B981; font-size: 12px; font-weight: bold; font-family: 'Microsoft JhengHei', sans-serif; background: rgba(16, 185, 129, 0.15); border-radius: 4px; padding: 2px 6px;")
        
        ly_title.addWidget(lbl_timing)
        ly_title.addStretch()
        ly_title.addWidget(lbl_qai)
        main_layout.addLayout(ly_title)
        
        lbl_stock = QLabel(f"{self.name} ({self.code})")
        lbl_stock.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; font-family: 'Microsoft JhengHei', sans-serif;")
        main_layout.addWidget(lbl_stock)
        
        ly_price = QHBoxLayout()
        lbl_price = QLabel(f"價格 {self.price:.2f}")
        lbl_price.setStyleSheet("color: #E2E8F0; font-size: 12px; font-family: 'Microsoft JhengHei', sans-serif;")
        
        chg_color = "#FF5B60" if self.change_pct > 0 else ("#34D399" if self.change_pct < 0 else "#94A3B8")
        chg_sign = "+" if self.change_pct > 0 else ""
        lbl_change = QLabel(f"{chg_sign}{self.change_pct:.2f}%")
        lbl_change.setStyleSheet(f"color: {chg_color}; font-size: 12px; font-weight: bold; font-family: 'Microsoft JhengHei', sans-serif;")
        
        ly_price.addWidget(lbl_price)
        ly_price.addWidget(lbl_change)
        ly_price.addStretch()
        
        lbl_tips = QLabel("⚡ 點擊關閉")
        lbl_tips.setStyleSheet("color: #64748B; font-size: 10px; font-family: 'Microsoft JhengHei', sans-serif;")
        ly_price.addWidget(lbl_tips)
        
        main_layout.addLayout(ly_price)
        
        screen = QApplication.primaryScreen().geometry()
        self.start_x = screen.width() - self.width() - 25
        self.target_y = screen.height() - self.height() - 60
        self.start_y = screen.height()
        
        self.move(self.start_x, self.start_y)
        
        self.anim_pos = QPropertyAnimation(self, b"pos")
        self.anim_pos.setDuration(450)
        self.anim_pos.setStartValue(QPoint(self.start_x, self.start_y))
        self.anim_pos.setEndValue(QPoint(self.start_x, self.target_y))
        
        self.anim_opacity = QPropertyAnimation(self, b"windowOpacity")
        self.anim_opacity.setDuration(500)
        self.anim_opacity.setStartValue(1.0)
        self.anim_opacity.setEndValue(0.0)
        self.anim_opacity.finished.connect(self.close)
        
        self.seq_anim = QSequentialAnimationGroup(self)
        self.seq_anim.addAnimation(self.anim_pos)
        self.seq_anim.addAnimation(QPauseAnimation(4500))
        self.seq_anim.addAnimation(self.anim_opacity)
        self.seq_anim.start()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(26, 32, 44, 230))
        gradient.setColorAt(1, QColor(17, 24, 39, 230))
        
        border_pen = QPen(QColor(96, 165, 250, 120))
        border_pen.setWidth(1.5)
        
        painter.setPen(border_pen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8.0, 8.0)
        
    def mousePressEvent(self, event):
        self.close()

# ----------------- UI 介面實作 -----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("勝率雷達 WinRadar v2.0.0")
        
        # 尋找並設定視窗圖標
        import sys
        icon_name = "winradar.ico"
        possible_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name),
            os.path.join(os.path.dirname(sys.argv[0]), icon_name),
        ]
        if hasattr(sys, '_MEIPASS'):
            possible_paths.append(os.path.join(sys._MEIPASS, icon_name))
            
        for path in possible_paths:
            if os.path.exists(path):
                self.setWindowIcon(QIcon(path))
                break
                
        self.resize(1300, 850)
        self.setup_styling()
        self.setup_ui()
        self.scan_worker = None
        self.latest_data = None
        if os.path.exists(LAST_SCAN_CACHE_FILE):
            try:
                self.latest_data = load_json_cache(LAST_SCAN_CACHE_FILE)
                if self.latest_data:
                    QtCore.QTimer.singleShot(150, self.restore_last_scan_ui)
            except Exception as e:
                logging.error(f"載入上次掃描快取數據失敗: {e}")
        
        # 配置日誌攔截
        self.setup_logger()
        logging.info("雷達系統 UI 初始化完成。")
        
        # 初始化 Live 監控定時器與警報管理器
        self.active_alerts = []
        self.timer_live = QtCore.QTimer(self)
        self.timer_live.timeout.connect(self.run_live_scan)
        self.live_scan_worker = None
        self.live_us_scan_worker = None
        self._live_force_run = False

    def restore_last_scan_ui(self):
        if not self.latest_data:
            return
        try:
            # 還原大盤卡片 UI
            scan_time = self.latest_data.get("scan_time")
            if scan_time:
                self.lbl_idx_title.setText(f"發行量加權股價指數 (TAIEX)  [最後掃描: {scan_time}]")
            regime = self.latest_data.get("regime", {})
            status_text = regime.get("status", "未知狀態")
            index_p = regime.get("index_p", 0.0)
            change_pct = regime.get("change_pct", 0.0)
            if index_p > 0:
                self.lbl_idx_val.setText(f"{index_p:.2f} 點 ({round(change_pct, 2)}%)")
                if change_pct > 0:
                    self.lbl_idx_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #FF5B60;")
                elif change_pct < 0:
                    self.lbl_idx_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #34D399;")
                else:
                    self.lbl_idx_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
            self.lbl_reg_val.setText(status_text)
            multiplier = regime.get("multiplier", 1.0)
            if multiplier == 0.5:
                self.lbl_reg_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #FF5B60;")
            elif multiplier == 0.8:
                self.lbl_reg_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFB800;")
            else:
                self.lbl_reg_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #05D994;")
                
            # 還原美股大盤卡片 UI
            us_regime = self.latest_data.get("us_regime", {})
            us_scan_time = self.latest_data.get("us_scan_time")
            if us_scan_time:
                self.lbl_dow_title.setText(f"道瓊工業 (^DJI)  [最後掃描: {us_scan_time}]")
            if us_regime:
                def update_index_ui(val_label, chg_label, data):
                    price = data.get("price", 0.0)
                    change_pct = data.get("change_pct", 0.0)
                    change_val = data.get("change_val", 0.0)
                    if price > 0.0:
                        val_label.setText(f"{price:,.2f}")
                        if change_pct > 0:
                            chg_label.setText(f"▲ {change_val:,.2f} (+{change_pct:.2f}%)")
                            chg_label.setStyleSheet("font-size: 11px; color: #FF5B60; font-weight: bold;")
                            val_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FF5B60;")
                        elif change_pct < 0:
                            chg_label.setText(f"▼ {abs(change_val):,.2f} ({change_pct:.2f}%)")
                            chg_label.setStyleSheet("font-size: 11px; color: #34D399; font-weight: bold;")
                            val_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #34D399;")
                        else:
                            chg_label.setText(f"  0.00 (0.00%)")
                            chg_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
                            val_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
                update_index_ui(self.lbl_dow_val, self.lbl_dow_chg, us_regime.get("dow", {}))
                update_index_ui(self.lbl_nas_val, self.lbl_nas_chg, us_regime.get("nasdaq", {}))
                update_index_ui(self.lbl_sp_val, self.lbl_sp_chg, us_regime.get("sp500", {}))
                update_index_ui(self.lbl_sox_val, self.lbl_sox_chg, us_regime.get("sox", {}))

            self.render_table(self.tbl_stocks, self.latest_data.get("stocks", []), is_etf=False)
            self.render_table(self.tbl_etfs, self.latest_data.get("etfs", []), is_etf=True)
            if "us_stocks" in self.latest_data:
                self.render_us_table(self.latest_data.get("us_stocks", []))
            self.render_advice_board(self.latest_data)
            self.render_lazier_table()
            logging.info("歷史掃描看板數據加載成功，介面還原完畢。")
        except Exception as e:
            logging.error(f"還原歷史掃描看板異常: {e}", exc_info=True)
        
    def setup_logger(self):
        log_handler = QTextEditLogHandler(self.log_panel)
        log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
        logging.getLogger().addHandler(log_handler)
        logging.getLogger().setLevel(logging.INFO)
        
    def setup_styling(self):
        # 現代化 Premium 暗色風格樣式表 (QSS)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0B0F17;
            }
            QWidget {
                color: #E2E8F0;
                font-family: "Microsoft JhengHei", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QFrame#card {
                background-color: #151C2C;
                border: 1px solid #23304A;
                border-radius: 10px;
            }
            QFrame#card QLabel {
                border: none;
            }
            QTabWidget::pane {
                border: 1px solid #23304A;
                background-color: #151C2C;
                border-radius: 10px;
            }
            QTabBar::tab {
                background-color: #0D1322;
                border: 1px solid #23304A;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 22px;
                color: #64748B;
                font-weight: bold;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: #151C2C;
                color: #3B82F6;
                border-bottom: 2px solid #3B82F6;
            }
            QTabBar::tab:hover:!selected {
                background-color: #101726;
                color: #F8FAFC;
            }
            QTableWidget {
                background-color: #151C2C;
                alternate-background-color: #1C2539;
                gridline-color: #23304A;
                border: none;
                selection-background-color: #2D3748;
                selection-color: #FFFFFF;
                outline: none;
            }
            QHeaderView::section {
                background-color: #1E293B;
                color: #94A3B8;
                padding: 8px;
                border: 1px solid #23304A;
                font-weight: bold;
            }
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #60A5FA;
            }
            QPushButton:pressed {
                background-color: #2563EB;
            }
            QPushButton#btn_run, QPushButton#btn_run_stocks, QPushButton#btn_run_etfs {
                background-color: #10B981;
                color: #0B0F17;
                font-size: 13px;
                border-radius: 8px;
            }
            QPushButton#btn_run:hover, QPushButton#btn_run_stocks:hover, QPushButton#btn_run_etfs:hover {
                background-color: #34D399;
            }
            QLineEdit {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                color: #F8FAFC;
            }
            QLineEdit:focus {
                border: 1px solid #3B82F6;
            }
            QTextEdit {
                background-color: #0A0E1A;
                border: 1px solid #23304A;
                border-radius: 8px;
                color: #34D399;
                font-family: "Consolas", monospace;
                font-size: 12px;
            }
            QProgressBar {
                border: 1px solid #23304A;
                border-radius: 6px;
                text-align: center;
                background-color: #0D1322;
                color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                width: 10px;
                border-radius: 3px;
            }
            QComboBox {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 30px 6px 12px;
                color: #F8FAFC;
                min-width: 100px;
            }
            QComboBox:hover {
                border: 1px solid #475569;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left-width: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E293B;
                border: 1px solid #334155;
                color: #F8FAFC;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
                outline: none;
                padding: 4px;
            }
            QScrollBar:vertical {
                border: none;
                background: #0B0F17;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #0B0F17;
                height: 8px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #334155;
                min-width: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #475569;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QMenu {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
            QMenu::item:disabled {
                color: #64748B;
            }
            QTableCornerButton::section {
                background-color: #1E293B;
                border: 1px solid #23304A;
            }
            QMessageBox {
                background-color: #151C2C;
            }
            QMessageBox QLabel {
                color: #E2E8F0;
            }
            QMessageBox QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
                min-width: 70px;
            }
            QMessageBox QPushButton:hover {
                background-color: #60A5FA;
            }
            QMessageBox QPushButton:pressed {
                background-color: #2563EB;
            }
        """)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # --- Bento Grid 市場總覽區 ---
        bento_layout = QGridLayout()
        bento_layout.setSpacing(10)
        
        # 加權指數卡片
        self.card_index = QFrame()
        self.card_index.setObjectName("card")
        ly_idx = QVBoxLayout(self.card_index)
        ly_idx.setContentsMargins(12, 10, 12, 10)
        self.lbl_idx_title = QLabel("發行量加權股價指數 (TAIEX)")
        self.lbl_idx_title.setStyleSheet("color: #94A3B8; font-size: 12px;")
        self.lbl_idx_val = QLabel("資料未載入")
        self.lbl_idx_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        ly_idx.addWidget(self.lbl_idx_title)
        ly_idx.addWidget(self.lbl_idx_val)
        bento_layout.addWidget(self.card_index, 0, 0)
        
        # 大盤 Regime 卡片
        self.card_regime = QFrame()
        self.card_regime.setObjectName("card")
        ly_reg = QVBoxLayout(self.card_regime)
        ly_reg.setContentsMargins(12, 10, 12, 10)
        self.lbl_reg_title = QLabel("大盤市場 Regime 風險狀態")
        self.lbl_reg_title.setStyleSheet("color: #94A3B8; font-size: 12px;")
        self.lbl_reg_val = QLabel("待掃描確定")
        self.lbl_reg_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #60A5FA;")
        ly_reg.addWidget(self.lbl_reg_title)
        ly_reg.addWidget(self.lbl_reg_val)
        bento_layout.addWidget(self.card_regime, 0, 1)
        
        # 系統控制卡片
        self.card_ctrl = QFrame()
        self.card_ctrl.setObjectName("card")
        ly_ctrl = QVBoxLayout(self.card_ctrl)
        ly_ctrl.setContentsMargins(12, 6, 12, 6)
        ly_ctrl.setSpacing(4)
        
        # 快取 CheckBox
        self.cb_use_cache = QCheckBox("開啟盤後快取優化 (推薦，3秒極速)")
        self.cb_use_cache.setChecked(False)
        self.cb_use_cache.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        ly_ctrl.addWidget(self.cb_use_cache)
        
        # Live 監控 CheckBox
        self.cb_live_monitor = QCheckBox("🔔 開啟盤中 Live 閃擊監控 (自選股)")
        self.cb_live_monitor.setChecked(False)
        self.cb_live_monitor.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        self.cb_live_monitor.stateChanged.connect(self.toggle_live_monitor)
        ly_ctrl.addWidget(self.cb_live_monitor)
        
        # 按鈕列
        ly_btns = QHBoxLayout()
        ly_btns.setSpacing(6)
        
        self.btn_run = QPushButton("⚡ 全掃描")
        self.btn_run.setObjectName("btn_run")
        self.btn_run.setMinimumHeight(32)
        self.btn_run.clicked.connect(self.start_full_scan)
        
        self.btn_run_stocks = QPushButton("📈 僅個股")
        self.btn_run_stocks.setObjectName("btn_run_stocks")
        self.btn_run_stocks.setMinimumHeight(32)
        self.btn_run_stocks.clicked.connect(self.start_stocks_scan)
        
        self.btn_run_etfs = QPushButton("📊 僅 ETF")
        self.btn_run_etfs.setObjectName("btn_run_etfs")
        self.btn_run_etfs.setMinimumHeight(32)
        self.btn_run_etfs.clicked.connect(self.start_etfs_scan)
        
        ly_btns.addWidget(self.btn_run)
        ly_btns.addWidget(self.btn_run_stocks)
        ly_btns.addWidget(self.btn_run_etfs)
        
        ly_ctrl.addLayout(ly_btns)
        # 新增更新基本面按鈕
        self.btn_update_fund = QPushButton("🔄 更新基本面 (清除快取)")
        self.btn_update_fund.setObjectName("btn_run_stocks")
        self.btn_update_fund.setMinimumHeight(32)
        self.btn_update_fund.setStyleSheet("background-color: #334155; color: #E2E8F0; font-size: 11px;")
        self.btn_update_fund.clicked.connect(self.clear_fundamentals_cache)
        ly_ctrl.addWidget(self.btn_update_fund)
        bento_layout.addWidget(self.card_ctrl, 0, 2)

        # === 美股 Bento Grid 第二列 ===
        # 卡片1: 道瓊與納指
        self.card_us_regime_1 = QFrame()
        self.card_us_regime_1.setObjectName("card")
        ly_us1 = QVBoxLayout(self.card_us_regime_1)
        ly_us1.setContentsMargins(12, 8, 12, 8)
        ly_us1.setSpacing(4)
        
        # 道瓊工業
        self.lbl_dow_title = QLabel("道瓊工業 (^DJI)")
        self.lbl_dow_title.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        self.lbl_dow_val = QLabel("資料未載入")
        self.lbl_dow_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        self.lbl_dow_chg = QLabel("")
        self.lbl_dow_chg.setStyleSheet("font-size: 11px;")
        
        # 那斯達克
        self.lbl_nas_title = QLabel("那斯達克 (^IXIC)")
        self.lbl_nas_title.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        self.lbl_nas_val = QLabel("資料未載入")
        self.lbl_nas_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        self.lbl_nas_chg = QLabel("")
        self.lbl_nas_chg.setStyleSheet("font-size: 11px;")
        
        ly_us1.addWidget(self.lbl_dow_title)
        ly_us1.addWidget(self.lbl_dow_val)
        ly_us1.addWidget(self.lbl_dow_chg)
        
        # 分割線
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        line1.setStyleSheet("background-color: #334155; max-height: 1px; border: none; margin: 2px 0;")
        ly_us1.addWidget(line1)
        
        ly_us1.addWidget(self.lbl_nas_title)
        ly_us1.addWidget(self.lbl_nas_val)
        ly_us1.addWidget(self.lbl_nas_chg)
        
        bento_layout.addWidget(self.card_us_regime_1, 1, 0)
        
        # 卡片2: S&P 500 與費城半導體
        self.card_us_regime_2 = QFrame()
        self.card_us_regime_2.setObjectName("card")
        ly_us2 = QVBoxLayout(self.card_us_regime_2)
        ly_us2.setContentsMargins(12, 8, 12, 8)
        ly_us2.setSpacing(4)
        
        # S&P 500
        self.lbl_sp_title = QLabel("S&P 500 指數 (^GSPC)")
        self.lbl_sp_title.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        self.lbl_sp_val = QLabel("資料未載入")
        self.lbl_sp_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        self.lbl_sp_chg = QLabel("")
        self.lbl_sp_chg.setStyleSheet("font-size: 11px;")
        
        # 費城半導體
        self.lbl_sox_title = QLabel("費城半導體 (^SOX)")
        self.lbl_sox_title.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        self.lbl_sox_val = QLabel("資料未載入")
        self.lbl_sox_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        self.lbl_sox_chg = QLabel("")
        self.lbl_sox_chg.setStyleSheet("font-size: 11px;")
        
        ly_us2.addWidget(self.lbl_sp_title)
        ly_us2.addWidget(self.lbl_sp_val)
        ly_us2.addWidget(self.lbl_sp_chg)
        
        # 分割線
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        line2.setStyleSheet("background-color: #334155; max-height: 1px; border: none; margin: 2px 0;")
        ly_us2.addWidget(line2)
        
        ly_us2.addWidget(self.lbl_sox_title)
        ly_us2.addWidget(self.lbl_sox_val)
        ly_us2.addWidget(self.lbl_sox_chg)
        
        bento_layout.addWidget(self.card_us_regime_2, 1, 1)
        
        # 美股控制卡片
        self.card_us_ctrl = QFrame()
        self.card_us_ctrl.setObjectName("card")
        ly_us_ctrl = QVBoxLayout(self.card_us_ctrl)
        ly_us_ctrl.setContentsMargins(12, 12, 12, 12)
        ly_us_ctrl.setSpacing(0)
        
        self.btn_run_us = QPushButton("🇺🇸 美股全掃描")
        self.btn_run_us.setObjectName("btn_run")
        self.btn_run_us.setMinimumHeight(40)
        self.btn_run_us.clicked.connect(self.start_us_scan)
        ly_us_ctrl.addWidget(self.btn_run_us)
        
        # 保留變數以相容其他引用
        self.lbl_us_input = QLabel()
        self.txt_us_custom_input = QLineEdit()
        self.btn_run_us_custom = QPushButton()
        
        bento_layout.addWidget(self.card_us_ctrl, 1, 2)
        
        main_layout.addLayout(bento_layout)
        
        # --- 主要分頁區 ---
        self.tabs = QTabWidget()
        
        # 0. 新手懶人選股看板分頁
        self.tab_lazier = QWidget()
        ly_lz = QVBoxLayout(self.tab_lazier)
        ly_lz.setContentsMargins(8, 8, 8, 8)
        
        ly_flt_lz = QHBoxLayout()
        ly_flt_lz.addWidget(QLabel("訊號過濾："))
        self.cb_filter_lz = QComboBox()
        self.cb_filter_lz.addItems(["全部訊號", "🔥 買進訊號", "🔴 避險/減碼訊號", "⏳ 觀察/潛伏"])
        self.cb_filter_lz.currentIndexChanged.connect(self.filter_lazier_table)
        ly_flt_lz.addWidget(self.cb_filter_lz)
        
        lbl_lz_tip = QLabel("💡 提示：按右鍵可選擇『新手買賣心法教學』。系統基於單筆交易 0.5% 風險限額自動計算建議股數。")
        lbl_lz_tip.setStyleSheet("color: #60A5FA; font-size: 11px; margin-left: 10px;")
        ly_flt_lz.addWidget(lbl_lz_tip)
        ly_flt_lz.addStretch()
        ly_lz.addLayout(ly_flt_lz)
        
        self.tbl_lazier = QTableWidget()
        self.setup_lazier_table_headers(self.tbl_lazier)
        self.tbl_lazier.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl_lazier.customContextMenuRequested.connect(self.show_lazier_context_menu)
        ly_lz.addWidget(self.tbl_lazier)
        self.tabs.addTab(self.tab_lazier, "🍀 新手懶人看板 (Lazier)")
        
        # 1. 個股分頁
        self.tab_stocks = QWidget()
        ly_st = QVBoxLayout(self.tab_stocks)
        ly_st.setContentsMargins(8, 8, 8, 8)
        
        # 篩選器與控制列
        ly_flt_s = QHBoxLayout()
        ly_flt_s.addWidget(QLabel("時機分組過濾："))
        self.cb_filter_s = QComboBox()
        self.cb_filter_s.addItems([
            "全部標的", 
            "🚀 E級：動能爆發",
            "⚡ A級：突破確認", 
            "🟢 B級：整理完成", 
            "🟡 C級：回檔低吸", 
            "🧊 D級：潛伏觀察",
            "💤 整理觀望區",
            "🎯 均線粘合與向上發散",
            "💎 縮量『地量』出現",
            "🕳️ 『挖坑』誘空洗盤",
            "🏹 壓力位『試盤』信號"
        ])
        self.cb_filter_s.currentIndexChanged.connect(self.filter_stocks_table)
        ly_flt_s.addWidget(self.cb_filter_s)
        ly_flt_s.addStretch()
        ly_st.addLayout(ly_flt_s)
        
        self.tbl_stocks = QTableWidget()
        self.setup_table_headers(self.tbl_stocks, is_etf=False)
        self.tbl_stocks.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl_stocks.customContextMenuRequested.connect(self.show_stocks_context_menu)
        ly_st.addWidget(self.tbl_stocks)
        self.tabs.addTab(self.tab_stocks, "📈 台股個股雷達 (Stocks)")
        
        # 2. ETF 分頁
        self.tab_etfs = QWidget()
        ly_et = QVBoxLayout(self.tab_etfs)
        ly_et.setContentsMargins(8, 8, 8, 8)
        
        ly_flt_e = QHBoxLayout()
        ly_flt_e.addWidget(QLabel("時機分組過濾："))
        self.cb_filter_e = QComboBox()
        self.cb_filter_e.addItems(["全部標的", "🚀 E級：動能爆發", "⚡ A級：突破確認", "🟢 B級：整理完成", "🟡 C級：回檔低吸", "🧊 D級：潛伏觀察", "💤 整理觀望區"])
        self.cb_filter_e.currentIndexChanged.connect(self.filter_etfs_table)
        ly_flt_e.addWidget(self.cb_filter_e)
        ly_flt_e.addStretch()
        ly_et.addLayout(ly_flt_e)
        
        self.tbl_etfs = QTableWidget()
        self.setup_table_headers(self.tbl_etfs, is_etf=True)
        self.tbl_etfs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl_etfs.customContextMenuRequested.connect(self.show_etfs_context_menu)
        ly_et.addWidget(self.tbl_etfs)
        self.tabs.addTab(self.tab_etfs, "📊 台股 ETF 雷達 (ETFs)")
        
        # 3. 自選診斷分頁
        self.tab_custom = QWidget()
        ly_cu = QVBoxLayout(self.tab_custom)
        ly_cu.setContentsMargins(12, 12, 12, 12)
        ly_cu.setSpacing(10)
        
        ly_cu_input = QHBoxLayout()
        ly_cu_input.addWidget(QLabel("請輸入診斷代碼 (逗號分隔，如 2330, 0050, 00980A)："))
        self.txt_custom_input = QLineEdit()
        self.txt_custom_input.setPlaceholderText("例如: 2330, 3680, 0050, 00980A")
        ly_cu_input.addWidget(self.txt_custom_input)
        
        self.btn_run_custom = QPushButton("🔍 執行指定量化掃描")
        self.btn_run_custom.clicked.connect(self.start_custom_scan)
        ly_cu_input.addWidget(self.btn_run_custom)
        
        self.btn_serenity_custom = QPushButton("💡 Serenity 卡點診斷")
        self.btn_serenity_custom.clicked.connect(self.trigger_serenity_diagnose_custom)
        ly_cu_input.addWidget(self.btn_serenity_custom)
        
        ly_cu.addLayout(ly_cu_input)
        
        self.tbl_custom = QTableWidget()
        self.setup_table_headers(self.tbl_custom, is_etf=False, is_custom=True)
        self.tbl_custom.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl_custom.customContextMenuRequested.connect(self.show_custom_context_menu)
        ly_cu.addWidget(self.tbl_custom)
        self.tabs.addTab(self.tab_custom, "🔍 自選深度診斷 (Custom)")
        
        # 5. 美股分頁
        self.tab_us_stocks = QWidget()
        ly_us = QVBoxLayout(self.tab_us_stocks)
        ly_us.setContentsMargins(8, 8, 8, 8)
        
        ly_flt_us = QHBoxLayout()
        ly_flt_us.addWidget(QLabel("時機分組過濾："))
        self.cb_filter_us = QComboBox()
        self.cb_filter_us.addItems([
            "全部標的", 
            "🚀 E級：動能爆發",
            "⚡ A級：突破確認", 
            "🟢 B級：整理完成", 
            "🟡 C級：回檔低吸", 
            "🧊 D級：潛伏觀察",
            "💤 整理觀望區",
            "🎯 均線粘合與向上發散",
            "💎 縮量『地量』出現",
            "🕳️ 『挖坑』動作",
            "🏹 關鍵壓力位試盤信號"
        ])
        self.cb_filter_us.currentIndexChanged.connect(self.filter_us_stocks_table)
        ly_flt_us.addWidget(self.cb_filter_us)
        ly_flt_us.addStretch()
        ly_us.addLayout(ly_flt_us)
        
        self.tbl_us_stocks = QTableWidget()
        self.setup_us_table_headers(self.tbl_us_stocks)
        self.tbl_us_stocks.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl_us_stocks.customContextMenuRequested.connect(self.show_us_stocks_context_menu)
        ly_us.addWidget(self.tbl_us_stocks)
        self.tabs.addTab(self.tab_us_stocks, "🇺🇸 美股 AI 半導體雷達 (US Stocks)")
        
        # 4. 戰術解讀板
        self.tab_advice = QWidget()
        ly_ad = QVBoxLayout(self.tab_advice)
        ly_ad.setContentsMargins(12, 12, 12, 12)
        self.txt_advice_board = QTextEdit()
        self.txt_advice_board.setReadOnly(True)
        self.txt_advice_board.setStyleSheet("background-color: #111622; color: #E2E8F0; font-size: 13px; font-family: monospace;")
        ly_ad.addWidget(self.txt_advice_board)
        self.tabs.addTab(self.tab_advice, "🧭 系統戰術指引板 (Tactics)")
        
        # 6. 監控池管理分頁
        self.initSetupTab()
        
        main_layout.addWidget(self.tabs, stretch=7)
        
        # --- 下方進度列與日誌控制板 ---
        bottom_splitter = QSplitter(Qt.Vertical)
        
        # 進度列
        progress_widget = QWidget()
        ly_pr = QHBoxLayout(progress_widget)
        ly_pr.setContentsMargins(0, 0, 0, 0)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(20)
        self.lbl_progress_desc = QLabel("系統準備就緒，請點擊上方按鈕開始掃描。")
        self.lbl_progress_desc.setStyleSheet("color: #94A3B8;")
        ly_pr.addWidget(self.progress_bar, stretch=3)
        ly_pr.addWidget(self.lbl_progress_desc, stretch=7)
        bottom_splitter.addWidget(progress_widget)
        
        # 日誌面板
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMinimumHeight(120)
        bottom_splitter.addWidget(self.log_panel)
        
        main_layout.addWidget(bottom_splitter, stretch=3)

    def initSetupTab(self):
        """初始化監控池管理 (Setup) 分頁"""
        self.tab_setup = QWidget()
        ly_setup = QVBoxLayout(self.tab_setup)
        ly_setup.setContentsMargins(12, 12, 12, 12)
        ly_setup.setSpacing(10)

        # 使用 Splitter 分割左側分類與右側股票
        splitter = QSplitter(Qt.Horizontal)
        
        # --- 左側分類管理 ---
        left_widget = QWidget()
        ly_left = QVBoxLayout(left_widget)
        ly_left.setContentsMargins(0, 0, 0, 0)
        ly_left.setSpacing(8)
        
        lbl_left = QLabel("📂 監控大項 (分類)")
        lbl_left.setStyleSheet("font-weight: bold; font-size: 14px; color: #6366F1;")
        ly_left.addWidget(lbl_left)
        
        # 市場選擇下拉選單
        ly_mkt = QHBoxLayout()
        ly_mkt.addWidget(QLabel("選擇市場: "))
        self.cb_setup_market = QComboBox()
        self.cb_setup_market.addItems(["🇹🇼 台股 (TW)", "🇺🇸 美股 (US)"])
        self.cb_setup_market.currentIndexChanged.connect(self.on_setup_market_changed)
        ly_mkt.addWidget(self.cb_setup_market)
        ly_left.addLayout(ly_mkt)
        
        self.lst_groups = QListWidget()
        self.lst_groups.setStyleSheet("background-color: #111622; color: #E2E8F0; font-size: 13px;")
        self.lst_groups.currentRowChanged.connect(self.on_setup_group_changed)
        ly_left.addWidget(self.lst_groups)
        
        # 左側按鈕區
        ly_left_btns = QHBoxLayout()
        self.btn_add_group = QPushButton("➕ 新增大項")
        self.btn_rename_group = QPushButton("✏️ 改名")
        self.btn_del_group = QPushButton("➖ 刪除大項")
        
        self.btn_add_group.clicked.connect(self.on_setup_add_group)
        self.btn_rename_group.clicked.connect(self.on_setup_rename_group)
        self.btn_del_group.clicked.connect(self.on_setup_del_group)
        
        ly_left_btns.addWidget(self.btn_add_group)
        ly_left_btns.addWidget(self.btn_rename_group)
        ly_left_btns.addWidget(self.btn_del_group)
        ly_left.addLayout(ly_left_btns)
        
        splitter.addWidget(left_widget)
        
        # --- 右側股票管理 ---
        right_widget = QWidget()
        ly_right = QVBoxLayout(right_widget)
        ly_right.setContentsMargins(0, 0, 0, 0)
        ly_right.setSpacing(8)
        
        lbl_right = QLabel("📋 股票清單 (打勾表示全掃描時啟用)")
        lbl_right.setStyleSheet("font-weight: bold; font-size: 14px; color: #10B981;")
        ly_right.addWidget(lbl_right)
        
        self.tbl_setup_stocks = QTableWidget()
        self.tbl_setup_stocks.setColumnCount(4)
        self.tbl_setup_stocks.setHorizontalHeaderLabels(["啟用", "代碼", "名稱", "題材定位"])
        self.tbl_setup_stocks.setStyleSheet("background-color: #111622; color: #E2E8F0; font-size: 13px;")
        self.tbl_setup_stocks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_setup_stocks.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_setup_stocks.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_setup_stocks.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_setup_stocks.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        
        self.tbl_setup_stocks.cellChanged.connect(self.on_setup_cell_changed)
        ly_right.addWidget(self.tbl_setup_stocks)
        
        # 右側新增股票輸入區
        ly_add_stock = QHBoxLayout()
        
        self.txt_add_stock_code = QLineEdit()
        self.txt_add_stock_code.setPlaceholderText("代碼 (如 2330 / NVDA)")
        self.txt_add_stock_code.setMaximumWidth(120)
        self.txt_add_stock_code.textChanged.connect(self.on_setup_code_text_changed)
        
        self.txt_add_stock_name = QLineEdit()
        self.txt_add_stock_name.setPlaceholderText("名稱 (如 台積電)")
        self.txt_add_stock_name.setMaximumWidth(150)
        
        self.txt_add_stock_theme = QLineEdit()
        self.txt_add_stock_theme.setPlaceholderText("題材定位")
        
        self.btn_add_stock = QPushButton("➕ 新增股票")
        self.btn_add_stock.clicked.connect(self.on_setup_add_stock)
        
        self.btn_del_stock = QPushButton("➖ 刪除所選")
        self.btn_del_stock.clicked.connect(self.on_setup_del_stock)
        
        ly_add_stock.addWidget(QLabel("新增股票: "))
        ly_add_stock.addWidget(self.txt_add_stock_code)
        ly_add_stock.addWidget(self.txt_add_stock_name)
        ly_add_stock.addWidget(self.txt_add_stock_theme)
        ly_add_stock.addWidget(self.btn_add_stock)
        ly_add_stock.addWidget(self.btn_del_stock)
        ly_right.addLayout(ly_add_stock)
        
        splitter.addWidget(right_widget)
        
        # 設置 splitter 的初始寬度分配
        splitter.setSizes([250, 750])
        ly_setup.addWidget(splitter)
        
        # --- 底部儲存套用區 ---
        ly_bottom = QHBoxLayout()
        self.btn_save_setup = QPushButton("💾 儲存並套用設定")
        self.btn_save_setup.setStyleSheet("background-color: #4F46E5; color: white; font-weight: bold; font-size: 14px; padding: 6px 12px;")
        self.btn_save_setup.clicked.connect(self.on_setup_save)
        
        self.lbl_setup_status = QLabel("")
        self.lbl_setup_status.setStyleSheet("color: #34D399; font-weight: bold;")
        
        ly_bottom.addWidget(self.btn_save_setup)
        ly_bottom.addWidget(self.lbl_setup_status)
        ly_bottom.addStretch()
        ly_setup.addLayout(ly_bottom)
        
        self.tabs.addTab(self.tab_setup, "⚙️ 監控池管理 (Setup)")
        
        # 載入資料至介面
        self.refresh_setup_groups()

    def on_setup_market_changed(self):
        """當切換市場 (台股/美股) 時，重新整理左側大項與右側股票"""
        self.refresh_setup_groups()
        self.txt_add_stock_code.clear()
        self.txt_add_stock_name.clear()
        self.txt_add_stock_theme.clear()

    def refresh_setup_groups(self, select_group=None):
        """重新整理左側大項清單，根據目前選擇的市場 (台股/美股)"""
        self.lst_groups.blockSignals(True)
        self.lst_groups.clear()
        
        is_us = self.cb_setup_market.currentIndex() == 1
        curr_sector_map = US_SECTOR_MAP if is_us else SECTOR_MAP
        
        groups = list(curr_sector_map.keys())
        self.lst_groups.addItems(groups)
        
        self.lst_groups.blockSignals(False)
        
        if select_group and select_group in groups:
            idx = groups.index(select_group)
            self.lst_groups.setCurrentRow(idx)
        elif groups:
            self.lst_groups.setCurrentRow(0)
        else:
            self.tbl_setup_stocks.setRowCount(0)

    def on_setup_group_changed(self, row):
        """當左側選中的大項改變時，渲染右側股票表格"""
        if row < 0:
            self.tbl_setup_stocks.setRowCount(0)
            return
            
        group_name = self.lst_groups.item(row).text()
        self.render_setup_stocks_table(group_name)

    def render_setup_stocks_table(self, group_name):
        """渲染右側指定大項下的股票表格"""
        self.tbl_setup_stocks.blockSignals(True)
        self.tbl_setup_stocks.setRowCount(0)
        
        is_us = self.cb_setup_market.currentIndex() == 1
        curr_sector_map = US_SECTOR_MAP if is_us else SECTOR_MAP
        curr_stock_map = US_STOCK_MAP if is_us else AI_STOCK_MAP
        curr_disabled = DISABLED_US_STOCKS if is_us else DISABLED_STOCKS
        
        codes = curr_sector_map.get(group_name, [])
        self.tbl_setup_stocks.setRowCount(len(codes))
        
        for idx, code in enumerate(codes):
            info = curr_stock_map.get(code, {"name": f"股票 {code}", "theme": "未知"})
            name = info.get("name", "")
            theme = info.get("theme", "")
            
            # 1. 啟用 CheckBox (第一欄)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            state = Qt.Unchecked if code in curr_disabled else Qt.Checked
            chk.setCheckState(state)
            self.tbl_setup_stocks.setItem(idx, 0, chk)
            
            # 2. 代碼 (唯讀)
            item_code = QTableWidgetItem(code)
            item_code.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.tbl_setup_stocks.setItem(idx, 1, item_code)
            
            # 3. 名稱 (可編輯)
            item_name = QTableWidgetItem(name)
            item_name.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.tbl_setup_stocks.setItem(idx, 2, item_name)
            
            # 4. 題材定位 (可編輯)
            item_theme = QTableWidgetItem(theme)
            item_theme.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.tbl_setup_stocks.setItem(idx, 3, item_theme)
            
        self.tbl_setup_stocks.blockSignals(False)

    def on_setup_cell_changed(self, row, col):
        """當表格單元格被修改時（CheckBox 改變或文字編輯）"""
        curr_row = self.lst_groups.currentRow()
        if curr_row < 0:
            return
        group_name = self.lst_groups.item(curr_row).text()
        
        is_us = self.cb_setup_market.currentIndex() == 1
        curr_sector_map = US_SECTOR_MAP if is_us else SECTOR_MAP
        curr_stock_map = US_STOCK_MAP if is_us else AI_STOCK_MAP
        curr_disabled = DISABLED_US_STOCKS if is_us else DISABLED_STOCKS
        
        codes = curr_sector_map.get(group_name, [])
        if row >= len(codes):
            return
            
        code = codes[row]
        
        if col == 0:
            item = self.tbl_setup_stocks.item(row, 0)
            if item:
                if item.checkState() == Qt.Checked:
                    curr_disabled.discard(code)
                else:
                    curr_disabled.add(code)
                self.lbl_setup_status.setText("⚠️ 設定已變更，請點擊「儲存並套用」")
        elif col == 2:
            item = self.tbl_setup_stocks.item(row, 2)
            if item and code in curr_stock_map:
                curr_stock_map[code]["name"] = item.text().strip()
                self.lbl_setup_status.setText("⚠️ 設定已變更，請點擊「儲存並套用」")
        elif col == 3:
            item = self.tbl_setup_stocks.item(row, 3)
            if item and code in curr_stock_map:
                curr_stock_map[code]["theme"] = item.text().strip()
                self.lbl_setup_status.setText("⚠️ 設定已變更，請點擊「儲存並套用」")

    def on_setup_add_group(self):
        """新增大項"""
        is_us = self.cb_setup_market.currentIndex() == 1
        curr_sector_map = US_SECTOR_MAP if is_us else SECTOR_MAP
        
        text, ok = QInputDialog.getText(self, "新增大項", "請輸入大項 (產業分類) 名稱：")
        if ok and text.strip():
            group_name = text.strip()
            if group_name in curr_sector_map:
                QMessageBox.warning(self, "錯誤", "該大項名稱已存在。")
                return
            curr_sector_map[group_name] = []
            self.refresh_setup_groups(select_group=group_name)
            self.lbl_setup_status.setText("⚠️ 設定已變更，請點擊「儲存並套用」")

    def on_setup_rename_group(self):
        """重新命名選中的大項"""
        curr_row = self.lst_groups.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "警告", "請先選取要重新命名的大項。")
            return
        old_name = self.lst_groups.item(curr_row).text()
        
        is_us = self.cb_setup_market.currentIndex() == 1
        curr_sector_map = US_SECTOR_MAP if is_us else SECTOR_MAP
        
        text, ok = QInputDialog.getText(self, "重新命名大項", f"將「{old_name}」重新命名為：", QLineEdit.Normal, old_name)
        if ok and text.strip():
            new_name = text.strip()
            if new_name == old_name:
                return
            if new_name in curr_sector_map:
                QMessageBox.warning(self, "錯誤", "該大項名稱已存在。")
                return
            curr_sector_map[new_name] = curr_sector_map.pop(old_name)
            self.refresh_setup_groups(select_group=new_name)
            self.lbl_setup_status.setText("⚠️ 設定已變更，請點擊「儲存並套用」")

    def on_setup_del_group(self):
        """刪除選中的大項"""
        curr_row = self.lst_groups.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "警告", "請先選取要刪除的大項。")
            return
        group_name = self.lst_groups.item(curr_row).text()
        
        is_us = self.cb_setup_market.currentIndex() == 1
        curr_sector_map = US_SECTOR_MAP if is_us else SECTOR_MAP
        curr_stock_map = US_STOCK_MAP if is_us else AI_STOCK_MAP
        curr_disabled = DISABLED_US_STOCKS if is_us else DISABLED_STOCKS
        
        reply = QMessageBox.question(self, "確認刪除", f"確認要刪除大項「{group_name}」嗎？\n(注意：此動作只會刪除此分類關係，該大項內的股票資料若在其他大項中仍會保留。)", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            codes = curr_sector_map.pop(group_name, [])
            for code in codes:
                still_exists = any(code in other_codes for other_codes in curr_sector_map.values())
                if not still_exists and code in curr_stock_map:
                    curr_stock_map.pop(code, None)
                    curr_disabled.discard(code)
            
            self.refresh_setup_groups()
            self.lbl_setup_status.setText("⚠️ 設定已變更，請點擊「儲存並套用」")

    def on_setup_code_text_changed(self, text):
        """當代碼輸入框改變時，嘗試從已知的對應中自動尋找股票名稱"""
        code = text.strip().upper()
        if not code:
            self.txt_add_stock_name.clear()
            self.txt_add_stock_theme.clear()
            return
            
        is_us = self.cb_setup_market.currentIndex() == 1
        curr_stock_map = US_STOCK_MAP if is_us else AI_STOCK_MAP
        curr_cache = GLOBAL_US_REALTIME_CACHE if is_us else GLOBAL_REALTIME_CACHE
        
        if code in curr_stock_map:
            self.txt_add_stock_name.setText(curr_stock_map[code].get("name", ""))
            self.txt_add_stock_theme.setText(curr_stock_map[code].get("theme", ""))
        elif code in curr_cache:
            self.txt_add_stock_name.setText(curr_cache[code].get("name", ""))

    def on_setup_add_stock(self):
        """在選中的大項中新增股票"""
        curr_row = self.lst_groups.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "警告", "請先選取要加入股票的監控大項。")
            return
        group_name = self.lst_groups.item(curr_row).text()
        
        code = self.txt_add_stock_code.text().strip().upper()
        name = self.txt_add_stock_name.text().strip()
        theme = self.txt_add_stock_theme.text().strip() or "自訂監控題材"
        
        if not code:
            QMessageBox.warning(self, "警告", "請輸入股票代碼。")
            return
            
        if not name:
            QMessageBox.warning(self, "警告", "請填寫股票名稱。")
            return

        is_us = self.cb_setup_market.currentIndex() == 1
        curr_sector_map = US_SECTOR_MAP if is_us else SECTOR_MAP
        curr_stock_map = US_STOCK_MAP if is_us else AI_STOCK_MAP

        if group_name not in curr_sector_map:
            curr_sector_map[group_name] = []
            
        if code not in curr_sector_map[group_name]:
            curr_sector_map[group_name].append(code)
            
        if code not in curr_stock_map:
            curr_stock_map[code] = {"name": name, "theme": theme}
        else:
            curr_stock_map[code]["name"] = name
            if theme != "自訂監控題材":
                curr_stock_map[code]["theme"] = theme
                
        self.render_setup_stocks_table(group_name)
        
        self.txt_add_stock_code.clear()
        self.txt_add_stock_name.clear()
        self.txt_add_stock_theme.clear()
        
        self.lbl_setup_status.setText("⚠️ 設定已變更，請點擊「儲存並套用」")

    def on_setup_del_stock(self):
        """從選中的大項中刪除所選股票"""
        curr_row = self.lst_groups.currentRow()
        if curr_row < 0:
            return
        group_name = self.lst_groups.item(curr_row).text()
        
        selected_ranges = self.tbl_setup_stocks.selectedRanges()
        if not selected_ranges:
            QMessageBox.warning(self, "警告", "請先點選表格中要刪除的股票。")
            return
            
        selected_rows = set()
        for r in selected_ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                selected_rows.add(row)
                
        if not selected_rows:
            return
            
        is_us = self.cb_setup_market.currentIndex() == 1
        curr_sector_map = US_SECTOR_MAP if is_us else SECTOR_MAP
        curr_stock_map = US_STOCK_MAP if is_us else AI_STOCK_MAP
        curr_disabled = DISABLED_US_STOCKS if is_us else DISABLED_STOCKS

        codes = curr_sector_map.get(group_name, [])
        sorted_rows = sorted(list(selected_rows), reverse=True)
        
        reply = QMessageBox.question(self, "確認刪除", f"確認要將這 {len(sorted_rows)} 檔股票從「{group_name}」中移除嗎？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for row in sorted_rows:
                if row < len(codes):
                    code = codes.pop(row)
                    still_exists = any(code in other_codes for other_codes in curr_sector_map.values())
                    if not still_exists:
                        curr_stock_map.pop(code, None)
                        curr_disabled.discard(code)
            
            self.tbl_setup_stocks.cellChanged.disconnect(self.on_setup_cell_changed)
            self.render_setup_stocks_table(group_name)
            self.tbl_setup_stocks.cellChanged.connect(self.on_setup_cell_changed)
            self.lbl_setup_status.setText("⚠️ 設定已變更，請點擊「儲存並套用」")

    def on_setup_save(self):
        """點擊儲存並套用按鈕"""
        save_user_universe()
        self.lbl_setup_status.setText("✅ 設定已儲存，並即時套用至全掃描！")
        QtCore.QTimer.singleShot(3000, lambda: self.lbl_setup_status.setText(""))

    def update_table_sort_indicator(self, table, logicalIndex, order):
        from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QIcon
        from PySide6.QtCore import Qt
        for col in range(table.columnCount()):
            item = table.horizontalHeaderItem(col)
            if item:
                item.setIcon(QIcon())
                
        pixmap = QPixmap(10, 10)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#94A3B8"))
        painter.setPen(Qt.NoPen)
        
        path = QPainterPath()
        if order == Qt.AscendingOrder:
            path.moveTo(5, 2)
            path.lineTo(1, 8)
            path.lineTo(9, 8)
        else:
            path.moveTo(5, 8)
            path.lineTo(1, 2)
            path.lineTo(9, 2)
        path.closeSubpath()
        painter.drawPath(path)
        painter.end()
        
        item = table.horizontalHeaderItem(logicalIndex)
        if item:
            item.setIcon(QIcon(pixmap))

    def clear_fundamentals_cache(self):
        global GLOBAL_FUNDAMENTALS_CACHE
        GLOBAL_FUNDAMENTALS_CACHE.clear()
        try:
            save_json_cache(FUNDAMENTALS_CACHE_FILE, GLOBAL_FUNDAMENTALS_CACHE)
            logging.info("基本面快取已成功清除！")
            QMessageBox.information(self, "成功", "基本面快取已清除，下一次掃描將重新線上獲取基本面數據。")
        except Exception as e:
            logging.error(f"清除基本面快取失敗: {e}")
            QMessageBox.critical(self, "錯誤", f"清除基本面快取失敗: {e}")

    def setup_table_headers(self, table, is_etf=False, is_custom=False):
        headers = [
            "代碼", "名稱", "最新價", "漲跌幅", "成交量", "QAI分數", "黑馬分數", "AI 信心度", "波段完成度",
            "外資連買", "自營/投信" if is_etf else "投信連買", "RS指標", "基本面", "時機分組", "⏳發動成熟度", "🔥主力推進", "🏭共振", "戰術操作指令"
        ]
        if is_custom:
            headers.insert(2, "類型")
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        
        # 為標頭欄位添加詳細的 ToolTip 說明
        tooltips = {
            "代碼": "證券代號，例如台積電為 2330。",
            "名稱": "證券名稱。\n滑鼠懸停於儲存格上，可查看所屬的產業主題或 ETF 類別。",
            "類型": "證券類型，區分為『個股』與『ETF』。",
            "最新價": "目前的即時或最後收盤價格（元）。",
            "漲跌幅": "今日收盤或即時漲跌百分比。紅色代表上漲，綠色代表下跌。",
            "成交量": "今日累計成交量（單位：張）。",
            "QAI分數": "QAI 綜合多因子打分：\n評估技術面收縮、籌碼面收集、量能速度等 9 大特徵因子的綜合得分（總分 100+加成）。\n用以衡量股票是否處於爆發前夕的最佳量價狀態。",
            "黑馬分數": "黑馬評分（Dark Horse Score）：\n評估量能極致壓縮（地量）、價格洗盤（黃金坑）、壓力位試盤等特徵，分數越高代表爆發黑馬潛力越大（0~100分）。",
            "AI 信心度": "AI 信心度（Confidence Score）：\n系統綜合評估時機分組與 QAI 得分，二次校正後的本波段爆發期望成功率或信心值（0~100%）。\n* 信心度 >= 80% (紅色/紫色)：信心極高，發動機率大。\n* 信心度 >= 70% (綠色)：信心偏高。\n* 信心度 < 70% (灰色)：信心一般。",
            "波段完成度": "波段完成度（Stage 1 Completion %）：\n評估當前波段價格上漲的成熟與完成進度，數值越接近 100% 代表本波段目標價已接近，需注意防守；接近 0% 代表仍在起漲點蓄勢。",
            "外資連買": "外資連續淨買超交易日天數。D 代表日（Days）。",
            "投信連買": "投信連續淨買超交易日天數. D 代表日（Days）。",
            "自營/投信": "自營商或投信連續淨買超交易日天數. D 代表日（Days）。",
            "RS指標": "相對強度指標（Relative Strength Score）：\n以個股過去 60 天報酬率扣除大盤 60 天報酬率得到超額報酬，並在全市場掃描標的（台灣或美股各自獨立）中進行百分位數排序（1~99分）。\n數值越接近 99 代表強度越強，越具備超額回報與黑馬潛力。",
            "基本面": "基本面綜合評分（Fundamental Score）：\n綜合評估營收年增率、毛利率方向、EPS 增長動能等指標加權計算而得的財務健康度評分（0~100分）。\n用以過濾基本面不佳、突破容易失敗的弱勢標的。",
            "時機分組": "發動時序分組：\n* 🚀 A級：臨界突破 (3日內極可能發動)\n* ⚠️ B級：高檔風險 (警惕假突破拉回陷阱)\n* 🟡 C級：回檔低吸 (多頭回踩均線支撐，非追高)\n* 🧊 D級：Silent Pool (波動極致壓縮的低位潛伏區)\n* 💤 整理觀望區 (目前無明確訊號，偏向整理)",
            "⏳發動成熟度": "⏳發動成熟度（Breakout Readiness Score）：\n依波動壓縮度、量能鎖定度、距離前高突破距離等 4 大量化因子綜合計算之爆發準備度（0~100 分）。\n* ⚡ 即將成熟 (>=90分)\n* 🔥 發動窗 (80~89分)\n* ⏳ 蓄勢整理 (70~79分)\n* 💤 長期整理 (60~69分)\n* 🧊 潛伏蓄能 (<60分)",
            "🔥主力推進": "主力推進強度（Smart Drive）：\n結合法人連買天數與量能爆發斜率所計算的主力資金動能。\n* 💤 無主力 (< 0.8)\n* ⚪ 輕微 (0.8~1.2)\n* 🟡 溫和 (1.2~2.0)\n* 🟢 強 (2.0~5.0)\n* 🔥 極強 (5.0~10.0)\n* ⚡ 異常放大 (>= 10.0)",
            "🏭共振": "🏭 產業族群共振分數（Resonance）：\n技術面同步(30%) + 量能同步(25%) + 題材關聯度(20%) + 方向一致性(15%) + 法人同步(10%)。\n* 分數 >= 70 (紅色)：主流族群極強共振，資金高度聚焦。\n* 分數 >= 50 (橘色)：族群溫和共振。\n* 顯示為 '-'：非主流產業鏈成員或 ETF。",
            "戰術操作指令": "依據大盤狀態與個股訊號綜合評分，由系統自動產出的實戰交易操作建議與風控指引（如限價買入、停損位置、防守降險等）。"
        }
        

        for col_idx, header_text in enumerate(headers):
            item = QTableWidgetItem(header_text)
            if header_text in tooltips:
                item.setToolTip(tooltips[header_text])
            table.setHorizontalHeaderItem(col_idx, item)

        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setShowGrid(True)
        table.setFocusPolicy(Qt.NoFocus)
        table.setSortingEnabled(True)
        try:
            table.horizontalHeader().sortIndicatorChanged.disconnect()
        except Exception:
            pass
        table.horizontalHeader().sortIndicatorChanged.connect(
            lambda idx, order: self.update_table_sort_indicator(table, idx, order)
        )

    def set_buttons_enabled(self, enabled):
        self.btn_run.setEnabled(enabled)
        self.btn_run_stocks.setEnabled(enabled)
        self.btn_run_etfs.setEnabled(enabled)
        self.btn_run_custom.setEnabled(enabled)
        if hasattr(self, 'btn_serenity_custom'):
            self.btn_serenity_custom.setEnabled(enabled)
        if hasattr(self, 'btn_run_us'):
            self.btn_run_us.setEnabled(enabled)

    def start_full_scan(self):
        self.run_scan(scan_mode="all")
        
    def start_stocks_scan(self):
        self.run_scan(scan_mode="stocks")
        
    def start_etfs_scan(self):
        self.run_scan(scan_mode="etfs")
        
    def run_scan(self, scan_mode):
        if self.scan_worker and self.scan_worker.isRunning():
            QMessageBox.warning(self, "警告", "掃描任務正在運行中，請耐心等待。")
            return
            
        use_cache = self.cb_use_cache.isChecked()
        self.set_buttons_enabled(False)
        self.btn_run.setText("⏳ 正在分析...")
        self.progress_bar.setValue(0)
        
        self.scan_worker = ScanWorker(scan_mode=scan_mode, use_cache=use_cache)
        self.scan_worker.progress_signal.connect(self.update_progress_ui)
        self.scan_worker.finished_signal.connect(self.scan_finished_callback)
        self.scan_worker.start()

    def toggle_live_monitor(self, state):
        if state == Qt.Checked or state == 2:
            self.timer_live.start(180000)
            logging.info("🔔 Live 閃擊監控已啟動，每 3 分鐘自動掃描一次自選股。")
            QtCore.QTimer.singleShot(1000, self.run_live_scan)
        else:
            self.timer_live.stop()
            logging.info("🔕 Live 閃擊監控已關閉。")

    def run_live_scan(self):
        if (self.scan_worker and self.scan_worker.isRunning()) or (hasattr(self, 'us_scan_worker') and self.us_scan_worker and self.us_scan_worker.isRunning()):
            logging.info("常規掃描任務正在運行，Live 監控跳過本次定時掃描。")
            return
            
        if (self.live_scan_worker and self.live_scan_worker.isRunning()) or (hasattr(self, 'live_us_scan_worker') and self.live_us_scan_worker and self.live_us_scan_worker.isRunning()):
            logging.info("上一次 Live 掃描尚未結束，跳過本次掃描。")
            return
            
        is_tw_open, _, _ = is_market_open()
        is_us_open, _, _ = is_us_market_open()
        
        force = getattr(self, '_live_force_run', False)
        if not force and not is_tw_open and not is_us_open:
            logging.info("Live 監控跳過：台美股均處於盤後非交易時段。")
            return
            
        text = self.txt_custom_input.text().strip()
        if not text:
            logging.info("Live 監控：未設定自選股代碼，跳過掃描。")
            return
            
        codes = [c.strip() for c in text.split(',') if c.strip()]
        if not codes:
            return
            
        tw_codes = [c for c in codes if not c[0].isalpha() and (is_tw_open or force)]
        us_codes = [c for c in codes if c[0].isalpha() and (is_us_open or force)]
        
        self.live_tw_results = []
        self.live_us_results = []
        self.live_pending_scans = []
        
        if tw_codes:
            self.live_pending_scans.append("tw")
            logging.info(f"Live 監控：啟動台股自選股掃描 {tw_codes} ...")
            self.live_scan_worker = ScanWorker(custom_codes=tw_codes, use_cache=False, latest_data=self.latest_data)
            self.live_scan_worker.finished_signal.connect(self.live_tw_finished_callback)
            self.live_scan_worker.start()
            
        if us_codes:
            self.live_pending_scans.append("us")
            logging.info(f"Live 監控：啟動美股自選股掃描 {us_codes} ...")
            self.live_us_scan_worker = USScanWorker(custom_tickers=us_codes, use_cache=False, latest_data=self.latest_data)
            self.live_us_scan_worker.finished_signal.connect(self.live_us_finished_callback)
            self.live_us_scan_worker.start()
            
        self._live_force_run = False

    @Slot(dict)
    def live_tw_finished_callback(self, results):
        self.live_tw_results = results.get("stocks", []) + results.get("etfs", [])
        if "tw" in self.live_pending_scans:
            self.live_pending_scans.remove("tw")
        self.check_live_scans_complete()

    @Slot(dict)
    def live_us_finished_callback(self, results):
        self.live_us_results = results.get("us_stocks", [])
        if "us" in self.live_pending_scans:
            self.live_pending_scans.remove("us")
        self.check_live_scans_complete()

    def check_live_scans_complete(self):
        if not self.live_pending_scans:
            logging.info("Live 監控自選股掃描完成。")
            all_live_results = self.live_tw_results + self.live_us_results
            if not all_live_results:
                return
                
            current_data = []
            for r in range(self.tbl_custom.rowCount()):
                code_item = self.tbl_custom.item(r, 0)
                if code_item:
                    s_data = code_item.data(Qt.UserRole)
                    if s_data:
                        current_data.append(s_data)
            
            data_map = {d["code"]: d for d in current_data}
            for new_d in all_live_results:
                data_map[new_d["code"]] = new_d
                
            merged_results = list(data_map.values())
            self.render_custom_table(merged_results)
            self.render_lazier_table()
            
            for stock in all_live_results:
                code = stock.get("code", "")
                name = stock.get("name", "")
                timing = stock.get("timing_class", "")
                qai = stock.get("qai_score", 0.0)
                price = stock.get("price", 0.0)
                change = stock.get("change_pct", 0.0)
                
                if timing in ("E_BREAKOUT", "A_BREAKOUT", "C_PULLBACK"):
                    timing_label = ""
                    if timing == "E_BREAKOUT":
                        timing_label = "🔥 E級：爆量發動"
                    elif timing == "A_BREAKOUT":
                        timing_label = "🚀 A級：突破發動"
                    elif timing == "C_PULLBACK":
                        timing_label = "🟢 C級：回檔低吸"
                        
                    self.show_live_alert(code, name, timing_label, qai, price, change)

    def show_live_alert(self, code, name, timing_label, qai_score, price, change_pct):
        valid_alerts = []
        for w in self.active_alerts:
            try:
                if w.isVisible():
                    valid_alerts.append(w)
            except RuntimeError:
                pass
        self.active_alerts = valid_alerts
        
        for w in self.active_alerts:
            if w.code == code:
                return
                
        popup = LiveAlertPopup(code, name, timing_label, qai_score, price, change_pct)
        
        screen = QApplication.primaryScreen().geometry()
        offset = len(self.active_alerts) * (popup.height() + 10)
        
        popup.target_y = screen.height() - popup.height() - 60 - offset
        popup.start_y = screen.height()
        
        popup.anim_pos.setEndValue(QPoint(popup.start_x, popup.target_y))
        popup.move(popup.start_x, popup.start_y)
        
        self.active_alerts.append(popup)
        popup.show()

    def start_custom_scan(self):
        text = self.txt_custom_input.text().strip()
        if not text:
            QMessageBox.warning(self, "警告", "請先輸入要診斷的股票或 ETF 代碼。")
            return
            
        codes = [c.strip() for c in text.split(',') if c.strip()]
        if (self.scan_worker and self.scan_worker.isRunning()) or (hasattr(self, 'us_scan_worker') and self.us_scan_worker and self.us_scan_worker.isRunning()):
            QMessageBox.warning(self, "警告", "掃描任務正在運行中，請耐心等待。")
            return
            
        tw_codes = [c for c in codes if not c[0].isalpha()]
        us_codes = [c for c in codes if c[0].isalpha()]

        self.custom_tw_results = []
        self.custom_us_results = []
        self.pending_scans = []

        if tw_codes:
            self.pending_scans.append("tw")
        if us_codes:
            self.pending_scans.append("us")

        if not self.pending_scans:
            QMessageBox.warning(self, "警告", "請輸入有效的股票或 ETF 代碼。")
            return

        use_cache = self.cb_use_cache.isChecked()
        self.set_buttons_enabled(False)
        self.progress_bar.setValue(0)
        
        if "tw" in self.pending_scans:
            self.scan_worker = ScanWorker(custom_codes=tw_codes, use_cache=use_cache, latest_data=self.latest_data)
            self.scan_worker.progress_signal.connect(self.update_progress_ui)
            self.scan_worker.finished_signal.connect(self.custom_tw_finished_callback)
            self.scan_worker.start()
            
        if "us" in self.pending_scans:
            self.us_scan_worker = USScanWorker(custom_tickers=us_codes, use_cache=use_cache, latest_data=self.latest_data)
            self.us_scan_worker.progress_signal.connect(self.update_progress_ui)
            self.us_scan_worker.finished_signal.connect(self.custom_us_finished_callback)
            self.us_scan_worker.start()

    @Slot(dict)
    def custom_tw_finished_callback(self, results):
        self.custom_tw_results = results.get("stocks", []) + results.get("etfs", [])
        if "tw" in self.pending_scans:
            self.pending_scans.remove("tw")
        self.check_custom_scans_complete()

    @Slot(dict)
    def custom_us_finished_callback(self, results):
        self.custom_us_results = results.get("us_stocks", [])
        if "us" in self.pending_scans:
            self.pending_scans.remove("us")
        self.check_custom_scans_complete()

    def check_custom_scans_complete(self):
        if not self.pending_scans:
            self.set_buttons_enabled(True)
            self.progress_bar.setValue(100)
            self.lbl_progress_desc.setText("指定深度診斷分析完成！")
            
            # 合併台美股結果並渲染自選表
            all_custom = self.custom_tw_results + self.custom_us_results
            self.render_custom_table(all_custom)
            
            # 同步更新新手懶人看板
            self.render_lazier_table()

    @Slot(int, str)
    def update_progress_ui(self, val, desc):
        self.progress_bar.setValue(val)
        self.lbl_progress_desc.setText(desc)
        logging.info(desc)

    @Slot(dict)
    def scan_finished_callback(self, results):
        self.set_buttons_enabled(True)
        self.btn_run.setText("⚡ 全掃描")
        try:
            self.progress_bar.setValue(100)
            regime = results.get("regime", {})
            status_text = regime.get("status", "未知狀態")
            
            if "掃描錯誤" in status_text or "中斷" in status_text:
                self.lbl_progress_desc.setText("掃描失敗！有部分數據出錯，請查看下方日誌。")
            else:
                self.lbl_progress_desc.setText("掃描完成！")
                
            # 狀態持久化合併邏輯
            scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            results["scan_time"] = scan_time
            if self.latest_data is None:
                self.latest_data = results
            else:
                self.latest_data["scan_time"] = scan_time
                if "regime" in results and results["regime"].get("status") != "未知狀態":
                    self.latest_data["regime"] = results["regime"]
                
                scan_mode = getattr(self.scan_worker, "scan_mode", "all")
                if scan_mode == "all":
                    self.latest_data["stocks"] = results.get("stocks", [])
                    self.latest_data["etfs"] = results.get("etfs", [])
                elif scan_mode == "stocks":
                    self.latest_data["stocks"] = results.get("stocks", [])
                elif scan_mode == "etfs":
                    self.latest_data["etfs"] = results.get("etfs", [])
                    
            regime = self.latest_data.get("regime", {})
            status_text = regime.get("status", "未知狀態")
            
            # 渲染大盤卡片
            scan_time = self.latest_data.get("scan_time", "")
            if scan_time:
                self.lbl_idx_title.setText(f"發行量加權股價指數 (TAIEX)  [最後掃描: {scan_time}]")
            index_p = regime.get("index_p", 0.0)
            change_pct = regime.get("change_pct", 0.0)
            if index_p > 0:
                self.lbl_idx_val.setText(f"{index_p:.2f} 點 ({round(change_pct, 2)}%)")
                if change_pct > 0:
                    self.lbl_idx_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #FF5B60;")
                elif change_pct < 0:
                    self.lbl_idx_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #34D399;")
                else:
                    self.lbl_idx_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
            else:
                self.lbl_idx_val.setText("無大盤資料")
                self.lbl_idx_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #64748B;")
            self.lbl_reg_val.setText(status_text)
            
            multiplier = regime.get("multiplier", 1.0)
            if multiplier == 0.5:
                self.lbl_reg_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #FF5B60;")
            elif multiplier == 0.8:
                self.lbl_reg_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFB800;")
            else:
                self.lbl_reg_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #05D994;")
                
            # 填入表格與戰術板
            self.render_table(self.tbl_stocks, self.latest_data.get("stocks", []), is_etf=False)
            self.render_table(self.tbl_etfs, self.latest_data.get("etfs", []), is_etf=True)
            self.render_advice_board(self.latest_data)
            
            # 將最後一次掃描結果持久化存檔
            save_json_cache(LAST_SCAN_CACHE_FILE, self.latest_data)
        except Exception as e:
            logging.error(f"渲染掃描結果異常: {e}", exc_info=True)
            self.lbl_progress_desc.setText(f"❌ 渲染失敗: {e}")

    @Slot(dict)
    def custom_scan_finished_callback(self, results):
        self.set_buttons_enabled(True)
        self.progress_bar.setValue(100)
        self.lbl_progress_desc.setText("指定深度診斷分析完成！")
        
        # 填入自選診斷表格
        all_custom = results["stocks"] + results["etfs"]
        self.render_custom_table(all_custom)
        
        # 同步更新新手懶人看板
        self.render_lazier_table()

    # ----------------- Serenity 診斷事件與右鍵選單 -----------------
    def show_stocks_context_menu(self, pos):
        self.show_context_menu(self.tbl_stocks, pos)
        
    def show_etfs_context_menu(self, pos):
        self.show_context_menu(self.tbl_etfs, pos)
        
    def show_custom_context_menu(self, pos):
        self.show_context_menu(self.tbl_custom, pos)
        
    def show_context_menu(self, table, pos):
        item = table.itemAt(pos)
        if not item:
            return
        row = item.row()
        code_item = table.item(row, 0)
        name_item = table.item(row, 1)
        if not code_item or not name_item:
            return
            
        code = code_item.text().strip()
        name = name_item.text().strip()
        
        # 優先讀取綁定的數據
        s = code_item.data(Qt.UserRole)
        is_etf_stock = False
        is_us_stock = False
        if s is not None:
            is_etf_stock = code_item.data(Qt.UserRole + 1) or False
            is_us_stock = code_item.data(Qt.UserRole + 2) or False
        else:
            is_us_stock = not any(char.isdigit() for char in code)
            is_etf_stock = code.startswith('00')
            
        table_price = None
        table_vol = None
        
        # 優先從綁定數據 s 讀取價格與成交量以保持數據一致
        if s is not None:
            table_price = s.get("price")
            table_vol = s.get("today_vol")
            
        # 若 s 中無數據或讀取失敗，作為備援再從 Table 中提取
        if table_price is None:
            price_col = 3 if (table == self.tbl_custom or table == self.tbl_lazier) else 2
            price_item = table.item(row, price_col)
            if price_item:
                try:
                    table_price = float(price_item.text().replace(',', '').strip())
                except ValueError:
                    pass
                    
        if table_vol is None:
            price_col = 3 if (table == self.tbl_custom or table == self.tbl_lazier) else 2
            if table != self.tbl_lazier:
                vol_item = table.item(row, price_col + 2)
                if vol_item:
                    try:
                        table_vol = float(vol_item.text().replace(',', '').strip())
                    except ValueError:
                        pass
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
            }
            QMenu::item {
                padding: 8px 24px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
        """)
        
        is_in_watchlist = False
        if is_us_stock:
            is_in_watchlist = (code in US_STOCK_MAP)
        else:
            is_in_watchlist = (code in AI_STOCK_MAP)
            
        clean_name = name.replace(" ➕", "").strip()
        
        action_teaching = menu.addAction(f"💡 新手買賣心法教學 ({code} {clean_name})")
        action_intraday = menu.addAction(f"📊 日內即時分析 ({code} {clean_name})")
        action_diagnose = menu.addAction(f"🔍 Serenity 深度卡點診斷 ({code} {clean_name})")
        action_web = menu.addAction(f"🌐 查詢個股新聞與簡介 ({code} {clean_name})")
        
        action_add_watchlist = None
        if not is_in_watchlist:
            action_add_watchlist = menu.addAction(f"➕ 將 {code} {clean_name} 加入監控池")
        
        action = menu.exec(table.mapToGlobal(pos))
        
        if action == action_intraday:
            self.trigger_intraday_analysis(code, clean_name, is_us=is_us_stock, table_price=table_price, table_vol=table_vol)
        elif action == action_diagnose:
            self.trigger_serenity_diagnose(code)
        elif action == action_web:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            if is_us_stock:
                url = f"https://finance.yahoo.com/quote/{code}"
            else:
                url = f"https://tw.stock.yahoo.com/quote/{code}.TW"
            QDesktopServices.openUrl(QUrl(url))
        elif action == action_teaching:
            if s is None:
                if self.latest_data:
                    for x in self.latest_data.get("stocks", []):
                        if x["code"] == code: s = x; break
                    if not s:
                        for x in self.latest_data.get("etfs", []):
                            if x["code"] == code: s = x; is_etf_stock = True; break
                    if not s:
                        for x in self.latest_data.get("us_stocks", []):
                            if x["code"] == code: s = x; is_us_stock = True; break
            if s is not None:
                s_copy = s.copy()
                if "name" in s_copy:
                    s_copy["name"] = s_copy["name"].replace(" ➕", "").strip()
                self.popup_teaching_dialog(s_copy, is_etf_stock, is_us_stock)
        elif action_add_watchlist and action == action_add_watchlist:
            self.add_stock_to_watchlist(code, name, is_us_stock)
            
    def add_stock_to_watchlist(self, code, name, is_us):
        # 移除名稱中的 "➕" 符號後綴，如果有話
        clean_name = name.replace(" ➕", "").strip()
        
        if is_us:
            if code in US_STOCK_MAP:
                QMessageBox.information(self, "提示", f"美股代碼 {code} 已經在監控池中。")
                return
            US_STOCK_MAP[code] = {
                "name": clean_name,
                "theme": "個股自選題材",
                "type": "個股"
            }
            if "個股自選題材" not in US_SECTOR_MAP:
                US_SECTOR_MAP["個股自選題材"] = []
            if code not in US_SECTOR_MAP["個股自選題材"]:
                US_SECTOR_MAP["個股自選題材"].append(code)
        else:
            if code in AI_STOCK_MAP:
                QMessageBox.information(self, "提示", f"台股代碼 {code} 已經在監控池中。")
                return
            is_etf = code.startswith('00')
            AI_STOCK_MAP[code] = {
                "name": clean_name,
                "theme": "個股自選題材",
                "type": "ETF" if is_etf else "個股"
            }
            if "個股自選題材" not in SECTOR_MAP:
                SECTOR_MAP["個股自選題材"] = []
            if code not in SECTOR_MAP["個股自選題材"]:
                SECTOR_MAP["個股自選題材"].append(code)
                
        # 儲存
        try:
            save_user_universe()
        except Exception as e:
            logging.error(f"儲存監控池失敗: {e}")
        
        # 同步更新自選診斷 Table 的 UI 名稱 (拿掉 ➕)
        if hasattr(self, 'tbl_custom'):
            for r in range(self.tbl_custom.rowCount()):
                c_item = self.tbl_custom.item(r, 0)
                if c_item and c_item.text().strip() == code:
                    n_item = self.tbl_custom.item(r, 1)
                    if n_item:
                        n_item.setText(clean_name)
                    break
                    
        # 切換 Setup 介面，並重新整理
        if hasattr(self, 'cb_setup_market') and hasattr(self, 'refresh_setup_groups'):
            try:
                self.cb_setup_market.setCurrentIndex(1 if is_us else 0)
                self.refresh_setup_groups(select_group="個股自選題材")
            except Exception as e:
                logging.error(f"同步 Setup 介面失敗: {e}")
            
        QMessageBox.information(self, "成功", f"已成功將 {code} {clean_name} 加入監控池群組『個股自選題材』！")
        
    def trigger_serenity_diagnose(self, code):
        if hasattr(self, 'serenity_worker') and self.serenity_worker and self.serenity_worker.isRunning():
            QMessageBox.warning(self, "警告", "已有 Serenity 診斷任務正在運行中，請稍候。")
            return
            
        progress = QProgressDialog("正在執行 Serenity 供應鏈卡點診斷，請稍候...", None, 0, 0, self)
        progress.setWindowTitle("診斷中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.setWindowFlags(progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        progress.show()
        
        self.serenity_worker = SerenityDiagnoseWorker(code, self)
        
        def on_finished(c_code, report_path, report_md):
            progress.close()
            dialog = SerenityReportDialog(c_code, report_path, report_md, self)
            dialog.exec()
            
        def on_error(c_code, error_msg):
            progress.close()
            QMessageBox.critical(self, "錯誤", f"診斷個股 {c_code} 失敗：\n{error_msg}")
            
        self.serenity_worker.finished.connect(on_finished)
        self.serenity_worker.error.connect(on_error)
        self.serenity_worker.start()
        
    def trigger_serenity_diagnose_custom(self):
        text = self.txt_custom_input.text().strip()
        if not text:
            QMessageBox.warning(self, "警告", "請先輸入要診斷的股票代碼。")
            return
            
        codes = [c.strip() for c in text.split(',') if c.strip()]
        if not codes:
            QMessageBox.warning(self, "警告", "請先輸入要診斷的股票代碼。")
            return
            
        self.trigger_serenity_diagnose(codes[0])
        
    def trigger_intraday_analysis(self, code, name, is_us=False, table_price=None, table_vol=None):
        if hasattr(self, 'intraday_worker') and self.intraday_worker and self.intraday_worker.isRunning():
            QMessageBox.warning(self, "警告", "已有日內即時分析任務正在運行中，請稍候.")
            return
            
        progress = QProgressDialog(f"正在執行 {code} {name} 日內即時分析，請稍候...", None, 0, 0, self)
        progress.setWindowTitle("分析中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.setWindowFlags(progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        progress.setStyleSheet("""
            QProgressDialog {
                background-color: #0F172A;
                color: #E2E8F0;
            }
            QLabel {
                color: #F8FAFC;
            }
        """)
        progress.show()
        
        self.intraday_worker = IntradayAnalysisWorker(code, name, is_us=is_us, table_price=table_price, table_vol=table_vol, parent=self)
        
        def on_finished(c_code, c_name, analysis_dict):
            progress.close()
            # 獲取波段交易指令的建議限價與停損，以供日內圖表標記
            limit_p = 0.0
            sl_p = 0.0
            target_stock = None
            if self.latest_data:
                for x in self.latest_data.get("stocks", []):
                    if x["code"] == c_code: target_stock = x; break
                if not target_stock:
                    for x in self.latest_data.get("etfs", []):
                        if x["code"] == c_code: target_stock = x; break
                if not target_stock:
                    for x in self.latest_data.get("us_stocks", []):
                        if x["code"] == c_code: target_stock = x; break
            if target_stock:
                inst = target_stock.get("trade_instruction", {})
                limit_p = inst.get("limit_price", 0.0) or inst.get("trigger_price", 0.0)
                sl_p = inst.get("stop_loss", 0.0)
            analysis_dict["limit_price"] = limit_p
            analysis_dict["stop_loss"] = sl_p
            
            dialog = IntradayAnalysisDialog(c_code, c_name, analysis_dict, self)
            dialog.exec()
            
        def on_error(c_code, error_msg):
            progress.close()
            QMessageBox.critical(self, "錯誤", f"分析 {c_code} {name} 失敗：\n{error_msg}")
            
        self.intraday_worker.finished.connect(on_finished)
        self.intraday_worker.error.connect(on_error)
        self.intraday_worker.start()
        
    # ----------------- UI 渲染與美化細節 -----------------
    def render_table(self, table, data_list, is_etf=False):
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for s in data_list:
            row_idx = table.rowCount()
            table.insertRow(row_idx)
            
            # 各欄位填入
            c_code = QTableWidgetItem(s["code"])
            c_code.setTextAlignment(Qt.AlignCenter)
            c_code.setData(Qt.UserRole, s)
            c_code.setData(Qt.UserRole + 1, is_etf)
            c_code.setData(Qt.UserRole + 2, False) # is_us = False
            
            c_name = QTableWidgetItem(s["name"])
            c_name.setTextAlignment(Qt.AlignCenter)
            c_name.setToolTip(s["theme"])
            
            c_price = NumericTableWidgetItem(f"{s['price']:.2f}")
            c_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_price.setData(Qt.UserRole + 99, float(s['price'] or 0.0))
            
            c_chg = NumericTableWidgetItem(f"{s['change_pct']:.2f}%")
            c_chg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_chg.setData(Qt.UserRole + 99, float(s['change_pct'] or 0.0))
            if s["change_pct"] > 0: c_chg.setForeground(QColor("#FF5B60"))
            elif s["change_pct"] < 0: c_chg.setForeground(QColor("#34D399"))
            
            c_vol = NumericTableWidgetItem(f"{s['today_vol']:,}")
            c_vol.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_vol.setData(Qt.UserRole + 99, float(s['today_vol'] or 0.0))
            
            qai_val = float(s['comp_score'] + s['accum_score'] + s['trig_score'])
            c_qai = NumericTableWidgetItem(f"{qai_val:.1f}")
            c_qai.setTextAlignment(Qt.AlignCenter)
            c_qai.setData(Qt.UserRole + 99, qai_val)
            
            # 黑馬分數著色
            dark_score = float(s.get("dark_horse_score", 0.0) or 0.0)
            dark_label = s.get("dark_horse_label", "")
            c_dark = NumericTableWidgetItem(f"{dark_score:.1f}")
            c_dark.setTextAlignment(Qt.AlignCenter)
            c_dark.setToolTip(f"{dark_label}｜黑馬分數 {dark_score:.1f}")
            c_dark.setData(Qt.UserRole + 99, dark_score)
            if dark_score >= 75:
                c_dark.setForeground(QColor("#C084FC"))
                c_dark.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif dark_score >= 65:
                c_dark.setForeground(QColor("#05D994"))
            elif dark_score >= 55:
                c_dark.setForeground(QColor("#FFB800"))
            else:
                c_dark.setForeground(QColor("#64748B"))
 
            # AI信心度著色
            win_rate = float(s.get("win_rate", 50.0) or 50.0)
            c_win = NumericTableWidgetItem(f"{win_rate:.1f}%")
            c_win.setTextAlignment(Qt.AlignCenter)
            c_win.setToolTip(f"AI 信心度：{win_rate:.1f}%")
            c_win.setData(Qt.UserRole + 99, win_rate)
            if win_rate >= 80:
                c_win.setForeground(QColor("#FF5B60"))
                c_win.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif win_rate >= 70:
                c_win.setForeground(QColor("#05D994"))
            else:
                c_win.setForeground(QColor("#64748B"))
 
            # 波段完成度著色
            completion = float(s.get("stage1_completion_pct", 0.0) or 0.0)
            completion_label = s.get("stage1_completion_label", "")
            c_completion = NumericTableWidgetItem(f"{completion:.1f}%")
            c_completion.setTextAlignment(Qt.AlignCenter)
            c_completion.setToolTip(f"{completion_label}｜第一波段完成度 {completion:.1f}%")
            c_completion.setData(Qt.UserRole + 99, completion)
            if completion >= 90:
                c_completion.setForeground(QColor("#FF5B60"))
                c_completion.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif completion >= 75:
                c_completion.setForeground(QColor("#C084FC"))
            elif completion >= 60:
                c_completion.setForeground(QColor("#05D994"))
            elif completion >= 40:
                c_completion.setForeground(QColor("#FFB800"))
            else:
                c_completion.setForeground(QColor("#64748B"))
            
            c_foreign = NumericTableWidgetItem(f"{s['foreign_consecutive']}D")
            c_foreign.setTextAlignment(Qt.AlignCenter)
            c_foreign.setData(Qt.UserRole + 99, int(s['foreign_consecutive'] or 0))
            
            # 自營商或投信
            second_inst = s['dealer_consecutive'] if is_etf else s['trust_consecutive']
            c_second_inst = NumericTableWidgetItem(f"{second_inst}D")
            c_second_inst.setTextAlignment(Qt.AlignCenter)
            c_second_inst.setData(Qt.UserRole + 99, int(second_inst or 0))
            
            # RS指標
            rs_val = s.get("rs_score", 50.0)
            c_rs = NumericTableWidgetItem(f"{rs_val:.1f}")
            c_rs.setTextAlignment(Qt.AlignCenter)
            c_rs.setData(Qt.UserRole + 99, float(rs_val))
            if rs_val >= 80:
                c_rs.setForeground(QColor("#FF5B60"))
                c_rs.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif rs_val >= 60:
                c_rs.setForeground(QColor("#FFB800"))
            else:
                c_rs.setForeground(QColor("#64748B"))

            # 基本面
            fund_val = s.get("fundamental_score", 50.0)
            c_fundamental = NumericTableWidgetItem(f"{fund_val:.1f}")
            c_fundamental.setTextAlignment(Qt.AlignCenter)
            c_fundamental.setData(Qt.UserRole + 99, float(fund_val))
            if fund_val >= 80:
                c_fundamental.setForeground(QColor("#FF5B60"))
                c_fundamental.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif fund_val >= 60:
                c_fundamental.setForeground(QColor("#05D994"))
            else:
                c_fundamental.setForeground(QColor("#64748B"))
            # 基本面 ToolTip (台股)
            fund_data = GLOBAL_FUNDAMENTALS_CACHE.get(s["code"])
            if fund_data:
                c_fundamental.setToolTip(
                    f"【基本面數據詳情 - {s['name']}】\n"
                    f"營收年增率 (YoY): {fund_data.get('revenue_yoy', 0.0)}%\n"
                    f"最新毛利率: {fund_data.get('gross_margin', 0.0)}%\n"
                    f"最新季度 EPS: {fund_data.get('latest_eps', 0.0)} 元\n"
                    f"EPS 年增率 (YoY): {fund_data.get('eps_yoy', 0.0)}%\n"
                    f"毛利率相較上季或去年同期提升: {'是' if fund_data.get('gross_margin_increased') else '否'}"
                )
            else:
                c_fundamental.setToolTip("暫無該股之詳細基本面數據 (點擊更新後可抓取)")
            
            # 時機分組與著色
            timing_map = {"E_BREAKOUT": 5, "A_BREAKOUT": 4, "B_READY": 3, "C_PULLBACK": 2, "D_SILENT": 1}
            timing_val = timing_map.get(s.get("timing_class", "Decline"), 0)
            c_timing = NumericTableWidgetItem(s["timing_label"])
            c_timing.setTextAlignment(Qt.AlignCenter)
            c_timing.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            c_timing.setData(Qt.UserRole + 99, timing_val)
            if s["timing_class"] == "E_BREAKOUT":
                c_timing.setForeground(QColor("#C084FC"))
            elif s["timing_class"] == "A_BREAKOUT":
                c_timing.setForeground(QColor("#05D994"))
            elif s["timing_class"] == "B_READY":
                c_timing.setForeground(QColor("#10B981"))
            elif s["timing_class"] == "C_PULLBACK":
                c_timing.setForeground(QColor("#FFB800"))
            elif s["timing_class"] == "D_SILENT":
                c_timing.setForeground(QColor("#00A3FF"))
                
            readiness_val = float(s.get("readiness_score", 0.0) or 0.0)
            c_countdown = NumericTableWidgetItem(s["countdown"])
            c_countdown.setTextAlignment(Qt.AlignCenter)
            c_countdown.setData(Qt.UserRole + 99, readiness_val)
            
            drive_val = float(s.get("smart_drive_value", 0.0) or 0.0)
            c_drive = NumericTableWidgetItem(s["smart_drive"])
            c_drive.setTextAlignment(Qt.AlignCenter)
            c_drive.setData(Qt.UserRole + 99, drive_val)
            
            # 產業共振分數
            res_val = s.get("sector_resonance", 0.0)
            c_resonance = NumericTableWidgetItem(f"{res_val:.0f}" if res_val > 0 else "-")
            c_resonance.setTextAlignment(Qt.AlignCenter)
            c_resonance.setData(Qt.UserRole + 99, float(res_val or 0.0))
            if res_val >= 70:
                c_resonance.setForeground(QColor("#FF5B60"))
                c_resonance.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif res_val >= 50:
                c_resonance.setForeground(QColor("#FFB800"))
            else:
                c_resonance.setForeground(QColor("#64748B"))
            
            inst_text = format_trade_instruction(s["trade_instruction"])
            c_inst = QTableWidgetItem(inst_text)
            c_inst.setToolTip(inst_text)
            
            table.setItem(row_idx, 0, c_code)
            table.setItem(row_idx, 1, c_name)
            table.setItem(row_idx, 2, c_price)
            table.setItem(row_idx, 3, c_chg)
            table.setItem(row_idx, 4, c_vol)
            table.setItem(row_idx, 5, c_qai)
            table.setItem(row_idx, 6, c_dark)
            table.setItem(row_idx, 7, c_win)
            table.setItem(row_idx, 8, c_completion)
            table.setItem(row_idx, 9, c_foreign)
            table.setItem(row_idx, 10, c_second_inst)
            table.setItem(row_idx, 11, c_rs)
            table.setItem(row_idx, 12, c_fundamental)
            table.setItem(row_idx, 13, c_timing)
            table.setItem(row_idx, 14, c_countdown)
            table.setItem(row_idx, 15, c_drive)
            table.setItem(row_idx, 16, c_resonance)
            table.setItem(row_idx, 17, c_inst)
            
        table.resizeColumnsToContents()
        table.setSortingEnabled(True)
    def render_custom_table(self, data_list):
        self.tbl_custom.setSortingEnabled(False)
        self.tbl_custom.setRowCount(0)
        for s in data_list:
            is_etf = s["code"].startswith('00')
            row_idx = self.tbl_custom.rowCount()
            self.tbl_custom.insertRow(row_idx)
            
            c_code = QTableWidgetItem(s["code"])
            c_code.setTextAlignment(Qt.AlignCenter)
            c_code.setData(Qt.UserRole, s)
            c_code.setData(Qt.UserRole + 1, is_etf)
            is_us_stock = not any(char.isdigit() for char in s["code"])
            c_code.setData(Qt.UserRole + 2, is_us_stock)
            
            display_name = s["name"]
            is_in_watchlist = False
            if is_us_stock:
                is_in_watchlist = (s["code"] in US_STOCK_MAP)
            else:
                is_in_watchlist = (s["code"] in AI_STOCK_MAP)
                
            if not is_in_watchlist:
                display_name = f"{display_name} ➕"
                
            c_name = QTableWidgetItem(display_name)
            c_name.setTextAlignment(Qt.AlignCenter)
            
            c_type = QTableWidgetItem("ETF" if is_etf else "個股")
            c_type.setTextAlignment(Qt.AlignCenter)
            
            c_price = NumericTableWidgetItem(f"{s['price']:.2f}")
            c_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_price.setData(Qt.UserRole + 99, float(s['price'] or 0.0))
            
            c_chg = NumericTableWidgetItem(f"{s['change_pct']:.2f}%")
            c_chg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_chg.setData(Qt.UserRole + 99, float(s['change_pct'] or 0.0))
            if s["change_pct"] > 0: c_chg.setForeground(QColor("#FF5B60"))
            elif s["change_pct"] < 0: c_chg.setForeground(QColor("#34D399"))
            
            c_vol = NumericTableWidgetItem(f"{s['today_vol']:,}")
            c_vol.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_vol.setData(Qt.UserRole + 99, float(s['today_vol'] or 0.0))
            
            qai_val = float(s['comp_score'] + s['accum_score'] + s['trig_score'])
            c_qai = NumericTableWidgetItem(f"{qai_val:.1f}")
            c_qai.setTextAlignment(Qt.AlignCenter)
            c_qai.setData(Qt.UserRole + 99, qai_val)
            
            # 黑馬分數著色
            dark_score = float(s.get("dark_horse_score", 0.0) or 0.0)
            dark_label = s.get("dark_horse_label", "")
            c_dark = NumericTableWidgetItem(f"{dark_score:.1f}")
            c_dark.setTextAlignment(Qt.AlignCenter)
            c_dark.setToolTip(f"{dark_label}｜黑馬分數 {dark_score:.1f}")
            c_dark.setData(Qt.UserRole + 99, dark_score)
            if dark_score >= 75:
                c_dark.setForeground(QColor("#C084FC"))
                c_dark.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif dark_score >= 65:
                c_dark.setForeground(QColor("#05D994"))
            elif dark_score >= 55:
                c_dark.setForeground(QColor("#FFB800"))
            else:
                c_dark.setForeground(QColor("#64748B"))
 
            # AI信心度著色
            win_rate = float(s.get("win_rate", 50.0) or 50.0)
            c_win = NumericTableWidgetItem(f"{win_rate:.1f}%")
            c_win.setTextAlignment(Qt.AlignCenter)
            c_win.setToolTip(f"AI 信心度：{win_rate:.1f}%")
            c_win.setData(Qt.UserRole + 99, win_rate)
            if win_rate >= 80:
                c_win.setForeground(QColor("#FF5B60"))
                c_win.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif win_rate >= 70:
                c_win.setForeground(QColor("#05D994"))
            else:
                c_win.setForeground(QColor("#64748B"))
 
            # 波段完成度著色
            completion = float(s.get("stage1_completion_pct", 0.0) or 0.0)
            completion_label = s.get("stage1_completion_label", "")
            c_completion = NumericTableWidgetItem(f"{completion:.1f}%")
            c_completion.setTextAlignment(Qt.AlignCenter)
            c_completion.setToolTip(f"{completion_label}｜第一波段完成度 {completion:.1f}%")
            c_completion.setData(Qt.UserRole + 99, completion)
            if completion >= 90:
                c_completion.setForeground(QColor("#FF5B60"))
                c_completion.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif completion >= 75:
                c_completion.setForeground(QColor("#C084FC"))
            elif completion >= 60:
                c_completion.setForeground(QColor("#05D994"))
            elif completion >= 40:
                c_completion.setForeground(QColor("#FFB800"))
            else:
                c_completion.setForeground(QColor("#64748B"))
            
            c_foreign = NumericTableWidgetItem(f"{s['foreign_consecutive']}D")
            c_foreign.setTextAlignment(Qt.AlignCenter)
            c_foreign.setData(Qt.UserRole + 99, int(s['foreign_consecutive'] or 0))
            
            second_inst = s['dealer_consecutive'] if is_etf else s['trust_consecutive']
            c_second_inst = NumericTableWidgetItem(f"{second_inst}D")
            c_second_inst.setTextAlignment(Qt.AlignCenter)
            c_second_inst.setData(Qt.UserRole + 99, int(second_inst or 0))
            
            # RS指標
            rs_val = s.get("rs_score", 50.0)
            c_rs = NumericTableWidgetItem(f"{rs_val:.1f}")
            c_rs.setTextAlignment(Qt.AlignCenter)
            c_rs.setData(Qt.UserRole + 99, float(rs_val))
            if rs_val >= 80:
                c_rs.setForeground(QColor("#FF5B60"))
                c_rs.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif rs_val >= 60:
                c_rs.setForeground(QColor("#FFB800"))
            else:
                c_rs.setForeground(QColor("#64748B"))

            # 基本面
            fund_val = s.get("fundamental_score", 50.0)
            c_fundamental = NumericTableWidgetItem(f"{fund_val:.1f}")
            c_fundamental.setTextAlignment(Qt.AlignCenter)
            c_fundamental.setData(Qt.UserRole + 99, float(fund_val))
            if fund_val >= 80:
                c_fundamental.setForeground(QColor("#FF5B60"))
                c_fundamental.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif fund_val >= 60:
                c_fundamental.setForeground(QColor("#05D994"))
            else:
                c_fundamental.setForeground(QColor("#64748B"))
            # 基本面 ToolTip (自選股)
            fund_data = GLOBAL_FUNDAMENTALS_CACHE.get(s["code"])
            if fund_data:
                tt_msg = (
                    f"【基本面數據詳情 - {s['name']}】\n"
                    f"營收年增率 (YoY): {fund_data.get('revenue_yoy', 0.0)}%\n"
                )
                if not is_us_stock:
                    tt_msg += f"最新毛利率: {fund_data.get('gross_margin', 0.0)}%\n"
                tt_msg += (
                    f"最新季度 EPS: {fund_data.get('latest_eps', 0.0)} 元\n"
                    f"EPS 年增率 (YoY): {fund_data.get('eps_yoy', 0.0)}%\n"
                    f"毛利率相較上季或去年同期提升: {'是' if fund_data.get('gross_margin_increased') else '否'}"
                )
                c_fundamental.setToolTip(tt_msg)
            
            timing_map = {"E_BREAKOUT": 5, "A_BREAKOUT": 4, "B_READY": 3, "C_PULLBACK": 2, "D_SILENT": 1}
            timing_val = timing_map.get(s.get("timing_class", "Decline"), 0)
            c_timing = NumericTableWidgetItem(s["timing_label"])
            c_timing.setTextAlignment(Qt.AlignCenter)
            c_timing.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            c_timing.setData(Qt.UserRole + 99, timing_val)
            if s["timing_class"] == "E_BREAKOUT": c_timing.setForeground(QColor("#C084FC"))
            elif s["timing_class"] == "A_BREAKOUT": c_timing.setForeground(QColor("#05D994"))
            elif s["timing_class"] == "B_READY": c_timing.setForeground(QColor("#10B981"))
            elif s["timing_class"] == "C_PULLBACK": c_timing.setForeground(QColor("#FFB800"))
            elif s["timing_class"] == "D_SILENT": c_timing.setForeground(QColor("#00A3FF"))
                
            readiness_val = float(s.get("readiness_score", 0.0) or 0.0)
            c_countdown = NumericTableWidgetItem(s["countdown"])
            c_countdown.setTextAlignment(Qt.AlignCenter)
            c_countdown.setData(Qt.UserRole + 99, readiness_val)
            
            drive_val = float(s.get("smart_drive_value", 0.0) or 0.0)
            c_drive = NumericTableWidgetItem(s["smart_drive"])
            c_drive.setTextAlignment(Qt.AlignCenter)
            c_drive.setData(Qt.UserRole + 99, drive_val)
            
            # 產業共振分數
            res_val = s.get("sector_resonance", 0.0)
            c_resonance = NumericTableWidgetItem(f"{res_val:.0f}" if res_val > 0 else "-")
            c_resonance.setTextAlignment(Qt.AlignCenter)
            c_resonance.setData(Qt.UserRole + 99, float(res_val or 0.0))
            if res_val >= 70:
                c_resonance.setForeground(QColor("#FF5B60"))
                c_resonance.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif res_val >= 50:
                c_resonance.setForeground(QColor("#FFB800"))
            else:
                c_resonance.setForeground(QColor("#64748B"))
            
            inst_text = format_trade_instruction(s["trade_instruction"])
            c_inst = QTableWidgetItem(inst_text)
            
            self.tbl_custom.setItem(row_idx, 0, c_code)
            self.tbl_custom.setItem(row_idx, 1, c_name)
            self.tbl_custom.setItem(row_idx, 2, c_type)
            self.tbl_custom.setItem(row_idx, 3, c_price)
            self.tbl_custom.setItem(row_idx, 4, c_chg)
            self.tbl_custom.setItem(row_idx, 5, c_vol)
            self.tbl_custom.setItem(row_idx, 6, c_qai)
            self.tbl_custom.setItem(row_idx, 7, c_dark)
            self.tbl_custom.setItem(row_idx, 8, c_win)
            self.tbl_custom.setItem(row_idx, 9, c_completion)
            self.tbl_custom.setItem(row_idx, 10, c_foreign)
            self.tbl_custom.setItem(row_idx, 11, c_second_inst)
            self.tbl_custom.setItem(row_idx, 12, c_rs)
            self.tbl_custom.setItem(row_idx, 13, c_fundamental)
            self.tbl_custom.setItem(row_idx, 14, c_timing)
            self.tbl_custom.setItem(row_idx, 15, c_countdown)
            self.tbl_custom.setItem(row_idx, 16, c_drive)
            self.tbl_custom.setItem(row_idx, 17, c_resonance)
            self.tbl_custom.setItem(row_idx, 18, c_inst)
            
        self.tbl_custom.resizeColumnsToContents()
        self.tbl_custom.setSortingEnabled(True)
    def filter_stocks_table(self):
        self.filter_table(self.tbl_stocks, self.cb_filter_s.currentText())

    def filter_etfs_table(self):
        self.filter_table(self.tbl_etfs, self.cb_filter_e.currentText())

    def setup_us_table_headers(self, table):
        headers = [
            "Ticker", "名稱", "最新價(USD)", "漲跌幅", "成交量",
            "QAI分數", "黑馬分數", "AI 信心度", "波段完成度",
            "量價動能",
            "量能趨勢",
            "RS指標", "基本面", "時機分組",
            "⏳發動成熟度", "🔥主力推進", "🏭共振", "戰術操作指令"
        ]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        
        tooltips = {
            "Ticker": "股票代碼 (Ticker)",
            "名稱": "公司中文/英文名稱",
            "最新價(USD)": "最新收盤價或盤中即時價",
            "漲跌幅": "今日相比昨日收盤的漲跌幅百分比",
            "成交量": "今日成交股數 (Volume)",
            "QAI分數": "QAI 綜合多因子打分：\n評估技術面收縮、籌碼面收集、量能速度等 9 大特徵因子的綜合得分（總分 100+加成）。\n用以衡量股票是否處於爆發前夕的最佳量價狀態。",
            "黑馬分數": "潛在爆發黑馬機會打分 (0-100)",
            "AI 信心度": "AI 信心度（Confidence Score）：\n系統綜合評估時機分組與 QAI 打分，二次校正後的本波段發動上漲信心期望值（%），越高代表突破發動成功率或信心越高",
            "波段完成度": "當前波段發動與完成度百分比",
            "量價動能": "近期連續量價齊漲天數 (替代外資連買指標)",
            "量能趨勢": "5日均量/20日均量比例 (替代投信連買指標)",
            "RS指標": "相對強度指標（Relative Strength Score）：\n以個股過去 60 天報酬率扣除大盤 60 天報酬率得到超額報酬，並在全市場掃描標的中進行百分位數排序（1~99分）。\n數值越接近 99 代表強度越強，越具備超額回報與黑馬潛力。",
            "基本面": "基本面綜合評分（Fundamental Score）：\n綜合評估營收年增率、毛利率方向、EPS 增長動能等指標加權計算而得的財務健康度評分（0~100分）。\n用以過濾基本面不佳、突破容易失敗的弱勢標的。",
            "時機分組": "根據成熟度與型態劃分的五級進場時機 (E/A/B/C/D)",
            "⏳發動成熟度": "進場發動成熟機率，越高代表越接近突破發動點",
            "🔥主力推進": "主力多頭推進力道強度，越高代表多頭力道越集中",
            "🏭共振": "所屬美股 AI 族群板塊內其他個股同步強勢共振度",
            "戰術操作指令": "雷達系統生成的個股具體戰術操作建議"
        }
        for idx, header in enumerate(headers):
            item = QTableWidgetItem(header)
            if header in tooltips:
                item.setToolTip(tooltips[header])
            table.setHorizontalHeaderItem(idx, item)
        
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setDefaultSectionSize(90)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        try:
            table.horizontalHeader().sortIndicatorChanged.disconnect()
        except Exception:
            pass
        table.horizontalHeader().sortIndicatorChanged.connect(
            lambda idx, order: self.update_table_sort_indicator(table, idx, order)
        )

    def filter_us_stocks_table(self):
        self.filter_table(self.tbl_us_stocks, self.cb_filter_us.currentText())

    def start_us_scan(self):
        if hasattr(self, 'us_scan_worker') and self.us_scan_worker and self.us_scan_worker.isRunning():
            QMessageBox.warning(self, "警告", "美股掃描任務正在運行中，請耐心等待。")
            return
            
        use_cache = self.cb_use_cache.isChecked()
        self.set_buttons_enabled(False)
        self.btn_run_us.setText("⏳ 正在分析...")
        self.progress_bar.setValue(0)
        
        self.us_scan_worker = USScanWorker(use_cache=use_cache)
        self.us_scan_worker.progress_signal.connect(self.update_progress_ui)
        self.us_scan_worker.finished_signal.connect(self.us_scan_finished_callback)
        self.us_scan_worker.start()

    def start_us_custom_scan(self):
        text = self.txt_us_custom_input.text().strip()
        if not text:
            QMessageBox.warning(self, "警告", "請先輸入要診斷的美股 Tickers，例如 AAPL, MSFT。")
            return
            
        tickers = [t.strip().upper() for t in text.split(',') if t.strip()]
        if hasattr(self, 'us_scan_worker') and self.us_scan_worker and self.us_scan_worker.isRunning():
            QMessageBox.warning(self, "警告", "美股掃描任務正在運行中，請耐心等待。")
            return
            
        use_cache = self.cb_use_cache.isChecked()
        self.set_buttons_enabled(False)
        self.progress_bar.setValue(0)
        
        self.us_scan_worker = USScanWorker(custom_tickers=tickers, use_cache=use_cache)
        self.us_scan_worker.progress_signal.connect(self.update_progress_ui)
        self.us_scan_worker.finished_signal.connect(self.us_scan_finished_callback)
        self.us_scan_worker.start()

    @Slot(dict)
    def us_scan_finished_callback(self, results):
        self.set_buttons_enabled(True)
        self.btn_run_us.setText("🇺🇸 美股全掃描")
        try:
            self.progress_bar.setValue(100)
            us_regime = results.get("us_regime", {})
            status_text = us_regime.get("status", "未知狀態")
            
            if "掃描錯誤" in status_text or "中斷" in status_text:
                self.lbl_progress_desc.setText("美股掃描失敗！請查看日誌。")
            else:
                self.lbl_progress_desc.setText("美股掃描完成！")
                
            us_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            results["us_scan_time"] = us_scan_time
            if self.latest_data is None:
                self.latest_data = {}
            self.latest_data["us_regime"] = us_regime
            self.latest_data["us_stocks"] = results.get("us_stocks", [])
            self.latest_data["us_scan_time"] = us_scan_time
            
            # 渲染美股大盤卡片
            if us_scan_time:
                self.lbl_dow_title.setText(f"道瓊工業 (^DJI)  [最後掃描: {us_scan_time}]")
            def update_index_ui(val_label, chg_label, data):
                price = data.get("price", 0.0)
                change_pct = data.get("change_pct", 0.0)
                change_val = data.get("change_val", 0.0)
                
                if price > 0.0:
                    val_label.setText(f"{price:,.2f}")
                    if change_pct > 0:
                        chg_label.setText(f"▲ {change_val:,.2f} (+{change_pct:.2f}%)")
                        chg_label.setStyleSheet("font-size: 11px; color: #FF5B60; font-weight: bold;")
                        val_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FF5B60;")
                    elif change_pct < 0:
                        chg_label.setText(f"▼ {abs(change_val):,.2f} ({change_pct:.2f}%)")
                        chg_label.setStyleSheet("font-size: 11px; color: #34D399; font-weight: bold;")
                        val_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #34D399;")
                    else:
                        chg_label.setText(f"  0.00 (0.00%)")
                        chg_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
                        val_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
                else:
                    val_label.setText("資料未載入")
                    val_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #64748B;")
                    chg_label.setText("")
                    
            sp = us_regime.get("sp500", {})
            dow = us_regime.get("dow", {})
            nas = us_regime.get("nasdaq", {})
            sox = us_regime.get("sox", {})
            
            update_index_ui(self.lbl_dow_val, self.lbl_dow_chg, dow)
            update_index_ui(self.lbl_nas_val, self.lbl_nas_chg, nas)
            update_index_ui(self.lbl_sp_val, self.lbl_sp_chg, sp)
            update_index_ui(self.lbl_sox_val, self.lbl_sox_chg, sox)
                
            # 填入表格與戰術板
            self.render_us_table(self.latest_data.get("us_stocks", []))
            self.render_advice_board(self.latest_data)
            
            # 將最後一次掃描結果持久化存檔
            save_json_cache(LAST_SCAN_CACHE_FILE, self.latest_data)
        except Exception as e:
            logging.error(f"處理美股掃描結果回調失敗: {e}", exc_info=True)

    def render_us_table(self, data_list):
        self.tbl_us_stocks.setSortingEnabled(False)
        self.tbl_us_stocks.setRowCount(0)
        for s in data_list:
            row_idx = self.tbl_us_stocks.rowCount()
            self.tbl_us_stocks.insertRow(row_idx)
            
            c_code = QTableWidgetItem(s["code"])
            c_code.setTextAlignment(Qt.AlignCenter)
            c_code.setData(Qt.UserRole, s)
            c_code.setData(Qt.UserRole + 1, False)
            c_code.setData(Qt.UserRole + 2, True)
            
            c_name = QTableWidgetItem(s["name"])
            c_name.setTextAlignment(Qt.AlignCenter)
            c_name.setToolTip(s["theme"])
            
            c_price = NumericTableWidgetItem(f"{s['price']:.2f}")
            c_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_price.setData(Qt.UserRole + 99, float(s['price'] or 0.0))
            
            c_chg = NumericTableWidgetItem(f"{s['change_pct']:.2f}%")
            c_chg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_chg.setData(Qt.UserRole + 99, float(s['change_pct'] or 0.0))
            if s["change_pct"] > 0: c_chg.setForeground(QColor("#FF5B60"))
            elif s["change_pct"] < 0: c_chg.setForeground(QColor("#34D399"))
            
            c_vol = NumericTableWidgetItem(f"{s['today_vol']:,}")
            c_vol.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c_vol.setData(Qt.UserRole + 99, float(s['today_vol'] or 0.0))
            
            qai_val = float(s['comp_score'] + s['accum_score'] + s['trig_score'])
            c_qai = NumericTableWidgetItem(f"{qai_val:.1f}")
            c_qai.setTextAlignment(Qt.AlignCenter)
            c_qai.setData(Qt.UserRole + 99, qai_val)
            
            # 黑馬分數著色
            dark_score = float(s.get("dark_horse_score", 0.0) or 0.0)
            dark_label = s.get("dark_horse_label", "")
            c_dark = NumericTableWidgetItem(f"{dark_score:.1f}")
            c_dark.setTextAlignment(Qt.AlignCenter)
            c_dark.setToolTip(f"{dark_label}｜黑馬分數 {dark_score:.1f}")
            c_dark.setData(Qt.UserRole + 99, dark_score)
            if dark_score >= 75:
                c_dark.setForeground(QColor("#C084FC"))
                c_dark.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif dark_score >= 65:
                c_dark.setForeground(QColor("#05D994"))
            elif dark_score >= 55:
                c_dark.setForeground(QColor("#FFB800"))
            else:
                c_dark.setForeground(QColor("#64748B"))
 
            # AI信心度著色
            win_rate = float(s.get("win_rate", 50.0) or 50.0)
            c_win = NumericTableWidgetItem(f"{win_rate:.1f}%")
            c_win.setTextAlignment(Qt.AlignCenter)
            c_win.setToolTip(f"AI 信心度：{win_rate:.1f}%")
            c_win.setData(Qt.UserRole + 99, win_rate)
            if win_rate >= 80:
                c_win.setForeground(QColor("#FF5B60"))
                c_win.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif win_rate >= 70:
                c_win.setForeground(QColor("#05D994"))
            else:
                c_win.setForeground(QColor("#64748B"))
 
            # 波段完成度著色
            completion = float(s.get("stage1_completion_pct", 0.0) or 0.0)
            completion_label = s.get("stage1_completion_label", "")
            c_wave = NumericTableWidgetItem(f"{completion:.1f}%")
            c_wave.setTextAlignment(Qt.AlignCenter)
            c_wave.setToolTip(f"{completion_label}｜第一波段完成度 {completion:.1f}%")
            c_wave.setData(Qt.UserRole + 99, completion)
            if completion >= 90:
                c_wave.setForeground(QColor("#FF5B60"))
                c_wave.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif completion >= 75:
                c_wave.setForeground(QColor("#C084FC"))
            elif completion >= 60:
                c_wave.setForeground(QColor("#05D994"))
            elif completion >= 40:
                c_wave.setForeground(QColor("#FFB800"))
            else:
                c_wave.setForeground(QColor("#64748B"))
            
            c_foreign = NumericTableWidgetItem(f"{s['foreign_consecutive']}D")
            c_foreign.setTextAlignment(Qt.AlignCenter)
            c_foreign.setData(Qt.UserRole + 99, int(s['foreign_consecutive'] or 0))
            
            c_vol_ratio = NumericTableWidgetItem(f"{s.get('vol_trend_ratio', 1.0):.2f}x")
            c_vol_ratio.setTextAlignment(Qt.AlignCenter)
            c_vol_ratio.setData(Qt.UserRole + 99, float(s.get('vol_trend_ratio', 1.0) or 0.0))
            
            # RS指標
            rs_val = s.get("rs_score", 50.0)
            c_rs = NumericTableWidgetItem(f"{rs_val:.1f}")
            c_rs.setTextAlignment(Qt.AlignCenter)
            c_rs.setData(Qt.UserRole + 99, float(rs_val))
            if rs_val >= 80:
                c_rs.setForeground(QColor("#FF5B60"))
                c_rs.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif rs_val >= 60:
                c_rs.setForeground(QColor("#FFB800"))
            else:
                c_rs.setForeground(QColor("#64748B"))

            # 基本面
            fund_val = s.get("fundamental_score", 50.0)
            c_fundamental = NumericTableWidgetItem(f"{fund_val:.1f}")
            c_fundamental.setTextAlignment(Qt.AlignCenter)
            c_fundamental.setData(Qt.UserRole + 99, float(fund_val))
            if fund_val >= 80:
                c_fundamental.setForeground(QColor("#FF5B60"))
                c_fundamental.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif fund_val >= 60:
                c_fundamental.setForeground(QColor("#05D994"))
            else:
                c_fundamental.setForeground(QColor("#64748B"))
            # 基本面 ToolTip (美股)
            fund_data = GLOBAL_FUNDAMENTALS_CACHE.get(s["code"])
            if fund_data:
                c_fundamental.setToolTip(
                    f"【基本面數據詳情 - {s['name']}】\n"
                    f"營收年增率 (YoY): {fund_data.get('revenue_yoy', 0.0)}%\n"
                    f"最新季度 EPS: {fund_data.get('latest_eps', 0.0)} 元\n"
                    f"EPS 年增率 (YoY): {fund_data.get('eps_yoy', 0.0)}%\n"
                    f"毛利率相較上季或去年同期提升: {'是' if fund_data.get('gross_margin_increased') else '否'}"
                )
            else:
                c_fundamental.setToolTip("暫無該股之詳細基本面數據 (點擊更新後可抓取)")
            
            timing_map = {"E_BREAKOUT": 5, "A_BREAKOUT": 4, "B_READY": 3, "C_PULLBACK": 2, "D_SILENT": 1}
            timing_val = timing_map.get(s.get("timing_class", "Decline"), 0)
            c_timing = NumericTableWidgetItem(s["timing_label"])
            c_timing.setTextAlignment(Qt.AlignCenter)
            c_timing.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            c_timing.setData(Qt.UserRole + 99, timing_val)
            if s["timing_class"] == "E_BREAKOUT":
                c_timing.setForeground(QColor("#C084FC"))
            elif s["timing_class"] == "A_BREAKOUT":
                c_timing.setForeground(QColor("#05D994"))
            elif s["timing_class"] == "B_READY":
                c_timing.setForeground(QColor("#10B981"))
            elif s["timing_class"] == "C_PULLBACK":
                c_timing.setForeground(QColor("#FFB800"))
            elif s["timing_class"] == "D_SILENT":
                c_timing.setForeground(QColor("#00A3FF"))
                
            readiness_val = float(s.get("readiness_score", 0.0) or 0.0)
            c_countdown = NumericTableWidgetItem(s["countdown"])
            c_countdown.setTextAlignment(Qt.AlignCenter)
            c_countdown.setData(Qt.UserRole + 99, readiness_val)
            
            drive_val = float(s.get("smart_drive_value", 0.0) or 0.0)
            c_drive = NumericTableWidgetItem(s["smart_drive"])
            c_drive.setTextAlignment(Qt.AlignCenter)
            c_drive.setData(Qt.UserRole + 99, drive_val)
            
            res_val = s.get("sector_resonance", 0.0)
            c_resonance = NumericTableWidgetItem(f"{res_val:.0f}" if res_val > 0 else "-")
            c_resonance.setTextAlignment(Qt.AlignCenter)
            c_resonance.setData(Qt.UserRole + 99, float(res_val or 0.0))
            if res_val >= 70:
                c_resonance.setForeground(QColor("#FF5B60"))
                c_resonance.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            elif res_val >= 50:
                c_resonance.setForeground(QColor("#FFB800"))
            else:
                c_resonance.setForeground(QColor("#64748B"))
            
            inst_text = format_trade_instruction(s["trade_instruction"])
            c_inst = QTableWidgetItem(inst_text)
            c_inst.setToolTip(inst_text)
            
            table = self.tbl_us_stocks
            table.setItem(row_idx, 0, c_code)
            table.setItem(row_idx, 1, c_name)
            table.setItem(row_idx, 2, c_price)
            table.setItem(row_idx, 3, c_chg)
            table.setItem(row_idx, 4, c_vol)
            table.setItem(row_idx, 5, c_qai)
            table.setItem(row_idx, 6, c_dark)
            table.setItem(row_idx, 7, c_win)
            table.setItem(row_idx, 8, c_wave)
            table.setItem(row_idx, 9, c_foreign)
            table.setItem(row_idx, 10, c_vol_ratio)
            table.setItem(row_idx, 11, c_rs)
            table.setItem(row_idx, 12, c_fundamental)
            table.setItem(row_idx, 13, c_timing)
            table.setItem(row_idx, 14, c_countdown)
            table.setItem(row_idx, 15, c_drive)
            table.setItem(row_idx, 16, c_resonance)
            table.setItem(row_idx, 17, c_inst)
            
        self.tbl_us_stocks.resizeColumnsToContents()
        self.tbl_us_stocks.setSortingEnabled(True)
    def show_us_stocks_context_menu(self, pos):
        item = self.tbl_us_stocks.itemAt(pos)
        if not item: return
        row = item.row()
        ticker = self.tbl_us_stocks.item(row, 0).text().strip()
        name = self.tbl_us_stocks.item(row, 1).text().strip()
        
        # 美股最新價在第 2 欄
        price_item = self.tbl_us_stocks.item(row, 2)
        table_price = None
        if price_item:
            try:
                table_price = float(price_item.text().replace(',', '').strip())
            except ValueError:
                pass
                
        # 美股成交量在第 4 欄
        vol_item = self.tbl_us_stocks.item(row, 4)
        table_vol = None
        if vol_item:
            try:
                table_vol = float(vol_item.text().replace(',', '').strip())
            except ValueError:
                pass
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
            }
            QMenu::item {
                padding: 8px 24px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
        """)
        
        action_teaching = menu.addAction(f"💡 新手買賣心法教學 ({ticker} {name})")
        action_intraday = menu.addAction(f"📊 日內即時分析 ({ticker} {name})")
        action_diagnose = menu.addAction(f"🔍 Serenity 深度卡點診斷 ({ticker} {name})")
        action_web = menu.addAction(f"🌐 查詢個股新聞與簡介 ({ticker} {name})")
        action = menu.exec(self.tbl_us_stocks.viewport().mapToGlobal(pos))
        if action == action_intraday:
            self.trigger_intraday_analysis(ticker, name, is_us=True, table_price=table_price, table_vol=table_vol)
        elif action == action_diagnose:
            self.trigger_serenity_diagnose(ticker)
        elif action == action_web:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            url = f"https://finance.yahoo.com/quote/{ticker}"
            QDesktopServices.openUrl(QUrl(url))
        elif action == action_teaching:
            code_item = self.tbl_us_stocks.item(row, 0)
            s = code_item.data(Qt.UserRole)
            if s is None and self.latest_data:
                # 備援尋找
                for x in self.latest_data.get("us_stocks", []):
                    if x["code"] == ticker: s = x; break
            if s is not None:
                self.popup_teaching_dialog(s, False, True)

    def trigger_serenity_diagnose_us_stock(self, ticker, name):
        self.trigger_serenity_diagnose(ticker)

    def filter_table(self, table, filter_text):
        is_us_table = (table == self.tbl_us_stocks)
        if table == self.tbl_custom:
            timing_col_idx = 14
        else:
            timing_col_idx = 13
        
        for row in range(table.rowCount()):
            table.setRowHidden(row, False)
            if filter_text == "全部標的": continue
            
            code_item = table.item(row, 0)
            if not code_item: continue
            code = code_item.text().strip()
            
            # 四大特徵動態過濾
            is_pattern_filter = False
            pattern_key = None
            if "均線粘合" in filter_text:
                is_pattern_filter = True
                pattern_key = "pattern1_ma_align"
            elif "地量" in filter_text:
                is_pattern_filter = True
                pattern_key = "pattern2_valley_vol"
            elif "挖坑" in filter_text:
                is_pattern_filter = True
                pattern_key = "pattern3_golden_pit"
            elif "壓力" in filter_text or "試盤" in filter_text:
                is_pattern_filter = True
                pattern_key = "pattern4_test_pressure"
                
            if is_pattern_filter:
                found = False
                if self.latest_data:
                    if is_us_table:
                        all_sec = self.latest_data.get("us_stocks", [])
                    else:
                        all_sec = self.latest_data.get("stocks", []) + self.latest_data.get("etfs", [])
                        
                    sec_obj = next((x for x in all_sec if x["code"] == code), None)
                    if sec_obj and sec_obj.get(pattern_key):
                        found = True
                if not found:
                    table.setRowHidden(row, True)
            else:
                # 傳統時機分組過濾
                item = table.item(row, timing_col_idx)
                if item:
                    text_val = item.text().strip()
                    matched = False
                    for key in ["E級", "A級", "B級", "C級", "D級"]:
                        if key in filter_text and key in text_val:
                            matched = True
                            break
                    if not matched and ("整理觀望" in filter_text or "觀望" in filter_text) and ("整理觀望" in text_val or "Decline" in text_val or "觀望" in text_val):
                        matched = True
                        
                    if not matched:
                        table.setRowHidden(row, True)

    def render_advice_board(self, results):
        regime = results.get("regime", {"status": "未掃描", "index_p": 0.0, "change_pct": 0.0, "multiplier": 1.0})
        stocks = results.get("stocks", [])
        etfs = results.get("etfs", [])
        
        # 構造系統總結報告
        rep = []
        rep.append("=========================================================================")
        rep.append("  🏆 台股個股與 ETF 時序概率交易雷達系統 總體戰術指引板")
        rep.append("=========================================================================")
        rep.append(f"  大盤狀態: {regime['status']}")
        rep.append(f"  目前點位: {regime['index_p']:.2f} 點 | 今日大盤即時漲跌: {round(regime['change_pct'], 2)}%")
        rep.append(f"  系統建議操作係數: {regime['multiplier']} (風控過濾器)")
        rep.append("-------------------------------------------------------------------------")
        
        # 發動窗統計
        all_sec = stocks + etfs
        group_e = [s for s in all_sec if s["timing_class"] == "E_BREAKOUT"]
        group_a = [s for s in all_sec if s["timing_class"] == "A_BREAKOUT"]
        group_b = [s for s in all_sec if s["timing_class"] == "B_READY"]
        group_c = [s for s in all_sec if s["timing_class"] == "C_PULLBACK"]
        group_d = [s for s in all_sec if s["timing_class"] == "D_SILENT"]
        
        rep.append(f"  🔥 當前掃描標的統計：")
        rep.append(f"    - [🚀 E級 動能爆發]： {len(group_e)} 檔")
        rep.append(f"    - [⚡ A級 突破確認]： {len(group_a)} 檔")
        rep.append(f"    - [🟢 B級 整理完成]： {len(group_b)} 檔")
        rep.append(f"    - [🟡 C級 多頭回檔]： {len(group_c)} 檔")
        rep.append(f"    - [🧊 D級 潛伏觀察]： {len(group_d)} 檔")
        rep.append("-------------------------------------------------------------------------")
        
        # 發動窗重點提示
        rep.append("🚀 【動能爆發加速窗 - 強勢追擊標的】")
        if not group_e:
            rep.append("   [INFO] 當前無動能爆發標的。")
        else:
            for s in group_e[:8]:
                inst = format_trade_instruction(s["trade_instruction"])
                qai = s['comp_score'] + s['accum_score'] + s['trig_score']
                win_rate = float(s.get("win_rate", 50.0) or 50.0)
                dark = float(s.get("dark_horse_score", 0.0) or 0.0)
                comp = float(s.get("stage1_completion_pct", 0.0) or 0.0)
                rep.append(f"  ■ {s['code']} {s['name']} ({s['theme']})")
                rep.append(f"    📊 量化特徵：AI 信心度: {win_rate:.1f}% | QAI分數: {qai:.1f} | 黑馬分數: {dark:.1f} | 波段完成度: {comp:.1f}%")
                rep.append(f"    🚀 時機狀態：狀態: {s['timing_label']} | 🔥主力推進: {s['smart_drive']}")
                rep.append(f"    🧾 交易指令: {inst}")
                rep.append("")
                
        rep.append("-------------------------------------------------------------------------")
        rep.append("⚡ 【突破確認爆發窗 - 重點監控標的】")
        if not group_a:
            rep.append("   [INFO] 當前無突破確認標的。")
        else:
            for s in group_a[:8]:
                inst = format_trade_instruction(s["trade_instruction"])
                qai = s['comp_score'] + s['accum_score'] + s['trig_score']
                win_rate = float(s.get("win_rate", 50.0) or 50.0)
                dark = float(s.get("dark_horse_score", 0.0) or 0.0)
                comp = float(s.get("stage1_completion_pct", 0.0) or 0.0)
                rep.append(f"  ■ {s['code']} {s['name']} ({s['theme']})")
                rep.append(f"    📊 量化特徵：AI 信心度: {win_rate:.1f}% | QAI分數: {qai:.1f} | 黑馬分數: {dark:.1f} | 波段完成度: {comp:.1f}%")
                rep.append(f"    🚀 時機狀態：狀態: {s['timing_label']} | ⏳發動成熟度: {s['countdown']} | 🔥主力推進: {s['smart_drive']}")
                rep.append(f"    🧾 交易指令: {inst}")
                rep.append("")
                
        rep.append("-------------------------------------------------------------------------")
        rep.append("🟢 【整理完成起攻窗 - 潛在攻擊標的】")
        if not group_b:
            rep.append("   [INFO] 當前無整理完成標的。")
        else:
            for s in group_b[:8]:
                inst = format_trade_instruction(s["trade_instruction"])
                qai = s['comp_score'] + s['accum_score'] + s['trig_score']
                win_rate = float(s.get("win_rate", 50.0) or 50.0)
                dark = float(s.get("dark_horse_score", 0.0) or 0.0)
                comp = float(s.get("stage1_completion_pct", 0.0) or 0.0)
                rep.append(f"  ■ {s['code']} {s['name']} ({s['theme']})")
                rep.append(f"    📊 量化特徵：AI 信心度: {win_rate:.1f}% | QAI分數: {qai:.1f} | 黑馬分數: {dark:.1f} | 波段完成度: {comp:.1f}%")
                rep.append(f"    🚀 時機狀態：狀態: {s['timing_label']} | ⏳發動成熟度: {s['countdown']} | 🔥主力推進: {s['smart_drive']}")
                rep.append(f"    🧾 交易指令: {inst}")
                rep.append("")
                
        rep.append("-------------------------------------------------------------------------")
        
        # ═══ 📈 盤前拉升前四大核心特徵篩選 (Infographic Pattern Radar) ═══
        rep.append("=========================================================================")
        rep.append("  📈 盤前拉升前四大核心特徵篩選 (Infographic Pattern Radar)")
        rep.append("=========================================================================")
        
        # 1. 均線粘合與向上發散 (只對 stocks 個股進行篩選，因為 ETF 不適用)
        pattern1_list = [s for s in stocks if s.get("pattern1_ma_align", False)]
        rep.append("1️⃣ 【均線粘合與向上發散】— 🎯 籌碼成本合一，一箭穿心發動")
        rep.append("   特徵: 5D/20D/60D 糾結(≤5%) + 放量突破均線(量比>1.1) | 戰術: 多頭排列發散，帶量突破即追")
        rep.append("-------------------------------------------------------------------------")
        if not pattern1_list:
            rep.append("   [INFO] 當前無符合均線糾結突破特徵的個股。")
        else:
            for i, s in enumerate(pattern1_list):
                inst = format_trade_instruction(s.get('trade_instruction', {}))
                rep.append(f"  {i+1}. 📈 {s['code']} {s['name']} | 收盤: {s['price']} | 均線糾結度: {round(s.get('ma_spread', 0)*100, 2)}% | 量比: {round(s['vol_ratio'], 2)}")
                rep.append(f"     🧾 交易指令: {inst}")
        rep.append("")
        
        # 2. 縮量洗盤後的地量出現
        pattern2_list = [s for s in stocks if s.get("pattern2_valley_vol", False)]
        rep.append("2️⃣ 【縮量洗盤後『地量』出現】— 💎 賣壓徹底枯竭，放量啟動在即")
        rep.append("   特徵: 過去15天內有極端地量(≤均量60%) + 今日陽線回溫(量比>0.8) | 戰術: 地量見地價，首根放量紅K進場")
        rep.append("-------------------------------------------------------------------------")
        if not pattern2_list:
            rep.append("   [INFO] 當前無符合地量洗盤後回溫特徵的個股。")
        else:
            for i, s in enumerate(pattern2_list):
                inst = format_trade_instruction(s.get('trade_instruction', {}))
                rep.append(f"  {i+1}. 💎 {s['code']} {s['name']} | 收盤: {s['price']} | 漲跌: {round(s['change_pct'], 2)}% | 量比: {round(s['vol_ratio'], 2)}")
                rep.append(f"     🧾 交易指令: {inst}")
        rep.append("")
        
        # 3. 挖坑動作
        pattern3_list = [s for s in stocks if s.get("pattern3_golden_pit", False)]
        rep.append("3️⃣ 【『挖坑』動作 (最後洗盤)】— 坑爹誘空洗盤，快速收復失地")
        rep.append("   特徵: 8天內跌破平台/20MA(>3.5%) + 快速拉回20MA與5MA之上 | 戰術: 黃金坑誘空完成，站回平台即是買點")
        rep.append("-------------------------------------------------------------------------")
        if not pattern3_list:
            rep.append("   [INFO] 當前無符合黃金坑洗盤特徵的個股。")
        else:
            for i, s in enumerate(pattern3_list):
                inst = format_trade_instruction(s.get('trade_instruction', {}))
                rep.append(f"  {i+1}. 🕳️ {s['code']} {s['name']} | 收盤: {s['price']} | 漲跌: {round(s['change_pct'], 2)}% | 5MA: {s['ma5']} | 20MA: {s['ma20']}")
                rep.append(f"     🧾 交易指令: {inst}")
        rep.append("")
        
        # 4. 關鍵壓力位試盤信號
        pattern4_list = [s for s in stocks if s.get("pattern4_test_pressure", False)]
        rep.append("4️⃣ 【壓力位『試盤』信號】— 仙人指路投石問路，量縮蓄勢待發")
        rep.append("   特徵: 上影線≥1.5%試探壓力區 + 守穩低點 + 回檔量縮(量比<0.95) | 戰術: 仙人指路測試拋壓，量縮整理有撐伺機切入")
        rep.append("-------------------------------------------------------------------------")
        if not pattern4_list:
            rep.append("   [INFO] 當前無符合壓力位試盤特徵的個股。")
        else:
            for i, s in enumerate(pattern4_list):
                inst = format_trade_instruction(s.get('trade_instruction', {}))
                rep.append(f"  {i+1}. 🏹 {s['code']} {s['name']} | 收盤: {s['price']} | 突破距離: {round(s.get('breakout_pct', 0), 2)}% | 上影線: {round(s.get('upper_shadow', 0), 2)}% | 量比: {round(s['vol_ratio'], 2)}")
                rep.append(f"     🧾 交易指令: {inst}")
        rep.append("")
        rep.append("=========================================================================")
        
        # 追加美股 AI 半導體雷達 總體戰術指引
        us_regime = results.get("us_regime")
        us_stocks = results.get("us_stocks")
        if us_regime and us_stocks:
            rep.append("")
            rep.append("=========================================================================")
            rep.append("  🇺🇸 美股 AI 半導體雷達 總體戰術指引")
            rep.append("=========================================================================")
            rep.append(f"  美股大盤狀態: {us_regime['status']}")
            sp = us_regime.get("sp500", {})
            dow = us_regime.get("dow", {})
            nas = us_regime.get("nasdaq", {})
            sox = us_regime.get("sox", {})
            rep.append(f"  道瓊: {dow.get('price', 0.0):.2f} ({round(dow.get('change_pct', 0.0), 2)}%) | 納指: {nas.get('price', 0.0):.2f} ({round(nas.get('change_pct', 0.0), 2)}%) | S&P 500: {sp.get('price', 0.0):.2f} ({round(sp.get('change_pct', 0.0), 2)}%) | 費指: {sox.get('price', 0.0):.2f} ({round(sox.get('change_pct', 0.0), 2)}%)")
            rep.append(f"  美股風控操作係數: {us_regime['multiplier']}")
            rep.append("-------------------------------------------------------------------------")
            
            us_group_e = [s for s in us_stocks if s["timing_class"] == "E_BREAKOUT"]
            us_group_a = [s for s in us_stocks if s["timing_class"] == "A_BREAKOUT"]
            us_group_b = [s for s in us_stocks if s["timing_class"] == "B_READY"]
            us_group_c = [s for s in us_stocks if s["timing_class"] == "C_PULLBACK"]
            us_group_d = [s for s in us_stocks if s["timing_class"] == "D_SILENT"]
            
            rep.append(f"  🔥 美股當前掃描標的統計：")
            rep.append(f"    - [🚀 E級 動能爆發]： {len(us_group_e)} 檔")
            rep.append(f"    - [⚡ A級 突破確認]： {len(us_group_a)} 檔")
            rep.append(f"    - [🟢 B級 整理完成]： {len(us_group_b)} 檔")
            rep.append(f"    - [🟡 C級 多頭回檔]： {len(us_group_c)} 檔")
            rep.append(f"    - [🧊 D級 潛伏觀察]： {len(us_group_d)} 檔")
            rep.append("-------------------------------------------------------------------------")
            
            rep.append("🇺🇸 【美股動能與突破重點關注標的】")
            focus_list = us_group_e + us_group_a + us_group_b
            if not focus_list:
                rep.append("   [INFO] 當前無重點美股關注標的。")
            else:
                for s in focus_list[:12]:
                    inst = format_trade_instruction(s["trade_instruction"])
                    qai = s['comp_score'] + s['accum_score'] + s['trig_score']
                    win_rate = float(s.get("win_rate", 50.0) or 50.0)
                    dark = float(s.get("dark_horse_score", 0.0) or 0.0)
                    comp = float(s.get("stage1_completion_pct", 0.0) or 0.0)
                    rep.append(f"  ■ {s['code']} {s['name']} ({s['theme']})")
                    rep.append(f"    📊 量化特徵：AI 信心度: {win_rate:.1f}% | QAI分數: {qai:.1f} | 黑馬分數: {dark:.1f} | 波段完成度: {comp:.1f}%")
                    rep.append(f"    🚀 時機狀態：狀態: {s['timing_label']} | 🔋量價動能: {s['foreign_consecutive']}D | 📈量能趨勢: {round(s.get('vol_trend_ratio', 1.0), 2)}")
                    rep.append(f"    🧾 交易指令: {inst}")
                    rep.append("")
            rep.append("=========================================================================")

        self.txt_advice_board.setText("\n".join(rep))
        
        # 每次重新渲染戰術板時，同步重新渲染新手懶人看板
        self.render_lazier_table()

    def setup_lazier_table_headers(self, table):
        headers = [
            "代碼", "名稱", "市場類型", "最新價", "漲跌幅", "訊號狀態", "具體操作指引", "操作理由與心法"
        ]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        
        tooltips = {
            "代碼": "股票/ETF代碼",
            "名稱": "公司或ETF中文/英文名稱",
            "市場類型": "台股、美股或台股ETF",
            "最新價": "最新收盤價或即時價",
            "漲跌幅": "今日相比昨日收盤的漲跌幅百分比",
            "訊號狀態": "買進、賣出/避險或是觀察等訊號標籤",
            "具體操作指引": "雷達系統生成的個股具體買賣價位與股數指引",
            "操作理由與心法": "為什麼雷達生成該指令的白話文解釋與交易心法"
        }
        for idx, header in enumerate(headers):
            item = QTableWidgetItem(header)
            if header in tooltips:
                item.setToolTip(tooltips[header])
            table.setHorizontalHeaderItem(idx, item)
        
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setDefaultSectionSize(100)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        try:
            table.horizontalHeader().sortIndicatorChanged.disconnect()
        except Exception:
            pass
        table.horizontalHeader().sortIndicatorChanged.connect(
            lambda idx, order: self.update_table_sort_indicator(table, idx, order)
        )

    def render_lazier_table(self):
        self.tbl_lazier.setSortingEnabled(False)
        self.tbl_lazier.setRowCount(0)
        if not self.latest_data:
            return
            
        all_items = []
        for s in self.latest_data.get("stocks", []):
            all_items.append((s, "台股個股", False, False))
        for s in self.latest_data.get("etfs", []):
            all_items.append((s, "台股ETF", True, False))
        for s in self.latest_data.get("us_stocks", []):
            all_items.append((s, "美股", False, True))
            
        for s, market_type, is_etf, is_us in all_items:
            inst_dict = s.get("trade_instruction", {})
            action = inst_dict.get("action", "WATCH")
            action_label = inst_dict.get("action_label", "整理觀望")
            reason = inst_dict.get("reason", "整理觀望中")
            
            status_text = ""
            status_color = "#94A3B8"
            
            if action == "BUY_STRONG":
                status_text = "🔥 買進強烈"
                status_color = "#C084FC"
            elif action in ["BUY_LIMIT", "BUY_STOP_LIMIT"]:
                status_text = "🟢 限價買進" if action == "BUY_LIMIT" else "🟢 突破限價買進"
                status_color = "#10B981"
            elif action == "SELL":
                status_text = "🔴 出場/避險"
                status_color = "#EF4444"
            elif action == "AVOID":
                status_text = "⚠️ 假突破避開"
                status_color = "#F59E0B"
            else:
                timing = s.get("timing_class", "Decline")
                if timing == "D_SILENT":
                    status_text = "⏳ 潛伏觀察"
                    status_color = "#00A3FF"
                else:
                    status_text = "💤 整理觀望"
                    status_color = "#64748B"
            
            row_idx = self.tbl_lazier.rowCount()
            self.tbl_lazier.insertRow(row_idx)
            
            c_code = QTableWidgetItem(s["code"])
            c_code.setTextAlignment(Qt.AlignCenter)
            c_code.setData(Qt.UserRole, s)
            c_code.setData(Qt.UserRole + 1, is_etf)
            c_code.setData(Qt.UserRole + 2, is_us)
            
            c_name = QTableWidgetItem(s["name"])
            c_name.setTextAlignment(Qt.AlignCenter)
            c_name.setToolTip(s["theme"])
            
            c_mtype = QTableWidgetItem(market_type)
            c_mtype.setTextAlignment(Qt.AlignCenter)
            
            c_price = NumericTableWidgetItem(f"{s['price']:.2f}")
            c_price.setData(Qt.UserRole + 99, float(s['price'] or 0.0))
            c_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            c_chg = NumericTableWidgetItem(f"{s['change_pct']:.2f}%")
            c_chg.setData(Qt.UserRole + 99, float(s['change_pct'] or 0.0))
            c_chg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if s["change_pct"] > 0:
                c_chg.setForeground(QColor("#FF5B60"))
            elif s["change_pct"] < 0:
                c_chg.setForeground(QColor("#34D399"))
                
            c_status = QTableWidgetItem(status_text)
            c_status.setTextAlignment(Qt.AlignCenter)
            c_status.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            c_status.setForeground(QColor(status_color))
            
            inst_display = format_trade_instruction(s["trade_instruction"])
            c_inst = QTableWidgetItem(inst_display)
            c_inst.setToolTip(inst_display)
            
            c_reason = QTableWidgetItem(reason)
            c_reason.setToolTip(reason)
            
            self.tbl_lazier.setItem(row_idx, 0, c_code)
            self.tbl_lazier.setItem(row_idx, 1, c_name)
            self.tbl_lazier.setItem(row_idx, 2, c_mtype)
            self.tbl_lazier.setItem(row_idx, 3, c_price)
            self.tbl_lazier.setItem(row_idx, 4, c_chg)
            self.tbl_lazier.setItem(row_idx, 5, c_status)
            self.tbl_lazier.setItem(row_idx, 6, c_inst)
            self.tbl_lazier.setItem(row_idx, 7, c_reason)
            
        self.tbl_lazier.resizeColumnsToContents()
        self.tbl_lazier.setSortingEnabled(True)
        self.filter_lazier_table()

    def filter_lazier_table(self):
        filter_text = self.cb_filter_lz.currentText()
        for row in range(self.tbl_lazier.rowCount()):
            self.tbl_lazier.setRowHidden(row, False)
            if filter_text == "全部訊號":
                continue
            
            status_item = self.tbl_lazier.item(row, 5)
            if not status_item:
                continue
            status_str = status_item.text().strip()
            
            if filter_text == "🔥 買進訊號":
                if "買進" not in status_str:
                    self.tbl_lazier.setRowHidden(row, True)
            elif filter_text == "🔴 避險/減碼訊號":
                if "出場" not in status_str and "避開" not in status_str:
                    self.tbl_lazier.setRowHidden(row, True)
            elif filter_text == "⏳ 觀察/潛伏":
                if "觀察" not in status_str and "潛伏" not in status_str:
                    self.tbl_lazier.setRowHidden(row, True)

    def show_teaching_dialog_from_item(self, item):
        row = item.row()
        table = item.tableWidget()
        code_item = table.item(row, 0)
        if not code_item:
            return
            
        s = code_item.data(Qt.UserRole)
        is_etf = False
        is_us = False
        
        if s is not None:
            is_etf = code_item.data(Qt.UserRole + 1) or False
            is_us = code_item.data(Qt.UserRole + 2) or False
        else:
            code = code_item.text().strip()
            if self.latest_data:
                for x in self.latest_data.get("stocks", []):
                    if x["code"] == code:
                        s = x
                        break
                if not s:
                    for x in self.latest_data.get("etfs", []):
                        if x["code"] == code:
                            s = x
                            is_etf = True
                            break
                if not s:
                    for x in self.latest_data.get("us_stocks", []):
                        if x["code"] == code:
                            s = x
                            is_us = True
                            break
                            
        if s is None:
            return
            
        self.popup_teaching_dialog(s, is_etf, is_us)

    def popup_teaching_dialog(self, s, is_etf, is_us):
        dialog = TradingTeachingDialog(s, is_etf=is_etf, is_us=is_us, parent=self)
        dialog.exec()

    def show_lazier_context_menu(self, pos):
        self.show_context_menu(self.tbl_lazier, pos)

# ----------------- 日誌攔截組件 -----------------
from PySide6.QtCore import QObject

class LogSignaler(QObject):
    log_written = Signal(str)

class QTextEditLogHandler(logging.Handler):
    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit
        self.signaler = LogSignaler()
        self.signaler.log_written.connect(self._safe_append)

    def _safe_append(self, msg):
        self.text_edit.append(msg)
        self.text_edit.moveCursor(QTextCursor.End)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.signaler.log_written.emit(msg)
        except Exception:
            self.handleError(record)

# ----------------- 歷史日期輔助 -----------------
def get_last_trading_date():
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    # 下午 1 點 30 分之後即可判定今日已收盤
    if now.hour < 13 or (now.hour == 13 and now.minute < 30):
        target = now - timedelta(days=1)
    else:
        target = now
    while target.weekday() >= 5: target -= timedelta(days=1)
    return target.strftime('%Y%m%d')

def get_previous_trading_date(date_str):
    dt = datetime.strptime(date_str, "%Y%m%d")
    target = dt - timedelta(days=1)
    while target.weekday() >= 5: target -= timedelta(days=1)
    return target.strftime('%Y%m%d')

def format_trade_instruction(inst):
    action = inst.get("action", "WATCH")
    label = inst.get("action_label", action)
    parts = [label]
    if inst.get("trigger_price"): parts.append(f"觸發 {inst['trigger_price']}")
    if inst.get("limit_price"): parts.append(f"限價 {inst['limit_price']}")
    if inst.get("stop_loss"): parts.append(f"停損 {inst['stop_loss']}")
    if inst.get("take_profit_1"): parts.append(f"停利1 {inst['take_profit_1']}")
    shares = inst.get("shares", 0)
    if shares: parts.append(f"股數 {shares} ({inst.get('lots', 0)}張)")
    reason = inst.get("reason")
    if reason: parts.append(reason)
    return " | ".join(parts)

# ----------------- 啟動進入點 -----------------
def main():
    # 配置基礎日誌格式
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    # 載入本地雙快取
    try:
        load_all_caches()
        logging.info("本地雙快取加載完成。")
    except Exception as e:
        logging.error(f"加載快取異常: {e}")
        
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
