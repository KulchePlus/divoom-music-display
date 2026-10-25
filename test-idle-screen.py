"""Standby animation and transmission limits without Bluetooth uploads."""
from datetime import datetime
from unittest.mock import patch
import idle_screen
import now_playing as core
import transmission

now=datetime(2026,10,25,23,48)
frames,speed=idle_screen.frames(core.RESOURCE_ROOT,now)
assert len(frames)==3 and speed==900
assert all(frame.size==(160,128) for frame in frames)
assert len({frame.tobytes() for frame in frames})==3
assert len({frame.crop((30,23,130,48)).tobytes() for frame in frames})==1
idle={'App':'','Title':'Нет музыки','Artist':'','Status':'Stopped'}
assert core.is_idle(idle)
assert not core.is_idle(dict(idle,App='player',Status='Paused'))
with patch('idle_screen.frames',return_value=(frames,speed)):
 assert core.animation(idle)==(frames,speed)
for maximum in (1,2,3,8):
 decoded,timing,blob,metadata=transmission.prepare(frames,speed,transmission.Settings(24576,128,maximum))
 assert len(decoded)==metadata['frames']==min(maximum,3)
 assert metadata['max_frame_bytes']<=24576
 if maximum>1: assert blob[0]==0x23 and blob[1]==min(maximum,3)
 print(maximum,'=>',metadata['frames'],'frames;',metadata['bytes'],'bytes')
print('Idle frames, unchanged clock, pause behavior and frame budget: OK')
