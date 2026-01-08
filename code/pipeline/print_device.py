from lib import get_db
import sys


def print_device(device_id: str):
    db = get_db()
    device = db.devices[device_id]
    print(device)


if __name__ == "__main__":
    print_device(sys.argv[1])
