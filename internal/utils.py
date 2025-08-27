import subprocess

def make_file_extension(ext: str):
    """Make sure the file extension starts with a dot."""
    if not ext.startswith('.'):
        ext = '.' + ext
    return ext

def is_apport_active():
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "apport.service"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout.strip() == "active"
    except FileNotFoundError:
        return False  # systemctl not available

