#include "launcher_font_bundle.h"
#include "zh_launcher_font.inc"
#include <cstdio>

int main() {
    ImFontAtlas atlas;
    for (const int textureLimit : {2048, 4096, 8192}) {
        for (const float scale : {1.0f, 2.0f, 3.0f, 4.0f}) {
            LauncherFontRoles roles;
            if (!BuildLauncherFontBundle(atlas, kLauncherFontBytes, sizeof(kLauncherFontBytes),
                                         kLauncherFontRanges, scale, textureLimit, roles)) {
                std::fprintf(stderr, "Launcher glyph atlas failed at DPI %.1f and GPU limit %d\n", scale, textureLimit);
                return 1;
            }
            std::printf("DPI %.1f, GPU limit %d, font atlas %dx%d\n",
                        scale, textureLimit, atlas.TexWidth, atlas.TexHeight);
        }
    }
}
