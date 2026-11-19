import os
from pathlib import Path
os.environ["DATA_DIR"]="/tmp/serial-holdings-pytest"
# 规则版本不变时同文同批次；每轮测试从空库开始，避免上一轮的旧结果残留
for stale in Path("/tmp/serial-holdings-pytest").glob("runs.sqlite*"):
    stale.unlink()
import pytest
from app.pipeline import run,sample_text
@pytest.fixture
def sample(): return sample_text()
@pytest.fixture
def result(sample): return run(sample)
