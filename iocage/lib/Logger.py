import os

class Logger:

  COLORS = [
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "margenta",
    "cyan",
    "white"
  ]

  RESET_SEQ = "\033[0m"
  BOLD_SEQ = "\033[1m"

  LOG_LEVEL_SETTINGS = {
    "info"    : { "color": None },
    "notice"  : { "color": "magenta" },
    "verbose" : { "color": "blue" },
    "spam"    : { "color": "green" },
    "critical": { "color": "red", "bold": True  },
    "error"   : { "color": "red" },
    "debug"   : { "color": "green" },
    "warning" : { "color": "yellow" }
  }

  LOG_LEVELS = [
    "critical",
    "error",
    "warning",
    "info",
    "verbose",
    "debug",
    "spam"
  ]

  def __init__(self, print_level="spam", log_directory="/var/log/iocage"):
    self.print_level = print_level
    self._set_log_directory(log_directory)

  def _set_log_directory(self, log_directory):
    self.log_directory = os.path.abspath(log_directory)
    if not os.path.isdir(log_directory):
      self._create_log_directory()
    self.log(f"Log directory set to '{log_directory}'", level="spam")

  def log(self, message, level="info", jail=None):
    self._print(
      message=message,
      level=level,
      jail=jail
    )
    self._write(
      message=message,
      level=level,
      jail=jail 
    )

  def verbose(self, message, jail=None):
    self.log(message, level="verbose", jail=jail)

  def error(self, message, jail=None):
    self.log(message, level="error", jail=jail)

  def warn(self, message, jail=None):
    self.log(message, level="warning", jail=jail)

  def debug(self, message, jail=None):
    self.log(message, level="debug", jail=jail)

  def spam(self, message, jail=None):
    self.log(message, level="spam", jail=jail)

  def _print(self, message, level, jail=None):
    if Logger.LOG_LEVELS.index(level) > Logger.LOG_LEVELS.index(self.print_level):
      return

    try:
      color = Logger.LOG_LEVEL_SETTINGS[level]["color"]
    except:
      color = "none"

    print(self._colorize(message, color))

  def _write(self, message, level, jail=None):
    log_file = self._get_log_file_path(level=level, jail=jail)
    # ToDo: support file logging
    
  def _get_log_file_path(self, level, jail=None):
    return self.log_directory

  def _create_log_directory(self):
    os.makedirs(self.log_directory, 0x600)
    self.log("Log directory '{log_directory}' created", level="info")

  def _get_color_code(self, color_name):
    return Logger.COLORS.index(color_name) + 30

  def _colorize(self, message, color_name=None):
    try:
      color_code = self._get_color_code(color_name)
    except:
      return message

    return f"\033[1;{color_code}m{message}\033[0m"
