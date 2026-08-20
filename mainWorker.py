from pathlib import Path

import dotenv

dotenv.load_dotenv(Path(__file__).with_name(".env"))

from workers.promax_worker import main


if __name__ == "__main__":
    raise SystemExit(main())
