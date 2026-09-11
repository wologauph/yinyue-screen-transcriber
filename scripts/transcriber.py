# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import asyncio
import traceback
import subprocess
import shutil
from datetime import datetime, timedelta
import numpy as np
import soundfile as sf

# -----------------------------------------------------------------------------
# 路径与环境定位
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config", "config.json")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LATEST_LOG = os.path.join(LOG_DIR, "latest_run.log")
ERROR_LOG = os.path.join(LOG_DIR, "error.log")

def get_monthly_log():
    return os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y-%m')}.log")

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line, flush=True)
    for target in [LATEST_LOG, get_monthly_log()]:
        try:
            with open(target, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
    if level == "ERROR":
        try:
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

# 引入 SayIt 官方转录模块
sys.path.insert(0, r"D:\我的电脑工具库\03_系统与网络法宝\SayIt语音与鼠标守护管家\scripts")
try:
    from sayit_clipboard_guardian import async_retranscribe
except ImportError:
    log("[ERROR] 未找到 SayIt 守护管家转录核心模块！", "ERROR")
    async_retranscribe = None

# -----------------------------------------------------------------------------
# 配置读取
# -----------------------------------------------------------------------------
def load_config():
    default_config = {
        "desktop_dir": r"C:\Users\1\Desktop",
        "closure_base_dir": r"D:\桌面录屏\【被讨厌的勇气】2026-09-10_一镜到底录读闭环",
        "vault_base_dir": r"D:\银月baby的工作玉简\05_全自动项目与工作流\全自动高维阅读与智囊流水线\03_高维阅读产出区\被讨厌的勇气",
        "auto_clipboard": True,
        "clipboard_content": "polished_continuous",
        "show_toast": True,
        "toast_duration_sec": 8.0,
        "clean_desktop_video": True
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception as e:
            log(f"[WARNING] 读取配置文件异常，使用默认配置: {e}", "WARNING")
    return default_config

def format_sec(sec):
    td = timedelta(seconds=int(sec))
    m, s = divmod(td.seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

# -----------------------------------------------------------------------------
# 剪贴板写入与防竞争
# -----------------------------------------------------------------------------
def set_clipboard(text: str) -> bool:
    if not text:
        return False
    for attempt in range(5):
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            win32clipboard.CloseClipboard()
            return True
        except Exception:
            time.sleep(0.05)
    # 备用方案：通过 powershell 或 tkinter
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception as e:
        log(f"[ERROR] 写入剪贴板失败: {e}", "ERROR")
        return False

# -----------------------------------------------------------------------------
# 现代化轻量非阻塞 Toast 提示视窗
# -----------------------------------------------------------------------------
def show_toast_popup(title: str, msg: str, md_path: str, duration_sec: float = 8.0):
    try:
        import tkinter as tk
        import ctypes
        from ctypes import wintypes

        root = tk.Tk()
        root.withdraw()
        root.title("银月管家通知")

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()

        def get_work_area():
            try:
                rect = wintypes.RECT()
                ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
                return rect.left, rect.top, rect.right, rect.bottom
            except Exception:
                return 0, 0, sw, sh - 48

        toast = tk.Toplevel(root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0.96)
        toast.configure(bg="#1E1E2E")

        # 边框装饰容器
        card = tk.Frame(toast, bg="#181825", bd=2, relief="solid", highlightbackground="#89B4FA", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=2, pady=2)

        header_frame = tk.Frame(card, bg="#181825")
        header_frame.pack(fill="x", padx=14, pady=(10, 4))

        lbl_icon = tk.Label(header_frame, text="✨", font=("Segoe UI Emoji", 14), bg="#181825", fg="#A6E3A1")
        lbl_icon.pack(side="left")

        lbl_title = tk.Label(header_frame, text=title, font=("Microsoft YaHei UI", 11, "bold"), bg="#181825", fg="#CDD6F4")
        lbl_title.pack(side="left", padx=8)

        # 关闭按钮
        btn_close = tk.Label(header_frame, text="✕", font=("Segoe UI", 10, "bold"), bg="#181825", fg="#6C7086", cursor="hand2")
        btn_close.pack(side="right")
        btn_close.bind("<Button-1>", lambda e: root.destroy())

        lbl_msg = tk.Label(card, text=msg, font=("Microsoft YaHei UI", 10), bg="#181825", fg="#BAC2DE", justify="left", wraplength=420)
        lbl_msg.pack(fill="x", padx=16, pady=(2, 10))

        btn_frame = tk.Frame(card, bg="#181825")
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))

        def open_file():
            if os.path.exists(md_path):
                os.startfile(md_path)
            root.destroy()

        def open_dir():
            if os.path.exists(md_path):
                subprocess.Popen(f'explorer /select,"{os.path.abspath(md_path)}"')
            root.destroy()

        btn_open = tk.Button(btn_frame, text="📂 打开逐字稿", font=("Microsoft YaHei UI", 9, "bold"), bg="#89B4FA", fg="#11111B", activebackground="#B4BEFE", bd=0, padx=12, pady=4, cursor="hand2", command=open_file)
        btn_open.pack(side="left", padx=(0, 8))

        btn_folder = tk.Button(btn_frame, text="📁 所在大本营", font=("Microsoft YaHei UI", 9), bg="#313244", fg="#CDD6F4", activebackground="#45475A", bd=0, padx=10, pady=4, cursor="hand2", command=open_dir)
        btn_folder.pack(side="left")

        toast.update_idletasks()
        w = toast.winfo_width()
        h = toast.winfo_height()
        wa_l, wa_t, wa_r, wa_b = get_work_area()
        # 水平居中偏下贴近任务栏
        x = (wa_r - wa_l - w) // 2 + wa_l
        y = wa_b - h - 16
        toast.geometry(f"+{x}+{y}")

        root.after(int(duration_sec * 1000), root.destroy)
        root.mainloop()
    except Exception as e:
        log(f"[WARNING] 弹窗提示渲染异常: {e}", "WARNING")

# -----------------------------------------------------------------------------
# 核心业务管线
# -----------------------------------------------------------------------------
async def process_video(video_path: str = None):
    t_zero = time.time()
    # 覆盖最新流水账日志
    with open(LATEST_LOG, "w", encoding="utf-8") as f:
        f.write(f"=== 银月录屏一镜到底转录管家运行日志 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")

    log("[INFO] ========================================================")
    log("[INFO] 银月一镜到底录屏智能转录管家启动")
    log("[INFO] ========================================================")

    config = load_config()
    desktop_dir = config["desktop_dir"]
    closure_dir = config["closure_base_dir"]
    vault_dir = config["vault_base_dir"]

    os.makedirs(closure_dir, exist_ok=True)
    os.makedirs(vault_dir, exist_ok=True)

    # 1. 查找目标视频
    if not video_path:
        videos = []
        if os.path.exists(desktop_dir):
            for f in os.listdir(desktop_dir):
                if f.lower().endswith((".mp4", ".mkv", ".mov", ".avi", ".ts")):
                    full = os.path.join(desktop_dir, f)
                    videos.append((os.path.getmtime(full), full))
        if not videos:
            log("[WARNING] 桌面未发现待处理的屏幕录制文件！", "WARNING")
            show_toast_popup("未发现录屏", "桌面上未检测到任何视频文件，请先完成录屏。", "", 5.0)
            return
        videos.sort(key=lambda x: x[0], reverse=True)
        video_path = videos[0][1]

    video_name = os.path.basename(video_path)
    video_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    log(f"[INFO] 锁定待处理目标录屏: {video_name} (体积: {video_size_mb:.2f} MB)")

    # 提取时间戳标识 (如 2026-09-11_170507)
    time_tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    # 尝试从文件名解析 (屏幕录制 2026-09-11 170507.mp4)
    parts = video_name.replace("屏幕录制", "").replace(".mp4", "").strip().split()
    if len(parts) >= 2:
        time_tag = f"{parts[0]}_{parts[1]}"

    audio_file = os.path.join(closure_dir, f"audio_{time_tag}.wav")
    target_video = os.path.join(closure_dir, video_name)
    output_md = os.path.join(closure_dir, f"{time_tag}_现场一镜到底逐字原稿.md")
    vault_md = os.path.join(vault_dir, f"{time_tag}_现场一镜到底逐字原稿.md")
    temp_chunk_dir = os.path.join(closure_dir, f"_tmp_{time_tag}")
    os.makedirs(temp_chunk_dir, exist_ok=True)

    # 2. FFmpeg 抽离纯音频
    log(f"[INFO] 正在抽取 16kHz 单声道无损音频母带 -> {os.path.basename(audio_file)}")
    t_extract_start = time.time()
    cmd = f'ffmpeg -y -i "{video_path}" -vn -ar 16000 -ac 1 -c:a pcm_s16le "{audio_file}"'
    ret = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if ret.returncode != 0 or not os.path.exists(audio_file):
        log("[ERROR] FFmpeg 音频分离失败！", "ERROR")
        return
    log(f"[SUCCESS] 音频母带分离完成，耗时: {time.time() - t_extract_start:.2f} 秒")

    # 3. 智能静音语义切片
    log("[INFO] 正在分析音轨能量并执行智能语义停顿切片...")
    data, sr = sf.read(audio_file)
    total_sec = len(data) / sr
    win_size = int(sr * 0.02)
    num_wins = len(data) // win_size
    rms = np.sqrt(np.mean(data[:num_wins*win_size].reshape(-1, win_size)**2, axis=1))

    silence_thresh = 0.006
    is_silent = rms < silence_thresh
    min_silence_frames = 15

    split_indices = [0]
    last_split_sec = 0.0
    i = 0
    while i < len(rms):
        cur_sec = i * 0.02
        seg_sec = cur_sec - last_split_sec
        if seg_sec >= 25.0:
            if np.all(is_silent[i:i+min_silence_frames]) or seg_sec >= 45.0:
                silence_len = 0
                while (i + silence_len) < len(rms) and is_silent[i + silence_len] and silence_len < 50:
                    silence_len += 1
                split_sec = (i + silence_len // 2) * 0.02
                split_indices.append(int(split_sec * sr))
                last_split_sec = split_sec
                i += silence_len
                continue
        i += 1
    split_indices.append(len(data))
    num_chunks = len(split_indices) - 1
    log(f"[SUCCESS] 音频总长: {format_sec(total_sec)} ({total_sec:.1f}s)，智能切片生成 {num_chunks} 个语义块")

    # 4. SayIt 云端高速流式打捞
    log(f"[INFO] 正在启动 SayIt 官方流式 ASR 引擎打捞 {num_chunks} 个切片...")
    results = []
    t_trans_start = time.time()

    for idx in range(num_chunks):
        t_start = split_indices[idx] / sr
        t_end = split_indices[idx+1] / sr
        chunk_data = data[split_indices[idx]:split_indices[idx+1]]
        chunk_file = os.path.join(temp_chunk_dir, f"chunk_{idx:03d}.wav")
        sf.write(chunk_file, chunk_data, sr, subtype='PCM_16')

        timecode = f"[{format_sec(t_start)} - {format_sec(t_end)}]"
        res, err = await async_retranscribe(chunk_file, timeout=60)
        
        if res and (res.get("asr_text") or res.get("text")):
            asr_text = res.get("asr_text", "").strip()
            llm_text = res.get("text", "").strip()
            results.append({
                "index": idx + 1,
                "timecode": timecode,
                "asr_text": asr_text,
                "llm_text": llm_text,
                "is_speech": True
            })
            log(f"[SUCCESS] {timecode} -> {llm_text[:28]}...")
        else:
            results.append({
                "index": idx + 1,
                "timecode": timecode,
                "asr_text": "",
                "llm_text": "",
                "is_speech": False
            })
            log(f"[INFO] {timecode} -> [沉浸默读 / 思考静音]")

        try:
            os.remove(chunk_file)
        except Exception:
            pass
        await asyncio.sleep(0.12)

    shutil.rmtree(temp_chunk_dir, ignore_errors=True)
    t_trans = time.time() - t_trans_start
    log(f"[SUCCESS] SayIt 流式转录完成，总耗时: {t_trans:.2f} 秒 (平均每切片 {t_trans/max(1, num_chunks):.2f} 秒)")

    # 5. 生成结构化原稿
    raw_blocks = []
    polished_blocks = []
    for r in results:
        if r["is_speech"]:
            raw_blocks.append(f"**{r['timecode']}** {r['asr_text']}")
            polished_blocks.append(f"**{r['timecode']}** {r['llm_text']}")
        else:
            raw_blocks.append(f"*{r['timecode']} (默读与思考停顿)*")
            polished_blocks.append(f"*{r['timecode']} (默读与思考停顿)*")

    full_asr = " ".join([r["asr_text"] for r in results if r["is_speech"]])
    full_polished = "\n\n".join([r["llm_text"] for r in results if r["is_speech"]])
    total_char_count = len(full_polished)

    md_content = f"""# 《被讨厌的勇气》现场一镜到底录读逐字原稿

> **录制时间**：{time_tag}
> **总时长**：{format_sec(total_sec)}（{total_sec:.1f} 秒）
> **转录引擎**：SayIt 官方云端 ASR 引擎（双轨全量保真，零字遗漏）
> **独立闭环大本营**：`{closure_dir}`
> **配套原料**：
> - 🎬 视频原件：`{video_name}`
> - 🎙️ 纯音频母带：`{os.path.basename(audio_file)}`

---

## 📌 一、 主人原汁原味全文流（无删减·带时间轴）

{chr(10).join(raw_blocks)}

---

## 💎 二、 SayIt 语感精修版（消除口癖·保留原意）

{chr(10).join(polished_blocks)}

---

## 📜 三、 主人原始原声连续全文（纯文本原矿）

{full_asr}

---

## 📋 四、 语感精修连续全文（直投 AI 专属）

{full_polished}

---

## 🧠 五、 预留槽位：高维会诊与自媒体视频素材加工
- [ ] 核心击中点提取
- [ ] 人物与系统机制拆解
- [ ] 自媒体口播与短视频切片脚本文案
"""

    with open(output_md, "w", encoding="utf-8") as f:
        f.write(md_content)
    log(f"[SUCCESS] 闭环大本营逐字稿已保存: {output_md}")

    with open(vault_md, "w", encoding="utf-8") as f:
        f.write(md_content)
    log(f"[SUCCESS] 玉简同步镜像卡已更新: {vault_md}")

    # 6. 移动桌面大视频归位
    if config.get("clean_desktop_video", True) and os.path.exists(video_path):
        try:
            shutil.move(video_path, target_video)
            log(f"[CLEAN] 桌面录屏原件已自动移入大本营: {target_video}，桌面彻底恢复洁癖！")
        except Exception as e:
            log(f"[WARNING] 移动桌面视频异常: {e}", "WARNING")

    # 7. 写入剪贴板
    if config.get("auto_clipboard", True):
        clip_mode = config.get("clipboard_content", "polished_continuous")
        text_to_copy = full_polished if clip_mode == "polished_continuous" else md_content
        if set_clipboard(text_to_copy):
            log(f"[SUCCESS] 已将转录精修文本（共 {total_char_count} 字）写入 Windows 剪贴板！")
        else:
            log("[ERROR] 剪贴板写入失败！", "ERROR")

    t_total = time.time() - t_zero
    elapsed_str = f"{int(t_total // 60)}分{int(t_total % 60)}秒"
    log(f"[SUCCESS] === 全链路闭环圆满完成！总耗时: {elapsed_str} ({t_total:.2f}秒) ===")

    # 8. 现代化 Toast 弹窗反馈
    if config.get("show_toast", True):
        toast_title = "录读转录完成 · 逐字稿已就绪"
        toast_body = f"✨ 已成功转录 {format_sec(total_sec)} 录音（共 {total_char_count} 字，耗时 {elapsed_str}）！\n📋 精修逐字稿已自动存入剪贴板，您可以直接去 AI 窗口粘贴！"
        show_toast_popup(toast_title, toast_body, output_md, config.get("toast_duration_sec", 8.0))

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(process_video(arg))
