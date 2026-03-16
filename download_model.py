import os
os.environ["U2NET_HOME"] = "/tmp"
from rembg import new_session
print("Pre-downloading u2netp...")
sess = new_session("u2netp")
print("Done!")
