class IocageException(Exception):

    def __init__(self, message, errors=None, logger=None, level="error", append_warning=False, warning=None):
        if logger is not None:
            logger.__getattribute__(level)(message)
            if append_warning is True:
                logger.warn(warning)
        super().__init__(message, errors)

# Jails


class JailDoesNotExist(IocageException):

    def __init__(self, jail, *args, **kwargs):
        msg = f"Jail '{jail.humanreadable_name}' does not exist"
        super().__init__(msg, *args, **kwargs)


class JailAlreadyExists(IocageException):

    def __init__(self, jail, *args, **kwargs):
        msg = f"Jail '{jail.humanreadable_name}' already exists"
        super().__init__(msg, *args, **kwargs)


class JailNotRunning(IocageException):

    def __init__(self, jail, *args, **kwargs):
        msg = f"Jail '{jail.humanreadable_name}' is not running"
        super().__init__(msg, *args, **kwargs)


class JailAlreadyRunning(IocageException):

    def __init__(self, jail, *args, **kwargs):
        msg = f"Jail '{jail.humanreadable_name}' is already running"
        super().__init__(msg, *args, **kwargs)


class JailNotFound(IocageException):

    def __init__(self, text, *args, **kwargs):
        msg = f"No jail matching '{text}' was found"
        super().__init__(msg, *args, **kwargs)


class JailUnknownIdentifier(IocageException):

    def __init__(self, *args, **kwargs):
        msg = "The jail has not identifier yet"
        super().__init__(msg, *args, **kwargs)

# JailConfig


class JailConfigError(IocageException):
    pass


class InvalidJailName(JailConfigError):

    def __init__(self, *args, **kwargs):
        msg = (
            "Invalid jail name: "
            "Names have to begin and end with an alphanumeric character"
        )
        super().__init__(msg, *args, **kwargs)


class JailConigZFSIsNotAllowed(JailConfigError):

    def __init__(self, *args, **kwargs):
        msg = (
            "jail_zfs is disabled"
            "despite jail_zfs_dataset is configured"
        )
        super().__init__(msg, *args, **kwargs)


class InvalidJailConfigValue(JailConfigError):

    def __init__(self, property_name, jail=None, reason=None, **kwargs):
        msg = f"Invalid value for property '{property_name}'"
        if jail is not None:
            msg += f" of jail {jail.humanreadable_name}"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, **kwargs)


class InvalidJailConfigAddress(InvalidJailConfigValue):

    def __init__(self, value, **kwargs):
        reason = f"expected \"<nic>|<address>\" but got \"{value}\""
        super().__init__(
            reason=reason,
            **kwargs
        )


class JailConfigNotFound(Exception):
    # This is a silent error internally used

    def __init__(self, config_type, *args, **kwargs):
        msg = f"Could not read {config_type} config"
        Exception.__init__(self, msg, *args, **kwargs)

# Releases


class ReleaseNotFetched(IocageException):

    def __init__(self, name, *args, **kwargs):
        msg = f"Release '{name}' does not exist or is not fetched locally"
        super().__init__(msg, *args, **kwargs)

# General


class IocageNotActivated(IocageException):

    def __init__(self, *args, **kwargs):
        msg = (
            "iocage is not activated yet - "
            "please run `iocage activate` first and select a pool"
        )
        super().__init__(msg, *args, **kwargs)


class CommandFailure(IocageException):

    def __init__(self, returncode, *args, **kwargs):
        msg = f"Command exited with {returncode}"
        super().__init__(msg, *args, **kwargs)

# Host, Distribution


class DistributionUnknown(IocageException):

    def __init__(self, distribution_name, *args, **kwargs):
        msg = f"Unknown Distribution: {distribution_name}"
        super().__init__(msg, *args, **kwargs)

# Storage


class UnmountFailed(IocageException):

    def __init__(self, mountpoint, *args, **kwargs):
        msg = f"Failed to unmount {mountpoint}"
        super().__init__(msg, *args, **kwargs)


class MountFailed(IocageException):

    def __init__(self, mountpoint, *args, **kwargs):
        msg = f"Failed to mount {mountpoint}"
        super().__init__(msg, *args, **kwargs)


class DatasetNotMounted(IocageException):

    def __init__(self, dataset, *args, **kwargs):
        msg = f"Dataset '{dataset.name}' is not mounted"
        super().__init__(msg, *args, **kwargs)


class DatasetNotAvailable(IocageException):

    def __init__(self, dataset_name, *args, **kwargs):
        msg = f"Dataset '{dataset_name}' is not available"
        super().__init__(msg, *args, **kwargs)


class DatasetNotJailed(IocageException):

    def __init__(self, dataset, *args, **kwargs):
        name = dataset.name
        msg = f"Dataset {name} is not jailed."
        warning = f"Run 'zfs set jailed=on {name}' to allow mounting"
        kwargs["append_warning"] = warning
        super().__init__(msg, *args, **kwargs)


class ZFSPoolInvalid(IocageException, TypeError):

    def __init__(self, consequence=None, *args, **kwargs):

        msg = "Invalid ZFS pool"

        if consequence is not None:
            msg += f": {consequence}"

        IocageException.__init__(self, msg, *args, **kwargs)


class ZFSPoolUnavailable(IocageException):

    def __init__(self, pool_name, *args, **kwargs):
        msg = f"ZFS pool '{pool_name}' is UNAVAIL"
        super().__init__(msg, *args, **kwargs)

# Network


class VnetBridgeMissing(IocageException):

    def __init__(self, *args, **kwargs):
        msg = "VNET is enabled and requires setting a bridge"
        super().__init__(msg, *args, **kwargs)


class InvalidNetworkBridge(IocageException, ValueError):

    def __init__(self, reason=None, *args, **kwargs):
        msg = "Invalid network bridge argument"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, *args, **kwargs)

# Release


class UnknownReleasePool(IocageException):

    def __init__(self, *args, **kwargs):
        msg = (
            "Cannot determine the ZFS pool without knowing"
            "the dataset or root_dataset"
        )
        super().__init__(msg, *args, **kwargs)


class ReleaseUpdateFailure(IocageException):

    def __init__(self, release_name, reason=None, *args, **kwargs):
        msg = f"Release update of '{release_name}' failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, *args, **kwargs)


class InvalidReleaseAssetSignature(ReleaseUpdateFailure):

    def __init__(self, release_name, asset_name, *args, **kwargs):
        msg = f"Asset {asset_name} has an invalid signature"
        super().__init__(release_name, reason=msg, *args, **kwargs)


class IllegalReleaseAssetContent(ReleaseUpdateFailure):

    def __init__(self, release_name, asset_name, reason, *args, **kwargs):
        msg = f"Asset {asset_name} contains illegal files - {reason}"
        super().__init__(release_name, reason=msg, *args, **kwargs)

# Missing Features


class MissingFeature(IocageException, NotImplementedError):

    def __init__(self, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
