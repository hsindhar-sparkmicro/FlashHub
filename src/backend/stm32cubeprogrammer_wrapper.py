import logging
import os
import shutil
import subprocess


class STM32CubeProgrammerWrapper:
    DEFAULT_BIN_ADDRESS = "0x08000000"
    EXECUTABLE_CANDIDATES = [
        "STM32_Programmer_CLI",
        "STM32_Programmer_CLI.exe",
        "STM32CubeProgrammerCLI",
    ]

    @classmethod
    def resolve_executable(cls, cli_path=""):
        candidates = []
        if cli_path:
            candidates.append(cli_path)
        candidates.extend(cls.EXECUTABLE_CANDIDATES)

        for candidate in candidates:
            if not candidate:
                continue

            if os.path.isabs(candidate) or os.path.sep in candidate:
                if os.path.isfile(candidate):
                    return candidate
            else:
                resolved = shutil.which(candidate)
                if resolved:
                    return resolved

        raise FileNotFoundError(
            "STM32CubeProgrammer CLI executable not found. Configure the CLI path from tool settings."
        )

    @classmethod
    def _build_connect_args(cls, probe_id):
        return ["-c", "port=SWD", f"sn={probe_id}", "mode=UR", "reset=HWrst"]

    @classmethod
    def flash_firmware(cls, probe_id, target_device, file_path, cli_path="", progress_callback=None):
        del target_device

        executable = cls.resolve_executable(cli_path)
        file_ext = os.path.splitext(file_path)[1].lower()

        cmd = [executable, *cls._build_connect_args(probe_id), "-d", file_path]
        if file_ext == ".bin":
            cmd.append(cls.DEFAULT_BIN_ADDRESS)
        cmd.extend(["-v", "-rst"])

        if progress_callback:
            progress_callback(10)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
            logging.error("STM32CubeProgrammer flash failed: %s", output.strip())
            raise Exception(output.strip() or "STM32CubeProgrammer CLI flash failed.")

        if progress_callback:
            progress_callback(100)

    @classmethod
    def reset_target(cls, probe_id, target_device, cli_path=""):
        del target_device

        executable = cls.resolve_executable(cli_path)
        cmd = [executable, *cls._build_connect_args(probe_id), "-rst"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
            logging.error("STM32CubeProgrammer reset failed: %s", output.strip())
            raise Exception(output.strip() or "STM32CubeProgrammer CLI reset failed.")
