from mud_slop.input_buffer import InputBuffer


class TestInsertAndBasicState:
    def test_empty_initial_state(self):
        buf = InputBuffer()
        assert buf.text == ""
        assert buf.cursor == 0

    def test_insert_single_char(self):
        buf = InputBuffer()
        buf.insert("a")
        assert buf.text == "a"
        assert buf.cursor == 1

    def test_insert_multiple_chars(self):
        buf = InputBuffer()
        buf.insert("h")
        buf.insert("i")
        assert buf.text == "hi"
        assert buf.cursor == 2

    def test_insert_at_middle(self):
        buf = InputBuffer()
        buf.set_text("ac")
        buf._cursor = 1
        buf.insert("b")
        assert buf.text == "abc"
        assert buf.cursor == 2

    def test_insert_at_beginning(self):
        buf = InputBuffer()
        buf.set_text("bc")
        buf.move_home()
        buf.insert("a")
        assert buf.text == "abc"
        assert buf.cursor == 1


class TestBackspace:
    def test_backspace_at_end(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.backspace()
        assert buf.text == "hell"
        assert buf.cursor == 4

    def test_backspace_at_middle(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf._cursor = 3
        buf.backspace()
        assert buf.text == "helo"
        assert buf.cursor == 2

    def test_backspace_at_beginning(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_home()
        buf.backspace()
        assert buf.text == "hello"
        assert buf.cursor == 0

    def test_backspace_empty(self):
        buf = InputBuffer()
        buf.backspace()
        assert buf.text == ""
        assert buf.cursor == 0


class TestDelete:
    def test_delete_at_cursor(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf._cursor = 2
        buf.delete()
        assert buf.text == "helo"
        assert buf.cursor == 2

    def test_delete_at_beginning(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_home()
        buf.delete()
        assert buf.text == "ello"
        assert buf.cursor == 0

    def test_delete_at_end(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.delete()
        assert buf.text == "hello"
        assert buf.cursor == 5

    def test_delete_empty(self):
        buf = InputBuffer()
        buf.delete()
        assert buf.text == ""
        assert buf.cursor == 0


class TestMoveLeftRight:
    def test_move_left(self):
        buf = InputBuffer()
        buf.set_text("abc")
        buf.move_left()
        assert buf.cursor == 2

    def test_move_left_to_beginning(self):
        buf = InputBuffer()
        buf.set_text("ab")
        buf.move_left()
        buf.move_left()
        assert buf.cursor == 0

    def test_move_left_at_beginning(self):
        buf = InputBuffer()
        buf.set_text("abc")
        buf.move_home()
        buf.move_left()
        assert buf.cursor == 0

    def test_move_right(self):
        buf = InputBuffer()
        buf.set_text("abc")
        buf.move_home()
        buf.move_right()
        assert buf.cursor == 1

    def test_move_right_at_end(self):
        buf = InputBuffer()
        buf.set_text("abc")
        buf.move_right()
        assert buf.cursor == 3

    def test_left_then_right(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_left()
        buf.move_left()
        buf.move_right()
        assert buf.cursor == 4


class TestHomeEnd:
    def test_move_home(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf.move_home()
        assert buf.cursor == 0

    def test_move_end(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf.move_home()
        buf.move_end()
        assert buf.cursor == 11

    def test_home_on_empty(self):
        buf = InputBuffer()
        buf.move_home()
        assert buf.cursor == 0

    def test_end_on_empty(self):
        buf = InputBuffer()
        buf.move_end()
        assert buf.cursor == 0


class TestMoveWordLeft:
    def test_word_left_from_end(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf.move_word_left()
        assert buf.cursor == 6

    def test_word_left_twice(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf.move_word_left()
        buf.move_word_left()
        assert buf.cursor == 0

    def test_word_left_from_middle_of_word(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf._cursor = 8  # in "world"
        buf.move_word_left()
        assert buf.cursor == 6

    def test_word_left_from_beginning(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_home()
        buf.move_word_left()
        assert buf.cursor == 0

    def test_word_left_multiple_spaces(self):
        buf = InputBuffer()
        buf.set_text("hello   world")
        buf.move_word_left()
        assert buf.cursor == 8

    def test_word_left_with_punctuation(self):
        buf = InputBuffer()
        buf.set_text("hello-world")
        buf.move_word_left()
        assert buf.cursor == 6

    def test_word_left_single_word(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_word_left()
        assert buf.cursor == 0


class TestMoveWordRight:
    def test_word_right_from_start(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf.move_home()
        buf.move_word_right()
        assert buf.cursor == 5

    def test_word_right_twice(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf.move_home()
        buf.move_word_right()
        buf.move_word_right()
        assert buf.cursor == 11

    def test_word_right_from_middle(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf._cursor = 3
        buf.move_word_right()
        assert buf.cursor == 5

    def test_word_right_at_end(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_word_right()
        assert buf.cursor == 5

    def test_word_right_multiple_spaces(self):
        buf = InputBuffer()
        buf.set_text("hello   world")
        buf.move_home()
        buf.move_word_right()
        assert buf.cursor == 5

    def test_word_right_with_punctuation(self):
        buf = InputBuffer()
        buf.set_text("hello-world")
        buf.move_home()
        buf.move_word_right()
        assert buf.cursor == 5


class TestKillWordBack:
    def test_kill_word_back_at_end(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf.kill_word_back()
        assert buf.text == "hello "
        assert buf.cursor == 6

    def test_kill_word_back_middle(self):
        buf = InputBuffer()
        buf.set_text("one two three")
        buf._cursor = 7  # after "two"
        buf.kill_word_back()
        assert buf.text == "one  three"
        assert buf.cursor == 4

    def test_kill_word_back_at_beginning(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_home()
        buf.kill_word_back()
        assert buf.text == "hello"
        assert buf.cursor == 0

    def test_kill_word_back_single_word(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.kill_word_back()
        assert buf.text == ""
        assert buf.cursor == 0


class TestKillToStart:
    def test_kill_to_start_from_middle(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf._cursor = 5
        buf.kill_to_start()
        assert buf.text == " world"
        assert buf.cursor == 0

    def test_kill_to_start_from_end(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.kill_to_start()
        assert buf.text == ""
        assert buf.cursor == 0

    def test_kill_to_start_from_beginning(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_home()
        buf.kill_to_start()
        assert buf.text == "hello"
        assert buf.cursor == 0


class TestKillToEnd:
    def test_kill_to_end_from_middle(self):
        buf = InputBuffer()
        buf.set_text("hello world")
        buf._cursor = 5
        buf.kill_to_end()
        assert buf.text == "hello"
        assert buf.cursor == 5

    def test_kill_to_end_from_beginning(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.move_home()
        buf.kill_to_end()
        assert buf.text == ""
        assert buf.cursor == 0

    def test_kill_to_end_from_end(self):
        buf = InputBuffer()
        buf.set_text("hello")
        buf.kill_to_end()
        assert buf.text == "hello"
        assert buf.cursor == 5


class TestSetTextAndClear:
    def test_set_text(self):
        buf = InputBuffer()
        buf.set_text("hello")
        assert buf.text == "hello"
        assert buf.cursor == 5

    def test_set_text_replaces(self):
        buf = InputBuffer()
        buf.set_text("old")
        buf.set_text("new text")
        assert buf.text == "new text"
        assert buf.cursor == 8

    def test_clear_returns_text(self):
        buf = InputBuffer()
        buf.set_text("hello")
        result = buf.clear()
        assert result == "hello"
        assert buf.text == ""
        assert buf.cursor == 0

    def test_clear_empty(self):
        buf = InputBuffer()
        result = buf.clear()
        assert result == ""
        assert buf.text == ""
        assert buf.cursor == 0


class TestEditingWorkflow:
    """Integration-style tests simulating realistic editing sequences."""

    def test_type_then_fix_typo_in_middle(self):
        buf = InputBuffer()
        for c in "helo world":
            buf.insert(c)
        # Move back to fix "helo" -> "hello"
        buf.move_word_left()  # to start of "world"
        buf.move_word_left()  # to start of "helo"
        buf.move_right()
        buf.move_right()
        buf.move_right()
        buf.insert("l")
        assert buf.text == "hello world"

    def test_type_delete_word_retype(self):
        buf = InputBuffer()
        for c in "hello wrlod":
            buf.insert(c)
        buf.kill_word_back()
        for c in "world":
            buf.insert(c)
        assert buf.text == "hello world"
        assert buf.cursor == 11

    def test_ctrl_a_then_type(self):
        buf = InputBuffer()
        buf.set_text("world")
        buf.move_home()
        for c in "hello ":
            buf.insert(c)
        assert buf.text == "hello world"

    def test_navigate_and_delete(self):
        buf = InputBuffer()
        buf.set_text("abcdef")
        buf.move_home()
        buf.move_right()
        buf.move_right()
        buf.delete()  # delete 'c'
        assert buf.text == "abdef"
        buf.backspace()  # delete 'b'
        assert buf.text == "adef"
        assert buf.cursor == 1

    def test_kill_to_start_then_type(self):
        buf = InputBuffer()
        buf.set_text("wrong command")
        buf.kill_to_start()
        for c in "right command":
            buf.insert(c)
        assert buf.text == "right command"

    def test_word_navigation_roundtrip(self):
        buf = InputBuffer()
        buf.set_text("one two three")
        buf.move_home()
        buf.move_word_right()
        assert buf.cursor == 3
        buf.move_word_right()
        assert buf.cursor == 7
        buf.move_word_right()
        assert buf.cursor == 13
        buf.move_word_left()
        assert buf.cursor == 8
        buf.move_word_left()
        assert buf.cursor == 4
        buf.move_word_left()
        assert buf.cursor == 0
