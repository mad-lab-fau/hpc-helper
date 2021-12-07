"""Helper functions for working with FAU's High Performance Cluster (HPC)."""
import re
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Optional, Sequence

from typing_extensions import Literal

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
    if deploy_type in ("hpc", "remote") and "woody" not in executable:
        raise AttributeError(f"'deploy_type' is '{deploy_type}', but '{deploy_type}' is not set as Python interpreter!")
    if deploy_type in ("local", "develop") and "woody" in executable:
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
        ``True`` if the ``hpc_status`` file exists and contains the status code ``0``, i.e.,
        the job was successfully terminated.

    """
    folder_path = Path(folder_path)
    touch_command = f"cd {str(folder_path)} && touch hpc_status"
    subprocess.call(touch_command, shell=True)
    with open(Path(f"{folder_path}/hpc_status"), "w+", encoding="utf-8") as f:
        status = f.read()
        if len(status) > 0 and int(status) == 0:
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
    out_command = f"cd {str(folder_path)} && echo {exit_status} > hpc_status"
    subprocess.call(out_command, shell=True)


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
    # job_pattern = (VP_\w+)
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
    # job_pattern = (VP_\w+)
    # out = subprocess.check_output("squeue").decode("utf-8")
    # return re.findall(rf"\S* {job_pattern}\s*\w+\s*\S*\s*R", out)
    raise NotImplementedError("Not implemented yet!")


def build_job_submit_torque(
    job_name: str,
    script_name: str,
    target_system: Optional[TARGET_SYSTEM] = "woody",
    nodes: Optional[int] = 1,
    ppn: Optional[int] = 4,
    walltime: Optional[str] = "24:00:00",
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
    qsub_command = f"{qsub} -N {job_name} -m abe -l nodes={nodes}:ppn={ppn},walltime={walltime} "

    if len(kwargs) != 0:
        qsub_command += "-v "
        for key, value in kwargs.items():
            qsub_command += f"{key}={value} "

    qsub_command += f"{script_name}"
    return qsub_command


def build_job_submit_slurm(
    job_name: str,
    script_name: str,
    target_system: Optional[TARGET_SYSTEM] = "woody",
    nodes: Optional[int] = 1,
    tasks_per_node: Optional[int] = 4,
    walltime: Optional[str] = "24:00:00",
    mail_type: Optional[Literal["BEGIN", "END", "FAIL", "ALL"]] = "ALL",
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
    walltime : str
        required wall clock time (runtime) in the format ``HH:MM:SS``.
        Default: "24:00:00" (24 hours)
    mail_type : one of {"BEGIN", "END", "FAIL", "ALL"}
        type of mails to receive
    kwargs :
        additional arguments that are passed to the job submission script.
        This can, for instance, be a path to the data folder etc.

    Returns
    -------
    str
        command to submit the specified job via Slurm. The command can be executed by passing it to
        :func:`subprocess.call`.

    """
    sbatch = _check_command_for_target_system("sbatch", target_system=target_system)
    sbatch_command = (
        f"{sbatch} --job-name {job_name} --nodes={nodes} --ntasks-per-node={tasks_per_node} "
        f"--time={walltime} --mail-type={mail_type} "
    )

    if kwargs is not None:
        sbatch_command += "-v "
        for key, value in kwargs.items():
            sbatch_command += f"{key}={value} "

    sbatch_command += f"{script_name}"
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
    if target_system is "tinygpu":
        command += ".tinygpu"

    return command
