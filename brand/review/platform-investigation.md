# 系统启动动画技术调查（未通过，仍阻断）

基线：PR #6 `3cce060`。本文件记录调查与执行环境限制，不代表完成平台技术验证。

- 生产主题 `app/src/main/res/values/themes.xml` 的启动图标仍为静态 `@drawable/ic_launcher_foreground`，根资源是包含原图位图的 inset；它不是动画载体。`MainActivity` 的系统启动回调向 Compose 传递平台起始时间。平台提供零或无效值时，现有应用页面直接显示完成态；这不构成一秒织入。
- 现有 Compose 的独立预览采用水平裁切，它不能证明真实启动逐笔绘制。加载页放大之后，静态系统图标到应用页也可能出现尺寸跳变；本次尚未解决进度/几何接力。
- Android [启动画面文档](https://developer.android.com/develop/ui/views/launch/splash-screen)支持平台动画资源，并不能证明原 PNG 可无损嵌入 AnimatedVectorDrawable，也不能证明本项目中一个候选在系统启动环境已经播放。
- [AnimationDrawable 源码](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/graphics/java/android/graphics/drawable/AnimationDrawable.java)按运行时间及每帧时长调度；不应未经验证就认定其会遵循系统动画缩放。以普通图层包装动画也不能证明启动系统会启动内部图层。
- 环境检查：SDK 只有 build-tools、cmdline-tools、platform-tools、platforms，未发现 emulator 和 system-images。`adb devices -l` 启动服务器时因 `/home/agent/.android` 只读失败。未有实际 API 34/36 动画候选、系统设置或系统启动实测；无最小失败设备演示，不能把源码推断当设备失败证据。
- 后续应以原图为视觉真值实现候选，在真实主题/Activity 分别核验根载体、逐笔中间帧、末帧、0.5×/1×/2×、animator/transition 关闭组合、系统到应用的时间和尺寸、快速 ready 立即导航。不能用静态图片加 duration 或独立预览结果充当证据。
