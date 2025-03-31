#!/usr/bin/env python3

import argparse
import io
import json
import logging
import os
import pathlib
import re
import subprocess
import sys

import tes

LOGGING_FORMAT = "%(asctime)-15s - [%(levelname)s] %(message)s"
DEBUG_LOGGING_FORMAT = (
        "%(asctime)-15s - [%(name)s %(funcName)s %(lineno)d][%(levelname)s] %(message)s"
)

DEFAULT_DOCKER_CMD = "/usr/bin/docker"

#  run         Create and run a new container from an image
#  exec        Execute a command in a running container
#  ps          List containers
#  build       Build an image from a Dockerfile
#  pull        Download an image from a registry
#  push        Upload an image to a registry
#  images      List images
#  login       Authenticate to a registry
#  logout      Log out from a registry
#  search      Search Docker Hub for images
#  version     Show the Docker version information
#  info        Display system-wide information


# Obtained from https://krkeegan.com/python-argparse-group-sub-parsers/
#===========================================================================
#
# Extend Argparse to Enable Sub-Parser Groups
#
# Based on this very old issue: https://bugs.python.org/issue9341
#
# Adds the method `add_parser_group()` to the sub-parser class.
# This adds a group heading to the sub-parser list, just like the
# `add_argument_group()` method.
#
# NOTE: As noted on the issue page, this probably won't work with [parents].
# see http://bugs.python.org/issue16807
#
#===========================================================================
# Pylint doesn't like us access protected items like this
#pylint:disable=protected-access,abstract-method
#import argparse

class _SubParsersAction(argparse._SubParsersAction):

    class _PseudoGroup(argparse.Action):

        def __init__(self, container, title):
            sup = super(_SubParsersAction._PseudoGroup, self)
            sup.__init__(option_strings=[], dest=title)
            self.container = container
            self._choices_actions = []

        def add_parser(self, name, **kwargs):
            # add the parser to the main Action, but move the pseudo action
            # in the group's own list
            parser = self.container.add_parser(name, **kwargs)
            choice_action = self.container._choices_actions.pop()
            self._choices_actions.append(choice_action)
            return parser

        def _get_subactions(self):
            return self._choices_actions

        def add_parser_group(self, title):
            # the formatter can handle recursive subgroups
            grp = _SubParsersAction._PseudoGroup(self, title)
            self._choices_actions.append(grp)
            return grp

    def add_parser_group(self, title):
        #
        grp = _SubParsersAction._PseudoGroup(self, title)
        self._choices_actions.append(grp)
        return grp


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register('action', 'parsers', _SubParsersAction)


def run_local_docker(logger: "logging.Logger", docker_cmd: "str", args: "argparse.Namespace", *params: "str") -> "int":
    retval = subprocess.call(
        [
            docker_cmd,
            *params,
        ],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
    )

    return retval

def local_docker_help(docker_cmd: "str") -> "str":
    proc = subprocess.Popen(
        [
            docker_cmd,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        outs, errs = proc.communicate(timeout=15)
    except TimeoutExpired:
        proc.kill()
        outs, errs = proc.communicate()

    return errs

SUBCOMMAND_RE = re.compile(r"^  ([a-z]+)\*?\s+(.*)")

def inject_subparsers(p: "argparse.ArgumentParser", docker_cmd: "str") -> "None":
    # Let's learn the sub-commands
    help_block = local_docker_help(docker_cmd=docker_cmd)
    # print(help_block)

    current_sp = p.add_subparsers(dest="command", metavar="COMMAND")
    current_sp_grp = None
    for line in help_block.split("\n"):
        if line.endswith("Options:"):
            current_sp_grp = None
        elif line.endswith("Commands:"):
            current_sp_grp = current_sp.add_parser_group(line)
        elif current_sp is not None:
            match = SUBCOMMAND_RE.match(line)
            if match is not None:
                if match[1] == "run":
                    sp = current_sp_grp.add_parser(
                        match[1],
                        help=match[2],
                        add_help=False,
                    )
                    # run parameters
                    sp.add_argument(
                        "--add-host",
                        metavar="list",
                        action="append",
                        help="Add a custom host-to-IP mapping (host:ip)",
                    )

                    sp.add_argument(
                        "--annotation",
                        metavar="map",
                        action="append",
                        help="Add an annotation to the container (passed through to the OCI runtime)",
                    )

                    sp.add_argument(
                        "-a",
                        "--attach",
                        metavar="list",
                        action="append",
                        help="Attach to STDIN, STDOUT or STDERR",
                    )

                    sp.add_argument(
                        "--blkio-weight",
                        metavar="uint16",
                        type=int,
                        default=0,
                        help="Block IO (relative weight), between 10 and 1000, or 0 to disable",
                    )

                    sp.add_argument(
                        "--blkio-weight-device",
                        metavar="list",
                        action="append",
                        help="Block IO weight (relative device weight)",
                    )

                    sp.add_argument(
                        "--cap-add",
                        metavar="list",
                        action="append",
                        help="Add Linux capabilities",
                    )

                    sp.add_argument(
                        "--cap-drop",
                        metavar="list",
                        action="append",
                        help="Drop Linux capabilities",
                    )

                    sp.add_argument(
                        "--cgroup-parent",
                        metavar="string",
                        help="Optional parent cgroup for the container",
                    )

                    sp.add_argument(
                        "--cgroupns",
                        metavar="string",
                        help="""\
Cgroup namespace to use (host|private)
'host':    Run the container in the Docker host's cgroup namespace
'private': Run the container in its own private cgroup namespace
'':        Use the cgroup namespace as configured by the
           default-cgroupns-mode option on the daemon (default)""",
                    )

                    sp.add_argument(
                        "--cidfile",
                        metavar="string",
                        help="Write the container ID to the file",
                    )

                    sp.add_argument(
                        "--cpu-period",
                        metavar="int",
                        type=int,
                        help="Limit CPU CFS (Completely Fair Scheduler) period",
                    )

                    sp.add_argument(
                        "--cpu-quota",
                        metavar="int",
                        type=int,
                        help="Limit CPU CFS (Completely Fair Scheduler) quota",
                    )

                    sp.add_argument(
                        "--cpu-rt-period",
                        metavar="int",
                        type=int,
                        help="Limit CPU real-time period in microseconds",
                    )

                    sp.add_argument(
                        "--cpu-rt-runtime",
                        metavar="int",
                        type=int,
                        help="Limit CPU real-time runtime in microseconds",
                    )

                    sp.add_argument(
                        "-c",
                        "--cpu-shares",
                        metavar="int",
                        type=int,
                        help="CPU shares (relative weight)",
                    )

                    sp.add_argument(
                        "--cpus",
                        metavar="decimal",
                        type=float,
                        help="Number of CPUs",
                    )

                    sp.add_argument(
                        "--cpuset-cpus",
                        metavar="string",
                        help="CPUs in which to allow execution (0-3, 0,1)",
                    )

                    sp.add_argument(
                        "--cpuset-mems",
                        metavar="string",
                        help="MEMs in which to allow execution (0-3, 0,1)",
                    )

                    sp.add_argument(
                        "-d",
                        "--detach",
                        action="store_true",
                        help="Run container in background and print container ID",
                    )

                    sp.add_argument(
                        "--detach-keys",
                        metavar="string",
                        help="Override the key sequence for detaching a container",
                    )

                    sp.add_argument(
                        "--device",
                        metavar="list",
                        action="append",
                        help="Add a host device to the container",
                    )

                    sp.add_argument(
                        "--device-cgroup-rule",
                        metavar="list",
                        action="append",
                        help="Add a rule to the cgroup allowed devices list",
                    )

                    sp.add_argument(
                        "--device-read-bps",
                        metavar="list",
                        action="append",
                        help="Limit read rate (bytes per second) from a device",
                    )

                    sp.add_argument(
                        "--device-read-iops",
                        metavar="list",
                        action="append",
                        help="Limit read rate (IO per second) from a device",
                    )

                    sp.add_argument(
                        "--device-write-bps",
                        metavar="list",
                        action="append",
                        help="Limit write rate (bytes per second) from a device",
                    )

                    sp.add_argument(
                        "--device-write-iops",
                        metavar="list",
                        action="append",
                        help="Limit write rate (IO per second) from a device",
                    )

                    sp.add_argument(
                        "--disable-content-trust",
                        action="store_true",
                        help="Skip image verification",
                    )

                    sp.add_argument(
                        "--dns",
                        metavar="list",
                        action="append",
                        help="Set custom DNS servers",
                    )

                    sp.add_argument(
                        "--dns-option",
                        metavar="list",
                        action="append",
                        help="Set DNS options",
                    )

                    sp.add_argument(
                        "--dns-search",
                        metavar="list",
                        action="append",
                        help="Set custom DNS search domains",
                    )

                    sp.add_argument(
                        "--domainname",
                        metavar="string",
                        help="Container NIS domain name",
                    )

                    sp.add_argument(
                        "--entrypoint",
                        metavar="string",
                        help="Overwrite the default ENTRYPOINT of the image",
                    )

                    sp.add_argument(
                        "-e",
                        "--env",
                        metavar="list",
                        action="append",
                        help="Set environment variables",
                    )

                    sp.add_argument(
                        "--env-file",
                        metavar="list",
                        action="append",
                        help="Read in a file of environment variables",
                    )

                    sp.add_argument(
                        "--expose",
                        metavar="list",
                        action="append",
                        help="Expose a port or a range of ports",
                    )

                    sp.add_argument(
                        "--gpus",
                        metavar="gpu-request",
                        action="append",
                        help="GPU devices to add to the container ('all' to pass all GPUs)",
                    )

                    sp.add_argument(
                        "--group-add",
                        metavar="list",
                        action="append",
                        help="Add additional groups to join",
                    )

                    sp.add_argument(
                        "--health-cmd",
                        metavar="string",
                        help="Command to run to check health",
                    )

                    sp.add_argument(
                        "--health-interval",
                        metavar="duration",
                        default="0s",
                        help="Time between running the check (ms|s|m|h)",
                    )

                    sp.add_argument(
                        "--health-retries",
                        metavar="int",
                        type=int,
                        help="Consecutive failures needed to report unhealthy",
                    )

                    sp.add_argument(
                        "--health-start-interval",
                        metavar="duration",
                        default="0s",
                        help="Time between running the check during the start period (ms|s|m|h)",
                    )

                    sp.add_argument(
                        "--health-timeout",
                        metavar="duration",
                        default="0s",
                        help="Maximum time to allow one check to run (ms|s|m|h)",
                    )

                    sp.add_argument(
                        "-h",
                        "--hostname",
                        metavar="string",
                        help="Container host name",
                    )

                    sp.add_argument(
                        "--init",
                        action="store_true",
                        help="Run an init inside the container that forwards signals and reaps processes",
                    )

                    sp.add_argument(
                        "-i",
                        "--interactive",
                        action="store_true",
                        help="Keep STDIN open even if not attached",
                    )

                    sp.add_argument(
                        "--ip",
                        metavar="string",
                        help="IPv4 address (e.g., 172.30.100.104)",
                    )

                    sp.add_argument(
                        "--ip6",
                        metavar="string",
                        help="IPv6 address (e.g., 2001:db8::33)",
                    )

                    sp.add_argument(
                        "--ipc",
                        metavar="string",
                        help="IPC mode to use",
                    )

                    sp.add_argument(
                        "--isolation",
                        metavar="string",
                        help="Container isolation technology",
                    )

                    sp.add_argument(
                        "--kernel-memory",
                        metavar="bytes",
                        help="Kernel memory limit",
                    )

                    sp.add_argument(
                        "-l",
                        "--label",
                        metavar="list",
                        action="append",
                        help="Set meta data on a container",
                    )

                    sp.add_argument(
                        "--label-file",
                        metavar="list",
                        action="append",
                        help="Read in a line delimited file of labels",
                    )

                    sp.add_argument(
                        "--link",
                        metavar="list",
                        action="append",
                        help="Add link to another container",
                    )

                    sp.add_argument(
                        "--link-local-ip",
                        metavar="list",
                        action="append",
                        help="Container IPv4/IPv6 link-local addresses",
                    )

                    sp.add_argument(
                        "--log-driver",
                        metavar="string",
                        help="Logging driver for the container",
                    )

                    sp.add_argument(
                        "--log-opt",
                        metavar="list",
                        action="append",
                        help="Log driver options",
                    )

                    sp.add_argument(
                        "--mac-address",
                        metavar="string",
                        help="Container MAC address (e.g., 92:d0:c6:0a:29:33)",
                    )

                    sp.add_argument(
                        "-m",
                        "--memory",
                        metavar="bytes",
                        help="Memory limit",
                    )

                    sp.add_argument(
                        "--memory-reservation",
                        metavar="bytes",
                        help="Memory soft limit",
                    )

                    sp.add_argument(
                        "--memory-swap",
                        metavar="bytes",
                        help="Swap limit equal to memory plus swap: '-1' to enable unlimited swap",
                    )

                    sp.add_argument(
                        "--memory-swappiness",
                        metavar="int",
                        type=int,
                        default=-1,
                        help="Tune container memory swappiness (0 to 100)",
                    )

                    sp.add_argument(
                        "--mount",
                        metavar="mount",
                        action="append",
                        help="Attach a filesystem mount to the container",
                    )

                    sp.add_argument(
                        "--name",
                        metavar="string",
                        help="Assign a name to the container",
                    )

                    sp.add_argument(
                        "--network",
                        metavar="network",
                        action="append",
                        help="Connect a container to a network",
                    )

                    sp.add_argument(
                        "--network-alias",
                        metavar="list",
                        action="append",
                        help="Add network-scoped alias for the container",
                    )

                    sp.add_argument(
                        "--no-healthcheck",
                        action="store_true",
                        help="Disable any container-specified HEALTHCHECK",
                    )

                    sp.add_argument(
                        "--oom-kill-disable",
                        action="store_true",
                        help="Disable OOM Killer",
                    )

                    sp.add_argument(
                        "--oom-score-adj",
                        metavar="int",
                        type=int,
                        help="Tune host's OOM preferences (-1000 to 1000)",
                    )

                    sp.add_argument(
                        "--pid",
                        metavar="string",
                        help="PID namespace to use",
                    )

                    sp.add_argument(
                        "--pids-limit",
                        metavar="int",
                        type=int,
                        help="Tune container pids limit (set -1 for unlimited)",
                    )

                    sp.add_argument(
                        "--platform",
                        metavar="string",
                        help="Set platform if server is multi-platform capable",
                    )

                    sp.add_argument(
                        "--privileged",
                        action="store_true",
                        help="Give extended privileges to this container",
                    )

                    sp.add_argument(
                        "-p"
                        "--publish",
                        metavar="list",
                        action="append",
                        help="Publish a container's port(s) to the host",
                    )

                    sp.add_argument(
                        "-P"
                        "--publish-all",
                        action="store_true",
                        help="Publish all exposed ports to random ports",
                    )

                    sp.add_argument(
                        "--pull",
                        metavar="string",
                        choices=["always", "missing", "never"],
                        default="missing",
                        help="Pull image before running (\"always\", \"missing\", \"never\")",
                    )

                    sp.add_argument(
                        "-q",
                        "--quiet",
                        action="store_true",
                        help="Suppress the pull output",
                    )

                    sp.add_argument(
                        "--read-only",
                        action="store_true",
                        help="Mount the container's root filesystem as read only",
                    )

                    sp.add_argument(
                        "--restart",
                        metavar="string",
                        default="no",
                        help="Restart policy to apply when a container exits",
                    )

                    sp.add_argument(
                        "--rm",
                        action="store_true",
                        help="Automatically remove the container and its associated anonymous volumes when it exits",
                    )

                    sp.add_argument(
                        "--runtime",
                        metavar="string",
                        default="no",
                        help="Runtime to use for this container",
                    )

                    sp.add_argument(
                        "--security-opt",
                        metavar="list",
                        action="append",
                        help="Security Options",
                    )

                    sp.add_argument(
                        "--shm-size",
                        metavar="bytes",
                        help="Size of /dev/shm",
                    )

                    sp.add_argument(
                        "--sig-proxy",
                        action="store_true",
                        help="Proxy received signals to the process",
                    )

                    sp.add_argument(
                        "--stop-signal",
                        metavar="string",
                        help="Signal to stop the container",
                    )

                    sp.add_argument(
                        "--stop-timeout",
                        metavar="int",
                        type=int,
                        help="Timeout (in seconds) to stop a container",
                    )

                    sp.add_argument(
                        "--storage-opt",
                        metavar="list",
                        action="append",
                        help="Storage driver options for the container",
                    )

                    sp.add_argument(
                        "--sysctl",
                        metavar="map",
                        action="append",
                        help="Sysctl options",
                    )

                    sp.add_argument(
                        "--tmpfs",
                        metavar="list",
                        action="append",
                        help="Mount a tmpfs directory",
                    )

                    sp.add_argument(
                        "-t",
                        "--tty",
                        action="store_true",
                        help="Allocate a pseudo-TTY",
                    )

                    sp.add_argument(
                        "--ulimit",
                        metavar="ulimit",
                        action="append",
                        help="Ulimit options",
                    )

                    sp.add_argument(
                        "-u",
                        "--user",
                        metavar="string",
                        help="Username or UID (format: <name|uid>[:<group|gid>])",
                    )

                    sp.add_argument(
                        "--userns",
                        metavar="string",
                        help="User namespace to use",
                    )

                    sp.add_argument(
                        "--uts",
                        metavar="string",
                        help="UTS namespace to use",
                    )

                    sp.add_argument(
                        "-v",
                        "--volume",
                        metavar="list",
                        action="append",
                        help="Bind mount a volume",
                    )

                    sp.add_argument(
                        "--volume-driver",
                        metavar="string",
                        help="Optional volume driver for the container",
                    )

                    sp.add_argument(
                        "--volumes-from",
                        metavar="list",
                        action="append",
                        help="Mount volumes from the specified container(s)",
                    )

                    sp.add_argument(
                        "-w",
                        "--workdir",
                        metavar="string",
                        help="Working directory inside the container",
                    )

                    sp.add_argument(
                        "IMAGE",
                        help="Docker image tag",
                    )
                    sp.add_argument(
                        "CMDARGS",
                        nargs=argparse.REMAINDER,
                        help="Command line and args",
                    )
                else:
                    current_sp_grp.add_parser(
                        match[1],
                        help=match[2],
                    )

DEFAULT_DEBUG_HOST = "http://localhost:8000"

def subcommand_run(logger: "logging.Logger", docker_cmd: "str", args: "argparse.Namespace", unknown: "Sequence[str]") -> "int":
    # This shim cannot work without command-line args
    if len(args.CMDARGS) == 0:
        return 125

    logger.debug(f"args {args}")
    logger.debug(f"unk {unknown}")

    host = args.host[0] if isinstance(args.host, list) and len(args.host) else DEFAULT_DEBUG_HOST
    try:
        cli = tes.HTTPClient(host, timeout=5)
    except:
        return 125

    task_env: "Optional[MutableMapping[str, str]]" = None
    if isinstance(args.env, list) or isinstance(args.env_file, list):
        task_env = dict()
        env_files = []
        # Queuing files
        if isinstance(args.env_file, list):
            for env_file in args.env_file:
                eF = open(env_file, mode="r", encoding="utf-8")
                env_files.append(eF)
        
        if isinstance(args.env, list):
            env_files.append(io.StringIO("\n".join(args.env)))

        for eF in env_files:
            try:
                for env_line in eF:
                    if env_line.startswith("#"):
                        continue
                    # Remove the end of the line
                    env_line = env_line.rstrip("\n")
                    # Now, detect the equals
                    equal_pos = env_line.find("=")
                    if equal_pos == 0:
                        continue
                    elif equal_pos == -1:
                        task_env[env_line] = os.environ.get(env_line, "")
                    else:
                        task_env[env_line[0:equal_pos]] = env_line[equal_pos+1:]
            finally:
                eF.close()

    # Define task
    task = tes.Task(
        executors=[
            tes.Executor(
                image=args.IMAGE,
                command=args.CMDARGS,
                env=task_env,
            )
        ]
    )

    if args.interactive:
        logger.debug("--interactive cannot be honoured as there is no STDIN streaming communication in GA4GH TES")
    
    # Create and run task
    try:
        task_id = cli.create_task(task)
    except:
        return 126

    timeout = None
    w_task = cli.wait(task_id, timeout=timeout)

    logger.debug(w_task)

    task_info = cli.get_task(task_id, view="FULL" if args.tty else "BASIC")

    if isinstance(task_info.logs, list) and len(task_info.logs) > 0:
        task_log = task_info.logs[-1]
        if isinstance(task_log.logs, list) and len(task_log.logs) > 0:
            exec_log = task_log.logs[-1]
            
            retval = exec_log.exit_code
            if args.tty:
                if exec_log.stdout is not None:
                    sys.stdout.write(exec_log.stdout)
                if exec_log.stderr is not None:
                    sys.stderr.write(exec_log.stderr)
    else:
        retval = 126

    logger.debug(task_info)
    # j = json.loads(task_info.as_json())
    # print(j)

    if args.rm:
        logger.debug("--rm cannot be honoured, as there is no standard way to remove the task from the list of already completed tasks in GA4GH TES")

    return retval

SUBCOMMAND_ROUTER = {
    "run": subcommand_run,
}

LOG_MAPPING = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.FATAL,
}

def main(docker_cmd: "str" = DEFAULT_DOCKER_CMD, subcommand_router: "Mapping[str, SubcommandProc]" = SUBCOMMAND_ROUTER) -> "int":
    p = ArgumentParser(
        prog="docker",
        description="Docker GA4GH TES shim",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument(
        "--config",
        metavar="string",
        default=(pathlib.Path.home() / ".docker").as_posix(),
        help="Location of client config files",
    )
    p.add_argument(
        "-c",
        "--context",
        metavar="string",
        help="Name of the context to use to connect to the daemon (overrides DOCKER_HOST env var and default context set with \"docker context use\")",
    )
    p.add_argument(
        "-D",
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    p.add_argument(
        "-H",
        "--host",
        metavar="list",
        action="append",
        # default=["unix:///var/run/docker.sock"],
        help="Daemon socket to connect to",
    )
    p.add_argument(
        "-l",
        "--log-level",
        metavar="string",
        choices=["debug", "info", "warn", "error", "fatal"],
        default="info",
        help="Set the logging level",
    )
    p.add_argument(
        "--tls",
        action="store_true",
        help="Use TLS; implied by --tlsverify",
    )
    p.add_argument(
        "--tlscacert",
        metavar="string",
        default=(pathlib.Path.home() / ".docker" / "ca.pem").as_posix(),
        help="Trust certs signed only by this CA",
    )
    p.add_argument(
        "--tlscert",
        metavar="string",
        default=(pathlib.Path.home() / ".docker" / "cert.pem").as_posix(),
        help="Path to TLS certificate file",
    )
    p.add_argument(
        "--tlskey",
        metavar="string",
        default=(pathlib.Path.home() / ".docker" / "key.pem").as_posix(),
        help="Path to TLS key file",
    )
    p.add_argument(
        "--tlsverify",
        action="store_true",
        help="Use TLS and verify the remote",
    )
    p.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Print version information and quit",
    )

    inject_subparsers(p, docker_cmd=docker_cmd)

    args, unknown = p.parse_known_args()
    
    if args.version:
        return run_local_docker(docker_cmd, "-v")
    
    log_level_str = "info"
    if args.debug:
        log_level_str = "debug"
    elif args.log_level is not None:
        log_level_str = args.log_level

    log_level = LOG_MAPPING.get(log_level_str, logging.INFO)
    if log_level < logging.INFO:
            log_format = LOGGING_FORMAT
    else:
            log_format = DEBUG_LOGGING_FORMAT

    logging_config = {
        "level": log_level,
        "format": log_format,
    }
    logging.basicConfig(**logging_config)
    logger = logging.getLogger("docker-tes-proxy")

    if args.command is None:
        return run_local_docker(logger, docker_cmd, args, *unknown)
    elif args.command not in subcommand_router:
        return run_local_docker(logger, docker_cmd, args, args.command, *unknown)
    else:
        return subcommand_router[args.command](logger, docker_cmd, args, unknown)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())