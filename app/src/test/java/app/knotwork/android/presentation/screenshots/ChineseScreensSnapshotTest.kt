package app.knotwork.android.presentation.screenshots

import org.robolectric.annotation.Config

/**
 * The shared app-screen screenshots ([TranslatedScreensSnapshotTest]) in Chinese, at
 * font scale 200 %; baselines `src/test/snapshots/zh_*_fontscale200_light.png`.
 */
@Config(qualifiers = "zh-w360dp-h760dp-xhdpi")
class ChineseScreensSnapshotTest : TranslatedScreensSnapshotTest() {

    override val language: String = "zh"

    override val samples: SampleTexts = SampleTexts(
        memories = listOf(
            "喜欢简短的分条回答，不要开场白。",
            "在杭州工作，时区是东八区。",
            "周四下午三点团队例会。",
            "正在学日语，周末希望用日语回复。",
        ),
        chatName = "本周计划",
        researchTask = "调研：中国咖啡市场",
        queueStage = "队列处理",
        digestTask = "早间简报",
        digestPrompt = "按我的关注点汇总新闻",
        reportTask = "出行报告",
    )
}
