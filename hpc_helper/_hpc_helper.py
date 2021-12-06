"""Helper functions for working with FAU's High Performance Cluster (HPC)."""
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

from hpc_helper._types import path_t


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
    if (deploy_type == "hpc" or deploy_type == "remote") and "woody" not in executable:
        raise AttributeError(f"'deploy_type' is '{deploy_type}', but '{deploy_type}' is not set as Python interpreter!")
    if (deploy_type == "local" or deploy_type == "develop") and "woody" in executable:
        raise AttributeError(f"'deploy_type' is '{deploy_type}', but 'hpc' is set as Python interpreter!")

    print(f"Running on {sys.executable}...")


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


def get_running_jobs_torque(job_pattern: str) -> Sequence[str]:
    """Return a list of all currently running jobs in the Torque scheduler on the HPC.

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
    out = subprocess.check_output("qstat").decode("utf-8")
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


def build_job_submit_slurm(
    job_name: str,
    script_name: str,
    nodes: Optional[int] = 1,
    tasks_per_node: Optional[int] = 4,
    walltime: Optional[str] = "24:00:00",
    **kwargs,
) -> str:
    """Build job submission command for Slurm.

    Parameters
    ----------
    job_name : str
        job name
    script_name : str
        name of script to submit
    nodes : int
        number of nodes requested.
        Default: 1
    tasks_per_node : int
        number of tasks per node.
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
        command to submit the specified job via Slurm. The command can be executed by passing it to
        :func:`subprocess.call`.

    """
    # job_name: subject_id
    sbatch_command = (
        f"sbatch --job-name {job_name} --nodes={nodes} --ntasks-per-node={tasks_per_node} --time={walltime} "
    )

    if kwargs is not None:
        sbatch_command += "-v "
        for key, value in kwargs.items():
            sbatch_command += f"{key}={value} "

    sbatch_command += f"{script_name}"
    return sbatch_command


def build_job_submit_torque(
    job_name: str,
    script_name: str,
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
    # job_name: subject_id
    qsub_command = f"qsub --N {job_name} --l nodes={nodes}:ppn={ppn},walltime={walltime} "

    if len(kwargs) != 0:
        qsub_command += "-v "
        for key, value in kwargs.items():
            qsub_command += f"{key}={value} "

    qsub_command += f"{script_name}"
    return qsub_command


if __name__ == "__main__":
    build_job_submit_torque("VP_03", "jobscript.sh")
