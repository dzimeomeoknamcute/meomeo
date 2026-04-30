import os
import sys
import time
import json
import random
import hashlib
import threading
import re
import multiprocessing
from collections import defaultdict
from urllib.parse import urlparse
import requests
import psutil
import gc
from bs4 import BeautifulSoup
import paho.mqtt.client as mqtt
import ssl
import string
import pyfiglet

cookie_attempts = defaultdict(lambda: {'count': 0, 'last_reset': time.time(), 'banned_until': 0, 'permanent_ban': False})
cookie_delays = {}
active_threads = {}
cleanup_lock = threading.Lock()

def clr():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def handle_failed_connection(cookie_hash):
    global cookie_attempts
    
    current_time = time.time()
    
    if current_time - cookie_attempts[cookie_hash]['last_reset'] > 43200:
        cookie_attempts[cookie_hash]['count'] = 0
        cookie_attempts[cookie_hash]['last_reset'] = current_time
        cookie_attempts[cookie_hash]['banned_until'] = 0
    
    if cookie_attempts[cookie_hash]['banned_until'] > 0:
        ban_count = getattr(cookie_attempts[cookie_hash], 'ban_count', 0) + 1
        cookie_attempts[cookie_hash]['ban_count'] = ban_count
        
        if ban_count >= 5:
            cookie_attempts[cookie_hash]['permanent_ban'] = True
            print(f"Cookie {cookie_hash[:10]} Đã Bị Ngưng Hoạt Động Vĩnh Viễn Để Tránh Đầy Memory, Lí Do: Acc Die, CheckPoint v.v")
            
            for key in list(active_threads.keys()):
                if key.startswith(cookie_hash):
                    active_threads[key].stop()
                    del active_threads[key]

def cleanup_global_memory():
    global active_threads, cookie_attempts
    
    with cleanup_lock:
        current_time = time.time()
        
        expired_cookies = []
        for cookie_hash, data in cookie_attempts.items():
            if data['permanent_ban'] or (current_time - data['last_reset'] > 86400):
                expired_cookies.append(cookie_hash)
        
        for cookie_hash in expired_cookies:
            del cookie_attempts[cookie_hash]
            for key in list(active_threads.keys()):
                if key.startswith(cookie_hash):
                    active_threads[key].stop()
                    del active_threads[key]
        
        gc.collect()
        
        process = psutil.Process()
        memory_info = process.memory_info()
        print(f"Memory Usage: {memory_info.rss / (1024**3):.2f} GB")

def extract_keys(html):
    soup = BeautifulSoup(html, 'html.parser')
    code_div = soup.find('div', class_='plaintext') 
    if code_div:
        keys = [line.strip() for line in code_div.get_text().split('\n') if line.strip()]
        return keys
    return []

def parse_cookie_string(cookie_string):
    cookie_dict = {}
    cookies = cookie_string.split(";")
    for cookie in cookies:
        if "=" in cookie:
            key, value = cookie.split("=")
        else:
            pass
        try: 
            cookie_dict[key] = value
        except: 
            pass
    return cookie_dict

def generate_offline_threading_id() -> str:
    ret = int(time.time() * 1000)
    value = random.randint(0, 4294967295)
    binary_str = format(value, "022b")[-22:]
    msgs = bin(ret)[2:] + binary_str
    return str(int(msgs, 2))
    
def get_headers(
    url: str, options: dict = {}, ctx: dict = {}, customHeader: dict = {}
) -> dict:
    headers = {
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.facebook.com/",
        "Host": url.replace("https://", "").split("/")[0],
        "Origin": "https://www.facebook.com",
        "User-Agent": "Mozilla/5.0 (Linux; Android 9; SM-G973U Build/PPR1.180610.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Mobile Safari/537.36",
        "Connection": "keep-alive",
    }

    if "user_agent" in options:
        headers["User-Agent"] = options["user_agent"]

    for key in customHeader:
        headers[key] = customHeader[key]

    if "region" in ctx:
        headers["X-MSGR-Region"] = ctx["region"]

    return headers

def get_from(input_str, start_token, end_token):
    start = input_str.find(start_token) + len(start_token)
    if start < len(start_token):
        return ""

    last_half = input_str[start:]
    end = last_half.find(end_token)
    if end == -1:
        raise ValueError(f"Could not find endTime `{end_token}` in the given string.")

    return last_half[:end]

def base36encode(number: int, alphabet="0123456789abcdefghijklmnopqrstuvwxyz"):
    if not isinstance(number, int):
        raise TypeError("number must be an integer")

    base36 = ""
    sign = ""

    if number < 0:
        sign = "-"
        number = -number

    if 0 <= number < len(alphabet):
        return sign + alphabet[number]

    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36

    return sign + base36

def dataSplit(string1, string2, numberSplit1=None, numberSplit2=None, HTML=None, amount=None, string3=None, numberSplit3=None, defaultValue=None):
    if (defaultValue): numberSplit1, numberSplit2 = 1, 0
    if (amount == None):
        return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2]
    elif (amount == 3):
        return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2].split(string3)[numberSplit3]

def digitToChar(digit):
    if digit < 10:
        return str(digit)
    return chr(ord('a') + digit - 10)

def str_base(number, base):
    if number < 0:
        return "-" + str_base(-number, base)
    (d, m) = divmod(number, base)
    if d > 0:
        return str_base(d, base) + digitToChar(m)
    return digitToChar(m)

def generate_session_id():
    return random.randint(1, 2 ** 53)

def generate_client_id():
    def gen(length):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return gen(8) + '-' + gen(4) + '-' + gen(4) + '-' + gen(4) + '-' + gen(12)

def json_minimal(data):
    return json.dumps(data, separators=(",", ":"))

class Counter:
    def __init__(self, initial_value=0):
        self.value = initial_value
        
    def increment(self):
        self.value += 1
        return self.value
        
    @property
    def counter(self):
        return self.value

def formAll(dataFB, FBApiReqFriendlyName=None, docID=None, requireGraphql=None):
    global _req_counter
    if '_req_counter' not in globals():
        _req_counter = Counter(0)
    
    __reg = _req_counter.increment()
    dataForm = {}
    
    if (requireGraphql == None):
        dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
        dataForm["jazoest"] = dataFB["jazoest"]
        dataForm["__a"] = 1
        dataForm["__user"] = str(dataFB["FacebookID"])
        dataForm["__req"] = str_base(__reg, 36) 
        dataForm["__rev"] = dataFB["clientRevision"]
        dataForm["av"] = dataFB["FacebookID"]
        dataForm["fb_api_caller_class"] = "RelayModern"
        dataForm["fb_api_req_friendly_name"] = FBApiReqFriendlyName
        dataForm["server_timestamps"] = "true"
        dataForm["doc_id"] = str(docID)
    else:
        dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
        dataForm["jazoest"] = dataFB["jazoest"]
        dataForm["__a"] = 1
        dataForm["__user"] = str(dataFB["FacebookID"])
        dataForm["__req"] = str_base(__reg, 36) 
        dataForm["__rev"] = dataFB["clientRevision"]
        dataForm["av"] = dataFB["FacebookID"]

    return dataForm

def mainRequests(url, data, cookies):
    return {
        "url": url,
        "data": data,
        "headers": {
            "authority": "www.facebook.com",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,vi;q=0.8",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.facebook.com",
            "referer": "https://www.facebook.com/",
            "sec-ch-ua": "\"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"108\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "x-fb-friendly-name": "FriendingCometFriendRequestsRootQueryRelayPreloader",
            "x-fb-lsd": "YCb7tYCGWDI6JLU5Aexa1-"
        },
        "cookies": parse_cookie_string(cookies),
        "verify": True
    }

class fbTools:
    def __init__(self, dataFB, threadID="0"):
        self.threadID = threadID
        self.dataGet = None
        self.dataFB = dataFB
        self.ProcessingTime = None
        self.last_seq_id = None
    
    def getAllThreadList(self):
        randomNumber = str(int(format(int(time.time() * 1000), "b") + ("0000000000000000000000" + format(int(random.random() * 4294967295), "b"))[-22:], 2))
        dataForm = formAll(self.dataFB, requireGraphql=0)

        dataForm["queries"] = json.dumps({
            "o0": {
                "doc_id": "3336396659757871",
                "query_params": {
                    "limit": 20,
                    "before": None,
                    "tags": ["INBOX"],
                    "includeDeliveryReceipts": False,
                    "includeSeqID": True,
                }
            }
        })
        
        sendRequests = requests.post(**mainRequests("https://www.facebook.com/api/graphqlbatch/", dataForm, self.dataFB["cookieFacebook"]))
        response_text = sendRequests.text
        self.ProcessingTime = sendRequests.elapsed.total_seconds()
        
        if response_text.startswith("for(;;);"):
            response_text = response_text[9:]
        
        if not response_text.strip():
            print("Error: Empty response from Facebook API")
            return False
            
        try:
            response_parts = response_text.split("\n")
            first_part = response_parts[0]
            
            if first_part.strip():
                response_data = json.loads(first_part)
                self.dataGet = first_part
                
                if "o0" in response_data and "data" in response_data["o0"] and "viewer" in response_data["o0"]["data"] and "message_threads" in response_data["o0"]["data"]["viewer"]:
                    self.last_seq_id = response_data["o0"]["data"]["viewer"]["message_threads"]["sync_sequence_id"]
                    return True
                else:
                    print("Error: Expected fields not found in response")
                    return False
            else:
                print("Error: Empty first part of response")
                return False
                
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Response first part: {response_parts[0][:100]}")
            return False
        except KeyError as e:
            print(f"Key Error: {e}")
            print("The expected data structure wasn't found in the response")
            return False
    
    def typeCommand(self, commandUsed):
        listData = []
        
        try:
            if self.dataGet is None:
                return "No data available. Make sure to call getAllThreadList first."
                
            data_to_parse = self.dataGet
            if data_to_parse.startswith("for(;;);"):
                data_to_parse = data_to_parse[9:]
                
            getData = json.loads(data_to_parse)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
        except json.JSONDecodeError as e:
            return f"Failed to decode JSON response: {e}"
        except KeyError as e:
            try:
                error_data = json.loads(data_to_parse)["o0"]
                if "errors" in error_data:
                    return error_data["errors"][0]["summary"]
                else:
                    return f"Unexpected response structure. Missing key: {e}"
            except:
                return f"Unexpected response structure. Missing key: {e}"
        
        dataThread = None
        for getNeedIDThread in getData:
            thread_key = getNeedIDThread.get("thread_key", {})
            thread_fbid = thread_key.get("thread_fbid")
            if thread_fbid and str(thread_fbid) == str(self.threadID):
                dataThread = getNeedIDThread
                break
        
        if dataThread is not None:
            if commandUsed == "getAdmin":
                for dataID in dataThread.get("thread_admins", []):
                    listData.append(str(dataID["id"]))
                exportData = {
                    "adminThreadList": listData
                }
            elif commandUsed == "threadInfomation":
                threadInfoList = dataThread.get("customization_info", {})
                exportData = {
                    "nameThread": dataThread.get("name"), 
                    "IDThread": self.threadID, 
                    "emojiThread": threadInfoList.get("emoji"),
                    "messageCount": dataThread.get("messages_count"),
                    "adminThreadCount": len(dataThread.get("thread_admins", [])),
                    "memberCount": len(dataThread.get("all_participants", {}).get("edges", [])),
                    "approvalMode": "Bật" if (dataThread.get("approval_mode", 0) != 0) else "Tắt",
                    "joinableMode": "Bật" if (dataThread.get("joinable_mode", {}).get("mode") != "0") else "Tắt",
                    "urlJoinableThread": dataThread.get("joinable_mode", {}).get("link", "")
                }
            elif commandUsed == "exportMemberListToJson":
                getMemberList = dataThread.get("all_participants", {}).get("edges", [])
                for exportMemberList in getMemberList:
                    node = exportMemberList.get("node", {})
                    dataUserThread = node.get("messaging_actor", {})
                    if dataUserThread:
                        exportData = json.dumps({
                            dataUserThread.get("id", ""): {
                                "nameFB": str(dataUserThread.get("name", "")),
                                "idFacebook": str(dataUserThread.get("id", "")),
                                "profileUrl": str(dataUserThread.get("url", "")),
                                "avatarUrl": str(dataUserThread.get("big_image_src", {}).get("uri", "")),
                                "gender": str(dataUserThread.get("gender", "")),
                                "usernameFB": str(dataUserThread.get("username", ""))
                            }
                        }, skipkeys=True, allow_nan=True, ensure_ascii=False, indent=5)
                        listData.append(exportData)
                exportData = listData
            else:
                exportData = {
                    "err": "no data"
                }
                
            return exportData
            
        else:
            return "Không lấy được dữ liệu ThreadList, đã xảy ra lỗi T___T"
    
    def getListThreadID(self):
        try:
            if self.dataGet is None:
                return {
                    "ERR": "No data available. Make sure to call getAllThreadList first."
                }
                
            data_to_parse = self.dataGet
            if data_to_parse.startswith("for(;;);"):
                data_to_parse = data_to_parse[9:]
                
            threadIDList = []
            threadNameList = []
            try:
                getData = json.loads(data_to_parse)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
                
                for getThreadID in getData:
                    thread_key = getThreadID.get("thread_key", {})
                    thread_fbid = thread_key.get("thread_fbid")
                    
                    if thread_fbid is not None:
                        threadIDList.append(thread_fbid)
                        threadNameList.append(getThreadID.get("name", "No Name"))
                        
                return {
                    "threadIDList": threadIDList,
                    "threadNameList": threadNameList,
                    "countThread": len(threadIDList)
                }
                
            except (KeyError, json.JSONDecodeError) as e:
                return {
                    "ERR": f"Error processing thread data: {str(e)}"
                }
                
        except Exception as errLog:
            return {
                "ERR": f"Unexpected error: {str(errLog)}"
            }

class MessageSender:
    def __init__(self, fbt, dataFB, fb_instance):
        self.fbt = fbt
        self.dataFB = dataFB
        self.fb_instance = fb_instance
        self.mqtt = None
        self.ws_req_number = 0
        self.ws_task_number = 0
        self.syncToken = None
        self.lastSeqID = None
        self.req_callbacks = {}
        self.cookie_hash = hashlib.md5(dataFB['cookieFacebook'].encode()).hexdigest()
        self.connect_attempts = 0
        self.last_cleanup = time.time()

    def cleanup_memory(self):
        current_time = time.time()
        if current_time - self.last_cleanup > 3600:
            self.req_callbacks.clear()
            gc.collect()
            self.last_cleanup = current_time

    def get_last_seq_id(self):
        success = self.fbt.getAllThreadList()
        if success:
            self.lastSeqID = self.fbt.last_seq_id
        else:
            print("Failed To Get Last Sequence ID. Check Facebook Authentication.")
            return

    def on_disconnect(self, client, userdata, rc):
        global cookie_attempts
        print(f"Disconnected With Code {rc}")
        
        cookie_attempts[self.cookie_hash]['count'] += 1
        current_time = time.time()
        
        if current_time - cookie_attempts[self.cookie_hash]['last_reset'] > 43200:
            cookie_attempts[self.cookie_hash]['count'] = 1
            cookie_attempts[self.cookie_hash]['last_reset'] = current_time
        
        if cookie_attempts[self.cookie_hash]['count'] >= 20:
            print(f"Cookie {self.cookie_hash[:10]} Bị Tạm Ngưng Connect Trong 12 Giờ Vì Disconnect, Nghi Vấn: Die Cookies, Check Point")
            cookie_attempts[self.cookie_hash]['banned_until'] = current_time + 43200
            return
        
        if rc != 0:
            print("Attempting To Reconnect...")
            try:
                time.sleep(min(cookie_attempts[self.cookie_hash]['count'] * 2, 30))
                client.reconnect()
            except:
                print("Reconnect Failed")

    def _messenger_queue_publish(self, client, userdata, flags, rc):
        print(f"Connected To MQTT With Code: {rc}")
        if rc != 0:
            print(f"Connection Failed With Code {rc}")
            return

        topics = [("/t_ms", 0)]
        client.subscribe(topics)

        queue = {
            "sync_api_version": 10,
            "max_deltas_able_to_process": 1000,
            "delta_batch_size": 500,
            "encoding": "JSON",
            "entity_fbid": self.dataFB['FacebookID']
        }

        if self.syncToken is None:
            topic = "/messenger_sync_create_queue"
            queue["initial_titan_sequence_id"] = self.lastSeqID
            queue["device_params"] = None
        else:
            topic = "/messenger_sync_get_diffs"
            queue["last_seq_id"] = self.lastSeqID
            queue["sync_token"] = self.syncToken

        print(f"Publishing To {topic}")
        client.publish(
            topic,
            json_minimal(queue),
            qos=1,
            retain=False,
        )

    def connect_mqtt(self):
        global cookie_attempts
        
        if cookie_attempts[self.cookie_hash]['permanent_ban']:
            print(f"Cookie {self.cookie_hash[:10]} Đã Bị Ngưng Connect Vĩnh Viễn, Lí Do: Die Cookies, Check Point v.v")
            return False
            
        current_time = time.time()
        if current_time < cookie_attempts[self.cookie_hash]['banned_until']:
            remaining = cookie_attempts[self.cookie_hash]['banned_until'] - current_time
            print(f"Cookie {self.cookie_hash[:10]} Bị Tạm Khóa, Còn {remaining/3600:.1f} Giờ")
            return False

        if not self.lastSeqID:
            print("Error: No last_seq_id Available. Cannot Connect To MQTT.")
            return False

        chat_on = json_minimal(True)
        session_id = generate_session_id()
        user = {
            "u": self.dataFB["FacebookID"],
            "s": session_id,
            "chat_on": chat_on,
            "fg": False,
            "d": generate_client_id(),
            "ct": "websocket",
            "aid": 219994525426954,
            "mqtt_sid": "",
            "cp": 3,
            "ecp": 10,
            "st": ["/t_ms", "/messenger_sync_get_diffs", "/messenger_sync_create_queue"],
            "pm": [],
            "dc": "",
            "no_auto_fg": True,
            "gas": None,
            "pack": [],
        }

        host = f"wss://edge-chat.messenger.com/chat?region=eag&sid={session_id}"
        options = {
            "client_id": "mqttwsclient",
            "username": json_minimal(user),
            "clean": True,
            "ws_options": {
                "headers": {
                    "Cookie": self.dataFB['cookieFacebook'],
                    "Origin": "https://www.messenger.com",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 9; SM-G973U Build/PPR1.180610.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Mobile Safari/537.36",
                    "Referer": "https://www.messenger.com/",
                    "Host": "edge-chat.messenger.com",
                },
            },
            "keepalive": 10,
        }

        self.mqtt = mqtt.Client(
            client_id="mqttwsclient",
            clean_session=True,
            protocol=mqtt.MQTTv31,
            transport="websockets",
        )

        self.mqtt.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLSv1_2)
        self.mqtt.on_connect = self._messenger_queue_publish
        self.mqtt.on_disconnect = self.on_disconnect
        self.mqtt.username_pw_set(username=options["username"])

        parsed_host = urlparse(host)
        self.mqtt.ws_set_options(
            path=f"{parsed_host.path}?{parsed_host.query}",
            headers=options["ws_options"]["headers"],
        )

        print(f"Connecting To {options['ws_options']['headers']['Host']}...")
        try:
            self.mqtt.connect(
                host=options["ws_options"]["headers"]["Host"],
                port=443,
                keepalive=options["keepalive"],
            )

            print("MQTT Connection Established")
            self.mqtt.loop_start()
            return True
        except Exception as e:
            print(f"MQTT Connection Error: {e}")
            cookie_attempts[self.cookie_hash]['count'] += 1
            return False

    def stop(self):
        if self.mqtt:
            print("Stopping MQTT Client...")
            try:
                self.mqtt.disconnect()
                self.mqtt.loop_stop()
            except:
                pass
        self.cleanup_memory()

    def upload_file(self, file_path):
        user_id = self.fb_instance.user_id
        url = "https://www.facebook.com/ajax/mercury/upload.php"
        headers = {
            'Cookie': self.dataFB['cookieFacebook'],
            'User-Agent': 'python-http/0.27.0',
            'Origin': 'https://www.facebook.com',
            'Referer': 'https://www.facebook.com/'
        }

        params = {
            'ads_manager_write_regions': 'true',
            '__aaid': '0',
            '__user': user_id,
            '__a': '1',
            '__hs': '20207.HYP:comet_pkg.2.1...0',
            'dpr': '3',
            '__ccg': 'GOOD',
            '__rev': '1022311521',
            'fb_dtsg': self.dataFB['fb_dtsg'],
            'jazoest': self.dataFB['jazoest'],
            '__crn': 'comet.fbweb.CometHomeRoute'
        }

        mime_type = 'image/jpeg'
        if file_path.lower().endswith(('.mp4', '.mov', '.avi', '.wmv')):
            mime_type = 'video/mp4'

        with open(file_path, 'rb') as file:
            files = {'farr': (file_path.split('/')[-1], file, mime_type)}
            response = requests.post(url, headers=headers, params=params, files=files)

        if response.status_code == 200:
            content = response.text.replace('for (;;);', '')
            try:
                data = json.loads(content)
                if 'payload' in data and 'metadata' in data['payload'] and '0' in data['payload']['metadata']:
                    metadata = data['payload']['metadata']['0']
                    if mime_type.startswith('video'):
                        file_id = metadata.get('video_id')
                        return {'id': file_id, 'type': 'video'}
                    else:
                        file_id = metadata.get('fbid') or metadata.get('image_id')
                        return {'id': file_id, 'type': 'image'}
                else:
                    with open('response_debug.json', 'w', encoding='utf-8') as f:
                        f.write(content)
                    raise Exception(f"JSON Structure Not As Expected. Response Saved To response_debug.json")
            except json.JSONDecodeError:
                raise Exception(f"Cannot Parse JSON From Response: {response.text}")
        else:
            raise Exception(f"Error Uploading File: {response.status_code}")

    def get_valid_mentions(self, text, mention):
        if not isinstance(mention, dict) and not isinstance(mention, list):
            raise ValueError("Mentions must be a dict or list of dict")

        mentions = mention if isinstance(mention, list) else [mention]
        valid_mentions = []
        current_offset = 0

        for mention in mentions:
            if "id" in mention and "tag" in mention:
                provided_offset = mention.get("offset")
                tag_len = 0

                if type(provided_offset) is int:
                    if provided_offset >= len(text):
                        break
                    is_length_exceed = provided_offset + len(mention["tag"]) > len(text)
                    tag_len = (
                        len(mention["tag"])
                        if not is_length_exceed
                        else len(text) - provided_offset
                    )
                    current_offset = provided_offset
                else:
                    if current_offset >= len(text):
                        break
                    find = text.find(mention["tag"], current_offset)
                    if find != -1:
                        is_length_exceed = find + len(mention["tag"]) > len(text)
                        tag_len = (
                            len(mention["tag"])
                            if not is_length_exceed
                            else len(text) - find
                        )
                        current_offset = find

                valid_mentions.append({
                    "i": mention["id"],
                    "o": current_offset,
                    "l": tag_len,
                })
                current_offset += tag_len

        return valid_mentions

    def send_message(self, text=None, thread_id=None, attachment=None, mention=None, message_id=None, callback=None):
        if self.mqtt is None:
            print("Error: Not Connected To MQTT")
            return False

        if thread_id is None:
            print("Error: Thread ID Is Required")
            return False

        if text is None and attachment is None:
            print("Error: Text Or Attachment Is Required")
            return False

        self.cleanup_memory()

        self.ws_req_number += 1
        content = {
            "app_id": "2220391788200892",
            "payload": {
                "data_trace_id": None,
                "epoch_id": int(generate_offline_threading_id()),
                "tasks": [],
                "version_id": "7545284305482586",
            },
            "request_id": self.ws_req_number,
            "type": 3,
        }

        text = str(text) if text is not None else ""
        if len(text) > 0:
            self.ws_task_number += 1
            task_payload = {
                "initiating_source": 0,
                "multitab_env": 0,
                "otid": generate_offline_threading_id(),
                "send_type": 1,
                "skip_url_preview_gen": 0,
                "source": 0,
                "sync_group": 1,
                "text": text,
                "text_has_links": 0,
                "thread_id": int(thread_id),
            }

            if message_id is not None:
                if type(message_id) is not str:
                    raise ValueError("message_id must be a string")
                task_payload["reply_metadata"] = {
                    "reply_source_id": message_id,
                    "reply_source_type": 1,
                    "reply_type": 0,
                }

            if mention is not None and len(text) > 0:
                valid_mentions = self.get_valid_mentions(text, mention)
                task_payload["mention_data"] = {
                    "mention_ids": ",".join([str(x["i"]) for x in valid_mentions]),
                    "mention_lengths": ",".join([str(x["l"]) for x in valid_mentions]),
                    "mention_offsets": ",".join([str(x["o"]) for x in valid_mentions]),
                    "mention_types": ",".join(["p" for _ in valid_mentions]),
                }

            task = {
                "failure_count": None,
                "label": "46",
                "payload": json.dumps(task_payload, separators=(",", ":")),
                "queue_name": str(thread_id),
                "task_id": self.ws_task_number,
            }

            content["payload"]["tasks"].append(task)

        self.ws_task_number += 1
        task_mark_payload = {
            "last_read_watermark_ts": int(time.time() * 1000),
            "sync_group": 1,
            "thread_id": int(thread_id),
        }

        task_mark = {
            "failure_count": None,
            "label": "21",
            "payload": json.dumps(task_mark_payload, separators=(",", ":")),
            "queue_name": str(thread_id),
            "task_id": self.ws_task_number,
        }

        content["payload"]["tasks"].append(task_mark)

        if attachment is not None:
            attachments = attachment if isinstance(attachment, list) else [attachment]
            for file_info in attachments:
                self.ws_task_number += 1
                if file_info["type"] == "image":
                    task_payload = {
                        "attachment_fbids": [file_info["id"]],
                        "otid": generate_offline_threading_id(),
                        "send_type": 3,
                        "source": 0,
                        "sync_group": 1,
                        "text": None,
                        "thread_id": int(thread_id),
                    }
                else:
                    task_payload = {
                        "attachment_fbids": [file_info["id"]],
                        "otid": generate_offline_threading_id(),
                        "send_type": 3,
                        "source": 0,
                        "sync_group": 1,
                        "text": None,
                        "thread_id": int(thread_id),
                    }

                if message_id is not None:
                    task_payload["reply_metadata"] = {
                        "reply_source_id": message_id,
                        "reply_source_type": 1,
                        "reply_type": 0,
                    }

                task = {
                    "failure_count": None,
                    "label": "46",
                    "payload": json.dumps(task_payload, separators=(",", ":")),
                    "queue_name": str(thread_id),
                    "task_id": self.ws_task_number,
                }

                content["payload"]["tasks"].append(task)

        content["payload"] = json.dumps(content["payload"], separators=(",", ":"))

        if callback is not None and callable(callback):
            self.req_callbacks[self.ws_req_number] = callback

        try:
            self.mqtt.publish(
                topic="/ls_req",
                payload=json.dumps(content, separators=(",", ":")),
                qos=1,
                retain=False,
            )
            return True
        except Exception as e:
            print(f"Error Publishing Message: {e}")
            return False

    def send_message_with_attachment(self, text, thread_id, file_path, message_id=None, callback=None):
        if self.mqtt is None:
            print("Error: Not Connected To MQTT")
            return False

        if thread_id is None:
            print("Error: Thread ID Is Required")
            return False

        try:
            file_info = self.upload_file(file_path)
            if not file_info:
                print("Failed To Upload File")
                return False

            self.cleanup_memory()

            self.ws_req_number += 1
            content = {
                "app_id": "2220391788200892",
                "payload": {
                    "data_trace_id": None,
                    "epoch_id": int(generate_offline_threading_id()),
                    "tasks": [],
                    "version_id": "7545284305482586",
                },
                "request_id": self.ws_req_number,
                "type": 3,
            }

            self.ws_task_number += 1
            task_payload = {
                "attachment_fbids": [file_info["id"]],
                "initiating_source": 0,
                "multitab_env": 0,
                "otid": generate_offline_threading_id(),
                "send_type": 3,
                "skip_url_preview_gen": 0,
                "source": 0,
                "sync_group": 1,
                "text": text,
                "text_has_links": 0,
                "thread_id": int(thread_id),
            }

            if message_id is not None:
                if type(message_id) is not str:
                    raise ValueError("message_id must be a string")
                task_payload["reply_metadata"] = {
                    "reply_source_id": message_id,
                    "reply_source_type": 1,
                    "reply_type": 0,
                }

            task = {
                "failure_count": None,
                "label": "46",
                "payload": json.dumps(task_payload, separators=(",", ":")),
                "queue_name": str(thread_id),
                "task_id": self.ws_task_number,
            }

            content["payload"]["tasks"].append(task)

            self.ws_task_number += 1
            task_mark_payload = {
                "last_read_watermark_ts": int(time.time() * 1000),
                "sync_group": 1,
                "thread_id": int(thread_id),
            }

            task_mark = {
                "failure_count": None,
                "label": "21",
                "payload": json.dumps(task_mark_payload, separators=(",", ":")),
                "queue_name": str(thread_id),
                "task_id": self.ws_task_number,
            }

            content["payload"]["tasks"].append(task_mark)

            content["payload"] = json.dumps(content["payload"], separators=(",", ":"))

            if callback is not None and callable(callback):
                self.req_callbacks[self.ws_req_number] = callback

            try:
                self.mqtt.publish(
                    topic="/ls_req",
                    payload=json.dumps(content, separators=(",", ":")),
                    qos=1,
                    retain=False,
                )
                return True
            except Exception as e:
                print(f"Error Publishing Message: {e}")
                return False

        except Exception as e:
            print(f"Error Sending Message With Attachment: {e}")
            return False

    def share_contact(self, text=None, sender_id=None, thread_id=None):
        if self.mqtt is None:
            print("Error: Not Connected To MQTT")
            return False

        if sender_id is None:
            print("Error: Sender ID Is Required")
            return False

        if thread_id is None:
            print("Error: Thread ID Is Required")
            return False

        self.cleanup_memory()

        self.ws_req_number += 1
        self.ws_task_number += 1

        content = {
            "app_id": "2220391788200892",
            "payload": {
                "tasks": [{
                    "label": 359,
                    "payload": json.dumps({
                        "contact_id": sender_id,
                        "sync_group": 1,
                        "text": text or "",
                        "thread_id": thread_id
                    }, separators=(",", ":")),
                    "queue_name": "xma_open_contact_share",
                    "task_id": self.ws_task_number,
                    "failure_count": None,
                }],
                "epoch_id": generate_offline_threading_id(),
                "version_id": "7214102258676893",
            },
            "request_id": self.ws_req_number,
            "type": 3
        }

        content["payload"] = json.dumps(content["payload"], separators=(",", ":"))

        try:
            self.mqtt.publish(
                topic="/ls_req",
                payload=json.dumps(content, separators=(",", ":")),
                qos=1,
                retain=False,
            )
            return True
        except Exception as e:
            print(f"Error Publishing Contact Share: {e}")
            return False

    def share_link(self, text=None, url=None, thread_id=None, callback=None):
        if self.mqtt is None:
            print("Error: Not Connected To MQTT")
            return False

        if thread_id is None:
            print("Error: Thread ID Is Required")
            return False

        self.cleanup_memory()

        self.ws_req_number += 1
        self.ws_task_number += 1

        content = {
            "app_id": "2220391788200892",
            "payload": {
                "tasks": [{
                    "label": 46,
                    "payload": json.dumps({
                        "otid": generate_offline_threading_id(),
                        "source": 524289,
                        "sync_group": 1,
                        "send_type": 6,
                        "mark_thread_read": 0,
                        "url": url or "https://www.facebook.com",
                        "text": text or "",
                        "thread_id": thread_id,
                        "initiating_source": 0
                    }, separators=(",", ":")),
                    "queue_name": str(thread_id),
                    "task_id": self.ws_task_number,
                    "failure_count": None,
                }],
                "epoch_id": generate_offline_threading_id(),
                "version_id": "7191105584331330",
            },
            "request_id": self.ws_req_number,
            "type": 3
        }

        content["payload"] = json.dumps(content["payload"], separators=(",", ":"))

        if callback is not None and callable(callback):
            self.req_callbacks[self.ws_req_number] = callback

        try:
            self.mqtt.publish(
                topic="/ls_req",
                payload=json.dumps(content, separators=(",", ":")),
                qos=1,
                retain=False,
            )
            return True
        except Exception as e:
            print(f"Error Publishing Link Share: {e}")
            return False

def send_messages_with_cookie(cookie, thread_id, message_files, delay, option=0, file_path=None, contact_uid=None):
    global cookie_attempts, active_threads
    
    cookie_hash = hashlib.md5(cookie.encode()).hexdigest()
    
    if cookie_attempts[cookie_hash]['permanent_ban']:
        print(f"Cookie {cookie_hash[:10]} Đã Bị Ngưng Hoạt Động Vĩnh Viễn\nLí Do: Cookies Die, CheckPoint V.V")
        return False
        
    current_time = time.time()
    if current_time < cookie_attempts[cookie_hash]['banned_until']:
        remaining = cookie_attempts[cookie_hash]['banned_until'] - current_time
        print(f"Cookie {cookie_hash[:10]} Bị Tạm Khóa, Còn {remaining/3600:.1f} Giờ\nLí Do: Checkpoint, Mõm, Cookies Die")
        return False

    try:
        fb = DzixMode(cookie)
        sender = MessageSender(fbTools({
            "FacebookID": fb.user_id,
            "fb_dtsg": fb.fb_dtsg,
            "clientRevision": fb.rev,
            "jazoest": fb.jazoest,
            "cookieFacebook": cookie
        }), {
            "FacebookID": fb.user_id,
            "fb_dtsg": fb.fb_dtsg,
            "clientRevision": fb.rev,
            "jazoest": fb.jazoest,
            "cookieFacebook": cookie
        }, fb)

        sender.get_last_seq_id()
        if not sender.connect_mqtt():
            handle_failed_connection(cookie_hash)
            return False

        print(f"Bắt Đầu Gửi Tin Nhắn Cho Box: {thread_id}")
        
        active_threads[f"{cookie_hash}_{thread_id}"] = sender

        try:
            while True:
                if len(message_files) > 1:
                    selected = random.choice(message_files)
                else:
                    selected = message_files[0]

                with open(selected, 'r', encoding='utf-8') as f:
                    content = f.read().strip()

                if option == 2:
                    uid_to_share = contact_uid or fb.user_id
                    sender.share_contact(content, uid_to_share, thread_id)
                elif option == 1:
                    sender.send_message_with_attachment(content, thread_id, file_path)
                elif option == 3:
                    # Gửi chỉ share link, URL dựa trên UID
                    uid_to_share = contact_uid or fb.user_id
                    share_url = f"https://www.facebook.com/{uid_to_share}"
                    sender.share_link(content, share_url, thread_id)
                else:
                    sender.send_message(content, thread_id)

                time.sleep(delay)
                
                if current_time - sender.last_cleanup > 600:
                    gc.collect()

        except KeyboardInterrupt:
            print(f"\nDừng Gửi Tin Nhắn Cho Box: {thread_id}")
        finally:
            sender.stop()
            if f"{cookie_hash}_{thread_id}" in active_threads:
                del active_threads[f"{cookie_hash}_{thread_id}"]

        return True

    except Exception as e:
        print(f"Lỗi Trong Luồng Gửi Tin Nhắn Cho Box {thread_id}: {e}")
        handle_failed_connection(cookie_hash)
        return False

class DzixMode:
    def __init__(self, cookie, mqtt_broker="broker.hivemq.com", mqtt_port=1883):
        self.cookie = cookie
        self.user_id = self.id_user()
        self.fb_dtsg = None
        self.jazoest = None
        self.rev = None
        self.init_params()

        # MQTT Client Setup
        self.mqtt_client = mqtt.Client(
            client_id=f"messenger_{self.user_id}_{int(time.time())}",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic_base = "messenger/spam"

    def id_user(self):
        try:
            match = re.search(r"c_user=(\d+)", self.cookie)
            if not match:
                raise Exception("Cookie không hợp lệ")
            return match.group(1)
        except Exception as e:
            raise Exception(f"Lỗi khi lấy user_id: {str(e)}")

    def init_params(self):
        headers = {
            'Cookie': self.cookie,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        urls = [
            'https://www.facebook.com',
            'https://mbasic.facebook.com',
            'https://m.facebook.com'
        ]

        for url in urls:
            try:
                print(f"[*] Thử lấy fb_dtsg từ {url}")
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code != 200:
                    print(f"[❌] Yêu cầu tới {url} thất bại, mã trạng thái: {response.status_code}")
                    continue

                with open('response_debug.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"[*] Đã lưu phản hồi HTML vào response_debug.html để kiểm tra")

                fb_dtsg_patterns = [
                    r'"token":"(.*?)"',
                    r'name="fb_dtsg" value="(.*?)"',
                    r'"fb_dtsg":"(.*?)"',
                    r'fb_dtsg=([^&"]+)'
                ]
                jazoest_pattern = r'name="jazoest" value="(\d+)"'
                rev_pattern = r'"__rev":"(\d+)"'

                fb_dtsg = None
                for pattern in fb_dtsg_patterns:
                    match = re.search(pattern, response.text)
                    if match:
                        fb_dtsg = match.group(1)
                        break

                jazoest_match = re.search(jazoest_pattern, response.text)
                rev_match = re.search(rev_pattern, response.text)

                if fb_dtsg:
                    self.fb_dtsg = fb_dtsg
                    self.jazoest = jazoest_match.group(1) if jazoest_match else "22036"
                    self.rev = rev_match.group(1) if rev_match else "1015919737"
                    print(f"[✓] Lấy được fb_dtsg: {self.fb_dtsg}, jazoest: {self.jazoest}, rev: {self.rev}")
                    return
                else:
                    print(f"[⚠] Không tìm thấy fb_dtsg trong {url}")

            except Exception as e:
                print(f"[❌] Lỗi khi truy cập {url}: {str(e)}")
                time.sleep(2)

        raise Exception("Không thể lấy được fb_dtsg từ bất kỳ URL nào")

    def gui_tn(self, recipient_id, message):
        if not self.fb_dtsg or not self.jazoest or not self.rev:
            self.init_params()
        timestamp = int(time.time() * 1000)
        data = {
            'thread_fbid': recipient_id,
            'action_type': 'ma-type:user-generated-message',
            'body': message,
            'client': 'mercury',
            'author': f'fbid:{self.user_id}',
            'timestamp': timestamp,
            'source': 'source:chat:web',
            'offline_threading_id': str(timestamp),
            'message_id': str(timestamp),
            'ephemeral_ttl_mode': '',
            '__user': self.user_id,
            '__a': '1',
            '__req': '1b',
            '__rev': self.rev,
            'fb_dtsg': self.fb_dtsg,
            'jazoest': self.jazoest
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.facebook.com',
            'Referer': f'https://www.facebook.com/messages/t/{recipient_id}',
            'Cookie': self.cookie
        }

        try:
            response = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"[❌] Gửi thất bại. Status: {response.status_code}")
                return {'success': False}

            if 'for (;;);' in response.text:
                json_data = json.loads(response.text.replace('for (;;);', ''))
                if 'error' in json_data:
                    print(f"[❌] Lỗi từ Facebook: {json_data.get('errorDescription', 'Unknown error')}")
                    return {'success': False}

            print("[✅] Gửi tin nhắn thành công.")
            return {'success': True}
        except Exception as e:
            print(f"[❌] Lỗi khi gửi: {str(e)}")
            return {'success': False}

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"[✓] Kết nối MQTT broker: {self.mqtt_broker}")
            client.subscribe(f"{self.mqtt_topic_base}/#", qos=1)
            print(f"[✓] Subscribe topic: {self.mqtt_topic_base}/#")
        else:
            print(f"[❌] Kết nối MQTT thất bại, mã lỗi: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            print(f"[📩] Nhận từ {topic}: {payload}")

            recipient_id = topic.split('/')[-1]
            message = json.loads(payload).get('message', '')
            if not message:
                print("[!] Nội dung rỗng, bỏ qua.")
                return

            result = self.gui_tn(recipient_id, message)
            if result.get('success'):
                print(f"[✓] Gửi thành công tới {recipient_id}")
            else:
                print(f"[×] Gửi thất bại tới {recipient_id}")

        except Exception as e:
            print(f"[!] Lỗi xử lý MQTT: {str(e)}")

    def start_mqtt(self):
        print(f"[*] Kết nối MQTT {self.mqtt_broker}:{self.mqtt_port}...")
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"[❌] Lỗi kết nối MQTT: {str(e)}")

    def stop_mqtt(self):
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("[*] Ngắt kết nối MQTT.")
        except Exception as e:
            print(f"[❌] Lỗi ngắt kết nối MQTT: {str(e)}")

def publish_messages(broker, port, topic_base, recipient_id, file_txt, delay):
    client = mqtt.Client(
        client_id=f"publisher_{int(time.time())}",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    try:
        client.connect(broker, port, keepalive=60)
        topic = f"{topic_base}/{recipient_id}"

        print(f"[*] Publish tới {topic}...")
        while True:
            try:
                with open(file_txt, 'r', encoding='utf-8') as f:
                    message = f.read().strip()

                if not message:
                    print("[!] Nội dung rỗng, dừng.")
                    break

                payload = json.dumps({'message': message})
                client.publish(topic, payload, qos=1)
                print(f"[✓] Đã publish: {message}")

                sys.stdout.write("[*] Đang chờ ")
                for _ in range(int(delay)):
                    sys.stdout.write("⌛")
                    sys.stdout.flush()
                    time.sleep(1)
                sys.stdout.write("\n")

            except Exception as e:
                print(f"[!] Lỗi publish: {str(e)}")
                time.sleep(delay)

    except Exception as e:
        print(f"[❌] Lỗi kết nối publisher: {str(e)}")
    finally:
        client.disconnect()
        print("[*] Ngắt kết nối publisher.")



# ═══════════════════════════════════════════════════════
# DZIXTOOL - TREO MES MQTT
# ═══════════════════════════════════════════════════════

def taobanner():
    banner = pyfiglet.figlet_format('MES MQTT V6', font="slant")
    return banner

def xemcookiesonghaychet(cookie):
    try:
        if 'c_user=' not in cookie:
            return {"status": "failed", "msg": "Cookie không chứa c_user"}
        user_id = cookie.split('c_user=')[1].split(';')[0]
        headers = {
            'cookie': cookie,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }
        r = requests.get(f'https://m.facebook.com/profile.php?id={user_id}', headers=headers, timeout=20)
        if '<title>' not in r.text:
            return {"status": "failed", "msg": "Không lấy được tên (cookie die hoặc checkpoint)"}
        name = r.text.split('<title>')[1].split('<')[0].strip()
        if not name or name.lower() in ['facebook', '']:
            return {"status": "failed", "msg": "Cookie die hoặc checkpoint"}
        return {"status": "success", "name": name, "user_id": user_id}
    except Exception as e:
        return {"status": "failed", "msg": str(e)}

def don_ram_cpu_disk():
    gc.collect()
    try:
        process = psutil.Process()
        process.cpu_percent(interval=None)
        mem = process.memory_info()
        ram_mb = mem.rss / (1024 ** 2)
        cpu = psutil.cpu_percent(interval=1)
        disk = psutil.disk_usage('/')
        disk_free_gb = disk.free / (1024 ** 3)
        if ram_mb > 300:
            gc.collect()
            import ctypes
            try:
                ctypes.cdll.msvcrt.malloc_trim(0)
            except:
                pass
        print(f"[🧹] RAM: {ram_mb:.1f} MB | CPU: {cpu:.1f}% | Disk trống: {disk_free_gb:.2f} GB")
    except Exception as e:
        print(f"[!] Dọn tài nguyên lỗi: {e}")

def liet_ke_file_txt(thu_muc='.'):
    files = [f for f in os.listdir(thu_muc) if f.endswith('.txt') and os.path.isfile(os.path.join(thu_muc, f))]
    return sorted(files)

def nhap_so_hop_le(prompt, min_val=1, max_val=None):
    while True:
        try:
            val = int(input(prompt).strip())
            if val < min_val:
                print(f"[!] Phải >= {min_val}, nhập lại.")
                continue
            if max_val is not None and val > max_val:
                print(f"[!] Phải <= {max_val}, nhập lại.")
                continue
            return val
        except ValueError:
            print("[!] Phải nhập số nguyên, nhập lại.")

def nhap_chon_1_hoac_2(prompt):
    while True:
        val = input(prompt).strip()
        if val in ('1', '2'):
            return val
        print("[!] Chỉ nhập 1 hoặc 2, nhập lại.")

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
]

def lay_danh_sach_box(cookie, fb_dtsg, user_id, limit=100):
    headers = {
        'Cookie': cookie,
        'User-Agent': random.choice(_USER_AGENTS),
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Origin': 'https://www.facebook.com',
        'Referer': 'https://www.facebook.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'X-FB-Friendly-Name': 'MessengerThreadListQuery',
        'X-FB-LSD': 'null'
    }
    form_data = {
        "av": user_id,
        "__user": user_id,
        "__a": "1",
        "__req": "1b",
        "__hs": "19234.HYP:comet_pkg.2.1..2.1",
        "dpr": "1",
        "__ccg": "EXCELLENT",
        "__rev": "1015919737",
        "__comet_req": "15",
        "fb_dtsg": fb_dtsg,
        "jazoest": "null",
        "lsd": "null",
        "__spin_r": "",
        "__spin_b": "trunk",
        "__spin_t": str(int(time.time())),
        "queries": json.dumps({
            "o0": {
                "doc_id": "3336396659757871",
                "query_params": {
                    "limit": limit,
                    "before": None,
                    "tags": ["INBOX"],
                    "includeDeliveryReceipts": False,
                    "includeSeqID": True,
                }
            }
        })
    }
    try:
        response = requests.post(
            'https://www.facebook.com/api/graphqlbatch/',
            data=form_data,
            headers=headers,
            timeout=15
        )
        if response.status_code != 200:
            return {"error": f"HTTP Error: {response.status_code}"}
        response_text = response.text.split('{"successful_results"')[0]
        data = json.loads(response_text)
        if "o0" not in data or data["o0"] is None:
            return {"error": "Không tìm thấy dữ liệu thread list"}
        if "errors" in data["o0"]:
            return {"error": f"Facebook API Error: {data['o0']['errors'][0]['summary']}"}
        viewer = (data["o0"].get("data") or {}).get("viewer")
        if not viewer:
            return {"error": "Không lấy được viewer data (cookie có thể die)"}
        threads = viewer["message_threads"]["nodes"]
        thread_list = []
        for thread in threads:
            if not thread.get("thread_key") or not thread["thread_key"].get("thread_fbid"):
                continue
            thread_list.append({
                "thread_id": thread["thread_key"]["thread_fbid"],
                "thread_name": thread.get("name", "Không có tên")
            })
        return {
            "success": True,
            "thread_count": len(thread_list),
            "threads": thread_list
        }
    except json.JSONDecodeError as e:
        return {"error": f"Lỗi parse JSON: {str(e)}"}
    except Exception as e:
        return {"error": f"Lỗi không xác định: {str(e)}"}

def chon_box(input_str, max_index):
    try:
        numbers = [int(i.strip()) for i in input_str.split(',')]
        return [n for n in numbers if 1 <= n <= max_index]
    except:
        print("Định dạng không hợp lệ!")
        return []

def tai_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if not content.strip():
            raise Exception(f"File {file_path} trống!")
        return [line.strip() for line in content.splitlines() if line.strip()]
    except Exception as e:
        raise Exception(f"Lỗi đọc file: {str(e)}")

# ═══════════════════════════════════════════════════════
# WORKER PROCESS: 1 account → N box → MQTT loop
# ═══════════════════════════════════════════════════════

def worker_treo_mes(cookie, account_name, selected_ids, selected_names, message_files, delay):
    try:
        fb = DzixMode(cookie)
        dataFB = {
            "FacebookID": fb.user_id,
            "fb_dtsg": fb.fb_dtsg,
            "clientRevision": fb.rev,
            "jazoest": fb.jazoest,
            "cookieFacebook": cookie
        }

        senders = {}
        for tid, tname in zip(selected_ids, selected_names):
            try:
                fbt = fbTools(dataFB, tid)
                sender = MessageSender(fbt, dataFB, fb)
                sender.get_last_seq_id()
                if sender.connect_mqtt():
                    senders[tid] = (sender, tname)
                    print(f"[✓] {account_name} → Kết nối MQTT box: {tname} ({tid})")
                else:
                    print(f"[✗] {account_name} → Không kết nối được box: {tname}")
            except Exception as e:
                print(f"[!] {account_name} → Lỗi box {tname}: {e}")

        if not senders:
            print(f"[✗] {account_name} → Không có box nào kết nối được, dừng process.")
            return

        print(f"\n[*] {account_name} → Bắt đầu treo {len(senders)} box...")

        while True:
            msg = random.choice(message_files)
            for tid, (sender, tname) in senders.items():
                try:
                    ok = sender.send_message(msg, tid)
                    status = "✓" if ok else "✗"
                    print(f"[{status}] {account_name} → {tname}: {msg[:40]}")
                except Exception as e:
                    print(f"[!] {account_name} → {tname}: Lỗi gửi: {e}")
            time.sleep(delay)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[!] Process {account_name} lỗi: {e}")

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    clr()
    print(taobanner())
    print("=" * 55)
    print("   TOOL MES MQTT V6 BY DZI")
    print("=" * 55 + "\n")

    don_ram_cpu_disk()

    n = nhap_so_hop_le("Số lượng tài khoản: ", min_val=1)

    chon_loai_cookie = nhap_chon_1_hoac_2(
        "\nNhập cookie theo cách nào?\n  1. Nhập thủ công\n  2. Từ file .txt\nChọn (1/2): "
    )

    danh_sach_cookies = []

    if chon_loai_cookie == '1':
        for i in range(n):
            print(f"\n{'─'*45}")
            print(f"  TÀI KHOẢN {i+1}/{n}")
            print(f"{'─'*45}")
            while True:
                cookie = input("Cookie: ").strip().replace('"', '').replace("'", '')
                if cookie and 'c_user=' in cookie:
                    danh_sach_cookies.append(cookie)
                    break
                print("[!] Cookie không hợp lệ (thiếu c_user=), nhập lại.")
    else:
        files_txt = liet_ke_file_txt('.')
        if not files_txt:
            print("[!] Không tìm thấy file .txt nào trong thư mục hiện tại.")
            return
        print("\nDanh sách file .txt tìm thấy:")
        for idx, fn in enumerate(files_txt, 1):
            print(f"  {idx}. {fn}")
        while True:
            try:
                chon_file_idx = int(input(f"\nChọn file (1-{len(files_txt)}): ").strip())
                if 1 <= chon_file_idx <= len(files_txt):
                    break
                print(f"[!] Nhập số từ 1 đến {len(files_txt)}, nhập lại.")
            except ValueError:
                print("[!] Phải nhập số nguyên, nhập lại.")
        ten_file_cookie = files_txt[chon_file_idx - 1]
        try:
            with open(ten_file_cookie, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines() if l.strip() and 'c_user=' in l]
            if not lines:
                print(f"[!] File '{ten_file_cookie}' không có cookie hợp lệ nào. Thoát.")
                return
            danh_sach_cookies = lines[:n]
        except Exception as e:
            print(f"[!] Đọc file lỗi: {e}. Thoát.")
            return

        print(f"\n[*] Đang check {len(danh_sach_cookies)} cookie sống/die...")
        cookies_song = []
        for idx, ck in enumerate(danh_sach_cookies, 1):
            cl = xemcookiesonghaychet(ck)
            if cl["status"] == "success":
                print(f"  [{idx}] ✓ SỐNG - {cl['name']} (ID: {cl['user_id']})")
                cookies_song.append((ck, cl['name'], cl['user_id']))
            else:
                print(f"  [{idx}] ✗ DIE  - {cl['msg']}")
        print(f"\n[*] Kết quả: {len(cookies_song)}/{len(danh_sach_cookies)} cookie sống.")
        if not cookies_song:
            print("[!] Không có cookie sống nào. Thoát.")
            return
        print(f"[*] Sẽ treo {len(cookies_song)} tài khoản sống.")
        danh_sach_cookies = [ck for ck, _, _ in cookies_song]

    chon_loai_box = nhap_chon_1_hoac_2(
        "\nChọn box theo cách nào?\n  1. Chọn từ danh sách box của tài khoản đầu tiên\n  2. Nhập ID box thủ công\nChọn (1/2): "
    )

    selected_ids = []
    selected_names = []

    if chon_loai_box == '1':
        print("\n[*] Đang lấy danh sách box từ tài khoản đầu tiên...")
        cookie_dau = danh_sach_cookies[0]
        fb_tmp = None
        try:
            fb_tmp = DzixMode(cookie_dau)
        except Exception as e:
            print(f"[!] Không khởi tạo được tài khoản đầu: {e}. Thoát.")
            return
        if not fb_tmp or not fb_tmp.fb_dtsg:
            print("[!] Không lấy được fb_dtsg. Thoát.")
            return
        result = lay_danh_sach_box(cookie_dau, fb_tmp.fb_dtsg, fb_tmp.user_id)
        if not result or "error" in result:
            err = result.get('error', 'None') if result else 'None'
            print(f"[!] Lỗi lấy box: {err}. Thoát.")
            return
        threads_list = result.get('threads') or []
        if not threads_list:
            print("[!] Không có box nào. Thoát.")
            return
        print(f"\nTìm thấy {len(threads_list)} box:")
        print("=" * 55)
        for idx, t in enumerate(threads_list, 1):
            name = t['thread_name'][:45] + ('...' if len(t['thread_name']) > 45 else '')
            print(f"{idx}. {name}")
            print(f"   ID: {t['thread_id']}")
            print("─" * 50)
        while True:
            raw = input("Chọn box (VD: 1,3,5): ").strip()
            selected = chon_box(raw, len(threads_list))
            if selected:
                break
            print("[!] Không chọn được box nào, nhập lại.")
        selected_ids = [threads_list[k-1]['thread_id'] for k in selected]
        selected_names = [threads_list[k-1]['thread_name'] for k in selected]
    else:
        while True:
            raw_ids = input("Nhập ID box (nhiều ID cách nhau bằng dấu ,): ").strip()
            ids = [x.strip() for x in raw_ids.split(',') if x.strip().isdigit()]
            if ids:
                selected_ids = ids
                selected_names = [f"Box_{x}" for x in ids]
                break
            print("[!] Không có ID hợp lệ, nhập lại.")

    files_txt_all = liet_ke_file_txt('.')
    if not files_txt_all:
        print("[!] Không tìm thấy file .txt nào trong thư mục để làm nội dung.")
        return
    print("\nDanh sách file .txt nội dung:")
    for idx, fn in enumerate(files_txt_all, 1):
        print(f"  {idx}. {fn}")
    print("Nhập số thứ tự các file (VD: 1,3), hoặc Enter để chọn tất cả:")
    while True:
        raw_fn = input("Chọn file nội dung: ").strip()
        if not raw_fn:
            chon_files = files_txt_all
            break
        try:
            idxs = [int(x.strip()) for x in raw_fn.split(',') if x.strip()]
            chon_files = [files_txt_all[i-1] for i in idxs if 1 <= i <= len(files_txt_all)]
            if chon_files:
                break
            print("[!] Không có file nào hợp lệ, nhập lại.")
        except:
            print("[!] Định dạng không đúng, nhập lại.")

    messages = []
    for fp in chon_files:
        try:
            messages.extend(tai_file(fp))
        except Exception as e:
            print(f"[!] {e}")
    if not messages:
        print("[!] Nội dung rỗng. Thoát.")
        return

    while True:
        try:
            delay_input = input("Delay mỗi vòng (giây, khuyến nghị 10-60, Enter = 15): ").strip()
            delay = float(delay_input) if delay_input else 15.0
            if delay < 1:
                print("[!] Delay quá nhỏ, tự đặt 10 giây.")
                delay = 10.0
            break
        except ValueError:
            print("[!] Nhập số hợp lệ, nhập lại.")

    processes = []
    for i, cookie in enumerate(danh_sach_cookies):
        cl = xemcookiesonghaychet(cookie)
        acc_name = cl.get('name', f'Acc_{i+1}') if cl['status'] == 'success' else f'Acc_{i+1}'
        if cl['status'] != 'success':
            print(f"[✗] Cookie {i+1} die lúc khởi động: {cl['msg']}. Bỏ qua.")
            continue
        print(f"\n[*] Khởi động process: {acc_name} → {len(selected_ids)} box | delay {delay}s")
        p = multiprocessing.Process(
            target=worker_treo_mes,
            args=(cookie, acc_name, selected_ids, selected_names, messages, delay)
        )
        processes.append(p)
        p.start()

    if not processes:
        print("\n[!] Không có tài khoản nào được khởi động. Thoát.")
        return

    print(f"\n{'='*55}")
    print(f"  Đã khởi động {len(processes)} process. Ctrl+C để dừng.")
    print(f"{'='*55}")

    try:
        loop_count = 0
        while True:
            time.sleep(1)
            loop_count += 1
            if loop_count % 300 == 0:
                don_ram_cpu_disk()
    except KeyboardInterrupt:
        print("\n[*] Dừng tất cả process...")
        for p in processes:
            p.terminate()
        don_ram_cpu_disk()
        print("[✓] Đã dừng tool.")
        os._exit(0)

if __name__ == "__main__":
    main()