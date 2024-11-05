import requests, zipfile, os, shutil, argparse
from io import BytesIO

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

IUFI_URL = "https://github.com/ChocoMeow/IUFI/archive/"
IGNORE_FILES = ["images", "frames", "cover", "musicTracks", "newImages", "settings.json", "logs"]

class bcolors:
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    OKGREEN = '\033[92m'
    ENDC = '\033[0m'

def download_file(version: str):
    print(version)
    """Download the latest version of the project.

    Args:
        version (str): the version to download. If None, download the latest version.

    Returns:
        BytesIO: the downloaded zip file.
    """
    print(f"Downloading Vocard version: {version}")
    response = requests.get(IUFI_URL + version + ".zip")
    if response.status_code == 404:
        print(f"{bcolors.FAIL}Warning: Version not found!{bcolors.ENDC}")
        exit()
    print("Download Completed")
    return response

def install(response, version):
    print(response, version)
    """Install the downloaded version of the project.

    Args:
        response (BytesIO): the downloaded zip file.
        version (str): the version to install.
    """
    user_input = input(f"{bcolors.WARNING}--------------------------------------------------------------------------\n"
                           "Note: Before proceeding, please ensure that there are no personal files or\n" \
                           "sensitive information in the directory you're about to delete. This action\n" \
                           "is irreversible, so it's important to double-check that you're making the \n" \
                           f"right decision. {bcolors.ENDC} Continue with caution? (Y/n) ")
        
    if user_input.lower() in ["y", "yes"]:
        print("Installing ...")
        zfile = zipfile.ZipFile(BytesIO(response.content))
        zfile.extractall(ROOT_DIR)

        source_dir = os.path.join(ROOT_DIR, f"IUFI-{version}")
        if os.path.exists(source_dir):
            for filename in os.listdir(ROOT_DIR):
                if filename in IGNORE_FILES + [f"IUFI-{version}"]:
                    continue

                filename = os.path.join(ROOT_DIR, filename)
                if os.path.isdir(filename):
                    shutil.rmtree(filename)
                else:
                    os.remove(filename)
            for filename in os.listdir(source_dir):
                shutil.move(os.path.join(source_dir, filename), os.path.join(ROOT_DIR, filename))
            os.rmdir(source_dir)
        print(f"{bcolors.OKGREEN}Version {version} installed Successfully! Run `python main.py` to start your bot{bcolors.ENDC}")
    else:
        print("Update canceled!")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Update script for IUFI.')
    parser.add_argument('-l', '--latest', action='store_true', help='Install the latest version of the IUFI from Github')
    parser.add_argument('-b', '--branch', type=str, help='Install the specified branch of the IUFI')
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()

    if args.latest:
        response = download_file(f"refs/heads/main")
        install(response, "main")
        
    elif args.branch:
        branch = args.branch
        response = download_file(f"refs/heads/{branch}")
        install(response, branch)
        pass

    else:
        print(f"{bcolors.FAIL}No arguments provided. Run `python update.py -h` for help.{bcolors.ENDC}")

if __name__ == "__main__":
    main()