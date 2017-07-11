import subprocess

class Command:

  def exec(self, command):

    if isinstance(command, str):
      command = [command]

    command_str = " ".join(command)
    print(f"Executing: {command_str}")
    return subprocess.check_output(command, shell=False)

  def shell(self, command):
    if not isinstance(command, str):
      command = " ".join(command)

    print(f"Executing Shell: {command}")
    return subprocess.check_output(command, shell=True, universal_newlines=True)
