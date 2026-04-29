"""
视频/图片去水印插件 for AstrBot
多图时逐张发送。
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
        logger.info("视频/图片去水印插件已加载（纯媒体发送模式，支持多图逐张发送）")

    async def _extract_url(self, text: str) -> Optional[str]:
        url_pattern = r"https?://[^\s]+"
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    async def _call_api(self, media_url: str) -> Optional[dict]:
        api_base = "https://api-v2.cenguigui.cn/api/juhe/video.php"
        encoded_url = urllib.parse.quote(media_url, safe="")
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
        url_lower = url.lower()
        if any(url_lower.endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.flv', '.mkv', '.webm']):
            return "video"
        if any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
            return "image"
        video_keywords = ['/video/', 'douyinvod', 'mp4', 'playurl', 'upgcxcode', 'bilibili', 'kuaishou']
        if any(keyword in url_lower for keyword in video_keywords):
            return "video"
        return "video"

    async def _process_and_get_media_chains(self, url: str) -> List[List[Union[Plain, Image, Video]]]:
        """
        处理链接，返回多个消息链列表（每个消息链可包含一个媒体组件或错误文本）。
        例如：单个视频 -> [[Video(...)]]；多张图片 -> [[Image1], [Image2], ...]
        """
        api_data = await self._call_api(url)
        if not api_data:
            return [[Plain("❌ 解析失败：无法连接到去水印服务，请稍后再试。")]]

        code = api_data.get("code", 0)
        if code != 200:
            msg = api_data.get("msg", "未知错误")
            tips = api_data.get("tips", "")
            error_text = f"❌ 解析失败：{msg}"
            if tips:
                error_text += f"\n提示：{tips}"
            return [[Plain(error_text)]]

        data = api_data.get("data", {})

        # 1. 优先处理视频链接（url/down）
        video_url = data.get("url") or data.get("down")
        if video_url and isinstance(video_url, str) and video_url.startswith("http"):
            logger.info(f"提取到视频链接: {video_url}")
            media_type = self._guess_media_type(video_url)
            if media_type == "video":
                try:
                    return [[Video.fromURL(video_url)]]
                except Exception as e:
                    logger.error(f"发送视频失败: {e}，降级为文本链接")
                    return [[Plain(f"✅ 去水印成功！\n📹 视频链接：{video_url}")]]
            else:
                # 如果是图片，按图片处理
                try:
                    return [[Image.fromURL(video_url)]]
                except Exception as e:
                    return [[Plain(f"✅ 去水印成功！\n📹 媒体链接：{video_url}")]]

        # 2. 处理图片：优先 images 数组，其次 pic
        image_urls = []
        images = data.get("images")
        if isinstance(images, list) and images:
            for img in images:
                if isinstance(img, str) and img.startswith("http"):
                    image_urls.append(img)
        if not image_urls:
            pic = data.get("pic")
            if pic and isinstance(pic, str) and pic.startswith("http"):
                image_urls.append(pic)

        if image_urls:
            logger.info(f"提取到 {len(image_urls)} 张图片")
            chains = []
            for img_url in image_urls:
                try:
                    chains.append([Image.fromURL(img_url)])
                except Exception as e:
                    logger.error(f"发送图片失败: {e}，该图片跳过")
                    chains.append([Plain(f"⚠️ 图片发送失败：{img_url}")])
            return chains

        # 3. 没有提取到任何媒体
        logger.warning(f"未提取到有效媒体链接: {api_data}")
        return [[Plain("⚠️ 解析成功但未能提取到有效媒体链接")]]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        message_text = getattr(event, 'message_str', None)
        if not message_text:
            return

        if hasattr(event, 'is_send_by_self') and event.is_send_by_self:
            return

        media_url = await self._extract_url(message_text)
        if not media_url:
            return

        logger.info(f"检测到链接: {media_url}，开始处理")
        chains = await self._process_and_get_media_chains(media_url)
        for chain in chains:
            yield event.chain_result(chain)

    async def terminate(self):
        logger.info("视频/图片去水印插件已卸载")
