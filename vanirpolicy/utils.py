def _sanitize_char(input_char, extra_allowed_characters):
    input_char_ord = ord(input_char)

    if (ord('a') <= input_char_ord <= ord('z')) \
       or (ord('A') <= input_char_ord <= ord('Z')) \
       or (ord('0') <= input_char_ord <= ord('9')) \
       or (input_char in ['@', '_', '-', '.']) \
       or (input_char in extra_allowed_characters):
        result = input_char
    else:
        result = '_'

    return result


def _sanitize_name(input_string, extra_allowed_characters, assert_sanitized):
    result = ''.join(_sanitize_char(character, extra_allowed_characters)
                    for character in input_string)

    if assert_sanitized:
        assert input_string == result, \
               'Input string was expected to be sanitized, but was not.'
    return result


def sanitize_domain_name(input_string, assert_sanitized=False):
    return _sanitize_name(input_string, {}, assert_sanitized)


def sanitize_service_name(input_string, assert_sanitized=False):
    return _sanitize_name(input_string, {'+'}, assert_sanitized)