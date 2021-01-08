"""
Patch a .rom file from Konami4 to Konami5 (SCC) mapper
"""
import os
import glob
import subprocess
import hashlib

from konami_scc.compile import compile
from konami_scc.games import nemesis3


def loadrom(filename):
    """Load a rom file"""
    with open(filename, 'rb') as stream:
        return bytearray(stream.read())


def check_hash(data, expected_hash):
    """Check that the data is what we expect"""
    h = hashlib.md5(data).hexdigest()
    assert h == expected_hash, 'Incorrect hash. Are you using the right ROM?'


def patch_mapper(rom):
    """Patch mapper writes from Konami4 to Konami5"""
    for offset in range(len(rom) - 2):
        if (rom[offset] == 0x32 and
            rom[offset + 1] == 0x00 and
            rom[offset + 2] in [0x60, 0x80, 0xa0]):
            rom[offset + 2] += 0x10

PATCH_IGNORE_LIST = [0x20daa, 0x23340, 0x20beb]
#CHANNEL_OFFSET = -0xc000  # 0e00h -> 02000h
CHANNEL_OFFSET = +0x0e00  # 0e00h -> 0ee00h


def offset_address(rom, index, offset):
    """Modify an address in the ROM by a certain amount"""
    addr = rom[index] + rom[index + 1] * 256
    addr += offset
    rom[index] = addr & 255
    rom[index + 1] = addr >> 8


def patch_music_channel_locations(rom):
    """Patch scc player to move channel data locations"""
    for offset in range(0x20000, 0x213f0):
        if offset in PATCH_IGNORE_LIST:
            continue
        if (rom[offset] == 0xdd and
            rom[offset + 1] == 0x21 and
            (rom[offset + 3] & 0xfc) == 0xe0):
            offset_address(rom, offset + 2, CHANNEL_OFFSET)
        if (rom[offset] in [0x01, 0x11, 0x21, 0x32, 0x3a, 0x22, 0x2a] and
            (rom[offset + 2] & 0xfc) == 0xe0):
            offset_address(rom, offset + 1, CHANNEL_OFFSET)


def patch_bios_psg_calls(rom):
    """Patch replace calls to bios psg_write function with our own function"""
    for offset in range(0x20000, len(rom) - 4):
        if (rom[offset] == 0xcd and
            rom[offset + 1] == 0x93 and
            rom[offset + 2] == 0x00):
            rom[offset + 1] = 0xe8;
            rom[offset + 2] = 0x7e;


def save_kss_file(filename, rom):
    """Save KSS file containing the new music"""
    kss = loadrom('nemesis3_kss_header.bin')
    for page in [0x10, 0x0, 0x0, 0x11, 0x12, 0x13]:
        offset = page * 8 * 1024
        kss += rom[offset:offset + 8 * 1024]

    with open(filename, 'wb') as stream:
        stream.write(kss)


rom = loadrom('vkiller.rom')
scc_rom = loadrom('nemesis3.rom')
check_hash(rom, '66da3107684286d1eba45efb8eae9113')
check_hash(scc_rom[0x14000:0x1a000], '61c33112a5a2cefd1df81dc1434aa42a')

rom = rom + scc_rom[0x14000:0x1a000] + b' ' * 0x1a000

# Nemesis 3 kick drum fix
# See: https://www.msx.org/forum/msx-talk/general-discussion/nemesis-3-gofers-ambition-episode-ii-bass-drum-lost
assert rom[0x21484] == 0x0a
#rom[0x21484] = 0xf0  # make kick envelope longer
# kick fix (maybe?)
rom[0x21485] = 0x90
rom[0x21486] = 0
# snare fix (maybe?)
rom[0x21487] = 0x90
rom[0x21488] = 0

# kick
rom[0x213e0] = 0xc0
rom[0x213e1] = 0

# snare click
rom[0x21404] = 0xa0
rom[0x21405] = 0

# move the stack to 0xfaf0. this is a bit of memory
# that is used by the MSX BASIC 'PAINT' command so it
# is unused for our purposes. This then frees up the area
# that Vampire Killer has reserved for the stack:
# 0xee00 - 0xf100. We then use this area of memory
# for the Nemesis 3 SCC player's state data
rom[0x0078] = 0xfa
rom[0x0077] = 0xf0

# there are lots of these, and some of the drums
# will iterate through a list of them over time


# compile new music into ROM
compile('mml/vkiller_scc.mml', rom, nemesis3, 0x1a000, 0x7510, 0x8000)

save_kss_file('vkiller_scc.kss', rom)

patch_mapper(rom)
patch_music_channel_locations(rom)
patch_bios_psg_calls(rom)

for filename in glob.glob('vkiller_patch*.bin'):
    os.remove(filename)

# compile patches
try:
    subprocess.check_output(['sjasmplus', 'vkiller_scc.asm'])
except subprocess.CalledProcessError as exc:
    print(exc.output)
    exit(-1)

# apply patches
patches = glob.glob('vkiller_patch*.bin')
for patch_filename in patches:
    offset = int(patch_filename[13:18], 16)
    data = loadrom(patch_filename)
    for i in range(len(data)):
        rom[offset + i] = data[i]

with open('vkilscc.rom', 'wb') as stream:
    stream.write(rom)

print('done')
