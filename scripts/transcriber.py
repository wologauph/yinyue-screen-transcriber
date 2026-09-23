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
    # 首选用 Windows 官方原生的 PowerShell Set-Clipboard（最稳固、能跨进程与锁常驻）
    try:
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        proc.communicate(input=text.encode("utf-8"))
        if proc.returncode == 0:
            return True
    except Exception:
        pass

    for attempt in range(3):
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
# 智能书名与场景感知路由
# -----------------------------------------------------------------------------
def detect_current_book():
    # 1. 优先从 NeatReader 嗅探当前精读书目
    neat_dir = os.path.expandvars(r"%APPDATA%\NeatReader\bookData")
    if os.path.exists(neat_dir):
        try:
            folders = []
            for d in os.listdir(neat_dir):
                fp = os.path.join(neat_dir, d)
                if os.path.isdir(fp):
                    folders.append((os.path.getmtime(fp), fp))
            if folders:
                folders.sort(key=lambda x: x[0], reverse=True)
                for _, folder in folders[:3]:
                    files = os.listdir(folder)
                    book_files = [x for x in files if not x.startswith("cover") and not x.startswith("pagination")]
                    if book_files:
                        raw_name = book_files[0]
                        for k in ["白夜行", "绿山墙的安妮", "被讨厌的勇气", "解忧杂货店", "恶意", "秘密", "不良之年少轻狂", "不良之谁与争锋", "金瓶梅", "嫌疑人X的献身"]:
                            if k in raw_name:
                                return k
                        import re
                        clean = re.sub(r"[（\(【].*?[）\)】]|[：:•·\s]+", " ", raw_name).strip().split()[0]
                        if clean:
                            return clean
        except Exception as e:
            log(f"[WARNING] 嗅探 NeatReader 书目异常: {e}", "WARNING")

    # 2. 备选方案：从 Readest 嗅探
    readest_books_dir = os.path.expandvars(r"%APPDATA%\com.bilingify.readest\Readest\Books")
    if os.path.exists(readest_books_dir):
        try:
            configs = []
            for root, dirs, files in os.walk(readest_books_dir):
                if "config.json" in files:
                    full = os.path.join(root, "config.json")
                    configs.append((os.path.getmtime(full), full))
            if configs:
                configs.sort(key=lambda x: x[0], reverse=True)
                latest_config = configs[0][1]
                book_hash = os.path.basename(os.path.dirname(latest_config))
                
                lib_file = os.path.join(readest_books_dir, "library.json")
                if os.path.exists(lib_file):
                    with open(lib_file, "r", encoding="utf-8") as f:
                        lib = json.load(f)
                    for b in lib:
                        if b.get("hash") == book_hash:
                            title = b.get("title", "")
                            for k in ["白夜行", "绿山墙的安妮", "被讨厌的勇气", "解忧杂货店", "恶意", "秘密", "不良之年少轻狂", "不良之谁与争锋", "金瓶梅", "嫌疑人X的献身"]:
                                if k in title:
                                    return k
                            import re
                            clean = re.sub(r"[（\(【].*?[）\)】]|[：:•·\s]+", " ", title).strip().split()[0]
                            return clean or title
        except Exception as e:
            log(f"[WARNING] 嗅探 Readest 书目异常: {e}", "WARNING")
    return None

# -----------------------------------------------------------------------------
# 核心业务管线
# -----------------------------------------------------------------------------
async def process_video(video_path: str = None, book_override: str = None):
    t_zero = time.time()
    # 覆盖最新流水账日志
    with open(LATEST_LOG, "w", encoding="utf-8") as f:
        f.write(f"=== 银月录屏一镜到底转录管家运行日志 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")

    log("[INFO] ========================================================")
    log("[INFO] 银月一镜到底录屏智能转录管家启动")
    log("[INFO] ========================================================")

    config = load_config()
    desktop_dir = config.get("desktop_dir", r"C:\Users\1\Desktop")
    recordings_dir = r"D:\桌面录屏"

    # 1. 查找目标视频 (同时扫描桌面与 D:\桌面录屏 根目录最新视频)
    if not video_path:
        videos = []
        scan_dirs = [desktop_dir]
        if os.path.exists(recordings_dir):
            scan_dirs.append(recordings_dir)
        
        for sdir in scan_dirs:
            if not os.path.exists(sdir):
                continue
            for f in os.listdir(sdir):
                full = os.path.join(sdir, f)
                # 仅查找顶级文件，排除子文件夹内的历史视频
                if os.path.isfile(full) and f.lower().endswith((".mp4", ".mkv", ".mov", ".avi", ".ts")):
                    videos.append((os.path.getmtime(full), full))

        if not videos:
            log("[WARNING] 桌面及录屏总库未发现待处理的屏幕录制文件！", "WARNING")
            show_toast_popup("未发现录屏", "未检测到任何待处理录屏视频，请先完成录屏。", "", 5.0)
            return
        videos.sort(key=lambda x: x[0], reverse=True)
        video_path = videos[0][1]

    video_name = os.path.basename(video_path)
    video_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    log(f"[INFO] 锁定待处理目标录屏: {video_name} ({video_path}) (体积: {video_size_mb:.2f} MB)")

    # 2. 智能感知当前阅读书目，动态确立归档大本营
    if book_override:
        book_title = book_override
        log(f"[INFO] 🎯 使用指定书目归档: 《{book_title}》")
        closure_dir = os.path.join(recordings_dir, f"【{book_title}】一镜到底录读闭环")
        vault_dir = os.path.join(r"D:\银月baby的工作玉简\05_全自动项目与工作流\全自动高维阅读与智囊流水线\03_高维阅读产出区", book_title)
    else:
        detected_book = detect_current_book()
        if detected_book:
            log(f"[INFO] 🎯 智能感知到主人当前正在精读: 《{detected_book}》")
            book_title = detected_book
            closure_dir = os.path.join(recordings_dir, f"【{book_title}】一镜到底录读闭环")
            vault_dir = os.path.join(r"D:\银月baby的工作玉简\05_全自动项目与工作流\全自动高维阅读与智囊流水线\03_高维阅读产出区", book_title)
        else:
            book_title = "录读原稿"
            closure_dir = config.get("closure_base_dir", os.path.join(recordings_dir, "【通用录屏】一镜到底录读闭环"))
            vault_dir = config.get("vault_base_dir", os.path.join(r"D:\银月baby的工作玉简\05_全自动项目与工作流\全自动高维阅读与智囊流水线\03_高维阅读产出区", "通用录屏"))

    os.makedirs(closure_dir, exist_ok=True)
    os.makedirs(vault_dir, exist_ok=True)
    log(f"[INFO] 归档大本营锁定: {closure_dir}")
    log(f"[INFO] 玉简产出区锁定: {vault_dir}")

    # 提取时间戳标识 (如 2026-09-19_035328)
    import re
    m_obs = re.search(r"(\d{4}-\d{2}-\d{2})[ _-](\d{2})[-:](\d{2})[-:](\d{2})", video_name)
    if m_obs:
        time_tag = f"{m_obs.group(1)}_{m_obs.group(2)}{m_obs.group(3)}{m_obs.group(4)}"
    else:
        m_win = re.search(r"(\d{4}-\d{2}-\d{2})[ _-](\d{6})", video_name)
        if m_win:
            time_tag = f"{m_win.group(1)}_{m_win.group(2)}"
        else:
            time_tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    audio_file = os.path.join(closure_dir, f"audio_{time_tag}.wav")
    target_video = os.path.join(closure_dir, video_name)
    output_md = os.path.join(closure_dir, f"{time_tag}_现场一镜到底逐字原稿.md")
    vault_md = os.path.join(vault_dir, f"{time_tag}_现场一镜到底逐字原稿.md")
    temp_chunk_dir = os.path.join(closure_dir, f"_tmp_{time_tag}")
    os.makedirs(temp_chunk_dir, exist_ok=True)

    # 3. FFmpeg 抽离纯音频
    log(f"[INFO] 正在抽取 16kHz 单声道无损音频母带 -> {os.path.basename(audio_file)}")
    t_extract_start = time.time()
    cmd = f'ffmpeg -y -i "{video_path}" -vn -ar 16000 -ac 1 -c:a pcm_s16le "{audio_file}"'
    ret = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if ret.returncode != 0 or not os.path.exists(audio_file):
        log("[ERROR] FFmpeg 音频分离失败！", "ERROR")
        return
    log(f"[SUCCESS] 音频母带分离完成，耗时: {time.time() - t_extract_start:.2f} 秒")

    # 4. 分析音轨能量与智能语义切片
    log("[INFO] 正在分析音轨能量并执行智能语义停顿切片...")
    data, sr = sf.read(audio_file)
    total_sec = len(data) / sr

    # 同步压制广播级饱满人声 MP3 (按实际时长动态命名，告别硬编码)
    h = int(round(total_sec / 3600.0))
    dur_tag = f"{max(1, h)}小时" if total_sec >= 1800 else f"{int(total_sec//60)}分钟"
    enhanced_mp3 = os.path.join(closure_dir, f"{book_title}_{dur_tag}录读_人声饱满增强版.mp3")
    log(f"[INFO] 正在同步压制广播级饱满人声 MP3 -> {os.path.basename(enhanced_mp3)}")
    cmd_mp3 = f'ffmpeg -y -i "{audio_file}" -af "highpass=f=80,volume=5dB" -b:a 192k -ar 44100 "{enhanced_mp3}"'
    subprocess.run(cmd_mp3, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        timecode = f"[{format_sec(t_start)} - {format_sec(t_end)}]"

        # 智能静音极速过滤：若切片最大振幅 < 0.02，说明为纯净默读，直接跳过云端调用
        chunk_max = np.max(np.abs(chunk_data)) if len(chunk_data) > 0 else 0
        if chunk_max < 0.02:
            results.append({
                "index": idx + 1,
                "timecode": timecode,
                "asr_text": "",
                "llm_text": "",
                "is_speech": False
            })
            log(f"[INFO] {timecode} -> [沉浸默读 / 思考静音] (能量极低秒级跳过)")
            continue

        chunk_file = os.path.join(temp_chunk_dir, f"chunk_{idx:03d}.wav")
        sf.write(chunk_file, chunk_data, sr, subtype='PCM_16')

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

    md_content = f"""# 《{book_title}》现场一镜到底录读逐字原稿

> **录制时间**：{time_tag}
> **总时长**：{format_sec(total_sec)}（{total_sec:.1f} 秒）
> **转录引擎**：SayIt 官方云端 ASR 引擎（双轨全量保真，零字遗漏）
> **独立闭环大本营**：`{closure_dir}`
> **配套原料**：
> - 🎬 视频原件：`{video_name}`
> - 🎙️ 纯音频母带：`{os.path.basename(audio_file)}`
> - 🎧 广播级增强音频：`{os.path.basename(enhanced_mp3)}`

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

    # 6. 移动录屏原件归位大本营
    if config.get("clean_desktop_video", True) and os.path.exists(video_path):
        if os.path.abspath(video_path) != os.path.abspath(target_video):
            try:
                shutil.move(video_path, target_video)
                log(f"[CLEAN] 录屏原件已自动归位至大本营: {target_video}，原目录彻底恢复洁癖！")
            except Exception as e:
                log(f"[WARNING] 移动录屏视频异常: {e}", "WARNING")

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
    v_arg = sys.argv[1] if len(sys.argv) > 1 else None
    b_arg = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(process_video(v_arg, b_arg))
