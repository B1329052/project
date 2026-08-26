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
    REFERENCE_IMAGE_NAME,
    RESULT_FOLDER,
)

# 把符合格式的圖片路徑存進 image_files，最後排序後回傳
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

def get_group_folders(root_folder):
    """
    讀取 pictures 底下所有 group 資料夾。
    每個子資料夾代表一組場景。
    """
    group_folders = []

    for name in os.listdir(root_folder):
        full_path = os.path.join(root_folder, name)

        if os.path.isdir(full_path):
            group_folders.append(full_path)

    group_folders.sort()
    return group_folders

# 影像前處理
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

# 把圖片轉成 base64 字串
def encode_image(image_path):
    """
    將圖片檔案讀取並轉成 base64 字串
    回傳：base64 編碼的字串
    """
    with open(image_path, "rb") as f:
        image_data = f.read()
    base64_string = base64.b64encode(image_data).decode("utf-8")
    return base64_string

def get_mime_type(image_path):
    """
    根據副檔名判斷圖片格式，給 API 使用。
    """
    ext = os.path.splitext(image_path)[1].lower()

    if ext == ".png":
        return "image/png"
    elif ext == ".jpg" or ext == ".jpeg":
        return "image/jpeg"
    else:
        return "image/jpeg"

def build_image_info(scene_images, reference_image_path, group_name):
    """
    產生圖片說明文字。
    這階段不手動設定拍攝角度，只列出 group 名稱與圖片檔名。
    """
    info = f"\n目前處理的場景資料夾：{group_name}\n"

    if reference_image_path:
        ref_filename = os.path.basename(reference_image_path)
        info += f"\n參照圖片：{ref_filename}\n"

    info += f"\n場景圖片共有 {len(scene_images)} 張：\n"

    for i, image_path in enumerate(scene_images):
        filename = os.path.basename(image_path)
        info += f"- 場景圖片 {i + 1}：{filename}\n"

    info += "\n請注意：場景圖片檔名可以任意，這些圖片都屬於同一個場景。\n"

    return info

# API 呼叫 ChatGPT
def call_chatgpt(scene_images, reference_image_path, group_name):
    """
    把場景圖片、對照圖片和提示詞一起送給 ChatGPT API
    scene_images: 場景圖片路徑列表（數量不固定）
    reference_image_path: 對照清單圖片路徑（可以是 None）
    回傳：ChatGPT 回傳的文字內容
    """
    # 建立 OpenAI 客戶端
    if BASE_URL:
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=BASE_URL
    )
    else:
        client = OpenAI(
            api_key=OPENAI_API_KEY
        )

    # --- 步驟 A：壓縮所有圖片 ---
    print("\n正在壓縮場景圖片...")
    compressed_output_folder = os.path.join("compressed_images", group_name)
    compressed_scene = compress_images(scene_images, compressed_output_folder)

    # 檢查是否有壓縮成功的場景圖片
    if len(compressed_scene) == 0:
        raise Exception("所有場景圖片壓縮失敗，無法呼叫 API。")

    # 壓縮對照圖片（如果有的話）
    compressed_ref_path = None
    if reference_image_path:
        print("\n正在壓縮對照清單圖片...")
        compressed_ref_list = compress_images([reference_image_path], compressed_output_folder)
        if len(compressed_ref_list) > 0:
            compressed_ref_path = compressed_ref_list[0]
        else:
            print("對照清單圖片壓縮失敗，將不使用對照圖片。")

    # --- 組合提示詞 ---

    image_info = build_image_info(scene_images, reference_image_path, group_name)
    full_prompt = image_info + "\n" + PROMPT_TEXT

    # --- 組合訊息內容（文字 + 多張壓縮圖片）---

    # messages 的 content 是一個列表，可以放文字和圖片
    content_list = []

    # 第一個元素：文字提示
    content_list.append({
        "type": "text",
        "text": full_prompt,
    })

    # 接下來：每張壓縮後的場景圖片轉成 base64 後加入
    if compressed_ref_path:
        ref_filename = os.path.basename(compressed_ref_path)
        print(f"  正在編碼壓縮後參照圖片：{ref_filename}")

        content_list.append({
            "type": "text",
            "text": f"接下來這張是參照圖片：{ref_filename}"
        })

        base64_str = encode_image(compressed_ref_path)
        mime_type = get_mime_type(compressed_ref_path)

        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{base64_str}",
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

def clean_json_text(result_text):
    """
    清理 GPT 回傳內容外面的 ```json 包裝。
    """
    clean_text = result_text.strip()

    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]

    if clean_text.startswith("```"):
        clean_text = clean_text[3:]

    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]

    return clean_text.strip()

def save_json(data, filename="inventory_result.json"):
    """
    將 JSON 資料儲存成檔案
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"結果已儲存到：{filename}")

def process_one_group(group_folder):
    """
    處理單一 group 資料夾。
    每個 group 代表一個場景。
    每個 group 裡面都有自己的 reference.jpg。
    """
    group_name = os.path.basename(group_folder)

    print("\n" + "=" * 60)
    print(f"開始處理：{group_name}")
    print("=" * 60)

    # --- 找出這一組自己的參照圖片 ---
    reference_image_path = os.path.join(group_folder, REFERENCE_IMAGE_NAME)

    if not os.path.isfile(reference_image_path):
        print(f"錯誤：{group_name} 找不到參照圖片：{REFERENCE_IMAGE_NAME}")
        print("請確認每個 group 資料夾中都有 reference.jpg")
        return

    print(f"找到參照圖片：{REFERENCE_IMAGE_NAME}")

    # --- 讀取這個 group 裡的所有圖片 ---
    all_images = get_image_files(group_folder)

    # --- 把 reference.jpg 排除，剩下的都是場景圖片 ---
    scene_images = []

    for img in all_images:
        filename = os.path.basename(img)

        if filename != REFERENCE_IMAGE_NAME:
            scene_images.append(img)

    if len(scene_images) == 0:
        print(f"提醒：{group_name} 裡沒有找到場景圖片，跳過此組。")
        return

    print(f"找到 {len(scene_images)} 張場景圖片：")
    for img in scene_images:
        print(f"  - {os.path.basename(img)}")

    # --- 呼叫 GPT ---
    result_text = call_chatgpt(scene_images, reference_image_path, group_name)

    print("ChatGPT 回傳的原始結果：")
    print("-" * 50)
    print(result_text)
    print("-" * 50)

    # --- 解析 JSON ---
    clean_text = clean_json_text(result_text)

    try:
        result_json = json.loads(clean_text)
        print("\nJSON 解析成功！")
    except json.JSONDecodeError as e:
        print(f"\n警告：{group_name} 回傳內容不是合法 JSON：{e}")
        print("請檢查上方原始回傳內容。")
        return

    # --- 建立 results 資料夾 ---
    if not os.path.exists(RESULT_FOLDER):
        os.makedirs(RESULT_FOLDER)

    # --- 每組輸出不同檔名 ---
    output_filename = f"inventory_result_{group_name}.json"
    output_path = os.path.join(RESULT_FOLDER, output_filename)

    save_json(result_json, output_path)

    # --- 印出表格 ---
    print_table(result_json)

    # --- 第 2 階段新增：讀取 GPT 是否建議補拍 ---
    need_more = result_json.get("need_more_photos", {})
    suggest_reshoot = need_more.get("建議補拍", False)

    if suggest_reshoot == True or suggest_reshoot == "true" or suggest_reshoot == "是" or suggest_reshoot == "需要":
        print("\n" + "!" * 60)
        print(f"{group_name}：GPT 建議補拍照片")
        print("原因：", need_more.get("原因", "未提供原因"))

        angles = need_more.get("建議補拍角度", [])
        if angles:
            print("建議補拍角度：")
            for angle in angles:
                print("  -", angle)

        print("補拍重點：", need_more.get("補拍重點", "未提供補拍重點"))
        print("!" * 60)
    else:
        print(f"\n{group_name}：GPT 判斷目前照片足夠，不需要補拍。")

    print(f"\n{group_name} 處理完成！")

def print_table(inventory_data):
    """
    用簡單表格印出盤點結果，以及是否建議補拍。
    """
    items = inventory_data.get("inventory", [])

    print("\n" + "=" * 80)
    print("盤點結果")
    print("=" * 80)

    if not items:
        print("沒有辨識到任何物品。")
    else:
        print(f"{'物品種類':<12} | {'盤點數量':<8} | {'AI備註'}")
        print("-" * 80)

        for item in items:
            name = item.get("物品種類", "未知")
            count = item.get("辨識出的物品數量", "?")
            note = item.get("AI備註", "")
            print(f"{name:<12} | {str(count):<8} | {note}")

    print("=" * 80)

    # 印出是否建議補拍
    need_more = inventory_data.get("need_more_photos", {})

    print("\n是否建議補拍")
    print("-" * 80)

    if need_more:
        suggest = need_more.get("建議補拍", False)
        reason = need_more.get("原因", "")
        angles = need_more.get("建議補拍角度", [])
        focus = need_more.get("補拍重點", "")

        print("建議補拍：", suggest)
        print("原因：", reason)

        if angles:
            print("建議補拍角度：")
            for angle in angles:
                print("  -", angle)

        print("補拍重點：", focus)
    else:
        print("GPT 沒有回傳 need_more_photos 欄位。")

    # 印出整體備註
    overall = inventory_data.get("overall_note", "")
    if overall:
        print("\n整體備註：", overall)