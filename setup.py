"""Build the Linux Wayland transport; Windows continues to use ctypes/Win32."""
from pathlib import Path
import shlex
import subprocess
import sys
import sysconfig

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext


class WaylandBuild(build_ext):
    def build_extensions(self):
        generated = Path(self.build_temp) / "protocols"
        generated.mkdir(parents=True, exist_ok=True)
        for xml in sorted(Path("native/linux/protocols").glob("*.xml")):
            for mode, suffix in (("client-header", ".h"), ("private-code", ".c")):
                subprocess.run(["wayland-scanner", mode, str(xml), str(generated / (xml.stem + suffix))], check=True)
        flags = shlex.split(subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "wayland-client", "xkbcommon"], text=True))
        for extension in self.extensions:
            extension.sources += [str(p) for p in sorted(generated.glob("*.c"))]
            extension.include_dirs.append(str(generated))
            extension.extra_compile_args += [f for f in flags if not f.startswith("-l")]
            extension.extra_link_args += [f for f in flags if f.startswith("-l")]
        super().build_extensions()


setup(
    ext_modules=[Extension("torchbridge._wayland", ["native/linux/wayland.c"],
                           extra_compile_args=["-std=c11", "-Wall", "-Wextra", "-Werror"])]
    if sys.platform.startswith("linux") else [],
    cmdclass={"build_ext": WaylandBuild},
    # A Windows wheel has no compiled extension, but must not be advertised as
    # usable on Linux: the latter requires its own compiled Wayland transport.
    options={"bdist_wheel": {"plat_name": sysconfig.get_platform().replace("-", "_").replace(".", "_")}}
    if sys.platform == "win32" else {},
    data_files=[("share/torchbridge/" + str(path.parent), [str(path)])
                for path in sorted(Path("assets").rglob("*"))
                if path.is_file() and path.suffix.lower() in {".png", ".cur", ".svg"}
                and "native" not in path.parts]
    + ([("share/torchbridge/licenses", ["native/linux/THIRD_PARTY_NOTICES.txt"])]
       if sys.platform.startswith("linux") else [])
    + [("share/torchbridge/assets/native/x86", [str(path)])
       for path in sorted(Path("assets/native/x86").glob("*.dll"))]
    + [("share/torchbridge/licenses/minhook", ["native/input/vendor/minhook/LICENSE.txt"])],
)
