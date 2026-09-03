# ============================================================
# 物品盤點程式 - 設定檔
# ============================================================
# 所有可調整的參數都集中在這個檔案中
# ============================================================

import os

# API
BASE_URL = "https://air.cgu.edu.tw/cgullmapi/v1"
MODEL_NAME = "gpt-5.4"

# 專案根目錄
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 專案內資料夾
IMAGE_ROOT_FOLDER = os.path.join(BASE_DIR, "pictures")
RESULT_FOLDER = os.path.join(BASE_DIR, "results")
COMPRESSED_FOLDER = os.path.join(BASE_DIR, "compressed_images")

REFERENCE_IMAGE_NAME = "reference.jpg"
MAX_RESUPPLY_ROUNDS = 3

# API key 外部檔案
API_KEY_FILE = os.path.join(BASE_DIR, "api_key.txt")

def read_api_key():
    """
    從 api_key.txt 讀取 API key。
    """
    if not os.path.exists(API_KEY_FILE):
        raise FileNotFoundError(
            "找不到 api_key.txt，請在專案資料夾中建立 api_key.txt，並把 API key 放進去。"
        )

    with open(API_KEY_FILE, "r", encoding="utf-8") as file:
        api_key = file.read().strip()

    if not api_key:
        raise ValueError("api_key.txt 是空的，請確認裡面有填入 API key。")

    return api_key

OPENAI_API_KEY = read_api_key()

# 盤點提示詞
PROMPT_TEXT = """
我會提供一張參照圖片，以及多張同一個場景的盤點圖片。

請嚴格遵守以下規則：

1. 參照圖片只用來判斷「需要盤點哪些物品種類」。
2. 請不要統計參照圖片中的數量。
3. 最終輸出的 inventory 裡，「辨識出的物品數量」一定是場景圖片中的數量。
4. 場景圖片才是正式要盤點的圖片。
5. 多張場景圖片是同一個場景的不同角度，請整合判斷。
6. 同一個物品如果出現在多張場景圖片中，只能算一次。
7. 如果場景圖片中沒有出現參照圖片裡的某種物品，該物品數量請填 0。
8. 如果數量無法完全確認，請在 AI備註 中說明。

種類判斷規則：
- 請先根據參照圖片建立「要盤點的物品種類清單」。
- 不同外觀、用途、形狀明顯不同的物品，請視為不同物品種類。
- 盤點時請依照物品種類分開統計，不要把不同種類的物品合併計算。
- 如果場景圖片中同時出現多種物品，請分別判斷每一種物品的數量。
- 場景圖片中的物品只有在外觀與參照圖片中的某一種類明顯相同時，才可以計入該種類。
- 如果某個物品看起來相似但無法確定是否同種類，請不要直接合併，請在 AI備註 中說明不確定。
- 若參照圖片中有多種物品，inventory 必須每一種物品各自輸出一筆資料。

補拍判斷規則：
- 請先嘗試根據目前所有場景圖片統計數量。
- 如果大部分物品都能清楚辨識，且數量只可能有小幅誤差，請將「建議補拍」設為 false，並在 AI備註 說明不確定處。
- 如果有重要物品被遮擋、重疊、模糊、裁切，導致數量可能明顯少算或多算，請將「建議補拍」設為 true。
- 如果只能看到物品的一部分，無法判斷完整數量，請將「建議補拍」設為 true。
- 如果只有單一角度照片，且物品有堆疊、重疊、被其他物品遮住，請將「建議補拍」設為 true。
- 如果照片雖然不是最佳角度，但仍能合理判斷主要物品數量，請將「建議補拍」設為 false。
- 不要因為照片稍微不完美就建議補拍；只有當不補拍可能影響最終數量正確性時，才建議補拍。

請用 JSON 格式輸出，格式如下：

{
  "inventory": [
    {
      "物品種類": "物品名稱",
      "辨識出的物品數量": 數量,
      "AI備註": "此數量必須來自場景圖片，不是參照圖片；若數量不確定，請說明原因"
    }
  ],
  "need_more_photos": {
    "建議補拍": true,
    "原因": "簡短說明為什麼需要或不需要補拍",
    "建議補拍角度": ["角度1", "角度2"],
    "補拍重點": "補拍時應該拍清楚哪些物品或區域；如果不需要補拍，請填寫「不需要」"
  },
  "overall_note": "整體盤點說明"
}

請只輸出 JSON，不要輸出其他文字。
"""