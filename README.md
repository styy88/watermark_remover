# 抖音视频去水印插件 for AstrBot

## 功能简介

自动识别并处理抖音视频分享链接，调用 API 去除水印，返回无水印视频直链。

## 使用方法

1. 将插件放入 `AstrBot/data/plugins/` 目录
2. 重启 AstrBot 或在 WebUI 中重载插件
3. 在任意聊天窗口发送抖音视频链接（如 `https://v.douyin.com/xxxxx/`）
4. 等待片刻，机器人将回复无水印视频链接

## 支持的链接类型

- 抖音普通分享链接
- 抖音短链接（v.douyin.com）
- 抖音极速版链接
- TikTok 链接（部分支持）

## 注意事项

- 去水印服务由第三方 API 提供，稳定性和解析成功率取决于该服务
- 如果解析失败，请检查视频链接是否有效或稍后再试
- 本插件仅处理抖音相关链接，其他链接不会触发

## 开发调试

- 修改代码后可在 WebUI 中点击「重载插件」热更新
- 日志输出可使用 `self.logger` 或 `from astrbot.api.logger import logger`

## 许可证

MIT
