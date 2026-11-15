# 系统启动动画调查与 CI 实测（未通过，仍阻断）

生产主题 `app/src/main/res/values/themes.xml` 的开屏图案为静态
`@drawable/brand_startup_foreground`，包含原字标的位图，不是动画载体。桌面图标在用户
更新设计后使用独立资源，不改变开屏。`MainActivity` 把平台起始时间传给 Compose；静态
平台图标给出的时间无效时，应用显示完成态，未实现一秒逐笔织入。

PR #6 提交 `873d6c9` 的 [Instrumented CI](https://github.com/xialia150-wq/knotwork/actions/runs/43663906584)
复用 API 34 和 API 36 模拟器，执行真实 `MainActivity` 冷启动录像；分别记录 1×、0.5×、
2×、仅关闭动画器、仅关闭转场以及全部关闭。两台模拟器的正常倍率录像中，系统开屏
均显示完整静态字标；正常与全部关闭录像均能看到系统小字标切换为较大的加载页字标。
六组均返回 `COLD`，录像、设置和对应 APK 哈希位于上述 CI 的 artifacts。API 34 仅关闭
动画器的录像没有捕捉到加载页，不能据此评价该组合的交接。采集成功不代表动画需求通过。

当前 Compose 独立预览的水平裁切不是逐笔绘制，也不能证明真实系统启动动画。正常模式
的约一秒织入、系统到应用的动画时间/几何接力、不同倍率和减少动效下的目标表现均未
实现或验证。初始化不应为动画等待，错误和恢复行为也需保留。

Android [启动画面文档](https://developer.android.com/develop/ui/views/launch/splash-screen)
支持平台动画资源，并不能证明原 PNG 可无损嵌入 AnimatedVectorDrawable，也不能证明
某候选在本项目系统启动环境已经播放。[AnimationDrawable 源码](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/graphics/java/android/graphics/drawable/AnimationDrawable.java)
按运行时间及每帧时长调度，不能未经验证就认定它遵循系统动画缩放。普通图层包装动画
也不能证明启动系统会启动内部图层。

本地曾以 Potrace 1.16 对原 PNG 的 alpha 阈值生成 SVG 候选；在 1254×1254 下二值比较有
854 像素不同，并丢失连续 alpha 与原 RGB，未接入产品。它不是 AVD，也不是系统启动
试验。后续应以原图为视觉真值，验证真实动画载体、逐笔中间帧、末帧、动画缩放、系统
到应用的时间和尺寸、快速 ready 立即导航。不能用静态图片加 duration、独立预览或
手机验收代替尚未完成的动画实现。
