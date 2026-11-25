#ifndef PORT_ZH_DIALOGUE_H
#define PORT_ZH_DIALOGUE_H

#include <stddef.h>
#include <stdint.h>

enum {
    ZH_DIALOGUE_ROM_BUS_BASE = 0x08000000,
    ZH_DIALOGUE_ROM_SIZE = 0x02000000,
    ZH_DIALOGUE_GLYPH_OFFSET = 0x01F00000,
    ZH_DIALOGUE_GLYPH_COUNT = 6400,
    ZH_DIALOGUE_GLYPH_BYTES = 128,
    ZH_DIALOGUE_FIRST_LEAD = 0x9D,
    ZH_DIALOGUE_SCRIPT_STRIDE = 24,
    ZH_DIALOGUE_MAX_GLYPHS = 128
};

#if defined(PLATFORM_PC) && defined(VERSION_JP)
void PortCheckChineseDialogueRom(const uint8_t* rom);
#endif

static inline const uint8_t* PortChineseDialogueGlyph(const uint8_t* rom, uint16_t code) {
    unsigned int lead = code >> 8;
    unsigned int trail = code & 0xFF;
    unsigned int index;

    if (lead < ZH_DIALOGUE_FIRST_LEAD || trail == 0)
        return NULL;
    index = (lead - ZH_DIALOGUE_FIRST_LEAD) * 255 + trail - 1;
    if (index >= ZH_DIALOGUE_GLYPH_COUNT)
        return NULL;
    return rom + ZH_DIALOGUE_GLYPH_OFFSET + index * ZH_DIALOGUE_GLYPH_BYTES;
}

static inline uint32_t PortChineseDialogueReadWord(const uint8_t* bytes) {
    return (uint32_t)bytes[0] | (uint32_t)bytes[1] << 8 |
           (uint32_t)bytes[2] << 16 | (uint32_t)bytes[3] << 24;
}

static inline int PortIsChineseDialogueRom(const uint8_t* rom) {
    uint32_t crc = 0xFFFFFFFFu;
    uint32_t table[256];
    unsigned int i;

    /* Check the font hook first so an unmodified ROM skips the CRC scan. */
    if (PortChineseDialogueReadWord(rom + 0x01ED3560) != 0x20990A09u)
        return 0;

    for (i = 0; i < 256; i++) {
        unsigned int bit;
        uint32_t value = i;
        for (bit = 0; bit < 8; bit++)
            value = (value >> 1) ^ ((value & 1) ? 0xEDB88320u : 0);
        table[i] = value;
    }
    for (i = 0; i < ZH_DIALOGUE_ROM_SIZE; i++)
        crc = (crc >> 8) ^ table[(crc ^ rom[i]) & 0xFF];
    return ~crc == 0xBAABFF26u;
}

static inline const uint8_t* PortChineseDialogueText(const uint8_t* rom, size_t offset) {
    size_t cursor;
    size_t length = 0;

    for (cursor = offset; cursor < ZH_DIALOGUE_ROM_SIZE; cursor += 2) {
        unsigned int lead = rom[cursor];
        uint16_t code;

        if (lead == 0)
            return rom + offset;
        if (++length > ZH_DIALOGUE_MAX_GLYPHS || cursor + 1 >= ZH_DIALOGUE_ROM_SIZE)
            break;
        code = (uint16_t)(lead << 8 | rom[cursor + 1]);
        if (code == 0x6E6E)
            continue;
        if (lead < 0x81 || (lead >= ZH_DIALOGUE_FIRST_LEAD && !PortChineseDialogueGlyph(rom, code)))
            break;
    }
    return NULL;
}

#endif
