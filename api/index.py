import sys
import os

# Ensure the parent directory (project root) is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Import the Flask app instance from SSAT dashboard
from SSAT.ssat.visualize import app

# Vercel serverless runtime expects 'app' instance at module level
