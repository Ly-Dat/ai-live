@echo off
chcp 65001

pip install -r requirements_bilibili.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements_dy.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements_ks.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements_bilibili.txt -i https://pypi.python.org/simple/
pip install -r requirements_dy.txt -i https://pypi.python.org/simple/
pip install -r requirements_ks.txt -i https://pypi.python.org/simple/

echo If everything succeeded you're done; if any failed, please install them manually
@REM cmd /k