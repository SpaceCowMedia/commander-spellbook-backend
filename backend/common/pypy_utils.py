import subprocess


def check_pypy():
    try:
        result = subprocess.run(['pypy', '--version'], stdout=subprocess.PIPE)
        if result.returncode != 0:
            return False
        return result.stdout.decode().startswith('Python 3.')
    except FileNotFoundError:
        return False


PYPY_AVAILABLE = check_pypy()
