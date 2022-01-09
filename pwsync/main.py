#!/usr/bin/env python3

# Copyright 2022 Francis Meyvis (pwsync@mikmak.fun)

""" password sync's entry point"""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from getpass import getpass
from logging import INFO, FileHandler, basicConfig, getLogger
from os import getenv, path
from time import strftime
from typing import Optional

from .bw_cli_wrapper import BitwardenClientWrapper
from .common import LOGGER_NAME, PwsNotFound, PwsQueryInfo
from .console import console_sync
from .dataset import PasswordDataset
from .gui import gui_sync
from .kp_db_cli import KeepassDatabaseClient
from .sync import PwsSyncer
from .version import __version__


def _parse_command_line():
    parser = ArgumentParser(
        description="Synchronise 2 password databases", formatter_class=ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--from",
        required=True,
        help="synchronize from. Specify a Keepass database filename or the keyword 'bitwarden'",
    )

    parser.add_argument(
        "--to",
        required=True,
        help="synchronize to. Specify a Keepass database filename or the keyword 'bitwarden'",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="describe the action then quit without modifications",
    )

    parser.add_argument(
        "--id",
        default="folder,title",
        help="an ordered, comma separated property list, "
        + "used to identify equivalent entries among the from and to password databases",
    )

    parser.add_argument("--id-sep", default=":", help="a separator to separate the id key parts (see --id)")

    parser.add_argument(
        "--sync-all",
        action="store_true",
        help="synchronize all the password database entries. "
        + "By default only entries that have their 'pws_sync' flag attribute set, "
        + "are synchronized; not the whole database",
    )

    parser.add_argument(
        "--from-username",
        help="the username to access the 'from' password database. Overrides the env. var. PWS_FROM_USERNAME",
    )

    parser.add_argument(
        "--from-password",
        help="the password to access the 'from' password database. Overrides the env. var. PWS_FROM_PASSWORD. "
        + "Warning: this is unsafe as command-line options can leak out from the process scope, "
        + "or stored in the shell history buffer, etc. If left empty, it is prompted for on the command line",
    )

    parser.add_argument(
        "--to-username",
        help="the username to access the 'to' password database. Overrides the env. var. PWS_TO_USERNAME",
    )

    parser.add_argument(
        "--to-password",
        help="password to access the 'to' password database. Overwrites the env. var. PWS_TO_PASSWORD. "
        + "Warning: this is unsafe as command-line options can leak out from the process scope, "
        + "or stored in the shell history buffer, etc. If left empty, it is prompted for on the command line",
    )

    parser.add_argument("--gui", action="store_true", help="use a graphical user interface (not implemented)")

    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    parser.add_argument("-l", "--log-level", type=int, default=30, help="logging level")

    parser.add_argument("--log-dir", action="store", default=".", help="log directory")

    args = parser.parse_args()

    # get values from env. vars. if necessary
    if getattr(args, "from") is None:
        setattr(args, "from", getenv("PWS_FROM", None))
    if args.to is None:
        args.to = getenv("PWS_TO", None)

    args.sync = not args.sync_all

    if args.from_username is None:
        args.from_username = getenv("PWS_FROM_USERNAME", None)
    if args.from_password is None:
        args.from_password = getenv("PWS_FROM_PASSWORD", None)
    if args.to_username is None:
        args.to_username = getenv("PWS_TO_USERNAME", None)
    if args.to_password is None:
        args.to_password = getenv("PWS_TO_PASSWORD", None)
    getLogger(LOGGER_NAME).info(args)

    return args


def _create_bitwarden_dataset(
    name: str,
    username: Optional[str],
    password: Optional[str],
    query_info: PwsQueryInfo,
) -> PasswordDataset:
    session = getenv("BW_SESSION", None)
    client = BitwardenClientWrapper(session, username, password, query_info.ids)
    dataset = PasswordDataset(name, query_info, client)
    return dataset


def _create_keepass_dataset(
    name: str,
    password: Optional[str],
    query_info: PwsQueryInfo,
) -> PasswordDataset:
    if password is None:
        password = getpass(f"Password for {name}:")
    client = KeepassDatabaseClient(name, password)
    dataset = PasswordDataset(name, query_info, client)
    return dataset


def _open_password_db(
    query_info: PwsQueryInfo,
    position: str,
    name: str,
    username: Optional[str],
    password: Optional[str],
):
    if name.lower() in ["bitwarden", "bw"]:
        return _create_bitwarden_dataset(position + name.lower(), username, password, query_info)
    if path.exists(name):
        return _create_keepass_dataset(name, password, query_info)
    raise PwsNotFound(name)


def main():
    """entry point for password synchronisation"""

    args = _parse_command_line()

    basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=INFO)
    logger = getLogger(LOGGER_NAME)
    logger.setLevel(args.log_level)

    file_handler = FileHandler(strftime(path.join(args.log_dir, "pwsync_%Y_%m_%d_%H_%M_%S.log")))
    logger.addHandler(file_handler)
    logger.propagate = False  # do not further propagate to the root handler (stdout)

    query_info = PwsQueryInfo(args.id.split(","), args.id_sep, args.sync)

    from_dataset = _open_password_db(query_info, "from", getattr(args, "from"), args.from_username, args.from_password)
    to_dataset = _open_password_db(query_info, "to", args.to, args.to_username, args.to_password)
    syncer = PwsSyncer(from_dataset, to_dataset)
    syncer.sync()

    # TODO validate the password database soundness before synchronizing

    if args.gui:
        gui_sync(query_info, syncer, args.dry_run, to_dataset)
    else:
        console_sync(query_info, syncer, args.dry_run, to_dataset)


if __name__ == "__main__":
    main()
