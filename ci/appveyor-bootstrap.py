"""
AppVeyor will at least have few Pythons around so there's no point of implementing a bootstrapper in PowerShell.

This is a port of https://github.com/pypa/python-packaging-user-guide/blob/master/source/code/install.ps1
with various fixes and improvements that just weren't feasible to implement in PowerShell.
"""
from __future__ import print_function
from os import environ
from os.path import exists
from subprocess import check_call

try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve

BASE_URL = "https://www.python.org/ftp/python/"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
GET_PIP_PATH = "C:\get-pip.py"
URLS = {
    ("3.7", "64"): BASE_URL + "3.7.9/python-3.7.9-amd64.exe",
    ("3.7", "32"): BASE_URL + "3.7.9/python-3.7.9.exe",
    ("3.8", "64"): BASE_URL + "3.8.6/python-3.8.6-amd64.exe",
    ("3.8", "32"): BASE_URL + "3.8.6/python-3.8.6.exe",
    ("3.9", "64"): BASE_URL + "3.9.0/python-3.9.0-amd64.exe",
    ("3.9", "32"): BASE_URL + "3.9.0/python-3.9.0.exe",
}
INSTALL_CMD = {
    # Commands are allowed to fail only if they are not the last command.  Eg: uninstall (/x) allowed to fail.
    "3.7": [["{path}", "/quiet", "TargetDir={home}"]],
    "3.8": [["{path}", "/quiet", "TargetDir={home}"]],
    "3.9": [["{path}", "/quiet", "TargetDir={home}"]],
}


def download_file(url, path):
    print("Downloading: {} (into {})".format(url, path))
    progress = [0, 0]

    def report(count, size, total):
        progress[0] = count * size
        if progress[0] - progress[1] > 1000000:
            progress[1] = progress[0]
            print("Downloaded {:,}/{:,} ...".format(progress[1], total))

    dest, _ = urlretrieve(url, path, reporthook=report)
    return dest


def install_python(version, arch, home):
    print("Installing Python", version, "for", arch, "bit architecture to", home)
    if exists(home):
        return

    path = download_python(version, arch)
    print("Installing", path, "to", home)
    success = False
    for cmd in INSTALL_CMD[version]:
        cmd = [part.format(home=home, path=path) for part in cmd]
        print("Running:", " ".join(cmd))
        try:
            check_call(cmd)
        except Exception as exc:
            print("Failed command", cmd, "with:", exc)
            if exists("install.log"):
                with open("install.log") as fh:
                    print(fh.read())
        else:
            success = True
    if success:
        print("Installation complete!")
    else:
        print("Installation failed")


def download_python(version, arch):
    for _ in range(3):
        try:
            return download_file(URLS[version, arch], "installer.exe")
        except Exception as exc:
            print("Failed to download:", exc)
        print("Retrying ...")


def install_pip(home):
    pip_path = home + "/Scripts/pip.exe"
    python_path = home + "/python.exe"
    if exists(pip_path):
        print("Ensuring pip is up to date...")
        check_call([python_path, "-m", "pip", "install", "--upgrade", "pip"])
    else:
        print("Installing pip...")
        download_file(GET_PIP_URL, GET_PIP_PATH)
        print("Executing:", python_path, GET_PIP_PATH)
        check_call([python_path, GET_PIP_PATH])


def install_packages(home, *packages):
    cmd = [home + "/Scripts/pip.exe", "install"]
    cmd.extend(packages)
    check_call(cmd)


if __name__ == "__main__":
    install_python(environ['PYTHON_VERSION'], environ['PYTHON_ARCH'], environ['PYTHON_HOME'])
    install_pip(environ['PYTHON_HOME'])
    install_packages(environ['PYTHON_HOME'], "setuptools>=18.0.1", "wheel", "tox", "virtualenv>=13.1.0")
