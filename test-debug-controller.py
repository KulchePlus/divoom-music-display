"""Verify manual tests never overlap or trigger automatic screen uploads."""
import queue
import time
from unittest.mock import patch
from PIL import Image
import debug_image
from minitoo_app import Controller

calls = []


class FakeDisplay:
    def __init__(self, mac):
        self.sock = self

    def send_blob(self, blob):
        calls.append(blob)
        return .1

    def receive(self, timeout):
        return iter(())

    def shutdown(self, how):
        pass

    def close(self):
        pass


def until(events, name):
    deadline = time.monotonic()+4
    while time.monotonic() < deadline:
        try:
            event, data = events.get(timeout=.1)
        except queue.Empty:
            continue
        if event == name:
            return data
    raise AssertionError('No event: '+name)


events = queue.Queue()
track = {'App':'test','Title':'Song','Artist':'Artist','Status':'Playing'}
frame = Image.new('RGB', (160, 128), '#123456')
with patch('now_playing.Display', FakeDisplay), patch('now_playing.current_track', return_value=track), patch('now_playing.animation', return_value=([frame], 1000)):
    controller = Controller(events)
    controller.device_mac = "00:11:22:33:44:55"
    controller.set_debug(True)
    controller.connect()
    controller.thread.start()
    until(events, 'state')
    time.sleep(.3)
    assert not calls, 'Connecting in Debug sent an automatic image'
    image, blob, metadata = debug_image.generate('30')
    controller.send_debug('session', image, blob, metadata)
    result = until(events, 'debug_finished')
    assert result[0] == 'session' and result[1]['payload_bytes'] == 30720
    assert calls == [blob]
    time.sleep(.3)
    assert len(calls) == 1, 'Manual image was overwritten or retransmitted'
    controller.set_debug(False)
    until(events, 'sent')
    assert len(calls) == 2, 'Music card was not restored'
    controller.close()
    controller.thread.join(timeout=3)
    assert not controller.thread.is_alive()
print('Debug controller: no automatic sends, exactly one manual send, restore on close: OK')
