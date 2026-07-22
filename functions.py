# ============================================================
# 物品盤點程式 - 函式區
# ============================================================
# 所有功能函式集中在這個檔案中
# ============================================================

import os
import base64
import json
from PIL import Image, ImageOps, ImageEnhance
from openai import OpenAI
from config import (
    OPENAI_API_KEY,
    BASE_URL,
    MODEL_NAME,
    PROMPT_TEXT,
    camera_positions,
)


def get_image_files(folder_path):
    """
    讀取資料夾中所有支援的圖片檔案（.jpg, .jpeg, .png）
    回傳：圖片檔案路徑的列表
    """
    # 支援的圖片副檔名
    supported_extensions = (".jpg", ".jpeg", ".png")

    # 取得資料夾中所有符合格式的檔案
    image_files = []
    for filename in os.listdir(folder_path):
        # 用小寫比對副檔名，避免大小寫問題
        if filename.lower().endswith(supported_extensions):
            full_path = os.path.join(folder_path, filename)
            image_files.append(full_path)

    # 排序，讓結果穩定
    image_files.sort()

    return image_files


def compress_images(image_files, output_folder="compressed_images"):
    """
    將圖片清單中的每張圖片縮小尺寸並增加對比度後存到指定資料夾
    - 使用 thumbnail() 縮小，保持原始比例
    - 使用 ImageEnhance.Contrast 增加 50% 對比度
    - 保留原始檔案格式與副檔名
    回傳：處理後圖片路徑的列表
    """
    # 如果輸出資料夾不存在，自動建立
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"已建立壓縮圖片資料夾：{output_folder}")

    compressed_paths = []

    for image_path in image_files:
        filename = os.path.basename(image_path)
        # 保留原始副檔名（例如 .png 就是 .png，.jpg 就是 .jpg）
        output_path = os.path.join(output_folder, filename)

        try:
            # 開啟圖片
            img = Image.open(image_path)

            # 依照照片的 EXIF 方向資訊轉正，避免存檔後照片方向跑掉
            img = ImageOps.exif_transpose(img)

            # 印出原始圖片大小（方便 debug）
            original_size = os.path.getsize(image_path)
            print(f"  原始圖片：{filename}（{original_size / 1024:.1f} KB）")

            # 縮小圖片，保持比例，最大不超過 800x600
            img.thumbnail((800, 600))

            # 增加 50% 對比度
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)

            # 儲存圖片（保留原始格式）
            img.save(output_path)

            # 印出縮小後檔案大小
            compressed_size = os.path.getsize(output_path)
            print(f"  縮小完成：{output_path}（{compressed_size / 1024:.1f} KB）")
            compressed_paths.append(output_path)

        except Exception as e:
            print(f"  處理失敗：{filename}，錯誤：{e}")
            print(f"  跳過此圖片，繼續處理下一張。")

    return compressed_paths


def encode_image(image_path):
    """
    將圖片檔案讀取並轉成 base64 字串
    回傳：base64 編碼的字串
    """
    with open(image_path, "rb") as f:
        image_data = f.read()
    base64_string = base64.b64encode(image_data).decode("utf-8")
    return base64_string


def build_position_info(scene_images, reference_image_path):
    """
    根據場景圖片和對照圖片，自動產生拍攝位置說明文字。
    不寫死圖片數量，根據實際場景圖片動態產生。
    """
    num_scenes = len(scene_images)
    position_info = f"\n以下是 {num_scenes} 張場景圖片的拍攝位置：\n"

    for i, image_path in enumerate(scene_images):
        filename = os.path.basename(image_path)
        # 如果有設定攝影機位置就用，沒有就標記「未設定」
        position = camera_positions.get(filename, "未設定拍攝位置")
        position_info += f"- 場景圖片 {i + 1}（{filename}）：{position}\n"

    # 如果有對照圖片，加入說明
    if reference_image_path:
        ref_filename = os.path.basename(reference_image_path)
        position_info += f"\n- 對照清單圖片（{ref_filename}）：這是物品的對照清單/參考表，請用來比對盤點結果\n"

    return position_info


def call_chatgpt(scene_images, reference_image_path):
    """
    把場景圖片、對照圖片和提示詞一起送給 ChatGPT API
    scene_images: 場景圖片路徑列表（數量不固定）
    reference_image_path: 對照清單圖片路徑（可以是 None）
    回傳：ChatGPT 回傳的文字內容
    """
    # 建立 OpenAI 客戶端
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=BASE_URL)

    # --- 步驟 A：壓縮所有圖片 ---
    print("\n正在壓縮場景圖片...")
    compressed_scene = compress_images(scene_images)

    # 檢查是否有壓縮成功的場景圖片
    if len(compressed_scene) == 0:
        raise Exception("所有場景圖片壓縮失敗，無法呼叫 API。")

    # 壓縮對照圖片（如果有的話）
    compressed_ref_path = None
    if reference_image_path:
        print("\n正在壓縮對照清單圖片...")
        compressed_ref_list = compress_images([reference_image_path])
        if len(compressed_ref_list) > 0:
            compressed_ref_path = compressed_ref_list[0]
        else:
            print("對照清單圖片壓縮失敗，將不使用對照圖片。")

    # --- 組合提示詞 ---

    # 自動產生拍攝位置說明（根據實際場景圖片數量）
    position_info = build_position_info(scene_images, reference_image_path)

    # 完整提示詞 = 攝影機位置 + 主要提示詞
    full_prompt = position_info + "\n" + PROMPT_TEXT

    # --- 組合訊息內容（文字 + 多張壓縮圖片）---

    # messages 的 content 是一個列表，可以放文字和圖片
    content_list = []

    # 第一個元素：文字提示
    content_list.append({
        "type": "text",
        "text": full_prompt,
    })

    # 接下來：每張壓縮後的場景圖片轉成 base64 後加入
    for compressed_path in compressed_scene:
        filename = os.path.basename(compressed_path)
        print(f"  正在編碼壓縮後場景圖片：{filename}")

        base64_str = encode_image(compressed_path)

        # 壓縮後都是 JPEG 格式
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_str}",
            },
        })

    # 加入壓縮後的對照清單圖片
    if compressed_ref_path:
        ref_filename = os.path.basename(compressed_ref_path)
        print(f"  正在編碼壓縮後對照清單圖片：{ref_filename}")

        base64_str = encode_image(compressed_ref_path)

        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_str}",
            },
        })

    # --- 呼叫 API ---
    print("\n正在呼叫 ChatGPT API，請稍候...\n")

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": content_list,
            }
        ],
        max_completion_tokens=4096,
    )

    # 取出回傳的文字
    result_text = response.choices[0].message.content
    return result_text


def save_json(data, filename="inventory_result.json"):
    """
    將 JSON 資料儲存成檔案
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"結果已儲存到：{filename}")


def print_table(inventory_data):
    """
    用簡單的表格格式印出盤點結果（含遮擋分析、漏算位置、補拍建議）
    """
    # --- 1. 盤點結果表格 ---
    items = inventory_data.get("inventory", [])

    if not items:
        print("沒有辨識到任何物品。")
    else:
        print("\n" + "=" * 90)
        print("【盤點結果】")
        print("-" * 90)
        print(f"{'物品種類':<12} | {'辨識數量':<8} | {'AI備註'}")
        print("-" * 90)

        for item in items:
            name = item.get("物品種類", "未知")
            count = item.get("辨識出的物品數量", "?")
            note = item.get("AI備註", "")
            print(f"{name:<12} | {str(count):<8} | {note}")

        print("=" * 90)

    # --- 2. 遮擋分析表格 ---
    occlusion = inventory_data.get("occlusion_analysis", [])

    if occlusion:
        print("\n" + "=" * 90)
        print("【遮擋分析】")
        print("-" * 90)
        print(f"{'位置或照片':<20} | {'遮擋情況':<25} | {'可能影響'}")
        print("-" * 90)

        for item in occlusion:
            location = item.get("位置或照片", "未知")
            situation = item.get("遮擋情況", "")
            impact = item.get("可能影響", "")
            print(f"{location:<20} | {situation:<25} | {impact}")

        print("=" * 90)

    # --- 3. 可能漏算位置表格 ---
    missing_areas = inventory_data.get("possible_missing_areas", [])

    if missing_areas:
        print("\n" + "=" * 90)
        print("【可能漏算位置】")
        print("-" * 90)
        print(f"{'漏算位置':<15} | {'受影響物品':<12} | {'原因':<20} | {'不確定程度'}")
        print("-" * 90)

        for item in missing_areas:
            location = item.get("可能漏算的位置", "未知")
            affected = item.get("受影響的物品種類", "")
            reason = item.get("原因", "")
            uncertainty = item.get("不確定程度", "")
            print(f"{location:<15} | {affected:<12} | {reason:<20} | {uncertainty}")

        print("=" * 90)

    # --- 4. 是否建議補拍 ---
    more_photos = inventory_data.get("need_more_photos", {})

    if more_photos:
        print("\n" + "=" * 90)
        print("【是否建議補拍】")
        print("-" * 90)

        suggest = more_photos.get("建議補拍", False)
        reason = more_photos.get("原因", "")
        angles = more_photos.get("建議補拍角度", [])
        focus = more_photos.get("補拍重點", "")

        print(f"  建議補拍：{'是' if suggest else '否'}")
        print(f"  原因：{reason}")
        if angles:
            print(f"  建議補拍角度：{', '.join(angles) if isinstance(angles, list) else angles}")
        if focus:
            print(f"  補拍重點：{focus}")

        print("=" * 90)

    # --- 5. 整體備註 ---
    overall = inventory_data.get("overall_note", "")
    if overall:
        print(f"\n整體備註：{overall}")
