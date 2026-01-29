import os
import subprocess
import sys
import time
import click
from tqdm import tqdm

def run_adb(command):
    """Run an ADB command and return the output."""
    try:
        result = subprocess.run(
            ["adb"] + command,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        click.secho(f"Error running ADB command: {e}", fg="red")
        if e.stderr:
            click.secho(f"Details: {e.stderr.strip()}", fg="yellow")
        return None
    except FileNotFoundError:
        click.secho("ADB not found. Please install platform-tools (brew install --cask android-platform-tools).", fg="red")
        sys.exit(1)

def get_devices():
    """Get a list of connected ADB devices."""
    output = run_adb(["devices"])
    if not output:
        return []
    
    devices = []
    for line in output.split("\n")[1:]:
        if line.strip():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
    return devices

def get_remote_file_size(device, path):
    """Get the size of a remote file or directory on the Android device."""
    # Use 'du' command on Android to get size in bytes
    output = run_adb(["-s", device, "shell", f"du -sb \"{path}\""])
    if output:
        try:
            # du output is usually "size path"
            size_str = output.split()[0]
            return int(size_str)
        except (ValueError, IndexError):
            return 0
    return 0

@click.command()
@click.argument('src', type=str, default="/sdcard/Music/Adhimathra")
@click.argument('dest', type=click.Path(), default=".")
@click.option('--device', '-s', help='Target device ID')
def main(src, dest, device):
    """MacDrop: Copy files from Pixel (Android) phone to Mac via ADB (Pull)."""
    
    # 1. Check for devices
    devices = get_devices()
    if not devices:
        click.secho("No devices connected via ADB. Please check your USB connection and enable USB debugging.", fg="red")
        return

    if not device:
        if len(devices) > 1:
            click.echo("Multiple devices found. Please specify one with -s:")
            for d in devices:
                click.echo(f"  - {d}")
            return
        device = devices[0]
    elif device not in devices:
        click.secho(f"Device {device} not found.", fg="red")
        return

    click.echo(f"Connected to: {click.style(device, fg='green', bold=True)}")

    # 2. Prepare transfer
    total_size = get_remote_file_size(device, src)
    src_name = os.path.basename(src.rstrip('/'))
    
    click.echo(f"Preparing to download: {click.style(src_name, fg='cyan')} ({total_size / (1024*1024):.2f} MB)")
    
    # 3. Execute pull
    cmd = ["adb", "-s", device, "pull", src, dest]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    with tqdm(total=total_size, unit='B', unit_scale=True, desc=f"Pulling {src_name}") as pbar:
        while process.poll() is None:
            # Since we can't easily track progress of a single 'adb pull' stream,
            # we just wait for it to finish. 
            # (A more advanced version would monitor local file size growth if dest is a file)
            time.sleep(0.5)
            pbar.update(0)

        # Final check
        if process.returncode == 0:
            pbar.update(total_size)
            click.echo("\n" + click.style("✓ Successfully downloaded!", fg="green", bold=True))
        else:
            _, stderr = process.communicate()
            click.secho(f"\n✗ Failed to download: {stderr.strip()}", fg="red")

if __name__ == "__main__":
    main()
