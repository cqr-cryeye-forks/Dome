import pathlib
from typing import Final

ROOT_PATH: Final[pathlib.Path] = pathlib.Path(__file__).parent
WORDLIST_PATH: Final[pathlib.Path] = ROOT_PATH.joinpath("wordlist.txt")
CONFIG_PATH: Final[pathlib.Path] = ROOT_PATH.joinpath("config.api")
