# Each test: list of needles. A needle is a tuple of regexes that must ALL match
# inside the packet text (case-insensitive). Needles = the chat facts the answer key needs.
NEEDLES = {
    1: [(r"22nd",), (r"3 cousins",), (r"12 (kids|classmates)",)],
    2: [(r"1,?450",), (r"\b640\b",), (r"\b525\b",), (r"cousin", r"1,?800")],
    3: [(r"cilantro",), (r"tree nut",), (r"spicy",), (r"no meat|vegetarian",), (r"not coming",)],
    4: [(r"TZ=UTC",)],
    5: [(r"pearl",), (r"burnt end",)],
    6: [(r"70\.3",), (r"run-c", r"1e-4")],
    7: [(r"calls him moose",), (r"absolutely not",), (r"alternator",), (r"string cheese",)],
    8: [(r"riverside", r"carpet"), (r"no carpet",)],
    9: [(r"spielberg", r"december 18"),],
    10: [(r"april 12",), (r"wheelchair",), (r"\b250\b",), (r"kiyomizu",)],
    11: [(r"33,?320",), (r"3,?025",), (r"2,?748",)],
    12: [(r"uuid primary key",), (r"descending",), (r"secondary sort",), (r"get_session",), (r"envelope",)],
    # last-message tests: the needle is the immediately previous exchange
    13: [(r"2\+2",)],
    14: [(r"starry night",)],
    15: [(r"hold the (unit|apartment)",)],
    16: [(r"canberra",)],
}
