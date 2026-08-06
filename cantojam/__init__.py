"""cantojam (協音): melody and tone fit for Cantonese lyrics."""

from .check import check
from .contour import build_contour, render
from .jyutping import Lexicon, syllabify, tone_of
from .lexicon import Lexicon as WordList, rime
from .model import ToneModel

__version__ = "0.1.0"
__all__ = ["check", "build_contour", "render", "Lexicon", "syllabify",
           "tone_of", "ToneModel", "WordList", "rime"]
