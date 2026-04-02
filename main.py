"""
抖音视频去水印插件 for AstrBot
当用户发送抖音视频链接时，自动调用 API 去除水印并返回无水印视频地址。
"""

import re
import urllib.parse
from typing import Optional

import aiohttp
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api.message_components import Plain


class WatermarkRemover(Star):
    """去水印插件主类"""

    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("水印去除插件已加载，支持抖音视频链接去水印")

    async def _extract_url(self, text: str) -> Optional[str]:
        """从文本中提取第一个 URL"""
        url_pattern = r"https?://[^\s]+"
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    def _is_douyin_url(self, url: str) -> bool:
        """判断是否为抖音/TikTok 链接"""
        douyin_domains = [
            "douyin.com", "douyin.cn", "iesdouyin.com",
            "tiktok.com", "v.douyin.com", "dy.com"
        ]
        url_lower = url.lower()
        return any(domain in url_lower for domain in douyin_domains)

    async def _call_api(self, video_url: str) -> Optional[dict]:
        """调用去水印 API"""
        api_base = "https://api-v2.cenguigui.cn/api/douyin/api.php"
        encoded_url = urllib.parse.quote(video_url, safe="")
        full_url = f"{api_base}?url={encoded_url}"
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(full_url) as resp:
                    if resp.status != 200:
                        logger.error(f"API 请求失败，HTTP 状态码: {resp.status}")
                        return None
                    return await resp.json()
        except Exception as e:
            logger.error(f"网络请求异常: {e}")
            return None

    def _extract_video_url(self, api_data: dict) -> Optional[str]:
        """从 API 返回数据中提取无水印视频链接"""
        # 优先从 data 字段提取
        if "data" in api_data and api_data["data"]:
            data = api_data["data"]
            if isinstance(data, str) and data.startswith("http"):
                return data
            if isinstance(data, dict):
                for key in ["video_url", "url", "play_url", "video", "nwm_video_url"]:
                    if key in data and data[key] and isinstance(data[key], str):
                        return data[key]
        # 直接检查顶层字段
        for key in ["video_url", "url", "play_url", "nwm_url"]:
            if key in api_data and api_data[key] and isinstance(api_data[key], str):
                return api_data[key]
        return None

    async def _process_watermark_removal(self, url: str) -> str:
        """处理去水印核心逻辑，返回要回复的文本"""
        api_data = await self._call_api(url)
        if not api_data:
            return "❌ 解析失败：无法连接到去水印服务，请稍后再试。"

        code = api_data.get("code", 0)
        msg = api_data.get("msg", "未知错误")

        if code != 200:
            error_msg = f"❌ 解析失败：{msg}\n"
            if "text" in api_data and isinstance(api_data["text"], dict):
                text_msg = api_data["text"].get("msg", "")
                if text_msg:
                    error_msg += f"提示：{text_msg}"
            return error_msg

        video_url = self._extract_video_url(api_data)
        if not video_url:
            return f"⚠️ 解析成功但未能提取到视频链接，API 原始返回：\n{api_data}"

        return (
            f"✅ 去水印成功！\n"
            f"📹 无水印视频链接：\n{video_url}\n\n"
            f"💡 提示：点击链接即可观看或下载，部分链接可能需要复制到浏览器打开。"
        )

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，当包含抖音链接时自动处理"""
        message_text = event.message_str
        if not message_text:
            return

        # 忽略机器人自己发送的消息（防止死循环）
        if event.is_send_by_self:
            return

        # 提取链接
        video_url = await self._extract_url(message_text)
        if not video_url:
            return

        # 仅处理抖音相关链接
        if not self._is_douyin_url(video_url):
            return

        # 发送“处理中”提示（使用 event.send 直接发送，因为不能 yield 两次？实际上 yield 多次是允许的）
        # 但为了避免复杂，先 yield 提示，再 yield 结果
        yield event.plain_result("🔄 正在解析视频，请稍候...")

        result_msg = await self._process_watermark_removal(video_url)
        yield event.plain_result(result_msg)

    async def terminate(self):
        """插件被卸载/停用时的清理工作（可选）"""
        logger.info("水印去除插件已卸载")
