import subprocess

class Command:

  def exec(self, command):

    if isinstance(command, str):
      command = [command]

    command_str = " ".join(command)
    print(f"Executing: {command_str}")
    return subprocess.check_output(command, shell=False)
