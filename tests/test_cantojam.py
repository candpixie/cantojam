import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cantojam import Lexicon, ToneModel, build_contour, check, syllabify
from cantojam.check import parse_melody, parse_note
from cantojam.contour import note_name, parse_key, render

LINES = [
    "今日天氣真係好",
    "我哋一齊去食飯",
    "佢話唔記得帶錢",
    "呢首歌真係好好聽",
    "你有冇睇過本書",
    "聽日再嚟搵我傾偈",
    "落雨嗰陣唔好出街",
    "佢買咗好多嘢返屋企",
    "街市啲生果好新鮮",
    "呢個係我嘅位置",
]


@pytest.fixture(scope="module")
def model():
    return ToneModel()


@pytest.fixture(scope="module")
def lexicon():
    return Lexicon()


class TestLexicon:
    def test_frequency_ordering_survives_serialisation(self, lexicon):
        # The corpus attests ngo3 for 我 exactly once and ngo5 hundreds of
        # times. Sorting the JSON keys once silently flipped this.
        assert lexicon.lookup("我") == "ngo5"
        assert lexicon.lookup("講") == "gong2"
        assert lexicon.lookup("心") == "sam1"
        assert lexicon.lookup("話") == "waa6"

    def test_curated_covers_colloquial_gap(self, lexicon):
        for char, expected in [("唔", "m4"), ("嘅", "ge3"), ("哋", "dei6"),
                               ("冇", "mou5"), ("嘢", "je5"), ("咗", "zo2")]:
            assert lexicon.lookup(char) == expected
            assert lexicon.source(char) == "curated"

    def test_override_wins(self):
        pinned = Lexicon({"好": "hou3"})
        assert pinned.lookup("好") == "hou3"
        assert not pinned.is_ambiguous("好")
        assert pinned.source("好") == "override"

    def test_unknown_character(self, lexicon):
        assert lexicon.lookup("龘") is None
        assert lexicon.source("龘") is None

    def test_syllabic_nasal_parses(self, lexicon):
        rows = syllabify("唔", lexicon)
        assert rows[0]["jyutping"] == "m4"
        assert rows[0]["tone"] == "4"

    def test_latin_is_skipped_not_dropped(self, lexicon):
        rows = syllabify("一個block", lexicon)
        assert [r["char"] for r in rows] == ["一", "個", "b", "l", "o", "c", "k"]
        assert all(r["skipped"] for r in rows[2:])
        assert not any(r["skipped"] for r in rows[:2])


class TestModel:
    def test_measured_ladder_disagrees_with_0243(self, model):
        # 0243 buckets tones 5 and 6 together. The corpus puts 5 with 3.
        assert model.level("5") > model.level("6")
        assert abs(model.level("5") - model.level("3")) < 0.5
        # Tone 4 is a cliff, not a rung.
        assert model.level("6") - model.level("4") > 2.5

    def test_tone_order(self, model):
        order = sorted("123456", key=model.level)
        assert order[0] == "4"
        assert set(order[-2:]) == {"1", "2"}

    def test_five_six_is_directional(self, model):
        assert model.required_direction("6", "5") == 1
        assert model.required_direction("5", "6") == -1

    def test_same_tone_has_no_hard_rule(self, model):
        for tone in "123456":
            assert model.required_direction(tone, tone) == 0

    def test_tone_one_is_a_ceiling(self, model):
        # Nothing sits above tone 1, so rising onto another tone 1 is rare
        # without being outright wrong.
        assert model.required_direction("1", "1") == 0
        assert 1 in model.discouraged_directions("1", "1")
        assert -1 not in model.discouraged_directions("1", "1")

    def test_hard_rules_are_not_discouraged(self, model):
        for a in "123456":
            for b in "123456":
                required = model.required_direction(a, b)
                if required:
                    assert required not in model.discouraged_directions(a, b)

    def test_leap_out_of_tone_four(self, model):
        assert model.suggested_interval("4", "1") >= 7

    def test_chorus_sits_above_verse(self, model):
        assert model.section_offset("chorus") > model.section_offset("verse")

    def test_unknown_section_is_neutral(self, model):
        assert model.section_offset("nonexistent") == 0.0


class TestNotes:
    @pytest.mark.parametrize("token,midi", [
        ("C4", 60), ("F4", 65), ("A4", 69), ("C5", 72), ("C3", 48),
        ("F#4", 66), ("Bb3", 58), ("60", 60),
    ])
    def test_parse_note(self, token, midi):
        assert parse_note(token) == midi

    def test_round_trip(self):
        for midi in range(48, 84):
            assert parse_note(note_name(midi)) == midi

    @pytest.mark.parametrize("bad", ["", "H4", "C", "##4"])
    def test_bad_notes_raise(self, bad):
        with pytest.raises(ValueError):
            parse_note(bad)

    def test_parse_melody_accepts_both_separators(self):
        assert parse_melody("F4 G4,A4") == [65, 67, 69]

    def test_parse_key(self):
        assert parse_key("F major")[0] == 5
        assert parse_key("Bb major")[0] == 10
        assert parse_key("F# minor")[0] == 6
        with pytest.raises(ValueError):
            parse_key("H major")


class TestContour:
    @pytest.mark.parametrize("line", LINES)
    def test_generated_contour_passes_its_own_checker(self, line):
        contour = build_contour(line, key="F major", center="F4")
        melody = [n["midi"] for n in contour["notes"]]
        result = check(line, melody)
        assert result["violations"] == []
        assert not result["length_mismatch"]

    @pytest.mark.parametrize("spread", [1.0, 1.5, 2.0, 3.0])
    def test_spread_never_breaks_the_rules(self, spread):
        for line in LINES:
            contour = build_contour(line, spread=spread, center="F4")
            melody = [n["midi"] for n in contour["notes"]]
            assert check(line, melody)["violations"] == []

    def test_spread_widens_range(self):
        line = LINES[0]
        narrow = build_contour(line, spread=1.0)
        wide = build_contour(line, spread=3.0)

        def span(c):
            pitches = [n["midi"] for n in c["notes"]]
            return max(pitches) - min(pitches)

        assert span(wide) > span(narrow)

    def test_notes_stay_in_key(self):
        contour = build_contour(LINES[0], key="F major", center="F4")
        f_major = {5, 7, 9, 10, 0, 2, 4}
        assert all(n["midi"] % 12 in f_major for n in contour["notes"])

    def test_section_moves_the_centre(self):
        verse = build_contour(LINES[0], section="verse", center="F4")
        chorus = build_contour(LINES[0], section="chorus", center="F4")
        avg = lambda c: sum(n["midi"] for n in c["notes"]) / len(c["notes"])
        assert avg(chorus) > avg(verse)

    def test_unknown_characters_are_reported(self):
        contour = build_contour("我龘你")
        assert "龘" in contour["unresolved"]

    def test_render_is_drawable(self):
        drawn = render(build_contour(LINES[0]))
        assert "今" in drawn and "\n" in drawn

    def test_empty_input(self):
        contour = build_contour("...")
        assert contour["notes"] == []


class TestCheck:
    def test_flags_a_real_violation(self):
        # 係我 is tone 6 then tone 5, which rises in 96.7% of the corpus.
        result = check("係我", [67, 60])
        assert len(result["violations"]) == 1
        assert result["violations"][0]["char"] == "我"
        assert "should rise" in result["violations"][0]["message"]

    def test_accepts_the_correct_direction(self):
        assert check("係我", [60, 62])["violations"] == []

    def test_free_pair_is_not_flagged(self):
        # 冇叫 is tone 5 then tone 3. The two sit at the same measured height,
        # so the corpus holds 72.8% of the time and neither way is wrong.
        assert check("冇叫", [67, 60])["violations"] == []
        assert check("冇叫", [60, 67])["violations"] == []

    def test_soft_tier_flags_a_ceiling(self):
        # 心心 is tone 1 twice. No required direction, but rising off tone 1
        # happens 5.2% of the time because there is nothing above it.
        result = check("心心", [60, 64])
        assert result["violations"] == []
        assert len(result["unusual"]) == 1
        assert "rare" in result["unusual"][0]["message"]

    def test_length_mismatch_is_reported(self):
        result = check("我係邊個", [60, 62])
        assert result["length_mismatch"]
        assert result["syllables"] == 4 and result["notes"] == 2

    def test_extra_notes_do_not_crash(self):
        result = check("我係", [60, 62, 64, 65])
        assert result["length_mismatch"]

    def test_violation_message_cites_corpus_size(self):
        row = check("係我", [67, 60])["violations"][0]
        assert "examples" in row["message"]


class TestCorpusAgreement:
    """The model should agree with the corpus it was built from."""

    def test_real_lyric_line_is_clean(self):
        # 我唱得不夠動人, the opening of K歌之王, with its actual melody.
        line = "我唱得不夠動人"
        melody = [62, 64, 66, 64, 62, 61, 57]
        result = check(line, melody)
        assert len(result["violations"]) <= 1
