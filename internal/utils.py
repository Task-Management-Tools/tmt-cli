import subprocess

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

