# -*- coding: utf-8 -*-
"""
(c) 2012-2021 Martin Wendt; see https://github.com/mar10/pyftpsync
Licensed under the MIT license: https://www.opensource.org/licenses/mit-license.php
"""

import os

import yaml

from ftpsync.cli_common import common_parser, creds_parser, verbose_parser
from ftpsync.synchronizers import CONFIG_FILE_NAME
from ftpsync.tree_command import tree_handler
from ftpsync.util import write

MANDATORY_TASK_ARGS = {"command", "remote"}
KNOWN_RUN_COMMANDS = {"upload", "download", "sync", "tree"}

KNOWN_TASK_ARGS = {
    "case",
    "create_folder",
    "debug",
    "delete_unmatched",
    "delete",
    "dry_run",
    "exclude",
    "execute",
    "files",  # tree command
    "force",
    "ftp_active",
    "here",
    "local",
    "match",
    "no_color",
    "no_keyring",
    "no_netrc",
    "no_prompt",
    "no_verify_host_keys",
    "progress",
    "prompt",
    "resolve",
    "root",
    "sort",  # tree command
    "verbose",
}

#: Boolean task options that can be overridden by passing an argument to the
#: run command. For example
#:     $ pyftpsync run --progress
#: will override the YAML setting
#:     tasks.TASK.progress: true
CLI_OVERRIDABLE_BOOL_TASK_ARGS = {
    "create_folder",
    "dry_run",
    "execute",
    "files",  # tree command
    "force",
    "no_color",
    "no_keyring",
    "no_netrc",
    "no_prompt",
    "no_verify_host_keys",
    "progress",
    "sort",  # tree command
}
_diff = CLI_OVERRIDABLE_BOOL_TASK_ARGS.difference(KNOWN_TASK_ARGS)
assert not _diff, f"Must be in KNOWN_TASK_ARGS: {_diff}"


def _set_default_task_arg(cli_args, task, name, default):
    """Add a task option to the CLI arguments namespace if not present."""
    if hasattr(cli_args, name):
        write(f"SKIP: Yaml entry sets args.{name}: already {getattr(cli_args, name)}")
        return
    value = task.get(name, default)
    write(f"Yaml entry sets args.{name} => {value}")
    setattr(cli_args, name, value)


def add_run_parser(subparsers):
    # --- Create the parser for the "run" command ------------------------------

    parser = subparsers.add_parser(
        "run",
        parents=[verbose_parser, common_parser, creds_parser],
        help="run pyftpsync with configuration from `pyftpsync.yaml` in current or parent folder",
        allow_abbrev=False,
    )

    parser.add_argument(
        "task",
        nargs="?",
        help="task to run (default: use `default_task` from `pyftpsync.yaml`)",
    )

    p_group = parser.add_mutually_exclusive_group()
    p_group.add_argument(
        "--here", action="store_true", help="use current folder as root"
    )
    p_group.add_argument(
        "--root",
        action="store_true",
        help="use location of nearest `pyftpsync.yaml` as root folder",
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="force execution if dry-run mode is configured as default in `pyftpsync.yaml`",
    )
    parser.set_defaults(command="run")

    return parser


def handle_run_command(parser, args):
    """Implement `run` sub-command."""
    MAX_LEVELS = 15

    # --- Look for `pyftpsync.yaml` in current folder and parents ---

    cur_level = 0
    cur_folder = os.getcwd()
    config_path = None
    while cur_level < MAX_LEVELS:
        path = os.path.join(cur_folder, CONFIG_FILE_NAME)
        # print("Searching for {}...".format(path))
        if os.path.isfile(path):
            config_path = path
            break
        parent = os.path.dirname(cur_folder)
        if parent == cur_folder:
            break
        cur_folder = parent
        cur_level += 1

    if not config_path:
        parser.error(
            f"Could not locate `pyftpsync.yaml` in {os.getcwd()} or {cur_level} parent folders."
        )

    # --- Parse and validate `pyftpsync.yaml` ---

    try:
        with open(config_path, "rt", encoding="utf-8-sig") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        parser.error(f"Error parsing {config_path}: {e}")

    if "tasks" not in config:
        parser.error(f"Missing entry `tasks` in {config_path}")

    common_config = config.get("common_config", {})

    # --- Figure out which task to run ---

    DEFAULT_TASK = "default"
    if args.task:
        task_name = args.task
    elif config.get("default_task"):
        task_name = config.get("default_task")
        if task_name not in config["tasks"]:
            parser.error(
                f"Invalid entry `default_task: {task_name}`: "
                f"must also define `tasks.{task_name}` in {config_path}"
            )
        # write(f"Running configured `default_task: {task_name}` from {config_path}.")
    elif DEFAULT_TASK in config["tasks"]:
        task_name = DEFAULT_TASK
        # write(f"Running `tasks.{task_name}` from {config_path}.")
    else:
        parser.error(
            "No `task` argument was passed and no default task configured.\n"
            f"Either define `tasks.{DEFAULT_TASK}` or `default_task: TASK` in {config_path}"
        )

    if task_name not in config["tasks"]:
        parser.error(f"Missing entry `tasks.{task_name}` in {config_path}")

    task = config["tasks"][task_name]

    write(f"Running task '{task_name}' from {config_path}")

    common_config.update(task)
    task = common_config

    # --- Validate task configuration ---

    task_args = set(task.keys())

    missing_args = MANDATORY_TASK_ARGS.difference(task_args)
    if missing_args:
        parser.error(
            f"Missing mandatory entries: tasks.{task_name}.{', '.join(missing_args)}"
        )

    command = task["command"]
    if command not in KNOWN_RUN_COMMANDS:
        parser.error(
            f"Invalid entry: tasks.{task_name}.command: {command}: "
            f"expected one of {', '.join(KNOWN_RUN_COMMANDS)}"
        )

    allowed_args = KNOWN_TASK_ARGS.union(MANDATORY_TASK_ARGS)
    invalid_args = task_args.difference(allowed_args)
    if invalid_args:
        parser.error(f"Invalid entries: tasks.{task_name}.{', '.join(invalid_args)}")

    # --- Override yaml entries by command line args ---

    for name in allowed_args:
        task_val = task.get(name, None)
        cli_val = getattr(args, name, None)

        # write(
        #     f"check if entry `tasks.{task_name}.{name}: {task_val}` "
        #     f"is overriden by CLI arg `--{name}={cli_val!r}`"
        # )
        if cli_val != task_val:
            override = False
            if name in CLI_OVERRIDABLE_BOOL_TASK_ARGS and cli_val is True:
                override = True
                if name == "execute" and task.get("dry_run"):
                    write("--execute was passed: Resetting dry_run mode")
                    task["dry_run"] = False
            elif name in {"here", "root"} and (args.here or args.root):
                # assert cli_val is True, cli_val
                override = True
            elif name == "verbose" and cli_val != 3:
                assert type(cli_val) is int
                override = True

            if override:
                write(
                    f"Yaml entry `tasks.{task_name}.{name}: {task_val}` "
                    f"overriden by CLI arg `--{name}={cli_val!r}`"
                )
                task[name] = cli_val

    # --- Add all configured and overridden task options to args namespace ---

    # Needed, because the subsequent command that is executed by this `run`
    # command may expect it:

    args.command = task.get("command")

    for name in KNOWN_TASK_ARGS:
        task_val = task.get(name, None)
        cli_val = getattr(args, name, None)
        if task_val is not None and task_val != cli_val:
            # write(f"Set args.{name} = {cli_val!r} => {task_val!r}")
            setattr(args, name, task_val)

    # --- Figure out local target path ---

    cur_folder = os.getcwd()
    root_folder = os.path.dirname(config_path)
    if task.get("local"):
        root_folder = os.path.join(root_folder, task["local"])
    path_ofs = os.path.relpath(os.getcwd(), root_folder)

    if cur_level == 0 or task.get("root"):
        path_ofs = ""
        args.local = root_folder
        args.remote = task.get("remote")
    elif task.get("here"):
        write(f"Using sub-branch {path_ofs} of {root_folder}")
        args.local = cur_folder
        args.remote = os.path.join(task.get("remote"), path_ofs)
    else:
        parser.error(
            "`pyftpsync.yaml` configuration was found in a parent directory. "
            "Please pass an additional argument to clarify:\n"
            f"  --root: synchronize whole project ({root_folder})\n"
            f"  --here: synchronize sub branch ({root_folder}/{path_ofs})"
        )

    # --- Set the command handler and prepare args for subsequent call
    # --- of the configured task.command

    if command in ("upload", "download", "sync"):
        # This is handled by pyftpsync.run() afterwards
        pass
    # elif command == "scan":
    #     # Fix command line args as expected by command handler
    #     args.command = scan_handler
    #     args.target = args.remote
    #     _set_default_task_arg(args, task, "files", False)
    #     _set_default_task_arg(args, task, "sort", False)
    elif command == "tree":
        # Fix command line args as expected by command handler
        args.command = tree_handler
        args.target = args.remote
        _set_default_task_arg(args, task, "files", False)
        _set_default_task_arg(args, task, "sort", False)
    else:
        raise NotImplementedError(f"Run task command {command}")
