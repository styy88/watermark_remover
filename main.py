"""
视频去水印插件 for AstrBot
支持抖音、B站、快手等主流平台视频/图片链接，自动去除水印并直接发送媒体内容。
"""

import re
import urllib.parse
from typing import Optional, List, Union

import aiohttp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api.message_components import Plain, Image, Video


class WatermarkRemover(Star):
    """去水印插件主类"""

    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("视频去水印插件已加载（直接发送模式）")

    async def _extract_url(self, text: str) -> Optional[str]:
        """从文本中提取第一个 URL"""
        url_pattern = r"https?://[^\s]+"
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    async def _call_api(self, video_url: str) -> Optional[dict]:
        """调用聚合去水印 API"""
        api_base = "https://api-v2.cenguigui.cn/api/juhe/video.php"
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

    def _guess_media_type(self, url: str) -> str:
        """根据 URL 后缀猜测媒体类型：video / image / unknown"""
        url_lower = url.lower()
        if any(url_lower.endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.flv', '.mkv', '.webm']):
            return "video"
        if any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
            return "image"
        return "unknown"

    async def _process_and_build_chain(self, url: str) -> List[Union[Plain, Image, Video]]:
        """
        处理链接并直接构建消息链（媒体或错误文本）
        """
        api_data = await self._call_api(url)
        if not api_data:
            return [Plain("❌ 解析失败：无法连接到去水印服务，请稍后再试。")]

        code = api_data.get("code", 0)
        if code != 200:
            msg = api_data.get("msg", "未知错误")
            tips = api_data.get("tips", "")
            error_text = f"❌ 解析失败：{msg}"
            if tips:
                error_text += f"\n提示：{tips}"
            return [Plain(error_text)]

        # 提取媒体 URL
        data = api_data.get("data", {})
        media_url = data.get("url") or data.get("down")
        if not media_url or not isinstance(media_url, str) or not media_url.startswith("http"):
            return [Plain(f"⚠️ 解析成功但未能提取到有效媒体链接，原始返回：\n{api_data}")]

        # 猜测媒体类型并构建消息链
        media_type = self._guess_media_type(media_url)
        if media_type == "video":
            logger.info(f"发送视频：{media_url}")
            return [Video.fromURL(media_url)]
        elif media_type == "image":
            logger.info(f"发送图片：{media_url}")
            return [Image.fromURL(media_url)]
        else:
            # 无法识别类型，降级为文本链接
            return [Plain(f"✅ 去水印成功！\n📹 媒体链接：{media_url}")]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，当包含链接时自动处理"""
        message_text = getattr(event, 'message_str', None)
        if not message_text:
            return

        # 兼容不同平台：如果存在 is_send_by_self 属性且为 True，则忽略机器人自己的消息
        if hasattr(event, 'is_send_by_self') and event.is_send_by_self:
            return

        # 提取链接
        video_url = await self._extract_url(message_text)
        if not video_url:
            return

        # 直接处理并发送媒体（无任何提示文本）
        chain = await self._process_and_build_chain(video_url)
        yield event.chain_result(chain)

    async def terminate(self):
        """插件卸载时的清理"""
        logger.info("视频去水印插件已卸载")
