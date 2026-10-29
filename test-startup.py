"""Windows startup command quoting and per-user registry actions (mocked)."""
from unittest.mock import patch,MagicMock
import startup
with patch.object(startup.sys,'frozen',True,create=True),patch.object(startup.sys,'executable',r'C:\Program Files\Divoom\Divoom.exe'):
 command=startup.command()
 assert command=='"C:\\Program Files\\Divoom\\Divoom.exe" --background',command
 with patch('startup.winreg.CreateKeyEx') as create,patch('startup.winreg.SetValueEx') as write:
  startup.set_enabled(True)
  assert create.call_args.args[0]==startup.winreg.HKEY_CURRENT_USER
  assert write.call_args.args[-1]==command
 with patch('startup.winreg.CreateKeyEx'),patch('startup.winreg.DeleteValue') as delete:
  startup.set_enabled(False)
  assert delete.call_args.args[1]==startup.VALUE_NAME
 with patch('startup.winreg.OpenKey'),patch('startup.winreg.QueryValueEx',return_value=(command,startup.winreg.REG_SZ)):
  assert startup.is_enabled()
 with patch('startup.winreg.OpenKey',side_effect=FileNotFoundError):
  assert not startup.is_enabled()
print('Startup command quoting, current-user registry enable/disable and state: OK')
