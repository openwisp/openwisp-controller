import subprocess
import sys

import requests
from openwisp_utils.releaser.release import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Release process terminated by user.")
        sys.exit(1)
    except (
        subprocess.CalledProcessError,
        requests.RequestException,
        RuntimeError,
        FileNotFoundError,
    ) as e:
        print(f"\n❌ An error occurred: {e}", file=sys.stderr)
        if isinstance(e, subprocess.CalledProcessError):
            print(f"Error Details: {e.stderr}", file=sys.stderr)
        sys.exit(1)
