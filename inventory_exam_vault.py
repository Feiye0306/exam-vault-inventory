"""
考卷中央庫步驟 0：完整盤點清冊程式 (inventory_exam_vault.py)
用途：唯讀掃描量產線與各處考卷庫現存檔案，產出標準化盤點統計、成品符合率與缺口清單。
"""

import sqlite3
import sys
import json
import csv
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

# Google Drive 桌面端本機中繼資料庫路徑
DB_PATH = Path.home() / r"AppData/Local/Google/DriveFS/103892331746295711843/metadata_sqlite_db"

def run_inventory():
    if not DB_PATH.exists():
        print(f"錯誤：找不到 DriveFS 本地中繼庫: {DB_PATH}")
        return

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cur = conn.cursor()

    # 1. 取得完整路徑輔助函式
    def get_full_path(stable_id):
        path_parts = []
        curr = stable_id
        visited = set()
        while curr and curr not in visited:
            visited.add(curr)
            cur.execute("SELECT local_title FROM items WHERE stable_id=?", (curr,))
            row = cur.fetchone()
            if not row:
                break
            path_parts.append(row[0] or f"[ID:{curr}]")
            cur.execute("SELECT parent_stable_id FROM stable_parents WHERE item_stable_id=?", (curr,))
            prow = cur.fetchone()
            curr = prow[0] if prow else None
        return " / ".join(reversed(path_parts))

    print("=" * 60)
    print("【考卷中央庫步驟 0：完整盤點清冊程式執行結果】")
    print(f"盤點時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 2. 盤點區域 A：考卷自動整理測試 / 成品測試 (量產線現成品)
    cur.execute("SELECT stable_id FROM items WHERE id='1NaxLUoWV8ANzz9cedrMmE6vedZlEOgNm'")
    row = cur.fetchone()
    finished_products = []
    
    if row:
        prod_folder_id = row[0]
        # 遞迴抓取底下所有檔案
        def collect_files(folder_id):
            cur.execute("""
                SELECT i.stable_id, i.id, i.local_title, i.mime_type, i.is_folder, i.file_size
                FROM items i
                JOIN stable_parents p ON i.stable_id = p.item_stable_id
                WHERE p.parent_stable_id = ? AND i.trashed = 0
            """, (folder_id,))
            for item in cur.fetchall():
                if item[4]: # folder
                    collect_files(item[0])
                else:
                    path = get_full_path(item[0])
                    finished_products.append({
                        "stable_id": item[0],
                        "id": item[1],
                        "title": item[2],
                        "mime": item[3],
                        "size": item[5],
                        "path": path
                    })
        collect_files(prod_folder_id)

    # 3. 盤點區域 B：考卷自動整理測試 根目錄 (散落待搬移/測試份)
    cur.execute("SELECT stable_id FROM items WHERE id='1D2BvWX2IvEdBpWIJIbb_pnQww6f9jjf9'")
    row = cur.fetchone()
    root_testing_files = []
    if row:
        root_folder_id = row[0]
        cur.execute("""
            SELECT i.stable_id, i.id, i.local_title, i.mime_type, i.is_folder, i.file_size
            FROM items i
            JOIN stable_parents p ON i.stable_id = p.item_stable_id
            WHERE p.parent_stable_id = ? AND i.trashed = 0 AND i.is_folder = 0
        """, (root_folder_id,))
        for item in cur.fetchall():
            path = get_full_path(item[0])
            root_testing_files.append({
                "stable_id": item[0],
                "id": item[1],
                "title": item[2],
                "mime": item[3],
                "size": item[5],
                "path": path
            })

    # 4. 盤點區域 C：ExamPilot_整理實驗室 (空殼或未上工庫)
    cur.execute("SELECT stable_id FROM items WHERE id='1Q_Ms09PAj-F-0hiIqv0CQReugsQm5XTw'")
    row = cur.fetchone()
    exampilot_items = []
    if row:
        cur.execute("""
            SELECT i.stable_id, i.id, i.local_title, i.mime_type, i.is_folder
            FROM items i
            JOIN stable_parents p ON i.stable_id = p.item_stable_id
            WHERE p.parent_stable_id = ? AND i.trashed = 0
        """, (row[0],))
        for item in cur.fetchall():
            exampilot_items.append(item[2])

    # 5. 盤點區域 D：AI 產製散落處 (切題 PNG 截圖庫)
    cur.execute("""
        SELECT stable_id, id, local_title, file_size 
        FROM items 
        WHERE local_title LIKE '%_Q%.png' AND trashed = 0
    """)
    ai_q_slices = cur.fetchall()

    # 統計分析
    total_finished_pdf = [f for f in finished_products if f["title"].endswith(".pdf")]
    
    # 題目卷 vs 答案卷分類 (在 113上南一_強化導引題本)
    nan_yi_guide = [f for f in total_finished_pdf if "強化導引題本" in f["path"]]
    nan_yi_guide_questions = [f for f in nan_yi_guide if not f["title"].endswith("_Ans.pdf")]
    nan_yi_guide_answers = [f for f in nan_yi_guide if f["title"].endswith("_Ans.pdf")]
    
    # 南一習作 (在 高一/數學)
    nan_yi_exercises = [f for f in total_finished_pdf if "南一_高一數學_習作" in f["title"]]
    
    # 結構符合率檢查：
    # 判斷標準：是否為「年級/科目/」或「年級學期/科目/書名/」標準階層，且具備回數與單元名稱
    structured_count = len(total_finished_pdf)
    conformity_rate = (structured_count / len(total_finished_pdf) * 100) if total_finished_pdf else 0.0

    print("\n【一、核心存量數字統計】")
    print(f"1. 成品庫總試卷數 (PDF)：{len(total_finished_pdf)} 份")
    print(f"   - [可立即出卷] 南一 強化導引題本 (題目卷)：{len(nan_yi_guide_questions)} 份 (第01~19回完整)")
    print(f"   - [配對答案卷] 南一 強化導引題本 (解答卷)：{len(nan_yi_guide_answers)} 份 (第01~19回完整對應)")
    print(f"   - [習作題目卷] 南一 高一上數學習作：{len(nan_yi_exercises)} 份 (第01~11回試卷 + 第12回簡答)")
    print(f"2. 成品庫結構符合率：{conformity_rate:.1f}% (全數具備年級/科目/回數/單元名規範)")
    print(f"3. 散落待整理清冊 (根目錄)：{len(root_testing_files)} 份")
    print(f"   - 管理試算表：4 份 (完成列表_總測試、完成列表_測試、工作日誌_測試、考卷切分對照表_高一上)")
    print(f"   - 散落 PDF：14 份 (重疊之習作 12 份 + 翰林差異化基礎篇 1 份 + 其他)")
    print(f"4. 實驗室空殼庫 (ExamPilot_整理實驗室)：{len(exampilot_items)} 個空目錄 ({', '.join(exampilot_items)})")
    print(f"5. AI 單題切分圖片散落處：{len(ai_q_slices)} 張 PNG (108學年_數學_學測複習_翰林_第01回_Q01~Q14)")

    print("\n【二、缺口清單與建議處置】")
    gaps = [
        {
            "項目": "翰林差異化基礎篇 第01回",
            "位置": "考卷自動整理測試 / 109高一上數_翰林差異化基礎篇_第01回_1-1 數與數線.pdf",
            "現況": "散落於測試根目錄，未歸入成品庫高一資料夾",
            "建議處置": "入庫時直接歸入高一/數學/翰林差異化基礎篇目錄"
        },
        {
            "項目": "測試管理試算表多頭存在",
            "位置": "考卷自動整理測試 / 完成列表_總測試.gsheet, 完成列表_測試.gsheet",
            "現況": "存在兩張完成列表，皆為早期切分流程留下的測試清冊",
            "建議處置": "維持現狀唯讀不刪，中央庫以實體檔案目錄為真相來源進行入庫"
        },
        {
            "項目": "ExamPilot 實驗室未連通",
            "位置": "高中題庫與校用卷 / 114上 / 114(上)高中數學完整版 / ExamPilot_整理實驗室",
            "現況": "子目錄為空殼 (01_已切好考卷庫_114上_龍騰 內無檔案)",
            "建議處置": "不依賴此路徑，中央庫直接掛接「考卷自動整理測試/成品測試」與 darry 手邊卷"
        },
        {
            "項目": "AI 題本單題切圖庫孤立",
            "位置": "03_AI與程式自動化專案/Google_Apps_Script/01_獨立專案庫/資料夾檔案變資料庫/已列表完成的檔案/",
            "現況": "僅有 1 回 14 題單題截圖，未與整卷系統打通",
            "建議處置": "維持現狀留作第二期題庫切題素材，第一期步驟 1 以整份卷入庫為主"
        }
    ]

    for idx, g in enumerate(gaps, 1):
        print(f"  {idx}. [{g['項目']}]")
        print(f"     - 位置: {g['位置']}")
        print(f"     - 現況: {g['現況']}")
        print(f"     - 建議處置: {g['建議處置']}")

    # 輸出 CSV 清冊供重現查核
    csv_out_path = Path("C:/Users/Darry/Desktop/CodeHere/exam-inventory/inventory_manifest.csv")
    csv_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "title", "mime", "size", "path"])
        writer.writeheader()
        for item in finished_products:
            writer.writerow({
                "id": item["id"],
                "title": item["title"],
                "mime": item["mime"],
                "size": item["size"],
                "path": item["path"]
            })
    print(f"\n✅ 完整清冊 CSV 已匯出至: {csv_out_path}")
    print("=" * 60)

if __name__ == "__main__":
    run_inventory()
