import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

from hpc_helper import (
    build_job_submit_slurm,
    check_hpc_status_file,
    check_interpreter,
    cleanup_hpc_status_files,
    write_hpc_status_file,
)

TEST_FILE_PATH = Path(__file__).parent


@contextmanager
def does_not_raise():
    yield


class TestHpcHelper:
    @pytest.mark.parametrize(
        "deploy_type, expected",
        [
            ("hpc", pytest.raises(AttributeError)),
            ("remote", pytest.raises(AttributeError)),
            ("local", does_not_raise()),
            ("develop", does_not_raise()),
        ],
    )
    def test_check_interpreter_local_raises(self, deploy_type, expected):
        with expected:
            check_interpreter(deploy_type)

    @pytest.mark.parametrize(
        "deploy_type, expected",
        [
            ("hpc", does_not_raise()),
            ("remote", does_not_raise()),
            ("local", pytest.raises(AttributeError)),
            ("develop", pytest.raises(AttributeError)),
        ],
    )
    def test_check_interpreter_remote_raises(self, deploy_type, expected):
        with mock.patch.object(sys, "executable", "/home/woody/iwso/"):
            with expected:
                check_interpreter(deploy_type)

    def test_check_hpc_status_file_does_not_exist(self, tmp_path):
        assert check_hpc_status_file(tmp_path) is False

    def test_check_hpc_status_file_exists(self, tmp_path):
        tmp_path.joinpath("hpc_status").touch()
        assert check_hpc_status_file(tmp_path) is False

    @pytest.mark.parametrize(
        "exit_status, expected",
        [
            (0, True),
            (1, False),
        ],
    )
    def test_check_hpc_status_file_exists_and_has_exit_code(self, tmp_path, exit_status, expected):
        status_file = tmp_path.joinpath("hpc_status")
        status_file.touch()
        status_file.write_text(str(exit_status))

        assert check_hpc_status_file(tmp_path) is expected

    @pytest.mark.parametrize(
        "exit_status, expected",
        [
            (0, True),
            (1, False),
        ],
    )
    def test_write_hpc_status(self, tmp_path, exit_status, expected):
        write_hpc_status_file(tmp_path, exit_status)
        assert check_hpc_status_file(tmp_path) is expected

    def test_cleanup_hpc_status_files(self, tmp_path):
        write_hpc_status_file(tmp_path, 0)
        cleanup_hpc_status_files([tmp_path])
        assert tmp_path.joinpath("hpc_status").exists() is False

    # @pytest.mark.parametrize(
    #     "target_system, expected",
    #     [
    #         ("woody", does_not_raise()),
    #         ("tinygpu", pytest.warns(DeprecationWarning)),
    #         ("tinyfat", pytest.raises(AttributeError)),
    #     ],
    # )
    # def test_build_job_submit_torque_raises(self, target_system, expected):
    #     with expected:
    #         build_job_submit_torque(job_name="Test_Job", script_name="jobscript.sh", target_system=target_system)

    # @pytest.mark.parametrize(
    #     "target_system, args, kwargs, expected",
    #     [
    #         ("woody", None, {}, "qsub -N Test_Job -l nodes=1:ppn=4,walltime=24:00:00 -m abe jobscript.sh"),
    #         (
    #             "woody",
    #             ["path1", "path2"],
    #             {},
    #             'qsub -N Test_Job -l nodes=1:ppn=4,walltime=24:00:00 -m abe -v PARAMS="path1 path2" jobscript.sh',
    #         ),
    #         (
    #             "woody",
    #             ["path1", "path2"],
    #             {"SUBJECT_DIR": "path3"},
    #             "qsub -N Test_Job -l nodes=1:ppn=4,walltime=24:00:00 -m abe "
    #             '-v PARAMS="path1 path2" SUBJECT_DIR=path3 jobscript.sh',
    #         ),
    #         (
    #             "woody",
    #             ["path1", ""],
    #             {"SUBJECT_DIR": "path3"},
    #             "qsub -N Test_Job -l nodes=1:ppn=4,walltime=24:00:00 -m abe "
    #             '-v PARAMS="path1" SUBJECT_DIR=path3 jobscript.sh',
    #         ),
    #         (
    #             "woody",
    #             None,
    #             {"SUBJECT_DIR": "path3"},
    #             "qsub -N Test_Job -l nodes=1:ppn=4,walltime=24:00:00 -m abe -v SUBJECT_DIR=path3 jobscript.sh",
    #         ),
    #         (
    #             "woody",
    #             None,
    #             {"SUBJECT_DIR": "path3", "TEST_PATH": "path4"},
    #             "qsub -N Test_Job -l nodes=1:ppn=4,walltime=24:00:00 -m abe "
    #             "-v SUBJECT_DIR=path3,TEST_PATH=path4 jobscript.sh",
    #         ),
    #         ("tinygpu", None, {}, "qsub.tinygpu -N Test_Job -l nodes=1:ppn=4,walltime=24:00:00 -m abe jobscript.sh"),
    #     ],
    # )
    # def test_build_job_submit_torque(self, target_system, args, kwargs, expected):
    #     out = build_job_submit_torque(
    #         job_name="Test_Job", script_name="jobscript.sh", target_system=target_system, args=args, **kwargs
    #     )
    #     assert out == expected

    @pytest.mark.parametrize(
        "target_system, expected",
        [
            ("woody", does_not_raise()),
            ("tinygpu", does_not_raise()),
            ("tinyfat", does_not_raise()),
        ],
    )
    def test_build_job_submit_slurm_raises(self, target_system, expected):
        with expected:
            build_job_submit_slurm(job_name="Test_Job", script_name="jobscript.sh", target_system=target_system)

    @pytest.mark.parametrize(
        "target_system, partition, gres, args, kwargs, expected",
        [
            (
                "tinygpu",
                None,
                "gpu:1",
                None,
                {},
                "sbatch.tinygpu --job-name Test_Job --gres=gpu:1 --time=24:00:00 --mail-type=ALL jobscript.sh",
            ),
            (
                "tinygpu",
                None,
                None,
                ["path1", "path2"],
                {},
                "sbatch.tinygpu --job-name Test_Job --gres=gpu:1 "
                '--time=24:00:00 --mail-type=ALL --export=PARAMS="path1 path2" jobscript.sh',
            ),
            (
                "tinygpu",
                None,
                None,
                ["path1", ""],
                {"SUBJECT_DIR": "path3"},
                "sbatch.tinygpu --job-name Test_Job --gres=gpu:1 "
                '--time=24:00:00 --mail-type=ALL --export=PARAMS="path1",SUBJECT_DIR="path3" jobscript.sh',
            ),
            (
                "tinygpu",
                None,
                "gpu:rtx3080:4",
                None,
                {"SUBJECT_DIR": "path3"},
                "sbatch.tinygpu --job-name Test_Job --gres=gpu:rtx3080:4 "
                '--time=24:00:00 --mail-type=ALL --export=SUBJECT_DIR="path3" jobscript.sh',
            ),
            (
                "tinygpu",
                "a100",
                "gpu:a100:1",
                None,
                {},
                "sbatch.tinygpu --job-name Test_Job --partition=a100 --gres=gpu:a100:1 "
                "--time=24:00:00 --mail-type=ALL jobscript.sh",
            ),
            (
                "tinygpu",
                "v100",
                "gpu:v100:4",
                None,
                {},
                "sbatch.tinygpu --job-name Test_Job --partition=v100 --gres=gpu:v100:4 "
                "--time=24:00:00 --mail-type=ALL jobscript.sh",
            ),
        ],
    )
    def test_build_job_submit_tinygpu(self, target_system, partition, gres, args, kwargs, expected):
        out = build_job_submit_slurm(
            job_name="Test_Job",
            script_name="jobscript.sh",
            target_system=target_system,
            partition=partition,
            gres=gres,
            args=args,
            **kwargs,
        )

        assert out == expected

    @pytest.mark.parametrize(
        "target_system, partition, args, kwargs, expected",
        [
            (
                "tinyfat",
                None,
                None,
                {"SUBJECT_DIR": "path3"},
                "sbatch.tinyfat --job-name Test_Job --nodes=1 --ntasks-per-node=64 "
                '--time=24:00:00 --mail-type=ALL --export=SUBJECT_DIR="path3" jobscript.sh',
            ),
            (
                "tinyfat",
                "broadwell256",
                None,
                {"SUBJECT_DIR": "path3"},
                "sbatch.tinyfat --job-name Test_Job --nodes=1 --ntasks-per-node=64 -p broadwell256 "
                '--time=24:00:00 --mail-type=ALL --export=SUBJECT_DIR="path3" jobscript.sh',
            ),
        ],
    )
    def test_build_job_submit_tinyfat(self, target_system, partition, args, kwargs, expected):
        out = build_job_submit_slurm(
            job_name="Test_Job",
            script_name="jobscript.sh",
            target_system=target_system,
            partition=partition,
            nodes=1,
            tasks_per_node=64,
            args=args,
            **kwargs,
        )

        assert out == expected
