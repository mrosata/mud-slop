"""Tests for conversation speech pattern matching."""

from mud_slop.conversation import DEFAULT_SPEECH_PATTERNS, ConversationTracker


def make_tracker():
    return ConversationTracker(DEFAULT_SPEECH_PATTERNS)


class TestSingleWordSpeaker:
    """Verify single-word speakers still match correctly."""

    def test_says(self):
        t = make_tracker()
        result = t.match("Bob says, 'hello there'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "Bob"
        assert message == "hello there"
        assert quote == "'"

    def test_exclaims(self):
        t = make_tracker()
        result = t.match('Guard exclaims, "Stop right there!"')
        assert result is not None
        speaker, message, quote = result
        assert speaker == "Guard"
        assert quote == '"'

    def test_tells(self):
        t = make_tracker()
        result = t.match("Gandalf tells you, 'You shall not pass!'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "Gandalf"

    def test_whispers(self):
        t = make_tracker()
        result = t.match("Frodo whispers, 'the ring...'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "Frodo"

    def test_yells(self):
        t = make_tracker()
        result = t.match("Orc yells, 'Attack!'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "Orc"


class TestMultiWordSpeaker:
    """Verify multi-word speakers are matched correctly."""

    def test_two_word_speaker_exclaims(self):
        t = make_tracker()
        result = t.match("An Guard exclaims, 'Halt!'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "An Guard"

    def test_three_word_speaker_exclaims(self):
        t = make_tracker()
        result = t.match("An Alorian Guard exclaims, 'Halt!'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "An Alorian Guard"

    def test_multi_word_says(self):
        t = make_tracker()
        result = t.match("The Old Man says, 'Welcome traveler.'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "The Old Man"
        assert message == "Welcome traveler."

    def test_multi_word_tells(self):
        t = make_tracker()
        result = t.match("A Wise Elder tells you, 'Be careful out there.'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "A Wise Elder"

    def test_multi_word_whispers(self):
        t = make_tracker()
        result = t.match("The Dark Figure whispers, 'Follow me.'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "The Dark Figure"

    def test_multi_word_yells(self):
        t = make_tracker()
        result = t.match("A City Guard yells, 'Thief! Stop!'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "A City Guard"

    def test_multi_word_shouts(self):
        t = make_tracker()
        result = t.match("The Town Crier shouts, 'Hear ye!'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "The Town Crier"

    def test_multi_word_asks(self):
        t = make_tracker()
        result = t.match("A Curious Child asks, 'Who are you?'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "A Curious Child"

    def test_hyphenated_multi_word(self):
        t = make_tracker()
        result = t.match("The Half-Elf Ranger says, 'Well met.'")
        assert result is not None
        speaker, message, quote = result
        assert speaker == "The Half-Elf Ranger"

    def test_double_quote(self):
        t = make_tracker()
        result = t.match('An Alorian Guard exclaims, "Halt!"')
        assert result is not None
        speaker, message, quote = result
        assert speaker == "An Alorian Guard"
        assert quote == '"'


class TestFeedLine:
    """Test feed_line with multi-word speakers."""

    def test_single_line_speech_multi_word(self):
        t = make_tracker()
        consumed = t.feed_line(
            "An Alorian Guard exclaims, 'Halt!'",
            "An Alorian Guard exclaims, 'Halt!'",
        )
        assert consumed is True
        assert len(t.entries) == 1
        assert t.entries[0].speaker == "An Alorian Guard"
        assert t.entries[0].message == "Halt!"

    def test_multi_line_speech_multi_word(self):
        t = make_tracker()
        assert t.feed_line(
            "The Old Man says, 'Let me tell you",
            "The Old Man says, 'Let me tell you",
        )
        assert t.is_continuing()
        assert t.feed_line("a long story.'", "a long story.'")
        assert not t.is_continuing()
        assert len(t.entries) == 1
        assert t.entries[0].speaker == "The Old Man"
        assert "long story" in t.entries[0].message


class TestNonMatches:
    """Ensure non-speech lines are not matched."""

    def test_plain_text(self):
        t = make_tracker()
        assert t.match("You are standing in a field.") is None

    def test_no_quote(self):
        t = make_tracker()
        assert t.match("Bob says hello") is None

    def test_empty(self):
        t = make_tracker()
        assert t.match("") is None
