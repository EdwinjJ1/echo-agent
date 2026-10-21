# echo agent（回声）

**A voice AI agent for Mac, with a Windows beta.** Press Fn+Space in any app and say what you need. Speech is recognized on your computer, and echo agent answers, reads the window you're looking at, fills in messages, sets reminders, or hands coding tasks to the Claude Code and Codex already on your machine.

**Website: [echoagent.dev](https://echoagent.dev)** · [Download for Mac](https://echoagent.dev/downloads/echo-agent.dmg) · [Windows beta](https://echoagent.dev/windows/) · [Phone app](https://echoagent.dev/mobile/) · [Changelog](https://echoagent.dev/changelog/)

[![echo agent, the voice AI agent for Mac](https://echoagent.dev/media/og-en.png)](https://echoagent.dev)

This repository is where echo agent takes bug reports and feature requests. The app itself is closed source.

## What it does

- **Talk from anywhere.** Fn+Space in any app (Alt+Space on Windows), or say "echo echo" if you turn the wake word on. English and Chinese are both recognized on your computer; recordings are never saved or uploaded.
- **Hands coding work to your agents.** "Have Claude Code fix this error" runs the task in the background with your own Claude Code, Codex, DeepSeek Harness or opencode. When one of them needs an approval, the overlay asks you, and you can answer by voice.
- **One page for every session.** The Agents page lists every Claude Code and Codex session on the Mac, including ones you started in a terminal. It has model and permission pickers, separate git worktrees per task, and one-click pull requests. [More](https://echoagent.dev/agents/)
- **Asks about your screen.** "Screenshot this, how do I turn it on?" captures the window you're using and answers from it. [More](https://echoagent.dev/screenshot-ask-ai/)
- **Works with your apps.** Fills in WeChat, Feishu and email drafts without sending them, plus reminders, calendar, notes, music, browser tabs and Shortcuts.
- **Phone remote.** Send tasks, watch progress and approve steps from your phone. End-to-end encrypted. [More](https://echoagent.dev/mobile/)
- **Your own MCP servers**, web search with sources, and a short spoken answer in Live voice mode.

Free to download. The built-in echo model has free daily uses after sign-in, or bring your own API key (Anthropic, OpenAI, Google Gemini, OpenRouter and others).

**Requirements:** macOS 15 or later on Apple silicon. The Windows beta runs on Windows 10 22H2 or Windows 11 (x64).

## Feedback

[Open an issue](../../issues/new) for bugs and ideas, or email jiaedwin0605@gmail.com. Include the version (Settings › About) and what you were doing when it went wrong.

## Learn more

- [Control Claude Code and Codex with your voice](https://echoagent.dev/claude-code-voice/)
- [echo agent vs Claude Code voice mode, Superwhisper and Wispr Flow](https://echoagent.dev/compare/)
- [echo agent for Windows](https://echoagent.dev/windows/)

---

## 中文

**回声（echo agent）是 Mac 上的语音 AI Agent，Windows 版在测试中。** 在任何应用里按 Fn+Space 说一句话，语音在本机识别。回声会直接回答，或者看一眼你正在用的窗口再回答；也能替你在微信、飞书、邮件里把话填好、记提醒，或者把编程任务交给你电脑上的 Claude Code 和 Codex。

**官网：[echoagent.dev/zh/](https://echoagent.dev/zh/)** · [下载 Mac 版](https://echoagent.dev/downloads/echo-agent.dmg) · [Windows 版](https://echoagent.dev/zh/windows/) · [手机版](https://echoagent.dev/zh/mobile/) · [更新日志](https://echoagent.dev/zh/changelog/)

这个仓库用来收问题反馈和功能建议，App 本身不开源。

- **随时开口**：任何应用里按 Fn+Space（Windows 上是 Alt+Space），打开语音唤醒后喊一声「回声回声」也行。中文、英文都在本机识别，录音不保存、不上传。
- **把编程任务派出去**：说「让 Claude Code 修好这个报错」，任务交给你自己的 Claude Code、Codex、DeepSeek Harness 或 opencode 在后台跑；它们要批准时浮窗会来问你，用嘴答也行。
- **一页管所有会话**：「Agent 管理」把这台 Mac 上的 Claude Code、Codex 会话放在一起，你在终端里开的也算；能换模型、改权限，每个任务可以在单独的 git 副本里跑，做完一键开 PR。
- **截图问**：说「截图看看这里怎么打开」，回声截下你正在用的窗口，看图回答。
- **操作常用应用**：微信、飞书、邮件只填不发，还能记提醒、查日历、记备忘录、切歌、切网页标签、跑快捷指令。
- **手机遥控**：在手机上派活、看进度、点批准，手机和 Mac 之间端到端加密。

免费下载。登录后每天有免费次数使用内置模型 echo，也可以填自己的 API Key。

**反馈**：[提 issue](../../issues/new)，或发邮件到 jiaedwin0605@gmail.com，写上版本号（设置 › 关于）和出问题时在做什么。
