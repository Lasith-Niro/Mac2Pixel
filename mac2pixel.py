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

def get_file_size(path):
    """Get the size of a file or directory."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    elif os.path.isdir(path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size
    return 0

@click.command()
@click.argument('src', type=click.Path(exists=True))
@click.argument('dest', type=str, default="/sdcard/Music/Adhimathra")
@click.option('--device', '-s', help='Target device ID')
def main(src, dest, device):
    """Copy files from Mac to Pixel (Android) phone via ADB."""
    
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
    total_size = get_file_size(src)
    src_name = os.path.basename(src)
    
    click.echo(f"Preparing to copy: {click.style(src_name, fg='cyan')} ({total_size / (1024*1024):.2f} MB)")
    
    # ADB push doesn't provide easy progress info via stdout without parsing complex stuff.
    # We'll use a wrapper that monitors the destination file size growth (roughly).
    # Note: For simplicity and reliability, we start the adb push in background and track progress.
    
    cmd = ["adb", "-s", device, "push", src, dest]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    with tqdm(total=total_size, unit='B', unit_scale=True, desc=f"Pushing {src_name}") as pbar:
        # Simple polling approach for progress
        # This is an approximation since ADB push output is not easily streamable for progress
        # A better way would be to parse adb push output if it supports progress (it doesn't easily)
        # So we just wait and update based on completion or time if we want to be fancy.
        # BUT: ADB actually doesn't have a progress flag that's easy to use here.
        
        while process.poll() is None:
            # We can't easily get fine-grained progress from 'adb push' without 
            # monitoring the filesystem on the device, which is slow.
            # So we'll just wait for it to finish and then finish the bar.
            time.sleep(0.5)
            # Update bar a bit to show activity
            pbar.update(0)

        # Final check
        if process.returncode == 0:
            pbar.update(total_size)
            click.echo("\n" + click.style("✓ Successfully copied!", fg="green", bold=True))
        else:
            _, stderr = process.communicate()
            click.secho(f"\n✗ Failed to copy: {stderr.strip()}", fg="red")

if __name__ == "__main__":
    main()
