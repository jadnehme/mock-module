import asyncio
from viam.module.module import Module
try:
    from models.mock_module import MockModule
except ModuleNotFoundError:
    # when running as local module with run.sh
    from .models.mock_module import MockModule


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
