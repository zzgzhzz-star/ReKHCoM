# ReKHCoM [ZH] 构建

GitHub Actions 每天北京时间 08:17 检查上游最新正式 Release。也可以在默认分支手动运行工作流并指定上游标签。

工作流从上游标签检出源码并应用 `localization.patch`，编译两端启动器和 Android 导入逻辑。游戏核心来自同一上游发行版，下载后先核对 SHA-256。补丁冲突或任一平台构建失败时，工作流会停止发布。上游新增的启动器文案在中文词条补齐前显示英文。

日版汉化 ROM 和原版使用独立槽位，两份同时安装时可在首页切换。支持的汉化 ROM 通过完整 SHA-1 校验，已知 SHA-1 为 `7ebd009e0a3394ae2ad66e7fab77170053e90056`。工作流只使用该哈希，构建和发布均不需要 ROM。

Android 包名为 `com.rekhcom.android.zh`，签名使用仓库加密 Secret `REKHCOM_ANDROID_SIGNING`。发布任务先建立草稿，核对 Windows ZIP、Android APK 和 SHA-256 清单，再公开 Release。公开名称为上游发行名称加 `[ZH]`。

针对已发布版本的安卓界面修复可手动指定正式上游标签并选择 `android_hotfix`。工作流生成 `-zh.1` Release，沿用已经校验的 Windows ZIP。每日检查只考虑新的上游正式版本。
