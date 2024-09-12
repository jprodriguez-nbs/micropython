import re

NORMAL =        "\033[0;37;39m"

BOLD_GREEN =    "\033[1;32;38m"
BOLD_YELLOW =    "\033[1;33;38m"
BOLD_RED =      "\033[1;31;38m"
BOLD_PURPLE =   "\033[1;35;40m"
BOLD_BLUE =     "\033[1;34;38m"
GREY =          "\033[1;47;38m"

def remove_ascii_colors(s):
    result = re.sub('\033\\[[0-9]*;[0-9]*;[0-9]*m','', s)
    return result

