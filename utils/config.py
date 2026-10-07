import json

# Enum-like config values were renamed from Chinese to English. Configs saved by older
# versions (original Chinese values, or the intermediate English labels written by the
# first webui translation pass) are upgraded in memory when loaded, and written back in
# the new form the next time the webui saves the config.
#
# NOTE: this table intentionally contains Chinese strings. Do not run find/replace over it.
LEGACY_VALUE_MAP = {
    "弹幕": "Comment", "回复": "Reply", "弹幕+回复": "Comment + Reply", "礼物": "Gift",
    "关键词": "Keywords", "关键词+礼物": "Keywords + Gift", "不启用": "Disabled", "自动识别": "Auto detect",
    "回答": "Answer", "问答": "Q&A", "问题": "Question", "自定义命令": "Custom commands",
    "点歌": "Song request", "智能体": "Agent", "长期唤醒": "Persistent wake-up", "单次唤醒": "Single wake-up",
    "相似度匹配": "Similarity match", "包含关系": "Contains", "窗口截图": "Window screenshot",
    "摄像头截图": "Camera screenshot", "等待合成消息": "Pending synthesis messages",
    "待播放音频列表": "Pending audio list", "本地问答-音频": "Local Q&A - Audio",
    "本地问答-文本": "Local Q&A - Text", "直播间无消息更新闲时": "Idle: no room messages",
    "待合成消息队列更新闲时": "Idle: message queue", "待播放音频队列更新闲时": "Idle: audio queue",
    "消息产生时": "On message created", "聊天助手": "Chat assistant", "千帆大模型": "Qianfan",
    "固定角色": "Fixed role", "手机扫码": "Scan QR with phone", "模型": "Model", "其他": "Other",
    "音频播放时": "On audio playback", "知识库": "Knowledge base", "搜索引擎": "Search engine",
    "必应": "Bing", "应用": "App", "工作流": "Workflow", "问答库": "Q&A library",
    "手机扫码-终端": "Scan QR with phone - terminal", "账号密码登录": "Account & password login",
    "不登录": "No login",
    # intermediate English labels from the first webui translation pass
    "Danmaku": "Comment", "Danmaku + Reply": "Comment + Reply", "Local Q&A-音频": "Local Q&A - Audio",
    "Idle time updated when the live room has no messages": "Idle: no room messages",
    "Idle time updated by the pending-synthesis message queue": "Idle: message queue",
    "Idle time updated by the pending-playback audio queue": "Idle: audio queue",
    "When the message is generated": "On message created",
    "When the audio is played": "On audio playback",
    "Chat助手": "Chat assistant", "Qianfan Large Model": "Qianfan",
}

# `lang` (vits / bert_vits2 voice language) has its own legacy values. They are NOT part of the
# global map above because the same Chinese words are literal parameters for other TTS APIs
# (e.g. GPT-SoVITS), which must keep receiving them unchanged.
LEGACY_LANG_MAP = {"自动": "Auto", "中文": "Chinese", "英文": "English", "日文": "Japanese", "韩文": "Korean"}

# Only values stored under these keys are migrated, so free-text content such as trigger
# words or copywriting that happens to equal a legacy value is never touched.
_ENUM_KEYS = {
    "type", "mode", "trigger_position", "comment_log_type", "chat_type", "login_type",
    "model", "language", "text_lang", "text_language", "lang",
}
_LEGACY_KEY_RENAMES = {"固定角色": "Fixed role"}


def _is_enum_key(key):
    return key in _ENUM_KEYS or (isinstance(key, str) and key.endswith("_trigger_type"))


def migrate_legacy_values(node, key=None):
    """Return `node` with legacy enum values/keys replaced by their English equivalents."""
    if isinstance(node, dict):
        return {
            _LEGACY_KEY_RENAMES.get(k, k): migrate_legacy_values(v, _LEGACY_KEY_RENAMES.get(k, k))
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [migrate_legacy_values(v, key) for v in node]
    if isinstance(node, str) and key == "lang":
        return LEGACY_LANG_MAP.get(node, node)
    if isinstance(node, str) and _is_enum_key(key):
        return LEGACY_VALUE_MAP.get(node, node)
    return node


class Config:
    # Singleton pattern
    # _instance = None
    config = None

    # def __new__(cls, *args, **kwargs):
    #     if not cls._instance:
    #         cls._instance = super(Config, cls).__new__(cls)  # no longer pass *args, **kwargs
    #     return cls._instance

    def __init__(self, config_file):
        if self.config is None:
            with open(config_file, 'r', encoding="utf-8") as f:
                self.config = migrate_legacy_values(json.load(f))
    
    def __getitem__(self, key):
        return self.config.get(key)
    
    def get(self, *keys):
        result = self.config
        for key in keys:
            result = result.get(key, None)
            if result is None:
                break
        return result
