import ctypes
from ctypes import wintypes
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import winreg
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import psutil
from PySide6.QtCore import (
    QFileInfo,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Aero Chrono"
APP_VERSION = "1.0.0"
POLL_INTERVAL_MS = 3000        # 3 sec polling foreground window
FLUSH_INTERVAL_SEC = 15        # 15 sec sqLite sync

if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", EXE_DIR))
else:
    EXE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = EXE_DIR

BASE_DIR = EXE_DIR


def get_data_dir() -> Path:
    local_data = EXE_DIR / "data"
    if (EXE_DIR / "portable.txt").exists() or (EXE_DIR / "portable.dat").exists():
        return local_data

    appdata = os.environ.get("APPDATA")
    if appdata:
        target = Path(appdata) / "AeroChrono"
    else:
        target = Path.home() / "AppData" / "Roaming" / "AeroChrono"

    if local_data.exists() and (local_data / "chrono.db").exists() and not (target / "chrono.db").exists():
        try:
            target.mkdir(parents=True, exist_ok=True)
            if (local_data / "chrono.db").exists():
                shutil.copy2(local_data / "chrono.db", target / "chrono.db")
            if (local_data / "config.json").exists():
                shutil.copy2(local_data / "config.json", target / "config.json")
            if (local_data / "icons").exists():
                shutil.copytree(local_data / "icons", target / "icons", dirs_exist_ok=True)
        except Exception:
            pass

    return target


DATA_DIR = get_data_dir()
ICON_CACHE_DIR = DATA_DIR / "icons"
DB_PATH = DATA_DIR / "chrono.db"
CONFIG_PATH = DATA_DIR / "config.json"

ASSETS_DIR = BUNDLE_DIR / "assets" if (BUNDLE_DIR / "assets").exists() else (EXE_DIR / "assets")
APP_ICON_PATH = ASSETS_DIR / "app_icon.png"
APP_ICO_PATH = ASSETS_DIR / "app_icon.ico"
SEARCH_SVG_PATH = ASSETS_DIR / "search.svg"
GITHUB_SVG_PATH = ASSETS_DIR / "github.svg"
ARROW_DOWN_PATH = ASSETS_DIR / "arrow_down.svg"
ARROW_DOWN_HOVER_PATH = ASSETS_DIR / "arrow_down_hover.svg"
SORT_TIME_PATH = ASSETS_DIR / "sort_time.svg"
SORT_RECENT_PATH = ASSETS_DIR / "sort_recent.svg"
SORT_ALPHA_PATH = ASSETS_DIR / "sort_alpha.svg"
FOCUS_SVG_PATH = ASSETS_DIR / "focus.svg"
FOCUS_IDLE_SVG_PATH = ASSETS_DIR / "focus_idle.svg"
THEME_LIGHT_SVG_PATH = ASSETS_DIR / "theme_light.svg"
THEME_DARK_SVG_PATH = ASSETS_DIR / "theme_dark.svg"

DATA_DIR.mkdir(parents=True, exist_ok=True)
ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)

SIZE_PRESETS: Dict[str, Tuple[int, int, str, str]] = {
    "compact": (920,  660,  "Compact (920 x 660)", "Kompakt (920 x 660)"),
    "1080p":   (1060, 760,  "Standard - 1080p (1060 x 760)", "Standart - 1080p (1060 x 760)"),
    "1440p":   (1360, 960,  "Large - 2K / 1440p (1360 x 960)", "Büyük - 2K / 1440p (1360 x 960)"),
    "2160p":   (1760, 1220, "Ultra - 4K / 2160p (1760 x 1220)", "Ultra - 4K / 2160p (1760 x 1220)"),
}

# default exclusions (overlays, anticheat stuff, system processes, whatever)
DEFAULT_EXCLUDES = [
    # win stuff
    "explorer.exe",
    "applicationframehost.exe",
    "textinputhost.exe",
    "searchhost.exe",
    "searchapp.exe",
    "startmenuexperiencehost.exe",
    "shellexperiencehost.exe",
    "shellhost.exe",
    "sihost.exe",
    "lockapp.exe",
    "logonui.exe",
    "systemsettings.exe",
    "taskmgr.exe",
    "dwm.exe",
    "svchost.exe",
    "conhost.exe",
    "runtimebroker.exe",
    "credentialuibroker.exe",
    "pickerhost.exe",
    "openwith.exe",
    "consent.exe",
    "smartscreen.exe",
    "rundll32.exe",
    "dllhost.exe",
    "mmc.exe",
    "msiexec.exe",
    "werfault.exe",
    "wermgr.exe",
    "ctfmon.exe",
    "audiodg.exe",
    "spoolsv.exe",
    "taskhostw.exe",
    "useroobebroker.exe",
    "musnotification.exe",
    "musnotificationux.exe",
    "upfc.exe",
    "widgetservice.exe",
    "widgets.exe",
    "phoneexperiencehost.exe",
    "crossdeviceresume.exe",
    "gamebar.exe",
    "gamebarftserver.exe",
    "gamebarpresencewriter.exe",
    "screenclippinghost.exe",
    "snippingtool.exe",
    "snappingtool.exe",
    "copilot.exe",
    # webview / cef / whatever stuff
    "msedgewebview2.exe",
    "cefsharp.browsersubprocess.exe",
    "crashpad_handler.exe",
    "crashreporter.exe",
    "unitycrashhandler64.exe",
    "unitycrashhandler32.exe",
    "unrealcefsubprocess.exe",
    "zfgamebrowser.exe",
    "steamwebhelper.exe",
    "gameoverlayui.exe",
    "steamservice.exe",
    "epicwebhelper.exe",
    "eosoverlayrenderer-win64-shipping.exe",
    "eosoverlayrenderer-win32-shipping.exe",
    "riotclientservices.exe",
    "riotclientux.exe",
    "riotclientuxrender.exe",
    "eabackgroundservice.exe",
    "link2ea.exe",
    "easteamproxy.exe",
    "uplaywebcore.exe",
    "upc.exe",
    "ubisoftgamelauncher.exe",
    "battlenet.exe",
    "agent.exe",
    "galaxyclienthelper.exe",
    "galaxycommunication.exe",
    "steelseriesgg.exe",
    "steelseriesggclient.exe",
    "steelseriesengine.exe",
    "steelseriessonar.exe",
    "lghub.exe",
    "lghub_agent.exe",
    "lghub_system_tray.exe",
    "lghub_updater.exe",
    "logioptionsplus_agent.exe",
    "logioptionsplus_appbroker.exe",
    "logioverlay.exe",
    "razer synapse 3.exe",
    "razercentral.exe",
    "rzsdkserver.exe",
    "rzchromastreamserver.exe",
    "gamecaster.exe",
    "icue.exe",
    "icueupdateservice.exe",
    "corsair.service.exe",
    "armourycrate.exe",
    "armourycrate.usersessionhelper.exe",
    "acpowernotification.exe",
    "nzxt cam.exe",
    "cam_helper.exe",
    "wootility.exe",
    "sharex.exe",
    "overwolf.exe",
    "overwolfbrowser.exe",
    "overwolfhelper.exe",
    "overwolfhelper64.exe",
    "medal.exe",
    "medalencoder.exe",
    "outplayed.exe",
    "insights.exe",
    "plays.exe",
    "wallpaper32.exe",
    "wallpaper64.exe",
    "webwallpaper32.exe",
    "translucenttb.exe",
    "powertoys.exe",
    "powertoys.colorpickerui.exe",
    "powertoys.fancyzones.exe",
    "powertoys.powerlauncher.exe",
    "everything.exe",
    # anticheat splash / bg servicse
    "start_protected_game.exe",
    "easyanticheat_eos.exe",
    "easyanticheat.exe",
    "easyanticheat_setup.exe",
    "fortniteclient-win64-shipping_eac_eos.exe",
    "beservice.exe",
    "bedaisy.exe",
    "vgc.exe",
    "vgtray.exe",
    "ace-tray.exe",
    "sguard64.exe",
    "sguardsvc64.exe",
    "nksp.exe",
    "xhunter1.exe",
    "ucldr_battlegrounds_gl.exe",
    # nvSHITia overlay
    "nvidia overlay.exe",
    "nvidia share.exe",
    "nvcontainer.exe",
    "nvdisplay.container.exe",
    "nvsphelper64.exe",
    "nvcplui.exe",
    "radeonsoftware.exe",
    "amdrsserv.exe",
    "amdow.exe",
    "igcctray.exe",
    "igcc.exe",
    "rtss.exe",
    "rtsshooksloader64.exe",
    "encoderhost.exe",
    "presentmon.exe",
    # temp self process names
    "python.exe",
    "pythonw.exe",
    "aerochrono.exe",
]

_WINDIR = os.path.normpath(os.environ.get("WINDIR", r"C:\Windows")).lower()
WINDOWS_SYSTEM_PATH_PREFIXES = (
    os.path.join(_WINDIR, "system32") + "\\",
    os.path.join(_WINDIR, "syswow64") + "\\",
    os.path.join(_WINDIR, "systemapps") + "\\",
    os.path.join(_WINDIR, "immersivecontrolpanel") + "\\",
    os.path.join(_WINDIR, "winsxs") + "\\",
    os.path.join(_WINDIR, "servicing") + "\\",
)
WINDOWS_APPS_JUNK_PREFIXES = (
    "microsoft.windows.",
    "microsoftwindows.",
    "microsoft.ui.",
    "microsoft.xboxgamingoverlay",
    "microsoft.screensketch",
    "microsoft.yourphone",
    "microsoft.widgetsplatformruntime",
    "microsoft.desktopappinstaller",
    "microsoft.aad.brokerplugin",
    "microsoft.lockapp",
    "microsoft.sechealthui",
    "microsoft.winget.",
    "windows.cbs",
    "windows.printdialog",
)

GENERIC_PRODUCT_NAMES = {
    "application",
    "game",
    "bootstrap",
    "bootstrappackagedgame",
    "unrealengine",
    "unreal engine",
    "unity",
    "unityplayer",
    "electron",
    "chromium",
    "microsoft® windows® operating system",
    "microsoft windows operating system",
    "windows operating system",
    "launcher",
    "client",
    "main",
    "bin",
    "app",
}

TRANSLATIONS = {
    "en": {
        "app_title": "Aero Chrono - App Time Tracker",
        "app_subtitle": "App Time Tracker",
        "nav_overview": "Overview",
        "nav_filters": "Include / Exclude",
        "nav_settings": "Settings",
        "nav_about": "About",
        "nav_export": "Export",
        "nav_reset": "Reset All",
        "about_title": "About Aero Chrono",
        "about_desc": "A lightweight application time tracker that lets you customize what to track and what to exclude, always keeping you in full control of where your time goes.",
        "about_dev": "Developer:",
        "about_disclosure": "<b>Disclosure:</b> Icon is not AI generated, it was created by a friend, thank you Rei. Gemini assisted in code, debugging and implementing specific features.",
        "about_close": "Close",
        "status_active": "Tracking active",
        "status_summary": "Tracking active  |  Recorded: {total} apps  |  Currently running: {active}",
        "tray_active": "{name} — {count} active app(s) tracked",
        "tray_bg": "{name} — Tracking in background",
        "tray_open": "Open Window",
        "tray_quit": "Exit",
        "search_app_placeholder": "Search app or .exe...",
        "sort_total_time": "By Total Time",
        "sort_last_used": "By Last Used",
        "sort_name": "By Name (A-Z)",
        "col_app": "Application",
        "col_status": "Status",
        "col_all_time": "All Time",
        "col_sessions": "Sessions",
        "status_running": "Running (PID {pid})",
        "status_closed": "Closed",
        "inspector_empty_title": "Select an application",
        "inspector_empty_sub": "Detailed daily and session breakdown will appear here.",
        "btn_rename": "Rename",
        "btn_exclude": "Exclude",
        "lbl_daily_usage": "Daily Breakdown",
        "col_date": "Date",
        "col_launches": "Launches",
        "col_day_total": "Daily Total",
        "times_suffix": "times",
        "lbl_sessions_title": "Sessions for Selected Day",
        "lbl_sessions_title_count": "Sessions on {date} ({count} launches)",
        "col_session_idx": "#",
        "col_time_range": "Time Range",
        "col_duration": "Duration",
        "col_pid": "PID",
        "session_in_progress": "In progress",
        "session_item_prefix": "Session",
        "detail_empty": "Select a day and session above to inspect details.",
        "detail_empty_day": "Select a session above to inspect details.",
        "detail_text": "<b>Session {idx}</b> ({date})  |  Duration: <b>{dur}</b>  |  Time: {time_range}  |  PID: <b>{pid}</b><br><span style='color:{path_color};'>Path: {path}</span>",
        "path_unknown": "Unknown path",
        "all_time_totals": "All Time: {dur}  •  {count} sessions",
        "ctx_rename": "Edit Display Name",
        "ctx_exclude": "Add to Exclude List",
        "ctx_include": "Add to Include List",
        "dlg_rename_title": "Edit Application Name",
        "dlg_rename_prompt": "Custom name for {exe} (leave empty to use default):",
        "msg_excluded_title": "Excluded",
        "msg_excluded_text": "'{app}' was added to Exclude list. It will no longer be tracked.",
        "mode_title": "Tracking & System Filtering Mode",
        "mode_exclude": "Smart Mode (Default): Track active user apps, ignore Exclude list",
        "mode_include": "Strict Mode (Include Only): Only track applications in the Include list",
        "chk_auto_win_junk": "Automatically exclude Windows system components (System32, SystemApps, UWP shell hosts)",
        "include_panel_title": "Include List (Force Track)",
        "include_panel_desc": "Overrides system filter; tracks windowless/tray processes as well.",
        "exclude_panel_title": "Exclude List (Ignored)",
        "exclude_panel_desc": "Processes you don't want tracked (overlays, launchers, splash screens, etc.).",
        "filter_placeholder": "e.g. photoshop.exe",
        "btn_add": "Add",
        "btn_pick_running": "Pick from Running",
        "btn_remove_selected": "Remove Selected",
        "sec_language": "Language",
        "sec_language_desc": "Select display language for the application.",
        "sec_window_size": "Window Sizing",
        "sec_window_size_desc": "Window borders are fixed. Select a resolution preset suited for your display.",
        "size_auto": "Auto (Based on display resolution)",
        "btn_apply_size": "Apply Size",
        "sec_startup": "System & Startup",
        "chk_autostart": "Start minimized in system tray when Windows boots",
        "lbl_tray_info": "Closing the window minimizes to the system tray so tracking continues. To fully quit, right-click the tray icon and choose Exit.",
        "sec_data": "Data Management & Backup",
        "lbl_db_path": "Database location: {path}",
        "btn_open_folder": "Open Folder",
        "btn_export_json": "Export JSON",
        "btn_export_csv": "Export CSV",
        "btn_reset_all": "Reset All Time Data",
        "export_menu_json": "Export as JSON (.json)",
        "export_menu_csv": "Export as CSV (.csv)",
        "export_dialog_json": "Export as JSON",
        "export_dialog_csv": "Export as CSV",
        "file_filter_json": "JSON Files (*.json)",
        "file_filter_csv": "CSV Files (*.csv)",
        "export_done_title": "Export Completed",
        "export_done_msg": "Data successfully saved to:\n{path}",
        "reset_warn_title": "Reset All Time Data",
        "reset_warn_msg": "All recorded application times, daily logs, and session history will be permanently deleted.\n\nAre you sure you want to proceed?",
        "reset_done_sub": "All records have been reset.",
        "autostart_err_title": "Startup Setting Error",
        "autostart_err_msg": "Could not update registry key:\n{err}",
        "dlg_proc_title": "Select Running Process",
        "dlg_proc_label": "Select a running application from the list:",
        "dlg_proc_search": "Search process name (e.g. photoshop.exe)...",
        "btn_select": "Select",
        "btn_cancel": "Cancel",
        "csv_headers": ["Application", "EXE", "Date", "Session #", "PID", "Start", "End", "Duration (s)", "Duration"],
        "size_preset_status": "Profile: {label}",
        "nav_theme": "Theme",
        "theme_light": "Windows 7 Aero (Light)",
        "theme_dark": "Windows Vista Obsidian (Dark)",
        "theme_tooltip": "Toggle Theme (Light / Dark)",
        "ctx_focus_toggle": "Track only when focused",
        "status_focused": "Focused",
        "status_idle": "Idle",
        "focus_panel_title": "Focus-Only List (Track Only When Active)",
        "focus_panel_desc": "Applications that only track time when their window is actively focused in foreground.",
        "sec_theme": "Theme & Visual Style",
        "sec_theme_desc": "Select application theme: Windows 7 Aero Light or Windows Vista Obsidian Dark Glass.",
        "sec_track_mode": "Default Tracking Mode",
        "sec_track_mode_desc": "Choose whether background applications track time by default or only the focused window.",
        "track_mode_all": "Track all running applications (Default)",
        "track_mode_focused": "Track only focused window globally",
    },
    "tr": {
        "app_title": "Aero Chrono - Uygulama Kullanım Süresi İzleyici",
        "app_subtitle": "Uygulama Kullanım Süresi İzleyici",
        "nav_overview": "Genel Bakış",
        "nav_filters": "Include / Exclude",
        "nav_settings": "Ayarlar",
        "nav_about": "Hakkında",
        "nav_export": "Dışa Aktar",
        "nav_reset": "Süreleri Sıfırla",
        "about_title": "Aero Chrono Hakkında",
        "about_desc": "Neleri izleyip neleri hariç tutacağınızı kolayca özelleştirebileceğiniz, uygulamalarda ne kadar vakit geçirdiğinizi her an bilmenizi sağlayan hafif bir süre takip uygulaması.",
        "about_dev": "Geliştirici:",
        "about_disclosure": "<b>Açıklama:</b> İkon yapay zeka üretimi değildir, bir arkadaşım tarafından çizilmiştir, teşekkürler Rei. Gemini kodlama, hata ayıklama ve belirli özelliklerin geliştirilmesinde yardımcı olmuştur.",
        "about_close": "Kapat",
        "status_active": "İzleme etkin",
        "status_summary": "İzleme etkin  |  Kayıtlı: {total} uygulama  |  Şu an açık: {active}",
        "tray_active": "{name} — {count} aktif uygulama izleniyor",
        "tray_bg": "{name} — Arka planda izleniyor",
        "tray_open": "Pencereyi Aç",
        "tray_quit": "Tamamen Çıkış",
        "search_app_placeholder": "Uygulama veya .exe ara...",
        "sort_total_time": "Toplam Süreye Göre",
        "sort_last_used": "Son Kullanıma Göre",
        "sort_name": "İsme Göre (A-Z)",
        "col_app": "Uygulama",
        "col_status": "Durum",
        "col_all_time": "Tüm Zamanlar",
        "col_sessions": "Oturum",
        "status_running": "Açık (PID {pid})",
        "status_closed": "Kapalı",
        "inspector_empty_title": "Bir uygulama seçin",
        "inspector_empty_sub": "Detaylı günlük ve oturum dökümü burada görüntülenir.",
        "btn_rename": "Adlandır",
        "btn_exclude": "Hariç Tut",
        "lbl_daily_usage": "Günlere Göre Kullanım",
        "col_date": "Tarih",
        "col_launches": "Açılma",
        "col_day_total": "Günlük Toplam",
        "times_suffix": "kez",
        "lbl_sessions_title": "Seçili Günün Oturumları",
        "lbl_sessions_title_count": "{date} Tarihindeki Oturumlar ({count} kez açıldı)",
        "col_session_idx": "#",
        "col_time_range": "Saat Aralığı",
        "col_duration": "Süre",
        "col_pid": "PID",
        "session_in_progress": "Devam ediyor",
        "session_item_prefix": "Oturum",
        "detail_empty": "Detay görmek için bir gün ve oturum seçin.",
        "detail_empty_day": "Detay görmek için yukarıdan bir oturum seçin.",
        "detail_text": "<b>{idx}. Oturum</b> ({date})  |  Süre: <b>{dur}</b>  |  Saat: {time_range}  |  PID: <b>{pid}</b><br><span style='color:{path_color};'>Yol: {path}</span>",
        "path_unknown": "Bilinmiyor",
        "all_time_totals": "Tüm Zamanlar: {dur}  •  {count} oturum",
        "ctx_rename": "Görünen Adı Düzenle",
        "ctx_exclude": "Exclude Listesine Ekle",
        "ctx_include": "Include Listesine Ekle",
        "dlg_rename_title": "Uygulama Adını Düzenle",
        "dlg_rename_prompt": "{exe} için özel isim (boş bırakırsanız otomatik isim kullanılır):",
        "msg_excluded_title": "Hariç Tutuldu",
        "msg_excluded_text": "'{app}' Exclude listesine eklendi. Bundan sonra izlenmeyecek.",
        "mode_title": "İzleme ve Sistem Filtreleme Modu",
        "mode_exclude": "Akıllı Mod (Varsayılan): Açık kullanıcı uygulamalarını izle, Exclude listesindekileri yoksay",
        "mode_include": "Sıkı Mod (Sadece Include): Yalnızca Include listesine eklediğim uygulamaları izle",
        "chk_auto_win_junk": "Windows sistem bileşenlerini otomatik hariç tut (System32, SystemApps ve UWP kabuk host'ları)",
        "include_panel_title": "Include Listesi (Zorla İzle)",
        "include_panel_desc": "Sistem filtresini geçersiz kılar; penceresiz/tepside çalışan uygulamaları da izler.",
        "exclude_panel_title": "Exclude Listesi (Hariç Tutulanlar)",
        "exclude_panel_desc": "İzlenmesini istemediğiniz ek .exe adları (overlay, splash ekranı vb.).",
        "filter_placeholder": "örn. photoshop.exe",
        "btn_add": "Ekle",
        "btn_pick_running": "Çalışanlardan Seç",
        "btn_remove_selected": "Seçileni Kaldır",
        "sec_language": "Dil",
        "sec_language_desc": "Uygulama arayüz dilini seçin.",
        "sec_window_size": "Pencere Boyutu",
        "sec_window_size_desc": "Pencere boyutu kenarlardan sürüklenerek değiştirilemez. Monitör çözünürlüğünüze uygun sabit profili seçebilirsiniz.",
        "size_auto": "Otomatik (Ekran Çözünürlüğüne Göre)",
        "btn_apply_size": "Boyutu Uygula",
        "sec_startup": "Sistem ve Başlangıç",
        "chk_autostart": "Windows açıldığında sistem tepsisinde (simge durumunda) otomatik başlat",
        "lbl_tray_info": "Pencere kapatıldığında uygulama arka planda izlemeye devam etmek için sistem tepsisine küçülür. Tamamen kapatmak için sistem tepsisi simgesine sağ tıklayıp Çıkış yapabilirsiniz.",
        "sec_data": "Veri Yönetimi ve Yedekleme",
        "lbl_db_path": "Veritabanı konumu: {path}",
        "btn_open_folder": "Klasörü Aç",
        "btn_export_json": "JSON Olarak Dışa Aktar",
        "btn_export_csv": "CSV Olarak Dışa Aktar",
        "btn_reset_all": "Tüm Süreleri Sıfırla",
        "export_menu_json": "JSON Olarak Dışa Aktar (.json)",
        "export_menu_csv": "CSV Olarak Dışa Aktar (.csv)",
        "export_dialog_json": "JSON Olarak Dışa Aktar",
        "export_dialog_csv": "CSV Olarak Dışa Aktar",
        "file_filter_json": "JSON Dosyaları (*.json)",
        "file_filter_csv": "CSV Dosyaları (*.csv)",
        "export_done_title": "Dışa Aktarma Tamamlandı",
        "export_done_msg": "Veriler kaydedildi:\n{path}",
        "reset_warn_title": "Tüm Süreleri Sıfırla",
        "reset_warn_msg": "Kayıtlı tüm uygulama süreleri, günlük geçmiş ve oturum kayıtları kalıcı olarak silinecektir.\n\nDevam etmek istediğinize emin misiniz?",
        "reset_done_sub": "Tüm kayıtlar sıfırlandı.",
        "autostart_err_title": "Başlangıç Ayarı Hatası",
        "autostart_err_msg": "Kayıt defteri güncellenemedi:\n{err}",
        "dlg_proc_title": "Çalışan Süreç Seç",
        "dlg_proc_label": "Şu an çalışan uygulamalardan birini seçin:",
        "dlg_proc_search": "Süreç adı ara (örn. photoshop.exe)...",
        "btn_select": "Seç",
        "btn_cancel": "İptal",
        "csv_headers": ["Uygulama", "EXE", "Tarih", "Oturum No", "PID", "Başlangıç", "Bitiş", "Süre (sn)", "Süre"],
        "size_preset_status": "Profil: {label}",
        "nav_theme": "Tema",
        "theme_light": "Windows 7 Aero (Açık)",
        "theme_dark": "Windows Vista Obsidian (Koyu)",
        "theme_tooltip": "Temayı Değiştir (Açık / Koyu)",
        "ctx_focus_toggle": "Yalnızca odaklanıldığında izle",
        "status_focused": "Odaklı",
        "status_idle": "Boşta",
        "focus_panel_title": "Odak Takip Listesi (Sadece Öndeyken İzle)",
        "focus_panel_desc": "Yalnızca pencereleri ekranda aktif odaktayken süre sayacak uygulamalar (örn. boşta bekleyen tarayıcılar).",
        "sec_theme": "Görünüm ve Tema",
        "sec_theme_desc": "Uygulama temasını seçin: Windows 7 Aero Açık veya Windows Vista Obsidian Koyu Cam.",
        "sec_track_mode": "Varsayılan İzleme Modu",
        "sec_track_mode_desc": "Arka plandaki uygulamaların varsayılan olarak süre sayıp saymayacağını belirleyin.",
        "track_mode_all": "Tüm çalışan uygulamaları izle (Varsayılan)",
        "track_mode_focused": "Yalnızca öndeki aktif pencereyi izle (Global)",
    },
}

# win32 API wrapper (usermode, readonly)
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
version_dll = ctypes.WinDLL("version", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

try:
    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
    shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
except Exception:
    pass

try:
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM
except Exception:
    pass

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.HWND,
    wintypes.LONG,
    wintypes.LONG,
    wintypes.DWORD,
    wintypes.DWORD,
)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL

user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long

user32.SetWinEventHook.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HMODULE,
    WINEVENTPROC,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
]
user32.SetWinEventHook.restype = wintypes.HANDLE

user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.UnhookWinEvent.restype = wintypes.BOOL

dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

version_dll.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
version_dll.GetFileVersionInfoSizeW.restype = wintypes.DWORD

version_dll.GetFileVersionInfoW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
]
version_dll.GetFileVersionInfoW.restype = wintypes.BOOL

version_dll.VerQueryValueW.argtypes = [
    ctypes.c_void_p,
    wintypes.LPCWSTR,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(wintypes.UINT),
]
version_dll.VerQueryValueW.restype = wintypes.BOOL

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DWMWA_CLOAKED = 14
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

# read exe path with lowest privs
def get_process_image_path(pid: int) -> Optional[str]:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        try:
            buf_size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(buf_size)):
                return buf.value
        finally:
            kernel32.CloseHandle(handle)
    try:
        return psutil.Process(pid).exe()
    except Exception:
        return None


def is_valid_user_window(hwnd: int, own_pid: int) -> Tuple[bool, int, str]:
    if not hwnd or not user32.IsWindowVisible(hwnd):
        return False, 0, ""

    # skip tool windows / cloaked / 0-size ghost windows
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if ex_style & WS_EX_TOOLWINDOW:
        return False, 0, ""

    cloaked = wintypes.DWORD(0)
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    if hr == 0 and cloaked.value != 0:
        return False, 0, ""

    if not user32.IsIconic(hwnd):
        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            if (rect.right - rect.left) <= 0 or (rect.bottom - rect.top) <= 0:
                return False, 0, ""

    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return False, 0, ""

    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == 0 or pid.value == own_pid:
        return False, 0, ""

    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value.strip()
    if not title:
        return False, 0, ""

    return True, pid.value, title


def get_visible_window_processes() -> Dict[int, str]:
    found: Dict[int, str] = {}
    own_pid = os.getpid()

    def enum_cb(hwnd, _lparam):
        ok, pid, title = is_valid_user_window(hwnd, own_pid)
        if ok and pid not in found:
            found[pid] = title
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return found


def is_windows_system_junk_path(exe_path: Optional[str]) -> bool:
    if not exe_path:
        return False
    norm = os.path.normpath(exe_path).lower()

    if norm == os.path.join(_WINDIR, "explorer.exe"):
        return True

    if norm.startswith(WINDOWS_SYSTEM_PATH_PREFIXES):
        return True

    # ignore ms app packages
    marker = "\\windowsapps\\"
    idx = norm.find(marker)
    if idx != -1:
        rest = norm[idx + len(marker):]
        pkg_folder = rest.split("\\", 1)[0]
        if pkg_folder.startswith(WINDOWS_APPS_JUNK_PREFIXES):
            return True

    return False


# read pe strings from disk
def read_pe_version_strings(exe_path: str) -> Tuple[Optional[str], Optional[str]]:
    if not exe_path or not os.path.isfile(exe_path):
        return None, None

    dummy = wintypes.DWORD(0)
    size = version_dll.GetFileVersionInfoSizeW(exe_path, ctypes.byref(dummy))
    if not size:
        return None, None

    buf = ctypes.create_string_buffer(size)
    if not version_dll.GetFileVersionInfoW(exe_path, 0, size, buf):
        return None, None

    trans_ptr = ctypes.c_void_p()
    trans_len = wintypes.UINT(0)
    lang_codes = [("0409", "04b0"), ("0409", "04e4"), ("0000", "04b0")]

    if version_dll.VerQueryValueW(
        buf, r"\VarFileInfo\Translation", ctypes.byref(trans_ptr), ctypes.byref(trans_len)
    ) and trans_len.value >= 4:
        arr = (wintypes.WORD * (trans_len.value // 2)).from_address(trans_ptr.value)
        lang_codes.insert(0, (f"{arr[0]:04x}", f"{arr[1]:04x}"))

    def query_field(field: str) -> Optional[str]:
        for lang, cp in lang_codes:
            sub = f"\\StringFileInfo\\{lang}{cp}\\{field}"
            val_ptr = ctypes.c_void_p()
            val_len = wintypes.UINT(0)
            if version_dll.VerQueryValueW(buf, sub, ctypes.byref(val_ptr), ctypes.byref(val_len)):
                if val_len.value > 0 and val_ptr.value:
                    text = ctypes.wstring_at(val_ptr.value).strip()
                    if text:
                        return text
        return None

    return query_field("ProductName"), query_field("FileDescription")


# strip common suffixes (shipping, win64, etc)
class NameResolver:
    SUFFIX_PATTERN = re.compile(
        r"(?i)([-_. ]+(?:win64|win32|x64|x86|shipping|client|dx11|dx12|vulkan|"
        r"release|retail|steam|eos|ue4|ue5|64bit|32bit|standalone|launcher))+$"
    )
    TRAILING_TAG = re.compile(r"(?i)(?<=[a-z0-9]{3})(client|shipping|win64|win32)$")

    @classmethod
    def _sanitize_meta(cls, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        cleaned = re.sub(r"[®™©]", "", raw).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        if not cleaned or len(cleaned) < 2:
            return None
        if cleaned.lower() in GENERIC_PRODUCT_NAMES:
            return None
        if cleaned.lower().endswith(".exe"):
            return None
        return cleaned

    @classmethod
    def resolve(cls, exe_name: str, exe_path: Optional[str] = None) -> str:
        if exe_path:
            product, desc = read_pe_version_strings(exe_path)
            for candidate in (product, desc):
                valid = cls._sanitize_meta(candidate)
                if valid:
                    if cls.SUFFIX_PATTERN.search(valid):
                        valid = cls.SUFFIX_PATTERN.sub("", valid).strip(" -_")
                        valid = cls.TRAILING_TAG.sub("", valid).strip(" -_")
                    if valid and valid.lower() not in GENERIC_PRODUCT_NAMES:
                        return valid

        stem = exe_name[:-4] if exe_name.lower().endswith(".exe") else exe_name
        cleaned = cls.SUFFIX_PATTERN.sub("", stem)
        cleaned = cls.TRAILING_TAG.sub("", cleaned).strip(" -_")

        if cleaned and cleaned != stem and len(cleaned) >= 2:
            if not cleaned.isupper():
                cleaned = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cleaned)
            cleaned = cleaned.replace("_", " ").replace("-", " ")
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
            if cleaned and cleaned.lower() not in GENERIC_PRODUCT_NAMES:
                return cleaned

        return exe_name


def format_duration(seconds: int, include_seconds: bool = False, lang: str = "en") -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)

    h_unit = "h" if lang == "en" else "sa"
    m_unit = "m" if lang == "en" else "dk"
    s_unit = "s" if lang == "en" else "sn"

    if hours > 0:
        if include_seconds:
            return f"{hours} {h_unit} {minutes} {m_unit} {secs} {s_unit}"
        return f"{hours} {h_unit} {minutes} {m_unit}"
    if minutes > 0:
        if include_seconds:
            return f"{minutes} {m_unit} {secs} {s_unit}"
        return f"{minutes} {m_unit}"
    return f"{secs} {s_unit}"


def format_date(date_str: str, lang: str = "en") -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if lang == "tr":
            return dt.strftime("%d.%m.%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str


# hkcu run entry
def set_windows_autostart(enabled: bool) -> Tuple[bool, str]:
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            if getattr(sys, "frozen", False):
                cmd = f'"{sys.executable}" --minimized'
            else:
                exe = sys.executable
                if exe.lower().endswith("python.exe"):
                    candidate = exe[:-10] + "pythonw.exe"
                    if os.path.isfile(candidate):
                        exe = candidate
                script = str(Path(__file__).resolve())
                cmd = f'"{exe}" "{script}" --minimized'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True, ""
    except Exception as e:
        return False, str(e)


def is_windows_autostart_enabled() -> bool:
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


class ConfigManager:
    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _default(self) -> dict:
        return {
            "language": "en",
            "size_preset": "auto",
            "theme": "light",
            "filter_mode": "exclude",
            "auto_filter_windows_junk": True,
            "exclude_list": sorted(set(DEFAULT_EXCLUDES)),
            "include_list": [],
            "focus_only_list": [],
            "tracking_mode": "all",
            "autostart": False,
        }

    def _load(self) -> dict:
        cfg = self._default()
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                cfg.update(loaded)
            except Exception:
                pass
        if "language" not in cfg:
            cfg["language"] = "en"
        if "theme" not in cfg:
            cfg["theme"] = "light"
        if "focus_only_list" not in cfg:
            cfg["focus_only_list"] = []
        if "tracking_mode" not in cfg:
            cfg["tracking_mode"] = "all"
        return cfg

    def save(self):
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


# cache exe icons
class IconManager:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.provider = QFileIconProvider()
        self._mem_cache: Dict[str, QIcon] = {}
        self._default_icon: Optional[QIcon] = None

    def get_default_windows_icon(self) -> QIcon:
        if self._default_icon is not None:
            return self._default_icon
        windir = os.environ.get("WINDIR", r"C:\Windows")
        for candidate in ("System32\\svchost.exe", "System32\\rundll32.exe"):
            p = os.path.join(windir, candidate)
            if os.path.isfile(p):
                icon = self.provider.icon(QFileInfo(p))
                if not icon.isNull():
                    self._default_icon = icon
                    return icon
        self._default_icon = QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_FileIcon
        )
        return self._default_icon

    def get_icon(self, app_key: str, exe_path: Optional[str]) -> QIcon:
        if app_key in self._mem_cache:
            return self._mem_cache[app_key]

        file_hash = hashlib.md5(app_key.encode("utf-8")).hexdigest()
        cached_png = self.cache_dir / f"{file_hash}.png"

        if cached_png.exists():
            icon = QIcon(str(cached_png))
            if not icon.isNull():
                self._mem_cache[app_key] = icon
                return icon

        if exe_path and os.path.isfile(exe_path):
            icon = self.provider.icon(QFileInfo(exe_path))
            if not icon.isNull():
                pix = icon.pixmap(48, 48)
                if not pix.isNull():
                    pix.save(str(cached_png), "PNG")
                    cached_icon = QIcon(pix)
                    self._mem_cache[app_key] = cached_icon
                    return cached_icon

        return self.get_default_windows_icon()


class Database:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._init_schema()
        self._close_orphaned_sessions()

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS apps (
                app_key TEXT PRIMARY KEY,
                exe_name TEXT NOT NULL,
                exe_path TEXT,
                display_name TEXT NOT NULL,
                custom_name TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_key TEXT NOT NULL,
                pid INTEGER NOT NULL,
                date_str TEXT NOT NULL,
                start_ts REAL NOT NULL,
                end_ts REAL NOT NULL,
                duration_sec INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (app_key) REFERENCES apps(app_key) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_app_date
                ON sessions(app_key, date_str);
            """
        )
        self.conn.commit()

    def _close_orphaned_sessions(self):
        self.conn.execute("UPDATE sessions SET is_active = 0 WHERE is_active = 1")
        self.conn.commit()

    def upsert_app(self, app_key: str, exe_name: str, exe_path: Optional[str], display_name: str):
        now_iso = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.cursor()
        cur.execute("SELECT app_key, exe_path FROM apps WHERE app_key = ?", (app_key,))
        row = cur.fetchone()
        if row:
            new_path = exe_path or row["exe_path"]
            cur.execute(
                "UPDATE apps SET last_seen = ?, exe_path = ? WHERE app_key = ?",
                (now_iso, new_path, app_key),
            )
        else:
            cur.execute(
                """
                INSERT INTO apps (app_key, exe_name, exe_path, display_name, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (app_key, exe_name, exe_path, display_name, now_iso, now_iso),
            )
        self.conn.commit()

    def set_custom_name(self, app_key: str, custom_name: Optional[str]):
        val = custom_name.strip() if custom_name and custom_name.strip() else None
        self.conn.execute("UPDATE apps SET custom_name = ? WHERE app_key = ?", (val, app_key))
        self.conn.commit()

    def start_session(self, app_key: str, pid: int, start_ts: float, date_str: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO sessions (app_key, pid, date_str, start_ts, end_ts, duration_sec, is_active)
            VALUES (?, ?, ?, ?, ?, 0, 1)
            """,
            (app_key, pid, date_str, start_ts, start_ts),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_session(self, session_id: int, end_ts: float, duration_sec: int, is_active: int = 1):
        self.conn.execute(
            """
            UPDATE sessions
            SET end_ts = ?, duration_sec = ?, is_active = ?
            WHERE id = ?
            """,
            (end_ts, max(0, int(duration_sec)), is_active, session_id),
        )
        self.conn.commit()

    def get_all_apps_summary(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                a.app_key,
                a.exe_name,
                a.exe_path,
                COALESCE(a.custom_name, a.display_name) AS name,
                a.display_name,
                a.custom_name,
                a.last_seen,
                COALESCE(SUM(s.duration_sec), 0) AS total_sec,
                COUNT(s.id) AS session_count
            FROM apps a
            LEFT JOIN sessions s ON a.app_key = s.app_key
            GROUP BY a.app_key
            ORDER BY total_sec DESC, name ASC
            """
        )
        return [dict(r) for r in cur.fetchall()]

    def get_app_days(self, app_key: str) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                date_str,
                COUNT(id) AS session_count,
                COALESCE(SUM(duration_sec), 0) AS total_sec
            FROM sessions
            WHERE app_key = ?
            GROUP BY date_str
            ORDER BY date_str DESC
            """,
            (app_key,),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_day_sessions(self, app_key: str, date_str: str) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, pid, date_str, start_ts, end_ts, duration_sec, is_active
            FROM sessions
            WHERE app_key = ? AND date_str = ?
            ORDER BY start_ts ASC
            """,
            (app_key, date_str),
        )
        return [dict(r) for r in cur.fetchall()]

    def reset_all(self):
        self.conn.execute("DELETE FROM sessions")
        self.conn.execute("DELETE FROM apps")
        self.conn.commit()

    def export_full_data(self, lang: str = "en") -> List[dict]:
        apps = self.get_all_apps_summary()
        result = []
        for app in apps:
            days_out = []
            for d in self.get_app_days(app["app_key"]):
                sess_list = self.get_day_sessions(app["app_key"], d["date_str"])
                days_out.append(
                    {
                        "date": d["date_str"],
                        "date_formatted": format_date(d["date_str"], lang=lang),
                        "session_count": d["session_count"],
                        "total_seconds": d["total_sec"],
                        "sessions": [
                            {
                                "session_index": idx + 1,
                                "pid": s["pid"],
                                "start": datetime.fromtimestamp(s["start_ts"]).isoformat(timespec="seconds"),
                                "end": datetime.fromtimestamp(s["end_ts"]).isoformat(timespec="seconds"),
                                "duration_seconds": s["duration_sec"],
                            }
                            for idx, s in enumerate(sess_list)
                        ],
                    }
                )
            result.append(
                {
                    "name": app["name"],
                    "exe_name": app["exe_name"],
                    "exe_path": app["exe_path"],
                    "total_seconds": app["total_sec"],
                    "session_count": app["session_count"],
                    "days": days_out,
                }
            )
        return result


class ActiveSession:
    def __init__(self, session_id: int, app_key: str, pid: int, start_ts: float, date_str: str):
        self.session_id = session_id
        self.app_key = app_key
        self.pid = pid
        self.start_ts = start_ts
        self.date_str = date_str
        self.last_flush_ts = start_ts


class TrackerEngine:
    def __init__(self, db: Database, config: ConfigManager):
        self.db = db
        self.config = config
        self.active_sessions: Dict[str, ActiveSession] = {}
        self.observed_running_apps: Dict[str, Tuple[int, str, Optional[str]]] = {}
        self.current_foreground_app: Optional[str] = None
        self.current_foreground_pid: Optional[int] = None
        self._pid_meta_cache: Dict[int, Tuple[str, str, Optional[str]]] = {}
        self._resolved_names: Dict[str, str] = {}

        self._hook_handle = None
        self._win_event_cb = None
        self._on_instant_change: Optional[Callable[[], None]] = None

    def install_foreground_hook(self, on_change_callback: Optional[Callable[[], None]] = None):
        self._on_instant_change = on_change_callback
        own_pid = os.getpid()

        def _cb(_hook, _event, hwnd, _id_obj, _id_child, _thread, _time):
            try:
                ok, pid, _title = is_valid_user_window(hwnd, own_pid)
                if not ok:
                    return
                info = self._get_proc_info(pid)
                if info:
                    self.current_foreground_app = info[0]
                    self.current_foreground_pid = pid
                focus_list = {x.lower() for x in self.config.data.get("focus_only_list", [])}
                is_global_focus = (self.config.data.get("tracking_mode", "all") == "focused")
                has_focus_rules = bool(focus_list) or is_global_focus
                if self._register_pid_if_new(pid) or has_focus_rules:
                    self.poll()
                    if self._on_instant_change:
                        self._on_instant_change()
                elif self._on_instant_change:
                    self._on_instant_change()
            except Exception:
                pass

        # keep cb ref so gc doesnt drop it
        self._win_event_cb = WINEVENTPROC(_cb)
        self._hook_handle = user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND,
            EVENT_SYSTEM_FOREGROUND,
            0,
            self._win_event_cb,
            0,
            0,
            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
        )

    def _is_allowed(self, exe_name_lower: str, exe_path: Optional[str]) -> bool:
        mode = self.config.data.get("filter_mode", "exclude")
        includes = {x.lower() for x in self.config.data.get("include_list", [])}
        excludes = {x.lower() for x in self.config.data.get("exclude_list", [])}

        if exe_name_lower in includes:
            return True

        if mode == "include_only":
            return False

        if exe_name_lower in excludes:
            return False

        if self.config.data.get("auto_filter_windows_junk", True):
            if is_windows_system_junk_path(exe_path):
                return False

        return True

    def _get_proc_info(self, pid: int) -> Optional[Tuple[str, str, Optional[str]]]:
        if pid in self._pid_meta_cache:
            return self._pid_meta_cache[pid]

        exe_path = get_process_image_path(pid)
        exe_name = None
        if exe_path:
            exe_name = os.path.basename(exe_path)
        else:
            try:
                exe_name = psutil.Process(pid).name()
            except Exception:
                return None

        if not exe_name:
            return None

        app_key = exe_name.lower()
        info = (app_key, exe_name, exe_path)
        self._pid_meta_cache[pid] = info
        return info

    def _start_tracking_app(self, app_key: str, pid: int, exe_name: str, exe_path: Optional[str], now_ts: float, today_str: str):
        if app_key not in self._resolved_names:
            self._resolved_names[app_key] = NameResolver.resolve(exe_name, exe_path)
        display_name = self._resolved_names[app_key]
        self.db.upsert_app(app_key, exe_name, exe_path, display_name)
        sid = self.db.start_session(app_key, pid, now_ts, today_str)
        self.active_sessions[app_key] = ActiveSession(sid, app_key, pid, now_ts, today_str)

    def _register_pid_if_new(self, pid: int) -> bool:
        info = self._get_proc_info(pid)
        if not info:
            return False
        app_key, exe_name, exe_path = info
        if app_key in self.active_sessions:
            return False
        if not self._is_allowed(app_key, exe_path):
            return False

        now_ts = time.time()
        today_str = datetime.fromtimestamp(now_ts).strftime("%Y-%m-%d")
        self._start_tracking_app(app_key, pid, exe_name, exe_path, now_ts, today_str)
        return True

    def poll(self) -> bool:
        now_ts = time.time()
        today_str = datetime.fromtimestamp(now_ts).strftime("%Y-%m-%d")

        own_pid = os.getpid()
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd:
            ok, fg_pid, _ = is_valid_user_window(fg_hwnd, own_pid)
            if ok:
                fg_info = self._get_proc_info(fg_pid)
                if fg_info:
                    self.current_foreground_app = fg_info[0]
                    self.current_foreground_pid = fg_pid

        visible_pids = get_visible_window_processes()
        observed_apps: Dict[str, Tuple[int, str, Optional[str]]] = {}

        for pid in visible_pids.keys():
            info = self._get_proc_info(pid)
            if not info:
                continue
            app_key, exe_name, exe_path = info
            if not self._is_allowed(app_key, exe_path):
                continue
            if app_key not in observed_apps:
                observed_apps[app_key] = (pid, exe_name, exe_path)

        # force include windowless / tray processes
        include_set = {x.lower() for x in self.config.data.get("include_list", [])}
        missing_includes = include_set - set(observed_apps.keys())
        if missing_includes:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (proc.info["name"] or "").lower()
                    if pname in missing_includes and pname not in observed_apps:
                        pid = proc.info["pid"]
                        exe_path = get_process_image_path(pid)
                        observed_apps[pname] = (pid, proc.info["name"], exe_path)
                except Exception:
                    continue

        self.observed_running_apps = observed_apps

        # purge stale pids from cache
        alive_pids = set(visible_pids.keys()) | {v[0] for v in observed_apps.values()}
        if len(self._pid_meta_cache) > 250:
            self._pid_meta_cache = {
                k: v for k, v in self._pid_meta_cache.items() if k in alive_pids
            }

        focus_only_set = {x.lower() for x in self.config.data.get("focus_only_list", [])}
        global_focus_mode = (self.config.data.get("tracking_mode", "all") == "focused")

        # Determine which apps are actively tracked right now
        trackable_apps: Dict[str, Tuple[int, str, Optional[str]]] = {}
        for app_key, data in observed_apps.items():
            is_focus_only = (app_key in focus_only_set) or global_focus_mode
            if is_focus_only:
                if self.current_foreground_app == app_key:
                    trackable_apps[app_key] = data
            else:
                trackable_apps[app_key] = data

        changed = False

        closed_keys = [k for k in self.active_sessions if k not in trackable_apps]
        for app_key in closed_keys:
            sess = self.active_sessions.pop(app_key)
            dur = int(now_ts - sess.start_ts)
            self.db.update_session(sess.session_id, now_ts, dur, is_active=0)
            changed = True

        for app_key, (pid, exe_name, exe_path) in trackable_apps.items():
            if app_key not in self.active_sessions:
                self._start_tracking_app(app_key, pid, exe_name, exe_path, now_ts, today_str)
                changed = True
            else:
                sess = self.active_sessions[app_key]
                # midnight split
                if sess.date_str != today_str:
                    midnight_dt = datetime.strptime(today_str, "%Y-%m-%d")
                    end_prev_ts = midnight_dt.timestamp() - 1
                    prev_dur = max(0, int(end_prev_ts - sess.start_ts))
                    self.db.update_session(sess.session_id, end_prev_ts, prev_dur, is_active=0)

                    new_start_ts = midnight_dt.timestamp()
                    new_sid = self.db.start_session(app_key, pid, new_start_ts, today_str)
                    self.active_sessions[app_key] = ActiveSession(
                        new_sid, app_key, pid, new_start_ts, today_str
                    )
                    changed = True
                elif now_ts - sess.last_flush_ts >= FLUSH_INTERVAL_SEC:
                    dur = int(now_ts - sess.start_ts)
                    self.db.update_session(sess.session_id, now_ts, dur, is_active=1)
                    sess.last_flush_ts = now_ts
                    changed = True

        return changed

    def get_live_extra_seconds(self, app_key: str) -> int:
        sess = self.active_sessions.get(app_key)
        if not sess:
            return 0
        return max(0, int(time.time() - sess.last_flush_ts))

    def shutdown(self):
        if self._hook_handle:
            try:
                user32.UnhookWinEvent(self._hook_handle)
            except Exception:
                pass
            self._hook_handle = None

        now_ts = time.time()
        for sess in list(self.active_sessions.values()):
            dur = int(now_ts - sess.start_ts)
            self.db.update_session(sess.session_id, now_ts, dur, is_active=0)
        self.active_sessions.clear()


AERO_QSS = """
* {
    font-family: "Segoe UI", Tahoma, sans-serif;
    font-size: 9pt;
    color: #1e2a38;
}

QDialog {
    background-color: #f0f5fa;
    color: #1e2a38;
}

#InnerWorkspace {
    background-color: #f4f8fc;
    border: 1px solid #5f82a6;
    border-radius: 3px;
}

#AeroCommandBar {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #f7fbff,
        stop:0.48 #dcebf8,
        stop:0.50 #c5ddf2,
        stop:0.85 #d5e8f8,
        stop:1.00 #eef6fd
    );
    border-bottom: 1px solid #96b4d2;
}

QPushButton.aeroNavBtn {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 5px 12px;
    color: #1a3552;
    font-weight: 500;
}
QPushButton.aeroNavBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 rgba(255, 255, 255, 220),
        stop:0.49 rgba(220, 240, 255, 210),
        stop:0.50 rgba(186, 222, 250, 220),
        stop:1.00 rgba(218, 240, 255, 230)
    );
    border: 1px solid #76a2cc;
}
QPushButton.aeroNavBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #bcdcf6,
        stop:0.49 #92c5ed,
        stop:0.50 #7ab6e7,
        stop:1.00 #a8d3f5
    );
    border: 1px solid #3c73a8;
    color: #0b2238;
    padding-top: 6px;
    padding-bottom: 4px;
}
QPushButton.aeroNavBtn:checked {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #ffffff,
        stop:0.49 #cfe7fc,
        stop:0.50 #a7d2f7,
        stop:1.00 #cde6fc
    );
    border: 1px solid #4d80b3;
    color: #0f2942;
    font-weight: 600;
}

QPushButton.aeroBtn {
    min-height: 24px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #fcfdfe,
        stop:0.48 #eaeff5,
        stop:0.50 #d8e1eb,
        stop:1.00 #e8eef5
    );
    border: 1px solid #7e92a6;
    border-radius: 3px;
    padding: 4px 13px;
    color: #1c2938;
}
QPushButton.aeroBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #f2f9ff,
        stop:0.48 #d7eeff,
        stop:0.50 #b4dcfc,
        stop:1.00 #d3ecff
    );
    border: 1px solid #3c7fb1;
}
QPushButton.aeroBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #c4e2fa,
        stop:0.50 #98c8f0,
        stop:1.00 #b9dcf8
    );
    border: 1px solid #2c628b;
    padding-top: 5px;
    padding-bottom: 3px;
}

QPushButton.aeroDangerBtn {
    min-height: 24px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #fef2f1,
        stop:0.48 #f6d5d2,
        stop:0.50 #ebb7b2,
        stop:1.00 #f5d6d3
    );
    border: 1px solid #b56c65;
    border-radius: 3px;
    padding: 4px 13px;
    color: #5e1711;
    font-weight: 500;
}
QPushButton.aeroDangerBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #ffe8e6,
        stop:0.48 #f7bdb7,
        stop:0.50 #ea8d84,
        stop:1.00 #f4b6b0
    );
    border: 1px solid #a83328;
}
QPushButton.aeroDangerBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #f5c4be,
        stop:0.50 #e27d72,
        stop:1.00 #eb9e97
    );
    border: 1px solid #8e251b;
    padding-top: 5px;
    padding-bottom: 3px;
}

QLineEdit, QComboBox {
    min-height: 25px;
    background-color: #ffffff;
    border: 1px solid #9bb0c6;
    border-top: 1px solid #7c93ac;
    border-radius: 3px;
    padding: 3px 8px;
    color: #182330;
    selection-background-color: #3399ff;
}
QLineEdit:hover, QComboBox:hover {
    border: 1px solid #5aa2dc;
    border-top: 1px solid #4a8ec9;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #2f7ab5;
    background-color: #ffffff;
}

QComboBox {
    padding-right: 24px;
}
QComboBox:on {
    border: 1px solid #26689e;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid #b5c7d8;
    border-top-right-radius: 2px;
    border-bottom-right-radius: 2px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #f7fafd,
        stop:0.48 #e0ecf7,
        stop:0.50 #c9def0,
        stop:1.00 #e6f1f9
    );
}
QComboBox::drop-down:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #f5faff,
        stop:0.48 #d5ebfd,
        stop:0.50 #b4dcfc,
        stop:1.00 #d8edfe
    );
    border-left: 1px solid #6aa2d2;
}
QComboBox::drop-down:pressed, QComboBox::drop-down:on {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #b8dcf8,
        stop:0.48 #96c9f2,
        stop:0.50 #81baeb,
        stop:1.00 #b2d8f7
    );
    border-left: 1px solid #3c7fb1;
}
QComboBox::down-arrow {
    image: url(__ARROW_DOWN_PATH__);
    width: 9px;
    height: 6px;
}
QComboBox::down-arrow:hover {
    image: url(__ARROW_DOWN_HOVER_PATH__);
}
QComboBox::down-arrow:pressed, QComboBox::down-arrow:on {
    image: url(__ARROW_DOWN_HOVER_PATH__);
    top: 1px;
    left: 1px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #7da2ce;
    border-radius: 3px;
    selection-background-color: #cde6fc;
    selection-color: #10253a;
    outline: none;
    padding: 3px;
}
QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 3px 8px;
    border-radius: 2px;
}
QComboBox QAbstractItemView::item:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #f2f8ff,
        stop:1.00 #dceeff
    );
    color: #0d2844;
}
QComboBox QAbstractItemView::item:selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #eaf4fd,
        stop:0.50 #cde6fc,
        stop:1.00 #b9dcfb
    );
    border: 1px solid #7da2ce;
    color: #0b2238;
}

QCheckBox, QRadioButton {
    spacing: 6px;
    color: #1e2a38;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #7c93ac;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #ffffff,
        stop:1.00 #ebf2f8
    );
}
QCheckBox::indicator {
    border-radius: 2px;
}
QRadioButton::indicator {
    border-radius: 7px;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border: 1px solid #3c7fb1;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #ffffff,
        stop:1.00 #d8ecfc
    );
}
QCheckBox::indicator:pressed, QRadioButton::indicator:pressed {
    border: 1px solid #2c628b;
    background: #c8e0f5;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    border: 1px solid #286494;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #e3f2fd,
        stop:0.50 #90caf9,
        stop:1.00 #64b5f6
    );
}

QTreeWidget, QListWidget {
    background-color: #ffffff;
    border: 1px solid #a3b8ce;
    border-radius: 2px;
    outline: none;
    alternate-background-color: #f8fbfe;
}
QTreeWidget::item, QListWidget::item {
    padding: 5px 6px;
    border: 1px solid transparent;
    border-radius: 2px;
}
QTreeWidget::item:hover, QListWidget::item:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #f2f8ff,
        stop:1.00 #dceeff
    );
    border: 1px solid #b8d6fb;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #eaf4fd,
        stop:0.50 #cde6fc,
        stop:1.00 #b9dcfb
    );
    border: 1px solid #7da2ce;
    color: #10253a;
}

QHeaderView {
    background-color: #edf3f9;
    border: none;
    border-bottom: 1px solid #a6bad0;
}

QHeaderView::section {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #ffffff,
        stop:0.49 #edf3f9,
        stop:0.50 #dfe9f4,
        stop:1.00 #eef4fa
    );
    color: #2c435c;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid #c5d4e3;
    border-bottom: 1px solid #a6bad0;
    font-weight: 600;
}

#InspectorHeader {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #ffffff,
        stop:0.55 #edf5fc,
        stop:1.00 #dceaf7
    );
    border: 1px solid #a3b8ce;
    border-radius: 3px;
}

#SessionDetailBox, #SettingsCard {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #ffffff,
        stop:1.00 #eff5fb
    );
    border: 1px solid #a8bdd2;
    border-radius: 3px;
}

#AeroStatusBar {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #f1f6fc,
        stop:0.50 #dde8f5,
        stop:1.00 #cfe0f2
    );
    border-top: 1px solid #a0b8d1;
}

QScrollBar:vertical {
    background: rgba(225, 235, 245, 0.45);
    width: 10px;
    margin: 0px;
    border: none;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 #edf5fc,
        stop:0.45 #d9e7f5,
        stop:0.55 #c9dcef,
        stop:1.00 #e3f0fa
    );
    border: 1px solid #94b2d1;
    border-radius: 4px;
    min-height: 32px;
    margin: 1px;
}
QScrollBar::handle:vertical:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 #ddf0ff,
        stop:0.50 #bde0fa,
        stop:1.00 #d6ecfd
    );
    border: 1px solid #5193d1;
}
QScrollBar::handle:vertical:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 #9ec7ec,
        stop:0.50 #7eb2dc,
        stop:1.00 #98c2e9
    );
    border: 1px solid #3c7cb5;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    height: 0px;
}

QSplitter {
    background: transparent;
}
QSplitter::handle, QSplitter::handle:horizontal {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 #cad8e6,
        stop:0.50 #eef4fa,
        stop:1.00 #cad8e6
    );
    border-left: 1px solid #b3c5d6;
    border-right: 1px solid #b3c5d6;
    width: 6px;
}
QSplitter::handle:hover, QSplitter::handle:horizontal:hover {
    background: #62a3d8;
    border-left: 1px solid #3c7fb1;
    border-right: 1px solid #3c7fb1;
}

QMenu {
    background-color: #f7fafc;
    border: 1px solid #7da2ce;
    border-radius: 3px;
    padding: 3px;
    color: #1a2a3a;
}
QMenu::item {
    background: transparent;
    padding: 5px 22px 5px 24px;
    border-radius: 2px;
    color: #1a2a3a;
}
QMenu::item:selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #e3f2ff,
        stop:0.50 #b8ddfc,
        stop:1.00 #d8ecfe
    );
    border: 1px solid #4a94d8;
    color: #0c335e;
}
QMenu::item:disabled {
    color: #92a4b8;
    background: transparent;
}
QMenu::separator {
    height: 1px;
    background: #cddbe8;
    margin: 4px 6px;
}
QMenu::icon {
    margin-left: 5px;
}
"""

AERO_OBSIDIAN_QSS = """
* {
    font-family: "Segoe UI", Tahoma, sans-serif;
    font-size: 9pt;
    color: #dce5ef;
}

QDialog {
    background-color: #161a22;
    color: #dce5ef;
}

#InnerWorkspace {
    background-color: #14171d;
    border: 1px solid #283342;
    border-radius: 3px;
}

#AeroCommandBar {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #29303c,
        stop:0.48 #1e242d,
        stop:0.50 #151a22,
        stop:0.85 #1b212a,
        stop:1.00 #232a35
    );
    border-bottom: 1px solid #2d3847;
}

QPushButton.aeroNavBtn {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 5px 12px;
    color: #c4d4e5;
    font-weight: 500;
}
QPushButton.aeroNavBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 rgba(70, 95, 125, 200),
        stop:0.49 rgba(45, 65, 90, 190),
        stop:0.50 rgba(32, 50, 72, 200),
        stop:1.00 rgba(50, 75, 105, 210)
    );
    border: 1px solid #4a6f98;
    color: #ffffff;
}
QPushButton.aeroNavBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #1b2b3d,
        stop:0.49 #132030,
        stop:0.50 #0e1926,
        stop:1.00 #19283a
    );
    border: 1px solid #2b4d73;
    color: #7bc5ff;
    padding-top: 6px;
    padding-bottom: 4px;
}
QPushButton.aeroNavBtn:checked {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #35465c,
        stop:0.49 #223246,
        stop:0.50 #192738,
        stop:1.00 #293d56
    );
    border: 1px solid #4a74a3;
    color: #ffffff;
    font-weight: 600;
}

QPushButton.aeroBtn {
    min-height: 24px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #2a3340,
        stop:0.48 #1f2732,
        stop:0.50 #181f28,
        stop:1.00 #222b37
    );
    border: 1px solid #364455;
    border-radius: 3px;
    padding: 4px 13px;
    color: #d0deee;
}
QPushButton.aeroBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #3c4c60,
        stop:0.48 #2b394b,
        stop:0.50 #212d3c,
        stop:1.00 #324357
    );
    border: 1px solid #507198;
    color: #ffffff;
}
QPushButton.aeroBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #18222e,
        stop:0.50 #121b24,
        stop:1.00 #1e2a39
    );
    border: 1px solid #283e57;
    padding-top: 5px;
    padding-bottom: 3px;
}

QPushButton.aeroDangerBtn {
    min-height: 24px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #451f1c,
        stop:0.48 #341614,
        stop:0.50 #28100e,
        stop:1.00 #381816
    );
    border: 1px solid #6b2d27;
    border-radius: 3px;
    padding: 4px 13px;
    color: #ffb8b2;
    font-weight: 500;
}
QPushButton.aeroDangerBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #592521,
        stop:0.48 #441a17,
        stop:0.50 #331210,
        stop:1.00 #4d1e1a
    );
    border: 1px solid #8e3830;
    color: #ffffff;
}
QPushButton.aeroDangerBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #280d0b,
        stop:0.50 #1c0807,
        stop:1.00 #2e100e
    );
    border: 1px solid #521c17;
    padding-top: 5px;
    padding-bottom: 3px;
}

QLineEdit, QComboBox {
    min-height: 25px;
    background-color: #12161d;
    border: 1px solid #2c3848;
    border-top: 1px solid #242f3d;
    border-radius: 3px;
    padding: 3px 8px;
    color: #e5edf5;
    selection-background-color: #1d5f99;
}
QLineEdit:hover, QComboBox:hover {
    border: 1px solid #3c5e84;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #4a80b8;
    background-color: #141922;
}

QComboBox {
    padding-right: 24px;
}
QComboBox:on {
    border: 1px solid #4a80b8;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid #2c3848;
    border-top-right-radius: 2px;
    border-bottom-right-radius: 2px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #242c38,
        stop:0.48 #1b212b,
        stop:0.50 #151a22,
        stop:1.00 #1e2531
    );
}
QComboBox::drop-down:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #303c4c,
        stop:0.48 #232d3a,
        stop:0.50 #1b2430,
        stop:1.00 #293544
    );
    border-left: 1px solid #456282;
}
QComboBox::drop-down:pressed, QComboBox::drop-down:on {
    background: #151d27;
    border-left: 1px solid #456282;
}
QComboBox::down-arrow {
    image: url(__ARROW_DOWN_PATH__);
    width: 9px;
    height: 6px;
}
QComboBox::down-arrow:hover {
    image: url(__ARROW_DOWN_HOVER_PATH__);
}
QComboBox::down-arrow:pressed, QComboBox::down-arrow:on {
    image: url(__ARROW_DOWN_HOVER_PATH__);
    top: 1px;
    left: 1px;
}

QComboBox QAbstractItemView {
    background-color: #141820;
    border: 1px solid #36485e;
    border-radius: 3px;
    selection-background-color: #1d3e62;
    selection-color: #ffffff;
    outline: none;
    padding: 3px;
}
QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 3px 8px;
    border-radius: 2px;
    color: #dce5ef;
}
QComboBox QAbstractItemView::item:hover {
    background: #1b2838;
    color: #6bc2ff;
}
QComboBox QAbstractItemView::item:selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #25476d,
        stop:0.50 #1b3756,
        stop:1.00 #142d48
    );
    border: 1px solid #3d6896;
    color: #ffffff;
}

QCheckBox, QRadioButton {
    spacing: 6px;
    color: #dce5ef;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #3a4b60;
    background: #13171e;
}
QCheckBox::indicator {
    border-radius: 2px;
}
QRadioButton::indicator {
    border-radius: 7px;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border: 1px solid #4f7cae;
    background: #19202a;
}
QCheckBox::indicator:pressed, QRadioButton::indicator:pressed {
    border: 1px solid #335984;
    background: #0f141a;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    border: 1px solid #4a8dd1;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #3580ca,
        stop:0.50 #1d5fa0,
        stop:1.00 #154b80
    );
}

QTreeWidget, QListWidget {
    background-color: #12151b;
    border: 1px solid #283444;
    border-radius: 2px;
    outline: none;
    alternate-background-color: #161a22;
    color: #dce5ef;
}
QTreeWidget::item, QListWidget::item {
    padding: 5px 6px;
    border: 1px solid transparent;
    border-radius: 2px;
}
QTreeWidget::item:hover, QListWidget::item:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #1e2836,
        stop:1.00 #17212d
    );
    border: 1px solid #324e70;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #204165,
        stop:0.50 #163250,
        stop:1.00 #112740
    );
    border: 1px solid #36608e;
    color: #ffffff;
}

QHeaderView {
    background-color: #161b23;
    border: none;
    border-bottom: 1px solid #232b36;
}

QHeaderView::section {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #252d3a,
        stop:0.49 #1c222c,
        stop:0.50 #161b23,
        stop:1.00 #1e2531
    );
    color: #d8e6f5;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    border-bottom: 1px solid #232b36;
    font-weight: 600;
}

#InspectorHeader {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #242c38,
        stop:0.55 #1a202a,
        stop:1.00 #141921
    );
    border: 1px solid #2c3848;
    border-radius: 3px;
}

#SessionDetailBox, #SettingsCard {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #1d232c,
        stop:1.00 #151921
    );
    border: 1px solid #293444;
    border-radius: 3px;
}

#AeroStatusBar {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #1e242d,
        stop:0.50 #161b23,
        stop:1.00 #11151b
    );
    border-top: 1px solid #283340;
}

QScrollBar:vertical {
    background: rgba(14, 18, 24, 0.45);
    width: 10px;
    margin: 0px;
    border: none;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 #2d3b4d,
        stop:0.45 #202c3a,
        stop:0.55 #18222e,
        stop:1.00 #283646
    );
    border: 1px solid rgba(85, 120, 160, 0.40);
    border-radius: 4px;
    min-height: 32px;
    margin: 1px;
}
QScrollBar::handle:vertical:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 #456d9a,
        stop:0.45 #30547c,
        stop:0.55 #234468,
        stop:1.00 #3e638d
    );
    border: 1px solid #5d98d6;
}
QScrollBar::handle:vertical:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 #1e3a59,
        stop:0.50 #142a42,
        stop:1.00 #1b3552
    );
    border: 1px solid #3d75ab;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    height: 0px;
}

QSplitter {
    background: transparent;
}
QSplitter::handle, QSplitter::handle:horizontal {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 #151920,
        stop:0.50 #242c38,
        stop:1.00 #151920
    );
    border-left: 1px solid #11141a;
    border-right: 1px solid #11141a;
    width: 6px;
}
QSplitter::handle:hover, QSplitter::handle:horizontal:hover {
    background: #344862;
    border-left: 1px solid #1f2f42;
    border-right: 1px solid #1f2f42;
}

QMenu {
    background-color: #161a22;
    border: 1px solid #2f3e52;
    border-radius: 3px;
    padding: 3px;
    color: #dce5ef;
}
QMenu::item {
    background: transparent;
    padding: 5px 22px 5px 24px;
    border-radius: 2px;
    color: #dce5ef;
}
QMenu::item:selected {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0.00 #2a4362,
        stop:0.50 #1a3250,
        stop:1.00 #12253d
    );
    border: 1px solid #3d6896;
    color: #ffffff;
}
QMenu::item:disabled {
    color: #55677d;
    background: transparent;
}
QMenu::separator {
    height: 1px;
    background: #283546;
    margin: 4px 6px;
}
QMenu::icon {
    margin-left: 5px;
}

#BtnStatusBarGithub:hover {
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid #4a6a8c;
}
#BtnStatusBarGithub QLabel {
    color: #8da4bc;
}
#BtnStatusBarGithub:hover QLabel {
    color: #6bc2ff;
}
"""

AERO_QSS = (
    AERO_QSS
    .replace("__ARROW_DOWN_PATH__", ARROW_DOWN_PATH.resolve().as_posix())
    .replace("__ARROW_DOWN_HOVER_PATH__", ARROW_DOWN_HOVER_PATH.resolve().as_posix())
)

AERO_OBSIDIAN_QSS = (
    AERO_OBSIDIAN_QSS
    .replace("__ARROW_DOWN_PATH__", ARROW_DOWN_PATH.resolve().as_posix())
    .replace("__ARROW_DOWN_HOVER_PATH__", ARROW_DOWN_HOVER_PATH.resolve().as_posix())
)


class AeroLinkButton(QPushButton):
    def sizeHint(self) -> QSize:
        if self.layout():
            sh = self.layout().sizeHint()
            return QSize(sh.width() + 14, 22)
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()



# aero min/close btns
class AeroCaptionButton(QPushButton):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._hovered = False
        self._pressed = False
        self.setFixedSize(44 if kind == "close" else 30, 21)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFlat(True)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.0, self.width() - 1.0, self.height() - 0.5)

        path = QPainterPath()
        r = 3.5
        if self.kind == "minimize":
            path.moveTo(rect.left(), rect.top())
            path.lineTo(rect.right(), rect.top())
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left() + r, rect.bottom())
            path.quadTo(rect.left(), rect.bottom(), rect.left(), rect.bottom() - r)
            path.closeSubpath()
        else:
            path.moveTo(rect.left(), rect.top())
            path.lineTo(rect.right(), rect.top())
            path.lineTo(rect.right(), rect.bottom() - r)
            path.quadTo(rect.right(), rect.bottom(), rect.right() - r, rect.bottom())
            path.lineTo(rect.left(), rect.bottom())
            path.closeSubpath()

        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        if self.kind == "close":
            if self._pressed:
                grad.setColorAt(0.0, QColor(200, 95, 85, 240))
                grad.setColorAt(0.49, QColor(168, 45, 35, 245))
                grad.setColorAt(0.50, QColor(135, 20, 12, 250))
                grad.setColorAt(1.0, QColor(175, 58, 45, 240))
            elif self._hovered:
                grad.setColorAt(0.0, QColor(255, 165, 152, 250))
                grad.setColorAt(0.49, QColor(235, 82, 68, 250))
                grad.setColorAt(0.50, QColor(205, 35, 22, 255))
                grad.setColorAt(1.0, QColor(235, 110, 88, 245))
            else:
                grad.setColorAt(0.0, QColor(225, 138, 128, 225))
                grad.setColorAt(0.49, QColor(198, 86, 76, 225))
                grad.setColorAt(0.50, QColor(172, 48, 38, 235))
                grad.setColorAt(1.0, QColor(198, 92, 80, 225))
        else:
            if self._pressed:
                grad.setColorAt(0.0, QColor(150, 195, 235, 230))
                grad.setColorAt(0.50, QColor(85, 145, 205, 235))
                grad.setColorAt(1.0, QColor(125, 185, 235, 230))
            elif self._hovered:
                grad.setColorAt(0.0, QColor(220, 242, 255, 235))
                grad.setColorAt(0.49, QColor(145, 205, 248, 235))
                grad.setColorAt(0.50, QColor(95, 175, 238, 240))
                grad.setColorAt(1.0, QColor(175, 225, 255, 235))
            else:
                grad.setColorAt(0.0, QColor(225, 240, 252, 165))
                grad.setColorAt(0.49, QColor(178, 206, 230, 155))
                grad.setColorAt(0.50, QColor(135, 172, 204, 165))
                grad.setColorAt(1.0, QColor(170, 204, 230, 160))

        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(QColor(42, 68, 94, 205), 1.0))
        p.drawPath(path)

        p.setPen(QPen(QColor(255, 255, 255, 140), 1.0))
        p.drawLine(QPointF(rect.left() + 1.5, rect.top() + 1.0), QPointF(rect.right() - 1.5, rect.top() + 1.0))

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        if self.kind == "minimize":
            p.setPen(QPen(QColor(20, 35, 50, 190), 2.2))
            p.drawLine(QPointF(cx - 4.5, cy + 4.0), QPointF(cx + 4.5, cy + 4.0))
            p.setPen(QPen(QColor(255, 255, 255, 245), 2.0))
            p.drawLine(QPointF(cx - 4.5, cy + 3.0), QPointF(cx + 4.5, cy + 3.0))
        else:
            for dy, col, w in ((1.0, QColor(65, 15, 10, 190), 2.2), (0.0, QColor(255, 255, 255, 250), 1.8)):
                p.setPen(QPen(col, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(cx - 4.0, cy - 3.5 + dy), QPointF(cx + 4.0, cy + 4.5 + dy))
                p.drawLine(QPointF(cx + 4.0, cy - 3.5 + dy), QPointF(cx - 4.0, cy + 4.5 + dy))


# aero orb
class AeroOrb(QWidget):
    def __init__(self, active: bool = True, size: int = 12, parent=None):
        super().__init__(parent)
        self.active = active
        self.setFixedSize(size, size)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)

        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        if self.active:
            grad.setColorAt(0.0, QColor("#b7f7c2"))
            grad.setColorAt(0.45, QColor("#39c458"))
            grad.setColorAt(1.0, QColor("#15852f"))
            border = QColor("#126b26")
        else:
            grad.setColorAt(0.0, QColor("#eef3f8"))
            grad.setColorAt(0.5, QColor("#b8c6d4"))
            grad.setColorAt(1.0, QColor("#8ea0b2"))
            border = QColor("#6d7f91")

        p.setBrush(QBrush(grad))
        p.setPen(QPen(border, 1.0))
        p.drawEllipse(r)

        gloss = QRectF(r.left() + r.width() * 0.22, r.top() + 1.2, r.width() * 0.56, r.height() * 0.36)
        p.setBrush(QColor(255, 255, 255, 175))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(gloss)


def get_app_icon() -> QIcon:
    if APP_ICO_PATH.exists():
        return QIcon(str(APP_ICO_PATH))
    if APP_ICON_PATH.exists():
        return QIcon(str(APP_ICON_PATH))
    return QIcon(AeroClockEmblem.render_pixmap(32))


def get_search_icon() -> QIcon:
    if SEARCH_SVG_PATH.exists():
        return QIcon(str(SEARCH_SVG_PATH))
    pix = QPixmap(18, 18)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(QPen(QColor("#4d6f8f"), 2.0))
    p.setBrush(QColor(230, 243, 255, 120))
    p.drawEllipse(QRectF(2.0, 2.0, 9.5, 9.5))
    p.setPen(QPen(QColor("#314e6b"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(9.5, 9.5), QPointF(15.5, 15.5))
    p.end()
    return QIcon(pix)


def get_github_icon() -> QIcon:
    if GITHUB_SVG_PATH.exists():
        return QIcon(str(GITHUB_SVG_PATH))
    pix = QPixmap(16, 16)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#2d4b68"))
    p.drawEllipse(QRectF(1, 1, 14, 14))
    p.end()
    return QIcon(pix)


def get_sort_time_icon() -> QIcon:
    if SORT_TIME_PATH.exists():
        return QIcon(str(SORT_TIME_PATH))
    return QIcon()


def get_sort_recent_icon() -> QIcon:
    if SORT_RECENT_PATH.exists():
        return QIcon(str(SORT_RECENT_PATH))
    return QIcon()


def get_sort_alpha_icon() -> QIcon:
    if SORT_ALPHA_PATH.exists():
        return QIcon(str(SORT_ALPHA_PATH))
    return QIcon()


def get_focus_icon(active: bool = True) -> QIcon:
    target = FOCUS_SVG_PATH if active else FOCUS_IDLE_SVG_PATH
    if target.exists():
        return QIcon(str(target))
    return QIcon()


def get_theme_icon(theme: str = "light") -> QIcon:
    target = THEME_DARK_SVG_PATH if theme == "light" else THEME_LIGHT_SVG_PATH
    if target.exists():
        return QIcon(str(target))
    return QIcon()


# aero clock emblem
class AeroClockEmblem(QWidget):
    def __init__(self, size: int = 20, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    @staticmethod
    def render_pixmap(size: int = 32) -> QPixmap:
        if APP_ICON_PATH.exists():
            pix = QPixmap(str(APP_ICON_PATH))
            if not pix.isNull():
                return pix.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        margin = size * 0.08
        r = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0.0, QColor("#e3f4ff"))
        grad.setColorAt(0.45, QColor("#5ba7e6"))
        grad.setColorAt(0.55, QColor("#2975bd"))
        grad.setColorAt(1.0, QColor("#67bdf5"))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#1a4673"), max(1.0, size * 0.06)))
        p.drawEllipse(r)

        inner = r.adjusted(size * 0.14, size * 0.14, -size * 0.14, -size * 0.14)
        p.setBrush(QColor(255, 255, 255, 235))
        p.setPen(QPen(QColor("#33689c"), 0.8))
        p.drawEllipse(inner)

        c = inner.center()
        p.setPen(QPen(QColor("#143454"), max(1.2, size * 0.08), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(c, QPointF(c.x(), inner.top() + inner.height() * 0.2))
        p.drawLine(c, QPointF(inner.right() - inner.width() * 0.22, c.y() + inner.height() * 0.12))

        gloss = QRectF(r.left() + r.width() * 0.18, r.top() + r.height() * 0.08, r.width() * 0.64, r.height() * 0.36)
        p.setBrush(QColor(255, 255, 255, 130))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(gloss)
        p.end()
        return pix

    def paintEvent(self, _event):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.render_pixmap(self.width()))


class AeroTitleBar(QWidget):
    def __init__(self, parent_window: QWidget, title_text: str):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.title_text = title_text
        self._drag_pos: Optional[QPoint] = None
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(6)

        self.emblem = AeroClockEmblem(18)
        layout.addWidget(self.emblem, 0, Qt.AlignmentFlag.AlignVCenter)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(spacer)

        btn_wrap = QWidget()
        btn_layout = QHBoxLayout(btn_wrap)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(0)

        self.btn_min = AeroCaptionButton("minimize")
        self.btn_close = AeroCaptionButton("close")
        btn_layout.addWidget(self.btn_min, 0, Qt.AlignmentFlag.AlignTop)
        btn_layout.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignTop)

        layout.addWidget(btn_wrap, 0, Qt.AlignmentFlag.AlignTop)

    def set_title(self, new_text: str):
        self.title_text = new_text
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))

        text_rect = QRect(36, 0, self.width() - 125, 32)
        is_dark = getattr(self.parent_window, "current_theme", "light") == "dark"
        if is_dark:
            p.setPen(QColor(0, 0, 0, 200))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (0, 2)):
                p.drawText(
                    text_rect.translated(dx, dy),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    self.title_text,
                )
            p.setPen(QColor(245, 250, 255))
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.title_text)
        else:
            p.setPen(QColor(255, 255, 255, 145))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)):
                p.drawText(
                    text_rect.translated(dx, dy),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    self.title_text,
                )
            p.setPen(QColor(15, 32, 50))
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.title_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.parent_window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()


class RunningProcessDialog(QDialog):
    def __init__(self, parent=None, lang: str = "en"):
        super().__init__(parent)
        self.lang = lang
        t = TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])
        self.setWindowTitle(t["dlg_proc_title"])
        self.setFixedSize(440, 420)
        self.selected_exe: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel(t["dlg_proc_label"]))

        self.search = QLineEdit()
        self.search.setPlaceholderText(t["dlg_proc_search"])
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._accept_selected)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton(t["btn_select"])
        btn_ok.setProperty("class", "aeroBtn")
        btn_ok.clicked.connect(self._accept_selected)
        btn_cancel = QPushButton(t["btn_cancel"])
        btn_cancel.setProperty("class", "aeroBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        self._all_names: List[str] = []
        self._load_processes()

    def _load_processes(self):
        seen = set()
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info["name"]
                if name and name.lower().endswith(".exe"):
                    seen.add(name)
            except Exception:
                continue
        self._all_names = sorted(seen, key=str.lower)
        self._filter("")

    def _filter(self, text: str):
        q = text.strip().lower()
        self.list_widget.clear()
        for name in self._all_names:
            if not q or q in name.lower():
                self.list_widget.addItem(name)

    def _accept_selected(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_exe = item.text()
            self.accept()


# modal about dialog
class AboutDialog(QDialog):
    def __init__(self, parent=None, lang: str = "en", theme: str = "light"):
        super().__init__(parent)
        self.lang = lang
        self.theme = theme
        t = TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])
        self.setWindowTitle(t.get("about_title", "About Aero Chrono"))
        self.setWindowIcon(get_app_icon())
        self.setFixedSize(500, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        is_dark = (self.theme == "dark")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(11)

        card = QFrame()
        card.setObjectName("SettingsCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(14)

        logo_lbl = QLabel()
        logo_pix = AeroClockEmblem.render_pixmap(48)
        logo_lbl.setPixmap(logo_pix)
        logo_lbl.setFixedSize(48, 48)
        card_layout.addWidget(logo_lbl)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        title_color = "#e2efff" if is_dark else "#102d4b"
        ver_color = "#7cb9ec" if is_dark else "#557b9e"
        sub_color = "#9bb7d4" if is_dark else "#496a8a"
        title_lbl = QLabel(f"<b>Aero Chrono</b> <span style='color:{ver_color}; font-size:9pt;'>v{APP_VERSION}</span>")
        title_lbl.setStyleSheet(f"font-size: 13.5pt; color: {title_color};")
        sub_lbl = QLabel(t.get("app_subtitle", "App Time Tracker"))
        sub_lbl.setStyleSheet(f"color: {sub_color}; font-size: 9.5pt;")
        info_layout.addWidget(title_lbl)
        info_layout.addWidget(sub_lbl)
        card_layout.addLayout(info_layout)
        card_layout.addStretch()
        layout.addWidget(card)

        desc_lbl = QLabel(t.get("about_desc", ""))
        desc_lbl.setWordWrap(True)
        desc_color = "#d2e3f5" if is_dark else "#243b52"
        desc_lbl.setStyleSheet(f"color: {desc_color}; font-size: 9.5pt; line-height: 140%;")
        layout.addWidget(desc_lbl)

        link_card = QFrame()
        link_card.setObjectName("AboutLinkCard")
        if is_dark:
            link_card.setStyleSheet("""
                #AboutLinkCard {
                    background: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0.00 #202732,
                        stop:1.00 #161c24
                    );
                    border: 1px solid #2d3b4b;
                    border-radius: 3px;
                }
                #AboutLinkCard QLabel {
                    border: none;
                    background: transparent;
                    outline: none;
                }
            """)
        else:
            link_card.setStyleSheet("""
                #AboutLinkCard {
                    background: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0.00 #f7fafd,
                        stop:1.00 #edf4fb
                    );
                    border: 1px solid #b8cde0;
                    border-radius: 3px;
                }
                #AboutLinkCard QLabel {
                    border: none;
                    background: transparent;
                    outline: none;
                }
            """)
        link_layout = QHBoxLayout(link_card)
        link_layout.setContentsMargins(10, 6, 10, 6)
        link_layout.setSpacing(8)

        gh_icon_lbl = QLabel()
        gh_icon_pix = get_github_icon().pixmap(18, 18)
        gh_icon_lbl.setPixmap(gh_icon_pix)
        gh_icon_lbl.setFixedSize(18, 18)
        gh_icon_lbl.setStyleSheet("border: none; background: transparent;")
        link_layout.addWidget(gh_icon_lbl)

        link_a_color = "#6bc2ff" if is_dark else "#0e65c0"
        dev_text_color = "#c2d6ea" if is_dark else "#26425e"
        dev_lbl = QLabel(
            f"{t.get('about_dev', 'Developer:')} <b>rwynx</b>  •  "
            f"<a href='https://github.com/rwynx' style='color:{link_a_color}; text-decoration:none; font-weight:600;'>"
            "github.com/rwynx</a>"
        )
        dev_lbl.setOpenExternalLinks(True)
        dev_lbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        dev_lbl.setStyleSheet(f"border: none; background: transparent; color: {dev_text_color}; font-size: 9pt;")
        link_layout.addWidget(dev_lbl)
        link_layout.addStretch()
        layout.addWidget(link_card)

        disc_lbl = QLabel(t.get("about_disclosure", ""))
        disc_lbl.setWordWrap(True)
        disc_color = "#8ea8c4" if is_dark else "#556c82"
        disc_lbl.setStyleSheet(f"color: {disc_color}; font-size: 8.5pt; line-height: 135%;")
        layout.addWidget(disc_lbl)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton(t.get("about_close", "Close"))
        btn_close.setProperty("class", "aeroBtn")
        btn_close.setFixedWidth(85)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)


class AeroChronoWindow(QWidget):
    def __init__(self, db: Database, config: ConfigManager, engine: TrackerEngine, icons: IconManager):
        super().__init__()
        self.db = db
        self.config = config
        self.engine = engine
        self.icons = icons
        self.lang = self.config.data.get("language", "en")
        self.current_theme = self.config.data.get("theme", "light")

        self._selected_app_key: Optional[str] = None
        self._selected_date_str: Optional[str] = None
        self._apps_cache: Dict[str, dict] = {}
        self._really_quit = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(get_app_icon())

        # Enable native taskbar click-to-minimize on Windows and set explicit taskbar icon
        try:
            hwnd = int(self.winId())
            GWL_STYLE = -16
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            user32.SetWindowLongW(hwnd, GWL_STYLE, style | 0x00020000 | 0x00080000)

            if APP_ICO_PATH.exists():
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x0010
                WM_SETICON = 0x0080
                ICON_SMALL = 0
                ICON_BIG = 1
                hicon_big = user32.LoadImageW(0, str(APP_ICO_PATH), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
                hicon_small = user32.LoadImageW(0, str(APP_ICO_PATH), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                if hicon_big:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                if hicon_small:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
        except Exception:
            pass

        self._build_ui()
        self._setup_tray()
        self.apply_size_preset(self.config.data.get("size_preset", "auto"), center=True)

        self.engine.install_foreground_hook(self._on_instant_app_detected)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._on_poll_tick)
        self.poll_timer.start(POLL_INTERVAL_MS)

        self.engine.poll()
        self.refresh_overview()

    def t(self, key: str, **kwargs) -> str:
        dic = TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])
        val = dic.get(key, TRANSLATIONS["en"].get(key, key))
        if isinstance(val, str) and kwargs:
            return val.format(**kwargs)
        return val

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)

        outer_path = QPainterPath()
        outer_path.addRoundedRect(rect, 8.0, 8.0)

        if self.current_theme == "dark":
            base_grad = QLinearGradient(0, 0, 0, self.height())
            base_grad.setColorAt(0.00, QColor(36, 42, 50, 245))
            base_grad.setColorAt(0.14, QColor(24, 28, 35, 242))
            base_grad.setColorAt(0.55, QColor(16, 19, 24, 240))
            base_grad.setColorAt(1.00, QColor(22, 26, 33, 245))
            p.fillPath(outer_path, QBrush(base_grad))

            p.save()
            p.setClipPath(outer_path)
            w, h = float(self.width()), float(self.height())
            stripes = [
                ([(w * 0.08, 0), (w * 0.24, 0), (w * 0.02, h * 0.45), (-w * 0.10, h * 0.45)], 16),
                ([(w * 0.28, 0), (w * 0.35, 0), (w * 0.12, h * 0.55), (w * 0.05, h * 0.55)], 12),
                ([(w * 0.52, 0), (w * 0.68, 0), (w * 0.36, h), (w * 0.20, h)], 10),
                ([(w * 0.72, 0), (w * 0.77, 0), (w * 0.46, h), (w * 0.41, h)], 8),
            ]
            p.setPen(Qt.PenStyle.NoPen)
            for pts, alpha in stripes:
                p.setBrush(QColor(255, 255, 255, alpha))
                p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))

            top_gloss = QLinearGradient(0, 0, 0, 34)
            top_gloss.setColorAt(0.0, QColor(255, 255, 255, 60))
            top_gloss.setColorAt(0.55, QColor(255, 255, 255, 18))
            top_gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(QRectF(0, 0, w, 34), top_gloss)
            p.restore()

            inner_path = QPainterPath()
            inner_path.addRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), 7.0, 7.0)
            p.setPen(QPen(QColor(255, 255, 255, 45), 1.0))
            p.drawPath(inner_path)

            p.setPen(QPen(QColor(8, 10, 14, 255), 1.0))
            p.drawPath(outer_path)
        else:
            base_grad = QLinearGradient(0, 0, 0, self.height())
            base_grad.setColorAt(0.00, QColor(186, 218, 242, 236))
            base_grad.setColorAt(0.14, QColor(145, 190, 224, 228))
            base_grad.setColorAt(0.55, QColor(122, 168, 206, 222))
            base_grad.setColorAt(1.00, QColor(150, 194, 228, 232))
            p.fillPath(outer_path, QBrush(base_grad))

            p.save()
            p.setClipPath(outer_path)
            w, h = float(self.width()), float(self.height())
            stripes = [
                ([(w * 0.08, 0), (w * 0.24, 0), (w * 0.02, h * 0.45), (-w * 0.10, h * 0.45)], 48),
                ([(w * 0.28, 0), (w * 0.35, 0), (w * 0.12, h * 0.55), (w * 0.05, h * 0.55)], 34),
                ([(w * 0.52, 0), (w * 0.68, 0), (w * 0.36, h), (w * 0.20, h)], 32),
                ([(w * 0.72, 0), (w * 0.77, 0), (w * 0.46, h), (w * 0.41, h)], 24),
            ]
            p.setPen(Qt.PenStyle.NoPen)
            for pts, alpha in stripes:
                p.setBrush(QColor(255, 255, 255, alpha))
                p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))

            top_gloss = QLinearGradient(0, 0, 0, 34)
            top_gloss.setColorAt(0.0, QColor(255, 255, 255, 125))
            top_gloss.setColorAt(0.55, QColor(255, 255, 255, 35))
            top_gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(QRectF(0, 0, w, 34), top_gloss)
            p.restore()

            inner_path = QPainterPath()
            inner_path.addRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), 7.0, 7.0)
            p.setPen(QPen(QColor(255, 255, 255, 185), 1.0))
            p.drawPath(inner_path)

            p.setPen(QPen(QColor(27, 54, 82, 225), 1.0))
            p.drawPath(outer_path)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(7, 2, 7, 7)
        root.setSpacing(0)

        self.title_bar = AeroTitleBar(self, self.t("app_title"))
        self.title_bar.btn_min.clicked.connect(self.showMinimized)
        self.title_bar.btn_close.clicked.connect(self.hide_to_tray)
        root.addWidget(self.title_bar)

        workspace = QFrame()
        workspace.setObjectName("InnerWorkspace")
        ws_layout = QVBoxLayout(workspace)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        ws_layout.setSpacing(0)
        root.addWidget(workspace, 1)

        cmd_bar = QFrame()
        cmd_bar.setObjectName("AeroCommandBar")
        cmd_bar.setFixedHeight(38)
        cmd_layout = QHBoxLayout(cmd_bar)
        cmd_layout.setContentsMargins(8, 4, 8, 4)
        cmd_layout.setSpacing(4)

        self.btn_nav_overview = QPushButton(self.t("nav_overview"))
        self.btn_nav_filters = QPushButton(self.t("nav_filters"))
        self.btn_nav_settings = QPushButton(self.t("nav_settings"))
        for idx, btn in enumerate((self.btn_nav_overview, self.btn_nav_filters, self.btn_nav_settings)):
            btn.setProperty("class", "aeroNavBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, i=idx: self._switch_page(i))
            cmd_layout.addWidget(btn)
        self.btn_nav_overview.setChecked(True)

        cmd_layout.addStretch()

        self.btn_theme_toggle = QPushButton()
        self.btn_theme_toggle.setProperty("class", "aeroNavBtn")
        self.btn_theme_toggle.setIcon(get_theme_icon(self.current_theme))
        self.btn_theme_toggle.setIconSize(QSize(20, 20))
        self.btn_theme_toggle.setToolTip(self.t("theme_tooltip"))
        self.btn_theme_toggle.setFixedSize(38, 28)
        self.btn_theme_toggle.clicked.connect(self._toggle_theme)
        cmd_layout.addWidget(self.btn_theme_toggle)

        self.btn_about = QPushButton(self.t("nav_about"))
        self.btn_about.setProperty("class", "aeroNavBtn")
        self.btn_about.clicked.connect(self._show_about_dialog)
        cmd_layout.addWidget(self.btn_about)

        self.btn_export = QPushButton(self.t("nav_export"))
        self.btn_export.setProperty("class", "aeroNavBtn")
        self.btn_export.clicked.connect(self._show_export_menu)
        cmd_layout.addWidget(self.btn_export)

        self.btn_reset = QPushButton(self.t("nav_reset"))
        self.btn_reset.setProperty("class", "aeroNavBtn")
        self.btn_reset.clicked.connect(self._confirm_reset_all)
        cmd_layout.addWidget(self.btn_reset)

        ws_layout.addWidget(cmd_bar)

        self.pages = QStackedWidget()
        ws_layout.addWidget(self.pages, 1)

        self.pages.addWidget(self._build_overview_page())
        self.pages.addWidget(self._build_filters_page())
        self.pages.addWidget(self._build_settings_page())

        status_bar = QFrame()
        status_bar.setObjectName("AeroStatusBar")
        status_bar.setFixedHeight(28)
        st_layout = QHBoxLayout(status_bar)
        st_layout.setContentsMargins(10, 0, 10, 0)
        st_layout.setSpacing(8)

        self.status_orb = AeroOrb(active=True, size=11)
        st_layout.addWidget(self.status_orb)

        self.lbl_status_left = QLabel(self.t("status_active"))
        st_layout.addWidget(self.lbl_status_left)
        st_layout.addStretch()

        self.lbl_status_right = QLabel("")
        self.lbl_status_right.setStyleSheet("color: #3a526b;")
        st_layout.addWidget(self.lbl_status_right)

        self.status_sep = QLabel("•")
        self.status_sep.setStyleSheet("color: #7b9bbd;")
        st_layout.addWidget(self.status_sep)

        self.btn_github = AeroLinkButton()
        self.btn_github.setObjectName("BtnStatusBarGithub")
        self.btn_github.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_github.setToolTip("https://github.com/rwynx")
        self.btn_github.setStyleSheet("""
            #BtnStatusBarGithub {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 1px 6px;
                height: 22px;
            }
            #BtnStatusBarGithub:hover {
                background: rgba(255, 255, 255, 0.6);
                border: 1px solid #7da2ce;
            }
            #BtnStatusBarGithub QLabel {
                background: transparent;
                border: none;
                color: #24466b;
                font-weight: 500;
                font-size: 8.5pt;
            }
            #BtnStatusBarGithub:hover QLabel {
                color: #0c5cb2;
            }
        """)
        gh_btn_layout = QHBoxLayout(self.btn_github)
        gh_btn_layout.setContentsMargins(3, 0, 3, 0)
        gh_btn_layout.setSpacing(5)

        gh_icon_lbl = QLabel()
        gh_icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        gh_icon_lbl.setPixmap(get_github_icon().pixmap(13, 13))
        gh_icon_lbl.setFixedSize(13, 13)
        gh_icon_lbl.setStyleSheet("margin-top: 2px; border: none; background: transparent;")

        gh_text_lbl = QLabel("github.com/rwynx")
        gh_text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        gh_text_lbl.setStyleSheet("border: none; background: transparent;")

        gh_btn_layout.addWidget(gh_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        gh_btn_layout.addWidget(gh_text_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/rwynx")))
        st_layout.addWidget(self.btn_github)

        ws_layout.addWidget(status_bar)
        self._apply_theme_colors()

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.overview_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.overview_splitter.setHandleWidth(6)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 2, 0)
        left_layout.setSpacing(6)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.t("search_app_placeholder"))
        self.search_action = self.search_input.addAction(get_search_icon(), QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self.refresh_overview)
        filter_row.addWidget(self.search_input, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.setIconSize(QSize(15, 15))
        self.sort_combo.addItem(get_sort_time_icon(), self.t("sort_total_time"))
        self.sort_combo.addItem(get_sort_recent_icon(), self.t("sort_last_used"))
        self.sort_combo.addItem(get_sort_alpha_icon(), self.t("sort_name"))
        self.sort_combo.currentIndexChanged.connect(self.refresh_overview)
        filter_row.addWidget(self.sort_combo)
        left_layout.addLayout(filter_row)

        self.app_tree = QTreeWidget()
        self.app_tree.setColumnCount(4)
        self.app_tree.setHeaderLabels([
            self.t("col_app"),
            self.t("col_status"),
            self.t("col_all_time"),
            self.t("col_sessions"),
        ])
        self.app_tree.setRootIsDecorated(False)
        self.app_tree.setAlternatingRowColors(True)
        self.app_tree.setUniformRowHeights(True)
        self.app_tree.setIconSize(QSize(22, 22))
        self.app_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.app_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.app_tree.customContextMenuRequested.connect(self._show_app_context_menu)
        self.app_tree.itemSelectionChanged.connect(self._on_app_selected)

        self.app_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hdr = self.app_tree.header()
        hdr.setMinimumSectionSize(45)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.resizeSection(0, 235)
        hdr.resizeSection(1, 135)
        hdr.resizeSection(2, 85)
        hdr.sectionResized.connect(self._enforce_app_tree_columns)

        left_layout.addWidget(self.app_tree, 1)
        self.overview_splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(2, 0, 0, 0)
        right_layout.setSpacing(8)

        self.inspector_header = QFrame()
        self.inspector_header.setObjectName("InspectorHeader")
        ih_layout = QHBoxLayout(self.inspector_header)
        ih_layout.setContentsMargins(10, 10, 10, 10)
        ih_layout.setSpacing(10)

        self.lbl_app_icon = QLabel()
        self.lbl_app_icon.setFixedSize(44, 44)
        self.lbl_app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ih_layout.addWidget(self.lbl_app_icon)

        meta_col = QVBoxLayout()
        meta_col.setSpacing(2)
        self.lbl_app_title = QLabel(self.t("inspector_empty_title"))
        self.lbl_app_title.setStyleSheet("font-size: 12pt; font-weight: 600; color: #122d4a;")
        self.lbl_app_sub = QLabel(self.t("inspector_empty_sub"))
        self.lbl_app_sub.setStyleSheet("color: #49617a;")
        self.lbl_app_totals = QLabel("")
        self.lbl_app_totals.setStyleSheet("font-weight: 600; color: #1e4d7a;")
        meta_col.addWidget(self.lbl_app_title)
        meta_col.addWidget(self.lbl_app_sub)
        meta_col.addWidget(self.lbl_app_totals)
        ih_layout.addLayout(meta_col, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        self.btn_rename_app = QPushButton(self.t("btn_rename"))
        self.btn_rename_app.setProperty("class", "aeroBtn")
        self.btn_rename_app.setEnabled(False)
        self.btn_rename_app.clicked.connect(self._rename_selected_app)

        self.btn_exclude_app = QPushButton(self.t("btn_exclude"))
        self.btn_exclude_app.setProperty("class", "aeroBtn")
        self.btn_exclude_app.setEnabled(False)
        self.btn_exclude_app.clicked.connect(self._exclude_selected_app)

        btn_col.addWidget(self.btn_rename_app)
        btn_col.addWidget(self.btn_exclude_app)
        ih_layout.addLayout(btn_col)

        right_layout.addWidget(self.inspector_header)

        self.lbl_days = QLabel(self.t("lbl_daily_usage"))
        self.lbl_days.setStyleSheet("font-weight: 600; color: #1f3c5c;")
        right_layout.addWidget(self.lbl_days)

        self.days_tree = QTreeWidget()
        self.days_tree.setColumnCount(3)
        self.days_tree.setHeaderLabels([
            self.t("col_date"),
            self.t("col_launches"),
            self.t("col_day_total"),
        ])
        self.days_tree.setRootIsDecorated(False)
        self.days_tree.setAlternatingRowColors(True)
        self.days_tree.itemSelectionChanged.connect(self._on_day_selected)
        self.days_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        dh = self.days_tree.header()
        dh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        dh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        dh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        dh.resizeSection(0, 110)
        dh.resizeSection(1, 80)
        right_layout.addWidget(self.days_tree, 4)

        self.lbl_sessions_title = QLabel(self.t("lbl_sessions_title"))
        self.lbl_sessions_title.setStyleSheet("font-weight: 600; color: #1f3c5c;")
        right_layout.addWidget(self.lbl_sessions_title)

        self.sessions_tree = QTreeWidget()
        self.sessions_tree.setColumnCount(4)
        self.sessions_tree.setHeaderLabels([
            self.t("col_session_idx"),
            self.t("col_time_range"),
            self.t("col_duration"),
            self.t("col_pid"),
        ])
        self.sessions_tree.setRootIsDecorated(False)
        self.sessions_tree.setAlternatingRowColors(True)
        self.sessions_tree.itemSelectionChanged.connect(self._on_session_selected)
        self.sessions_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sh = self.sessions_tree.header()
        sh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        sh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        sh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        sh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        sh.resizeSection(0, 36)
        sh.resizeSection(1, 115)
        sh.resizeSection(2, 80)
        right_layout.addWidget(self.sessions_tree, 5)

        detail_box = QFrame()
        detail_box.setObjectName("SessionDetailBox")
        db_layout = QVBoxLayout(detail_box)
        db_layout.setContentsMargins(9, 7, 9, 7)
        db_layout.setSpacing(2)
        self.lbl_session_detail = QLabel(self.t("detail_empty"))
        self.lbl_session_detail.setWordWrap(True)
        self.lbl_session_detail.setStyleSheet("color: #2b4159;")
        db_layout.addWidget(self.lbl_session_detail)
        right_layout.addWidget(detail_box)

        self.overview_splitter.addWidget(right_panel)
        layout.addWidget(self.overview_splitter, 1)
        return page

    def _build_filters_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        mode_card = QFrame()
        mode_card.setObjectName("SettingsCard")
        mc_layout = QVBoxLayout(mode_card)
        mc_layout.setContentsMargins(12, 10, 12, 10)
        mc_layout.setSpacing(6)

        self.lbl_filter_mode_title = QLabel(self.t("mode_title"))
        self.lbl_filter_mode_title.setStyleSheet("font-weight: 600; font-size: 10pt; color: #163659;")
        mc_layout.addWidget(self.lbl_filter_mode_title)

        self.radio_exclude_mode = QRadioButton(self.t("mode_exclude"))
        self.radio_include_mode = QRadioButton(self.t("mode_include"))
        if self.config.data.get("filter_mode") == "include_only":
            self.radio_include_mode.setChecked(True)
        else:
            self.radio_exclude_mode.setChecked(True)
        self.radio_exclude_mode.toggled.connect(self._on_filter_mode_changed)

        self.chk_auto_win_junk = QCheckBox(self.t("chk_auto_win_junk"))
        self.chk_auto_win_junk.setChecked(self.config.data.get("auto_filter_windows_junk", True))
        self.chk_auto_win_junk.toggled.connect(self._on_auto_win_junk_toggled)

        mc_layout.addWidget(self.radio_exclude_mode)
        mc_layout.addWidget(self.radio_include_mode)
        mc_layout.addWidget(self.chk_auto_win_junk)
        layout.addWidget(mode_card)

        cols = QHBoxLayout()
        cols.setSpacing(10)
        cols.addWidget(self._create_filter_list_panel("include"), 1)
        cols.addWidget(self._create_filter_list_panel("exclude"), 1)
        cols.addWidget(self._create_filter_list_panel("focus"), 1)

        layout.addLayout(cols, 1)
        self._refresh_filter_lists()
        return page

    def _create_filter_list_panel(self, kind: str) -> QFrame:
        card = QFrame()
        card.setObjectName("SettingsCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)

        if kind == "include":
            title = self.t("include_panel_title")
            desc = self.t("include_panel_desc")
        elif kind == "exclude":
            title = self.t("exclude_panel_title")
            desc = self.t("exclude_panel_desc")
        else:
            title = self.t("focus_panel_title")
            desc = self.t("focus_panel_desc")

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-weight: 600; font-size: 10pt; color: #163659;")
        d_lbl = QLabel(desc)
        d_lbl.setStyleSheet("color: #4c6278;")
        d_lbl.setWordWrap(True)
        v.addWidget(t_lbl)
        v.addWidget(d_lbl)

        add_row = QHBoxLayout()
        inp = QLineEdit()
        inp.setPlaceholderText(self.t("filter_placeholder"))
        btn_add = QPushButton(self.t("btn_add"))
        btn_add.setProperty("class", "aeroBtn")
        btn_pick = QPushButton(self.t("btn_pick_running"))
        btn_pick.setProperty("class", "aeroBtn")
        add_row.addWidget(inp, 1)
        add_row.addWidget(btn_add)
        add_row.addWidget(btn_pick)
        v.addLayout(add_row)

        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        v.addWidget(lst, 1)

        btn_rem = QPushButton(self.t("btn_remove_selected"))
        btn_rem.setProperty("class", "aeroBtn")
        v.addWidget(btn_rem, 0, Qt.AlignmentFlag.AlignRight)

        if kind == "include":
            self.include_title_lbl = t_lbl
            self.include_desc_lbl = d_lbl
            self.include_input = inp
            self.include_list_widget = lst
            self.btn_include_add = btn_add
            self.btn_include_pick = btn_pick
            self.btn_include_rem = btn_rem
        elif kind == "exclude":
            self.exclude_title_lbl = t_lbl
            self.exclude_desc_lbl = d_lbl
            self.exclude_input = inp
            self.exclude_list_widget = lst
            self.btn_exclude_add = btn_add
            self.btn_exclude_pick = btn_pick
            self.btn_exclude_rem = btn_rem
        else:
            self.focus_title_lbl = t_lbl
            self.focus_desc_lbl = d_lbl
            self.focus_input = inp
            self.focus_list_widget = lst
            self.btn_focus_add = btn_add
            self.btn_focus_pick = btn_pick
            self.btn_focus_rem = btn_rem

        btn_add.clicked.connect(lambda: self._add_filter_entry(kind, inp.text()))
        inp.returnPressed.connect(lambda: self._add_filter_entry(kind, inp.text()))
        btn_pick.clicked.connect(lambda: self._pick_running_for_filter(kind))
        btn_rem.clicked.connect(lambda: self._remove_selected_filter(kind))

        return card

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(12)

        grid = QHBoxLayout()
        grid.setSpacing(12)

        # Left Column: General & Display
        left_widget = QWidget()
        col_left = QVBoxLayout(left_widget)
        col_left.setContentsMargins(0, 0, 0, 0)
        col_left.setSpacing(10)

        # Card 1: Language & Theme
        card_gen = QFrame()
        card_gen.setObjectName("SettingsCard")
        cg_layout = QVBoxLayout(card_gen)
        cg_layout.setContentsMargins(12, 10, 12, 10)
        cg_layout.setSpacing(5)

        self.lbl_lang_title = QLabel(self.t("sec_language"))
        self.lbl_lang_desc = QLabel(self.t("sec_language_desc"))
        self.lbl_lang_desc.setWordWrap(True)
        cg_layout.addWidget(self.lbl_lang_title)
        cg_layout.addWidget(self.lbl_lang_desc)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Türkçe", "tr")
        lang_idx = self.lang_combo.findData(self.lang)
        if lang_idx >= 0:
            self.lang_combo.setCurrentIndex(lang_idx)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        cg_layout.addWidget(self.lang_combo)

        cg_layout.addSpacing(6)

        self.lbl_theme_title = QLabel(self.t("sec_theme"))
        self.lbl_theme_desc = QLabel(self.t("sec_theme_desc"))
        self.lbl_theme_desc.setWordWrap(True)
        cg_layout.addWidget(self.lbl_theme_title)
        cg_layout.addWidget(self.lbl_theme_desc)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(self.t("theme_light"), "light")
        self.theme_combo.addItem(self.t("theme_dark"), "dark")
        cur_theme = self.config.data.get("theme", "light")
        t_idx = self.theme_combo.findData(cur_theme)
        if t_idx >= 0:
            self.theme_combo.setCurrentIndex(t_idx)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        cg_layout.addWidget(self.theme_combo)

        col_left.addWidget(card_gen)

        # Card 2: Window Sizing
        size_card = QFrame()
        size_card.setObjectName("SettingsCard")
        sc_layout = QVBoxLayout(size_card)
        sc_layout.setContentsMargins(12, 10, 12, 10)
        sc_layout.setSpacing(5)

        self.lbl_size_title = QLabel(self.t("sec_window_size"))
        self.lbl_size_desc = QLabel(self.t("sec_window_size_desc"))
        self.lbl_size_desc.setWordWrap(True)
        sc_layout.addWidget(self.lbl_size_title)
        sc_layout.addWidget(self.lbl_size_desc)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem(self.t("size_auto"), "auto")
        for key, (_, _, lbl_en, lbl_tr) in SIZE_PRESETS.items():
            self.preset_combo.addItem(lbl_en if self.lang == "en" else lbl_tr, key)

        cur_preset = self.config.data.get("size_preset", "auto")
        idx = self.preset_combo.findData(cur_preset)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)

        self.btn_apply_size = QPushButton(self.t("btn_apply_size"))
        self.btn_apply_size.setProperty("class", "aeroBtn")
        self.btn_apply_size.clicked.connect(self._on_apply_size_preset)

        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.btn_apply_size)
        sc_layout.addLayout(preset_row)
        col_left.addWidget(size_card)
        col_left.addStretch()

        # Right Column: Tracking & System & Data
        right_widget = QWidget()
        col_right = QVBoxLayout(right_widget)
        col_right.setContentsMargins(0, 0, 0, 0)
        col_right.setSpacing(10)

        # Card 3: Tracking Mode Card
        track_card = QFrame()
        track_card.setObjectName("SettingsCard")
        trc_layout = QVBoxLayout(track_card)
        trc_layout.setContentsMargins(12, 10, 12, 10)
        trc_layout.setSpacing(5)

        self.lbl_track_mode_title = QLabel(self.t("sec_track_mode"))
        self.lbl_track_mode_desc = QLabel(self.t("sec_track_mode_desc"))
        self.lbl_track_mode_desc.setWordWrap(True)
        trc_layout.addWidget(self.lbl_track_mode_title)
        trc_layout.addWidget(self.lbl_track_mode_desc)

        self.track_mode_combo = QComboBox()
        self.track_mode_combo.addItem(self.t("track_mode_all"), "all")
        self.track_mode_combo.addItem(self.t("track_mode_focused"), "focused")
        cur_mode = self.config.data.get("tracking_mode", "all")
        tm_idx = self.track_mode_combo.findData(cur_mode)
        if tm_idx >= 0:
            self.track_mode_combo.setCurrentIndex(tm_idx)
        self.track_mode_combo.currentIndexChanged.connect(self._on_tracking_mode_changed)
        trc_layout.addWidget(self.track_mode_combo)
        col_right.addWidget(track_card)

        # Card 4: System & Startup Card
        start_card = QFrame()
        start_card.setObjectName("SettingsCard")
        st_layout = QVBoxLayout(start_card)
        st_layout.setContentsMargins(12, 10, 12, 10)
        st_layout.setSpacing(5)

        self.lbl_start_title = QLabel(self.t("sec_startup"))
        st_layout.addWidget(self.lbl_start_title)

        self.chk_autostart = QCheckBox(self.t("chk_autostart"))
        self.chk_autostart.setChecked(is_windows_autostart_enabled())
        self.chk_autostart.toggled.connect(self._on_autostart_toggled)
        st_layout.addWidget(self.chk_autostart)

        self.lbl_tray_info = QLabel(self.t("lbl_tray_info"))
        self.lbl_tray_info.setWordWrap(True)
        st_layout.addWidget(self.lbl_tray_info)
        col_right.addWidget(start_card)

        # Card 5: Data Management & Backup Card
        data_card = QFrame()
        data_card.setObjectName("SettingsCard")
        dc_layout = QVBoxLayout(data_card)
        dc_layout.setContentsMargins(12, 10, 12, 10)
        dc_layout.setSpacing(6)

        self.lbl_data_title = QLabel(self.t("sec_data"))
        self.lbl_db_path = QLabel(self.t("lbl_db_path", path=DB_PATH))
        self.lbl_db_path.setWordWrap(True)
        dc_layout.addWidget(self.lbl_data_title)
        dc_layout.addWidget(self.lbl_db_path)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_open_folder = QPushButton(self.t("btn_open_folder"))
        self.btn_open_folder.setProperty("class", "aeroBtn")
        self.btn_open_folder.clicked.connect(self._open_data_folder)

        self.btn_exp_json = QPushButton(self.t("btn_export_json"))
        self.btn_exp_json.setProperty("class", "aeroBtn")
        self.btn_exp_json.clicked.connect(self._export_json)

        self.btn_exp_csv = QPushButton(self.t("btn_export_csv"))
        self.btn_exp_csv.setProperty("class", "aeroBtn")
        self.btn_exp_csv.clicked.connect(self._export_csv)

        self.btn_wipe = QPushButton(self.t("btn_reset_all"))
        self.btn_wipe.setProperty("class", "aeroDangerBtn")
        self.btn_wipe.clicked.connect(self._confirm_reset_all)

        btn_row.addWidget(self.btn_open_folder)
        btn_row.addWidget(self.btn_exp_json)
        btn_row.addWidget(self.btn_exp_csv)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_wipe)
        dc_layout.addLayout(btn_row)
        col_right.addWidget(data_card)
        col_right.addStretch()

        grid.addWidget(left_widget, 1)
        grid.addWidget(right_widget, 1)
        main_layout.addLayout(grid)
        main_layout.addStretch()

        return page

    def _on_language_changed(self):
        new_lang = self.lang_combo.currentData()
        if new_lang == self.lang:
            return
        self.lang = new_lang
        self.config.data["language"] = new_lang
        self.config.save()
        self._retranslate_ui()

    def _retranslate_ui(self):
        self.title_bar.set_title(self.t("app_title"))
        self.btn_nav_overview.setText(self.t("nav_overview"))
        self.btn_nav_filters.setText(self.t("nav_filters"))
        self.btn_nav_settings.setText(self.t("nav_settings"))
        self.btn_about.setText(self.t("nav_about"))
        self.btn_export.setText(self.t("nav_export"))
        self.btn_reset.setText(self.t("nav_reset"))

        self.search_input.setPlaceholderText(self.t("search_app_placeholder"))

        cur_sort = self.sort_combo.currentIndex()
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        self.sort_combo.addItem(get_sort_time_icon(), self.t("sort_total_time"))
        self.sort_combo.addItem(get_sort_recent_icon(), self.t("sort_last_used"))
        self.sort_combo.addItem(get_sort_alpha_icon(), self.t("sort_name"))
        self.sort_combo.setCurrentIndex(cur_sort if cur_sort >= 0 else 0)
        self.sort_combo.blockSignals(False)

        self.app_tree.setHeaderLabels([
            self.t("col_app"),
            self.t("col_status"),
            self.t("col_all_time"),
            self.t("col_sessions"),
        ])
        self.btn_rename_app.setText(self.t("btn_rename"))
        self.btn_exclude_app.setText(self.t("btn_exclude"))
        self.lbl_days.setText(self.t("lbl_daily_usage"))
        self.days_tree.setHeaderLabels([
            self.t("col_date"),
            self.t("col_launches"),
            self.t("col_day_total"),
        ])
        self.lbl_sessions_title.setText(self.t("lbl_sessions_title"))
        self.sessions_tree.setHeaderLabels([
            self.t("col_session_idx"),
            self.t("col_time_range"),
            self.t("col_duration"),
            self.t("col_pid"),
        ])

        self.lbl_filter_mode_title.setText(self.t("mode_title"))
        self.radio_exclude_mode.setText(self.t("mode_exclude"))
        self.radio_include_mode.setText(self.t("mode_include"))
        self.chk_auto_win_junk.setText(self.t("chk_auto_win_junk"))

        self.include_title_lbl.setText(self.t("include_panel_title"))
        self.include_desc_lbl.setText(self.t("include_panel_desc"))
        self.include_input.setPlaceholderText(self.t("filter_placeholder"))
        self.btn_include_add.setText(self.t("btn_add"))
        self.btn_include_pick.setText(self.t("btn_pick_running"))
        self.btn_include_rem.setText(self.t("btn_remove_selected"))

        self.exclude_title_lbl.setText(self.t("exclude_panel_title"))
        self.exclude_desc_lbl.setText(self.t("exclude_panel_desc"))
        self.exclude_input.setPlaceholderText(self.t("filter_placeholder"))
        self.btn_exclude_add.setText(self.t("btn_add"))
        self.btn_exclude_pick.setText(self.t("btn_pick_running"))
        self.btn_exclude_rem.setText(self.t("btn_remove_selected"))

        self.lbl_lang_title.setText(self.t("sec_language"))
        self.lbl_lang_desc.setText(self.t("sec_language_desc"))
        self.lbl_size_title.setText(self.t("sec_window_size"))
        self.lbl_size_desc.setText(self.t("sec_window_size_desc"))
        self.btn_apply_size.setText(self.t("btn_apply_size"))

        cur_preset = self.preset_combo.currentData()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem(self.t("size_auto"), "auto")
        for key, (_, _, lbl_en, lbl_tr) in SIZE_PRESETS.items():
            self.preset_combo.addItem(lbl_en if self.lang == "en" else lbl_tr, key)
        idx = self.preset_combo.findData(cur_preset)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.blockSignals(False)

        self.lbl_start_title.setText(self.t("sec_startup"))
        self.chk_autostart.setText(self.t("chk_autostart"))
        self.lbl_tray_info.setText(self.t("lbl_tray_info"))
        self.lbl_data_title.setText(self.t("sec_data"))
        self.lbl_db_path.setText(self.t("lbl_db_path", path=DB_PATH))
        if hasattr(self, "btn_open_folder"):
            self.btn_open_folder.setText(self.t("btn_open_folder"))
        self.btn_exp_json.setText(self.t("btn_export_json"))
        self.btn_exp_csv.setText(self.t("btn_export_csv"))
        self.btn_wipe.setText(self.t("btn_reset_all"))

        if hasattr(self, "btn_theme_toggle"):
            self.btn_theme_toggle.setToolTip(self.t("theme_tooltip"))
        if hasattr(self, "focus_title_lbl"):
            self.focus_title_lbl.setText(self.t("focus_panel_title"))
            self.focus_desc_lbl.setText(self.t("focus_panel_desc"))
            self.focus_input.setPlaceholderText(self.t("filter_placeholder"))
            self.btn_focus_add.setText(self.t("btn_add"))
            self.btn_focus_pick.setText(self.t("btn_pick_running"))
            self.btn_focus_rem.setText(self.t("btn_remove_selected"))
        if hasattr(self, "lbl_theme_title"):
            self.lbl_theme_title.setText(self.t("sec_theme"))
            self.lbl_theme_desc.setText(self.t("sec_theme_desc"))
            cur_th = self.theme_combo.currentData()
            self.theme_combo.blockSignals(True)
            self.theme_combo.clear()
            self.theme_combo.addItem(self.t("theme_light"), "light")
            self.theme_combo.addItem(self.t("theme_dark"), "dark")
            th_idx = self.theme_combo.findData(cur_th)
            if th_idx >= 0:
                self.theme_combo.setCurrentIndex(th_idx)
            self.theme_combo.blockSignals(False)
        if hasattr(self, "lbl_track_mode_title"):
            self.lbl_track_mode_title.setText(self.t("sec_track_mode"))
            self.lbl_track_mode_desc.setText(self.t("sec_track_mode_desc"))
            cur_tm = self.track_mode_combo.currentData()
            self.track_mode_combo.blockSignals(True)
            self.track_mode_combo.clear()
            self.track_mode_combo.addItem(self.t("track_mode_all"), "all")
            self.track_mode_combo.addItem(self.t("track_mode_focused"), "focused")
            tm_idx = self.track_mode_combo.findData(cur_tm)
            if tm_idx >= 0:
                self.track_mode_combo.setCurrentIndex(tm_idx)
            self.track_mode_combo.blockSignals(False)

        self.act_open.setText(self.t("tray_open"))
        self.act_quit.setText(self.t("tray_quit"))

        self.apply_size_preset(self.config.data.get("size_preset", "auto"), center=False)
        self._apply_theme_colors()
        self.refresh_overview()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(get_app_icon(), self)
        self.tray.setToolTip(self.t("tray_bg", name=APP_NAME))

        self.tray_menu = QMenu(self)
        self.tray_menu.setStyleSheet(AERO_OBSIDIAN_QSS if self.current_theme == "dark" else AERO_QSS)
        self.act_open = QAction(self.t("tray_open"), self)
        self.act_open.triggered.connect(self.restore_from_tray)
        self.act_quit = QAction(self.t("tray_quit"), self)
        self.act_quit.triggered.connect(self.quit_application)

        self.tray_menu.addAction(self.act_open)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.act_quit)

        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore_from_tray()

    def hide_to_tray(self):
        self.hide()

    def restore_from_tray(self):
        self.refresh_overview()
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_win32_taskbar_minimize()

    def _ensure_win32_taskbar_minimize(self):
        try:
            hwnd = int(self.winId())
            GWL_STYLE = -16
            WS_MINIMIZEBOX = 0x00020000
            WS_SYSMENU = 0x00080000
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            if not (style & WS_MINIMIZEBOX):
                user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_MINIMIZEBOX | WS_SYSMENU)
        except Exception:
            pass

    def quit_application(self):
        self._really_quit = True
        self.poll_timer.stop()
        self.engine.shutdown()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if not self._really_quit:
            event.ignore()
            self.hide_to_tray()
        else:
            event.accept()

    def _detect_auto_preset(self) -> str:
        screen = QApplication.primaryScreen()
        if not screen:
            return "1080p"
        avail = screen.availableGeometry()
        for key in ("2160p", "1440p", "1080p", "compact"):
            w, h, _, _ = SIZE_PRESETS[key]
            if w <= avail.width() * 0.90 and h <= avail.height() * 0.88:
                return key
        return "compact"

    def apply_size_preset(self, preset_key: str, center: bool = False):
        resolved = self._detect_auto_preset() if preset_key == "auto" else preset_key
        if resolved not in SIZE_PRESETS:
            resolved = "1080p"

        w, h, lbl_en, lbl_tr = SIZE_PRESETS[resolved]
        label = lbl_en if self.lang == "en" else lbl_tr
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(w, avail.width() - 24)
            h = min(h, avail.height() - 24)

        self.setFixedSize(w, h)
        left_w = int(w * 0.54)
        self.overview_splitter.setSizes([left_w, int(w * 0.46)])
        if hasattr(self, "app_tree"):
            hdr = self.app_tree.header()
            hdr.blockSignals(True)
            table_w = max(420, left_w - 28)
            if table_w >= 530:
                extra = table_w - 530
                col0 = 235 + int(extra * 0.6)
                col1 = 135
                col2 = 85
            else:
                col0 = max(170, table_w - 125 - 80 - 65)
                col1 = 125
                col2 = 80
            hdr.resizeSection(0, col0)
            hdr.resizeSection(1, col1)
            hdr.resizeSection(2, col2)
            hdr.blockSignals(False)
        self.lbl_status_right.setText(self.t("size_preset_status", label=label, w=w, h=h))

        if center and screen:
            geom = screen.availableGeometry()
            self.move(
                geom.x() + (geom.width() - w) // 2,
                geom.y() + (geom.height() - h) // 2,
            )

    def _on_apply_size_preset(self):
        key = self.preset_combo.currentData()
        self.config.data["size_preset"] = key
        self.config.save()
        self.apply_size_preset(key, center=True)

    def _switch_page(self, index: int):
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate((self.btn_nav_overview, self.btn_nav_filters, self.btn_nav_settings)):
            btn.setChecked(i == index)
        if index == 0:
            self.refresh_overview()

    def _on_instant_app_detected(self):
        if self.isVisible() and self.pages.currentIndex() == 0:
            self.refresh_overview()
        else:
            active_cnt = len(self.engine.active_sessions)
            self.tray.setToolTip(self.t("tray_active", name=APP_NAME, count=active_cnt))

    def _on_poll_tick(self):
        changed = self.engine.poll()
        if self.isVisible() and self.pages.currentIndex() == 0:
            if changed or self.engine.active_sessions:
                self.refresh_overview()
        else:
            active_cnt = len(self.engine.active_sessions)
            self.tray.setToolTip(self.t("tray_active", name=APP_NAME, count=active_cnt))

    def refresh_overview(self):
        apps = self.db.get_all_apps_summary()
        self._apps_cache = {a["app_key"]: a for a in apps}

        for app in apps:
            extra = self.engine.get_live_extra_seconds(app["app_key"])
            app["live_total_sec"] = app["total_sec"] + extra
            app["is_running"] = app["app_key"] in self.engine.active_sessions

        # hide closed apps that are excluded / unallowed
        apps = [
            a for a in apps
            if a["is_running"] or self.engine._is_allowed(a["app_key"], a["exe_path"])
        ]

        q = self.search_input.text().strip().lower()
        if q:
            apps = [a for a in apps if q in a["name"].lower() or q in a["exe_name"].lower()]

        sort_idx = self.sort_combo.currentIndex()
        if sort_idx == 0:
            apps.sort(key=lambda x: (-x["live_total_sec"], x["name"].lower()))
        elif sort_idx == 1:
            apps.sort(key=lambda x: x["last_seen"], reverse=True)
            apps.sort(key=lambda x: not x["is_running"])
        else:
            apps.sort(key=lambda x: x["name"].lower())

        prev_key = self._selected_app_key
        scroll_val = self.app_tree.verticalScrollBar().value()

        self.app_tree.blockSignals(True)
        self.app_tree.clear()

        selected_item = None
        for app in apps:
            item = QTreeWidgetItem()
            item.setIcon(0, self.icons.get_icon(app["app_key"], app["exe_path"]))
            item.setText(0, app["name"])
            item.setToolTip(0, f"{app['exe_name']}\n{app['exe_path'] or self.t('path_unknown')}")

            focus_set = {x.lower() for x in self.config.data.get("focus_only_list", [])}
            is_focus_rule = (app["app_key"] in focus_set) or (self.config.data.get("tracking_mode", "all") == "focused")
            is_dark = (self.current_theme == "dark")

            if app["is_running"]:
                pid = self.engine.active_sessions[app["app_key"]].pid
                if is_focus_rule:
                    item.setIcon(1, get_focus_icon(active=True))
                    item.setText(1, f"{self.t('status_running', pid=pid)} • {self.t('status_focused')}")
                    item.setForeground(1, QBrush(QColor("#42a5f5" if is_dark else "#0d6efd")))
                else:
                    item.setText(1, self.t("status_running", pid=pid))
                    item.setForeground(1, QBrush(QColor("#3ddc84" if is_dark else "#187a2f")))
            elif app["app_key"] in getattr(self.engine, "observed_running_apps", {}):
                pid = self.engine.observed_running_apps[app["app_key"]][0]
                if is_focus_rule:
                    item.setIcon(1, get_focus_icon(active=False))
                    item.setText(1, f"PID {pid} • {self.t('status_idle')}")
                    item.setForeground(1, QBrush(QColor("#8fa6be" if is_dark else "#5c748c")))
                else:
                    item.setText(1, self.t("status_closed"))
                    item.setForeground(1, QBrush(QColor("#8fa6be" if is_dark else "#697b8c")))
            else:
                item.setText(1, self.t("status_closed"))
                item.setForeground(1, QBrush(QColor("#8fa6be" if is_dark else "#697b8c")))

            item.setText(2, format_duration(app["live_total_sec"], lang=self.lang))
            item.setText(3, str(app["session_count"]))
            item.setData(0, Qt.ItemDataRole.UserRole, app["app_key"])

            self.app_tree.addTopLevelItem(item)
            if app["app_key"] == prev_key:
                selected_item = item

        if selected_item:
            self.app_tree.setCurrentItem(selected_item)
        self.app_tree.verticalScrollBar().setValue(scroll_val)
        self.app_tree.blockSignals(False)

        active_cnt = len(self.engine.active_sessions)
        total_cnt = len(apps)
        self.lbl_status_left.setText(self.t("status_summary", total=total_cnt, active=active_cnt))
        self.tray.setToolTip(self.t("tray_active", name=APP_NAME, count=active_cnt))

        if prev_key and any(a["app_key"] == prev_key for a in apps):
            self._update_inspector_header(prev_key)
            self._refresh_days_list(prev_key, keep_selection=True)
        else:
            self._selected_app_key = None
            self._selected_date_str = None
            self.lbl_app_title.setText(self.t("inspector_empty_title"))
            self.lbl_app_sub.setText(self.t("inspector_empty_sub"))
            self.lbl_app_totals.setText("")
            self.lbl_session_detail.setText(self.t("detail_empty"))
            self.lbl_app_icon.clear()
            self.btn_rename_app.setEnabled(False)
            self.btn_exclude_app.setEnabled(False)
            self.days_tree.clear()
            self.sessions_tree.clear()

    def _enforce_app_tree_columns(self, logical_index: int, _old_size: int, new_size: int):
        if getattr(self, "_resizing_columns", False) or logical_index >= 3:
            return
        self._resizing_columns = True
        try:
            hdr = self.app_tree.header()
            avail = self.app_tree.viewport().width()
            if avail <= 0:
                avail = self.app_tree.width()
            if avail <= 100:
                return

            min_widths = {0: 130, 1: 85, 2: 60}
            min_w = min_widths.get(logical_index, 60)
            if new_size < min_w:
                hdr.resizeSection(logical_index, min_w)
                return

            other_sum = sum(hdr.sectionSize(j) for j in range(3) if j != logical_index)
            # Ensure Sessions (col 3) has at least 55px
            max_allowed = avail - other_sum - 55
            if new_size > max_allowed:
                hdr.resizeSection(logical_index, max(min_w, max_allowed))
        finally:
            self._resizing_columns = False

    def _on_app_selected(self):
        items = self.app_tree.selectedItems()
        if not items:
            return
        app_key = items[0].data(0, Qt.ItemDataRole.UserRole)
        self._selected_app_key = app_key
        self._selected_date_str = None
        self._update_inspector_header(app_key)
        self._refresh_days_list(app_key, keep_selection=False)

    def _update_inspector_header(self, app_key: str):
        app = self._apps_cache.get(app_key)
        if not app:
            return
        icon = self.icons.get_icon(app_key, app["exe_path"])
        self.lbl_app_icon.setPixmap(icon.pixmap(40, 40))
        self.lbl_app_title.setText(app["name"])

        live_extra = self.engine.get_live_extra_seconds(app_key)
        total_sec = app["total_sec"] + live_extra
        active_sess = self.engine.active_sessions.get(app_key)
        pid_str = f"  •  PID: {active_sess.pid}" if active_sess else ""

        self.lbl_app_sub.setText(f"{app['exe_name']}{pid_str}")
        self.lbl_app_totals.setText(
            self.t(
                "all_time_totals",
                dur=format_duration(total_sec, include_seconds=True, lang=self.lang),
                count=app["session_count"],
            )
        )
        self.btn_rename_app.setEnabled(True)
        self.btn_exclude_app.setEnabled(True)

    def _refresh_days_list(self, app_key: str, keep_selection: bool):
        days = self.db.get_app_days(app_key)
        active_sess = self.engine.active_sessions.get(app_key)
        live_extra = self.engine.get_live_extra_seconds(app_key)
        scroll_val = self.days_tree.verticalScrollBar().value()

        self.days_tree.blockSignals(True)
        self.days_tree.clear()

        target_item = None
        for d in days:
            sec = d["total_sec"]
            if active_sess and active_sess.date_str == d["date_str"]:
                sec += live_extra
            item = QTreeWidgetItem([
                format_date(d["date_str"], lang=self.lang),
                f"{d['session_count']} {self.t('times_suffix')}",
                format_duration(sec, lang=self.lang),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, d["date_str"])
            self.days_tree.addTopLevelItem(item)
            if keep_selection and d["date_str"] == self._selected_date_str:
                target_item = item

        if target_item is None and self.days_tree.topLevelItemCount() > 0:
            target_item = self.days_tree.topLevelItem(0)

        if target_item:
            self.days_tree.setCurrentItem(target_item)
            self._selected_date_str = target_item.data(0, Qt.ItemDataRole.UserRole)
        else:
            self._selected_date_str = None
        self.days_tree.verticalScrollBar().setValue(scroll_val)
        self.days_tree.blockSignals(False)

        self._refresh_sessions_list()

    def _on_day_selected(self):
        items = self.days_tree.selectedItems()
        if not items:
            return
        self._selected_date_str = items[0].data(0, Qt.ItemDataRole.UserRole)
        self._refresh_sessions_list()

    def _refresh_sessions_list(self):
        scroll_val = self.sessions_tree.verticalScrollBar().value()
        self.sessions_tree.blockSignals(True)
        prev_sid = None
        cur_items = self.sessions_tree.selectedItems()
        if cur_items:
            prev_sid = cur_items[0].data(0, Qt.ItemDataRole.UserRole)

        self.sessions_tree.clear()
        if not self._selected_app_key or not self._selected_date_str:
            self.lbl_sessions_title.setText(self.t("lbl_sessions_title"))
            self.lbl_session_detail.setText(self.t("detail_empty"))
            self.sessions_tree.blockSignals(False)
            return

        sessions = self.db.get_day_sessions(self._selected_app_key, self._selected_date_str)
        disp_date = format_date(self._selected_date_str, lang=self.lang)
        self.lbl_sessions_title.setText(
            self.t("lbl_sessions_title_count", date=disp_date, count=len(sessions))
        )

        active_sess = self.engine.active_sessions.get(self._selected_app_key)
        target_item = None

        for idx, s in enumerate(sessions, start=1):
            start_dt = datetime.fromtimestamp(s["start_ts"])
            if active_sess and active_sess.session_id == s["id"]:
                end_hm = self.t("session_in_progress")
                dur_sec = max(0, int(time.time() - s["start_ts"]))
            else:
                end_dt = datetime.fromtimestamp(s["end_ts"])
                end_hm = end_dt.strftime("%H:%M")
                dur_sec = s["duration_sec"]

            time_range = f"{start_dt.strftime('%H:%M')} - {end_hm}"
            item = QTreeWidgetItem([
                str(idx),
                time_range,
                format_duration(dur_sec, include_seconds=True, lang=self.lang),
                str(s["pid"]),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, s["id"])
            item.setData(1, Qt.ItemDataRole.UserRole, (idx, s, dur_sec, time_range))
            self.sessions_tree.addTopLevelItem(item)
            if prev_sid == s["id"]:
                target_item = item

        if target_item is None and self.sessions_tree.topLevelItemCount() > 0:
            target_item = self.sessions_tree.topLevelItem(0)

        if target_item:
            self.sessions_tree.setCurrentItem(target_item)
        self.sessions_tree.verticalScrollBar().setValue(scroll_val)
        self.sessions_tree.blockSignals(False)
        self._on_session_selected()

    def _on_session_selected(self):
        items = self.sessions_tree.selectedItems()
        if not items or not self._selected_app_key:
            return
        payload = items[0].data(1, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        idx, s, dur_sec, time_range = payload
        app = self._apps_cache.get(self._selected_app_key, {})
        exe_path = app.get("exe_path") or self.t("path_unknown")
        dur_str = format_duration(dur_sec, include_seconds=True, lang=self.lang)
        disp_date = format_date(s["date_str"], lang=self.lang)
        path_color = "#8eaed1" if self.current_theme == "dark" else "#526a82"
        self.lbl_session_detail.setText(
            self.t(
                "detail_text",
                idx=idx,
                date=disp_date,
                dur=dur_str,
                time_range=time_range,
                pid=s["pid"],
                path=exe_path,
                path_color=path_color,
            )
        )

    def _show_app_context_menu(self, pos: QPoint):
        item = self.app_tree.itemAt(pos)
        if not item:
            return
        self.app_tree.setCurrentItem(item)
        menu = QMenu(self)

        focus_list = {x.lower() for x in self.config.data.get("focus_only_list", [])}
        is_focus = (self._selected_app_key in focus_list) if self._selected_app_key else False
        act_focus = menu.addAction(get_focus_icon(active=True), self.t("ctx_focus_toggle"))
        act_focus.setCheckable(True)
        act_focus.setChecked(is_focus)

        menu.addSeparator()
        act_rename = menu.addAction(self.t("ctx_rename"))
        act_exclude = menu.addAction(self.t("ctx_exclude"))
        act_include = menu.addAction(self.t("ctx_include"))

        chosen = menu.exec(self.app_tree.viewport().mapToGlobal(pos))
        if chosen == act_focus and self._selected_app_key:
            app_key = self._selected_app_key.lower()
            cur_list = set(x.lower() for x in self.config.data.get("focus_only_list", []))
            if app_key in cur_list:
                cur_list.discard(app_key)
            else:
                cur_list.add(app_key)
            self.config.data["focus_only_list"] = sorted(cur_list)
            self.config.save()
            self._refresh_filter_lists()
            self.engine.poll()
            self.refresh_overview()
        elif chosen == act_rename:
            self._rename_selected_app()
        elif chosen == act_exclude:
            self._exclude_selected_app()
        elif chosen == act_include and self._selected_app_key:
            self._add_filter_entry("include", self._selected_app_key)

    def _rename_selected_app(self):
        if not self._selected_app_key:
            return
        app = self._apps_cache.get(self._selected_app_key)
        if not app:
            return
        new_name, ok = QInputDialog.getText(
            self,
            self.t("dlg_rename_title"),
            self.t("dlg_rename_prompt", exe=app["exe_name"]),
            text=app["name"],
        )
        if ok:
            self.db.set_custom_name(self._selected_app_key, new_name)
            self.refresh_overview()

    def _exclude_selected_app(self):
        if not self._selected_app_key:
            return
        app_key = self._selected_app_key
        self._add_filter_entry("exclude", app_key)
        self.engine.poll()
        self._selected_app_key = None
        self._selected_date_str = None
        self.refresh_overview()
        QMessageBox.information(
            self,
            self.t("msg_excluded_title"),
            self.t("msg_excluded_text", app=app_key),
        )

    def _on_filter_mode_changed(self):
        self.config.data["filter_mode"] = (
            "include_only" if self.radio_include_mode.isChecked() else "exclude"
        )
        self.config.save()

    def _on_auto_win_junk_toggled(self, checked: bool):
        self.config.data["auto_filter_windows_junk"] = checked
        self.config.save()

    def _refresh_filter_lists(self):
        self.include_list_widget.clear()
        for item in sorted(self.config.data.get("include_list", [])):
            self.include_list_widget.addItem(item)

        self.exclude_list_widget.clear()
        for item in sorted(self.config.data.get("exclude_list", [])):
            self.exclude_list_widget.addItem(item)

        if hasattr(self, "focus_list_widget"):
            self.focus_list_widget.clear()
            for item in sorted(self.config.data.get("focus_only_list", [])):
                self.focus_list_widget.addItem(item)

    def _add_filter_entry(self, kind: str, raw_text: str):
        val = raw_text.strip().lower()
        if not val:
            return
        if not val.endswith(".exe"):
            val += ".exe"

        if kind == "focus":
            lst = set(x.lower() for x in self.config.data.get("focus_only_list", []))
            lst.add(val)
            self.config.data["focus_only_list"] = sorted(lst)
            self.config.save()
            if hasattr(self, "focus_input"):
                self.focus_input.clear()
            self._refresh_filter_lists()
            self.engine.poll()
            self.refresh_overview()
            return

        is_include = (kind == "include" or kind is True)
        key = "include_list" if is_include else "exclude_list"
        other_key = "exclude_list" if is_include else "include_list"

        lst = set(x.lower() for x in self.config.data.get(key, []))
        other = set(x.lower() for x in self.config.data.get(other_key, []))
        lst.add(val)
        other.discard(val)

        self.config.data[key] = sorted(lst)
        self.config.data[other_key] = sorted(other)
        self.config.save()

        if is_include and hasattr(self, "include_input"):
            self.include_input.clear()
        elif hasattr(self, "exclude_input"):
            self.exclude_input.clear()

        self._refresh_filter_lists()
        self.engine.poll()
        self.refresh_overview()

    def _pick_running_for_filter(self, kind: str):
        dlg = RunningProcessDialog(self, lang=self.lang)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_exe:
            self._add_filter_entry(kind, dlg.selected_exe)

    def _remove_selected_filter(self, kind: str):
        if kind == "focus":
            widget = self.focus_list_widget
            key = "focus_only_list"
        elif kind == "include" or kind is True:
            widget = self.include_list_widget
            key = "include_list"
        else:
            widget = self.exclude_list_widget
            key = "exclude_list"

        selected = {i.text().lower() for i in widget.selectedItems()}
        if not selected:
            return
        cur = [x for x in self.config.data.get(key, []) if x.lower() not in selected]
        self.config.data[key] = sorted(cur)
        self.config.save()
        self._refresh_filter_lists()
        self.engine.poll()
        self.refresh_overview()

    def _toggle_theme(self):
        new_theme = "dark" if self.current_theme == "light" else "light"
        self.set_theme(new_theme)

    def _on_theme_changed(self):
        new_theme = self.theme_combo.currentData()
        if new_theme and new_theme != self.current_theme:
            self.set_theme(new_theme)

    def _apply_theme_colors(self):
        is_dark = (self.current_theme == "dark")

        # Overview Inspector Header
        if hasattr(self, "lbl_app_title"):
            self.lbl_app_title.setStyleSheet(f"font-size: 12pt; font-weight: 600; color: {'#e2efff' if is_dark else '#122d4a'};")
        if hasattr(self, "lbl_app_sub"):
            self.lbl_app_sub.setStyleSheet(f"color: {'#9bb7d4' if is_dark else '#49617a'};")
        if hasattr(self, "lbl_app_totals"):
            self.lbl_app_totals.setStyleSheet(f"font-weight: 600; color: {'#72baff' if is_dark else '#1e4d7a'};")

        # Section titles
        if hasattr(self, "lbl_days"):
            self.lbl_days.setStyleSheet(f"font-weight: 600; color: {'#d4e5f7' if is_dark else '#1f3c5c'};")
        if hasattr(self, "lbl_sessions_title"):
            self.lbl_sessions_title.setStyleSheet(f"font-weight: 600; color: {'#d4e5f7' if is_dark else '#1f3c5c'};")
        if hasattr(self, "lbl_session_detail"):
            self.lbl_session_detail.setStyleSheet(f"color: {'#cce0f5' if is_dark else '#2b4159'};")

        # Status Bar right text
        if hasattr(self, "lbl_status_right"):
            self.lbl_status_right.setStyleSheet(f"color: {'#a2bdd8' if is_dark else '#3a526b'};")
        if hasattr(self, "status_sep"):
            self.status_sep.setStyleSheet(f"color: {'#4a6787' if is_dark else '#7b9bbd'};")

        # Filters page
        if hasattr(self, "lbl_filter_mode_title"):
            self.lbl_filter_mode_title.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {'#e2efff' if is_dark else '#163659'};")
        for t_attr in ("include_title_lbl", "exclude_title_lbl", "focus_title_lbl"):
            if hasattr(self, t_attr):
                getattr(self, t_attr).setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {'#e2efff' if is_dark else '#163659'};")
        for d_attr in ("include_desc_lbl", "exclude_desc_lbl", "focus_desc_lbl"):
            if hasattr(self, d_attr):
                getattr(self, d_attr).setStyleSheet(f"color: {'#9bb7d4' if is_dark else '#4c6278'};")

        # Settings page
        for title_attr in (
            "lbl_lang_title",
            "lbl_theme_title",
            "lbl_track_mode_title",
            "lbl_size_title",
            "lbl_start_title",
            "lbl_data_title",
        ):
            if hasattr(self, title_attr):
                getattr(self, title_attr).setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {'#e2efff' if is_dark else '#163659'};")

        for desc_attr in (
            "lbl_lang_desc",
            "lbl_theme_desc",
            "lbl_track_mode_desc",
            "lbl_size_desc",
            "lbl_tray_info",
            "lbl_db_path",
        ):
            if hasattr(self, desc_attr):
                getattr(self, desc_attr).setStyleSheet(f"color: {'#9bb7d4' if is_dark else '#4c6278'};")

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.config.data["theme"] = theme
        self.config.save()

        qss = AERO_OBSIDIAN_QSS if theme == "dark" else AERO_QSS
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

        self._apply_theme_colors()

        if hasattr(self, "btn_theme_toggle"):
            self.btn_theme_toggle.setIcon(get_theme_icon(theme))

        if hasattr(self, "theme_combo"):
            self.theme_combo.blockSignals(True)
            idx = self.theme_combo.findData(theme)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
            self.theme_combo.blockSignals(False)

        if hasattr(self, "tray_menu"):
            self.tray_menu.setStyleSheet(qss)

        self.update()
        self.title_bar.update()
        self.refresh_overview()

    def _on_tracking_mode_changed(self):
        new_mode = self.track_mode_combo.currentData()
        if new_mode:
            self.config.data["tracking_mode"] = new_mode
            self.config.save()
            self.engine.poll()
            self.refresh_overview()

    def _on_autostart_toggled(self, checked: bool):
        ok, err = set_windows_autostart(checked)
        if ok:
            self.config.data["autostart"] = checked
            self.config.save()
        else:
            self.chk_autostart.blockSignals(True)
            self.chk_autostart.setChecked(not checked)
            self.chk_autostart.blockSignals(False)
            QMessageBox.warning(self, self.t("autostart_err_title"), self.t("autostart_err_msg", err=err))

    def _show_about_dialog(self):
        dlg = AboutDialog(self, lang=self.lang, theme=self.current_theme)
        dlg.exec()

    def _show_export_menu(self):
        menu = QMenu(self)
        act_json = menu.addAction(self.t("export_menu_json"))
        act_csv = menu.addAction(self.t("export_menu_csv"))
        chosen = menu.exec(self.btn_export.mapToGlobal(QPoint(0, self.btn_export.height())))
        if chosen == act_json:
            self._export_json()
        elif chosen == act_csv:
            self._export_csv()

    def _open_data_folder(self):
        try:
            os.startfile(str(DATA_DIR))
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR)))

    def _export_json(self):
        default_name = f"AeroChrono_Export_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, self.t("export_dialog_json"), default_name, self.t("file_filter_json")
        )
        if not path:
            return
        data = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "applications": self.db.export_full_data(lang=self.lang),
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        QMessageBox.information(self, self.t("export_done_title"), self.t("export_done_msg", path=path))

    def _export_csv(self):
        default_name = f"AeroChrono_Export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, self.t("export_dialog_csv"), default_name, self.t("file_filter_csv")
        )
        if not path:
            return
        full = self.db.export_full_data(lang=self.lang)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(self.t("csv_headers"))
            for app in full:
                for day in app["days"]:
                    for s in day["sessions"]:
                        writer.writerow([
                            app["name"],
                            app["exe_name"],
                            day["date_formatted"],
                            s["session_index"],
                            s["pid"],
                            s["start"],
                            s["end"],
                            s["duration_seconds"],
                            format_duration(s["duration_seconds"], include_seconds=True, lang=self.lang),
                        ])
        QMessageBox.information(self, self.t("export_done_title"), self.t("export_done_msg", path=path))

    def _confirm_reset_all(self):
        reply = QMessageBox.warning(
            self,
            self.t("reset_warn_title"),
            self.t("reset_warn_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.engine.shutdown()
            self.db.reset_all()
            self._selected_app_key = None
            self._selected_date_str = None
            self.days_tree.clear()
            self.sessions_tree.clear()
            self.lbl_app_title.setText(self.t("inspector_empty_title"))
            self.lbl_app_sub.setText(self.t("reset_done_sub"))
            self.lbl_app_totals.setText("")
            self.lbl_session_detail.setText(self.t("detail_empty"))
            self.btn_rename_app.setEnabled(False)
            self.btn_exclude_app.setEnabled(False)
            self.engine.install_foreground_hook(self._on_instant_app_detected)
            self.engine.poll()
            self.refresh_overview()


def main():
    try:
        shell32.SetCurrentProcessExplicitAppUserModelID("rwynx.aerochrono.timetracker.v100")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(get_app_icon())

    config = ConfigManager(CONFIG_PATH)
    theme = config.data.get("theme", "light")
    app.setStyleSheet(AERO_OBSIDIAN_QSS if theme == "dark" else AERO_QSS)

    db = Database(DB_PATH)
    engine = TrackerEngine(db, config)
    icons = IconManager(ICON_CACHE_DIR)

    window = AeroChronoWindow(db, config, engine, icons)

    start_minimized = "--minimized" in sys.argv
    if not start_minimized:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
