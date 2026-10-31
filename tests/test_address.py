import pytest

from ppe.livefeed import check_address, normalise_address


@pytest.mark.parametrize("typed,expected", [
    ("https://192.168.137.93.8080", "http://192.168.137.93:8080/video"),       # the exact slip: a dot for the colon, and https
    ("http://192.168.137.93.8080/video", "http://192.168.137.93:8080/video"),
    ("192.168.137.93:8080", "http://192.168.137.93:8080/video"),                # no http://
    ("http://192.168.137.93:8080", "http://192.168.137.93:8080/video"),         # no /video
    ("http://192.168.137.93:8080/video", "http://192.168.137.93:8080/video"),   # already right
    ("  http://192.168.137.93:8080/video  ", "http://192.168.137.93:8080/video"),
    ("rtsp://192.168.1.20:554/stream1", "rtsp://192.168.1.20:554/stream1"),      # rtsp is left alone
    ("http://10.0.0.7:8080/mjpegfeed", "http://10.0.0.7:8080/mjpegfeed"),         # another path is respected
])
def test_common_typing_slips_are_fixed(typed, expected):
    assert normalise_address(typed) == expected


def test_a_fixed_address_still_has_to_be_on_the_local_network():
    with pytest.raises(ValueError):
        check_address(normalise_address("https://8.8.8.8.8080"))
    assert check_address(normalise_address("https://192.168.137.93.8080")) == "http://192.168.137.93:8080/video"
