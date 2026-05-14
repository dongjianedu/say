import requests
import hashlib
import time
import os

# --- 配置區 ---
PANEL_URL = "http://47.95.178.169:23556"
API_KEY = "1203127"  # 你在 sqlite3 設置的 Key
LOCAL_FILE = "test.txt"  # 本地文件
REMOTE_PATH = "/root/code"  # 遠端目錄


# --------------

def get_auth_headers():
    timestamp = str(int(time.time()))
    # 嚴格遵循公式: md5('1panel' + API-Key + UnixTimestamp)
    token_str = f"1panel{API_KEY}{timestamp}"
    token = hashlib.md5(token_str.encode()).hexdigest()

    return {
        "1Panel-Token": token,
        "1Panel-Timestamp": timestamp
    }


def sync_file():
    if not os.path.exists(LOCAL_FILE):
        print(f"錯誤: 找不到本地文件 {LOCAL_FILE}")
        return

    # 1. 獲取遠端文件資訊進行比對 (使用 /api/v1/external/files/search)
    # 注意：external 前綴通常用於繞過 Session 檢查，走 API Key 驗證
    search_url = f"{PANEL_URL}/api/v1/external/files/search"
    headers = get_auth_headers()

    payload = {
        "path": REMOTE_PATH,
        "name": os.path.basename(LOCAL_FILE)
    }

    print(f"正在比對文件: {os.path.basename(LOCAL_FILE)}...")
    try:
        res = requests.post(search_url, headers=headers, json=payload)

        # 如果返回 401，嘗試 v2 路徑（部分 1.10+ 版本開始過渡到 v2）
        if res.status_code == 401:
            search_url = f"{PANEL_URL}/api/v2/files/search"  # 或你參考文檔中的路徑
            res = requests.post(search_url, headers=headers, json=payload)

        should_upload = True
        if res.status_code == 200:
            data = res.json().get('data', [])
            if data:
                remote_size = data[0].get('size')
                local_size = os.path.getsize(LOCAL_FILE)
                if remote_size == local_size:
                    print("✨ 文件大小一致，跳過上傳。")
                    should_upload = False

        if should_upload:
            upload_file()

    except Exception as e:
        print(f"比對過程中發生錯誤: {e}")


def upload_file():
    # 上傳接口
    upload_url = f"{PANEL_URL}/api/v2/files/upload"
    headers = get_auth_headers()  # 重新獲取帶有最新時間戳的 headers

    # 準備文件與參數
    with open(LOCAL_FILE, 'rb') as f:
        files = {
            'file': (os.path.basename(LOCAL_FILE), f)
        }
        data = {
            'path': REMOTE_PATH,
            'isOverwrite': 'true'
        }

        print("🚀 正在上傳並覆蓋文件...")
        res = requests.post(upload_url, headers=headers, data=data, files=files)

        if res.status_code == 200:
            print("✅ 同步成功！")
            print(res.json())
        else:
            print(f"❌ 上傳失敗: {res.status_code} - {res.text}")


if __name__ == "__main__":
    upload_file()
    #sync_file()
