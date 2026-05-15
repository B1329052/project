# ============================================================
# 物品盤點程式 - 主程式
# ============================================================
# 使用方式：
#   1. 安裝套件：pip install openai pillow
#   2. 修改 config.py 中的參數
#   3. 執行：python main.py
# ============================================================

import os
import json
from config import OPENAI_API_KEY, IMAGE_FOLDER, REFERENCE_IMAGE
from functions import get_image_files, call_chatgpt, save_json, print_table


def main():
    print("=" * 50)
    print("  物品盤點程式 - ChatGPT 圖片辨識")
    print("=" * 50)

    # --- 步驟 1：檢查 API Key ---
    if OPENAI_API_KEY == "請在這裡填入你的 API key" or OPENAI_API_KEY.strip() == "":
        print("錯誤：請先填入你的 OpenAI API Key！")
        print("請打開 config.py，修改 OPENAI_API_KEY 變數。")
        return

    # --- 步驟 2：檢查資料夾是否存在 ---
    if not os.path.isdir(IMAGE_FOLDER):
        print(f"錯誤：找不到資料夾 '{IMAGE_FOLDER}'")
        print("請確認路徑是否正確。")
        return

    # --- 步驟 3：讀取圖片檔案 ---
    print(f"\n正在讀取資料夾：{IMAGE_FOLDER}")
    all_image_files = get_image_files(IMAGE_FOLDER)

    # 檢查是否有圖片
    if len(all_image_files) == 0:
        print("錯誤：資料夾中沒有找到任何圖片（.jpg, .jpeg, .png）")
        return

    # 分離對照圖片和場景圖片
    reference_image_path = None
    scene_images = []

    for img in all_image_files:
        filename = os.path.basename(img)
        if REFERENCE_IMAGE and filename == REFERENCE_IMAGE:
            reference_image_path = img
        else:
            scene_images.append(img)

    # 印出找到的場景圖片
    print(f"找到 {len(scene_images)} 張場景圖片：")
    for img in scene_images:
        print(f"  - {os.path.basename(img)}")

    # 印出對照圖片資訊
    if reference_image_path:
        print(f"找到對照清單圖片：{os.path.basename(reference_image_path)}")
    elif REFERENCE_IMAGE:
        print(f"\n提醒：找不到對照清單圖片 '{REFERENCE_IMAGE}'，將只做盤點不做比對。")

    # 如果場景圖片不是 4 張，印出提醒（但不中斷程式）
    if len(scene_images) != 4:
        print(f"\n提醒：預期 4 張場景圖片，但找到 {len(scene_images)} 張。")
        print("程式會繼續執行，但盤點結果可能不完整。\n")

    # --- 步驟 4：呼叫 ChatGPT API ---
    try:
        result_text = call_chatgpt(scene_images, reference_image_path)
    except Exception as e:
        print(f"API 呼叫失敗：{e}")
        return

    # --- 步驟 5：印出原始回傳結果 ---
    print("ChatGPT 回傳的原始結果：")
    print("-" * 50)
    print(result_text)
    print("-" * 50)

    # --- 步驟 6：嘗試解析 JSON ---

    # 有時候 ChatGPT 會在 JSON 外面包 ```json ... ```，這裡先清理掉
    clean_text = result_text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]  # 移除開頭的 ```json
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]  # 移除開頭的 ```
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]  # 移除結尾的 ```
    clean_text = clean_text.strip()

    try:
        result_json = json.loads(clean_text)
        print("\nJSON 解析成功！")
    except json.JSONDecodeError as e:
        print(f"\n警告：回傳內容不是合法的 JSON 格式：{e}")
        print("請檢查上方的原始回傳內容。")
        return

    # --- 步驟 7：儲存 JSON 檔案 ---
    save_json(result_json, "inventory_result.json")

    # --- 步驟 8：用表格印出結果 ---
    print_table(result_json)

    print("\n盤點完成！")


# 執行主程式
if __name__ == "__main__":
    main()
