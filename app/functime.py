from typing import AnyStr


def prettify_time(seconds: int) -> AnyStr:
    """
    Convert seconds into a prettified time format (MM:SS).

    :param seconds: The number of seconds to convert. (int)
    :return: The prettified time string in the format MM:SS. (AnyStr)
    """

    if not seconds:
        return "00:00"

    minutes = seconds_to_minutes(seconds)
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def milliseconds_to_seconds(milliseconds: int = 0) -> int:
    return milliseconds // 1000


def seconds_to_minutes(seconds: int) -> int:
    """
    Convert seconds to minutes.

    :param seconds: The number of seconds to convert. (int)
    :return: The equivalent number of minutes. (int)
    """

    return seconds // 60
