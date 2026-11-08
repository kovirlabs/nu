import os

import platformdirs

# The default directory for application data (i.e., configuration). The
# MU_DATA_DIR environment variable puts it somewhere else: the test suite uses
# it so it never touches a real one, and it gives a throwaway profile.
DATA_DIR = os.environ.get("MU_DATA_DIR") or platformdirs.user_data_dir(
    appname="mu", appauthor="python"
)

# The name of the default virtual environment used by Mu.
VENV_NAME = "mu_venv"

# The directory containing default virtual environment.
VENV_DIR = os.path.join(DATA_DIR, VENV_NAME)

# Maximum line length for using both in Check and Tidy
MAX_LINE_LENGTH = 88

# The user's home directory (where the default workspace goes); MU_HOME_DIR
# overrides it, as MU_DATA_DIR does DATA_DIR.
HOME_DIRECTORY = os.environ.get("MU_HOME_DIR") or os.path.expanduser("~")

# Name of the directory within the home folder to use by default
WORKSPACE_NAME = "mu_code"
