import os
import time
import json
import subprocess
import threading
import re
import cv2
import numpy as np
import random
import math
import sys
import requests
import win32gui
import win32con
import pygetwindow as gw
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCRCPY_DIR = os.path.join(BASE_DIR, "scrcpy-win64-v2.7")
ADB_PATH = os.path.join(SCRCPY_DIR, "adb.exe")
NEMO_DIR = os.path.join(BASE_DIR, "NemoADB")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# --- [設定與全域變數] ---
NEMO_TITLE = "NemoADB for GPS Joystick"
VISITED_FILE = os.path.join(BASE_DIR, "visited_pokestops.json")
target_serial = ""

POS_POKESTOP = (540, 1420)
POS_TALK_SKIP = (540, 2150)
POS_BATTLE_BTN = (540, 1730)
POS_CONFIRM_BTN = (540, 2050)
BATTLE_POINTS = [(350, 1950), (540, 1950), (730, 1950)]
POS_ATTACK_CENTER = (540, 1400)
ATTACK_RADIUS = 200
CATCH_SWIPE_START = (540, 2000)
CATCH_SWIPE_END = (540, 500)
POS_CATCH_CONFIRM_1 = (540, 1570)
POS_CATCH_CONFIRM_2 = (540, 2100)
POS_MENU_BALL = (540, 2110)
POS_BAG_ICON = (840, 1880)
POS_HEAL_CONFIRM = (540, 1910)
POS_DEAD_BAG = (300, 320)

# --- [工具程式：系統控制] ---
def get_screenshot():
    try:
        cmd = [ADB_PATH]
        if target_serial: cmd += ["-s", target_serial]
        cmd += ["shell", "screencap", "-p"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw_data, _ = process.communicate()
        if not raw_data: return None
        png_data = raw_data.replace(b'\r\n', b'\n')
        nparr = np.frombuffer(png_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"* 錯誤: {e}")
        return None


def find_image(template_name, threshold=0.75, return_pos=False):
    path = os.path.join(ASSETS_DIR, template_name)
    if not os.path.exists(path): return (False, None) if return_pos else False

    screen = get_screenshot()
    if screen is None: return (False, None) if return_pos else False
    try:
        template = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"* 錯誤: {e}")
        return (False, None) if return_pos else False

    if template is None: return (False, None) if return_pos else False

    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if return_pos:
        h, w = template.shape[:2]
        center = (max_loc[0] + w // 2, max_loc[1] + h // 2)
        return (max_val >= threshold, center)
    return max_val >= threshold

def adb_back():
    cmd = f'"{ADB_PATH}" '
    if target_serial: cmd += f'-s {target_serial} '
    cmd += 'shell input keyevent 4'
    subprocess.run(cmd, shell=True, capture_output=True)

def adb_swipe_random(start_base, end_base):
    s_x, s_y = start_base[0] + random.randint(-30, 30), start_base[1] + random.randint(-30, 30)
    e_x, e_y = end_base[0] + random.randint(-50, 50), end_base[1] + random.randint(-50, 50)
    duration = random.randint(180, 250)
    cmd = f'"{ADB_PATH}" '
    if target_serial: cmd += f'-s {target_serial} '
    cmd += f'shell input swipe {s_x} {s_y} {e_x} {e_y} {duration}'
    subprocess.run(cmd, shell=True, capture_output=True)

def ad_click_smart(target_pos):
    try:
        prefix = f'"{ADB_PATH}" '
        if target_serial: prefix += f'-s {target_serial} '
        out = subprocess.check_output(f'{prefix}shell wm size', shell=True).decode()
        m = re.search(r"(\d+)x(\d+)", out)
        curr_w, curr_h = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
        real_x, real_y = int((target_pos[0] / 1080) * curr_w), int((target_pos[1] / 2400) * curr_h)
        subprocess.run(f'{prefix}shell input tap {real_x} {real_y}', shell=True, capture_output=True)
    except:
        pass

def get_random_point_in_circle(center, radius):
    angle = random.uniform(0, 2 * math.pi)
    r = radius * math.sqrt(random.uniform(0, 1))
    return (int(center[0] + r * math.cos(angle)), int(center[1] + r * math.sin(angle)))

def ensure_nemo_open():
    hwnd = win32gui.FindWindow(None, NEMO_TITLE)
    if not hwnd:
        print("+ 啟動 NemoADB...")
        try:
            old_dir = os.getcwd()
            if not os.path.exists(NEMO_DIR):
                print(f"* 錯誤: 找不到 NemoADB 資料夾於 {NEMO_DIR}"); return None
            os.chdir(NEMO_DIR)
            subprocess.Popen(".\\NemoADB.exe", shell=True)
            time.sleep(2)
            os.chdir(old_dir)
            hwnd = win32gui.FindWindow(None, NEMO_TITLE)
        except Exception as e:
            print(f"* 錯誤: {e}"); return None
    if hwnd:
        windows = gw.getWindowsWithTitle(NEMO_TITLE)
        if windows and not windows[0].isMinimized: windows[0].minimize()
    return hwnd

def move_location(lat, lng):
    hwnd = ensure_nemo_open()
    if not hwnd: return False
    try:
        hwnd_edit = win32gui.FindWindowEx(hwnd, 0, "Edit", "")
        hwnd_start = win32gui.FindWindowEx(hwnd, 0, "Button", "   START   ")
        coord = f"{lat}, {lng}"
        win32gui.SendMessage(hwnd_edit, win32con.WM_SETTEXT, None, coord)
        time.sleep(0.5)
        def click_btn(btn):
            lp = (25 << 16) | 25
            win32gui.SendMessage(btn, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
            time.sleep(0.1)
            win32gui.SendMessage(btn, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, lp)
        click_btn(hwnd_start); time.sleep(0.2); click_btn(hwnd_start)
        print(f"- 傳送到座標: {coord}")
        return True
    except:
        return False

# --- [工具程式：雷達與計算] ---
def get_moonani_targets(pkm_types=[]):
    blacklist = ["Arlo", "Cliff", "Sierra", "Decoy", "Giovanni"]
    all_targets = []
    if not pkm_types:
        url = "https://moonani.com/PokeList/rocket.php"
        try:
            html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30).text
            rows = re.findall(r'<tr.*?>([\s\S]*?)</tr>', html)
            for r in rows:
                if any(b.lower() in r.lower() for b in blacklist): continue
                m = re.search(r'(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)', r)
                if m: all_targets.append({"lat": float(m.group(1)), "lng": float(m.group(2))})
            return all_targets
        except:
            return []
    else:
        opt = Options(); opt.add_argument("--headless"); opt.add_argument("--log-level=3")
        driver = webdriver.Chrome(options=opt)
        try:
            for t in pkm_types:
                url = f"https://moonani.com/PokeList/rocket.php?type={t}"
                driver.get(url)
                time.sleep(1)
                while True:
                    rows = driver.find_elements(By.CSS_SELECTOR, "#customers tbody tr")
                    for row in rows:
                        txt = row.text
                        if any(b.lower() in txt.lower() for b in blacklist): continue
                        m = re.search(r'(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)', txt)
                        if m: all_targets.append({"lat": float(m.group(1)), "lng": float(m.group(2))})
                    try:
                        nxt = driver.find_element(By.LINK_TEXT, "Next")
                        if "disabled" in nxt.find_element(By.XPATH, "./..").get_attribute("class"): break
                        nxt.click(); time.sleep(0.5)
                    except: break
            unique_targets = []
            seen = set()
            for t in all_targets:
                key = (t['lat'], t['lng'])
                if key not in seen: unique_targets.append(t); seen.add(key)
            return unique_targets
        finally: driver.quit()

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat, d_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_cooldown_seconds(dist):
    cooldown_table = [(1.0, 0.5), (2.0, 1), (4.0, 2), (10.0, 8), (15.0, 11), (20.0, 13), (25.0, 15), (30.0, 18), (40.0, 22), (45.0, 23), (60.0, 25), (80.0, 27), (100.0, 30), (250.0, 45), (500.0, 65), (1000.0, 100), (1250.0, 118)]
    for limit, minutes in cooldown_table:
        if dist <= limit: return max(0, int(minutes * 60) - 20)
    return 7180

def countdown(seconds, msg="Waiting"):
    if seconds <= 0: return
    for i in range(int(seconds), 0, -1):
        sys.stdout.write(f"\r- {msg}: {i}s   ")
        sys.stdout.flush()
        time.sleep(1)
    print(f"\r- {msg}: 完成！          ")

def load_json(f, d): return json.load(open(f, 'r')) if os.path.exists(f) else d
def save_json(f, d): json.dump(d, open(f, 'w'))

# --- [主程式邏輯] ---
def run_bot():
    global target_serial
    subprocess.run(f'"{ADB_PATH}" disconnect', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists(VISITED_FILE): os.remove(VISITED_FILE)
    print("-" * 45 + "\n" + " " * 12 + "Beat_Team_Rocket_v2.0\n" + "-" * 45)
    print("[啟動前檢查清單]\n1. 硬體連線：手機以傳輸線連接至電腦，並確認開啟 USB 偵錯模式\n2. 傳送設置：GPS Joystick 使用抽屜模式縮至最小，並將抽屜與搖桿置於手機畫面右上角\n3. 遊戲環境：遊戲視角縮至最小，建議不要孵蛋\n4. 雷達設置：建議關閉遊戲內火箭隊雷達與超級火箭隊雷達\n5. 夥伴設置：建議攜帶給力好夥伴\n6. 物資準備：確保包包中有足夠的厲害傷藥與活力碎片，建議可以先刷路線獲得\n7. 打手確認：確認各屬性皆已安排對應的戰鬥小隊\n8. 安全提醒：建議執行時全程在旁觀看以利應對突發狀況\n9. 打預防針：沒有做好如果打輸會怎麼樣，我覺得我不會打輸，還有如果抓到 XXL 和 XXS 也不知道會怎麼樣\n" + "-" * 45)

    print("[輸入設定]")
    conn_input = input("- 連線模式 (輸入 0 代表使用 USB 不拔線，輸入 1 代表使用 WiFi 可拔線): ").strip()
    scrcpy_params = '-m720 --max-fps 10 -b2m --no-audio --turn-screen-off'

    if conn_input == "1":
        print(f" - 使用 WiFi 連線模式")
        phone_ip = input("  - 輸入手機 WiFi IP 地址: ").strip()
        if phone_ip.count('.') == 3:
            subprocess.run(f'"{ADB_PATH}" tcpip 5555', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            subprocess.run(f'"{ADB_PATH}" connect {phone_ip}:5555', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            check_output = subprocess.check_output(f'"{ADB_PATH}" devices', shell=True).decode()
            if phone_ip in check_output:
                print(f"  - 連線成功，已連線至 {phone_ip}")
                print(f"  - 拔除傳輸線後，按 Enter 鍵繼續...")
                input()
                target_serial = f"{phone_ip}:5555"
            else:
                print(f"  - 連線失敗，使用 USB 連線模式。\n")
                target_serial = ""
        else:
            print(f"  - IP 格式錯誤，使用 USB 連線模式。\n"); target_serial = ""
    else:
        if conn_input == "": print(" - 輸入留空，使用 USB 連線模式\n")
        elif conn_input == "0": print(" - 輸入成功，使用 USB 連線模式\n")
        else: print(" - 輸入錯誤，使用 USB 連線模式\n")
        target_serial = ""

    p_input = input("- 目標屬性 (輸入屬性英文，多個以半形逗號隔開，留空則預設為不指定): ").strip()
    valid_types = ["normal", "fire", "water", "grass", "electric", "ice", "fighting", "poison", "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy"]
    p_types_list = []
    if p_input:
        raw_types = [t.strip().lower() for t in p_input.split(',')]
        all_valid = True
        for t in raw_types:
            if t in valid_types: p_types_list.append(t)
            else: all_valid = False
        if not all_valid or not p_types_list: print(" - 輸入錯誤，預設為不指定"); p_types_list = []
        else: print(" - 輸入成功，針對指定屬性")
    else: print(" - 輸入留空，預設為不指定"); p_types_list = []

    p_type = p_types_list
    r_input = input("- 定期掃描雷達週期 (輸入數字，預設為 5): ").strip()
    try: r_limit = int(r_input) if r_input else 5
    except: r_limit = 5; print(" - 格式錯誤，預設 5")

    h_input = input("- 定期復活補血週期 (輸入數字，預設為 5): ").strip()
    try: h_limit = int(h_input) if h_input else 5
    except: h_limit = 5; print(" - 格式錯誤，預設 5")

    m_pos = input("- 起點座標 (輸入經緯度，留空則預設為大安森林公園): ").strip()
    if m_pos:
        try:
            m_lat, m_lng = map(float, m_pos.split(','))
            curr_pos = {"lat": m_lat, "lng": m_lng}
            print(" - 輸入成功，傳送到輸入的位址")
        except:
            curr_pos = {"lat": 25.032966, "lng": 121.535516}
            print(" - 輸入錯誤，傳送到預設位置")
    else:
        curr_pos = {"lat": 25.032966, "lng": 121.535516}
        print(" - 輸入留空，傳送到預設位置")

    # 連線最後檢查
    try:
        check_devices = subprocess.check_output(f'"{ADB_PATH}" devices', shell=True).decode().strip()
        lines = [l for l in check_devices.split('\n') if l.strip() and not l.startswith('List')]
        if not lines:
            print("\n* 錯誤: 找不到任何已連線的手機！請檢查 USB 或 WiFi。")
            input("* 按 Enter 鍵結束並重新檢查...")
            sys.exit()
    except:
        print("\n* 錯誤: 無法執行 ADB 指令，請檢查 scrcpy 資料夾路徑。")
        input("* 按 Enter 鍵結束..."); sys.exit()

    print("")
    ensure_nemo_open()
    os.chdir(SCRCPY_DIR)
    print("+ 啟動 Scrcpy...")
    serial_arg = f"-s {target_serial}" if target_serial else "-d"
    subprocess.Popen(f'scrcpy.exe {serial_arg} --window-title "Beat_Team_Rocket_v2.0" {scrcpy_params}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chdir(BASE_DIR)
    time.sleep(5)

    total, skip, won, heal_cnt, caught = 0, 0, 0, 0, 0
    last_action_time = time.time()
    first_run = True
    while True:
        if first_run:
            print(f"\n- 正在爬蟲雷達資訊...")
            first_run = False
        else:
            print("\n- 執行定期掃描雷達流程...")

        visited = load_json(VISITED_FILE, [])
        all_targets = get_moonani_targets(pkm_types=p_type)
        targets = [t for t in all_targets if f"{t['lat']},{t['lng']}" not in visited]
        if not targets: time.sleep(30); continue
        targets.sort(key=lambda t: calculate_distance(curr_pos['lat'], curr_pos['lng'], t['lat'], t['lng']))

        for idx, target in enumerate(targets[:r_limit], 1):
            lat, lng, t_key = target['lat'], target['lng'], f"{target['lat']},{target['lng']}"
            theoretical_wait = get_cooldown_seconds(calculate_distance(curr_pos['lat'], curr_pos['lng'], lat, lng))
            elapsed_time = time.time() - last_action_time
            real_wait = max(0, theoretical_wait - elapsed_time)

            total += 1
            dist_from_last = calculate_distance(curr_pos['lat'], curr_pos['lng'], lat, lng)
            print(f"\n- 目標 {idx} (總計:{total} | 跳過:{skip} | 打完:{won} | 捕捉:{caught})")
            print(f"- 目標座標: {lat}, {lng} (距離:{dist_from_last:.2f}km)")

            if real_wait > 0: countdown(real_wait, "冷卻時間")

            if move_location(lat, lng):
                countdown(20, "傳送完畢, 等待載入地圖")
                if find_image("fast.png", 0.85): ad_click_smart((540, 1630)); time.sleep(2)
                entered = False
                for _ in range(2):
                    ad_click_smart((POS_POKESTOP[0] + random.randint(-20, 20), POS_POKESTOP[1] + random.randint(-20, 20)))
                    time.sleep(3)
                    if find_image("close_button.png", 0.85) or find_image("battle.png", 0.8): entered = True; break
                    if not find_image("map.png", 0.90): adb_back(); time.sleep(2)

                visited.append(t_key); save_json(VISITED_FILE, visited)
                if not entered: print("- 跳過目標。"); skip += 1; continue

                battle_ready = False
                for _ in range(10):
                    if find_image("battle.png", 0.85):
                        ad_click_smart(POS_BATTLE_BTN); time.sleep(1.5)
                        ad_click_smart(POS_CONFIRM_BTN); time.sleep(2)
                        if find_image("dead.png", 0.8):
                            ad_click_smart(POS_DEAD_BAG); time.sleep(1.5)
                            f, p = find_image("resurrect.png", 0.8, return_pos=True)
                            if f:
                                ad_click_smart(p); time.sleep(1.5); ad_click_smart(POS_HEAL_CONFIRM); time.sleep(1.5)
                                adb_back(); time.sleep(1.5); adb_back(); time.sleep(1.5)
                            ad_click_smart(POS_CONFIRM_BTN); time.sleep(3)
                        battle_ready = True; break
                    ad_click_smart(POS_TALK_SKIP); time.sleep(1.5)

                if battle_ready:
                    print("- 正在與火箭隊手下對戰中...")
                    stop_battle = threading.Event(); start_time = time.time()
                    def attack_worker():
                        while not stop_battle.is_set():
                            ad_click_smart(get_random_point_in_circle(POS_ATTACK_CENTER, ATTACK_RADIUS))
                            for pt in BATTLE_POINTS: ad_click_smart(pt)
                    t = threading.Thread(target=attack_worker); t.start()
                    try:
                        while time.time() - start_time < 300:
                            if find_image("win.png", 0.75):
                                curr_pos = {"lat": lat, "lng": lng}; last_action_time = time.time(); break
                            time.sleep(5)
                    finally: stop_battle.set(); t.join()

                    print("- 正在捕捉暗影寶可夢...")
                    while True:
                        adb_swipe_random(CATCH_SWIPE_START, CATCH_SWIPE_END); time.sleep(2.5)
                        if not find_image("win.png", 0.70):
                            time.sleep(8)
                            if find_image("catched.png", 0.8):
                                caught += 1; time.sleep(2)
                                f_ok, p_ok = find_image("OK.png", 0.8, return_pos=True)
                                ad_click_smart(p_ok if f_ok else POS_CATCH_CONFIRM_1)
                                time.sleep(3); ad_click_smart(POS_CATCH_CONFIRM_2); time.sleep(2); break
                        if find_image("map.png", 0.90): break

                    won += 1; heal_cnt += 1
                    if heal_cnt >= h_limit:
                        print("\n- 執行定期復活補血流程...")
                        ad_click_smart(POS_MENU_BALL); time.sleep(1.5); ad_click_smart(POS_BAG_ICON); time.sleep(2)
                        f1, p1 = find_image("resurrect.png", 0.8, return_pos=True)
                        if f1: ad_click_smart(p1); time.sleep(1.5); ad_click_smart(POS_HEAL_CONFIRM); time.sleep(1.5); adb_back(); time.sleep(1.5)
                        f2, p2 = find_image("medicine.png", 0.8, return_pos=True)
                        if f2: ad_click_smart(p2); time.sleep(1.5); ad_click_smart(POS_HEAL_CONFIRM); time.sleep(1.5); adb_back(); time.sleep(1.5)
                        adb_back(); time.sleep(1.5); heal_cnt = 0

if __name__ == "__main__":
    try: run_bot()
    except KeyboardInterrupt: print("\n\n~ 腳本終止")