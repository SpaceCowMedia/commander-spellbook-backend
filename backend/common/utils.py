import subprocess


def check_pypy():
    result = subprocess.run(['pypy', '--version'], stdout=subprocess.PIPE)
    if result.returncode != 0:
        return False
    return result.stdout.decode().startswith('Python 3.')


PYPY_AVAILABLE = check_pypy()
