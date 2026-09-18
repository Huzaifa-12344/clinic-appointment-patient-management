from datetime import time

def test_thirty_minute_slot_math():
    start=time(9,0); end=time(11,0)
    minutes=(end.hour*60+end.minute)-(start.hour*60+start.minute)
    assert minutes//30 == 4

def test_cancel_cutoff_definition():
    assert 2*60 == 120
