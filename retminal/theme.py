"""Colours, themes and the pixel-art mascot sprites."""

BG = "#0a0e0a"
BG_BAR = "#070a07"
BORDER = "#1c2a1c"
FG = "#5df58a"
FG_DIM = "#47895c"
FG_BRIGHT = "#aeffc9"
FG_CYAN = "#56d3f5"
FG_RED = "#ff5f56"
FG_PROMPT = "#7cffb2"
SEL_BG = "#13351f"
DOT_RED = "#ff5f56"
DOT_YELLOW = "#ffbd2e"
DOT_GREEN = "#27c93f"

CLAWD_HEX = "#d8825f"
RETY_GREEN = (174, 255, 201, 255)
RETY_TURQ = (94, 230, 210, 255)
CLAWD_ORANGE = (216, 130, 95, 255)
CREATURE_NORMAL = [
    "...XXXXXXXXXXXX...",
    "...XX.XXXXXX.XX...",
    ".XXXXXXXXXXXXXXXX.",
    "...XXXXXXXXXXXX...",
    "....X.X....X.X....",
    "..................",
]
CREATURE_WALK = [
    "...XXXXXXXXXXXX...",
    "XX.XX.XXXXXX.XX.XX",
    ".XXXXXXXXXXXXXXXX.",
    "...XXXXXXXXXXXX...",
    ".....XX....XX.....",
    "..................",
]
CREATURE_HAPPY = [
    "...XXXXXXXXXXXX...",
    "...XX.XXXXXX.XX...",
    ".XXX.X.XXXX.X.XXX.",
    "...XXXXXXXXXXXX...",
    "....X.X....X.X....",
    "..................",
]
CREATURE_BLINK = [
    "...XXXXXXXXXXXX...",
    "...XXXXXXXXXXXX...",
    ".XXXXXXXXXXXXXXXX.",
    "...XXXXXXXXXXXX...",
    "....X.X....X.X....",
    "..................",
]
CREATURE_OOPS = [
    "...XX.XXXXXX.XX...",
    "...XX.XXXXXX.XX...",
    ".XXXXXXXXXXXXXXXX.",
    "...XXXXXXXXXXXX...",
    "....X.X....X.X....",
    "..................",
]
CREATURE_HOLD = [
    "...XXXXXXXXXXX..X.",
    "...XX.XXXXXX.XXXX.",
    ".XXXXXXXXXXXXXXX..",
    "...XXXXXXXXXXXX...",
    "....X.X....X.X....",
    "..................",
]

THEME_GREEN = {
    "bg": BG,
    "bg_bar": BG_BAR,
    "border": BORDER,
    "fg": FG,
    "dim": FG_DIM,
    "bright": FG_BRIGHT,
    "cyan": FG_CYAN,
    "prompt": FG_PROMPT,
    "input_border": "#3f7a52",
    "sel_bg": SEL_BG,
    "code_bg": "#11261a",
    "accent": FG_BRIGHT,
}
THEME_CLAUDE = {
    "bg": "#140d09",
    "bg_bar": "#0e0906",
    "border": "#5a371f",
    "fg": "#e6a07c",
    "dim": "#ab6e4f",
    "bright": "#ffdcbd",
    "cyan": "#f3b96a",
    "prompt": "#ffbf91",
    "input_border": "#b3613a",
    "sel_bg": "#3a2114",
    "code_bg": "#2a1a0e",
    "accent": CLAWD_HEX,
}
THEME_BLUE = {
    "bg": "#0a0e16",
    "bg_bar": "#06080f",
    "border": "#2b4a7a",
    "fg": "#5d9cf5",
    "dim": "#5b7eb3",
    "bright": "#a8ccff",
    "cyan": "#56c6f5",
    "prompt": "#79b4ff",
    "input_border": "#42618f",
    "sel_bg": "#163259",
    "code_bg": "#101d33",
    "accent": "#a8ccff",
}
THEME_ROSE = {
    "bg": "#160910",
    "bg_bar": "#0f0609",
    "border": "#43182c",
    "fg": "#ff8ac9",
    "dim": "#b0638d",
    "bright": "#ffc6e4",
    "cyan": "#f7a8ff",
    "prompt": "#ffb0dc",
    "input_border": "#a55480",
    "sel_bg": "#3f1330",
    "code_bg": "#2a0f1f",
    "accent": "#ffc6e4",
}
THEME_RED = {
    "bg": "#150707",
    "bg_bar": "#0d0404",
    "border": "#481818",
    "fg": "#ff6363",
    "dim": "#c25c5c",
    "bright": "#ffb5b5",
    "cyan": "#ff9a72",
    "prompt": "#ff8585",
    "input_border": "#9e3b3b",
    "sel_bg": "#3f1414",
    "code_bg": "#2a0d0d",
    "accent": "#ff7a7a",
}
THEME_PURPLE = {
    "bg": "#0f0a17",
    "bg_bar": "#090610",
    "border": "#301c4d",
    "fg": "#b98cff",
    "dim": "#8c6dc1",
    "bright": "#dcc6ff",
    "cyan": "#9f8bff",
    "prompt": "#c9a8ff",
    "input_border": "#6f4aae",
    "sel_bg": "#271145",
    "code_bg": "#1b0f30",
    "accent": "#dcc6ff",
}
THEME_CYAN = {
    "bg": "#071615",
    "bg_bar": "#041110",
    "border": "#164543",
    "fg": "#4de3e0",
    "dim": "#2f8f8c",
    "bright": "#a8fff9",
    "cyan": "#56f5ec",
    "prompt": "#7dfff9",
    "input_border": "#2f8f8c",
    "sel_bg": "#0e3c39",
    "code_bg": "#0a2725",
    "accent": "#a8fff9",
}
MC_COLORS = {
    "0": "#3c3c3c",
    "1": "#0000aa",
    "2": "#00aa00",
    "3": "#00aaaa",
    "4": "#aa0000",
    "5": "#aa00aa",
    "6": "#ffaa00",
    "7": "#aaaaaa",
    "8": "#555555",
    "9": "#5555ff",
    "a": "#55ff55",
    "b": "#55ffff",
    "c": "#ff5555",
    "d": "#ff55ff",
    "e": "#ffff55",
    "f": "#ffffff",
}
THEMES = {
    "vert": THEME_GREEN,
    "bleu": THEME_BLUE,
    "orange": THEME_CLAUDE,
    "rose": THEME_ROSE,
    "rouge": THEME_RED,
    "violet": THEME_PURPLE,
    "cyan": THEME_CYAN,
}
