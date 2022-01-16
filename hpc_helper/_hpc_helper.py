"""Helper functions for working with FAU's High Performance Cluster (HPC)."""
import re
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Optional, Sequence

from typing_extensions import Literal, get_args

from hpc_helper._types import path_t

TARGET_SYSTEM = Literal["woody", "tinygpu", "tinyfat", "emmy", "meggie"]


def check_interpreter(deploy_type: str):
    """Check whether the correct Python interpreter is selected for the specified deploy type.

    This function will raise an ``AttributeError`` if the Python interpreter that executed the script does not
    match the specified deploy type.

    Parameters
    ----------
    deploy_type : str
        specified deploy type. Currently supported types are:

        * "hpc" or "remote" to run code on the HPC. Here, it is assumed that the path to the Python executable contains
          the name of the cluster (i.e., "woody").
        * "local" or "develop" to run code locally.

    Raises
    ------
    AttributeError
        if the Python interpreter does not match ``deploy_type``

    """
    executable = sys.executable
    if deploy_type in ("hpc", "remote") and all(target not in executable for target in get_args(TARGET_SYSTEM)):
        raise AttributeError(f"'deploy_type' is '{deploy_type}', but '{deploy_type}' is not set as Python interpreter!")
    if deploy_type in ("local", "develop") and any(target in executable for target in get_args(TARGET_SYSTEM)):
        raise AttributeError(f"'deploy_type' is '{deploy_type}', but 'hpc' is set as Python interpreter!")

    print(f"Running on {sys.executable}")


def check_hpc_status_file(folder_path: path_t) -> bool:
    """Check whether a ``hpc_status`` file already exists and whether the job was already processed.

    Parameters
    ----------
    folder_path : :class:`~pathlib.Path` or str
        path to folder where ``hpc_status`` file should be.

    Returns
    -------
    bool
        ``True`` if the ``hpc_status`` file exists and contains the exit_status ``0``, i.e.,
        the job was successfully terminated.

    """
    folder_path = Path(folder_path)
    hpc_status_path = folder_path.joinpath("hpc_status")
    hpc_status_path.touch()
    exit_status = hpc_status_path.read_text(encoding="utf-8")
    if len(exit_status) > 0 and int(exit_status) == 0:
        return True

    return False


def write_hpc_status_file(folder_path: path_t, exit_status: int):
    """Write job exit status to ``hpc_status`` file.

    Parameters
    ----------
    folder_path : :class:`~pathlib.Path` or str
        path to folder where ``hpc_status`` file should be.
    exit_status : int
        exit status returned by the job submission

    """
    folder_path = Path(folder_path)
    hpc_status_path = folder_path.joinpath("hpc_status")
    hpc_status_path.write_text(str(exit_status), encoding="utf-8")


def cleanup_hpc_status_files(dir_list: Sequence[path_t]):
    """Clean up ``hpc_status`` files from directories after successful completion of all jobs.

    Parameters
    ----------
    dir_list : list of :class:`~pathlib.Path` or str
        list of directories where ``hpc_status`` files should be.

    """
    for dir_path in dir_list:
        hpc_status_path = Path(dir_path).joinpath("hpc_status")
        if hpc_status_path.exists():
            hpc_status_path.unlink()
    print("Done with cleanup!")


def get_running_jobs_torque(job_pattern: str, target_system: Optional[TARGET_SYSTEM] = "woody") -> Sequence[str]:
    """Return a list of all currently running jobs in the Torque scheduler on the HPC.

    Parameters
    ----------
    job_pattern : str
        regex pattern of job names. regex string **must** contain a capture group.
    target_system : one of {"woody", "tinygpu", "tinyfat", "emmy", "meggie"}
        name of target system/cluster

    Returns
    -------
    list of str
        list of job names that are currently running

    """
    qstat = _check_command_for_target_system("qstat", target_system)
    out = subprocess.check_output(qstat).decode("utf-8")
    return re.findall(rf"\S* {job_pattern}\s*\w+\s*\S*\s*R", out)


def get_running_jobs_slurm(job_pattern: str):
    """Return a list of all currently running jobs in the Slurm scheduler on the HPC.

    Parameters
    ----------
    job_pattern : str
        regex pattern of job names. regex string **must** contain a capture group.

    Returns
    -------
    list of str
        list of job names that are currently running

    """
    out = subprocess.check_output("squeue").decode("utf-8")
    return re.findall(rf"\d+\s*\w+\s*{job_pattern}\s*\w+\s*R\S*", out)


def build_job_submit_torque(
    job_name: str,
    script_name: str,
    target_system: Optional[TARGET_SYSTEM] = "woody",
    nodes: Optional[int] = 1,
    ppn: Optional[int] = 4,
    walltime: Optional[str] = "24:00:00",
    args: Optional[Sequence[str]] = None,
    **kwargs,
) -> str:
    """Build job submission command for Torque.

    Parameters
    ----------
    job_name : str
        job name
    script_name : str
        name of script to submit
    target_system : one of {"woody", "tinygpu", "tinyfat", "emmy", "meggie"}
        name of target system/cluster
    nodes : int
        number of nodes requested.
        Default: 1
    ppn : int
        number of requested processors per node.
        Default: 4 (for woody)
    walltime : str
        required wall clock time (runtime) in the format ``HH:MM:SS``.
        Default: "24:00:00" (24 hours)
    args : list of str
        list of unnamed arguments that will be passed to the job submission script as ``$PARAMS`` environment variable.
        In the job submission script the arguments can be parsed by calling ``eval set "$PARAMS"``
    kwargs :
        additional arguments that are passed to the job submission script.
        This can, for instance, be a path to the data folder etc.

    Returns
    -------
    str
        command to submit the specified job via Torque. The command can be executed by passing it to
        :func:`subprocess.call`.

    """
    if target_system == "tinygpu":
        warnings.warn(
            f"Using torque for '{target_system}' is deprecated. "
            f"Please consider migrating your submission scripts to slurm!",
            category=DeprecationWarning,
        )
    qsub = _check_command_for_target_system("qsub", target_system)
    qsub_command = f"{qsub} -N {job_name} -l nodes={nodes}:ppn={ppn},walltime={walltime} -m abe "

    qsub_command = _add_arguments_torque(qsub_command, args, **kwargs)

    qsub_command += f" {script_name}"
    return qsub_command


def _check_partition_slurm(partition: str, gres: str):
    if partition in ("v100", "a100"):
        assert partition in gres


def build_job_submit_slurm(
    job_name: str,
    script_name: str,
    target_system: Optional[TARGET_SYSTEM] = "woody",
    nodes: Optional[int] = 1,
    tasks_per_node: Optional[int] = 4,
    gres: Optional[str] = "gpu:1",
    partition: Optional[str] = None,
    walltime: Optional[str] = "24:00:00",
    mail_type: Optional[Literal["BEGIN", "END", "FAIL", "ALL"]] = "ALL",
    args: Optional[Sequence[str]] = None,
    **kwargs,
) -> str:
    """Build job submission command for Slurm.

    Parameters
    ----------
    job_name : str
        job name
    script_name : str
        name of script to submit
    target_system : one of {"woody", "tinygpu", "tinyfat", "emmy", "meggie"}
        name of target system/cluster
    nodes : int
        number of nodes requested.
        Default: 1
    tasks_per_node : int
        number of tasks per node.
        Default: 4 (for woody)
    gres : str, optional
        configuration of requested GPUs (for tinygpu)
        Default: "gpu:1" (for tinygpu)
    partition : str, optional
        partition for tinygpu when specific nodes (e.g., A100 or V100) are requested.
    walltime : str, optional
        required wall clock time (runtime) in the format ``HH:MM:SS``.
        Default: "24:00:00" (24 hours)
    mail_type : one of {"BEGIN", "END", "FAIL", "ALL"}, optional
        type of mails to receive. Default: "ALL"
    args : list of str, optional
        list of unnamed arguments that will be passed to the job submission script as ``$PARAMS`` environment variable.
        In the job submission script the arguments can be parsed by calling ``eval set "$PARAMS"``
    kwargs :
        additional named arguments that are passed to the job submission script as environment variables.
        This can, for instance, be a path to the data folder, etc.

    Returns
    -------
    str
        command to submit the specified job via Slurm. The command can be executed by passing it to
        :func:`subprocess.call`.

    """
    sbatch = _check_command_for_target_system("sbatch", target_system=target_system)
    sbatch_command = f"{sbatch} --job-name {job_name} "
    if target_system != "tinygpu":
        sbatch_command += f"--nodes={nodes} --ntasks-per-node={tasks_per_node} "
    if target_system == "tinygpu":
        if partition is not None:
            _check_partition_slurm(partition, gres)
            sbatch_command += f"--partition={partition} "
        sbatch_command += f"--gres={gres} "
    sbatch_command += f"--time={walltime} --mail-type={mail_type} "

    sbatch_command = _add_arguments_slurm(sbatch_command, args, **kwargs)
    sbatch_command += f" {script_name}"

    return sbatch_command


def _check_command_for_target_system(command: str, target_system: TARGET_SYSTEM) -> str:
    if command.startswith("q"):
        if target_system in ["meggie", "tinyfat"]:
            raise AttributeError(
                f"'torque' not supported for target system '{target_system}'! "
                f"Please migrate your submission scripts to slurm!"
            )
    if command.startswith("s"):
        if target_system in ["woody"]:
            raise AttributeError(
                f"'slurm' not supported for target system '{target_system}'! "
                f"Please migrate your submission scripts to torque!"
            )
    if target_system == "tinygpu":
        command += ".tinygpu"

    return command


def _add_arguments_torque(command_str: str, args: Optional[Sequence[str]] = None, **kwargs) -> str:
    if len(kwargs) != 0 or args is not None:
        command_str += "-v "
        if args is not None:
            command_str += 'PARAMS="'
            for arg in args:
                command_str += f"{arg} "
            command_str = command_str.strip()
            command_str += '" '
        if len(kwargs) != 0:
            for key, value in kwargs.items():
                command_str += f"{key}={value},"
            # remove the last comma
            command_str = command_str[:-1]

    return command_str.strip()


def _add_arguments_slurm(command_str: str, args: Optional[Sequence[str]] = None, **kwargs) -> str:
    if len(kwargs) != 0 or args is not None:
        command_str += "--export="
        if args is not None:
            command_str += 'PARAMS="'
            for arg in args:
                command_str += f"{arg} "
            command_str = command_str.strip() + '"'
            if len(kwargs) != 0:
                command_str += ","
        if len(kwargs) != 0:
            for key, value in kwargs.items():
                command_str += f'{key}="{value}",'
            # remove the last comma and add the quote again
            command_str = command_str[:-2] + '"'

    return command_str.strip()


if __name__ == "__main__":
    print(build_job_submit_slurm("VP_01", "jobscript.sh", "tinygpu", BASE_PATH="hello", SUBJECT_ID="VP_01"))
