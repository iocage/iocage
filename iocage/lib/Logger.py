import os


class Logger:

    COLORS = (
        "black",
        "red",
        "green",
        "yellow",
        "blue",
        "margenta",
        "cyan",
        "white",
    )

    RESET_SEQ = "\033[0m"
    BOLD_SEQ = "\033[1m"

    LOG_LEVEL_SETTINGS = {
        "info": {"color": None},
        "notice": {"color": "magenta"},
        "verbose": {"color": "blue"},
        "spam": {"color": "green"},
        "critical": {"color": "red", "bold": True},
        "error": {"color": "red"},
        "debug": {"color": "green"},
        "warning": {"color": "yellow"}
    }

    LOG_LEVELS = (
        "critical",
        "error",
        "warning",
        "info",
        "verbose",
        "debug",
        "spam",
    )

    INDENT_PREFIX = "  "

    def __init__(self, print_level=None, log_directory="/var/log/iocage"):
        self._print_level = print_level
        self._set_log_directory(log_directory)

    @property
    def default_print_level(self):
        return "spam"

    @property
    def print_level(self):
        if self._print_level is None:
            return self.default_print_level
        else:
            return self._print_level

    @print_level.setter
    def print_level(self, value):
        self._print_level = value

    def _set_log_directory(self, log_directory):
        self.log_directory = os.path.abspath(log_directory)
        if not os.path.isdir(log_directory):
            self._create_log_directory()
        self.log(f"Log directory set to '{log_directory}'", level="spam")

    def log(self, *args, **kwargs):

        args = list(args)

        if ("message" not in kwargs) and (len(args) > 0):
            kwargs["message"] = args.pop(0)

        if ("level" not in kwargs) and (len(args) > 0):
            kwargs["level"] = args.pop(0)

        if "level" not in kwargs:
            kwargs["level"] = "info"

        self._print(**kwargs)
        # self._write(**kwargs)

    def verbose(self, message, jail=None, indent=0):
        self.log(
            message=message,
            level="verbose",
            jail=jail,
            indent=indent
        )

    def error(self,
              message,
              jail=None,
              indent=0):

        self.log(message, level="error", jail=jail, indent=indent)

    def warn(self,
             message,
             jail=None,
             indent=0):

        self.log(message, level="warning", jail=jail, indent=indent)

    def debug(self,
              message,
              jail=None,
              indent=0):

        self.log(message, level="debug", jail=jail, indent=indent)

    def spam(self,
             message,
             jail=None,
             indent=0):

        self.log(message, level="spam", jail=jail, indent=indent)

    def _print(self, message, level, jail=None, indent=0):
        if self.print_level is False:
            return

        print_level = Logger.LOG_LEVELS.index(self.print_level)
        if Logger.LOG_LEVELS.index(level) > print_level:
            return

        try:
            color = Logger.LOG_LEVEL_SETTINGS[level]["color"]
        except:
            color = "none"

        message = self._indent(message, indent)
        message = self._colorize(message, color)
        print(message)

    def _indent(self, message, level):
        indent = Logger.INDENT_PREFIX * level
        return f"{indent}{message}"

    # ToDo: support file logging
    # def _write(self, message, level, jail=None):
    #     log_file = self._get_log_file_path(level=level, jail=jail)

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
