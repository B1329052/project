# ============================================================
# 物品盤點程式 - 主程式
# ============================================================
# 使用方式：
#   1. 安裝套件：pip install openai pillow
#   2. 修改 config.py 中的參數
#   3. 執行：python main.py
# ============================================================

import os
from config import OPENAI_API_KEY, IMAGE_ROOT_FOLDER
from functions import get_group_folders, process_one_group


def main():
    print("=" * 50)
    print("  多組物品盤點程式 - ChatGPT 圖片辨識")
    print("=" * 50)

    # --- 步驟 1：檢查 API Key ---
    if OPENAI_API_KEY == "請在這裡填入你的 API key" or OPENAI_API_KEY.strip() == "":
        print("錯誤：請先填入你的 OpenAI API Key！")
        print("請打開 config.py，修改 OPENAI_API_KEY 變數。")
        return

    # --- 步驟 2：檢查圖片根資料夾 ---
    if not os.path.isdir(IMAGE_ROOT_FOLDER):
        print(f"錯誤：找不到圖片根資料夾：{IMAGE_ROOT_FOLDER}")
        print("請確認 pictures 資料夾是否存在。")
        return

    # --- 步驟 3：讀取所有 group 資料夾 ---
    group_folders = get_group_folders(IMAGE_ROOT_FOLDER)

    if len(group_folders) == 0:
        print("錯誤：pictures 資料夾中沒有任何 group 資料夾。")
        return

    print(f"\n找到 {len(group_folders)} 組場景資料：")
    for group in group_folders:
        print(f"  - {os.path.basename(group)}")

    # --- 步驟 4：逐一處理每一組 ---
    for group_folder in group_folders:
        try:
            process_one_group(group_folder)
        except Exception as e:
            print(f"\n此組處理失敗：{group_folder}")
            print(f"錯誤原因：{e}")
            print("繼續處理下一組。")

    print("\n全部 group 處理完成！")


# 執行主程式
if __name__ == "__main__":
    main()
