# 用户提供的原图

`reference-original.jpg` 是用户发送的 1254 × 1254 JPEG 原文件，SHA-256 为
`26e338db469052cb18a0030aecd42054521ec329efa469e14056db85eef1d452`。
不修改原文件，不重新描摹文字。

`catalog/src/main/res/drawable-nodpi/brand_mark.png` 从该文件生成：按像素亮度提取
透明度并保留字形处的原始 RGB。通过以下 ImageMagick 命令重新生成（`alpha.png` 为临时文件）：

```sh
convert brand/reference-original.jpg -colorspace gray -negate -level 8%,75% alpha.png
convert brand/reference-original.jpg alpha.png -alpha off -compose CopyOpacity -composite \
  catalog/src/main/res/drawable-nodpi/brand_mark.png
```

透明提取会改变字形边缘的 alpha 和移除米白背景，并非原始 JPEG 的逐字节副本；文字的
位置与相对比例直接来自原图。系统开屏图案在 108 dp 视口内等比缩放至 75.5 dp；
测试检查字形宽度、圆形安全区、原图 SHA-256 和字形区域 RGB。深色开屏使用主题色着色。

加载页单独使用 PNG 中非零 alpha 包围盒 `[129, 418, 1125, 890)`，四周增加 2px
边距，源矩形为 `[127, 416, 1127, 892)`；按等比缩放、目标宽度约屏宽的 64%，
上限 320dp，并受可用宽高限制。启动图标仍沿用安全区规则。离线预览和已知限制见
`brand/review/README.md`；系统启动与放大后的加载页尺寸衔接尚未解决。

## 新桌面图标（2026-11-15）

`launcher-original.png` 是用户提供的 1254 × 1254 新图原件，SHA-256：
`8a505bee118bcf7bf984b594e8e01bcacd4b963cd7f5859f936caf3e34527bdc`。
只用于桌面图标；系统开屏和加载页仍使用上面的原字标。

桌面图标透明前景从新原图按以下方式提取，保留图案与文字的相对比例和不透明像素的 RGB：

```sh
convert brand/launcher-original.png -colorspace gray -negate -level 8%,75% alpha.png
convert brand/launcher-original.png alpha.png -alpha off -compose CopyOpacity -composite \
  app/src/main/res/drawable-nodpi/launcher_mark.png
```

透明提取改变边缘 alpha 并移除原图背景，深色和单色变体对同一轮廓着色；并非逐字节
显示原图。桌面前景在 108 dp 视口内等比缩放至 70 dp，所有非透明像素落在半径 33 dp
安全圆内。圆形、圆角及小尺寸图片仅为离线模拟；实际桌面显示仍需设备检查。
