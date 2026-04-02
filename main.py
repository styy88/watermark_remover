"""
抖音视频去水印插件 for AstrBot

功能：当用户发送抖音视频链接时，自动调用 API 解析并返回无水印视频地址。
"""

import re
import urllib.parse
from typing import Optional

import aiohttp
from astrbot.api import AstrBotPlugin, Context, Plain, MessageEvent, register
from astrbot.api.logger import logger


@register(
    name="watermark_remover",
    author="AstrBot Community",
    description="发送抖音视频链接，自动去除水印并返回无水印视频地址。",
    version="1.0.0"
)
class WatermarkRemoverPlugin(AstrBotPlugin):
    """去水印插件主类"""

    async def initialize(self) -> None:
        """插件初始化"""
        logger.info("水印去除插件已加载，支持抖音视频链接去水印")

    async def _extract_url(self, text: str) -> Optional[str]:
        """
        从文本中提取第一个 URL
        
        Args:
            text: 原始消息文本
            
        Returns:
            提取到的 URL 或 None
        """
        url_pattern = r"https?://[^\s]+"
        match = re.search(url_pattern, text)
        if match:
            return match.group(0)
        return None

    def _is_douyin_url(self, url: str) -> bool:
        """
        判断是否为抖音/抖音极速版/TikTok 链接
        
        Args:
            url: 待判断的 URL
            
        Returns:
            是否为抖音相关链接
        """
        douyin_domains = [
            "douyin.com",
            "douyin.cn",
            "iesdouyin.com",
            "tiktok.com",
            "v.douyin.com",
            "dy.com",
        ]
        url_lower = url.lower()
        return any(domain in url_lower for domain in douyin_domains)

    async def _call_api(self, video_url: str) -> Optional[dict]:
        """
        调用去水印 API
        
        Args:
            video_url: 用户分享的抖音视频链接
            
        Returns:
            API 返回的 JSON 数据，失败返回 None
        """
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
                    data = await resp.json()
                    return data
        except aiohttp.ClientError as e:
            logger.error(f"网络请求异常: {e}")
            return None
        except Exception as e:
            logger.error(f"未知错误: {e}")
            return None

    def _extract_video_url(self, api_data: dict) -> Optional[str]:
        """
        从 API 返回数据中提取无水印视频链接
        
        Args:
            api_data: API 返回的 JSON 数据
            
        Returns:
            无水印视频链接或 None
        """
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
        """
        处理去水印核心逻辑
        
        Args:
            url: 抖音视频链接
            
        Returns:
            要回复的消息文本
        """
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

    @AstrBotPlugin.trigger("message")
    async def on_message(self, event: MessageEvent, context: Context) -> None:
        """
        消息处理入口
        
        Args:
            event: 消息事件对象
            context: 上下文对象
        """
        message_text = event.message_str
        if not message_text:
            return
        
        # 忽略机器人自己发送的消息
        if event.is_send_by_self:
            return
        
        video_url = await self._extract_url(message_text)
        if not video_url:
            return
        
        if not self._is_douyin_url(video_url):
            logger.debug(f"非抖音链接，忽略：{video_url}")
            return
        
        # 发送处理中提示（可选）
        yield Plain("🔄 正在解析视频，请稍候...")
        
        result_msg = await self._process_watermark_removal(video_url)
        yield Plain(result_msg)
